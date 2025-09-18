import logging
import os
import re
import glob
import shutil
from datetime import datetime
from Condition import (id_conditions_F1D2, id_conditions_F1D3, id_conditions_Fault_Config,
                       id_conditions_TrueDrive, id_conditions_Routine, id_conditions_F1D5,
                       id_conditions_CanConfig_103, id_Standart_Generetic)
from logger import setup_logger

SKIP_IDENTIFIERS = {""}

SUPPRESS_NRC_DIDS = {
     "0100", "0101", "0102"
}

Logs_folder = os.path.join("Logs")
if not os.path.exists(Logs_folder):
    os.mkdir(Logs_folder)

def extract_script_name(line):
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
            elif len(values) == 2:
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
    conditions = []
    if script_name == "Network_TimeOut_F1D2":
        condition_dict = id_conditions_F1D2.ID_CONDITIONS
    elif script_name == "Network_Missmatch_F1D3":
        condition_dict = id_conditions_F1D3.ID_CONDITIONS
    elif script_name == "Faults_Configuration":
        condition_dict = id_conditions_Fault_Config.ID_CONDITIONS
    elif script_name == "TrueDriveManager":
        condition_dict = id_conditions_TrueDrive.ID_CONDITIONS
    elif script_name == "Routine_Control":
        condition_dict = id_conditions_Routine.ID_CONDITIONS
    elif script_name == "Network_F1D5":
        condition_dict = id_conditions_F1D5.ID_CONDITIONS
    elif script_name == "CanConfig_103":
        condition_dict = id_conditions_CanConfig_103.ID_CONDITIONS
    else:
        condition_dict = {}
    for key, value in condition_dict.items():
        value_parts = value.split()
        for i, part in enumerate(value_parts):
            if part != "00" and i == position:
                conditions.append(key)
    return conditions if conditions else ["Unknown Condition"]

