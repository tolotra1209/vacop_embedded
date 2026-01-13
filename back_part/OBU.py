# File: OBU.py
# This file is part of the VACOP project.
# Created by Rémi Myard
# Modified by Iban LEGINYORA and Tinhinane AIT-MESSAOUD
# MQTT integration for gamepad commands
# Execute : python3 -m back_part.OBU -v

import os
import json
import time
import threading
import argparse
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

from CAN_system.CANSystem_p import CANSystem
from .DualMotorController import DualMotorController
from .SteerController import SteerController

# Load environment variables
load_dotenv()

# MQTT settings from .env
# MQTT_BROKER_URL = os.getenv("MQTT_BROKER_URL")
# MQTT_USERNAME = os.getenv("MQTT_USERNAME")
# MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
# MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID")
# MQTT_TOPIC = os.getenv("MQTT_COMMAND_BASE")

# Constants
MAX_TORQUE = 20.0
TORQUE_SCALE = MAX_TORQUE / 1023.0
STAY_ERROR_MODE_SLEEP = 3.0
BTN_AUTO_MODE = 0
BTN_MANUAL_MODE = 1

# Constants for AUTO mode
MAX_AUTO_SPEED = 30.0  # km/h maximum
TORQUE_AT_MAX_SPEED = 15.0  # Nm at max speed

