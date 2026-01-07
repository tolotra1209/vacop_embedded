import time
from .MotorController import MotorController

class DualMotorController:
    def __init__(self, verbose=False):
        self.verbose = verbose

        self.m1 = None
        self.m2 = None

        # 2 UART différents (à adapter)
        try:
            self.m1 = MotorController(node=1, stoPin=16, uart_port="/dev/ttyAMA0", verbose=verbose)
        except Exception as e:
            self._print("ERROR init m1:", e)

        try:
            self.m2 = MotorController(node=2, stoPin=26, uart_port="/dev/ttyAMA3", verbose=verbose)
        except Exception as e:
            self._print("ERROR init m2:", e)

        if self.m1 is None and self.m2 is None:
            raise RuntimeError("No motor could be initialized (m1 and m2 failed).")

    def _print(self, *args, **kwargs):
        if self.verbose:
            print("[DualMotorController]", *args, **kwargs)

    def configure(self):
        """Configuration minimale (pas de calibration)."""
        self._print("configure()")
        if self.m1: self.m1.configure()
        if self.m2: self.m2.configure()

    def set_forward(self):
        if self.m1: self.m1.set_direction("CW")
        if self.m2: self.m2.set_direction("CCW")

    def set_reverse(self):
        if self.m1: self.m1.set_direction("CCW")
        if self.m2: self.m2.set_direction("CW")

    def set_torque(self, torque_value):
        self._print("set_torque:", torque_value)
        if self.m1: self.m1.set_torque(torque_value)
        if self.m2: self.m2.set_torque(torque_value)

    def stop_motor(self):
        self._print("stop_motor()")
        if self.m1:
            try: self.m1.stop_motor()
            except Exception as e: self._print("WARN stop m1:", e)
        if self.m2:
            try: self.m2.stop_motor()
            except Exception as e: self._print("WARN stop m2:", e)

    # Optionnel
    def stop(self):
        self.stop_motor()


if __name__ == "__main__":
    ctrl = DualMotorController(verbose=True)
    ctrl.configure()

    ctrl.set_forward()
    ctrl.set_torque(8)
    time.sleep(5)

    ctrl.set_reverse()
    ctrl.set_torque(5)
    time.sleep(5)

    ctrl.stop_motor()
