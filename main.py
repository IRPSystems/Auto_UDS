import fix_routine_log
from Condition import (id_conditions_F1D2, id_conditions_F1D3, id_conditions_Fault_Config,
                       id_conditions_TrueDrive, id_conditions_Routine, id_conditions_F1D5, id_conditions_CanConfig_103, id_Standart_Generetic)
from logger import setup_logger
import os, re, glob, shutil, logging

#SKIP_IDENTIFIERS = {"0100", "02", "F186"}
SKIP_IDENTIFIERS = {"0100", "0102"}

Logs_folder = os.path.join("Logs")
if not os.path.exists(Logs_folder):
    os.mkdir(Logs_folder)

def extract_script_name(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if ">>> Script Start" in line:
                match = re.search(r">>> Script Start:(.*\\Scripts\\([^\\]+)\.script)", line)
                if match:
                    return match.group(2)

    return None

def extract_values_from_line(line):
    try:
        _, data_part = line.split(":", 1)
    except ValueError:
        return []
    return re.findall(r'0x[0-9A-Fa-f]{2}', data_part)

def normalize_values(values):
    return [x for x in values if x != "0x00"]

def convert(values):
    try:
        hex_str = " ".join(values).replace("0x00", "").strip()
        if not hex_str:
            return "0"
        values = hex_str.split()
        data = [int(x, 16) for x in values]
        if len(values) > 3:
            result = "".join(chr(x) for x in data)
            if all(32 <= ord(c) <= 126 for c in result):
                return result
            return " ".join(str(x) for x in data)
        else:  # 1-3 bytes
            combined_hex = "".join(x[2:] for x in values)
            unsigned_int = int(combined_hex, 16)
            if len(values) == 1:
                return str(unsigned_int)
            elif len(values) == 2:  #
                if unsigned_int >= 0x8000:
                    unsigned_int -= 0x10000
                return str(unsigned_int)
            elif len(values) == 3:  # 24-bit signed
                if unsigned_int >= 0x800000:
                    unsigned_int -= 0x1000000
                return str(unsigned_int)

    except ValueError:
        return "wrong output"

def get_tx_position(tx_values):
    for i, value in enumerate(tx_values[2:], start=0):

        if value != "0x00":
            return i
    return -1

def get_condition_from_position(position, script_name):
    if isinstance(script_name, tuple):
        script_name = script_name[0]
    conditions=[]
    if script_name == "Network_TimeOut_F1D2":
        condition_dict=id_conditions_F1D2.ID_CONDITIONS

    elif script_name == "Network_Missmatch_F1D3":
        condition_dict = id_conditions_F1D3.ID_CONDITIONS

    elif script_name == "Faults_Configuration":
        condition_dict= id_conditions_Fault_Config.ID_CONDITIONS

    elif script_name == "TrueDriveManager":
        condition_dict = id_conditions_TrueDrive.ID_CONDITIONS

    elif script_name == "Routine_Control":
       condition_dict = id_conditions_Routine.ID_CONDITIONS

    elif script_name == "Network_F1D5":
       condition_dict = id_conditions_F1D5.ID_CONDITIONS

    elif script_name == "CanConfig_103":
        condition_dict = id_conditions_CanConfig_103.ID_CONDITIONS
    else: condition_dict={}

    for key, value in condition_dict.items():
        value_parts = value.split()
        for i, part in enumerate(value_parts):
            if part != "00" and i == position:
                conditions.append(key)
    return conditions if conditions else ["Unknown Condition"]


def process_uds_file(file_path):
    logger.info(f"Processing file: {file_path}")
    tx_lines, rx_lines = [], []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Tx)"):
                tx_lines.append(line.strip())
            elif line.startswith("Rx)"):
                rx_lines.append(line.strip())
            elif "Tester Present:ON" in line:
                logger.info("\033[94mTester Present: ON \033[0m")
    return tx_lines, rx_lines

def strip_ansi_codes(file_path):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    cleaned_content = ansi_escape.sub('', content)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)

