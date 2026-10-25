# -*- coding: utf-8 -*-
"""v1.43.5 预览：① 窗口透明度滑块把手（圆角扁平方形）② 底部常驻版权（临时消息后仍在）。"""
import os
import sys
import tempfile
from collections import Counter

from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QSlider
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_render_v1435_")
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
for _ in range(12):
    app.processEvents()

# ① 底部：先无消息，再弹一条临时消息（证明版权不被顶掉）
h = win.height()
top = h - 80
on_dark(win.grab(QRect(0, top, win.width(), 80)), os.path.join(OUT, "v1435_footer.png"))
im = Image.open(os.path.join(OUT, "v1435_footer.png"))
im.resize((im.width, im.height * 2), Image.LANCZOS).save(os.path.join(OUT, "v1435_footer.png"))
win.statusBar().showMessage("已刷新（临时消息，3 秒后消失）", 3000)
app.processEvents()
on_dark(win.grab(QRect(0, top, win.width(), 80)), os.path.join(OUT, "v1435_footer_toast.png"))
im = Image.open(os.path.join(OUT, "v1435_footer_toast.png"))
im.resize((im.width, im.height * 2), Image.LANCZOS).save(os.path.join(OUT, "v1435_footer_toast.png"))
print("saved v1435_footer.png / v1435_footer_toast.png")

# ② 外观页滑块把手
dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
for _ in range(10):
    app.processEvents()
dlg._show("个性化设置")
for _ in range(12):
    app.processEvents()
sl = dlg.findChildren(QSlider)
print("sliders:", len(sl), [s.objectName() for s in sl])
if sl:
    s0 = sl[0]
    on_dark(s0.grab(), os.path.join(TMP, "slider.png"))
    im2 = Image.open(os.path.join(TMP, "slider.png"))
    im2 = im2.crop((im2.width - 120, 0, im2.width, im2.height))
    im2 = im2.resize((im2.width * 3, im2.height * 4), Image.LANCZOS)
    im2.save(os.path.join(OUT, "v1435_slider_handle.png"))
    print("saved v1435_slider_handle.png  slider=%dx%d" % (s0.width(), s0.height()))
print("RENDER_DONE")
