import os
import time
import can
import isotp

from enum import Enum
from udsoncan import services
from udsoncan.client import Client
from udsoncan.connections import PythonIsoTpConnection
import logging
import clr  # pythonnet
from System.Collections.Generic import List
from System import String

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UDSStatusEnum(Enum):
    OK = 0
    NotInitialized = 1
    NoFileDefined = 2
    FileNotFound = 3
    InvalidCustomer = 4
    FlashError = 5

class ECustomer(Enum):
    GENERIC = 0
    NEWGEN = 1
    SILENCE = 2
    UPP = 3
    BOOTLOADER = 4
    NUM_CODES = 99

def flash(hex_path, xml_path, dll_path, customer_name):
    for label, path in [('HEX', hex_path), ('XML', xml_path), ('DLL', dll_path)]:
        if not path or not os.path.exists(path):
            logger.error(f"{label} file not found at: {path}")
            return UDSStatusEnum.FileNotFound

    customer_map = {
        "generic": ECustomer.GENERIC,
        "newgen": ECustomer.NEWGEN,
        "silence": ECustomer.SILENCE,
        "upp": ECustomer.UPP,
        "bootloader": ECustomer.BOOTLOADER
    }
    e_customer = customer_map.get(customer_name.lower())
    if e_customer is None:
        logger.error(f"Invalid customer name: {customer_name}")
        return UDSStatusEnum.InvalidCustomer

    bus = None
    client = None
    try:
        logger.info("Establishing CAN and UDS connection...")
        bus = can.Bus(channel='PCAN_USBBUS1', interface='pcan', bitrate=500000)
        tp_addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=0x7D0, rxid=0x7D8)
        stack = isotp.CanStack(bus=bus, address=tp_addr)
        conn = PythonIsoTpConnection(stack)
        client = Client(conn, request_timeout=1.0)
        with client:
            client.change_session(services.DiagnosticSessionControl.Session.defaultSession)
            client.change_session(services.DiagnosticSessionControl.Session.extendedDiagnosticSession)
            logger.info("UDS handshake successful")
    except Exception as e:
        logger.error(f"Failed to initialize CAN/UDS connection: {e}")
        return UDSStatusEnum.FlashError

    try:
        logger.info("Loading .NET DLL and invoking handleUserDefinedSequence()")
        clr.AddReference(dll_path)

        from Iso15765Namespace import IsoHandler, SBLState, ECustomer as DotNetCustomer

        iso = IsoHandler()

        # Build stateList based on XML or static example
        state_list = List[SBLState]()
        step = SBLState()
        step.mState = 0  # Replace with enum or valid integer
        step.mRetry = 0
        state_list.Add(step)

        dotnet_customer_code = getattr(DotNetCustomer, customer_name.upper())

        result = iso.handleUserDefinedSequence(
            String(hex_path),
            state_list,
            dotnet_customer_code
        )

        if result < 0:
            logger.error("❌ Flashing failed. DLL returned error code: %d", result)
            return UDSStatusEnum.FlashError

        logger.info("✅ Flashing completed successfully.")
        return UDSStatusEnum.OK

    except Exception as e:
        logger.error(f".NET DLL invocation failed: {e}")
        return UDSStatusEnum.FlashError
    finally:
        if client:
            try:
                client.close()
                logger.info("UDS client closed")
            except Exception as e:
                logger.warning(f"Failed to close UDS client: {e}")
        if bus:
            try:
                bus.shutdown()
                logger.info("CAN bus shut down")
            except Exception as e:
                logger.warning(f"Failed to shut down CAN bus: {e}")

if __name__ == "__main__":
    flash_result = flash(
        hex_path=r"C:\Users\ilyar\Desktop\UPP\UPP_v3.01.06\FW Merged\HD_Gen2_Merge_App_UPP_v3.01.06.brn.hex",
        xml_path=r"C:\Users\ilyar\PycharmProjects\UDS\Flashing\UDS_Messages.xml",
        dll_path=r"C:\Users\ilyar\PycharmProjects\UDS\Flashing\iso15765.dll",
        customer_name="UPP"
    )
    print("Flash result:", flash_result.name)
