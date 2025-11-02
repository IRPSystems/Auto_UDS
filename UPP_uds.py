
import os
import subprocess
from pathlib import Path

EXE = Path(r"C:\Program Files (x86)\UdsClient_CL\UdsClient_CL.exe")
CWD = EXE.parent
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
missing = [p for p in SCRIPTS if not Path(p).is_file()]
if missing:
    raise FileNotFoundError(f"Script(s) not found:\n  " + "\n  ".join(missing))

for script in SCRIPTS:
    print(f"==> Running UdsClient_CL on: {script}")
    subprocess.run(
        [str(EXE), "51", "UPP", "/s", script],
        cwd=str(CWD),
        check=True
    )
    subprocess.run(
       [r"C:\Users\ilyar\PycharmProjects\UDS\.venv\Scripts\python.exe",
       r"C:\Users\ilyar\PycharmProjects\UDS\upp.py"],
       check=True
    )
#os.system('python modify_compliance_matrix.py')