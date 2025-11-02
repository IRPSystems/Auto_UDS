import os
import subprocess
from pathlib import Path

working_dir = Path(r"C:\Program Files (x86)\UdsClient_CL")
exe = working_dir / "UdsClient_CL.exe"          # full path
assert exe.exists(), f"EXE not found: {exe}"

args = [
    str(exe),
    "51",
    "UPP",
    "/s", r"C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\Scripts\Standard_Identifiers.script",
   # r"C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\Scripts\CanConfig_103.script",
   # r"C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\Scripts\Faults_Configuration.script",
   # r"C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\Scripts\Network_F1D5.script",
   #  r"C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\Scripts\Network_Missmatch_F1D3.script",
   # "C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\Scripts\Network_TimeOut_F1D2.script",
   # r"C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\Scripts\Routine_Control.script",
   #  r"C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\Scripts\TrueDriveManager.script",
   # r"C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\Scripts\Generetic_ECU_Read.script",
]

subprocess.run(args, cwd=str(working_dir), check=True)

import os

os.system(r'"C:\Users\ilyar\PycharmProjects\UDS\.venv\Scripts\python.exe" "C:\Users\ilyar\PycharmProjects\UDS\Project\UPP\upp.py"')

