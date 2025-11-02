#
# import os
# import subprocess
# from pathlib import Path
#
# EXE = Path(r"C:\Program Files (x86)\UdsClient_CL\UdsClient_CL.exe")
# CWD = EXE.parent
# SCRIPTS = [
#     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\CanConfig_103.script",
#     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Faults_Configuration.script",
#     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Network_F1D5.script",
#     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Network_Missmatch_F1D3.script",
#     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Network_TimeOut_F1D2.script",
#     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Routine_Control.script",
#     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Standard_Identifiers.script",
#     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\TrueDriveManager.script",
#     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Generetic_ECU_Read.script",
# ]
# missing = [p for p in SCRIPTS if not Path(p).is_file()]
# if missing:
#     raise FileNotFoundError(f"Script(s) not found:\n  " + "\n  ".join(missing))
#
# for script in SCRIPTS:
#     print(f"==> Running UdsClient_CL on: {script}")
#     subprocess.run(
#         [str(EXE), "51", "UPP", "/s", script],
#         cwd=str(CWD),
#         check=True
#     )
#     subprocess.run(
#        [r"C:\Users\ilyar\PycharmProjects\UDS\.venv\Scripts\python.exe",
#        r"C:\Users\ilyar\PycharmProjects\UDS\upp.py"],
#        check=True
#     )
# os.system('python modify_compliance_matrix.py')

import subprocess
from pathlib import Path
from itertools import chain
import sys, time, threading, queue

EXE = Path(r"C:\Program Files (x86)\UdsClient_CL\UdsClient_CL.exe")
CWD = EXE.parent
CHANNEL = "51"
DEVICE = "UPP"

SCRIPTS = [
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\CanConfig_103.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Faults_Configuration.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Network_F1D5.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Network_Missmatch_F1D3.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Network_TimeOut_F1D2.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Routine_Control.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Standard_Identifiers.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\TrueDriveManager.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Generetic_ECU_Read.script",
]

PARSER = [
    r"C:\Users\ilyar\PycharmProjects\UDS\.venv\Scripts\python.exe",
    r"C:\Users\ilyar\PycharmProjects\UDS\upp.py",
]

# Timeouts
SILENCE_WATCHDOG = 60      # seconds of no output => assume stuck
TIMEOUT_SINGLE_TOTAL = 3600
TIMEOUT_PER_SCRIPT = 900

def _pump(proc, q):
    # push lines into a queue so we can watchdog silence
    for line in proc.stdout:
        q.put(line)
    q.put(None)  # sentinel

def _run_and_watch(args, cwd, total_timeout, silence_timeout):
    print("\n> Running:", " ".join(args))
    proc = subprocess.Popen(
        args,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    q = queue.Queue()
    t = threading.Thread(target=_pump, args=(proc, q), daemon=True)
    t.start()

    last_output = time.time()
    start = time.time()
    while True:
        try:
            item = q.get(timeout=0.2)
        except queue.Empty:
            item = None

        if item is not None:
            if item is None:  # sentinel
                break
            sys.stdout.write(item)
            sys.stdout.flush()
            last_output = time.time()
        else:
            # no new output chunk
            pass

        # silence watchdog
        if time.time() - last_output > silence_timeout:
            proc.kill()
            raise RuntimeError(f"Stuck (no output for {silence_timeout}s). Killed.")

        # hard total timeout
        if time.time() - start > total_timeout:
            proc.kill()
            raise RuntimeError(f"Timed out after {total_timeout}s. Killed.")

    rc = proc.wait(timeout=10)
    if rc != 0:
        raise subprocess.CalledProcessError(rc, args)

def try_variant_A():
    # /s before each script:  ... 51 UPP /s file1 /s file2 ...
    args = [str(EXE), CHANNEL, DEVICE]
    args.extend(list(chain.from_iterable(("/s", s) for s in SCRIPTS)))
    _run_and_watch(args, CWD, TIMEOUT_SINGLE_TOTAL, SILENCE_WATCHDOG)

def try_variant_B():
    # single /s followed by all files: ... 51 UPP /s file1 file2 ...
    args = [str(EXE), CHANNEL, DEVICE, "/s"] + SCRIPTS
    _run_and_watch(args, CWD, TIMEOUT_SINGLE_TOTAL, SILENCE_WATCHDOG)

def run_per_script():
    for s in SCRIPTS:
        print(f"\n==> Running per-script: {s}")
        _run_and_watch(
            [str(EXE), CHANNEL, DEVICE, "/s", s],
            CWD,
            TIMEOUT_PER_SCRIPT,
            SILENCE_WATCHDOG
        )
        time.sleep(0.5)  # tiny gap helps some CLIs

def main():
    if not EXE.is_file():
        raise FileNotFoundError(f"UdsClient not found: {EXE}")
    missing = [p for p in SCRIPTS if not Path(p).is_file()]
    if missing:
        raise FileNotFoundError("Missing script(s):\n  " + "\n  ".join(missing))

    # 1) Variant A
    try:
        print("\n=== Variant A: /s before EACH script ===")
        try_variant_A()
    except Exception as e_a:
        print(f"\n[Variant A failed] {e_a}")
        # 2) Variant B
        try:
            print("\n=== Variant B: single /s then all scripts ===")
            try_variant_B()
        except Exception as e_b:
            print(f"\n[Variant B failed] {e_b}")
            # 3) Fallback: per-script
            print("\n=== Fallback: running scripts one-by-one ===")
            run_per_script()

    # Parser once at the end
    print("\n==> Launching parser …")
    subprocess.run(PARSER, check=True)
    print("All done.")

if __name__ == "__main__":
    main()
