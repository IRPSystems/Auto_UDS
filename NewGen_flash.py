import os
import re
import shutil
import sys
import subprocess
import time
from pathlib import Path
from typing import Tuple, List
import argparse

# ---- Console safety: avoid charmap/encoding crashes everywhere ----
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# =========================
# ======  CONFIG  =========
# =========================

SOURCE_ROOT = Path(r"C:\Jenkins\NewVersion")

# Tool install dir and EXE
TARGET_DIR = Path(r"C:\Jenkins\UdsClient_CL")
EXE = TARGET_DIR / "UdsClient_CL.exe"

LOGS_DIR = Path(r"C:\temp3")

# Flash params
CHANNEL = "51"
FIRMWARE_NewGen = "NewGen"
BOOT_NG = "**Bootloader-NG**"  # kept as you requested

# =========================
# ======  HELPERS  ========
# =========================

def require_exists(path: Path, desc: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{desc} not found: {path}")

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", type=str, help="Path to previous version folder")
    ap.add_argument("--new", type=str, help="Path to latest version folder")
    return ap.parse_args()

def find_two_version_dirs(root: Path) -> Tuple[Path, Path]:
    """
    Returns (old_dir, new_dir) by modification time.
    Only directories under root are considered.
    """
    require_exists(root, "SOURCE_ROOT")
    subdirs = [p for p in root.iterdir() if p.is_dir()]
    if len(subdirs) < 2:
        raise FileNotFoundError(f"Expected at least 2 version folders inside {root}, found {len(subdirs)}")
    # Sort by mtime ascending → last two are newest
    subdirs.sort(key=lambda p: p.stat().st_mtime)
    return subdirs[-2], subdirs[-1]

def pick_latest_file(candidates: List[Path]) -> Path:
    if not candidates:
        raise FileNotFoundError("No matching files found.")
    return max(candidates, key=lambda p: p.stat().st_mtime)

def find_merged_files(version_dir: Path) -> Tuple[Path, Path]:
    merged_dir = version_dir / "Firmware"
    require_exists(merged_dir, f"'Firmware' directory for {version_dir.name}")

    # Application: *.brn.hex but NOT *_Boot.brn.hex
    app_candidates = [
        p for p in merged_dir.glob("*.brn.hex")
        if "_Boot" not in p.name
    ]

    # Boot: *_Boot.brn.hex
    boot_candidates = list(merged_dir.glob("*_Boot.brn.hex"))

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
    def require_exists(path: Path, desc: str) -> None:
        if not path.exists():
            raise FileNotFoundError(f"{desc} not found: {path}")

    def list_xmls_in_target(target_dir: Path):
        xmls = list(target_dir.glob("*.xml"))
        if not xmls:
            print(f"[WARN] No XML files found in {target_dir}")
        else:
            print("[INFO] XML files visible to tool:")
            for x in xmls:
                print("   -", x.name)

    require_exists(exe, "UdsClient_CL.exe")
    require_exists(file_path, f"hex file for {target}")

    cmd = [str(exe), channel, target, "/f", str(file_path)]
    print(f'\n==> Running: {Path(exe).name} {channel} {target} /f "{file_path}"')
    print(f"[INFO] Working directory for process: {TARGET_DIR}")
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
        universal_newlines=True,
    )

    pct_re = re.compile(r"^\s*(\d{1,3})%\s*$")
    last_pct = None

    def render_progress(pct: int):
        nonlocal last_pct
        if last_pct == pct:
            return  # suppress duplicates (Jenkins prints each line)
        last_pct = pct
        msg = f"Flashing progress: {pct}%"
        sys.stdout.write("\x1b[2K\r" + msg)
        sys.stdout.flush()

    for raw in process.stdout:
        line = raw.rstrip("\r\n")
        stripped = line.strip()

        m = pct_re.match(line)
        if m:
            pct = int(m.group(1))
            render_progress(pct)
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
        raise RuntimeError(f"Flash command failed with exit code {process.returncode}")

def sleep_with_countdown(seconds: int, message: str):
    """Show live countdown in console while waiting."""
    for remaining in range(seconds, 0, -1):
        sys.stdout.write(f"\r{message}: {remaining:3d}s remaining")
        sys.stdout.flush()
        time.sleep(1)
    print()  # newline after countdown

