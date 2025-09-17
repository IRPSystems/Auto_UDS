###python bump_vin_byte.py --script "Standard_Identifiers.script"



#!/usr/bin/env python3
import re
import argparse
from pathlib import Path

PATTERN = re.compile(
    r"""^(?P<prefix>\s*send\s+2E\s+F190\s+
         (?:[0-9A-Fa-f]{2}\s+){16})      # first 16 VIN bytes
         (?P<last>[0-9A-Fa-f]{2})        # the 17th (last) VIN byte
         (?P<suffix>\s*)$""",
    re.VERBOSE
)

def inc_hex_byte(byte_str: str) -> str:
    """Increment a 2-hex-digit string modulo 0x100, return uppercase 2 digits."""
    val = int(byte_str, 16)
    return f"{(val + 1) & 0xFF:02X}"

def bump_last_vin_byte(script_path: Path, update_all: bool = False) -> int:
    text = script_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    updated = 0
    new_lines = []
    for line in lines:
        m = PATTERN.match(line)
        if m and (update_all or updated == 0):
            old_last = m.group("last")
            new_last = inc_hex_byte(old_last)
            new_line = f"{m.group('prefix')}{new_last}{m.group('suffix')}"
            new_lines.append(new_line)
            updated += 1
            print(f"VIN last byte: {old_last} -> {new_last}")
        else:
            new_lines.append(line)

    if updated == 0:
        print("No VIN 'send 2E F190 ...' line found (17-byte pattern). Nothing changed.")
        return 0

    script_path.write_text("\n".join(new_lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
    print(f"Updated script saved: {script_path}")
    return updated

def main():
    ap = argparse.ArgumentParser(description="Increment the last byte of the VIN write line (send 2E F190 ...) by 1.")
    ap.add_argument("--script", required=True, help="Path to the .script file (e.g., Standard_Identifiers.script)")
    ap.add_argument("--all", action="store_true", help="Update all matching VIN lines (default: only the first match).")
    args = ap.parse_args()

    path = Path(args.script)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    bump_last_vin_byte(path, update_all=args.all)

if __name__ == "__main__":
    main()
