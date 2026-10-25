# -*- coding: utf-8 -*-
"""v1.43.0 页面几何/构建自检：元数据管理页与演员刮削页是否溢出、控件是否建全。"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QGroupBox, QStackedWidget
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_geo_v1430_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

import main_window as mw
import ui_settings as uis

mw.load_style(app)
win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
dlg = uis.SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
for _ in range(10):
    app.processEvents()

print("dialog %dx%d" % (dlg.width(), dlg.height()))
print("stack 视口 %dx%d" % (dlg.stack.width(), dlg.stack.height()) if hasattr(dlg, "stack")
      else "no stack attr")

for key, page in (("元数据管理", dlg._pg_data), ("演员刮削", dlg._pg_scraper)):
    inner = page
    seen = 0
    while hasattr(inner, "widget") and seen < 4:
        w = inner.widget()
        if w is None:
            break
        inner = w
        seen += 1
    print("\n== %s ==" % key)
    print("  page %dx%d  minHint=%s" % (inner.width(), inner.height(),
                                        inner.minimumSizeHint()))
    gs = inner.findChildren(QGroupBox)
    for g in gs:
        print("    %-46s h=%-4d y=%-4d" % (g.title()[:44], g.height(),
                                          g.mapTo(inner, g.rect().topLeft()).y()))
    print("  控件检查：", end="")
    checks = []
    if key == "元数据管理":
        checks = [("pref_hint", hasattr(dlg, "pref_hint")),
                  ("导出偏好按钮", any(b.text() == "导出偏好…" for b in inner.findChildren(
                      __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton))),
                  ("导入偏好按钮", any(b.text() == "导入偏好…" for b in inner.findChildren(
                      __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)))]
    else:
        checks = [("sc_clean", hasattr(dlg, "sc_clean")),
                  ("sc_gf", hasattr(dlg, "sc_gf")),
                  ("sc_tpdb", hasattr(dlg, "sc_tpdb")),
                  ("数据源行数", dlg.src_list.count()),
                  ("列表高", dlg.src_list.height())]
    print(checks)
print()
print("导航键：", [k for k in dlg.sub_btns.keys()])
print("GEO_DONE")
