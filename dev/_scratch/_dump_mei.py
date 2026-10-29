# -*- coding: utf-8 -*-
"""查打包后的 exe 里到底装的是哪一版 main_window：一次性解开 _MEIxxxx 目录看字节码字符串。"""
import os
import sys
import glob
import time
import subprocess

TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp")
BASE = os.path.join(TEMP, "lmc_exe_v14613")
exe = None
for fn in os.listdir(BASE):
    if fn.lower().endswith(".exe"):
        exe = os.path.join(BASE, fn)
exe_name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)

before = set(glob.glob(os.path.join(TEMP, "_MEI*")))
proc = subprocess.Popen([exe], cwd=BASE)
time.sleep(14)

after = set(glob.glob(os.path.join(TEMP, "_MEI*")))
dirs = sorted(after - before) or sorted(after, key=os.path.getmtime)[-3:]
print("pid:", proc.pid, "MEI dirs:", dirs)

probes = [b"ScanNote", b"_upgrade_virtual", b"_scan_own_busy", b"ScanBar",
          b"\xe5\x85\xb1 %d \xe4\xb8\xaa\xe8\xb7\xaf\xe5\xbe\x84"]
for d in dirs:
    mw = os.path.join(d, "main_window.pyc")
    if not os.path.exists(mw):
        print("  no main_window.pyc in", d, sorted(os.listdir(d))[:10])
        continue
    data = open(mw, "rb").read()
    print("  %s  %d bytes" % (d, len(data)))
    for pr in probes:
        print("     ", pr[:24], b"<FOUND>" if pr in data else b"-")

proc.terminate()
print("DONE")
