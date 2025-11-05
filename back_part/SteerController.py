# back_part/SteerController.py
import time

class SteerController:
    """
    Contrôle de la direction côté OBU.
    - Reçoit une cible haute-niveau (steer_target) -> via set_target()
    - Reçoit le feedback capteur (steer_pos_real) -> via on_feedback()
    - A chaque update(), calcule une consigne 'steer_pos_set' et l'envoie via CAN.
    """
    def __init__(self, canSystem, kp: float = 0.8, max_step: int = 30, verbose: bool = False):
        self.can = canSystem
        self.kp = kp                  # gain proportionnel (à régler)
        self.max_step = max_step      # limite de pas par tick (anti-saut)
        self.verbose = verbose

        self.enabled = False
        self.target = None            # cible (int, ex 0..1023)
        self.meas = None              # feedback courant
        self.last_set = None          # mémo dernière commande envoyée
        self.last_update = time.time()

    # --- API exposée à OBU ---
    def enable(self, flag: bool):
        self.enabled = bool(flag)
        # Notifie l'actionneur (si nécessaire)
        self.can.can_send("STEER", "steer_enable", self.enabled)
        if not self.enabled:
            self.target = None
            self.last_set = None
        self._log(f"steer_enable -> {self.enabled}")

    def set_target(self, target: int):
        try:
            self.target = int(target)
            self._log(f"steer_target set to {self.target}")
        except Exception:
            self._log(f"Invalid steer_target: {target}")

    def on_feedback(self, meas: int):
        try:
            self.meas = int(meas)
        except Exception:
            self._log(f"Invalid steer_pos_real: {meas}")

    # --- Tick périodique (appelé par OBU en AUTO) ---
    def update(self):
        if not self.enabled or self.target is None or self.meas is None:
            return

        err = self.target - self.meas
        # commande P bornée
        step = self.kp * err
        if step > self.max_step:  step = self.max_step
        if step < -self.max_step: step = -self.max_step

        cmd = int(self.meas + step)

        if cmd != self.last_set:
            self.can.can_send("STEER", "steer_pos_set", cmd)
            self.last_set = cmd
            if self.verbose:
                self._log(f"meas={self.meas} target={self.target} err={int(err)} -> set={cmd}")

    # --- utils ---
    def _log(self, *a):
        if self.verbose:
            print("[STEER]", *a)

