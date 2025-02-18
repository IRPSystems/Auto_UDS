import os
import glob
import re

from logger import setup_logger

# Initialize the logger from logger.py
logger = setup_logger()
def process_latest_uds_file(folder_path):
    files = glob.glob(os.path.join(folder_path, "*.uds.txt"))
    if not files:
        print("No matching files found.")
        return [], []
    files.sort(key=os.path.getctime, reverse=True)
    latest_file = files[0]
    print(f"Processing file: {latest_file}")

    tx_lines = []
    rx_lines = []

    with open(latest_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Tx)"):
                tx_lines.append(line.strip())
            elif line.startswith("Rx)"):
                rx_lines.append(line.strip())

    if not tx_lines and not rx_lines:
        print("No 'Tx)' or 'Rx)' lines found in the file.")
        return [], []

    print(f"Found {len(tx_lines)} 'Tx)' lines and {len(rx_lines)} 'Rx)' lines.")
    return tx_lines, rx_lines


def extract_values_from_line(line):
    try:
        _, data_part = line.split(":", 1)
    except ValueError:
        print("The line does not contain a colon followed by data.")
        return []

    hex_values = re.findall(r'0x[0-9A-Fa-f]{2}', data_part)

    if len(hex_values) < 3:
        return []

    return hex_values

def convert(values):
    if len(values) < 3:
        return None

    try:
        data = [int(x, 16) for x in values]

        if all(byte == 0 for byte in data[4:]):

            return "wrong output"

        result = "".join(chr(x) for x in data)

        if not all(32 <= ord(c) <= 126 for c in result):
            return "wrong output"

        return result
    except ValueError:
        return "wrong output"


def process_tx_rx_lines(tx_lines, rx_lines):
    seen_identifiers = set()

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
        if len(rx_values) < 4:
            continue
        rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])
        logger.info(f"Read Data By Identifier: Rx) Read Data By Identifier {rx_identifier} : {' '.join(rx_values[2:])}")
        result = convert(rx_values[2:])

        if result == "0" or result == "wrong output":
            logger.error("Converted result: wrong output")
        else:
            logger.info(f"Converted result: {result}")


if __name__ == '__main__':
    folder_path = r"C:\temp3"
    tx_lines, rx_lines = process_latest_uds_file(folder_path)

    if tx_lines or rx_lines:
        process_tx_rx_lines(tx_lines, rx_lines)

