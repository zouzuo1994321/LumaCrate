# -*- coding: utf-8 -*-
"""v1.18.0 离屏验证：设置→数据与日志 的「实时运行状态」面板确实建出并填充（#98）。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QGroupBox
import version as version
import ui_settings as us

app = QApplication([])
dlg = us.SettingsDialog()           # __init__ 已构建数据页并填过一次运行状态
dlg._refresh_runtime_status()       # 再刷一次，确保标签有值

labels = dlg._rt_labels
groups = [w for w in dlg.findChildren(QGroupBox) if w.title() == "实时运行状态"]

print("RT group found:", bool(groups))
print("RT keys:", list(labels.keys()))
for k, v in labels.items():
    print("   ", k, "=", v.text())

ok = bool(groups)
ok = ok and labels.get("软件版本", None) is not None and labels["软件版本"].text() == version.FULL_VERSION
# 数据库模式应包含 WAL；媒体总数（顶层）应已填充（非占位 —）
ok = ok and "WAL" in (labels.get("数据库模式", None).text() or "")
ok = ok and labels.get("媒体总数（顶层）", None) is not None and "部" in labels["媒体总数（顶层）"].text()

print("SETTINGS_RUNTIME_OK" if ok else "SETTINGS_RUNTIME_FAIL")
sys.exit(0 if ok else 1)