def process_uds_file(file_path, logger):
    logger.info(f"Processing file: {file_path}")
    script_sections = []  # List to store (script_name, tx_lines, rx_lines, all_lines) for each script
    current_tx_lines, current_rx_lines, current_all_lines = [], [], []
    current_lines = []  # Temporary storage for lines in a script section
    current_script_name = None
    script_started = False

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Check for script start marker using regex
            if re.search(r">>>\s*Script Start", line):
                if script_started and current_script_name:
                    # Save the previous script section
                    script_sections.append((current_script_name, current_tx_lines, current_rx_lines, current_all_lines))
                    logger.debug(f"Saved script section: {current_script_name} with {len(current_tx_lines)} Tx lines and {len(current_rx_lines)} Rx lines")
                # Start a new script section
                current_script_name = extract_script_name(line)
                if not current_script_name:
                    current_script_name = f"unknown_script_{len(script_sections) + 1}"
                script_started = True
                current_tx_lines, current_rx_lines, current_all_lines, current_lines = [], [], [], []
                current_lines.append(line)
                current_all_lines.append((line, "Other"))
                logger.debug(f"Script start marker found: {line}, Script name: {current_script_name}")
                continue

            # Check for script end marker using regex
            if re.search(r"<<< Script End", line):
                if script_started and current_script_name:
                    # Process Routine_Control lines before saving
                    if current_script_name == "Routine_Control":
                        fixed_lines = []
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        for line in current_lines:
                            if re.search(r">>> Script Start", line):
                                match = re.search(r">>> Script Start:(.*\\Scripts\\([^\\]+)\.script)", line)
                                fixed_lines.append(f"{timestamp} >>> Script Start:{match.group(1)}")
                                continue
                            if re.search(r"<<< Script End", line, re.IGNORECASE):
                                fixed_lines.append(f"{timestamp} <<< Script End")
                                continue
                            values = extract_values_from_line(line)
                            if (line.startswith("Tx)") and "Routine Control" in line and
                                    current_script_name == "Routine_Control" and len(values) >= 3 and
                                    values[:3] == ["0x01", "0x02", "0x01"]):
                                # Extract payload after the first 3 values, limit to 25 more (total 27)
                                payload_values = values[3:] if len(values) > 3 else []
                                if len(payload_values) >= 25:  # 2 prefix + 25 payload = 27 total
                                    payload_values = payload_values[:25]  # Truncate to 25
                                payload = " ".join(payload_values) if payload_values else ""
                                fixed_tx = f"{timestamp} Tx) Routine Control               : 0x02 0x01 {payload}"
                                fixed_lines.append(fixed_tx)
                                continue
                            if values and len(values) > 27:
                                truncated_values = " ".join(values[:27])
                                fixed_line = f"{timestamp} {line.split(':', 1)[0]}: {truncated_values}"
                                fixed_lines.append(fixed_line)
                            else:
                                fixed_lines.append(f"{timestamp} {line}")
                        # Reprocess fixed lines to update tx_lines, rx_lines, all_lines
                        current_tx_lines, current_rx_lines, current_all_lines = [], [], []
                        for fixed_line in fixed_lines:
                            if fixed_line.startswith(f"{timestamp} Tx)"):
                                current_tx_lines.append(fixed_line)
                                current_all_lines.append((fixed_line, "Tx"))
                            elif fixed_line.startswith(f"{timestamp} Rx)"):
                                current_rx_lines.append(fixed_line)
                                current_all_lines.append((fixed_line, "Rx"))
                            else:
                                current_all_lines.append((fixed_line, "Other"))
                    script_sections.append((current_script_name, current_tx_lines, current_rx_lines, current_all_lines))
                    logger.debug(f"Saved script section: {current_script_name} with {len(current_tx_lines)} Tx lines and {len(current_rx_lines)} Rx lines")
                    script_started = False
                    current_script_name = None
                    current_tx_lines, current_rx_lines, current_all_lines, current_lines = [], [], [], []
                current_all_lines.append((line, "Other"))
                continue

            # Only process lines if within a script section
            if script_started:
                current_lines.append(line)
                if line.startswith("Tx)"):
                    current_tx_lines.append(line)
                    current_all_lines.append((line, "Tx"))
                elif line.startswith("Rx)"):
                    current_rx_lines.append(line)
                    current_all_lines.append((line, "Rx"))
                elif "Tester Present:ON" in line:
                    logger.info("\033[94mTester Present: ON \033[0m")
                    current_all_lines.append((line, "Other"))
                elif re.search(r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\s+ERROR:.*No response from ECU", line, re.IGNORECASE):
                    current_all_lines.append((line, "Error"))
                else:
                    current_all_lines.append((line, "Other"))

    # Save the last script section if it hasn't been closed
    if script_started and current_script_name:
        # Process Routine_Control lines before saving
        if current_script_name == "Routine_Control":
            fixed_lines = []
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for line in current_lines:
                if re.search(r">>> Script Start", line):
                    match = re.search(r">>> Script Start:(.*\\Scripts\\([^\\]+)\.script)", line)
                    fixed_lines.append(f"{timestamp} >>> Script Start:{match.group(1)}")
                    continue
                if re.search(r"<<< Script End", line, re.IGNORECASE):
                    fixed_lines.append(f"{timestamp} <<< Script End")
                    continue
                values = extract_values_from_line(line)
                if (line.startswith("Tx)") and "Routine Control" in line and
                        current_script_name == "Routine_Control" and len(values) >= 3 and
                        values[:3] == ["0x01", "0x02", "0x01"]):
                    # Extract payload after the first 3 values, limit to 25 more (total 27)
                    payload_values = values[3:] if len(values) > 3 else []
                    if len(payload_values) >= 25:  # 2 prefix + 25 payload = 27 total
                        payload_values = payload_values[:25]  # Truncate to 25
                    payload = " ".join(payload_values) if payload_values else ""
                    fixed_tx = f"{timestamp} Tx) Routine Control               : 0x02 0x01 {payload}"
                    fixed_lines.append(fixed_tx)
                    continue
                if values and len(values) > 27:
                    truncated_values = " ".join(values[:27])
                    fixed_line = f"{timestamp} {line.split(':', 1)[0]}: {truncated_values}"
                    fixed_lines.append(fixed_line)
                else:
                    fixed_lines.append(f"{timestamp} {line}")
            # Reprocess fixed lines to update tx_lines, rx_lines, all_lines
            current_tx_lines, current_rx_lines, current_all_lines = [], [], []
            for fixed_line in fixed_lines:
                if fixed_line.startswith(f"{timestamp} Tx)"):
                    current_tx_lines.append(fixed_line)
                    current_all_lines.append((fixed_line, "Tx"))
                elif fixed_line.startswith(f"{timestamp} Rx)"):
                    current_rx_lines.append(fixed_line)
                    current_all_lines.append((fixed_line, "Rx"))
                else:
                    current_all_lines.append((fixed_line, "Other"))
        script_sections.append((current_script_name, current_tx_lines, current_rx_lines, current_all_lines))
        logger.debug(f"Saved final script section: {current_script_name} with {len(current_tx_lines)} Tx lines and {len(current_rx_lines)} Rx lines")

    if not script_sections:
        logger.warning("No script sections found in file: %s", file_path)

    return script_sections

def strip_ansi_codes(file_path):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    cleaned_content = ansi_escape.sub('', content)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)

