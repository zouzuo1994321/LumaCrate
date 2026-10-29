# -*- coding: utf-8 -*-
"""诊断 3：真机 exe 里工具窗导航点击到底落在哪一项（连点几个 y，比对前后截图）。"""
import os
import sys
import json
import time
import ctypes
import shutil
import subprocess

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_navdbg")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication

os.makedirs(TEMP, exist_ok=True)
src = lv.newest_exe()
exe = os.path.join(TEMP, os.path.basename(src))
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)
cfg = os.path.join(TEMP, "settings.json")
json.dump({"libraries": [{"name": "Javlibrary", "kind": "电影",
                          "paths": ["D:/a%d" % i for i in range(14)], "filter": {}},
                         {"name": "Jav-VR", "kind": "电影", "paths": ["D:/vr"], "filter": {}},
                         {"name": "Jav-临时", "kind": "混合", "paths": ["D:/tmp"],
                          "filter": {}}]},
          open(cfg, "w", encoding="utf-8"), ensure_ascii=False)
os.environ["LMC_CONFIG"] = cfg

COORDS = json.load(open(lv.COORDS, encoding="utf-8"))
TOOLS = tuple(COORDS["main_settings_btn"])
name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(name, [proc.pid], timeout=120, title_sub="Build")
print("主窗", hwnd, flush=True)
time.sleep(6)
lv.click(hwnd, TOOLS[0], TOOLS[1])
dlg = lv.find_window_ex(name, [proc.pid], exclude=(hwnd,), timeout=25, title_sub="工具")
print("工具窗", dlg, flush=True)
time.sleep(3.0)


def shot(tag):
    for _ in range(6):
        pm = app.primaryScreen().grabWindow(dlg)
        if pm.width() > 1000:
            break
        time.sleep(0.5)
        app.processEvents()
    p2 = os.path.join(SHOTS, "_nav_%s.png" % tag)
    pm.save(p2, "PNG")
    print("  图", tag, pm.width(), pm.height(), flush=True)
    return pm


def diff(a, b):
    from PIL import Image, ImageChops
    import numpy as np
    ia = a.toImage().convertToFormat(4)
    a.save(r"C:\Users\zouzu\AppData\Local\Temp\_a.png", "PNG")
    b.save(r"C:\Users\zouzu\AppData\Local\Temp\_b.png", "PNG")
    x = Image.open(r"C:\Users\zouzu\AppData\Local\Temp\_a.png").convert("L")
    y = Image.open(r"C:\Users\zouzu\AppData\Local\Temp\_b.png").convert("L")
    if x.size != y.size:
        return -1
    return sum(abs(px - qx) for px, qx in zip(x.getdata(), y.getdata())) / (x.width * x.height)


p0 = shot("initial")
for y in (101, 62, 629, 590):
    lv.click(dlg, 72, y)
    time.sleep(1.8)
    pn = shot("y%d" % y)
    print("  click y=%d → 与初始页差异 %.2f" % (y, diff(p0, pn)), flush=True)

lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
time.sleep(1.0)
lv.u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
t0 = time.time()
while time.time() - t0 < 20 and proc.poll() is None:
    time.sleep(0.3)
print("退出", proc.poll(), flush=True)
