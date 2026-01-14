# File: OBU.py
# This file is part of the VACOP project.
# Modified for ROBUSTNESS, SAFETY and INTERRUPTIBLE TRAJECTORY
# FIX: Auto Mode Detection at Startup

import os
import time
import threading
import argparse
from dotenv import load_dotenv

# Import de vos modules
from CAN_system.CANSystem_p import CANSystem
from .DualMotorController import DualMotorController
from .SteerController import SteerController

load_dotenv()

# --- CONSTANTES ---
MAX_TORQUE = 60.0
TORQUE_SCALE = MAX_TORQUE / 1023.0
STAY_ERROR_MODE_SLEEP = 5.0 # Temps d'attente avant de retenter après une erreur
BTN_AUTO_MODE = 0
BTN_MANUAL_MODE = 1

# Paramètres de Robustesse
TORQUE_DEADBAND = 0.5   # Evite de spammer le moteur pour des petits changements
MAX_RETRIES = 3         # Nombre d'essais en cas d'erreur de com (bruit électrique)
RETRY_DELAY = 0.05      # Temps d'attente entre deux essais (50ms)

class OBU:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.readyComponents = set()
        self.mode = "INIT"
        self.state = None
        self.running = True

        # Flag pour savoir si l'init a réussi ou échoué
        self.motors_initialized = False

        # 1. LE VERROU (MUTEX)
        self.motor_lock = threading.Lock()

        self.canSystem = CANSystem(verbose=self.verbose, device_name='OBU')
        self.canSystem.set_callback(self.on_can_message)

        self.motors = None
        self.steer = SteerController(self.canSystem, kp=0.8, max_step=30, verbose=self.verbose)

        self.last_torque_sent = -999.0
        self.current_direction = None
        self.btn_auto_manu = None
        self.btn_reverse   = None

        self.canSystem.start_listening()

        self._brake_ready_evt = threading.Event()
        self._steer_ready_evt = threading.Event()
        self._motor_ready_evt = threading.Event()

        # Démarrage
        self._change_mode("INITIALIZE")

    # === CAN message Reception ===
    def on_can_message(self, _, messageType, data):
        match messageType:
            case "brake_rdy": self._handle_brake_ready()
            case "steer_rdy": self._handle_steer_ready()
            case "accel_pedal": self._handle_accel_pedal(data)
            case "brake_enable": self.shutdown()
            case "bouton_park": print("PARK not implemented")
            case "bouton_auto_manu": self._handle_bouton_auto_manu(data)
            case "bouton_on_off": self._handle_bouton_reverse(data)
            case "bouton_reverse": self._handle_bouton_reverse(data)
            case "steer_pos_real": self.steer.on_feedback(data)
            case "steer_target":
                if self.mode == "AUTO": self.steer.set_target(data)
            case _: pass

    # === CAN Handlers ===
    def _handle_brake_ready(self):
        print("[OBU] brake_rdy received")
        self.readyComponents.add("brake_rdy")
        self.canSystem.can_send("BRAKE", "ready_ack", 0)
        self._brake_ready_evt.set()
        if self.mode == "START":
            self.canSystem.can_send("BRAKE", "start", 0)

    def _handle_steer_ready(self):
        print("[OBU] steer_rdy received")
        self.readyComponents.add("steer_rdy")
        self.canSystem.can_send("STEER", "ready_ack", 0)
        self._steer_ready_evt.set()
        if self.mode == "START":
            self.canSystem.can_send("STEER", "start", 0)

    def _handle_accel_pedal(self, data):
        if self.mode != "MANUAL": return
        try:
            val = float(data) * TORQUE_SCALE
            self._safe_set_torque(val)
        except: pass

    def _handle_bouton_reverse(self, data):
        try:
            val = int(data)
            self.btn_reverse = val
            # Changement de direction autorisé uniquement si pas en init
            if self.mode not in ["INITIALIZE", "ERROR", "RESTART"]:
                self._apply_direction_from_button()
        except: pass

    def _handle_bouton_auto_manu(self, data):
        try:
            val = int(data)
            # Log pour debug
            if self.btn_auto_manu != val:
                print(f"[OBU] Button AUTO/MANU changed to {val}")
            
            self.btn_auto_manu = int(data)
            
            if self.mode not in ["INITIALIZE", "ERROR", "RESTART"]:
                newMode = "MANUAL" if int(data) == 1 else "AUTO"
                # On ne change de mode que si c'est différent de l'actuel
                if self.mode != newMode:
                    self._change_mode(newMode)
        except: pass
    # === Mode Management ===
    def _change_mode(self, newMode):
        # SÉCURITÉ : Si on quitte le mode AUTO, on force l'arrêt immédiat.
        if self.mode == "AUTO" and newMode != "AUTO":
            print("[OBU] Exiting AUTO mode -> SAFETY STOP")
            self._safe_set_torque(0.0)

        # Protection : On ne peut pas passer en START/AUTO/MANUAL si les moteurs sont HS
        if newMode in ["START", "AUTO", "MANUAL"] and not self.motors_initialized:
            print(f"[OBU] CANNOT ENTER {newMode}: Motors not initialized -> Going to ERROR")
            threading.Thread(target=self._change_mode, args=("ERROR",)).start()
            return

        print(f"[OBU] Changing Mode: {self.mode} -> {newMode}")
        self.mode = newMode

        match newMode:
            case "INITIALIZE":
                self._brake_ready_evt.clear()
                self._steer_ready_evt.clear()
                self._motor_ready_evt.clear()
                self._initialize_components()
                self._wait_for_ready()
                self._change_mode("START")

            case "START":
                # Vérification Stricte
                if not self.motors_initialized:
                    print("[OBU] START rejected: Motors Missing.")
                    self._change_mode("ERROR")
                    return

                self._enter_start_mode()
                
                # --- LOGIQUE CORRIGÉE ---
                if self.btn_auto_manu == BTN_AUTO_MODE:
                    print(f"[OBU] Switch detected as AUTO ({self.btn_auto_manu}) -> GOING AUTO")
                    self._change_mode("AUTO")
                else:
                    # Si c'est MANUEL (1) ou INCONNU (None), on va en MANUEL par sécurité
                    print(f"[OBU] Switch is MANUAL or UNKNOWN ({self.btn_auto_manu}) -> GOING MANUAL")
                    self._change_mode("MANUAL")

            case "RESTART":
                print("[OBU] ENTER: RESTART")
                self.canSystem.can_send("BRAKE", "restart", 0)
                self.canSystem.can_send("STEER", "restart", 0)
                time.sleep(1.0)
                self._change_mode("INITIALIZE")

            case "MANUAL":
                print("[OBU] ENTER: MANUAL")
                self.steer.enable(False)
                self._safe_set_torque(0.0) 
                self._apply_direction_from_button()

            case "AUTO":
                print("[OBU] ENTER: AUTO")
                self.steer.enable(True)
                self._safe_set_torque(0.0)
                threading.Thread(target=self.apply_trajectory, daemon=True).start()

            case "ERROR":
                print(f"[OBU] !!! SYSTEM ERROR !!! waiting {STAY_ERROR_MODE_SLEEP}s.")
                self.stop_all() 
                time.sleep(STAY_ERROR_MODE_SLEEP)
                self._change_mode("RESTART")

            case "OFF":
                self.shutdown()

            case _:
                self._change_mode("OFF")

    # === Initialisation et Attente ===
    def _wait_for_ready(self):
        print("[OBU] Waiting for components (max 60s)...")
        events = {"BRAKE": self._brake_ready_evt, "STEER": self._steer_ready_evt, "MOTOR": self._motor_ready_evt}
        pending = set(events.keys())
        timeout = time.time() + 60 
        
        while pending and time.time() < timeout:
            for name in list(pending):
                if events[name].wait(timeout=0.1):
                    print(f"[OBU] {name} ready")
                    pending.remove(name)
        if pending: print(f"[OBU] WARN: Timeout waiting for {pending}")

    def _initialize_components(self):
        print("[OBU] Init Motors...")
        self.motors_initialized = False
        try:
            if self.motors is None:
                self.motors = DualMotorController(verbose=self.verbose)
            self.motors.configure()
            print("[OBU] Motors Initialized Successfully.")
            self.motors_initialized = True
            self._motor_ready_evt.set()
        except Exception as e:
            print(f"[OBU] MOTOR INIT FAILED: {e}")
            self.motors = None
            self.motors_initialized = False
            self._motor_ready_evt.set()

    def _enter_start_mode(self):
        self.canSystem.can_send("BRAKE", "start", 0)
        time.sleep(0.2)
        if "steer_rdy" in self.readyComponents:
            self.canSystem.can_send("STEER", "start", 0)

    # === Gestion État (Avant/Arrière) ===
    def _change_state(self, newState):
        self.state = newState
        if newState == "FORWARD": self._execute_motor_command("set_forward")
        elif newState == "REVERSE": self._execute_motor_command("set_reverse")
        elif newState == "ERROR": self._change_mode("ERROR")

    def _apply_direction_from_button(self):
        desired_state = "FORWARD"
        if self.btn_reverse is not None:
            desired_state = "FORWARD" if self.btn_reverse == 1 else "REVERSE"
        
        # On applique l'état si différent ou si pas encore défini (None)
        if self.state != desired_state or self.state is None:
            self._change_state(desired_state)

    # === CŒUR DU SYSTÈME : COMMANDE MOTEUR BLINDÉE ===
    def _execute_motor_command(self, command_type, value=None):
        """
        Gère l'envoi d'ordres aux moteurs avec Lock et Retries.
        """
        if not self.motors: 
            if self.mode not in ["ERROR", "RESTART", "INITIALIZE"]:
                self._change_mode("ERROR")
            return

        with self.motor_lock: 
            attempts = 0
            while attempts < MAX_RETRIES:
                try:
                    if command_type == "set_torque": self.motors.set_torque(value)
                    elif command_type == "set_forward": self.motors.set_forward()
                    elif command_type == "set_reverse": self.motors.set_reverse()
                    elif command_type == "stop": self.motors.stop_motor()
                    return # Succès
                except Exception as e:
                    attempts += 1
                    print(f"[OBU] UART Fail ({attempts}/{MAX_RETRIES}): {e}")
                    time.sleep(RETRY_DELAY)
            
            print(f"[OBU] CRITICAL: Cannot execute {command_type} -> GOING TO ERROR MODE")
            threading.Thread(target=self._change_mode, args=("ERROR",)).start()

    def _safe_set_torque(self, torque_val):
        # Anti-flood
        if abs(torque_val - self.last_torque_sent) < TORQUE_DEADBAND and torque_val != 0.0: return
        self._execute_motor_command("set_torque", torque_val)
        self.last_torque_sent = torque_val

    # === Trajectoire ===
    def _responsive_sleep(self, duration):
        steps = int(duration / 0.1)
        for _ in range(steps):
            if self.mode != "AUTO": return False
            time.sleep(0.1)
        return True 

    def apply_trajectory(self):
        print("[OBU] Applying trajectory sequence...")
        try:
            if not self._responsive_sleep(1.0): return
            self._execute_motor_command("set_forward")
            self._safe_set_torque(60.0)
            
            if not self._responsive_sleep(30.0): return
            self._safe_set_torque(0.0)

            self.apply_extend_brake()
            if not self._responsive_sleep(5.0): return

            self.apply_release_brake()
            if not self._responsive_sleep(0.01): return

            if not self._responsive_sleep(1.0): return
            self._execute_motor_command("set_reverse")
            self._safe_set_torque(60.0)
            
            if not self._responsive_sleep(30.0): return
            self._safe_set_torque(0.0)

            self.apply_extend_brake()
            if not self._responsive_sleep(5.0): return

            self.apply_release_brake()
            if not self._responsive_sleep(0.01): return
            
            self._execute_motor_command("set_forward")
            print("[OBU] Trajectory complete.")

        except Exception as e:
            print(f"[OBU] Trajectory Error: {e}")
            self._change_mode("ERROR")

    # === Helpers ===
    def apply_extend_brake(self):
        self.canSystem.can_send("BRAKE", "brake_pos_set", 670)
        
    def apply_release_brake(self):
        self.canSystem.can_send("BRAKE", "brake_pos_set", 288)

    def stop_all(self):
        print("[OBU] STOP ALL")
        try:
            if self.motors:
                self.motors.stop_motor()
        except: pass
        try: self.steer.enable(False)
        except: pass

    def shutdown(self):
        if not self.running: return
        self.running = False
        try:
            self.stop_all()
            self.canSystem.can_send("BRAKE", "stop", 0)
            self.canSystem.can_send("STEER", "stop", 0)
            self.canSystem.stop()
        except: pass
        print("Shutdown complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    try:
        obu = OBU(verbose=args.verbose)
        while obu.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt -> Stopping.")
        obu.shutdown()
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        if 'obu' in locals(): obu.shutdown()