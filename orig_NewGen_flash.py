# -*- coding: utf-8 -*-
"""
Flash rollback test + copy logs to network share (with & in path)
Works reliably under Jenkins service account.
"""

import os
import re
import shutil
import sys
import subprocess
import time
from pathlib import Path
from typing import Tuple, List
import argparse

# ================================
# CONFIG
# ================================
SOURCE_ROOT = Path(r"C:\Jenkins\NewVersion")
TARGET_DIR  = Path(r"C:\Jenkins\UdsClient_CL")
EXE         = TARGET_DIR / "UdsClient_CL.exe"
LOGS_DIR    = Path(r"C:\temp3")

CHANNEL         = "51"
FIRMWARE_NewGen = "NewGen"
BOOT_NG         = "**Bootloader-NG**"

# ================================
# CREDENTIALS (injected by Jenkins)
# ================================
# These will be overridden by environment variables in Jenkins
DOMAIN   = os.environ.get("nexus.local",   "YOUR_DOMAIN")      # e.g. CORP
USERNAME = os.environ.get("dyno",     "your.username")   # e.g. john.doe
PASSWORD = os.environ.get("nexus1",     "fallback")        # will be replaced

# ================================
# Windows Impersonation (fixes Access Denied forever)
# ================================
import ctypes
from ctypes import wintypes

advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

LOGON32_LOGON_NEW_CREDENTIALS = 9
LOGON32_PROVIDER_DEFAULT = 0

def impersonate_and_run(func, *args, **kwargs):
    """Run function as a specific domain user (fixes network share access)."""
    if not USERNAME or PASSWORD == "fallback":
        print("No valid credentials → skipping impersonation (running as current user)")
        return func(*args, **kwargs)

    token = wintypes.HANDLE()
    success = advapi32.LogonUserW(
        ctypes.c_wchar_p(USERNAME),
        ctypes.c_wchar_p(DOMAIN if DOMAIN != "." else None),
        ctypes.c_wchar_p(PASSWORD),
        LOGON32_LOGON_NEW_CREDENTIALS,
        LOGON32_PROVIDER_DEFAULT,
        ctypes.byref(token)
    )

    if not success:
        err = ctypes.WinError(ctypes.get_last_error())
        print(f"LogonUser failed: {err}")
        return func(*args, **kwargs)  # fallback

    try:
        if not advapi32.ImpersonateLoggedOnUser(token):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            print(f"Running as {DOMAIN}\\{USERNAME}")
            return func(*args, **kwargs)
        finally:
            advapi32.RevertToSelf()
    finally:
        kernel32.CloseHandle(token)

