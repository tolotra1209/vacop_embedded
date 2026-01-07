import time
import SoloPy as solo
import RPi.GPIO as GPIO

TIMEOUT_S = 15

# ====== CONFIG A ADAPTER ======
M1 = {"port": "/dev/ttyAMA0", "node": 1, "sto": 16}
M2 = {"port": "/dev/ttyAMA3", "node": 2, "sto": 26}
BAUD = solo.UartBaudRate.RATE_937500
# ==============================

def connect_uart(port, node):
    s = solo.SoloMotorControllerUart(port, node, BAUD)
    deadline = time.time() + TIMEOUT_S
    ok = False
    last_err = None
    while time.time() < deadline and not ok:
        time.sleep(0.3)
        ok, last_err = s.communication_is_working()
    if not ok:
        raise RuntimeError(f"[node {node}] UART {port}: communication failed (err={last_err})")
    return s

def configure_light(s, node_label=""):
    # config minimale (pas de calibration ici)
    s.set_command_mode(solo.CommandMode.DIGITAL)
    s.set_motor_type(solo.MotorType.BLDC_PMSM)
    s.set_feedback_control_mode(solo.FeedbackControlMode.HALL_SENSORS)
    s.set_control_mode(solo.ControlMode.TORQUE_MODE)

def set_sto(pin, enabled: bool):
    GPIO.output(pin, GPIO.HIGH if enabled else GPIO.LOW)

def stop_all(s1, s2):
    try:
        s1.set_torque_reference_iq(0.0)
    except Exception:
        pass
    try:
        s2.set_torque_reference_iq(0.0)
    except Exception:
        pass

def read_feedback(name, s):
    tq, e1 = s.get_quadrature_current_iq_feedback()
    sp, e2 = s.get_speed_feedback()
    print(f"{name} | torque(A)={tq} err={e1} | speed(RPM)={sp} err={e2}")

def main():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(M1["sto"], GPIO.OUT)
    GPIO.setup(M2["sto"], GPIO.OUT)

    # STO ON (sécurité active)
    set_sto(M1["sto"], True)
    set_sto(M2["sto"], True)

    print("Connecting M1...")
    s1 = connect_uart(M1["port"], M1["node"])
    print("Connecting M2...")
    s2 = connect_uart(M2["port"], M2["node"])
    print("OK: both connected")

    print("Config light...")
    configure_light(s1, "M1")
    configure_light(s2, "M2")
    print("OK: configured")

    # === Test 1: Forward 5s ===
    print("\nTEST: forward (5s)")
    s1.set_motor_direction(solo.Direction.CLOCKWISE)
    s2.set_motor_direction(solo.Direction.COUNTERCLOCKWISE)
    s1.set_torque_reference_iq(6)
    s2.set_torque_reference_iq(6)

    t0 = time.time()
    while time.time() - t0 < 5:
        read_feedback("M1", s1)
        read_feedback("M2", s2)
        time.sleep(1)

    # === Test 2: Reverse 5s ===
    print("\nTEST: reverse (5s)")
    s1.set_motor_direction(solo.Direction.COUNTERCLOCKWISE)
    s2.set_motor_direction(solo.Direction.CLOCKWISE)
    s1.set_torque_reference_iq(4)
    s2.set_torque_reference_iq(4)

    t0 = time.time()
    while time.time() - t0 < 5:
        read_feedback("M1", s1)
        read_feedback("M2", s2)
        time.sleep(1)

    print("\nStopping...")
    stop_all(s1, s2)
    time.sleep(0.5)

    # STO OFF (safe torque off)
    set_sto(M1["sto"], False)
    set_sto(M2["sto"], False)
    print("Done.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCTRL+C -> stopping safely")
    finally:
        # Sécurité: torque=0 + STO off + cleanup
        try:
            GPIO.cleanup()
        except Exception:
            pass
