import os
import xml.etree.ElementTree as ET
import can
from udsoncan import configs
from intelhex import IntelHex
import isotp
from udsoncan import MemoryLocation, DataFormatIdentifier
from udsoncan.connections import PythonIsoTpConnection
from udsoncan.client import Client
from udsoncan import services, configs, DidCodec, Request, Response
import time
import logging
import argparse
import glob
from datetime import datetime
from ctypes import cdll, c_uint32, byref




# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Custom DidCodec for udsoncan 1.25.0
class CustomDidCodec(DidCodec):
    def encode(self, value):
        return value

    def decode(self, data):
        return data

    def __len__(self):
        return 0  # Dynamic length, adjust if ECU specifies fixed length


# Custom udsoncan configuration with DID definitions
custom_config = configs.default_client_config.copy()
custom_config['data_identifiers'] = {
    0x0001: CustomDidCodec(),
    0x0250: CustomDidCodec(),
    0x3231: CustomDidCodec(),
    0x0201: CustomDidCodec(),
    0xF195: CustomDidCodec(),
    0xF18B: CustomDidCodec(),
}


def parse_xml_config(xml_content):
    """Parse XML configuration and extract customer settings and steps."""
    try:
        root = ET.fromstring(xml_content)
        customer = root.attrib
        steps = [step.attrib for step in root.findall('FWStep')]
        iso_tp = root.find('ISO-TP').attrib if root.find('ISO-TP') is not None else {}
        return {
            'name': customer.get('Name'),
            'rate': int(customer.get('Rate', 500000)),
            'can_dev': customer.get('CanDev', 'PCAN'),
            'rx_id': int(customer.get('RxID', '0x7D8'), 16),
            'tx_id': int(customer.get('TxID', '0x7D0'), 16),
            'bc_id': int(customer.get('BCID', '0x7F8'), 16),
            'steps': steps,
            'iso_tp': {
                'block_size': int(iso_tp.get('ISO_TP_DEFAULT_BLOCK_SIZE', 8)),
                'st_min': int(iso_tp.get('ISO_TP_DEFAULT_ST_MIN', 0)),
                'response_timeout': int(iso_tp.get('ISO_TP_DEFAULT_RESPONSE_TIMEOUT', 1000)),
            }
        }
    except ET.ParseError as e:
        logger.error(f"Failed to parse XML: {e}")
        raise


def read_hex_file(file_path):
    """Read .brn.hex file and extract only the UDS-flashable region (0x6000-0xFFFF)."""
    try:
        ih = IntelHex(file_path)

        start_addr = 0x6000
        end_addr = 0x10000  # upper bound is exclusive

        if ih.minaddr() > start_addr or ih.maxaddr() < (end_addr - 1):
            logger.warning(f"HEX file range is {hex(ih.minaddr())}–{hex(ih.maxaddr())}, expected >=0x6000.")

        trimmed = ih.tobinarray(start=start_addr, end=end_addr - 1)
        logger.info(f"Read HEX file: {file_path}, trimmed region size: {len(trimmed)} bytes [0x6000–0xFFFF]")
        return bytes(trimmed)
    except Exception as e:
        logger.error(f"Failed to read and trim HEX file {file_path}: {e}")
        raise


def find_hex_file(folder_path, mode):
    """Find the latest .brn.hex file in the folder based on mode."""
    pattern = os.path.join(folder_path,
                           "HD_Gen2_Merge_App_UPP_v*.brn.hex" if mode == 'burn UPP' else "HD_Gen2_Merge_Boot_UPP_v*.brn.hex")
    files = glob.glob(pattern)
    if not files:
        logger.error(f"No HEX file found matching pattern: {pattern}")
        return None
    latest_file = max(files, key=os.path.getmtime)
    logger.info(f"Selected HEX file: {latest_file}")
    #breakpoint()
    return latest_file



def check_connection(client, max_attempts=8, timeout=2.0):
    """Verify CAN connection stability with DEFAULT_SESSION then EXTENDED_SESSION."""
    client.config['request_timeout'] = timeout
    for attempt in range(max_attempts):
        try:
            response = client.change_session(services.DiagnosticSessionControl.Session.defaultSession)
            logger.info("DEFAULT_SESSION successful")
            response = client.change_session(services.DiagnosticSessionControl.Session.extendedDiagnosticSession)
            logger.info("CAN connection stable: EXTENDED_SESSION successful")
            return True
        except Exception as e:
            logger.warning(f"Connection check failed, attempt {attempt + 1}/{max_attempts}: {e}")
        time.sleep(0.5)
    logger.error(f"Failed to establish stable connection after {max_attempts} attempts")
    return False


