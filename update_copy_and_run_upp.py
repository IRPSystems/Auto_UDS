import os
import sys
import shutil
import subprocess
from pathlib import Path
from selectors import SelectSelector
from typing import List

# =========================
# ======  CONFIG  =========
# =========================

username = os.environ.get('USERNAME', 'unknown')
if username == 'unknown':
    raise EnvironmentError("USERNAME environment variable not set.")

base_dir =  os.path.dirname((os.path.abspath(__file__)))
SOURCE_UDS = os.path.join(base_dir, 'Project' )
print(SOURCE_UDS)

#SOURCE_ROOT = Path(fr"C:\Users\{username}\Desktop\UPP")   # where new builds appear
home = Path.home()
candidate = home / "Desktop" / "UPP"
SOURCE_ROOT = candidate if candidate.exists() else Path(r"C:\Jenkins\NewVersion")


CLIENT_DIR_NAME = "UDS-Client"                       # subfolder to copy from
TARGET_DIR = Path(r"C:\Jenkins\UdsClient_CL")        # tool install dir (writable by Jenkins)

EXE = TARGET_DIR / "UdsClient_CL.exe"               # tool exe

CHANNEL = "51"
DEVICE = "UPP"


SCRIPTS: List[str] = [
    os.path.join(SOURCE_UDS,  'UPP', 'Scripts', 'Standard_Identifiers.script'),
    os.path.join(SOURCE_UDS,  'UPP', 'Scripts', 'CanConfig_103.script'),
    os.path.join(SOURCE_UDS,  'UPP',  'Scripts', 'Faults_Configuration.script'),
    os.path.join(SOURCE_UDS,  'UPP',  'Scripts', 'Network_F1D5.script'),
    os.path.join(SOURCE_UDS,  'UPP',  'Scripts', 'Network_Missmatch_F1D3.script'),
    os.path.join(SOURCE_UDS,  'UPP',  'Scripts', 'Network_TimeOut_F1D2.script'),
    os.path.join(SOURCE_UDS,  'UPP',  'Scripts', 'Routine_Control.script'),
    os.path.join(SOURCE_UDS,  'UPP',  'Scripts', 'TrueDriveManager.script'),
    os.path.join(SOURCE_UDS,  'UPP',  'Scripts', 'Generetic_ECU_Read.script'),

]

# Run your parser AFTER EACH script:
PARSER_CMD = [
    # os.path.join(base_dir),'.venv\Scripts\python.exe',
    os.path.join(base_dir,'.venv', 'Scripts', 'python.exe'),
    os.path.join(SOURCE_UDS,  'UPP', 'upp.py'),
]
# ]
TIMEOUT_PER_SCRIPT = 900  # seconds

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

def copy_all_files(src_dir: Path, dst_dir: Path) -> list[Path]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    files = [p for p in src_dir.iterdir() if p.is_file()]
    if not files:
        raise FileNotFoundError(f"No files in {src_dir}")
    copied = []
    for f in files:
        target = dst_dir / f.name
        shutil.copy2(f, target)
        copied.append(target)
    return copied

def run_one_script(script_path: str):
    """Run a single .script via UdsClient_CL, stream output, with timeout."""
    args = [str(EXE), CHANNEL, DEVICE, "/s", script_path]
    print(f"\n==> Running: {script_path}")
    proc = subprocess.Popen(
        args,
        cwd=str(TARGET_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)  # safe on *nix too
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
        rc = proc.wait(timeout=TIMEOUT_PER_SCRIPT)
        if rc != 0:
            raise subprocess.CalledProcessError(rc, args)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Timed out after {TIMEOUT_PER_SCRIPT}s: {script_path}")

def run_parser_for(script_path: str):
    """Run the parser right after one script, passing context."""
    print("   -> Parsing logs for:", script_path)
    env = os.environ.copy()
    env["LAST_UDS_SCRIPT"] = script_path  # in case upp.py wants to know
    # If upp.py supports a CLI arg (optional), we provide it:
    cmd = PARSER_CMD + [script_path]
    subprocess.run(cmd, check=True, env=env)

# =========================
# ========= MAIN ==========
# =========================
def main():
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

    missing = [s for s in SCRIPTS if not Path(s).is_file()]
    if missing:
        raise FileNotFoundError("Missing .script file(s):\n  " + "\n  ".join(missing))

    # 3) For each script: run UDS, then run parser
    for s in SCRIPTS:
        run_one_script(s)
        run_parser_for(s)

    print("\n✅ All scripts executed and parsed.")

if __name__ == "__main__":

    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
