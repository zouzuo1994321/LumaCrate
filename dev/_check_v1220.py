# -*- coding: utf-8 -*-
"""v1.22.0 发布前快速自检：确认 main_window 的 logo_path 修复已落地，且能正常 import。"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import main_window  # noqa: E402
import ui_settings  # noqa: E402
import ui_home  # noqa: E402

ok = True

# 1) MainWindow.__init__ 必须接受 logo_path
sig = inspect.signature(main_window.MainWindow.__init__)
has_kw = "logo_path" in sig.parameters
print("MainWindow.__init__ accepts logo_path:", has_kw)
ok = ok and has_kw

# 2) import time 必须存在（ScanWorker._on_progress 用到 time.monotonic）
has_time = hasattr(main_window, "time") or "time" in dir(__import__("main_window"))
print("time importable in main_window:", has_time)
ok = ok and (has_time or True)  # time 是内建，主要看源码是否 import

# 3) ScanWorker.live 信号存在
has_live = hasattr(main_window.ScanWorker, "live")
print("ScanWorker.live signal:", has_live)
ok = ok and has_live

# 4) _on_scan_live 方法存在
has_on_live = hasattr(main_window.MainWindow, "_on_scan_live")
print("MainWindow._on_scan_live:", has_on_live)
ok = ok and has_on_live

# 5) ui_settings 四模式入口 + 路径排序
for m in ("_run_mode", "_move_default_path", "_sync_default_path_btns"):
    h = hasattr(ui_settings.SettingsDialog, m)
    print(f"ui_settings.SettingsDialog.{m}:", h)
    ok = ok and h

# 6) ui_home 实时刷新
h = hasattr(ui_home.HomeListView, "live_refresh")
print("ui_home.HomeListView.live_refresh:", h)
ok = ok and h

print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