def generate_key_from_dll(seed):
    """Attempt to generate key using iso15765.dll."""
    dll_path = r"C:\Users\ilyar\PycharmProjects\UDS\Flashing\iso15765.dll"
    try:
        if not os.path.exists(dll_path):
            logger.error(f"DLL not found at: {dll_path}")
            return None
        logger.info(f"DLL found at: {dll_path}, size: {os.path.getsize(dll_path)} bytes")
        dll = cdll.LoadLibrary(dll_path)
        # Attempt to access generate_key, may fail due to no export table
        dll.generate_key.argtypes = [c_uint32]
        dll.generate_key.restype = c_uint32
        seed_int = int.from_bytes(seed, byteorder='big')
        key_int = dll.generate_key(seed_int)
        key = key_int.to_bytes(4, byteorder='big')
        logger.info(f"Generated key from DLL: {key.hex()}")
        return key
    except Exception as e:
        logger.error(f"Failed to generate key from DLL: {e}")
        return None


def execute_firmware_step(client, step, hex_data=None):
    """Execute a single firmware update step using udsoncan."""
    step_name = step.get('Name')
    retry = int(step.get('Retry', 0))
    param = step.get('Param')

    logger.info(f"Executing step: {step_name}")

    for attempt in range(retry + 1 if retry > 0 else 1):
        try:
            if step_name == 'EXTENDED_SESSION':
                response = client.change_session(services.DiagnosticSessionControl.Session.extendedDiagnosticSession)
                time.sleep(0.5)
                return response
            elif step_name == 'COMM_START':
                response = client.communication_control(
                    services.CommunicationControl.ControlType.enableRxAndTx,
                    communication_type=0x02
                )
                return response
            elif step_name == 'PROGRAMMING_SESSION':
                response = client.change_session(services.DiagnosticSessionControl.Session.programmingSession)
                return response
            elif step_name == 'SOFT_RESET':
                response = client.ecu_reset(services.ECUReset.ResetType.softReset)
                return response
            elif step_name == 'HARD_RESET':
                response = client.ecu_reset(services.ECUReset.ResetType.hardReset)
                return response
            elif step_name == 'COMM_STOP':
                try:
                    logger.info("→ Sending COMM_STOP")
                    response = client.communication_control(
                        services.CommunicationControl.ControlType.disableRxAndTx,
                        communication_type=0x02
                    )
                    logger.info("← COMM_STOP response: success")
                    return response
                except Exception as e:
                    logger.warning(f"COMM_STOP skipped due to error or no response: {e}")
                    return True  # Continue flashing process

            elif step_name == 'STOP_DTC':
                response = client.routine_control(0x0202, services.RoutineControl.ControlType.startRoutine)
                return response
            # elif step_name == 'START_DTC':
            #     payload = b'\x00'  # or actual payload if known
            #     response = client.routine_control(0x0201, services.RoutineControl.ControlType.startRoutine,
            #                                       data=payload)
                return response
            elif step_name == 'CLEAR_DTC':
                response = client.clear_dtc(group=0xFFFFFF)
                return response
            elif step_name == 'READ_APPL_ID':
                response = client.read_data_by_identifier(0xF18B)
                return response
            elif step_name == 'READ_APPL_VER':
                response = client.read_data_by_identifier(0xF195)
                return response
            elif step_name == 'READ_HISTORY_ZONE':
                response = client.read_data_by_identifier(0x0201)
                return response
            elif step_name == 'UPDATE_HISTORY_ZONE':
                payload = bytes.fromhex(
                    '00' +  # NumberInFlash
                    '0102' +  # TesterVersion
                    '4D43554143543030' +  # PrevApplSWID = "MCUACT00"
                    '4D43554143543030' +  # PrevApplDataID = "MCUACT00"
                    '1C0A07E8' +  # Date = 2024-10-28 (hex)
                    '0A1E'  # Time = 10:30 (hex)
                )
                response = client.routine_control(0x0201, services.RoutineControl.ControlType.startRoutine,
                                                  data=payload)

                return response
            elif step_name == 'SET_BOOT_FLAG':
                response = client.routine_control(0x0200, services.RoutineControl.ControlType.startRoutine)
                return response
            # elif step_name == 'CLEAR_BOOT_FLAG':
            #     routine_id = int(param, 16) if param else 0x0202
            #     response = client.routine_control(routine_id, services.RoutineControl.ControlType.startRoutine)
            #     return response
            elif step_name == 'ERASE_FLASH' or step_name == 'ERASE_BOOT_FLASH':
                routine_id = 0xFF00 if step_name == 'ERASE_FLASH' else 0xFF01
                response = client.routine_control(routine_id, services.RoutineControl.ControlType.startRoutine)
                return response
            elif step_name == 'CHECK_MEM':
                response = client.routine_control(0x0203, services.RoutineControl.ControlType.startRoutine)
                return response
            elif step_name == 'VALIDATE_APPL':
                response = client.routine_control(0x0204, services.RoutineControl.ControlType.startRoutine)
                return response
            elif step_name == 'SECURITY_ACCESS_LEVEL':
                response = client.request_seed(1)
                if response.positive:
                    seed = response.service_data.seed
                    logger.info(f"Received seed: {seed.hex()}")
                    # Skip DLL and use placeholder key
                    logger.warning("Using placeholder key due to DLL issues")
                    key = b'\x12\x34\x56\x78'
                    send_key_request = Request(service=services.SecurityAccess, subfunction=1, data=key)
                    response = client.send_request(send_key_request)
                    return response
                return None
            elif step_name == 'ACCESS_TIMING':
                response = client.set_timing_parameters(bytes([0x83, 0x00, 0x00, 0x03, 0xE8]))
                return response

            elif step_name == 'REQ_DOWNLOAD':

                if not hex_data:
                    logger.error("No HEX data provided for REQ_DOWNLOAD")
                    return None

                if not hex_data:
                    logger.error("No HEX data provided for REQ_DOWNLOAD")
                    return None
                dfi = DataFormatIdentifier(0x0, 0x0)
                mem_loc = MemoryLocation(0x00006000, 0xA000, 32, 32)
                logger.info(f"RequestDownload: Address=0x{mem_loc.address:X}, Size=0x{mem_loc.memorysize:X}")

                response = client.request_download(mem_loc, dfi)
                return response

            elif step_name == 'TRANSFER_DATA':

                if not hex_data:
                    logger.error("No HEX data provided for TRANSFER_DATA")
                    return None

                block_size = 256
                num_blocks = (len(hex_data) + block_size - 1) // block_size
                sequence_number = 1

                for i in range(num_blocks):
                    chunk = hex_data[i * block_size: (i + 1) * block_size]
                    logger.info(
                        f"TransferData<0x36> - Sending block #{i + 1}/{num_blocks}, SequenceNumber={sequence_number}, Size={len(chunk)} bytes")
                    try:
                        client.transfer_data(sequence_number, chunk)
                    except Exception as e:
                        logger.error(f"TransferData failed on block {i + 1}: {e}")
                        return None
                    sequence_number = (sequence_number + 1) % 256

                logger.info("All data blocks transferred. Sending TransferExit.")
                try:
                    client.request_transfer_exit()
                    return True
                except Exception as e:
                    logger.error(f"TransferExit failed: {e}")
                    return None


            elif step_name == 'TRANSFER_EXIT':
                response = client.request_transfer_exit()
                return response
            elif step_name == 'COMP_CS':
               # routine_id = int(param, 16) if param else 0xFF01
               # response = client.routine_control(routine_id, services.RoutineControl.ControlType.startRoutine)

               response = client.routine_control(0xFF01, services.RoutineControl.ControlType.startRoutine)

               return response

            elif step_name == 'DELAY':
                if param:
                    delay_ms = int(param) / 1000.0
                    logger.info(f"Delaying for {delay_ms} seconds")
                    time.sleep(delay_ms)
                    return True
                logger.error("DELAY step requires Param attribute")
                return None
            elif step_name == 'END_SESSION':
                response = client.change_session(services.DiagnosticSessionControl.Session.defaultSession)
                return response
            else:
                logger.error(f"Unknown step: {step_name}")
                return None
        except Exception as e:
            logger.error(f"Failed to execute step {step_name}, attempt {attempt + 1}/{retry + 1}: {e}")
            if attempt < retry:
                time.sleep(0.5)
                continue
            return None