def process_tx_rx_lines(tx_lines, rx_lines):
    global logger, script_name
    seen_identifiers = set()
    passed_identifiers = set()
    result_folder = None

    #logger.debug(f"Initial RX lines: {rx_lines}")

    for tx_line in tx_lines:
        tx_values = extract_values_from_line(tx_line)


        if len(tx_values) == 2:
            #logger.debug(f"Skipping TX line with only two bytes: {tx_line}")
            continue

        if len(tx_values) < 2:
            continue

        tx_identifier = "".join(byte.replace("0x", "").upper() for byte in tx_values[:2])

        tx_position = get_tx_position(tx_values)
        if tx_position == -1:
            continue
        if script_name in ["Standard_Identifiers", "Generetic_ECU_Read"]:
            Standart_Generetic_condition = id_Standart_Generetic.ID_CONDITIONS.get(tx_identifier, "Unknown DID")
        else:
            Standart_Generetic_condition = get_condition_from_position(tx_position, script_name)[0]  # Take first condition

        expected_condition = get_condition_from_position(tx_position, script_name)

        matched_rx_line = None

        for rx_line in rx_lines[:]:
            rx_values = extract_values_from_line(rx_line)

            if len(rx_values) == 2:
                #logger.debug(f"Skipping RX line with only two bytes: {rx_line}")
                rx_lines.remove(rx_line)
                continue

            if len(rx_values) >= 4:
                rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])

                if rx_identifier in SKIP_IDENTIFIERS:
                    #logger.debug(f"Skipping RX identifier: {rx_identifier}")
                    rx_lines.remove(rx_line)
                    continue

                if tx_identifier == rx_identifier:
                    matched_rx_line = rx_line
                    rx_lines.remove(rx_line)
                    break

        if matched_rx_line:
            rx_values = extract_values_from_line(matched_rx_line)
            tx_normalized = normalize_values(tx_values[2:])
            rx_normalized = normalize_values(rx_values[2:])
            result = convert(tx_values[2:])
            #logger.debug(f"Matched RX line: {matched_rx_line}")
            #logger.debug(f"Remaining RX lines after removal: {rx_lines}")
            #logger.debug(f"Raw TX values: {tx_values[2:]}")
            #logger.debug(f"Raw RX values: {rx_values[2:]}")
            #logger.debug(f"Normalized TX values: {tx_normalized}")
            #logger.debug(f"Normalized RX values: {rx_normalized}")

