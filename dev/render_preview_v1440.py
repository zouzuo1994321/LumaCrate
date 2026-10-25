# -*- coding: utf-8 -*-
"""v1.44.0 预览：① 数据管理页（含维护与重置）② 日志中心页 ③ 底部（版权左下 + 临时消息右下）。"""
import os
import sys
import tempfile
from collections import Counter

from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_render_v1440_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

import main_window as mw
from ui_settings import SettingsDialog

mw.load_style(app)
OUT = os.path.join(ROOT, "dev", "screenshots")


def on_dark(pix, out_path, bg=(23, 19, 15)):
    tmp = os.path.join(TMP, "x.png")
    pix.save(tmp)
    im = Image.open(tmp).convert("RGBA")
    cv = Image.new("RGBA", im.size, bg + (255,))
    cv.alpha_composite(im)
    cv.convert("RGB").save(out_path)
    return out_path


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


SettingsDialog.screen = lambda self: _FakeScr()

win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
for _ in range(10):
    app.processEvents()

# ③ 底部：版权左下 + 临时消息右下
h = win.height()
win._toast("已刷新（右下临时消息，4 秒后消失）", 4000)
app.processEvents()
on_dark(win.grab(QRect(0, h - 80, win.width(), 80)), os.path.join(OUT, "v1440_footer.png"))
im0 = Image.open(os.path.join(OUT, "v1440_footer.png"))
im0.resize((im0.width, im0.height * 2), Image.LANCZOS).save(os.path.join(OUT, "v1440_footer.png"))
print("saved v1440_footer.png")

dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
for _ in range(10):
    app.processEvents()

dlg._show("数据管理")
for _ in range(12):
    app.processEvents()
on_dark(dlg._pg_data.grab() if hasattr(dlg._pg_data, "grab") else dlg.grab(),
        os.path.join(OUT, "v1440_data_page.png"))
print("saved v1440_data_page.png")

dlg._show("日志中心")
for _ in range(12):
    app.processEvents()
on_dark(dlg._pg_logs.grab(), os.path.join(OUT, "v1440_logs_page.png"))
print("saved v1440_logs_page.png")
print("RENDER_DONE")
