import re
from id_conditions import ID_CONDITIONS
from logger import setup_logger
import os
import glob

logger = setup_logger()

def extract_values_from_line(line):
    try:
        _, data_part = line.split(":", 1)
    except ValueError:
        return []
    return re.findall(r'0x[0-9A-Fa-f]{2}', data_part)

def convert(values):
    try:
        data = [int(x, 16) for x in values]
        result = "".join(chr(x) for x in data)
        return result if all(32 <= ord(c) <= 126 for c in result) else "wrong output"
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

def convert(values):
    if len(values) < 3:
        return "wrong output"

    try:
        data = [int(x, 16) for x in values]


        while data and data[-1] == 0:
            data.pop()

        result = "".join(chr(x) for x in data)


        if result.strip() == "0" or not all(32 <= ord(c) <= 126 for c in result):
            return "wrong output"

        return result
    except ValueError:
        return "wrong output"


def validate_response(tx_values, rx_values, id_key):
    condition = ID_CONDITIONS.get(id_key, {})
    expected_length = condition.get("length")
    data_type = condition.get("data_type")
    description = condition.get("description", id_key)

    if expected_length and len(rx_values[2:]) != expected_length:
        logger.info(f"{id_key} {description} RX/TX match FAILED: Incorrect length")
        return False
    if data_type == "string":
        converted = convert(rx_values[2:])
        if converted == "wrong output":
            logger.info(f"{id_key} {description} RX/TX match FAILED: Incorrect data format")
            return False
        logger.info(f"{id_key} {description} RX/TX match PASS - Converted Output: {converted}")
    else:
        logger.info(f"{id_key} {description} RX/TX match PASS")
    return True

def process_tx_rx_lines(tx_lines, rx_lines):
    seen_identifiers = set()
    rx_identifier = 0

    for tx_line in tx_lines:
        tx_values = extract_values_from_line(tx_line)
        if len(tx_values) < 3:
            continue

        tx_identifier = "".join(byte.replace("0x", "").upper() for byte in tx_values[:2])

        matched_rx_line = None
        for rx_line in rx_lines:
            rx_values = extract_values_from_line(rx_line)
            if len(rx_values) >= 4:
                rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])

                if tx_identifier == rx_identifier:
                    matched_rx_line = rx_line
                    rx_lines.remove(rx_line)
                    break

        if matched_rx_line:
            rx_values = extract_values_from_line(matched_rx_line)


            logger.debug(f"Inspecting rx_values: {rx_values}")

            if "Negative Response" in rx_values or "NRC=Sub Function Not Supported" in rx_values:
                logger.error(f"Negative Response detected: {rx_values}")
                logger.error(f"Failed Response for Tx: {tx_line.split(':')[0]} {tx_identifier} : {' '.join(tx_values[2:])}")
                continue
            if rx_values[2:] == tx_values[2:]:
                logger.info(f"Matching Tx and Rx: {tx_line.split(':')[0]} {tx_identifier} : {' '.join(tx_values[2:])}")
                result = convert(tx_values[2:])
                if result != "0" and result != "wrong output":
                    logger.info(f"Converted result: {result} (pass)")
            else:
                logger.warning(f"Mismatch Tx and Rx: {tx_line.split(':')[0]} {tx_identifier} : {' '.join(tx_values[2:])}")
                logger.error(f"Rx: Failed")

    for rx_line in rx_lines:
        rx_values = extract_values_from_line(rx_line)
        # if len(rx_values) < 4:
        #     #rx_lines.remove(rx_line)
        #     continue



        if re.search(r"negative response", rx_line, re.IGNORECASE):
            # if "Negative Response" in rx_line.strip().lower():
            rx_identifier = "".join(byte.replace("0x", "").upper() for byte in tx_values[:2])
            logger.error(f"Negative Response detected: {rx_line}")
            logger.error(f"Failed Response for Rx: Read Data By Identifier {rx_identifier} : {' '.join(rx_values[2:])}")
        else:
            rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])
            logger.info(f"Read Data By Identifier: Rx) Read Data By Identifier {rx_identifier} : {' '.join(rx_values[2:])}")
            logger.debug(f"Inspecting rx_values: {rx_values}")

            result = convert(rx_values[2:])

            if result == "0" or result == "wrong output":
                logger.error("Converted result: wrong output")
            else:
                logger.info(f"Converted result: {result}")




if __name__ == "__main__":
    folder_path = r"C:\\temp3"

    files = glob.glob(os.path.join(folder_path, "*.uds.txt"))

    if not files:
        logger.info("No matching files found.")
    else:

        newest_file = max(files, key=os.path.getmtime)
        logger.info(f"The newest file is: {newest_file}")

        # Process the newest file
        tx_lines, rx_lines = process_uds_file(newest_file)

        if tx_lines or rx_lines:
            process_tx_rx_lines(tx_lines, rx_lines)

