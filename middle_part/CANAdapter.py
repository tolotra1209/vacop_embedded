# middle_part/CANAdapter.py
from CAN_system.CANSystem_p import CANSystem

class CANAdapter:
    """
    Petit wrapper autour CANSystem pour la middle_part :
    - centralise le CAN
    - diffuse les messages reçus à une liste de handlers Python
    """

    def __init__(self, device_name="STEER", verbose=False):
        self.device_name = device_name
        self.verbose = verbose

        self._handlers = []  # liste de callbacks (device, order, data)

        # CANSystem "brut"
        self._can = CANSystem(device_name=device_name, verbose=verbose)
        # on branche notre propre dispatcher
        self._can.set_callback(self._on_can_message)
        self._can.start_listening()

    # ---------- utils ----------
    def _print(self, *args):
        if self.verbose:
            print("[CANAdapter]", *args)

    # ---------- réception ----------
    def _on_can_message(self, device_id, order_id, data):
        """
        Callback donné à CANSystem. On redispatche vers tous
        les handlers enregistrés via add_handler().
        """
        # debug optionnel :
        # self._print("RX:", device_id, order_id, data)

        for cb in list(self._handlers):
            try:
                cb(device_id, order_id, data)
            except Exception as e:
                self._print("handler error:", e)

    def add_handler(self, callback):
        """c
        Enregistre un handler appelé comme cb(device, order, data)
        à chaque trame CAN reçue.
        """
        if callback not in self._handlers:
            self._handlers.append(callback)

    # ---------- émission ----------
    def can_send(self, device_id, order_id, data=None):
        """
        Envoie une trame CAN vers device_id avec l'order_id et data.
        """
        # debug optionnel :
        # self._print("TX ->", device_id, order_id, data)
        self._can.can_send(device_id, order_id, data)

    # ---------- stop ----------
    def stop(self):
        try:
            self._can.stop()
        except Exception as e:
            self._print("Error on stop():", e)