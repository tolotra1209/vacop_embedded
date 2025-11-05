import RPi.GPIO as GPIO
import SoloPy as solo
import time

# Motor Torque feedback
actualMotorTorque = 0

# Motor speed feedback
actualMotorSpeed = 0

# Désactiver les warnings GPIO
GPIO.setwarnings(False)

# Set the DEVICE as On Board Unit (OBU). It will be used to sort incoming can messages destined to this DEVICE
DEVICE = "OBU"

# Set GPIO mode to BCM
GPIO.setmode(GPIO.BCM)

# Set GPIO pins for the propulsion controller
DIR_1_PIN = 23   # chose the direction of the motor1 (HIGH = CCW) (LOW = CW)
DIR_2_PIN = 17   # chose the direction of the motor2 (HIGH = CCW) (LOW = CW)
SET_TORQUE_1_PIN = 24  # set the current applied to motor 1
SET_TORQUE_2_PIN = 22  # set the current applied to motor 2
STO1_PIN = 16    # Set Torque Off motor 1
STO2_PIN = 26    # Set Torque Off motor 2

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

# For this Test, make sure you have calibrated your Motor and Hall sensors before
# to know more please read: https://www.solomotorcontrollers.com/hall-sensors-to-solo-for-controlling-speed-torque-brushless-motor/

# RUN IT BEFORE TEST THE CODE ON RASPBERRY PI:
# sudo ip link set can0 up type can bitrate 1000000

try:
    # Instancier un objet SOLO
    mySolo = solo.SoloMotorControllersCanopen(2, solo.CanBusBaudRate.RATE_1000)

    # Attendre que la communication soit OK
    print("Trying to Connect To SOLO")
    communication_is_working = False
    while not communication_is_working:
        time.sleep(1)
        communication_is_working, error = mySolo.communication_is_working()

    print("Communication Established successfully!")

        # Initial Configuration of the device and the Motor
    mySolo.set_command_mode(solo.CommandMode.DIGITAL)
    mySolo.set_motor_type(solo.MotorType.BLDC_PMSM)
    mySolo.set_feedback_control_mode(solo.FeedbackControlMode.HALL_SENSORS)
    mySolo.set_control_mode(solo.ControlMode.TORQUE_MODE)

    # run the motor identification to Auto-tune the current controller gains Kp and Ki needed for Torque Loop
    # run ID. always after selecting the Motor Type!
    # ID. doesn't need to be called everytime, only one time after wiring up the Motor will be enough
    # the ID. values will be remembered by SOLO after power recycling
    mySolo.motor_parameters_identification(solo.Action.START)
    print("Identifying the Motor")
    # wait at least for 10sec till ID. is done
    time.sleep(10)

        # loop actions
    while True:
        # set the Direction on C.W.
        mySolo.set_motor_direction(solo.Direction.CLOCKWISE)
        # set an arbitrary Positive speed reference[RPM]
        mySolo.set_torque_reference_iq(8)
        # wait till motor reaches to the reference
        time.sleep(2)
        actualMotorTorque, error = mySolo.get_quadrature_current_iq_feedback()
        print("Measured Iq/Torque [A]: " + str(actualMotorTorque))
        actualMotorSpeed, error = mySolo.get_speed_feedback()
        print("Motor Speed [RPM]: " + str(actualMotorSpeed))
        time.sleep(2)

        # set the Direction on C.C.W.
        mySolo.set_motor_direction(solo.Direction.COUNTERCLOCKWISE)
        # set an arbitrary Positive speed reference[RPM]
        mySolo.set_torque_reference_iq(5)
        # wait till motor reaches to the reference
        time.sleep(1)
        actualMotorTorque, error = mySolo.get_quadrature_current_iq_feedback()
        print("Measured Iq/Torque [A]: " + str(actualMotorTorque))
        actualMotorSpeed, error = mySolo.get_speed_feedback()
        print("Motor Speed [RPM]: " + str(actualMotorSpeed))
        time.sleep(3)


finally:
    # Nettoyer correctement les GPIO à la fin
    GPIO.cleanup()
    print("GPIO libérés")
