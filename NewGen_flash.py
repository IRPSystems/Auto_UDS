import os
import re
import shutil
import sys
import subprocess
import time
from pathlib import Path
from typing import Tuple, List
import argparse

# =========================
# ====== CONFIG ===========
# =========================
SOURCE_ROOT = Path(r"C:\Jenkins\NewVersion")
TARGET_DIR = Path(r"C:\Jenkins\UdsClient_CL")
EXE = TARGET_DIR / "UdsClient_CL.exe"
LOGS_DIR = Path(r"C:\temp3")

CHANNEL = "51"
FIRMWARE_NewGen = "NewGen"
BOOT_NG = "**Bootloader-NG**"

# =========================
# ====== HELPERS ==========
# =========================

def require_exists(path: Path, desc: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{desc} not found: {path}")

def parse_args():
    ap = argparse.ArgumentParser(description="Flash old → old boot (for rollback test)")
    ap.add_argument("--old", type=str, help="Path to previous version folder")
    ap.add_argument("--new", type=str, help="Path to latest version folder")
    return ap.parse_args()

def find_two_version_dirs(root: Path) -> Tuple[Path, Path]:
    require_exists(root, "SOURCE_ROOT")
    subdirs = [p for p in root.iterdir() if p.is_dir()]
    if len(subdirs) < 2:
        raise FileNotFoundError(f"Expected at least 2 version folders in {root}, found {len(subdirs)}")
    subdirs.sort(key=lambda p: p.stat().st_mtime)
    return subdirs[-2], subdirs[-1]

def pick_latest_file(candidates: List[Path]) -> Path:
    if not candidates:
        raise FileNotFoundError("No matching files found.")
    return max(candidates, key=lambda p: p.stat().st_mtime)

def find_merged_files(version_dir: Path) -> Tuple[Path, Path]:
    merged_dir = version_dir / "Firmware"
    require_exists(merged_dir, f"'Firmware' folder in {version_dir.name}")

    app_candidates = [p for p in merged_dir.glob("*.brn.hex") if "_Boot" not in p.name]
    boot_candidates = list(merged_dir.glob("*_Boot.brn.hex"))

    app_hex = pick_latest_file(app_candidates)
    boot_hex = pick_latest_file(boot_candidates)
    return app_hex, boot_hex

def list_xmls_in_target(target_dir: Path = TARGET_DIR) -> None:
    """Show which XML config files the flashing tool can see."""
    xmls = list(target_dir.glob("*.xml"))
    if not xmls:
        print(f"[WARN] No XML files found in {target_dir}")
    else:
        print(f"[INFO] XML files visible to tool in {target_dir}:")
        for x in xmls:
            print(f"   - {x.name}")

def run_flash(exe: Path, channel: str, target: str, file_path: Path) -> None:
    require_exists(exe, "UdsClient_CL.exe")
    require_exists(file_path, f"hex file for {target}")

    cmd = [str(exe), channel, target, "/f", str(file_path)]
    print(f"\n==> Running: {' '.join(cmd)}")
    print(f"[INFO] Working directory: {TARGET_DIR}")
    list_xmls_in_target(TARGET_DIR)

    env = os.environ.copy()
    env["PATH"] = str(TARGET_DIR) + os.pathsep + env.get("PATH", "")

    process = subprocess.Popen(
        cmd,
        cwd=str(TARGET_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    pct_re = re.compile(r"^\s*(\d{1,3})%\s*$")
    last_pct: int | None = None

    def render_progress(pct: int):
        nonlocal last_pct
        if last_pct == pct:
            return
        last_pct = pct
        msg = f"Flashing progress: {pct}%"
        sys.stdout.write("\x1b[2K\r" + msg)
        sys.stdout.flush()

    for line in process.stdout:
        line = line.rstrip("\r\n")
        m = pct_re.match(line)
        if m:
            render_progress(int(m.group(1)))
            continue
        if last_pct is not None:
            sys.stdout.write("\n")
            sys.stdout.flush()
            last_pct = None
        print(line)

    process.wait()
    if last_pct is not None:
        sys.stdout.write("\n")
        sys.stdout.flush()

    if process.returncode != 0:
        raise RuntimeError(f"Flash failed with exit code {process.returncode}")

def sleep_with_countdown(seconds: int, message: str = "Waiting"):
    for i in range(seconds, 0, -1):
        sys.stdout.write(f"\r{message}: {i:3d}s ")
        sys.stdout.flush()
        time.sleep(1)
    print("\r" + " " * 50 + "\r", end="")

# =========================
# ====== ROBUST MKDIR =====
# =========================

def robust_mkdir_robocopy(path: Path) -> None:
    """Create directory using robocopy — works on any UNC path, even with & ( ) # etc."""
    if path.exists():
        return

    print(f"   Creating folder (robocopy): {path}")
    dummy = Path(r"C:\Windows\Temp\_empty_dir_for_robocopy")
    dummy.mkdir(exist_ok=True)

    cmd = [
        "robocopy",
        str(dummy),
        str(path),
        "/MIR", "/R:1", "/W:1", "/NP", "/NJH", "/NJS"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode > 7:  # 0–7 = success in robocopy world
        raise OSError(f"robocopy failed (code {result.returncode})\n"
                      f"Command: {' '.join(cmd)}\n"
                      f"Output: {result.stdout}\n{result.stderr}")

    if not path.exists():
        raise OSError(f"robocopy succeeded but folder was not created: {path}")

# =========================
# ========= MAIN ==========
# =========================

def clear_temp3():
    print("Cleaning old logs in C:\\temp3 ...")
    if not LOGS_DIR.exists():
        return
    for entry in LOGS_DIR.iterdir():
        try:
            if entry.is_file() or entry.is_symlink():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
        except Exception as e:
            print(f"   Warning: Could not delete {entry}: {e}")
    print("   Cleanup done.")

def copy_logs_to_network(version_str: str):
    if not version_str or not LOGS_DIR.exists() or not any(LOGS_DIR.iterdir()):
        print("No logs to copy.")
        return

    network_root = Path(r"\\nexus-srv\Users Temp Files\V&V\UDS_Result")
    final_root = network_root / "NewGen" / f"0{version_str.lstrip('0.')}"   # e.g., 0.03.53 → 00.03.53
    dest_dir = final_root / "Flashing logs"

    print(f"\nCopying logs to network share:")
    print(f"   → {dest_dir}")

    try:
        robust_mkdir_robocopy(final_root)
        robust_mkdir_robocopy(dest_dir)
    except Exception as e:
        print(f"   Failed to create network folder: {e}")
        print("   Skipping log copy.")
        return

    copied = 0
    for src_file in LOGS_DIR.iterdir():
        if src_file.is_file():
            try:
                shutil.copy2(src_file, dest_dir / src_file.name)
                print(f"   Copied: {src_file.name}")
                copied += 1
            except Exception as e:
                print(f"   Failed to copy {src_file.name}: {e}")

    print(f"   Log copy complete: {copied} file(s) → {dest_dir}")

def flash_one_round(old_app: Path, old_boot: Path):
    print("\n=== STARTING FLASH SEQUENCE (old FW → old Boot) ===")
    start_time = time.time()

    # Step 1: Flash old application
    print("\n[1/2] Flashing OLD firmware...")
    run_flash(EXE, CHANNEL, FIRMWARE_NewGen, old_app)
    print(f"   Done in {int(time.time() - start_time)}s")
    sleep_with_countdown(60, "Waiting after firmware flash")

    # Step 2: Flash old bootloader
    print("\n[2/2] Flashing OLD bootloader...")
    run_flash(EXE, CHANNEL, BOOT_NG, old_boot)
    total_time = int(time.time() - start_time)
    print(f"   Done in {total_time}s total")
    sleep_with_countdown(20, "Waiting after bootloader")

    print(f"\nFLASH SEQUENCE COMPLETED in {total_time} seconds")

def main() -> int:
    clear_temp3()

    try:
        args = parse_args()

        if args.old and args.new:
            old_dir = Path(args.old)
            new_dir = Path(args.new)
            require_exists(old_dir, "Old version folder")
            require_exists(new_dir, "New version folder")
        else:
            old_dir, new_dir = find_two_version_dirs(SOURCE_ROOT)

        old_app, old_boot = find_merged_files(old_dir)
        new_app, new_boot = find_merged_files(new_dir)  # kept for future use

        match = re.search(r"NewGen_v(.+)", new_dir.name)
        version_str = match.group(1) if match else new_dir.name

        print(f"\nOld version : {old_dir.name}")
        print(f"   App  → {old_app.name}")
        print(f"   Boot → {old_boot.name}")
        print(f"New version : {new_dir.name}")
        print(f"   App  → {new_app.name}")
        print(f"   Boot → {new_boot.name}")
        print(f"Log folder  : 0{version_str}")

        # Perform flash sequence
        flash_one_round(old_app, old_boot)

        # Copy logs to network share
        copy_logs_to_network(version_str)

        print("\nALL TASKS COMPLETED SUCCESSFULLY!")
        return 0

    except Exception as e:
        print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())