# -*- coding: utf-8 -*-
"""探测本机屏幕配置（诊断 live_verify 抓图 0x0）。"""
import os
import sys
import ctypes
import ctypes.wintypes as wt

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

print("--- Qt screens ---")
for i, s in enumerate(app.screens()):
    print(f"  [{i}] name={s.name()!r} geo={s.geometry().getRect()} "
          f"dpr={s.devicePixelRatio()} primary={s is app.primaryScreen()}")

print("virtualDesktop:", app.primaryScreen().virtualGeometry().getRect())

print("--- Win32 ---")
u32 = ctypes.windll.user32
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
SM_CXSCREEN, SM_CYSCREEN = 0, 1
print("  virtual screen origin:", u32.GetSystemMetrics(SM_XVIRTUALSCREEN),
      u32.GetSystemMetrics(SM_YVIRTUALSCREEN),
      "size:", u32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
      u32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
print("  primary screen size:", u32.GetSystemMetrics(SM_CXSCREEN),
      u32.GetSystemMetrics(SM_CYSCREEN))
# 进程的 DPI  awareness
try:
    print("  DPI aware:", ctypes.windll.shcore.GetProcessDpiAwareness(
        ctypes.windll.kernel32.GetCurrentProcess()))
except Exception as e:
    print("  GetProcessDpiAwareness failed:", e)
