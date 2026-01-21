import time
import argparse

from CAN_system.CANSystem_p import CANSystem
from back_part.DualMotorController import DualMotorController
from back_part.SteerController import SteerController


def test_motors_forward(motors):
    print("\n=== TEST 1 : MOTEURS EN AVANT ===")
    motors.set_forward()
    motors.set_torque(5.0)
    time.sleep(3)
    motors.set_torque(0.0)
    print("OK moteurs avant")


def test_steering(can, steer):
    print("\n=== TEST 2 : DIRECTION ===")
    steer.enable(True)

    steer.on_feedback(511)
    steer.set_target(1023)
    for _ in range(20):
        steer.update()
        time.sleep(0.05)

    steer.set_target(0)
    for _ in range(20):
        steer.update()
        time.sleep(0.05)

    steer.enable(False)
    print("OK direction")


def test_brake(can):
    print("\n=== TEST 3 : FREIN ===")
    print("Activation frein")
    can.can_send("BRAKE", "start", 0)
    time.sleep(2)

    print("Désactivation frein")
    can.can_send("BRAKE", "stop", 0)
    time.sleep(1)

    print("OK frein")


def main(verbose=False):
    print("===== MODE TEST =====")

    # --- CAN ---
    can = CANSystem(verbose=verbose, device_name="TEST")
    can.start_listening()

    # --- MOTEURS ---
    motors = DualMotorController(verbose=verbose)
    motors.configure()

    # --- DIRECTION ---
    steer = SteerController(can, kp=0.8, max_step=30, verbose=verbose)

    try:
        test_motors_forward(motors)
        test_steering(can, steer)
        test_brake(can)

    except KeyboardInterrupt:
        print("\nInterruption utilisateur")

    except Exception as e:
        print(f"\nERREUR pendant les tests : {e}")

    finally:
        print("\nArrêt propre...")
        try:
            motors.stop_motor()
        except Exception:
            pass

        steer.enable(False)
        can.stop()

        print("Tests terminés.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    main(verbose=args.verbose)