def process_tx_rx_lines(script_name, tx_lines, rx_lines, all_lines, logger):
    seen_identifiers = set()
    passed_identifiers = set()
    result_folder = None

    for tx_line in tx_lines:
        tx_values = extract_values_from_line(tx_line)
        if len(tx_values) == 2:
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
            Standart_Generetic_condition = get_condition_from_position(tx_position, script_name)[0]
        expected_condition = get_condition_from_position(tx_position, script_name)
        matched_rx_line = None
        for rx_line in rx_lines[:]:
            rx_values = extract_values_from_line(rx_line)
            if len(rx_values) == 2:
                rx_lines.remove(rx_line)
                continue
            if len(rx_values) >= 4:
                rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])
                if rx_identifier in SKIP_IDENTIFIERS:
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
            for condition in expected_condition:
                if rx_normalized == tx_normalized:
                    if script_name not in ["Standard_Identifiers", "Generetic_ECU_Read"]:
                        logger.info(
                            f"\033[34m{condition},\033[0m Converted result: \033[93m{result}\033[0m \033[32m Pass\033[0m ")
                        continue
                    if script_name in ["Standard_Identifiers", "Generetic_ECU_Read"]:
                        if result != "wrong output":
                            logger.info(
                                f"\033[93m{tx_identifier} \033[93m{Standart_Generetic_condition}\033[0m Matching Tx and Rx, Converted: \033[93m{result}\033[0m \033[32m Pass\033[0m")
                            passed_identifiers.add(tx_identifier)
                        else:
                            logger.error(
                                f"{tx_identifier} {Standart_Generetic_condition} Mismatch Tx and Rx, Condition: \033[93m{condition}\033[0m, Converted: wrong output Fail")
                else:
                    if script_name in ["Standard_Identifiers", "Generetic_ECU_Read"]:
                        logger.error(f"Mismatch Tx and Rx {tx_identifier} {Standart_Generetic_condition} wrong output Fail")
                    else:
                        logger.error(f"{condition}, Mismatch Tx and Rx {tx_identifier}, Fail")

    for i, (line, line_type) in enumerate(all_lines):
        if line_type == "Rx" and ("Negative Response" in line or "NRC=Sub Function Not Supported" in line):
            # Try to find the previous Tx
            for j in range(i - 1, -1, -1):
                prev_line, prev_type = all_lines[j]
                if prev_type == "Tx":
                    prev_values = extract_values_from_line(prev_line)
                    if len(prev_values) >= 2:
                        prev_identifier = "".join(b.replace("0x", "").upper() for b in prev_values[:2])
                        msg = line.split(':', 1)[1].strip()

                        # 0x78: Request Correctly Received - Response Pending
                        if "Request Correctly Received - Response Pending" in line:
                            if prev_identifier in SUPPRESS_NRC_DIDS:
                                # suppress 0x78 for configured DIDs
                                pass
                            else:
                                logger.error(f"{prev_identifier} Negative Response: {msg}")
                            break

                        # 0x12: Sub Function Not Supported — always show
                        if "NRC=Sub Function Not Supported" in line:
                            logger.error(f"{prev_identifier} Negative Response: {msg}")
                            break

                        # Any other Negative Response: suppress only if DID is listed
                        if prev_identifier not in SUPPRESS_NRC_DIDS:
                            logger.error(f"{prev_identifier} Negative Response: {msg}")
                        break
                    else:
                        # We have a Tx line but couldn't parse an identifier
                        msg = line.split(':', 1)[1].strip()
                        # Suppress orphaned 0x78 to avoid noise
                        if "Request Correctly Received - Response Pending" not in line:
                            logger.error(f"Unknown Negative Response: {msg} (previous Tx invalid)")
                        break
            else:
                # No previous Tx found
                msg = line.split(':', 1)[1].strip()
                # Suppress orphaned 0x78 to avoid noise
                if "Request Correctly Received - Response Pending" not in line:
                    logger.error(f"Unknown Negative Response: {msg} (no previous Tx found)")

        elif line_type == "Error":
            for j in range(i - 1, -1, -1):
                prev_line, prev_type = all_lines[j]
                if prev_type == "Tx":
                    prev_values = extract_values_from_line(prev_line)
                    if len(prev_values) >= 2:
                        prev_identifier = "".join(b.replace("0x", "").upper() for b in prev_values[:2])
                        timestamp = line[:21] if len(line) >= 19 else "Unknown timestamp"
                        logger.error(f"{prev_identifier} No response from ECU detected at {timestamp}")
                    else:
                        timestamp = line[:21] if len(line) >= 19 else "Unknown timestamp"
                        logger.error(f"Unknown No response from ECU detected at {timestamp} (previous Tx invalid)")
                    break
            else:
                timestamp = line[:21] if len(line) >= 19 else "Unknown timestamp"
                logger.error(f"Unknown No response from ECU detected at {timestamp} (no previous Tx found)")

    for rx_line in rx_lines:
        rx_values = extract_values_from_line(rx_line)
        if len(rx_values) < 3:
            continue
        rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])
        if rx_identifier == "F195":
            result = convert(rx_values[2:])
            if result and result != "0" and result != "wrong output":
                result_folder = os.path.join("Logs", result)
                os.makedirs(result_folder, exist_ok=True)
                logger.debug(f"Creating folder at: {result_folder}")

        if rx_identifier in SKIP_IDENTIFIERS:
            continue
        if rx_identifier in passed_identifiers:
            continue
        seen_identifiers.add(rx_identifier)
        if "Request Correctly Received - Response Pending" in rx_line:
            # 0x78: suppress only for configured DIDs
            if rx_identifier in SUPPRESS_NRC_DIDS:
                continue
            else:
                logger.error(f"{rx_identifier}\033[91m Negative Response detected \033[0m")
            continue
        if "NRC=Sub Function Not Supported" in rx_line:
            # Always show this NRC
            logger.error(f"{rx_identifier}\033[91m Negative Response detected \033[0m")
            continue
        elif "Negative Response" in rx_line:
            # Other NRCs can be suppressed per DID
            if rx_identifier not in SUPPRESS_NRC_DIDS:
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
        rx_conditions = get_condition_from_position(rx_position, script_name) if rx_position >= 0 else ["Unknown Condition"]
        for condition in rx_conditions:
            if result == "wrong output":
                logger.error(
                    f"{rx_identifier} Read Data By Identifier, Condition: \033[91m{condition}\033[0m, Converted result: wrong output")
            elif result == "0":
                logger.info(
                    f"\033[93m{rx_identifier} {Standart_Generetic_condition} \033[0m Read Data By Identifier, Converted result: \033[93m0\033[0m, Raw Values: \033[93m{raw_values}\033[0m")
            else:
                if script_name in ["Standard_Identifiers"]:
                    logger.info(
                        f"\033[93m{rx_identifier} {Standart_Generetic_condition}\033[0m Read Data By Identifier, Converted result: \033[93m{result}\033[0m, Raw Values: \033[93m{raw_values}\033[0m")
                elif script_name in ["Generetic_ECU_Read"]:
                    logger.info(
                        f"\033[93m{rx_identifier} {Standart_Generetic_condition} \033[0m Read Data By Identifier, Converted result: \033[93m{result}\033[0m, Raw Values: \033[93m{raw_values}\033[0m")

    # Close and remove logger handlers
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
    return result_folder
if __name__ == "__main__":
    folder_path = r"C:\\temp3"
    files = glob.glob(os.path.join(folder_path, "*.uds.txt"))
    if not files:
        print("No matching files found.")
    else:
        newest_file = max(files, key=os.path.getmtime)
        logger = setup_logger("main", Logs_folder)
        logger.setLevel(logging.DEBUG)
        # Process all script sections
        script_sections = process_uds_file(newest_file, logger)
        if not script_sections:
            logger.warning("No script sections to process in %s", newest_file)
        else:
            result_folder = None
            for script_name, tx_lines, rx_lines, all_lines in script_sections:
                logger.info(f"Processing script section: {script_name}")
                script_logger = setup_logger(script_name, Logs_folder)
                script_logger.setLevel(logging.DEBUG)
                if tx_lines or rx_lines:
                    result=process_tx_rx_lines(script_name, tx_lines, rx_lines, all_lines, script_logger)

                    if result:  # only overwrite if we actually got a result
                        result_folder = os.path.basename(result)

            if result_folder:
                 os.environ['RESULT_FOLDER'] = result_folder
                 os.system('python modify_compliance_matrix.py')
            else:
                 logger.warning("No result folder was detected from logs. Compliance matrix not generated.")


