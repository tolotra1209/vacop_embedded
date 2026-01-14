import SoloPy as solo
import RPi.GPIO as GPIO
import time

TIMEOUT = 30  # seconds

class MotorController:
    _gpio_initialized = False

    def __init__(
        self,
        node: int,
        stoPin: int,
        uart_port: str,
        uart_baud=None,
        verbose: bool = False,
    ):
        if not isinstance(node, int):
            raise TypeError(f"[{node}] ERROR: node must be int")
        if not isinstance(stoPin, int):
            raise TypeError(f"[{node}] ERROR: stoPin must be int")
        if not isinstance(uart_port, str):
            raise TypeError(f"[{node}] ERROR: uart_port must be str")

        self.node = node
        self.stoPin = stoPin
        self.uart_port = uart_port
        self.uart_baud = uart_baud or solo.UartBaudRate.RATE_115200
        self.verbose = verbose

        self.mySolo = None
        self.connected = False

        self._initialize_gpio_once()
        self._initialize_STO()
        self._initialize_motor()

    def _print(self, *args, **kwargs):
        if self.verbose:
            print(f"[{self.node}]", *args, **kwargs)

    @classmethod
    def _initialize_gpio_once(cls):
        if not cls._gpio_initialized:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            cls._gpio_initialized = True

    def _initialize_STO(self):
        self._print("[MOTOR] Init STO with pin", self.stoPin)
        GPIO.setup(self.stoPin, GPIO.OUT)
        GPIO.output(self.stoPin, GPIO.HIGH)  # enable STO
        time.sleep(0.05)

    def _initialize_motor(self):
        self.mySolo = solo.SoloMotorControllerUart(self.uart_port, self.node, self.uart_baud)

        self._print(f"[MOTOR] Trying to connect over UART ({self.uart_port})...")
        deadline = time.time() + TIMEOUT
        connected = False
        last_err = None

        while time.time() < deadline:
            time.sleep(0.5)
            connected, last_err = self.mySolo.communication_is_working()
            if connected:
                break

        if not connected:
            self._print("[MOTOR] SOLO not reachable:", last_err)
            raise RuntimeError(
                f"[{self.node}] ERROR: SOLO not reachable over UART {self.uart_port} (err={last_err})"
            )

        self.connected = True
        self._print("[MOTOR] Communication established!")

    def _ensure_connected(self):
        if self.mySolo is None:
            raise RuntimeError(f"[{self.node}] ERROR: SOLO object not initialized")

    # ---------- CONFIG ----------
    def configure(self):
        """
        Configuration minimale UNIQUEMENT.
        Aucune calibration, aucune identification.
        """
        self._ensure_connected()
        self.mySolo.set_command_mode(solo.CommandMode.DIGITAL)
        self.mySolo.set_motor_type(solo.MotorType.BLDC_PMSM)
        self.mySolo.set_feedback_control_mode(solo.FeedbackControlMode.HALL_SENSORS)
        self.mySolo.set_control_mode(solo.ControlMode.TORQUE_MODE)
        self._print("Configured (no calibration).")

    # ---------- STOP / SAFE ----------
    def stop_motor(self):
        self._stop_torque()
        self._stop_STO()

    def _stop_STO(self):
        try:
            GPIO.output(self.stoPin, GPIO.LOW)
        except Exception:
            pass
        self._print("[STO] LOW (Safe Torque Off)")

    def _stop_torque(self):
        try:
            self.mySolo.set_torque_reference_iq(0.0)
        except Exception:
            pass
        self._print("[Motor] torque set to zero")

    # ---------- COMMANDS ----------
    def set_direction(self, direction_str: str):
        self._ensure_connected()

        directions = {
            "CW": solo.Direction.CLOCKWISE,
            "CCW": solo.Direction.COUNTERCLOCKWISE,
        }
        direction_str = direction_str.upper()
        if direction_str not in directions:
            raise ValueError(f"[{self.node}] ERROR: invalid direction '{direction_str}' (CW/CCW)")

        ret = self.mySolo.set_motor_direction(directions[direction_str])
        if isinstance(ret, tuple) and len(ret) >= 2:
            ok, err = ret[0], ret[1]
            if err != solo.Error.NO_ERROR_DETECTED:
                raise RuntimeError(f"[{self.node}] set_motor_direction failed: {err}")

        self._print("Direction set to", direction_str)

    def set_torque(self, torque_value):
        self._ensure_connected()
        torque_value = float(torque_value)
        if torque_value < 0:
            raise ValueError(f"[{self.node}] ERROR: torque must be non-negative")

        ret = self.mySolo.set_torque_reference_iq(torque_value)
        if isinstance(ret, tuple) and len(ret) >= 2:
            ok, err = ret[0], ret[1]
            if err != solo.Error.NO_ERROR_DETECTED:
                raise RuntimeError(f"[{self.node}] set_torque_reference_iq failed: {err}")

        self._print("Torque set to", torque_value)

    # ---------- FEEDBACK ----------
    def display_torque(self):
        torque, error = self.mySolo.get_quadrature_current_iq_feedback()
        print(f"[{self.node}] Measured Iq/Torque [A]: {torque} | Error: {error}")

    def display_speed(self):
        speed, error = self.mySolo.get_speed_feedback()
        print(f"[{self.node}] Motor Speed [RPM]: {speed} | Error: {error}")
