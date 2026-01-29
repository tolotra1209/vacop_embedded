#!/usr/bin/env python3
import RPi.GPIO as RPI
import time
import Adafruit_GPIO.GPIO as AGPIO
import Adafruit_MCP3008

# --- Configuration des pins GPIO (BCM mode) ---
CLK = 21   # Pin CLK (GPIO 21)
MISO = 19  # Pin MISO (GPIO 19)
MOSI = 20  # Pin MOSI (GPIO 20)
CS = 7     # Pin CS (GPIO 7)

# --- Configuration des GPIO pour contrôle du moteur ---
EXTEND_PWM_PIN = 12
RETRACT_PWM_PIN = 13
EXTEND_EN_PIN  = 24
RETRACT_EN_PIN = 23

# Réglage de la fréquence PWM
PWM_FREQ = 1000  # Fréquence en Hz
DUTY = 70     # Pourcentage de puissance (ajuste si besoin)

# Seuils du frein
BRAKE_RELEASED = 300
BRAKE_PRESSED = 670

# --- Initialisation des GPIO ---
RPI.setmode(RPI.BCM)  # Utilisation du mode BCM pour les broches GPIO
RPI.setwarnings(False)  # Désactivation des avertissements

# Configuration des broches GPIO pour l'extension et la rétraction du moteur
RPI.setup([EXTEND_PWM_PIN, RETRACT_PWM_PIN, EXTEND_EN_PIN, RETRACT_EN_PIN], RPI.OUT)

# --- Initialisation des PWM ---
extend_pwm = RPI.PWM(EXTEND_PWM_PIN, PWM_FREQ)
retract_pwm = RPI.PWM(RETRACT_PWM_PIN, PWM_FREQ)
extend_pwm.start(0)
retract_pwm.start(0)

# --- Initialisation du MCP3008 avec bit-banging ---
gpio = AGPIO.RPiGPIOAdapter(RPI)  # Adapter RPi.GPIO à Adafruit_GPIO
mcp = Adafruit_MCP3008.MCP3008(clk=CLK, cs=CS, miso=MISO, mosi=MOSI, gpio=gpio)

# --- Fonction pour lire la position du moteur ---
def read_motor_position(channel=1):
    # Lire la valeur du canal (par défaut canal 1)
    position = mcp.read_adc(channel)
    return position

# --- Fonction pour arrêter le moteur ---
def stop():
    # Arrêter tout mouvement
    retract_pwm.start(0)
    extend_pwm.start(0)    

def apply_brake():
    print("Frein activé")

    RPI.output(EXTEND_EN_PIN, RPI.HIGH)

    extend_pwm.start(DUTY)
    time.sleep(1)
    
    while True:
        motor_position = read_motor_position()
        print(f"Position : {motor_position}")

        if motor_position >= BRAKE_PRESSED:
            print("Position atteinte")
            break

        time.sleep(0.02)

    print("Fin")
    stop()

def released_brake():
    print("Frein rétracté")

    RPI.output(RETRACT_EN_PIN, RPI.HIGH)

    retract_pwm.start(DUTY)
    
    while True:
        motor_position = read_motor_position()
        print(f"Position : {motor_position}")

        if motor_position <= BRAKE_RELEASED:
            print("Position atteinte")
            break

        time.sleep(0.02)

    print("Fin")
    stop()

# --- Exemple d'utilisation ---
try:
    # Test des commandes d'activation et de désactivation du moteur
    apply_brake()
    time.sleep(3)
    released_brake()

finally:
    stop()
