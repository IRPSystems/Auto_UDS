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
SOURCE_UDS = base_dir / 'Project'
print(SOURCE_UDS)

# Where new builds appear
home = Path.home()
candidate = home / "Desktop" / "NewGen"
SOURCE_ROOT = candidate if candidate.exists() else Path(r"C:\Jenkins\NewVersion")

CLIENT_DIR_NAME = "UDS-Client"                # subfolder to copy from
TARGET_DIR = Path(r"C:\Jenkins\UdsClient_CL") # tool install dir (writable by Jenkins)

EXE = TARGET_DIR / "UdsClient_CL.exe"         # tool exe

CHANNEL = "51"
DEVICE = "NewGen"

# Script list
SCRIPTS: List[Path] = [
    SOURCE_UDS / 'NewGen' / 'Scripts' / 'Standard_Identifiers.script',

]

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

def run_one_script(script_path: Path):
    """Run a single .script via UdsClient_CL, stream output, with timeout."""
    args = [str(EXE), CHANNEL, DEVICE, "/s", str(script_path)]
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

def run_parser_for(script_path: Path):

    print("   -> Parsing logs for:", script_path)
    env = os.environ.copy()
    env["LAST_UDS_SCRIPT"] = str(script_path)


    add_paths = [
        str(base_dir),                        # contains 'Project'
        str(base_dir / "Project" / "NewGen"),    # so bare 'Condition' resolves
    ]
    current_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([p for p in add_paths + [current_pp] if p])

    python_exe = base_dir / '.venv' / 'Scripts' / 'python.exe'
    #cmd = [str(python_exe), "-m", "Project.NewGen.ng", str(script_path)]
    ng_path = base_dir / 'Project' / 'NewGen' / 'ng.py'
    cmd = [str(python_exe), str(ng_path), str(script_path)]
    # Run from the repo root (folder that has the 'Project' package)
    subprocess.run(cmd, check=True, env=env, cwd=str(base_dir))


# =========================
# ========= MAIN ==========
# =========================
def main():
    # 1) Locate latest and copy client files
    print("🔍 Searching latest NewGen drop …")
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
