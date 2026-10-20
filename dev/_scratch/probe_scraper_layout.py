# -*- coding: utf-8 -*-
"""实测演员刮削页各组框 y/高/间距 + 源列表行高，定位「行间太高 / 下方留白」。离屏。"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QGroupBox
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_measure_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow
from ui_settings import SettingsDialog


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


SettingsDialog.screen = lambda self: _FakeScr()

win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()

dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
app.processEvents()

# 导航到「演员刮削」页
for k, b in dlg.sub_btns.items():
    if "刮削" in k:
        b.click()
        break
app.processEvents()

pg = dlg._pg_scraper
# 解包 freeze 的滚动区/画布
from PySide6.QtWidgets import QScrollArea, QWidget
seen = 0
while isinstance(pg, QScrollArea) and seen < 4:
    inner = pg.widget()
    if inner is None:
        break
    pg = inner
    seen += 1
if isinstance(pg, QWidget) and pg.layout() is not None:
    lay = pg.layout()
    kids = [lay.itemAt(i).widget() for i in range(lay.count())]
    kids = [w for w in kids if w is not None and w.width() > 100 and w.layout() is not None]
    if len(kids) == 1:
        pg = kids[0]

print("== 刮削页各组框 ==")
groups = [g for g in pg.findChildren(QGroupBox)]
groups.sort(key=lambda g: g.mapTo(pg, QPoint(0, 0)).y())
prev_bottom = None
for g in groups:
    p = g.mapTo(pg, QPoint(0, 0))
    gap = (p.y() - prev_bottom) if prev_bottom is not None else 0
    print(f"  {g.title()[:24]:24s} y={p.y():4d} h={g.height():4d} bottom={p.y()+g.height():4d} 上间距={gap}")
    prev_bottom = p.y() + g.height()

print("\n== 源列表 ==")
sl = dlg.src_list
p = sl.mapTo(pg, QPoint(0, 0))
print(f"  src_list y={p.y()} h={sl.height()} count={sl.count()} spacing={sl.spacing()}")
for i in range(sl.count()):
    it = sl.item(i)
    w = sl.itemWidget(it)
    rh = sl.sizeHintForRow(i)
    print(f"  row{i}: sizeHintForRow={rh} widget.sizeHint.h={w.sizeHint().height() if w else '?'}")

print("\n== 数据源组内子项 y ==")
g0 = [g for g in groups if "数据源" in g.title()]
if g0:
    g0 = g0[0]
    for w in g0.findChildren(QWidget):
        pp = w.mapTo(g0, QPoint(0, 0))
        if pp.y() >= 0 and w.height() > 5 and ("PushButton" in type(w).__name__ or "QLabel" in type(w).__name__ or "ToggleSwitch" in type(w).__name__ or "QListWidget" in type(w).__name__):
            txt = ""
            if hasattr(w, "text"):
                try:
                    txt = w.text()[:16]
                except Exception:
                    txt = ""
            print(f"  {type(w).__name__:16s} y={pp.y():4d} h={w.height():4d} {txt}")
