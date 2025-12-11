import time
import serial

UARTS = [
    ("/dev/ttyAMA0", "UART0 (PL011)"), 
    ("/dev/ttyAMA3", "UART3"),
]
# ttyAMA0 => UART PRINCIPAL
# ttyAMA3 => DEUXIEME UART ACTIVE

BAUD = 937_500 

def send_and_read(port: str, label: str, msg: str) -> None:
    print(f"\n--- {label} on {port} @ {BAUD} ---")
    try:
        with serial.Serial(
            port=port,
            baudrate=BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.3,
            write_timeout=0.3,
        ) as ser:
            payload = (msg + "\r\n").enc
            ode("utf-8")

            ser.reset_input_buffer()
            ser.reset_output_buffer()

            print("Sending:", msg)
            ser.write(payload)
            ser.flush()

    except Exception as e:
        print("Error:", e)

def main():
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    for port, label in UARTS:
        send_and_read(port, label, f"HELLO {label} {ts}")

if __name__ == "__main__":
    main()