#Green: \033[32m (regular green) or \033[92m (bright green).
#Red: \033[31m (regular red) or \033[91m (bright red).
#Red appears via \033[91m in error messages
            for condition in expected_condition:
                if rx_normalized == tx_normalized:
                    if script_name not in ["Standard_Identifiers", "Generetic_ECU_Read"]:
                        logger.info(
                            f"\033[34m{condition},\033[0m Converted result: \033[93m{result}\033[0m \033[32m Pass\033[0m ")
                        continue
                    if script_name in ["Standard_Identifiers", "Generetic_ECU_Read"]:
                        if result != "wrong output":  # Include "0" as a Pass
                            logger.info(
                                f"\033[93m{tx_identifier} {Standart_Generetic_condition}\033[0m Matching Tx and Rx, Converted: \033[93m{result}\033[0m \033[32m Pass\033[0m")
                            passed_identifiers.add(tx_identifier)
                        else:
                            logger.error(
                                f"{tx_identifier} {Standart_Generetic_condition} Mismatch Tx and Rx, Condition: \033[93m{condition}\033[0m, Converted: wrong output Fail")
                else:
                    if script_name in ["Standard_Identifiers", "Generetic_ECU_Read"]:
                        logger.error(f"Mismatch Tx and Rx {tx_identifier} {Standart_Generetic_condition} wrong output Fail")
                    else:
                        logger.error(f"{condition}  Mismatch Tx and Rx {tx_identifier}, Fail")

    #logger.debug(f"Remaining RX lines before standalone processing: {rx_lines}")

    for rx_line in rx_lines:
        rx_values = extract_values_from_line(rx_line)

        # if len(rx_values) == 2:
        #     #logger.debug(f"Skipping RX line with only two bytes: {rx_line}")
        #     continue

        if len(rx_values) < 3:
            if "Negative Response" in rx_line or "NRC=Sub Function Not Supported" in rx_line:
               logger.error(f"{rx_line.split(':')[0]}\033[91m")
            continue

        rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])


        if rx_identifier == "F195":

            result = convert(rx_values[2:])
            if result and result != "0" and result != "wrong output":
                result_folder = os.path.join("Logs", result)
                os.makedirs(result_folder, exist_ok=True)
                logger.debug(f"Creating folder at: {result_folder}")

        if rx_identifier in SKIP_IDENTIFIERS:
            #logger.debug(f"Skipping RX identifier: {rx_identifier}")
            continue

        if rx_identifier in passed_identifiers:
            #logger.debug(f"Skipping already matched RX identifier: {rx_identifier}")
            continue

        #disabled for F186, should read if the session has been changed
        # if rx_identifier in seen_identifiers:
        #     #logger.debug(f"Skipping already processed RX identifier: {rx_identifier}")
        #     continue

        seen_identifiers.add(rx_identifier)
        if "Negative Response" in rx_line or "NRC=Sub Function Not Supported" in rx_line:
            #rx_identifier = "".join(byte.replace("0x", "").upper() for byte in tx_values[:2])
            logger.error(f"{rx_identifier}\033[91m Negative Response detected \033[0m")
            continue

        if "Diagnostic Session Control " in rx_line:
            logger.warning(f"{rx_identifier}\033[94m Diagnostic Session Control \033[0m")
            continue
        if "Security Access " in rx_line:
            logger.warning(f"{rx_identifier}\033[94m Security Access \033[0m")
            continue
        Standart_Generetic_condition = id_Standart_Generetic.ID_CONDITIONS.get(rx_identifier, "Unknown DID")

        result = convert(rx_values[2:])
        raw_values = " ".join(val.replace("0x", "") for val in rx_values[2:])
        rx_position = get_tx_position(rx_values)
        rx_conditions = get_condition_from_position(rx_position, script_name) if rx_position >= 0 else [
            "Unknown Condition"]
        for condition in rx_conditions:
            if  result == "wrong output":
                logger.error(
                    f"{rx_identifier} Read Data By Identifier, Condition: \033[91m{condition}\033[0m, Converted result: wrong output")
            elif result == "0":
                logger.info(
                    f"\033[93m{rx_identifier} {Standart_Generetic_condition} \033[0m Read Data By Identifier, Converted result: \033[93m0\033[0m, Raw Values: \033[93m{raw_values}\033[0m")
            else:
               if script_name in ["Standard_Identifiers"]:   #### full print
                   logger.info(
                       f"\033[93m{rx_identifier} {Standart_Generetic_condition}\033[0m Read Data By Identifier: Converted result: \033[93m{result}\033[0m, Raw Values: \033[93m{raw_values}\033[0m")

               elif script_name in ["Generetic_ECU_Read"]:   #### full print
                   logger.info(
                       f"\033[93m{rx_identifier} {Standart_Generetic_condition} \033[0m Read Data By Identifier: Converted result: \033[93m{result}\033[0m, Raw Values: \033[93m{raw_values}\033[0m")

    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)
    if isinstance(script_name, tuple):
        script_name = script_name[0]

    original_log_file = os.path.join(Logs_folder, f"{script_name}.log")
    if result_folder and os.path.exists(original_log_file):
        new_log_file = os.path.join(result_folder, f"{script_name}.log")
        try:
            shutil.move(original_log_file, new_log_file)
            strip_ansi_codes(new_log_file)
            logger.debug(f"Created and cleaned log file in {new_log_file}")
        except Exception as e:
            logger.error(f"Failed to move or clean log file: {e}")
    elif os.path.exists(original_log_file):
        strip_ansi_codes(original_log_file)

if __name__ == "__main__":
    folder_path = r"C:\\temp3"
    files = glob.glob(os.path.join(folder_path, "*.uds.txt"))
    if not files:
        print("No matching files found.")
    else:
        newest_file = max(files, key=os.path.getmtime)
        #print(f"The newest file is: {newest_file}")

        script_name = extract_script_name(newest_file)
        if script_name is None:
            script_name = "default_log"

        if script_name == "Routine_Control":
            fixed_file = newest_file.replace(".uds.txt", "_fixed.uds.txt")
            fix_routine_log.fix_log_file(newest_file, fixed_file)
            newest_file = fixed_file
            print(f"Fixed Routine_Control log file: {fixed_file}")

        logger = setup_logger(script_name, Logs_folder)
        logger.setLevel(logging.DEBUG)
        tx_lines, rx_lines = process_uds_file(newest_file)

        if tx_lines or rx_lines:
            process_tx_rx_lines(tx_lines, rx_lines)