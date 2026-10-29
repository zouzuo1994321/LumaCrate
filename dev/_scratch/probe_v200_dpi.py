# -*- coding: utf-8 -*-
"""量一下真机窗口的 DPI / 客户区 / grab 尺寸，搞清 lv.click 的坐标空间。"""
import os
import sys
import json
import time
import ctypes
import ctypes.wintypes
import subprocess

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v200")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"
_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication

u32 = ctypes.windll.user32
exe = os.path.join(TEMP, "流明盒-v2.0.0-2610290119.exe")
exe_name = os.path.basename(exe)
cfg_path = os.path.join(TEMP, "settings.json")
os.environ["LMC_CONFIG"] = cfg_path

subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
print("hwnd", hwnd)


def info(h, tag):
    r = ctypes.wintypes.RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    c = ctypes.wintypes.RECT()
    u32.GetClientRect(h, ctypes.byref(c))
    try:
        dpi = u32.GetDpiForWindow(h)
    except Exception:
        dpi = -1
    pm = app.primaryScreen().grabWindow(h)
    print("%-6s rect=%dx%d client=%dx%d dpi=%s grab=%dx%d"
          % (tag, r.right - r.left, r.bottom - r.top, c.right, c.bottom, dpi,
             pm.width(), pm.height()))


info(hwnd, "main")
COORDS = json.load(open(lv.COORDS, encoding="utf-8"))
TOOLS_BTN = tuple(COORDS["main_settings_btn"])
lv.click(hwnd, TOOLS_BTN[0], TOOLS_BTN[1])
dlg = lv.find_window_ex(exe_name, [proc.pid], exclude=(hwnd,), timeout=25, title_sub="工具")
print("dlg hwnd", dlg)
if dlg:
    time.sleep(2.5)
    info(dlg, "dlg")
    sc = app.primaryScreen()
    print("qt screen: logical", sc.geometry().getRect(), "dpr", sc.devicePixelRatio(),
          "phys", sc.size().width(), sc.size().height())
    try:
        lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
    except Exception:
        pass
    time.sleep(1.0)
lv.u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
for _ in range(40):
    if proc.poll() is not None:
        break
    time.sleep(0.3)
if proc.poll() is None:
    proc.kill()
print("rc", proc.poll())
print("PROBE_DONE")
