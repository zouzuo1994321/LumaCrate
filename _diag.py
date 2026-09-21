# -*- coding: utf-8 -*-
import os, sys, glob, struct, builtins

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"
_OUT = open(r"C:\Users\zouzu\AppData\Local\Temp\lmc_diag2.txt", "w", encoding="utf-8")
def print(*a, **k):          # noqa: A001
    k["file"] = _OUT
    builtins.print(*a, **k)
print("PY", sys.executable)
print("PYVER", sys.version.split()[0])

# 1) dev / root listing
for sub in ("dev", ""):
    d = os.path.join(ROOT, sub) if sub else ROOT
    print("=== DIR", d)
    try:
        for n in sorted(os.listdir(d))[:80]:
            print("   ", n)
    except Exception as e:
        print("   ERR", e)

# 2) logo.png dimensions (PNG IHDR)
lp = os.path.join(ROOT, "logo.png")
try:
    with open(lp, "rb") as f:
        head = f.read(33)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", head[16:24])
        print("LOGO_PNG", lp, w, "x", h, "bytes", os.path.getsize(lp))
    else:
        print("LOGO_PNG not png", head[:8])
except Exception as e:
    print("LOGO_ERR", e)

# 3) Pillow / PySide6 availability
for mod in ("PIL", "PySide6", "PyInstaller"):
    try:
        m = __import__(mod)
        print("MOD", mod, "OK", getattr(m, "__version__", "?"))
    except Exception as e:
        print("MOD", mod, "MISSING", type(e).__name__)

# 4) look for venvs
for pat in (r"C:\Users\zouzu\.workbuddy\binaries\python\envs\*\Scripts\python.exe",
            os.path.join(ROOT, "**", "python.exe")):
    for p in glob.glob(pat, recursive=True)[:20]:
        print("VENV?", p)

_OUT.flush()
_OUT.close()
