# -*- coding: utf-8 -*-
"""诊断：真实鼠标点击为什么没落到按钮上（屏幕尺寸 / 窗口矩形 / 前台窗口 / 光标位置）。"""
import os
import sys
import time
import ctypes
import subprocess
from ctypes import wintypes

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v14613")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication

uu = ctypes.windll.user32
print("screen:", uu.GetSystemMetrics(0), uu.GetSystemMetrics(1))
print("virtual:", uu.GetSystemMetrics(76), uu.GetSystemMetrics(77),
      uu.GetSystemMetrics(78), uu.GetSystemMetrics(79))
print("dpi:", uu.GetDpiForSystem())

exe = None
for fn in os.listdir(TEMP):
    if fn.lower().endswith(".exe"):
        exe = os.path.join(TEMP, fn)
exe_name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP)
app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
print("hwnd:", hwnd)
time.sleep(8)

r, cr = wintypes.RECT(), wintypes.RECT()
uu.GetWindowRect(hwnd, ctypes.byref(r))
uu.GetClientRect(hwnd, ctypes.byref(cr))
print("window rect:", r.left, r.top, r.right, r.bottom)
print("client rect:", cr.left, cr.top, cr.right, cr.bottom)
pt = wintypes.POINT(0, 0)
uu.ClientToScreen(hwnd, ctypes.byref(pt))
print("client origin on screen:", pt.x, pt.y)

uu.SetForegroundWindow(hwnd)
uu.ShowWindow(hwnd, 9)
time.sleep(0.8)
fg = uu.GetForegroundWindow()
print("foreground ok:", fg == hwnd, "fg=", fg)

pt2 = wintypes.POINT(1724, 25)
uu.ClientToScreen(hwnd, ctypes.byref(pt2))
ok = uu.SetCursorPos(pt2.x, pt2.y)
cur = wintypes.POINT()
uu.GetCursorPos(ctypes.byref(cur))
print("SetCursorPos:", ok, "want", pt2.x, pt2.y, "got", cur.x, cur.y)

# 光标下是什么窗口（看是否被别的窗口挡住）
print("window under cursor:", uu.WindowFromPoint(cur))

pm = app.primaryScreen().grabWindow(0)
print("full screen grab:", pm.width(), pm.height())
pm.save(os.path.join(ROOT, "dev", "screenshots", "_diag_screen.png"), "PNG")
print("DONE")