class OBU:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.readyComponents = set()
        self.mode = "INIT"
        self.state = None
        self.running = True

        self.canSystem = CANSystem(verbose=self.verbose, device_name='OBU')
        self.canSystem.set_callback(self.on_can_message)

        self.motors = None
        self.steer = SteerController(self.canSystem, kp=0.8, max_step=30, verbose=self.verbose)

        self.last_steering = 0.0
        self.last_throttle = 0.0

        self.canSystem.start_listening()

        self._brake_ready_evt = threading.Event()
        self._steer_ready_evt = threading.Event()
        self._motor_ready_evt = threading.Event()

        self.current_direction = None  # "FORWARD" or "REVERSE"

        # --- MQTT Client ---
        # self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1, client_id=MQTT_CLIENT_ID)
        # self.mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        # self.mqtt_client.on_connect = self.on_mqtt_connect
        # self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        # self.mqtt_client.on_message = self.on_mqtt_message
        # self.mqtt_client.connect(MQTT_BROKER_URL, 1883, 60)
        # self.mqtt_client.loop_start()

        # --- Etats des boutons (None = inconnu au demarrage)
        self.btn_auto_manu = None   # 1 => MANUAL, 0 => AUTO
        self.btn_reverse   = None   # 1 => FORWARD, 0 => REVERSE

        self._retry_scheduled = False
        self._change_mode("INITIALIZE")

    # === MQTT Callbacks ===
    # def on_mqtt_connect(self, client, userdata, flags, rc):
    #     print(f"[MQTT] Connected with result code {rc}")
    #     client.subscribe(MQTT_TOPIC)

    # def on_mqtt_disconnect(self, client, userdata, reason_code, properties):
    #     try:
    #         rc_val = int(reason_code)
    #     except Exception:
    #         rc_val = reason_code
    #     print(f"[MQTT] Disconnected (reason_code={rc_val})")

    #     self.motors.set_torque(0.0)
    #     self.mqtt_client.on_mqtt_connect()

    # def on_mqtt_message(self, client, userdata, msg):
    #     try:
    #         data = json.loads(msg.payload.decode("utf-8"))
    #         throttle = float(data["vector"]["throttle"])
    #         steering = float(data["vector"]["steering"])
    #         ts = int(data["ts"])
            
    #         self.last_throttle = throttle
    #         self.last_steering = steering
    #         self.last_ts = ts
    #         self.apply_gamepad_command(throttle, steering)
    #     except Exception as e:
    #         print(f"[MQTT] Command handling failed: {e}")


    # === CAN message Reception ===
    def on_can_message(self, _, messageType, data):
        match messageType:
            case "brake_rdy":
                self._handle_brake_ready()
            case "steer_rdy":
                self._handle_steer_ready()
            case "accel_pedal":
                self._handle_accel_pedal(data)
            case "brake_enable":
                self._handle_brake_enable()
            case "bouton_park":
                self._handle_bouton_park()
            case "bouton_auto_manu":
                self._handle_bouton_auto_manu(data)
            case "bouton_on_off":
                self._handle_bouton_on_off(data)
            case "bouton_reverse":
                self._handle_bouton_reverse(data)
            case "steer_pos_real":
                self.steer.on_feedback(data)
            case "steer_target":
                if self.mode == "AUTO":
                    self.steer.set_target(data)
            case _:
                self._handle_event(messageType, data)

    # === CAN Message Handlers ===
    def _handle_brake_ready(self):
        print("[OBU] brake_rdy received")
        self.readyComponents.add("brake_rdy")
        self.canSystem.can_send("BRAKE", "ready_ack", 0)
        self._brake_ready_evt.set()
        if self.mode != "INITIALIZE":
            self.canSystem.can_send("BRAKE", "start", 0)

    def _handle_steer_ready(self):
        print("[OBU] steer_rdy received")
        self.readyComponents.add("steer_rdy")
        self.canSystem.can_send("STEER", "ready_ack", 0)
        self._steer_ready_evt.set()
        if self.mode != "INITIALIZE":
            self.canSystem.can_send("STEER", "start", 0)
            if self.mode == "AUTO":
                self.steer.enable(True)
            else:
                self.steer.enable(False)

    def _handle_accel_pedal(self, data):
        if self.mode != "MANUAL":
            return
        try:
            torque_value = float(data) * TORQUE_SCALE
            if self.motors:
                self.motors.set_torque(torque_value)
            if self.verbose:
                print(f"[MANUAL] acceleration_pedal = {data} => torque_value = {torque_value:.2f}")
        except Exception:
            print(f"ERROR: Invalid torque data: {data}")

    def _handle_brake_enable(self):
        print("Shutdown requested via brake_enable.")
        self.shutdown()

    def _handle_bouton_on_off(self, data):
        self._handle_bouton_reverse(data)

    def _handle_bouton_reverse(self, data):
        try:
            val = int(data)
            print(f"[OBU] bouton_reverse = {val}")
            self.btn_reverse = val
        except Exception:
            print(f"[OBU] WARN: invalid reverse button value: {data}")
            return
        if self.mode != "INITIALIZE":
            newState = "FORWARD" if val == 1 else "REVERSE"
            print(f"[DEBUG] newState = {newState}")
            self._change_state(newState)

    def _handle_bouton_auto_manu(self, data):
        try:
            val = int(data)
            print(f"[OBU] bouton_auto_manu = {val}")
            self.btn_auto_manu = int(data)
        except Exception:
            print(f"[OBU] WARN: invalid auto/manu button value: {data}")
            return
        if self.mode != "INITIALIZE":
            newMode = "MANUAL" if int(data) == 1 else "AUTO"
            self._change_mode(newMode)

    def _handle_bouton_park(self):
        print("PARK button pressed: behavior not implemented.")

    def _handle_event(self, messageType, data):
        print(f"[Unhandled] {messageType}, data: {data}, state: {self.state}")

    # === Mode Management ===
    def _change_mode(self, newMode):
        self.mode = newMode
        match newMode:
            case "INITIALIZE":
                print("[OBU] Entering INITIALIZE mode")
                self._brake_ready_evt.clear()
                self._steer_ready_evt.clear()
                self._motor_ready_evt.clear()
                self._initialize_components()
                self._wait_for_ready()
                self._change_mode("START")
            case "START":
                print("[OBU] Entering START mode")
                self._enter_start_mode()
                if self.btn_auto_manu == BTN_MANUAL_MODE:
                    self._change_mode("MANUAL")
                elif self.btn_auto_manu == BTN_AUTO_MODE:
                    self._change_mode("AUTO")
                else:
                    self._change_mode("MANUAL")
            case "MANUAL":
                print("[OBU] Entering MANUAL mode")
                self._enter_manual_mode()
            case "AUTO":
                print("[OBU] Entering AUTO mode")
                self._enter_auto_mode()
            case "ERROR":
                print("[OBU] Entering ERROR mode")
                time.sleep(STAY_ERROR_MODE_SLEEP)
                self._change_mode("INITIALIZE")
            case "OFF":
                self.shutdown()
            case _:
                print(f"Unknown mode '{newMode}'")
                self._change_mode("OFF")

    # === Mode Handlers ===
    def _wait_for_ready(self):
        print("[OBU] Waiting for BRAKE, STEER and MOTOR to be ready…")
        events = {
            "BRAKE": self._brake_ready_evt,
            "STEER": self._steer_ready_evt,
            "MOTOR": self._motor_ready_evt,
        }
        pending = set(events.keys())
        while pending:
            for name in list(pending):
                evt = events[name]
                if evt.wait(timeout=0.1):
                    print(f"[OBU]  {name} ready")
                    pending.remove(name)
        print("[OBU]  All required components ready.")

    def _initialize_components(self):
        print("[OBU] Initialization phase started.")
        try:
            if self.motors is None:
                print("[OBU] Trying to connect to SOLO…")
                self.motors = DualMotorController(verbose=self.verbose)
                print("[OBU] [MOTOR] Configuring SOLO (UART)...")
                self.motors.configure()
                print("[OBU] [MOTOR] Communication Established successfully!")
            self._motor_ready_evt.set()
        except Exception as e:
            print(f"[OBU] [MOTOR] Error during motor init: {e}")
            self.motors = None
            self._motor_ready_evt.clear()

    def _enter_start_mode(self):
        self.canSystem.can_send("BRAKE", "start", 0)
        time.sleep(0.2)
        if "steer_rdy" in self.readyComponents:
            self.canSystem.can_send("STEER", "start", 0)

    def _enter_manual_mode(self):
        print("MANUAL mode activated.")
        self._apply_direction_from_button()
        self.steer.enable(False)
        if self.motors:
            self.motors.set_torque(0.0)

    def _enter_auto_mode(self):
        print("AUTO mode activated.")
        self.steer.enable(True)
        if self.motors:
            self.motors.set_torque(0.0)
        self.apply_gamepad_command(self.last_throttle, self.last_steering)

    # === State Management ===
    def _change_state(self, newState):
        self.state = newState
        match newState:
            case "FORWARD":
                self._enter_forward_state()
            case "REVERSE":
                self._enter_reverse_state()
            case "ERROR":
                self._change_mode("ERROR")

    def _enter_forward_state(self):
        if self.motors:
            self.motors.set_forward()

    def _enter_reverse_state(self):
        if self.motors:
            self.motors.set_reverse()

    def _apply_direction_from_button(self):
        desired_state = "FORWARD"
        if self.btn_reverse is not None:
            desired_state = "FORWARD" if self.btn_reverse == 1 else "REVERSE"
        if self.state != desired_state:
            self._change_state(desired_state)

    def apply_gamepad_command(self, throttle: float, steering: float):
        if not self.motors:
            return
            
        # if ts :
        #     self.set_torque(0.0)
            
        desired_direction = None
        if throttle > 0:
            desired_direction = "FORWARD"
        elif throttle < 0:
            desired_direction = "REVERSE"

        if desired_direction and desired_direction != self.current_direction:
            self.motors.set_torque(0.0)
            time.sleep(0.01)
            if desired_direction == "FORWARD":
                self.motors.set_forward()
            else:
                self.motors.set_reverse()
            self.current_direction = desired_direction

        torque = abs(throttle) * 8.0
        self.motors.set_torque(torque)

        steering_target = int((steering + 1.0) / 2.0 * 1023)
        steering_target = max(0, min(1023, steering_target))
        
        if not hasattr(self, 'last_steering_target'):
            self.last_steering_target = steering_target
        
        if abs(steering_target - self.last_steering_target) > 10:
            self.canSystem.can_send("STEER", "steer_target", steering_target)
            self.last_steering_target = steering_target

    def apply_direction():

        pass
    
    def apply_brake(self):
        self.canSystem.can_send("BRAKE", "brake_pos_set", 670)
        time.sleep(2)
        self.canSystem.can_send("BRAKE", "brake_pos_set", 288)

    def stop_all(self):
        if self.motors:
            try:
                print("[OBU] Stopping motors...")
                self.motors.stop_motor()
            except Exception as e:
                print(f"[OBU] Error stopping motor: {e}")
        try:
            self.steer.enable(False)
        except Exception:
            pass
    
    def shutdown(self):
        if not self.running:
            return
        print("Shutting down system...")
        self.running = False
        try:
            self.canSystem.can_send("BRAKE", "stop", 0)
            self.canSystem.can_send("STEER", "stop", 0)
            self.stop_all()
            self.canSystem.stop()
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        except Exception as e:
            print(f"Error during shutdown: {e}")
        print("System shutdown complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OBU system")
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    obu = OBU(verbose=args.verbose)

    try:
        test_positions = [512, 0, 512, 1023]
        counter = 0
        while obu.running:
            position = test_positions[counter % len(test_positions)]
            obu.canSystem.can_send("STEER", "steer_pos_set", position)
            counter += 1
            time.sleep(2)
    except KeyboardInterrupt:
        print("KeyboardInterrupt received.")
        obu.shutdown()