# middle_part/DeviceManager.py
import argparse
import time
import RPi.GPIO as GPIO

from .CANAdapter import CANAdapter
from .steer_part import SteerController
from .button_part import ButtonController
from AbstractClasses import AbstractController


class DeviceManager:
    def __init__(self, controllers: list[AbstractController], verbose=False):
        self.verbose = verbose
        self.controllers = controllers
        self.running = True

    def _print(self, *a):
        if self.verbose:
            print("[MIDDLE PART]", *a)

    def run(self):
        self._print("=== MIDDLE PART START ===")

        # 1) INITIALIZE
        self._print("Initializing all controllers…")
        for c in self.controllers:
            try:
                if hasattr(c, "initialize"):
                    c.initialize()
            except Exception as e:
                self._print(f"[WARN] init failed for {c.__class__.__name__}: {e}")

        # 2) SELF-CHECK
        all_ok = True
        for c in self.controllers:
            if hasattr(c, "self_check"):
                try:
                    if not c.self_check():
                        self._print(f"[ERR] self_check FAILED for {c.__class__.__name__}")
                        all_ok = False
                except Exception as e:
                    self._print(f"[ERR] self_check exception for {c.__class__.__name__}: {e}")
                    all_ok = False

        if not all_ok:
            self._print("[ERR] Some controllers failed self_check. Abort.")
            self.stop_all()
            return

        # 3) READY PHASE — SteerController envoie steer_rdy ici
        self._print("Sending READY signals…")
        for c in self.controllers:
            if hasattr(c, "send_ready"):
                try:
                    c.send_ready()
                except Exception as e:
                    self._print(f"[WARN] send_ready() failed for {c.__class__.__name__}: {e}")

        # 4) WAIT FOR START
        self._print("Waiting for 'start' from OBU…")
        started = False
        while not started and self.running:
            for c in self.controllers:
                if hasattr(c, "wait_for_start"):
                    try:
                        if c.wait_for_start():
                            started = True
                            break
                    except Exception as e:
                        self._print(f"[WARN] wait_for_start() failed: {e}")
            time.sleep(0.05)

        if not started:
            self._print("[ERR] Start not received, aborting.")
            self.stop_all()
            return

        # 5) MAIN LOOP
        self._print("Main loop started.")
        try:
            while self.running:
                for c in self.controllers:
                    if hasattr(c, "update"):
                        try:
                            c.update()
                        except Exception as e:
                            self._print(f"[WARN] update failed: {e}")
                time.sleep(0.01)
        except KeyboardInterrupt:
            self._print("Interrupted by user.")
        finally:
            self.stop_all()

    def stop_all(self):
        self.running = False
        self._print("Cleaning up controllers…")
        for c in self.controllers:
            try:
                c.stop()
            except Exception:
                pass
        try:
            GPIO.cleanup()
        except Exception:
            pass
        self._print("All resources cleaned up.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="middle_part DeviceManager")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose")
    args = parser.parse_args()

    # Transport CAN partagé pour tous les contrôleurs
    transport = CANAdapter(device_name="STEER", verbose=args.verbose)

    # Création des contrôleurs
    steer = SteerController(transport, verbose=args.verbose)
    buttons = [
        ButtonController("bouton_park", 22, transport, verbose=args.verbose),
        ButtonController("bouton_auto_manu", 23, transport, verbose=args.verbose),
        ButtonController("bouton_on_off", 24, transport, verbose=args.verbose),
    ]

    manager = DeviceManager([*buttons, steer], verbose=args.verbose)
    manager.run()
