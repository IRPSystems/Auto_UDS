import os
import re
import sys
import subprocess
import time
from pathlib import Path
from typing import Tuple, List

# =========================
# ======  CONFIG  =========
# =========================

# Root that contains version folders like: UPP_v3.02.00, UPP_v3.02.02, ...
SOURCE_ROOT = Path(r"C:\Jenkins\NewVersion")

# Tool install dir and EXE
TARGET_DIR = Path(r"C:\Jenkins\UdsClient_CL")
EXE = TARGET_DIR / "UdsClient_CL.exe"
cwd=TARGET_DIR

# Flash params
CHANNEL = "51"
FIRMWARE_UPP = "UPP"
BOOT_UPP = "**Bootloader**"  # (avoid the markdown "**" — the real arg is plain Bootloader)

# =========================
# ======  HELPERS  ========
# =========================

def require_exists(path: Path, desc: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{desc} not found: {path}")

def find_two_version_dirs(root: Path) -> Tuple[Path, Path]:
    """
    Returns (old_dir, new_dir) by modification time.
    Only directories under root are considered.
    """
    require_exists(root, "SOURCE_ROOT")
    subdirs = [p for p in root.iterdir() if p.is_dir()]
    if len(subdirs) < 2:
        raise FileNotFoundError(f"Expected at least 2 version folders inside {root}, found {len(subdirs)}")

    # Sort by mtime ascending → last two are the newest; pick [ -2 ] as old, [ -1 ] as new
    subdirs.sort(key=lambda p: p.stat().st_mtime)
    return subdirs[-2], subdirs[-1]

def pick_latest_file(candidates: List[Path]) -> Path:
    if not candidates:
        raise FileNotFoundError("No matching files found.")
    return max(candidates, key=lambda p: p.stat().st_mtime)

def find_merged_files(version_dir: Path) -> Tuple[Path, Path]:

    # Inside <version_dir>\FW Merged\ find:
    #   - *Merge_App_*UPP_v*.hex  (firmware/app)
    #   - *Merge_Boot_*UPP_v*.hex (bootloader)
    # Returns (app_hex, boot_hex)

    merged_dir = version_dir / "FW Merged"
    require_exists(merged_dir, f"'FW Merged' directory for {version_dir.name}")

    app_candidates = list(merged_dir.glob("*Merge_App_*UPP_v*.hex"))
    boot_candidates = list(merged_dir.glob("*Merge_Boot_*UPP_v*.hex"))

    app_hex = pick_latest_file(app_candidates)
    boot_hex = pick_latest_file(boot_candidates)
    return app_hex, boot_hex

def list_xmls_in_target():
    xmls = list(TARGET_DIR.glob("*.xml"))
    if not xmls:
        print(f"[WARN] No XML files found in {TARGET_DIR}")
    else:
        print("[INFO] XML files visible to tool:")
        for x in xmls:
            print("   -", x.name)

def run_flash(exe: Path, channel: str, target: str, file_path: Path) -> None:
    require_exists(exe, "UdsClient_CL.exe")
    require_exists(file_path, f"hex file for {target}")

    cmd = [str(exe), channel, target, "/f", str(file_path)]
    print(f'\n==> Running: {exe.name} {channel} {target} /f "{file_path}"')
    print(f"[INFO] Working directory for process: {TARGET_DIR}")

    # show what XMLs the tool will actually see
    list_xmls_in_target()

    env = os.environ.copy()
    env["PATH"] = str(TARGET_DIR) + os.pathsep + env.get("PATH", "")

    # Start process and stream output so we can rewrite percentages live
    process = subprocess.Popen(
        cmd,
        cwd=str(TARGET_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",     # tolerate odd console encodings
        bufsize=1,
        universal_newlines=True
    )

    pct_re = re.compile(r"^\s*(\d{1,3})%\s*$")
    last_pct = None
    line_len = 0             # length of the last rendered progress line

    def render_progress(pct_text: str):
        nonlocal line_len
        msg = f"Flashing progress: {pct_text}%"
        # overwrite previous line safely even if \r doesn't erase the tail:
        pad = " " * max(0, line_len - len(msg))
        sys.stdout.write("\r" + msg + pad)
        sys.stdout.flush()
        line_len = len(msg)

    for raw in process.stdout:
        line = raw.rstrip("\r\n")
        m = pct_re.match(line)
        if m:
            pct = int(m.group(1))
            # detect sequence reset (tool starts a new chunk)
            if last_pct is not None and pct < last_pct:
                # end the previous progress line
                sys.stdout.write("\n")
                sys.stdout.flush()
                line_len = 0
            render_progress(str(pct))
            last_pct = pct
            continue

        # Non-percent line: finish progress line (if any), then print the message
        if last_pct is not None:
            sys.stdout.write("\n")
            sys.stdout.flush()
            last_pct = None
            line_len = 0
        print(line)

    process.wait()

    # If we ended on a progress line, close it nicely
    if last_pct is not None:
        sys.stdout.write("\n")
        sys.stdout.flush()

    if process.returncode != 0:
        raise RuntimeError(f"Flash command failed with exit code {process.returncode}")

def main() -> int:
    try:
        old_dir, new_dir = find_two_version_dirs(SOURCE_ROOT)

        # Discover merged files in each version
        old_app, old_boot = find_merged_files(old_dir)
        new_app, new_boot = find_merged_files(new_dir)

        # Print which versions we resolved
        print(f"Old version: {old_dir.name}")
        print(f"  FW: {old_app}")
        print(f"  BOOT: {old_boot}")
        print(f"New version: {new_dir.name}")
        print(f"  FW: {new_app}")
        print(f"  BOOT: {new_boot}")



        def sleep_with_countdown(seconds: int, message: str):
            """Show live countdown in console while waiting."""
            for remaining in range(seconds, 0, -1):
                sys.stdout.write(f"\r{message}: {remaining:3d}s remaining")
                sys.stdout.flush()
                time.sleep(1)
            print()  # newline after countdown

        for i in range(1):
            print(f"\n=== FLASH ROUND {i + 1}/5 ===")

            round_start = time.time()

            # 1) old firmware
            print("\n[STEP 1] Flashing OLD firmware...")
            step_start = time.time()
            run_flash(EXE, CHANNEL, FIRMWARE_UPP, old_app)
            step_end = time.time()
            print(f"\n=== FLASHED ROUND of {old_app} = {i + 1}/5 ===")
            print(f"   -> Done in {int(step_end - step_start)} sec")
            sleep_with_countdown(100, "Waiting after old firmware")


            # 2) old boot (optional)
            print("\n[STEP 2] Flashing OLD bootloader...")
            step_start = time.time()
            run_flash(EXE, CHANNEL, BOOT_UPP, old_boot)
            step_end = time.time()
            print(f"\n=== FLASHED ROUND of {old_boot} = {i + 1}/5 ===")
            print(f"   -> Done in {int(step_end - step_start)} sec")
            sleep_with_countdown(20, "Waiting after old boot")

            # 3) new firmware
            print("\n[STEP 3] Flashing NEW firmware...")
            step_start = time.time()
            run_flash(EXE, CHANNEL, FIRMWARE_UPP, new_app)
            step_end = time.time()
            print(f"\n=== FLASHED ROUND of {new_app} = {i + 1}/5 ===")
            print(f"   -> Done in {int(step_end - step_start)} sec")
            sleep_with_countdown(100, "Waiting after new firmware")

            # 4) new boot
            print("\n[STEP 4] Flashing NEW bootloader...")
            step_start = time.time()
            run_flash(EXE, CHANNEL, BOOT_UPP, new_boot)
            step_end = time.time()
            print(f"   -> Done in {int(step_end - step_start)} sec")
            print(f"\n=== FLASHED ROUND of {new_boot} = {i + 1}/5 ===")
            sleep_with_countdown(20, "Waiting after new boot")

            round_end = time.time()
            print(f"\n✅ Round {i + 1} completed in {int(round_end - round_start)} sec\n")
        return 0


    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
