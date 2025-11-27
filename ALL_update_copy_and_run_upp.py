import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List

# =========================
# ======  CONFIG  =========
# =========================

username = os.environ.get('USERNAME', 'unknown')
if username == 'unknown':
    raise EnvironmentError("USERNAME environment variable not set.")

# repo root (folder that contains Project/)
base_dir = Path(__file__).resolve().parent
SOURCE_UDS = base_dir / 'Project'  # expects Project/UPP/Scripts/*.script

#LOGS_DIR=Path(r"C:\temp3")

# Where new builds appear (preferred Desktop path, else Jenkins drop)
home = Path.home()
candidate = home / "Desktop" / "UPP"
SOURCE_ROOT = candidate if candidate.exists() else Path(r"C:\Jenkins\NewVersion")

CLIENT_DIR_NAME = "UDS-Client"                 # subfolder to copy from
TARGET_DIR = Path(r"C:\Jenkins\UdsClient_CL")  # tool install dir (writable by Jenkins)

EXE = TARGET_DIR / "UdsClient_CL.exe"          # tool exe

CHANNEL = "51"
DEVICE = "UPP"

# List of scripts to run (full paths)
SCRIPTS: List[Path] = [
    # SOURCE_UDS / 'UPP' / 'Scripts' / 'TrueDriveManager.script',
    # SOURCE_UDS / 'UPP' / 'Scripts' / 'Standard_Identifiers.script',
    # SOURCE_UDS / 'UPP' / 'Scripts' / 'CanConfig_103.script',
    # SOURCE_UDS / 'UPP' / 'Scripts' / 'Faults_Configuration.script',
     SOURCE_UDS / 'UPP' / 'Scripts' / 'Network_F1D5.script',
    # SOURCE_UDS / 'UPP' / 'Scripts' / 'Network_Missmatch_F1D3.script',
    # SOURCE_UDS / 'UPP' / 'Scripts' / 'Network_TimeOut_F1D2.script',
    # SOURCE_UDS / 'UPP' / 'Scripts' / 'Routine_Control.script',
    # SOURCE_UDS / 'UPP' / 'Scripts' / 'Generetic_ECU_Read.script',


]

# How long to allow the single “all scripts” run (seconds)
TIMEOUT_SINGLE_RUN = 3600

PARSER_CMD = [
    str(base_dir / '.venv' / 'Scripts' / 'python.exe'),
    "-m", "Project.UPP.upp"
]

# =========================
# =====  UTILITIES  =======
# =========================

def find_latest_subfolder(root: Path) -> Path:
    subdirs = [p for p in root.iterdir() if p.is_dir()]
    if not subdirs:
        raise FileNotFoundError(f"No subfolders inside {root}")
    return max(subdirs, key=lambda p: p.stat().st_mtime)

def find_client_dir(base: Path, name: str) -> Path:
    name_lower = name.lower()
    for cur, dirs, _ in os.walk(base):
        for d in dirs:
            if d.lower() == name_lower:
                return Path(cur) / d
    raise FileNotFoundError(f"'{name}' not found under {base}")

def copy_all_files(src_dir: Path, dst_dir: Path) -> List[Path]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    files = [p for p in src_dir.iterdir() if p.is_file()]
    if not files:
        raise FileNotFoundError(f"No files in {src_dir}")
    copied: List[Path] = []
    for f in files:
        target = dst_dir / f.name
        shutil.copy2(f, target)
        copied.append(target)
    return copied

def run_all_together(scripts: List[Path], timeout_sec: int = TIMEOUT_SINGLE_RUN):
    """Run UdsClient_CL once: UdsClient_CL.exe 51 UPP /s <script1> <script2> ..."""
    args = [str(EXE), CHANNEL, DEVICE, "/s"] + [str(p) for p in scripts]

    print("\nRunning once with all scripts:")
    for i, a in enumerate(args):
        print(f"  [{i}] {a}")

    proc = subprocess.Popen(
        args,
        cwd=str(TARGET_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
        rc = proc.wait(timeout=timeout_sec)
        if rc != 0:
            raise subprocess.CalledProcessError(rc, args)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Timed out after {timeout_sec}s running ALL scripts")

def run_parser_once():
    """Run parser once after the UDS batch finishes.
    Ensures both repo root and Project/UPP are in PYTHONPATH for imports."""
    print("\n==> Launching parser …")
    env = os.environ.copy()

    add_paths = [
        str(base_dir),                     # contains 'Project'
        str(base_dir / "Project" / "UPP")  # so bare 'Condition' resolves
    ]
    current_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([p for p in add_paths + [current_pp] if p])

    subprocess.run(PARSER_CMD, check=True, env=env, cwd=str(base_dir))

# =========================
# ========= MAIN ==========
# =========================
# def clear_temp3():
#     """Delete all files and subfolders inside C:\\Temp3, but keep the folder itself."""
#     print("🧹 Deleting old log files in C:\\Temp3 ...")
#     if not LOGS_DIR.exists():
#         print(f"   - {LOGS_DIR} does not exist, nothing to clean.")
#         return
#
#     for entry in LOGS_DIR.iterdir():
#         try:
#             if entry.is_file() or entry.is_symlink():
#                 entry.unlink()
#             elif entry.is_dir():
#                 shutil.rmtree(entry)
#         except PermissionError as e:
#             print(f"   ! Permission denied removing {entry}: {e}")
#         except OSError as e:
#             print(f"   ! Failed removing {entry}: {e}")
#     print("   - Cleanup finished.")

def main():
    print("Delete old log files in the Temp3 folder")
    # clear_temp3()
    # 1) Locate latest and copy client files
    print("🔍 Searching latest UPP drop …")
    latest = find_latest_subfolder(SOURCE_ROOT)
    print(f"[INFO] Latest folder: {latest}")

    client_dir = find_client_dir(latest, CLIENT_DIR_NAME)
    print(f"[INFO] Found '{CLIENT_DIR_NAME}': {client_dir}")

    try:
        copied = copy_all_files(client_dir, TARGET_DIR)
    except PermissionError:
        print(f"\n[ERROR] Permission denied copying to '{TARGET_DIR}'. "
              f"Grant Jenkins account write access or choose a writable path.")
        sys.exit(1)

    print(f"[OK] Copied {len(copied)} file(s) to {TARGET_DIR}")
    for p in copied:
        print(f"   - {p.name}")

    # 2) Sanity checks before run
    if not EXE.is_file():
        raise FileNotFoundError(f"UdsClient not found: {EXE}")

    missing = [str(s) for s in SCRIPTS if not s.is_file()]
    if missing:
        raise FileNotFoundError("Missing .script file(s):\n  " + "\n  ".join(missing))

    # 3) Run ALL scripts in a single UdsClient_CL call
    run_all_together(SCRIPTS)

    # 4) Run parser once after everything finished
    run_parser_once()

    print("\n✅ All scripts executed and parsed.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
