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

        # 1️⃣ Étape d'initialisation
        self._print("Initializing all controllers…")
        for c in self.controllers:
            try:
                c.initialize()
            except Exception as e:
                self._print(f"[WARN] init failed for {c.__class__.__name__}: {e}")

        # 2️⃣ Auto-check matériel
        all_ok = all(c.self_check() for c in self.controllers)
        if not all_ok:
            self._print("[ERR] Some controllers failed self_check. Abort.")
            self.stop_all()
            return

        # 3️⃣ Phase READY : seuls ceux qui ont besoin (steer par ex.) envoient leur signal
        for c in self.controllers:
            if hasattr(c, "send_ready"):
                try:
                    c.send_ready()
                except Exception:
                    pass

        # 4️⃣ Attente du START de l’OBU
        self._print("Waiting for 'start' from OBU…")
        started = False
        while not started and self.running:
            for c in self.controllers:
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

        # 5️⃣ Boucle principale
        self._print("Main loop started.")
        try:
            while self.running:
                for c in self.controllers:
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
    #steer = SteerController(transport, verbose=args.verbose)
    buttons = [
        ButtonController("bouton_park", 22, transport, verbose=args.verbose),
        ButtonController("bouton_auto_manu", 23, transport, verbose=args.verbose),
        ButtonController("bouton_on_off", 24, transport, verbose=args.verbose),
        # ButtonController("bouton_reverse", <pin>, transport, verbose=args.verbose),
    ]

    manager = DeviceManager([*buttons], verbose=args.verbose)
    manager.run()