# ================================
# Helpers
# ================================
def require_exists(path: Path, desc: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{desc} not found: {path}")

def find_two_version_dirs(root: Path) -> Tuple[Path, Path]:
    require_exists(root, "SOURCE_ROOT")
    subdirs = [p for p in root.iterdir() if p.is_dir()]
    if len(subdirs) < 2:
        raise FileNotFoundError(f"Need ≥2 version folders in {root}, found {len(subdirs)}")
    subdirs.sort(key=lambda p: p.stat().st_mtime)
    return subdirs[-2], subdirs[-1]

def pick_latest_file(candidates: List[Path]) -> Path:
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None

def find_merged_files(version_dir: Path) -> Tuple[Path, Path]:
    merged_dir = version_dir / "Firmware"
    require_exists(merged_dir, f"Firmware dir in {version_dir}")

    app = pick_latest_file([p for p in merged_dir.glob("*.brn.hex") if "_Boot" not in p.name])
    boot = pick_latest_file(list(merged_dir.glob("*_Boot.brn.hex")))

    if not app or not boot:
        raise FileNotFoundError(f"Missing .brn.hex files in {merged_dir}")
    return app, boot

def list_xmls_in_target():
    xmls = list(TARGET_DIR.glob("*.xml"))
    if not xmls:
        print(f"[WARN] No XML files in {TARGET_DIR}")
    else:
        print(f"[INFO] XMLs in {TARGET_DIR}: {[x.name for x in xmls]}")

def run_flash(file_path: Path, target: str):
    require_exists(EXE, "UdsClient_CL.exe")
    require_exists(file_path, "hex file")

    cmd = [str(EXE), CHANNEL, target, "/f", str(file_path)]
    print(f"\nRunning: {' '.join(cmd)}")
    list_xmls_in_target()

    env = os.environ.copy()
    env["PATH"] = str(TARGET_DIR) + os.pathsep + env.get("PATH", "")

    proc = subprocess.Popen(
        cmd, cwd=str(TARGET_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1
    )

    pct_re = re.compile(r"^\s*(\d{1,3})%\s*$")
    last_pct = None
    for line in proc.stdout:
        line = line.rstrip()
        m = pct_re.match(line)
        if m:
            pct = int(m.group(1))
            if last_pct != pct:
                sys.stdout.write(f"\rFlashing: {pct}%")
                sys.stdout.flush()
                last_pct = pct
            continue
        if last_pct is not None:
            print()
            last_pct = None
        print(line)

    proc.wait()
    if last_pct is not None:
        print()
    if proc.returncode != 0:
        raise RuntimeError(f"Flash failed (code {proc.returncode})")

def sleep_with_countdown(sec: int, msg: str):
    for i in range(sec, 0, -1):
        sys.stdout.write(f"\r{msg}: {i:3d}s ")
        sys.stdout.flush()
        time.sleep(1)
    print("\r" + " " * 60 + "\r", end="")

# ================================
# Robust folder creation (under impersonated user)
# ================================
def robust_mkdir(path: Path):
    if path.exists():
        return
    print(f"   Creating: {path}")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"   Python mkdir failed: {e}")
        # Fallback: robocopy (more reliable on UNC)
        dummy = Path(r"C:\Windows\Temp\_empty_for_robocopy")
        dummy.mkdir(exist_ok=True)
        result = subprocess.run([
            "robocopy", str(dummy), str(path), "/MIR", "/R:1", "/W:1", "/NP", "/NJH", "/NJS"
        ], capture_output=True, text=True)
        if result.returncode > 7:
            raise OSError(f"robocopy failed: {result.stderr}")
        if not path.exists():
            raise OSError("Directory still missing after robocopy")

# ================================
# Copy logs (with impersonation)
# ================================
def copy_logs_to_network(version_str: str):
    if not any(LOGS_DIR.iterdir()):
        print("No logs to copy.")
        return

    dest_base = Path(r"\\nexus-srv\Users Temp Files\V&V\UDS_Result\NewGen")
    final_root = dest_base / f"0{version_str.lstrip('0.')}"
    dest_dir = final_root / "Flashing logs"

    print(f"\nCopying logs → {dest_dir}")

    def _perform_copy():
        robust_mkdir(final_root)
        robust_mkdir(dest_dir)

        copied = 0
        for f in LOGS_DIR.iterdir():
            if f.is_file():
                try:
                    shutil.copy2(f, dest_dir / f.name)
                    print(f"   Copied: {f.name}")
                    copied += 1
                except Exception as e:
                    print(f"   Failed {f.name}: {e}")
        print(f"   Success: {copied} file(s) copied")

    try:
        impersonate_and_run(_perform_copy)
    except Exception as e:
        print(f"   FINAL FAILURE (even with impersonation): {e}")

# ================================
# Main
# ================================
def main() -> int:
    print("=== UDS Rollback Flash + Log Copy ===")
    try:
        # 1. Find versions
        old_dir, new_dir = find_two_version_dirs(SOURCE_ROOT)
        old_app, old_boot = find_merged_files(old_dir)
        new_app, new_boot = find_merged_files(new_dir)

        match = re.search(r"NewGen_v(.+)", new_dir.name)
        version_str = match.group(1) if match else new_dir.name

        print(f"\nOld: {old_dir.name}")
        print(f"   App:  {old_app.name}")
        print(f"   Boot: {old_boot.name}")
        print(f"New: {new_dir.name}")

        # 2. Flash sequence
        print("\n[1/2] Flashing OLD firmware...")
        run_flash(old_app, FIRMWARE_NewGen)
        sleep_with_countdown(60, "Waiting after firmware")

        print("\n[2/2] Flashing OLD bootloader...")
        run_flash(old_boot, BOOT_NG)
        sleep_with_countdown(20, "Waiting after bootloader")

        print("\nFLASH SEQUENCE COMPLETED")

        # 3. Copy logs
        copy_logs_to_network(version_str)

        print("\nALL DONE SUCCESSFULLY!")
        return 0

    except Exception as e:
        print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())