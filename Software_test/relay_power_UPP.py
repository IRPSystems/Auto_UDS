# relay_power_UPP.py
import os

import serial
import time, datetime



def power_cycle_relay(port: str = "COM3", off_time: float = 10.0):
    """
    Turn relay 1 ON (power off), wait `off_time` seconds,
    then turn relay 1 OFF (power on again).
    """
    BAUD = 9600

    ser = serial.Serial(port, BAUD, timeout=1)
    time.sleep(0.2)  # small pause after open

    def send_byte(b):
        if isinstance(b, int):
            b = bytes([b])
        ser.write(b)

    # Relay 1 ON (power off)
    send_byte(0x65)
    print("Relay 1 ON, power off: ", datetime.datetime.now())
    time.sleep(off_time)

    # Relay 1 OFF (power on)
    send_byte(0x6F)
    print("Relay 1 ON, power on: " , datetime.datetime.now())

    # optional: read state
    send_byte(0x5B)
    state = ser.read(1)
    print("State byte:", state, "int:", state[0] if state else None)

    ser.close()


if __name__ == "__main__":
    # test run if you execute this file directly
    power_cycle_relay()
