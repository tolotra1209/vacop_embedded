import RPi.GPIO as GPIO
import SoloPy as solo
import time


# Désactiver les warnings GPIO
GPIO.setwarnings(False)

# Set the DEVICE as On Board Unit (OBU). It will be used to sort incoming can messages destined to this DEVICE
DEVICE = "OBU"


# For this Test, make sure you have calibrated your Motor and Hall sensors before
# to know more please read: https://www.solomotorcontrollers.com/hall-sensors-to-solo-for-controlling-speed-torque-brushless-motor/

# RUN IT BEFORE TEST THE CODE ON RASPBERRY PI:
# sudo ip link set can0 up type can bitrate 1000000

try:
    # Instancier un objet SOLO
    mySolo = solo.SoloMotorControllersCanopen(1, solo.CanBusBaudRate.RATE_1000)

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

 
    while True:
        print("Read from SOLO -> Board Temperature: " + str(mySolo.get_board_temperature()))
        time.sleep(5)

finally:
    # Nettoyer correctement les GPIO à la fin
    GPIO.cleanup()
    print("GPIO libérés")
