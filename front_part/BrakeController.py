# back_part/BrakeController.py
import time
import RPi.GPIO as RPI
import Adafruit_GPIO.GPIO as AGPIO
import Adafruit_MCP3008
from AbstractClasses import AbstractController

class BrakeController(AbstractController):
    def __init__(self, can_adapter=None, verbose=False):
        self.verbose = verbose
        self.can_adapter = can_adapter
        
        # Configuration GPIO
        self.CLK = 21
        self.MISO = 19
        self.MOSI = 20
        self.CS = 7
        self.EXTEND_PWM_PIN = 12
        self.RETRACT_PWM_PIN = 13
        self.EXTEND_EN_PIN = 24
        self.RETRACT_EN_PIN = 23

        self.PWM_FREQ = 1000
        self.DUTY = 70
        self.BRAKE_RELEASED = 300
        self.BRAKE_PRESSED = 670
        self.BRAKE_CHANNEL = 1
        
        self.is_braking = False
        self.is_initialized = False
        self.running = True
        
        self.extend_pwm = None
        self.retract_pwm = None
        self.mcp = None
        
        # Pour la communication
        self.last_can_command = None

    def initialize(self):
        """Initialisation matérielle"""
        try:
            RPI.setmode(RPI.BCM)
            RPI.setwarnings(False)
            
            RPI.setup([self.EXTEND_PWM_PIN, self.RETRACT_PWM_PIN, 
                      self.EXTEND_EN_PIN, self.RETRACT_EN_PIN], RPI.OUT)
            
            self.extend_pwm = RPI.PWM(self.EXTEND_PWM_PIN, self.PWM_FREQ)
            self.retract_pwm = RPI.PWM(self.RETRACT_PWM_PIN, self.PWM_FREQ)
            self.extend_pwm.start(0)
            self.retract_pwm.start(0)
            
            gpio = AGPIO.RPiGPIOAdapter(RPI)
            self.mcp = Adafruit_MCP3008.MCP3008(
                clk=self.CLK, cs=self.CS, 
                miso=self.MISO, mosi=self.MOSI, gpio=gpio
            )
            
            # Enregistrer le callback CAN
            if self.can_adapter:
                self.can_adapter.register_callback(self._on_can_message)
            
            self.is_initialized = True
            
            # Relâcher le frein au démarrage (sécurité)
            self.release_brake()
            
            if self.verbose:
                print("[BRAKE] Initialisé, frein relâché")
            
            return True
        except Exception as e:
            print(f"[BRAKE] Erreur: {e}")
            return False

    def _on_can_message(self, msg_type, data):
        """Reçoit les messages CAN de l'OBU"""
        if self.verbose:
            print(f"[BRAKE] CAN: {msg_type}={data}")
        
        if msg_type == "brake_pos_set":
            try:
                target = int(data)
                self.last_can_command = target
                
                # L'OBU décide: 670=appliquer, 300=relâcher
                if target >= 500:  # Valeur haute = appliquer
                    self.apply_brake()
                else:  # Valeur basse = relâcher
                    self.release_brake()
                    
            except ValueError:
                print(f"[BRAKE] Commande invalide: {data}")
        
        elif msg_type == "stop":
            self.stop()
            if self.verbose:
                print("[BRAKE] Arrêt demandé via CAN")

    # ===== Méthodes AbstractController =====
    
    def self_check(self):
        if not self.is_initialized:
            if not self.initialize():
                return False
        
        try:
            pos = self.read_motor_position()
            return 0 <= pos <= 1023
        except:
            return False
    
    def send_ready(self):
        if self.can_adapter:
            self.can_adapter.send_message("brake_rdy", "1")
            if self.verbose:
                print("[BRAKE] Prêt signalé")
        return True
    
    def wait_for_start(self):
        return False
    
    def update(self):
        pass
    
    def stop(self):
        if self.extend_pwm:
            self.extend_pwm.ChangeDutyCycle(0)
        if self.retract_pwm:
            self.retract_pwm.ChangeDutyCycle(0)
        
        RPI.output(self.EXTEND_EN_PIN, RPI.LOW)
        RPI.output(self.RETRACT_EN_PIN, RPI.LOW)

    def read_motor_position(self, channel=1):
        if not self.mcp:
            return 0
        try:
            return self.mcp.read_adc(channel)
        except:
            return 0

    def apply_brake(self):
        """Applique le frein (commande de l'OBU)"""
        if not self.is_initialized or self.is_braking:
            return False
        
        if self.verbose:
            print("[BRAKE] Application frein...")
        
        RPI.output(self.EXTEND_EN_PIN, RPI.HIGH)
        RPI.output(self.RETRACT_EN_PIN, RPI.HIGH)
        
        self.extend_pwm.ChangeDutyCycle(self.DUTY)
        self.retract_pwm.ChangeDutyCycle(0)

        while self.running:
            pos = self.read_motor_position()
            if pos >= self.BRAKE_PRESSED:
                break
            time.sleep(0.02)
        
        self.stop()
        self.is_braking = True
        return True

    def release_brake(self):
        """Relâche le frein (commande de l'OBU)"""
        if not self.is_initialized or not self.is_braking:
            return False
        
        if self.verbose:
            print("[BRAKE] Relâchement frein...")
        
        RPI.output(self.RETRACT_EN_PIN, RPI.HIGH)
        RPI.output(self.EXTEND_EN_PIN, RPI.HIGH)
        
        self.retract_pwm.ChangeDutyCycle(self.DUTY)
        self.extend_pwm.ChangeDutyCycle(0)

        while self.running:
            pos = self.read_motor_position()
            if pos <= self.BRAKE_RELEASED:
                break
            time.sleep(0.02)
        
        self.stop()
        self.is_braking = False
        return True

    def cleanup(self):
        self.running = False
        self.stop()
        if self.extend_pwm:
            self.extend_pwm.stop()
        if self.retract_pwm:
            self.retract_pwm.stop()
        if self.verbose:
            print("[BRAKE] Nettoyé")
