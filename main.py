import re
from Condition import id_conditions_F1D2, id_conditions_F1D3, id_conditions_Fault_Config, id_conditions_TrueDrive
from logger import setup_logger
import os
import glob
import shutil
import logging

SKIP_IDENTIFIERS = {"0100", "02", "F186"}

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
    if len(values) < 3:
        return "wrong output"
    try:
        data = [int(x, 16) for x in values]
        while data and data[-1] == 0:
            data.pop()
        result = "".join(chr(x) for x in data)
        if result.strip() == "0" or not all(32 <= ord(c) <= 126 for c in result):
            return " ".join(str(x) for x in data)
        return result
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
    if script_name == "Network_TimeOut_F1D2":
        for key, value in id_conditions_F1D2.ID_CONDITIONS.items():
            value_parts = value.split()
            for i, part in enumerate(value_parts):
                if part != "00" and i == position:
                    return key
    elif script_name == "Network_Missmatch_F1D3":
        for key, value in id_conditions_F1D3.ID_CONDITIONS.items():
            value_parts = value.split()
            for i, part in enumerate(value_parts):
                if part != "00" and i == position:
                    return key
    elif script_name == "Faults_Configuration":
        for key, value in id_conditions_Fault_Config.ID_CONDITIONS.items():
            value_parts = value.split()
            for i, part in enumerate(value_parts):
                if part != "00" and i == position:
                    return key
    elif script_name == "TrueDriveManager":
        for key, value in id_conditions_TrueDrive.ID_CONDITIONS.items():
            value_parts = value.split()
            for i, part in enumerate(value_parts):
                if part != "00" and i == position:
                    return key
    return "Unknown Condition"

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

        if len(tx_values) < 3:
            continue

        tx_identifier = "".join(byte.replace("0x", "").upper() for byte in tx_values[:2])

        if tx_identifier in SKIP_IDENTIFIERS:
            #logger.debug(f"Skipping TX identifier: {tx_identifier}")
            continue

        tx_position = get_tx_position(tx_values)
        expected_condition = get_condition_from_position(tx_position, script_name) if tx_position >= 0 else "Unknown Condition"

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

            #logger.debug(f"Matched RX line: {matched_rx_line}")
            #logger.debug(f"Remaining RX lines after removal: {rx_lines}")
            #logger.debug(f"Raw TX values: {tx_values[2:]}")
            #logger.debug(f"Raw RX values: {rx_values[2:]}")
            #logger.debug(f"Normalized TX values: {tx_normalized}")
            #logger.debug(f"Normalized RX values: {rx_normalized}")

            if rx_normalized == tx_normalized:
                result = convert(tx_values[2:])
                if script_name != "Standard_Identifiers":
                     logger.debug(f"Conversion result: {result}")  #f1d2
                if result != "0" and result != "wrong output":
                    if script_name == "Standard_Identifiers":
                         logger.info(f"Matching Tx and Rx {tx_identifier}, Converted: \033[93m{result}\033[0m Pass")
                         passed_identifiers.add(tx_identifier)
                    else:
                        continue
                        #logger.info(f"Matching Tx and Rx {tx_identifier},  Pass")
                else:
                    logger.error(f"Mismatch Tx and Rx {tx_identifier}, Converted: wrong output Fail")
            else:
                if script_name == "Standard_Identifiers":
                    logger.error(f"Mismatch Tx and Rx {tx_identifier}, Converted: wrong output Fail")
                else:
                    logger.error(f"Mismatch Tx and Rx {tx_identifier}, {expected_condition} Fail")

    #logger.debug(f"Remaining RX lines before standalone processing: {rx_lines}")

    for rx_line in rx_lines:
        rx_values = extract_values_from_line(rx_line)

        if len(rx_values) == 2:
            #logger.debug(f"Skipping RX line with only two bytes: {rx_line}")
            continue

        if len(rx_values) < 3:
            if "Negative Response" in rx_line or "NRC=Sub Function Not Supported" in rx_line:
                logger.error(f"{tx_identifier}\033[91m Negative Response detected \033[0m")
            continue

        rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])

        if rx_identifier == "F181":
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

        if rx_identifier in seen_identifiers:
            #logger.debug(f"Skipping already processed RX identifier: {rx_identifier}")
            continue

        seen_identifiers.add(rx_identifier)
        if "Negative Response" in rx_line or "NRC=Sub Function Not Supported" in rx_line:
            tx_identifier = "".join(byte.replace("0x", "").upper() for byte in tx_values[:2])
            logger.error(f"{tx_identifier}\033[91m Negative Response detected \033[0m")
            continue
        if "Diagnostic Session Control " in rx_line:
            logger.warning(f"{tx_identifier}\033[94m Diagnostic Session Control \033[0m")
            continue
        if "Security Access " in rx_line:
            logger.warning(f"{tx_identifier}\033[94m Security Access \033[0m")
            continue

        result = convert(rx_values[2:])
        raw_values = " ".join(val.replace("0x", "") for val in rx_values[2:])
        if result == "0" or result == "wrong output":
            logger.error(f"{rx_identifier} Read Data By Identifier: Converted result: wrong output")
        else:
           ######## logger.info(f"{rx_identifier} Read Data By Identifier: Converted result: \033[93m{result}\033[0m, Raw Values:  \033[93m{raw_values}")
           logger.info(
               f"\033[93m{rx_identifier}\033[0m Read Data By Identifier: Converted result: \033[93m{result}\033[0m, Raw Values: \033[93m{raw_values}\033[0m")


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
        print(f"The newest file is: {newest_file}")

        script_name = extract_script_name(newest_file)
        if script_name is None:
            script_name = "default_log"

        logger = setup_logger(script_name, Logs_folder)
        logger.setLevel(logging.DEBUG)
        tx_lines, rx_lines = process_uds_file(newest_file)

        if tx_lines or rx_lines:
            process_tx_rx_lines(tx_lines, rx_lines)