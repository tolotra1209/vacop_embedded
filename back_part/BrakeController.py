# back_part/BrakeController.py
import time
import RPi.GPIO as RPI
import Adafruit_MCP3008
import Adafruit_GPIO.GPIO as AGPIO

class BrakeController:
    def _init_(self, verbose=False):
        self.verbose = verbose

        self.CLK = 21
        self.MISO = 19
        self.MOSI = 20
        self.CS = 7
        
        self.EXTEND_PWM_PIN = 12  # Extension = Freinage
        self.RETRACT_PWM_PIN = 13  # Rétraction = Relâchement
        self.EXTEND_EN_PIN = 23
        self.RETRACT_EN_PIN = 24

        self.PWM_FREQ = 1000
        self.BRAKE_DUTY = 70  # Pourcentage de puissance pour le freinage
        self.RELEASE_DUTY = 50  # Pourcentage pour relâcher le frein
        
        # Position du frein via MCP3008
        self.mcp = None
        self.BRAKE_CHANNEL = 1  # Canal ADC pour lire la position du frein
        
        self.is_braking = False

    def initialize(self):
        """Initialise le contrôleur de frein"""
        try:
            RPI.setmode(RPI.BCM)
            RPI.setwarnings(False)
            
            # Configuration des broches GPIO
            RPI.setup([self.EXTEND_PWM_PIN, self.RETRACT_PWM_PIN, 
                      self.EXTEND_EN_PIN, self.RETRACT_EN_PIN], RPI.OUT)
            
            # Initialisation des PWM
            self.extend_pwm = RPI.PWM(self.EXTEND_PWM_PIN, self.PWM_FREQ)
            self.retract_pwm = RPI.PWM(self.RETRACT_PWM_PIN, self.PWM_FREQ)
            self.extend_pwm.start(0)
            self.retract_pwm.start(0)
            
            # Initialisation du MCP3008
            gpio = AGPIO.RPiGPIOAdapter(RPI)
            self.mcp = Adafruit_MCP3008.MCP3008(
                clk=self.CLK, cs=self.CS, 
                miso=self.MISO, mosi=self.MOSI, gpio=gpio
            )
            
            # Activer les deux broches d'activation
            RPI.output(self.EXTEND_EN_PIN, RPI.HIGH)
            RPI.output(self.RETRACT_EN_PIN, RPI.HIGH)
            
            # Relâcher le frein initialement
            self.release_brake()
            
            self.is_initialized = True
            if self.verbose:
                print("[BRAKE] Contrôleur de frein initialisé")
            
            return True
        except Exception as e:
            print(f"[BRAKE] Erreur d'initialisation: {e}")
            return False

    def apply_brake(self, duty):
        duty = self.BRAKE_DUTY
        self.retract_pwm.start(0.0)
        self.extend_pwm.start(duty)
        self.is_braking = True

    def release_brake(self, duty):
        duty = self.BRAKE_DUTY
        self.retract_pwm.start(duty)
        self.extend_pwm.start(0.0)
        self.is_braking = False

    def stop():
        retract_pwm.start(0.0)
        extend_pwm.start(0.0)

    def read_motor_position(channel = 1):
        position = mpc.read_adc(channel)
        return position
