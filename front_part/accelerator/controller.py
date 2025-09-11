import time
import threading
from .sensor import AcceleratorSensor
from AbstractClasses import AbstractController
from ..CANAdapter import CANAdapter

"""
    Contrôleur de la pédale d'accélération.

    Séquence d’usage attendue par le DeviceManager :
      1) c.self_check()        -> vérifie que le capteur de la pédale d'accélaration est OK
      2) c.send_ready()        -> envoie 'brake_rdy' et attend ACK de l'OBU
      3) c.wait_for_start()    -> renvoie True lors de la première réception de 'start'
      4) c.update() en boucle  -> lit capteur et envoie périodiquement 'accel_pedal'
      5) c.stop()              -> arrêt propre
"""
READY_TIMEOUT = 3.0          # secondes max avant abandon
READY_RETRY_INTERVAL = 0.5   # secondes entre deux essais

class AcceleratorController(AbstractController):
    def __init__(self, sensor: AcceleratorSensor, transport: CANAdapter, verbose=False):
        self.sensor = sensor
        self.transport = transport
        self.verbose = verbose
        self.running = False # Etat d'execution

        # Synchronisation événements CAN
        self.start_event = threading.Event()  # signalé quand 'start' reçu
        self.ready_ack = False                # devient True quand 'brake_ack' (ou équivalent) reçu

        # S'abonne à la réception CAN via le transport
        self.transport.add_handler(self._on_can)

        # Mémo de la dernière valeur envoyée (pour éviter du spam)
        self._last_sent = None

    def self_check(self) -> bool:
        #Vérifie que le capteur renvoie une valeur cohérente
        raw = self.sensor.read()
        clamped = self.sensor.clamp_acceleration(raw)
        if 200 <= clamped <= 300:
            self._print(f"Accelerator check OK ({clamped})")
            return True
        else:
            self._print(f"Accelerator check FAILED ({clamped})")
            return False

    def initialize(self):
        # Appelée par DeviceManager.initialize_all(). Retourne True si prêt, False sinon.
        ok = self.self_check()
        if not ok:
            self._print("Self-check failed. Not sending READY.")
            return False
        self.send_ready()
        return True

    def send_ready(self):
        #Annonce 'brake_rdy' à l'OBU (ready global du front).
        self.ready_ack = False
        deadline = time.time() + READY_TIMEOUT
        while not self.ready_ack and time.time() < deadline:
            self.transport.send("OBU", "brake_rdy")
            self._print("Sent READY (brake_rdy) to OBU, waiting for ACK")
            time.sleep(READY_RETRY_INTERVAL)
        if self.ready_ack:
            self._print("READY acknowledged by OBU.")
        else:
            self._print("READY ACK from OBU (timeout). Continuing a...")


    def _on_can(self, device, order, data):
        #Callback appelé automatiquement quand un message CAN est reçu.
        if order == "start":
            self._print("Start command received.")
            self.start_event.set()
            self.running = True

        elif order == "stop":
            self._print("Stop command received.")
            self.running = False

        elif order == "ready_ack":
            self._print("READY ACK received from OBU.")
            self.ready_ack = True

    def wait_for_start(self):
        #Renvoie True quand le start est reçu puis le remet à False. Pour qu'il initialise qu'une fois.
        if self.start_event.is_set():
            self.start_event.clear()   # on consomme l’événement
            self.running = True
            return True
        return False

    def update(self):
        #Lit la valeur de la pédale d'accélération, mappe la valeur et l'envoie si elle a changé. 
        if not self.running:
            return

        raw = self.sensor.read()
        clamped = self.sensor.clamp_acceleration(raw)
        mapped = self.sensor.map_to_output(clamped)

        if self.sensor.has_changed(mapped):
            self.transport.send("OBU", "accel_pedal", mapped)
            self._last_sent = mapped
            self._print(f"acceleration_pedal -> {mapped}")

    def stop(self):
        self.transport.stop()
        self._print("Stopped accelerator controller.")

    def _print(self, *args, **kwargs):
        if self.verbose:
            print("[CTRL ACCELERATOR]", *args, **kwargs)
