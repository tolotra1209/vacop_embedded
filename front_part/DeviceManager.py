import argparse
import time
from .accelerator.sensor import AcceleratorSensor
from .accelerator.controller import AcceleratorController
from .CANAdapter import CANAdapter
from AbstractClasses import AbstractController

# Execute : python3 -m front_part.DeviceManager -v

class DeviceManager:
    def __init__(self, controllers: list[AbstractController], verbose = False):
        self.verbose = verbose
        self.controllers = controllers
        self.running = True

    def run(self):
        # Check que l'accelerateur et le frein fonctionnent correctement
        all_ok = all(controller.self_check() for controller in self.controllers)
        if not all_ok :
            self._print("Sensor check failed. Aborting")
            return

	# Envoie à l'OBU que l'initialisation est réussit (envoie de la commande break readu
        self._print(" All sensors OK. Sending READY to OBU...")
        for controller in self.controllers:
            controller.send_ready()

        # Attend le start de l'OBU
        self._print("Waiting for 'start' command from CAN...")
        started = False
        while not started :
            for controller in self.controllers:
                if controller.wait_for_start():
                    self._print("Start received. Initializing...")
                    started = True
                    break
            time.sleep(0.1)

        # Boucle principale
        self._print("Main loop started.")
        try :
            while self.running :
                for controller in self.controllers:
                    controller.update()
                time.sleep(0.05)
        except KeyboardInterrupt:
            self._print("Interrupted by user. Exiting...")
        finally:
            self.stop_all()

    def main_loop(self):
        self._print("Main loop started.")
        try:
            while self.running:
                for controller in self.controllers:
                    controller.update()
                time.sleep(0.05)
        except KeyboardInterrupt:
            self._print("Interrupted during main loop. Exiting...")
            self.stop_all()

    def stop_all(self):
        for controller in self.controllers:
            controller.stop()
        self._print("All resources cleaned up.")

    def __del__(self):
        self._print("Destructor called, cleaning up ...")
        self.stop_all()

    def _print(self, *args, **kwargs):
        if self.verbose:
            print("[DeviceManager]", *args, **kwargs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DeviceManager to front vacop system")
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    
    sensor = AcceleratorSensor(verbose=args.verbose)
    transport = CANAdapter(verbose=args.verbose)
    accel_controller = AcceleratorController(sensor, transport, verbose=args.verbose)

    manager = DeviceManager([accel_controller], verbose=args.verbose)
    manager.run()
