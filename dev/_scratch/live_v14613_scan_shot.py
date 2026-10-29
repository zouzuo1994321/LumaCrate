# -*- coding: utf-8 -*-
"""v1.46.13 打包后 exe：点侧栏「演示库」→ 抓库页面，找扫描入口。

真实鼠标输入（SetCursorPos + mouse_event）。点击坐标从命令行给：x y。
"""
import os
import sys
import time
import ctypes
import subprocess
from ctypes import wintypes

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v14613")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication

uu = ctypes.windll.user32

CLICKS = []
# 参数形如  x,y  x,y ...
for a in sys.argv[1:]:
    try:
        x, y = a.split(",")
        CLICKS.append((int(x), int(y)))
    except Exception:
        pass

exe = None
for fn in os.listdir(TEMP):
    if fn.lower().endswith(".exe"):
        exe = os.path.join(TEMP, fn)
exe_name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP)
print("启动:", exe_name, "pid=", proc.pid)

app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
print("hwnd:", hwnd, lv.wtitle(hwnd))
time.sleep(8)


def shot(name):
    pm = lv.grab(app, hwnd, tries=10, gap=0.3, settle=5)
    p = os.path.join(SHOTS, name)
    pm.save(p, "PNG")
    print("  截图:", name, pm.width(), pm.height())


def real_click(cx, cy):
    uu.SetForegroundWindow(hwnd)
    uu.ShowWindow(hwnd, 9)
    time.sleep(0.5)
    pt = wintypes.POINT(cx, cy)
    uu.ClientToScreen(hwnd, ctypes.byref(pt))
    uu.SetCursorPos(pt.x, pt.y)
    time.sleep(0.25)
    uu.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.08)
    uu.mouse_event(0x0004, 0, 0, 0, 0)
    print("  点击 client", cx, cy, "→ screen", pt.x, pt.y)


shot("_v14613_exe_before_click.png")
for i, (x, y) in enumerate(CLICKS):
    real_click(x, y)
    time.sleep(2.2)
    shot("_v14613_exe_click%d.png" % i)

print("DONE")
