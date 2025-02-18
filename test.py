import os
import glob
import re
import logging

# Configure logging
logging.basicConfig(filename="uds_results.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def process_latest_uds_file(folder_path):
    files = glob.glob(os.path.join(folder_path, "*.uds.txt"))
    if not files:
        logging.warning("No matching files found.")
        return [], []

    files.sort(key=os.path.getctime, reverse=True)
    latest_file = files[0]
    logging.info(f"Processing file: {latest_file}")

    tx_lines, rx_lines = [], []
    with open(latest_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Tx)"):
                tx_lines.append(line.strip())
            elif line.startswith("Rx)"):
                rx_lines.append(line.strip())

    logging.info(f"Found {len(tx_lines)} 'Tx)' lines and {len(rx_lines)} 'Rx)' lines.")
    return tx_lines, rx_lines


def extract_values_from_line(line):
    try:
        _, data_part = line.split(":", 1)
    except ValueError:
        return []

    return re.findall(r'0x[0-9A-Fa-f]{2}', data_part)


def convert(values):
    if len(values) < 3:
        return None

    try:
        data = [int(x, 16) for x in values]
        if all(byte == 0 for byte in data[4:]):
            return "wrong output"

        result = "".join(chr(x) for x in data)
        return result if all(32 <= ord(c) <= 126 for c in result) else "wrong output"
    except ValueError:
        return "wrong output"


def process_tx_rx_lines(tx_lines, rx_lines):
    results = []

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
                result = convert(tx_values[2:])
                results.append(f"{tx_identifier}: PASS - {result}")
                logging.info(f"{tx_identifier}: PASS - {result}")
            else:
                results.append(f"{tx_identifier}: FAIL - Mismatch in Tx/Rx data")
                logging.error(f"{tx_identifier}: FAIL - Mismatch in Tx/Rx data")
        else:
            results.append(f"{tx_identifier}: FAIL - No matching Rx")
            logging.error(f"{tx_identifier}: FAIL - No matching Rx")

    for rx_line in rx_lines:
        rx_values = extract_values_from_line(rx_line)
        if len(rx_values) < 4:
            continue

        rx_identifier = "".join(byte.replace("0x", "").upper() for byte in rx_values[:2])
        result = convert(rx_values[2:])
        if result and result != "wrong output":
            results.append(f"{rx_identifier}: PASS - {result}")
            logging.info(f"{rx_identifier}: PASS - {result}")
        else:
            results.append(f"{rx_identifier}: FAIL - Invalid output")
            logging.error(f"{rx_identifier}: FAIL - Invalid output")

    with open("uds_test_results.txt", "w") as f:
        for res in results:
            f.write(res + "\n")

    for res in results:
        print(res)


if __name__ == '__main__':
    folder_path = r"C:\\temp3"
    tx_lines, rx_lines = process_latest_uds_file(folder_path)
    if tx_lines or rx_lines:
        process_tx_rx_lines(tx_lines, rx_lines)
