# -*- coding: utf-8 -*-
"""渲染演员刮削数据源组到 PNG，肉眼核对行高/文字裁切。"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QGroupBox
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtCore import Qt, QPoint, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_render_")
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
for k, b in dlg.sub_btns.items():
    if "刮削" in k:
        b.click()
        break
app.processEvents()

OUT = "C:/Users/zouzu/AppData/Local/Temp/src_rows.png"
pix = dlg.src_list.grab()
pix.save(OUT)
print("saved", OUT, pix.width(), pix.height())

# 顺便抓整页
pg = dlg._pg_scraper
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
pix2 = pg.grab()
pix2.save("C:/Users/zouzu/AppData/Local/Temp/scraper_page.png")
print("saved page", pix2.width(), pix2.height())
