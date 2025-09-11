from CAN_system.CANSystem import CANSystem

class CANAdapter:
    def __init__(self, channel='can0', interface='socketcan', device_name='BRAKE', verbose=False):
        self.verbose = verbose
        self.handlers = []
        self.canSystem = CANSystem(device_name=device_name, channel=channel, interface=interface, verbose=verbose)
        self.canSystem.set_callback(self._on_can)
        self.canSystem.start_listening()
        self.running = True

    def add_handler(self, fn):
        """Enregistre une fonction callback appelée à chaque message CAN reçu."""
        self.handlers.append(fn)


    def _on_can(self, device, order, data):
        self._print(f"[CANAdapter] Dispatch {device=} {order=} {data=}")
        for h in list(self.handlers):
            try:
                h(device, order, data)
            except Exception as e:
                self._print(f"[CANAdapter] handler error: {e}")

    def send(self, device_id, order_id, data=None):
        self._print(f"[CANAdapter] Sending {device_id=} {order_id=} {data=}")
        self.canSystem.can_send(device_id, order_id, data)

    def stop(self):
        self.running = False
        self.canSystem.stop()

    def _print(self, *args, **kwargs):
        if self.verbose:
            print("[CANAdapter]", *args, **kwargs)
