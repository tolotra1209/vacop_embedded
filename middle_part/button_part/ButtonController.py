# middle_part/button_part/ButtonController.py
import time
import RPi.GPIO as GPIO
from typing import Optional

from AbstractClasses import AbstractController
from ..CANAdapter import CANAdapter


class ButtonController(AbstractController):
    """
    Contrôleur d’un bouton physique qui envoie son état sur le CAN.
    - name : sera utilisé comme order_id (ex: 'bouton_on_off', 'bouton_auto_manu'…)
    - pin  : GPIO BCM
    - active_high : True si le bouton fournit 1 quand pressé, False si inverse
    - pull : 'up' | 'down' | None  -> résistance interne
    """

    def __init__(
        self,
        name: str,
        pin: int,
        transport: CANAdapter,
        *,
        active_high: bool = True,
        pull: Optional[str] = "down",  # <- Optional au lieu de str | None
        debounce_ms: int = 60,
        verbose: bool = False,
    ):
        self.name = name
        self.pin = pin
        self.t = transport
        self.verbose = verbose

        self.active_high = active_high
        self.pull = pull
        self.debounce_ms = debounce_ms

        self.running = False
        self._last_state = None  # état logique (0/1) après inversion éventuelle

    # ---------- utils ----------
    def _print(self, *args):
        if self.verbose:
            print(f"[BTN:{self.name}]", *args)

    def _read_raw(self) -> int:
        return int(GPIO.input(self.pin))

    def _logical_state(self, raw: int) -> int:
        """Applique active_high pour renvoyer 0/1 'appuyé' logiquement."""
        return raw if self.active_high else (0 if raw == 1 else 1)

    def _send_if_changed(self, logical_state: int):
        if logical_state != self._last_state:
            self._last_state = logical_state
            self._print("state ->", logical_state)
            # Envoi direct vers l’OBU
            self.t.can_send("OBU", self.name, logical_state)

    # ---------- AbstractController ----------
    def self_check(self) -> bool:
        # Rien de spécial à vérifier pour un bouton
        return True

    def send_ready(self):
        # Pas de phase READY pour les boutons
        pass

    def wait_for_start(self) -> bool:
        # Les boutons n’attendent pas START
        return False

    def initialize(self):
        # Config GPIO
        GPIO.setmode(GPIO.BCM)

        # Map du pull-up/down
        if self.pull == "up":
            pud = GPIO.PUD_UP
        elif self.pull == "down":
            pud = GPIO.PUD_DOWN
        else:
            pud = None

        if pud is None:
            GPIO.setup(self.pin, GPIO.IN)
        else:
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=pud)

        # Init état et envoi initial
        raw = self._read_raw()
        logical = self._logical_state(raw)
        self._last_state = logical
        self._print(f"initialized on pin {self.pin} (initial={logical})")
        self.t.can_send("OBU", self.name, logical)

        # Détection des fronts + debounce
        GPIO.add_event_detect(
            self.pin,
            GPIO.BOTH,
            callback=self._on_gpio_event,
            bouncetime=self.debounce_ms,
        )
        self.running = True

    def update(self):
        # Tout passe par l’IRQ GPIO.
        pass

    def stop(self):
        if not self.running:
            return
        try:
            GPIO.remove_event_detect(self.pin)
        except Exception:
            pass
        self.running = False
        self._print("stopped")

    # ---------- IRQ ----------
    def _on_gpio_event(self, channel):
        try:
            # Petit délai pour stabiliser (anti-rebond soft complémentaire)
            time.sleep(self.debounce_ms / 1000.0)
            raw = self._read_raw()
            logical = self._logical_state(raw)
            self._send_if_changed(logical)
        except Exception as e:
            self._print("callback error:", e)
