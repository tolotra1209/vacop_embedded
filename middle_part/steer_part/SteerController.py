# middle_part/steer/controller.py
import time
import threading
import RPi.GPIO as GPIO
import Adafruit_MCP3008
from AbstractClasses import AbstractController
from ..CANAdapter import CANAdapter

# === PARAMS 
PWM_FREQ_STEER      = 1000
STEER_DIR_PIN       = 17    # Direction
STEER_PUL_PIN       = 26    # Pulse
STEER_EN_PIN        = 16    # Enable
ADC_CH              = 0     # MCP3008 channel pour le volant

CLK = 21; MISO = 19; MOSI = 20; CS = 7

KP_STEER            = 1.0
STEER_LEFT_LIMIT    = 100
STEER_RIGHT_LIMIT   = 923
NEUTRAL_POSITION    = 512
STEER_THRESHOLD     = 10    # zone morte
FEEDBACK_PERIOD     = 0.05  # 20 Hz

READY_TIMEOUT       = 5.0
READY_RETRY         = 0.5

class SteerController(AbstractController):
    """
    - self_check(): centre et valide la mesure
    - send_ready(): envoie 'steer_rdy' et attend 'ready_ack'
    - wait_for_start(): retourne True une fois après réception 'start'
    - update(): pilote le moteur si steer_enable, publie steer_pos_real
    """
    def __init__(self, transport: CANAdapter, verbose=False):
        self.t = transport
        self.verbose = verbose

        # Etat
        self.running = False
        self.steer_enable = False
        self.target = NEUTRAL_POSITION
        self._last_sent_pos = None

        # Evènements
        self._start_evt = threading.Event()
        self._ready_ack = threading.Event()

        # GPIO / PWM / ADC
        GPIO.setmode(GPIO.BCM)
        GPIO.setup([STEER_EN_PIN, STEER_PUL_PIN, STEER_DIR_PIN], GPIO.OUT)
        self.pulse = GPIO.PWM(STEER_PUL_PIN, PWM_FREQ_STEER)
        self.pulse.start(0)
        self.mcp = Adafruit_MCP3008.MCP3008(clk=CLK, cs=CS, miso=MISO, mosi=MOSI)

        # CAN handler
        self.t.add_handler(self._on_can)

    # ---- Utils ----
    def _print(self, *a):
        if self.verbose: print("[STEER]", *a)

    def _read_pos(self):
        return self.mcp.read_adc(ADC_CH)

    def _apply_control(self, pos_wanted, force=False):
        pos = self._read_pos()
        if (pos < STEER_LEFT_LIMIT) or (pos > STEER_RIGHT_LIMIT):
            GPIO.output(STEER_EN_PIN, GPIO.HIGH)  # sécurité
            self._print("Out of bounds, motor disabled")
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
        self.pulse.ChangeDutyCycle(50)  # simple PWM fixe (tu ajusteras)

    # ---- AbstractController ----
    def self_check(self) -> bool:
        self._print("Self-check: centering to neutral…")
        # essaie de revenir au neutre en force
        for _ in range(100):
            cur = self._read_pos()
            if abs(cur - NEUTRAL_POSITION) < STEER_THRESHOLD:
                self._print("Center OK:", cur)
                return True
            self._apply_control(NEUTRAL_POSITION, force=True)
            time.sleep(0.02)
        self._print("Center FAILED:", self._read_pos())
        return False

    def send_ready(self):
        self._ready_ack.clear()
        deadline = time.time() + READY_TIMEOUT
        while time.time() < deadline and not self._ready_ack.is_set():
            self.t.send("OBU", "steer_rdy")
            self._print("Sent steer_rdy, waiting for ready_ack…")
            time.sleep(READY_RETRY)
        if self._ready_ack.is_set():
            self._print("ready_ack received.")
        else:
            self._print("ready_ack timeout (continue quand même).")

    def wait_for_start(self) -> bool:
        if self._start_evt.is_set():
            self._start_evt.clear()
            self.running = True
            return True
        return False

    def update(self):
        # feedback périodique
        now_pos = self._read_pos()
        if self._last_sent_pos is None or abs(now_pos - self._last_sent_pos) >= 2:
            self.t.send("OBU", "steer_pos_real", now_pos)
            self._last_sent_pos = now_pos

        if not self.running:
            return

        # suivi de consigne si activé
        self._apply_control(self.target)

    def stop(self):
        self.pulse.ChangeDutyCycle(0)
        GPIO.output(STEER_EN_PIN, GPIO.HIGH)
        self.pulse.stop()
        self._print("Stopped.")

    # ---- CAN ----
    def _on_can(self, device, order, data):
        # on ne traite que ce qui nous concerne logiquement
        if order == "start":
            self._print("start received.")
            self._start_evt.set()

        elif order == "stop":
            self._print("stop received.")
            self.running = False

        elif order == "ready_ack":
            self._print("ready_ack received.")
            self._ready_ack.set()

        elif order == "steer_enable":
            self.steer_enable = bool(int(data)) if isinstance(data, int) else bool(data)
            self._print("steer_enable:", self.steer_enable)

        elif order == "steer_pos_set":
            self.target = int(data)
            self._print("new target:", self.target)
