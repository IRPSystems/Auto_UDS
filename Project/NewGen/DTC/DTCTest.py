import can
import isotp
from udsoncan.connections import PythonIsoTpConnection
from udsoncan.client import Client
from udsoncan import configs
import pandas as pd
from tabulate import tabulate


# CAN interface setup
can_interface = 'pcan'
channel = 'PCAN_USBBUS1'
tx_id = 0x1CFFFEF9
rx_id = 0x1CFFF9FE

# ISO-TP addressing
tp_addr = isotp.Address(isotp.AddressingMode.Normal_29bits, txid=tx_id, rxid=rx_id)
bus = can.Bus(channel=channel, interface=can_interface, bitrate=500000)
stack = isotp.CanStack(bus=bus, address=tp_addr)
conn = PythonIsoTpConnection(stack)

# Ordered list of status flags (bit 0 to bit 7)
status_flags = [
    "test_failed",                              # Bit 0
    "test_failed_this_operation_cycle",         # Bit 1
    "pending",                                  # Bit 2
    "confirmed",                                # Bit 3
    "test_not_completed_since_last_clear",      # Bit 4
    "test_failed_since_last_clear",             # Bit 5
    "test_not_completed_this_operation_cycle",  # Bit 6
    "warning_indicator_requested"               # Bit 7
]

# Map DTC codes to names
dtc_names = {
"331798": "MotorOverTemp",
"33179A": "MotorLowTemp",
"331709": "MotorTempSensor",
"332798": "ControllerOverTemp",
"33279A": "ControllerLowTemp",
"332709": "ControllerTempSensor",
"332193": "Phase_U_OverCurrentPeak",
"332197": "Phase_U_Sensor",
"33211D": "Phase_V_OverCurrentPeak",
"33219A": "Phase_V_Sensor",
"332191": "Phase_W_OverCurrentPeak",
"332413": "Phase_U_Disconnected",
"332414": "Phase_V_Disconnected",
"33241D": "Phase_W_Disconnected",
"33274B": "PreChargeOverTempCbit",
"332863": "PreChargeTimeout",
"332896": "PreChargeLatch",
"332816": "BusLowVoltage",
"332817": "BusHighVoltage",
"333814": "GateDriverVoltage",
"333544": "MemoryRead",
"333546": "CurrentFactory",
"331296": "PositionSensor",
"331693": "MotorStall",
"333891": "PerfDeratingBusVoltage",
"333586": "Project0",
"33118F": "MotorOverSpeedFault",
"D33391": "CanMb0Timeout",
"D33392": "CanMb1Timeout",
"D33394": "CanMb2Timeout",
"332796": "PreChargeTempSensor",
"332119": "BusOverCurrent",
"332196": "BusCurrentSensor",
"332894": "PreChargeUnderVoltage",
"333816": "VswUnderVoltage",
"F33300": "CanNoCom",
"F33387": "CanTimeout",
"332746": "I2T",
"332797": "PreChargeOverTempPbit",
"33289A": "Project1",
"332891": "Project3",
"332813": "Project2",
"33281C": "Project4",
"332793": "Project6",
"333792": "Project5",
"333791": "Project7",
"33174B": "Project8",
"331793": "Project10",
"332794": "Project11"
}

GREEN_CHECK = "\033[1;92m✓\033[0m"  # Bold bright green ✓
RED_CROSS = "\033[1;91m✗\033[0m"    # Bold bright red ✗

try:
    with Client(conn, request_timeout=1, config=configs.default_client_config) as client:
        print("Sending ReadDTCInformation (subfunction 0x02 with mask 0xFF)...")
        response = client.read_dtc_information(subfunction=0x02, status_mask=0x27)

        print(f"\nNumber of DTCs: {response.service_data.dtc_count}")

        rows = []
        for dtc in response.service_data.dtcs:
            dtc_id = f"{dtc.id:06X}"
            fault_name = dtc_names.get(dtc_id, "(Unknown)")
            row = {
                "DTC Code": dtc_id,
                "Fault Name": fault_name
            }
            status = dtc.status
            for flag in reversed(status_flags):
                row[flag] = GREEN_CHECK if getattr(status, flag) else " "
            rows.append(row)

        df = pd.DataFrame(rows)

        # Convert all to string
        df = df.astype(str)

        # Build alignment list
        colalign = []
        for col in df.columns:
            if col in ["DTC Code", "Fault Name"]:
                colalign.append("left")
            else:
                colalign.append("center")

        print(tabulate(df, headers="keys", tablefmt="fancy_grid", showindex=False, colalign=colalign))

except Exception as e:
    print(f"❌ Error communicating with ECU: {e}")

finally:
    bus.shutdown()