import re
from id_conditions import ID_CONDITIONS
from logger import setup_logger
import os
import glob

###logger = setup_logger()

SKIP_IDENTIFIERS = {"0100", "02", "F186"}

Logs_folder = os.path.join("Logs")
if not os.path.exists(Logs_folder):
    os.mkdir(Logs_folder)


#####
def extract_script_name(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if ">>> Script Start" in line:
                match = re.search(r">>> Script Start:(.*\\Scripts\\([^\\]+)\.script)", line)
                if match:
                    return match.group(2)  # Extract only the script name
    return None
####
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


def process_uds_file(file_path):
    logger.info(f"Processing file: {file_path}")
    tx_lines, rx_lines = [], []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Tx)"):
                tx_lines.append(line.strip())
            elif line.startswith("Rx)"):
                rx_lines.append(line.strip())
    return tx_lines, rx_lines


def process_tx_rx_lines(tx_lines, rx_lines):
    global logger
    seen_identifiers = set()
    passed_identifiers = set()

    logger.debug(f"Initial RX lines: {rx_lines}")

    for tx_line in tx_lines:
        tx_values = extract_values_from_line(tx_line)

        if len(tx_values) == 2:
            logger.debug(f"Skipping TX line with only two bytes: {tx_line}")
            continue


        if len(tx_values) < 3:
            continue

        tx_identifier = "".join(byte.replace("0x", "").upper() for byte in tx_values[:2])

        if tx_identifier in SKIP_IDENTIFIERS:
            logger.debug(f"Skipping TX identifier: {tx_identifier}")
            continue

        matched_rx_line = None

        for rx_line in rx_lines[:]:
            rx_values = extract_values_from_line(rx_line)

            # Skip RX lines with only two bytes
            if len(rx_values) == 2:
                logger.debug(f"Skipping RX line with only two bytes: {rx_line}")
                rx_lines.remove(rx_line)
                continue

            if len(rx_values) >= 4:
                rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])


                if rx_identifier in SKIP_IDENTIFIERS:
                    logger.debug(f"Skipping RX identifier: {rx_identifier}")
                    rx_lines.remove(rx_line)
                    continue

                if tx_identifier == rx_identifier:
                    matched_rx_line = rx_line
                    rx_lines.remove(rx_line)
                    break

        if matched_rx_line:
            rx_values = extract_values_from_line(matched_rx_line)

            logger.debug(f"Matched RX line: {matched_rx_line}")
            logger.debug(f"Remaining RX lines after removal: {rx_lines}")


            logger.debug(f"Raw TX values: {tx_values[2:]}")
            logger.debug(f"Raw RX values: {rx_values[2:]}")

            tx_normalized = normalize_values(tx_values[2:])
            rx_normalized = normalize_values(rx_values[2:])

            logger.debug(f"Normalized TX values: {tx_normalized}")
            logger.debug(f"Normalized RX values: {rx_normalized}")

            if rx_normalized == tx_normalized:
                # Convert and validate the result
                result = convert(tx_values[2:])
                logger.debug(f"Conversion result: {result}")
                if result != "0" and result != "wrong output":
                    logger.info(f"Matching Tx and Rx {tx_identifier}, Converted: {result} Pass")
                    passed_identifiers.add(tx_identifier)
                else:
                    logger.error(f"Mismatch Tx and Rx {tx_identifier}, Converted: wrong output Fail")
            else:
                logger.error(f"Mismatch Tx and Rx {tx_identifier}, Converted: wrong output Fail")

    logger.debug(f"Remaining RX lines before standalone processing: {rx_lines}")

    # Process remaining RX lines
    for rx_line in rx_lines:
        rx_values = extract_values_from_line(rx_line)

        if len(rx_values) == 2:
            logger.debug(f"Skipping RX line with only two bytes: {rx_line}")
            continue

        rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])

        if rx_identifier == "F181":
            result = convert(rx_values[2:])
            if result and result != "0" and result != "wrong output":
                result_folder = os.path.join("Logs", result)
                os.makedirs(result_folder, exist_ok=True)
               # logger = setup_logger(script_name, Logs_folder, custom_folder=result)
                logger.debug(f"Creating folder at: {result_folder}")

        # Skip specific identifiers
        if rx_identifier in SKIP_IDENTIFIERS:
            logger.debug(f"Skipping RX identifier: {rx_identifier}")
            continue

        if rx_identifier in passed_identifiers:
            logger.debug(f"Skipping already matched RX identifier: {rx_identifier}")
            continue

        if rx_identifier in seen_identifiers:
            logger.debug(f"Skipping already processed RX identifier: {rx_identifier}")
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
        if result == "0" or result == "wrong output":
            logger.error(f"{rx_identifier} Read Data By Identifier: Converted result: wrong output")
        else:
            logger.info(f"{rx_identifier} Read Data By Identifier: Converted result: {result}")


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

        tx_lines, rx_lines = process_uds_file(newest_file)

        if tx_lines or rx_lines:
            process_tx_rx_lines(tx_lines, rx_lines)