# -*- coding: utf-8 -*-
"""v1.44.1 预览：① 演员刮削数据源（5 源 + Cookie 获取 + 测试全部 Cookie 存活）
② Cookie 获取对话框（顶部可点网址）。"""
import os
import sys
import tempfile

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

TMP = tempfile.mkdtemp(prefix="lmc_render_v1441_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

import main_window as mw
from ui_settings import SettingsDialog, CloudflareDialog

mw.load_style(app)
OUT = os.path.join(ROOT, "dev", "screenshots")


def on_dark(pix, out_path, bg=(23, 19, 15)):
    tmp = os.path.join(TMP, "x.png")
    pix.save(tmp)
    im = Image.open(tmp).convert("RGBA")
    cv = Image.new("RGBA", im.size, bg + (255,))
    cv.alpha_composite(im)
    cv.convert("RGB").save(out_path)


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
for _ in range(8):
    app.processEvents()

dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
for _ in range(10):
    app.processEvents()
dlg._show("演员刮削")
for _ in range(14):
    app.processEvents()
on_dark(dlg.grab(), os.path.join(OUT, "v1441_scraper_cookie.png"))
print("saved v1441_scraper_cookie.png  sources=%d" % dlg.src_list.count())

cd = CloudflareDialog("https://avbase.net/", "Cookie 获取 · avbase.net", parent=dlg)
cd.setAttribute(Qt.WA_DontShowOnScreen, True)
cd.resize(660, 320)
cd.show()
for _ in range(8):
    app.processEvents()
on_dark(cd.grab(), os.path.join(OUT, "v1441_cookie_dialog.png"))
print("saved v1441_cookie_dialog.png")
cd.close()
print("RENDER_DONE")
