import subprocess
from pathlib import Path

working_dir = Path(r"C:\Program Files (x86)\UdsClient_CL")
exe = working_dir / "UdsClient_CL.exe"          # full path
assert exe.exists(), f"EXE not found: {exe}"

args = [
    str(exe),
    "51",
    "UPP",
    "/s", r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Standard_Identifiers.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\CanConfig_103.script",
     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Faults_Configuration.script",
     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Network_F1D5.script",
     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Network_Missmatch_F1D3.script",
     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Network_TimeOut_F1D2.script",
     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Routine_Control.script",
     r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\TrueDriveManager.script",
    r"C:\Users\ilyar\PycharmProjects\UDS\Scripts\Generetic_ECU_Read.script",
]

subprocess.run(args, cwd=str(working_dir), check=True)