def flash_one_round(old_app: Path, old_boot: Path, new_app: Path, new_boot: Path) -> None:
    """Exactly one round: old FW -> old Boot (new steps commented out)."""
    round_label = os.environ.get("ROUND_INDEX") or "single run"
    print(f"\n=== FLASH ROUND {round_label} ===")

    round_start = time.time()

    # 1) old firmware
    print("\n[STEP 1] Flashing OLD firmware...")
    step_start = time.time()
    run_flash(EXE, CHANNEL, FIRMWARE_NewGen, old_app)
    print(f"   -> Done in {int(time.time() - step_start)} sec")
    sleep_with_countdown(60, "Waiting after old firmware")

    # 2) old boot
    print("\n[STEP 2] Flashing OLD bootloader...")
    step_start = time.time()
    run_flash(EXE, CHANNEL, BOOT_NG, old_boot)
    print(f"   -> Done in {int(time.time() - step_start)} sec")
    sleep_with_countdown(20, "Waiting after old boot")

    print(f"\n✅ Round completed in {int(time.time() - round_start)} sec\n")

# =========================
# ========= main ==========
# =========================

def clear_temp3():
    """Delete all files and subfolders inside C:\\Temp3, but keep the folder itself."""
    print("🧹 Deleting old log files in C:\\Temp3 ...")
    if not LOGS_DIR.exists():
        print(f"   - {LOGS_DIR} does not exist, nothing to clean.")
        return

    for entry in LOGS_DIR.iterdir():
        try:
            if entry.is_file() or entry.is_symlink():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)
        except PermissionError as e:
            print(f"   ! Permission denied removing {entry}: {e}")
        except OSError as e:
            print(f"   ! Failed removing {entry}: {e}")
    print("   - Cleanup finished.")

def robust_mkdir_robocopy(path: Path) -> bool:
    """
    Try to ensure a directory exists using robocopy from an empty dummy dir.
    Returns True on success (robocopy exit code 0–7), False on failure.
    """
    dummy = Path(r"C:\Windows\Temp\_dummy_empty_dir")
    try:
        dummy.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"  ❌ Failed to prepare dummy dir for robocopy: {e}")
        return False

    cmd = [
        "robocopy",
        str(dummy),   # source (empty)
        str(path),    # destination
        "/MIR"
    ]
    print(f"  Running robocopy to ensure directory exists: {path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    # robocopy 0–7 => success or minor issues; >7 => failure
    if result.returncode > 7:
        print(f"  ❌ robocopy mkdir failed for {path}: rc={result.returncode}")
        print("     stdout:", result.stdout)
        print("     stderr:", result.stderr)
        return False

    print(f"  ✅ Directory ensured via robocopy: {path} (rc={result.returncode})")
    return True

def copying_files(version_str: str):

    if not version_str:
        print("[copying_files] version_str is empty, nothing to copy.")
        return

    if not LOGS_DIR.exists():
        print(f"[copying_files] LOGS_DIR does not exist, nothing to copy: {LOGS_DIR}")
        return

    external_root = Path(r"\\nexus-srv\Users Temp Files\V&V\UDS_Result")
    final_root = external_root / "NewGen" / ("0" + version_str)
    dest_dir = final_root / "Flashing logs"

    print(f"\n📁 Copying logs to external disk under: {dest_dir}")

    # Ensure both final_root and dest_dir via robocopy
    if not robust_mkdir_robocopy(final_root):
        print("  ❌ Could not create/verify final_root, aborting copy.")
        return
    if not robust_mkdir_robocopy(dest_dir):
        print("  ❌ Could not create/verify dest_dir, aborting copy.")
        return

    files_copied = 0
    for entry in LOGS_DIR.iterdir():
        if entry.is_file():
            target = dest_dir / entry.name
            try:
                shutil.copy2(entry, target)
                print(f"  Copied {entry} -> {target}")
                files_copied += 1
            except Exception as e:
                print(f"  ❌ Failed to copy {entry} -> {target}: {e}")

    if files_copied == 0:
        print("  (No files found to copy in Temp3)")
    else:
        print(f"✅ Copy to external disk completed. {files_copied} file(s) copied.")

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
            # Fallback: auto-detect (kept for manual runs)
            old_dir, new_dir = find_two_version_dirs(SOURCE_ROOT)

        old_app, old_boot = find_merged_files(old_dir)
        new_app, new_boot = find_merged_files(new_dir)

        # Version string is derived from *new* version folder name
        m = re.search(r"NewGen_v(.+)", new_dir.name)
        version_str = m.group(1) if m else new_dir.name

        print(f"Old version: {old_dir.name}")
        print(f"  FW: {old_app}")
        print(f"  BOOT: {old_boot}")
        print(f"New version: {new_dir.name}")
        print(f"  FW: {new_app}")
        print(f"  BOOT: {new_boot}")
        print(f"Version folder name for logs: {version_str}")

        flash_one_round(old_app, old_boot, new_app, new_boot)

        # Copy Temp3 logs to external disk
        copying_files(version_str)

        return 0

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
