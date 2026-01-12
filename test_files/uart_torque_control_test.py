import RPi.GPIO as GPIO
import SoloPy as solo
import time

# Motor Torque feedback
actualMotorTorque = 0
# Motor speed feedback
actualMotorSpeed = 0

# Désactiver les warnings GPIO
GPIO.setwarnings(False)

# Set GPIO mode to BCM
GPIO.setmode(GPIO.BCM)

# Set GPIO pins for the propulsion controller
DIR_1_PIN = 23   # (si tu l'utilises) direction externe - ici SOLO gère la direction en interne
DIR_2_PIN = 17
SET_TORQUE_1_PIN = 24
SET_TORQUE_2_PIN = 22
STO1_PIN = 16    # Safe Torque Off motor 1
STO2_PIN = 26    # Safe Torque Off motor 2

# Initialisation des GPIO
GPIO.setup(DIR_1_PIN, GPIO.OUT)
GPIO.setup(DIR_2_PIN, GPIO.OUT)
GPIO.setup(SET_TORQUE_1_PIN, GPIO.OUT)
GPIO.setup(SET_TORQUE_2_PIN, GPIO.OUT)
GPIO.setup(STO1_PIN, GPIO.OUT)
GPIO.setup(STO2_PIN, GPIO.OUT)

# Activer les signaux STO (sécurité)
GPIO.output(STO1_PIN, GPIO.HIGH)
GPIO.output(STO2_PIN, GPIO.HIGH)

UART_PORT = "/dev/ttyAMA0"
NODE_ID = 1
UART_BAUD = solo.UartBaudRate.RATE_115200

TIMEOUT_S = 30

try:
    # Instancier un objet SOLO en UART
    mySolo = solo.SoloMotorControllerUart(UART_PORT, NODE_ID, UART_BAUD)

    # Attendre que la communication soit OK (timeout pour éviter boucle infinie)
    print("Trying to Connect To SOLO (UART)")
    deadline = time.time() + TIMEOUT_S
    communication_is_working = False

    while time.time() < deadline and not communication_is_working:
        time.sleep(0.5)
        communication_is_working, error = mySolo.communication_is_working()

    if not communication_is_working:
        raise RuntimeError(f"SOLO not reachable over UART after {TIMEOUT_S}s. Last error: {error}")

    print("Communication Established successfully!")

    # Initial Configuration of the device and the Motor
    mySolo.set_command_mode(solo.CommandMode.DIGITAL)
    mySolo.set_motor_type(solo.MotorType.BLDC_PMSM)
    mySolo.set_feedback_control_mode(solo.FeedbackControlMode.HALL_SENSORS)
    mySolo.set_control_mode(solo.ControlMode.TORQUE_MODE)

    # run the motor identification (autotune)
    mySolo.motor_parameters_identification(solo.Action.START)
    print("Identifying the Motor")
    time.sleep(10)

    # Calibration capteurs Hall (si ton setup l'exige)
    mySolo.sensor_calibration(solo.PositionSensorCalibrationAction.HALL_SENSOR_START_CALIBRATION)
    print("Hall Sensor calibration")
    time.sleep(10)

    # loop actions
    while True:
        # set the Direction on C.W.
        mySolo.set_motor_direction(solo.Direction.CLOCKWISE)
        # set an arbitrary Positive torque reference [A]
        mySolo.set_torque_reference_iq(8)
        time.sleep(2)

        actualMotorTorque, error = mySolo.get_quadrature_current_iq_feedback()
        print("Measured Iq/Torque [A]: " + str(actualMotorTorque) + " | Error: " + str(error))

        actualMotorSpeed, error = mySolo.get_speed_feedback()
        print("Motor Speed [RPM]: " + str(actualMotorSpeed) + " | Error: " + str(error))
        time.sleep(2)

        # set the Direction on C.C.W.
        mySolo.set_motor_direction(solo.Direction.COUNTERCLOCKWISE)
        mySolo.set_torque_reference_iq(8)
        time.sleep(1)

        actualMotorTorque, error = mySolo.get_quadrature_current_iq_feedback()
        print("Measured Iq/Torque [A]: " + str(actualMotorTorque) + " | Error: " + str(error))

        actualMotorSpeed, error = mySolo.get_speed_feedback()
        print("Motor Speed [RPM]: " + str(actualMotorSpeed) + " | Error: " + str(error))
        time.sleep(3)

finally:
    # Stop torque + STO pour être safe
    try:
        mySolo.set_torque_reference_iq(0.0)
    except Exception:
        pass

    try:
        GPIO.output(STO1_PIN, GPIO.LOW)
        GPIO.output(STO2_PIN, GPIO.LOW)
    except Exception:
        pass

    GPIO.cleanup()
    print("GPIO libérés")
