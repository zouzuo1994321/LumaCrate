# -*- coding: utf-8 -*-
import subprocess, os, builtins
_OUT = open(r"C:\Users\zouzu\AppData\Local\Temp\lmc_diag3.txt", "w", encoding="utf-8")
def print(*a, **k):
    k["file"] = _OUT
    builtins.print(*a, **k)

envs = r"C:\Users\zouzu\.workbuddy\binaries\python\envs"
code = "import PySide6,PyInstaller,sys;print(sys.executable,PySide6.__version__,PyInstaller.__version__)"
for name in sorted(os.listdir(envs)):
    py = os.path.join(envs, name, "Scripts", "python.exe")
    if not os.path.exists(py):
        continue
    try:
        r = subprocess.run([py, "-c", code], capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip() or (r.stderr or "").strip().splitlines()[-1:]
        print(name, "->", out)
    except Exception as e:
        print(name, "ERR", e)
_OUT.flush(); _OUT.close()
