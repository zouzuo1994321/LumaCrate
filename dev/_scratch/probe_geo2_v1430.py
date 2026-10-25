# -*- coding: utf-8 -*-
"""v1.43.0 页面几何自检（正确版）：切到目标页再量，判断是否溢出/可滚。"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QGroupBox, QScrollArea, QPushButton)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
if os.path.exists("C:/Windows/Fonts/msyh.ttc"):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_geo2_")
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
for _ in range(8):
    app.processEvents()


def unwrap(sc):
    inner = sc
    seen = 0
    while hasattr(inner, "widget") and seen < 4:
        w = inner.widget()
        if w is None:
            break
        inner = w
        seen += 1
    return inner


for key in ("元数据管理", "演员刮削"):
    dlg._show(key)
    for _ in range(15):
        app.processEvents()
    sc = getattr(dlg, {"元数据管理": "_pg_data", "演员刮削": "_pg_scraper"}[key])
    inner = unwrap(sc)
    is_scroll = isinstance(sc, QScrollArea)
    vh = sc.viewport().height() if is_scroll else sc.height()
    print("\n== %s ==" % key)
    print("  滚动区=%s 画布 %dx%d 视口高=%d 溢出=%d"
          % (is_scroll, inner.width(), inner.height(), vh,
             inner.height() - vh))
    gs = sorted(inner.findChildren(QGroupBox), key=lambda g: g.mapTo(inner, g.rect().topLeft()).y())
    for g in gs:
        y = g.mapTo(inner, g.rect().topLeft()).y()
        print("    %-44s y=%-4d h=%-4d 底=%-4d" % (g.title()[:42], y, g.height(), y + g.height()))

print()
print("== 元数据管理页按钮 ==")
pg = unwrap(dlg._pg_data)
for b in pg.findChildren(QPushButton):
    if "偏好" in b.text():
        print("   ", b.text(), b.size().width(), "x", b.size().height())
print("== 刮削页源码行数/列表 ==")
print("   sources:", [dlg.src_list.item(i).data(Qt.UserRole) for i in range(dlg.src_list.count())],
      "h=", dlg.src_list.height())
print("GEO2_DONE")
