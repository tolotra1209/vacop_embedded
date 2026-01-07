# File: OBU.py
# This file is part of the VACOP project.
# Created by Rémi Myard
# Modified by Iban LEGINYORA and Tinhinane AIT-MESSAOUD
# This program is free software: you can redistribute it and/or modify
# it under the terms of the MIT License

# Execute : python3 -m back_part.OBU -v


from CAN_system.CANSystem_p import CANSystem
from .DualMotorController import DualMotorController
from .SteerController import SteerController
import argparse
import time
import threading

MAX_TORQUE = 20.0
TORQUE_SCALE = MAX_TORQUE / 1023.0
STAY_ERROR_MODE_SLEEP = 3.0 # Stay in error mode for 3 sec before going to INITIALIZE MODE
BTN_AUTO_MODE = 0
BTN_MANUAL_MODE = 1 

class OBU:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.readyComponents = set()
        self.mode = "INIT"
        self.state = None
        self.running = True

        self.canSystem = CANSystem(verbose=self.verbose, device_name='OBU')
        self.canSystem.set_callback(self.on_can_message)

        self.motors = None # créé plus tard
        self.steer  = SteerController(self.canSystem, kp=0.8, max_step=30, verbose=self.verbose)

        self.canSystem.start_listening()

        self._brake_ready_evt = threading.Event()
        self._steer_ready_evt = threading.Event()
        self._motor_ready_evt = threading.Event()

         # --- Etats des boutons (None = inconnu au demarrage) 
        self.btn_auto_manu = None   # 1 => MANUAL, 0 => AUTO
        self.btn_reverse   = None   # 1 => FORWARD, 0 => REVERSE

        self._retry_scheduled = False
        self._change_mode("INITIALIZE")

    # === CAN message Reception ===
    def on_can_message(self, _, messageType, data):
        """Callback function"""
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
        # ACK au module BRAKE (le front qui a envoyé brake_rdy)
        self.canSystem.can_send("BRAKE", "ready_ack", 0)
        self._brake_ready_evt.set()

        # Si BRAKE redémarre pendant que nous sommes déjà en RUN, relancer la séquence minimale.
        if self.mode != "INITIALIZE":
            self.canSystem.can_send("BRAKE", "start", 0)

    def _handle_steer_ready(self):
        print("[OBU] steer_rdy received")
        self.readyComponents.add("steer_rdy")
        # ACK au module STEER (le front de la direction)
        self.canSystem.can_send("STEER", "ready_ack", 0)
        self._steer_ready_evt.set()

        # Si STEER redémarre pendant MANUAL/AUTO, renvoyer les ordres essentiels.
        if self.mode != "INITIALIZE":
            self.canSystem.can_send("STEER", "start", 0)

            # Réappliquer l'état steer_enable attendu par le front.
            if self.mode == "AUTO":
                self.steer.enable(True)
            else:
                self.steer.enable(False)

    def _handle_accel_pedal(self, data):
        if self.mode != "MANUAL":
            return
        try:
            torque_value = float(data) * TORQUE_SCALE
            if self.motors :
                self.motors.set_torque(torque_value)

            if self.verbose : 
                print(f"[MANUAL] acceleration_pedal = {data} => torque_value = {torque_value:.2f}")
        except Exception:
                print(f"ERROR: Invalid torque data: {data}")

    def _handle_brake_enable(self):
        print("Shutdown requested via brake_enable.")
        self.shutdown()

    def _handle_bouton_on_off(self, data):
        # Temporary fallback to reverse handler since reverse button is not physically connected
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

        if self.mode != "INITIALIZE" :
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
                #check button btn_auto_manu saved state and change mode accordingly

                if self.btn_auto_manu == BTN_MANUAL_MODE :
                    self._change_mode("MANUAL")

                elif  self.btn_auto_manu == BTN_AUTO_MODE :
                    self._change_mode("AUTO")

                else:
                    # valeur inattendue -> fail-safe
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
         # On attend passivement les *_rdy (ACK envoyés plus haut)
        print("[OBU] Initialization phase started.")
        try:
            if self.motors is None :
                print("[OBU] Trying to connect to SOLO…")
                self.motors = DualMotorController(verbose=self.verbose)
                print("[OBU] [MOTOR] Communication Established successfully!")

            self._motor_ready_evt.set()
        except Exception as e:
            print(f"[OBU] [MOTOR] Error during motor init: {e}")
            self.motors = None
            self._motor_ready_evt.clear()


    def _enter_start_mode(self):
        # start BRAKE si brake_rdy reçu
        self.canSystem.can_send("BRAKE", "start", 0)
        time.sleep(0.2)
        # start STEER seulement si reçu
        if "steer_rdy" in self.readyComponents:
            self.canSystem.can_send("STEER", "start", 0)

    def _enter_manual_mode(self):
        print("MANUAL mode activated.")
        self._apply_direction_from_button()
        self.steer.enable(False)
        if self.motors :
       	    self.motors.set_torque(0.0)

    def _enter_auto_mode(self):
        print("AUTO mode activated.")
        self._apply_direction_from_button()
        self.steer.enable(True)
        if self.motors :
            self.motors.set_torque(0.0)

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

    # === State Handlers ===

    def _enter_forward_state(self):
        if self.motors :
            self.motors.set_forward()

    def _enter_reverse_state(self):
        if self.motors :
            self.motors.set_reverse()

    # === Others ===
    def _apply_direction_from_button(self):
        """Align internal state with the last known reverse button value."""
        desired_state = "FORWARD"
        if self.btn_reverse is not None:
            desired_state = "FORWARD" if self.btn_reverse == 1 else "REVERSE"
        if self.state != desired_state:
            self._change_state(desired_state)

    def stop_all(self):
        """Stoppe tous les actionneurs (moteurs, steer...) proprement."""
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
            # Stop modules
            self.canSystem.can_send("BRAKE", "stop", 0)
            self.canSystem.can_send("STEER", "stop", 0)
            # Stop moteurs proprement
            self.stop_all()
            # Stop bus CAN
            self.canSystem.stop()
        except Exception as e:
            print(f"Error during shutdown: {e}")
        print("System shutdown complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OBU system")
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    
    obu = OBU(verbose=args.verbose)

    try:
        TICK = 0.05
        while obu.running:
            #Steer control in "AUTO" mode
            if obu.mode == "AUTO":
                obu.steer.update()

            time.sleep(TICK)
    except KeyboardInterrupt:
        print("KeyboardInterrupt received.")
        obu.shutdown()
