#!/usr/bin/env python3
import time
import subprocess
import can

CAN_IFACE = "can0"
BITRATE = 1_000_000

LOOPBACK = True

TX_ID = 0x123

def sh(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=True)

def setup_can():
    sh(f"sudo ip link set {CAN_IFACE} down || true")
    sh(f"sudo ip link set {CAN_IFACE} type can bitrate {BITRATE} loopback {'on' if LOOPBACK else 'off'} restart-ms 100")
    sh(f"sudo ip link set {CAN_IFACE} up")
    sh(f"ip -details link show {CAN_IFACE}")

def main():
    setup_can()

    bus = can.interface.Bus(channel=CAN_IFACE, bustype="socketcan")

    print(f"\nCAN ready on {CAN_IFACE} @ {BITRATE} bps | loopback={LOOPBACK}")
    print("Sending frames every 0.5s, and printing any received frames. Ctrl+C to stop.\n")

    counter = 0
    try:
        while True:
            # Envoi
            data = [counter & 0xFF, 0xDE, 0xAD, 0xBE, 0xEF, 0, 0, 0]
            msg = can.Message(arbitration_id=TX_ID, data=data, is_extended_id=False)
            bus.send(msg)
            print(f"TX  id=0x{TX_ID:X} data={data}")

            # Réception (0.5s de fenêtre)
            t_end = time.time() + 0.5
            while time.time() < t_end:
                rx = bus.recv(timeout=0.05)
                if rx is not None:
                    print(f"RX  id=0x{rx.arbitration_id:X} data={list(rx.data)}")

            counter = (counter + 1) % 256

    except KeyboardInterrup
