# -*- coding: utf-8 -*-
"""量 v1.40.2 执行页各子项高度 + 执行组框高度，为「压缩执行高度」定基准。

离屏（offscreen）跑；必须 setStyle(Fusion) + 注册中文字体。
"""
import os
import sys

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication, QGroupBox, QScrollArea
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtCore import Qt

app = QApplication.instance() or QApplication([])
app.setStyle("Fusion")
for f in ("msyh.ttc", "msyh.ttf"):
    p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f)
    if os.path.exists(p):
        QFontDatabase.addApplicationFont(p)
app.setFont(QFont("Microsoft YaHei", 11))

import tempfile
TMP = tempfile.mkdtemp(prefix="lmc_probe_exec_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

import database as db
import applog
db.db_path = lambda: os.path.join(TMP, "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

from main_window import load_style
load_style(app)

import ui_settings
print("ui_settings:", ui_settings.__file__)
import config as cfg

st = cfg.get_settings()
dlg = ui_settings.SettingsDialog()
dlg.resize(1000, 960)
dlg.show()

# 切到演员刮削页
for key in ("scraper", "演员刮削"):
    try:
        dlg._show(key)
        break
    except Exception:
        continue

pg = dlg._pg_scraper
if isinstance(pg, QScrollArea):
    pg = pg.widget()
print("\n=== 页面 ===")
print("page h=", pg.height(), "sizeHint=", pg.sizeHint().height())
lay = pg.layout()
print("layout margins=", lay.contentsMargins().top(), lay.contentsMargins().bottom(),
      "spacing=", lay.spacing(), "count=", lay.count())
print("\n=== 逐子项 ===")
for i in range(lay.count()):
    it = lay.itemAt(i)
    w = it.widget()
    if w is None:
        print(f"  [{i}] stretch/spring  stretch={it.spacerItem() is not None}")
        continue
    title = ""
    if isinstance(w, QGroupBox):
        title = w.title()
    print(f"  [{i}] {type(w).__name__:16s} h={w.height():4d} "
          f"minH={w.minimumHeight()} maxH={w.maximumHeight()} "
          f"sizeHint={w.sizeHint().height()} stretch={lay.stretch(i)} '{title}'")

print("\n=== 执行组框内逐项 ===")
# 找执行组框
g3 = None
for i in range(lay.count()):
    w = lay.itemAt(i).widget()
    if isinstance(w, QGroupBox) and w.title() == "执行":
        g3 = w
        break
if g3 is None:
    print("未找到执行组框")
else:
    print("执行组框 h=", g3.height(), "sizeHint=", g3.sizeHint().height())
    g3l = g3.layout()
    print("组内 spacing=", g3l.spacing(), "count=", g3l.count())
    for i in range(g3l.count()):
        it = g3l.itemAt(i)
        w = it.widget()
        if w is None:
            print(f"    [{i}] stretch={g3l.stretch(i)}")
            continue
        print(f"    [{i}] {type(w).__name__:16s} h={w.height():4d} "
              f"minH={w.minimumHeight()} maxH={w.maximumHeight()} "
              f"sizeHint={w.sizeHint().height()} stretch={g3l.stretch(i)}")

print("\n=== 窗口 ===")
print("dlg size=", dlg.width(), dlg.height())
print("stack h=", dlg.stack.height())
