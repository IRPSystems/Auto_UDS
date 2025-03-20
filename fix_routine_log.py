import re
import os
import glob

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

def fix_log_file(input_path, output_path):
    script_name = extract_script_name(input_path)
    fixed_lines = []

    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                fixed_lines.append(line)
                continue

            values = extract_values_from_line(line)
            if (line.startswith("Tx)") and "Routine Control" in line and
                script_name == "Routine_Control" and len(values) >= 3 and
                values[:3] == ["0x01", "0x02", "0x01"]):
                # Extract payload after the first 3 values, limit to 25 more (total 28)
                payload_values = values[3:] if len(values) > 3 else []
                if len(payload_values) >= 27:  # 3 prefix + 25 payload = 28 total
                    payload_values = payload_values[:27]  # Truncate to 25
                payload = " ".join(payload_values) if payload_values else ""
                fixed_tx = f"Tx) Routine Control               : 0x02 0x01 {payload}"
                fixed_lines.append(fixed_tx)
                continue

            if values and len(values) > 27:
                truncated_values = " ".join(values[:27])
                fixed_line = f"{line.split(':', 1)[0]}: {truncated_values}"
                fixed_lines.append(fixed_line)
            else:
                fixed_lines.append(line)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Fixed by fix_log.py\n")
        for line in fixed_lines:
            f.write(line + "\n")

if __name__ == "__main__":
    input_folder = r"C:\\temp3"
    files = glob.glob(os.path.join(input_folder, "*.uds.txt"))
    if not files:
        print("No matching files found.")
    else:
        newest_file = max(files, key=os.path.getmtime)
        output_file = newest_file.replace(".uds.txt", "_fixed.uds.txt")
        fix_log_file(newest_file, output_file)
        print(f"Fixed log file created: {output_file}")