def flash_controller(mode, folder_path, xml_content):
    """Main function to flash firmware or bootloader."""
    config = parse_xml_config(xml_content)
    logger.info(f"Parsed XML config for {config['name']}")

    hex_path = find_hex_file(folder_path, mode)
    if not hex_path:
        return False

    bus = None
    client = None
    try:
        can_interface = 'pcan'
        channel = 'PCAN_USBBUS1'
        tp_addr = isotp.Address(
            isotp.AddressingMode.Normal_11bits,
            txid=config['tx_id'],
            rxid=config['rx_id']
        )
        bus = can.Bus(
            channel=channel,
            interface=can_interface,
            bitrate=config['rate']
        )
        stack = isotp.CanStack(bus=bus, address=tp_addr)
        conn = PythonIsoTpConnection(stack)
        client = Client(conn, request_timeout=1.0, config=custom_config)
        logger.info(
            f"Connected to CAN bus: {can_interface}, channel={channel}, RxID=0x{config['rx_id']:03X}, TxID=0x{config['tx_id']:03X}")

        with client:
            if not check_connection(client):
                logger.error("Cannot proceed with flashing due to unstable connection")
                return False

            hex_data = read_hex_file(hex_path)

            for step in config['steps']:
                logger.info(f"→ Executing firmware step: {step.get('Name')}")

                result = execute_firmware_step(client, step, hex_data)
                if result is None:
                    logger.error(f"Step {step.get('Name')} failed, aborting")
                    return False
            logger.info(f"Successfully completed {mode} update")
            # if os.path.exists('modify_compliance_matrix.py'):
            #     logger.info("Running modify_compliance_matrix.py")
            #     os.system('python modify_compliance_matrix.py')
            return True
    except Exception as e:
        logger.error(f"Error during {mode} update: {e}")
        return False
    finally:
        if client:
            try:
                client.close()
                logger.info("UDS client closed")
            except Exception as e:
                logger.error(f"Failed to close UDS client: {e}")
        if bus:
            try:
                bus.shutdown()
                logger.info("CAN bus shut down")
            except Exception as e:
                logger.error(f"Failed to shut down CAN bus: {e}")


