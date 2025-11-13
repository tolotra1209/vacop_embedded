# middle_part/CANAdapter.py
from CAN_system.CANSystem_p import CANSystem

class CANAdapter:
    """Wrapper simplifié autour de CANSystem pour middle_part (STEER + boutons)."""

    def __init__(self, device_name="STEER", verbose=False):
        self.verbose = verbose
        self.device_name = device_name
        self.can_system = CANSystem(device_name=device_name, verbose=verbose)
        self.listener = self.can_system  # compatibilité avec .listener.can_input()

    def _print(self, *args):
        if self.verbose:
            print("[CANAdapter]", *args)

    def can_send(self, target: str, order_id: str, data):
        """Envoie un message CAN à une autre unité."""
        try:
            self._print(f"Sending to {target}: order='{order_id}', data={data}")
            self.can_system.can_send(target, order_id, data)
        except Exception as e:
            self._print(f"[ERR] can_send failed: {e}")

    def set_callback(self, callback):
        """Définit une fonction callback pour les messages entrants."""
        self.can_system.set_callback(callback)

    def start_listening(self):
        """Démarre l'écoute du bus CAN."""
        self._print("Starting CAN listener thread…")
        self.can_system.start_listening()

    def stop(self):
        """Arrête proprement le CAN bus."""
        self._print("Stopping CAN listener…")
        self.can_system.stop()
