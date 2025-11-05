# middle_part/steer_part/SteerController.py
import time
import threading
import RPi.GPIO as GPIO
import Adafruit_MCP3008

from AbstractClasses import AbstractController
from ..CANAdapter import CANAdapter

PWM_FREQ_STEER = 1000
STEER_DIR_PIN = 17
STEER_PUL_PIN = 26
STEER_EN_PIN  = 16

ADC_CH = 0

CLK = 21; MISO = 19; MOSI = 20; CS = 7

STEER_LEFT_LIMIT  = 100
STEER_RIGHT_LIMIT = 923
NEUTRAL_POSITION  = 512
STEER_THRESHOLD   = 10
FEEDBACK_PERIOD   = 0.05

READY_TIMEOUT = 20.0
READY_RETRY   = 0.5


class SteerController(AbstractController):

    def __init__(self, transport: CANAdapter, verbose=False):
        self.t = transport
        self.verbose = verbose

        # État
        self.running = False
        self.steer_enable = False
        self.target = NEUTRAL_POSITION

        # Événements
        self._start_evt = threading.Event()
        self.ready_ack = False

        # ADC + PWM
        GPIO.setmode(GPIO.BCM)
        GPIO.setup([STEER_EN_PIN, STEER_PUL_PIN, STEER_DIR_PIN], GPIO.OUT)

        self.pulse = GPIO.PWM(STEER_PUL_PIN, PWM_FREQ_STEER)
        self.pulse.start(0)

        self.mcp = Adafruit_MCP3008.MCP3008(clk=CLK, cs=CS, miso=MISO, mosi=MOSI)

        # Enregistrement du handler CAN
        self.t.add_handler(self._on_can)

        self._last_feedback_ts = 0.0

    def _print(self, *a):
        if self.verbose:
            print("[STEER]", *a)

    def _read_pos(self):
        return self.mcp.read_adc(ADC_CH)

    def _apply_control(self, pos_wanted, force=False):
        pos = self._read_pos()

        if pos < STEER_LEFT_LIMIT or pos > STEER_RIGHT_LIMIT:
            GPIO.output(STEER_EN_PIN, GPIO.HIGH)
            self.pulse.ChangeDutyCycle(0)
            self._print("Out of bounds — motor disabled")
            return

        if not self.steer_enable and not force:
            self.pulse.ChangeDutyCycle(0)
            GPIO.output(STEER_EN_PIN, GPIO.HIGH)
            return

        err = pos_wanted - pos
        if abs(err) < STEER_THRESHOLD:
            self.pulse.ChangeDutyCycle(0)
            GPIO.output(STEER_EN_PIN, GPIO.HIGH)
            return

        GPIO.output(STEER_EN_PIN, GPIO.LOW)
        GPIO.output(STEER_DIR_PIN, GPIO.HIGH if err > 0 else GPIO.LOW)
        self.pulse.ChangeDutyCycle(50)

    # --- AbstractController methods ---
    def self_check(self):
        try:
            v = self._read_pos()
            self._print("Self-check ADC:", v)
            return 0 <= v <= 1023
        except Exception as e:
            self._print("Self-check FAILED:", e)
            return False

    def initialize(self):
        self._print("Centering to neutral...")
        for _ in range(200):
            cur = self._read_pos()
            if abs(cur - NEUTRAL_POSITION) < STEER_THRESHOLD:
                break
            self._apply_control(NEUTRAL_POSITION, force=True)
            time.sleep(0.02)

        self.pulse.ChangeDutyCycle(0)
        GPIO.output(STEER_EN_PIN, GPIO.HIGH)

    def send_ready(self):
        self.ready_ack = False
        deadline = time.time() + READY_TIMEOUT

        while not self.ready_ack and time.time() < deadline:
            self.t.can_send("OBU", "steer_rdy", 1)
            self._print("Sent steer_rdy — waiting for ACK…")
            time.sleep(READY_RETRY)

        if self.ready_ack:
            self._print("steer READY_ACK received.")
        else:
            self._print("steer READY_ACK timeout.")

    def wait_for_start(self):
        if self._start_evt.is_set():
            self._start_evt.clear()
            self.running = True
            return True
        return False

    def update(self):
        if not self.running:
            return

        now = time.time()
        if now - self._last_feedback_ts >= FEEDBACK_PERIOD:
            pos = self._read_pos()
            self.t.can_send("OBU", "steer_pos_real", pos)
            self._last_feedback_ts = now

        self._apply_control(self.target)

    def stop(self):
        self.running = False
        try:
            self.pulse.ChangeDutyCycle(0)
            self.pulse.stop()
            GPIO.output(STEER_EN_PIN, GPIO.HIGH)
        except:
            pass

    # ---------- CAN ----------
    def _on_can(self, device, order, data):

        if order == "start":
            self._print("start received")
            self._start_evt.set()

        elif order == "stop":
            self.running = False

        elif order == "ready_ack":
            self._print("ready_ack received")
            self.ready_ack = True

        elif order == "steer_enable":
            self.steer_enable = bool(int(data))
            self._print("steer_enable =", self.steer_enable)

        elif order == "steer_pos_set":
            self.target = int(data)
            self._print("new target =", self.target)