def main():
    parser = argparse.ArgumentParser(description="Flash firmware or bootloader to automotive controller")
    parser.add_argument('mode', choices=['burn UPP', 'burn boot'],
                        help="Update mode: 'burn UPP' for firmware, 'burn boot' for bootloader")
    parser.add_argument('folder_path', help="Path to folder containing .brn.hex file")
    args = parser.parse_args()

    firmware_xml = """
    <Customer Name="UPP" Rate="500000" CanDev="PCAN" RxID="0x7D8" TxID="0x7D0" BCID="0x7F8">
        <FWStep Name="EXTENDED_SESSION" />
        <FWStep Name="COMM_STOP" />
        <FWStep Name="SECURITY_ACCESS_LEVEL" />
        <FWStep Name="PROGRAMMING_SESSION" />
        <FWStep Name="SET_BOOT_FLAG" />
        <FWStep Name="UPDATE_HISTORY_ZONE" />
        <FWStep Name="ACCESS_TIMING" />
        <FWStep Name="ERASE_FLASH" />
        <FWStep Name="REQ_DOWNLOAD" />
        <FWStep Name="TRANSFER_DATA" />
        <FWStep Name="TRANSFER_EXIT" />
        <FWStep Name="COMP_CS" />
      <!--  <FWStep Name="CLEAR_BOOT_FLAG" /> --> 
        <FWStep Name="EXTENDED_SESSION" />
        <FWStep Name="SECURITY_ACCESS_LEVEL" />
        <FWStep Name="SOFT_RESET" />
        <FWStep Name="EXTENDED_SESSION" Retry="8" />
        <FWStep Name="COMM_START" />
     <!--   <FWStep Name="START_DTC" /> --> 
        <FWStep Name="CLEAR_DTC" />
        <FWStep Name="END_SESSION" />
        <ISO-TP ISO_TP_DEFAULT_BLOCK_SIZE="8" ISO_TP_DEFAULT_ST_MIN="0" ISO_TP_DEFAULT_RESPONSE_TIMEOUT="1000" />
    </Customer>
    """

    bootloader_xml = """
    <Customer Name="Bootloader" Rate="500000" CanDev="PCAN" RxID="0x7D8" TxID="0x7D0" BCID="0x7F8">
        <FWStep Name="EXTENDED_SESSION" />
        <FWStep Name="COMM_STOP" />
        <FWStep Name="ERASE_BOOT_FLASH" />
        <FWStep Name="REQ_DOWNLOAD" />
        <FWStep Name="TRANSFER_DATA" />
        <FWStep Name="TRANSFER_EXIT" />
        <FWStep Name="CHECK_MEM" />
        <FWStep Name="VALIDATE_APPL" />
        <FWStep Name="COMM_START" />
        <FWStep Name="END_SESSION" />
        <ISO-TP ISO_TP_DEFAULT_BLOCK_SIZE="8" ISO_TP_DEFAULT_ST_MIN="0" ISO_TP_DEFAULT_RESPONSE_TIMEOUT="1000" />
    </Customer>
    """

    xml_content = firmware_xml if args.mode == 'burn UPP' else bootloader_xml
    logger.info(f"Starting {args.mode} with folder: {args.folder_path}")

    if not os.path.isdir(args.folder_path):
        logger.error(f"Folder not found: {args.folder_path}")
        return

    success = flash_controller(args.mode, args.folder_path, xml_content)
    if success:
        logger.info(f"{args.mode} completed successfully")
    else:
        logger.error(f"{args.mode} failed")


if __name__ == "__main__":
    main()