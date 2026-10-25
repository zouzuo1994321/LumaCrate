# -*- coding: utf-8 -*-
"""v1.43.4 预览：① 外观页高亮色卡（圆角扁平方形）② 主窗底部状态栏（面板色）。"""
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

TMP = tempfile.mkdtemp(prefix="lmc_render_v1434_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

import main_window as mw
from ui_settings import SettingsDialog

mw.load_style(app)
OUT = os.path.join(ROOT, "dev", "screenshots")


def to_rgb(pix, out_path, fallback=(24, 21, 19)):
    tmp = os.path.join(TMP, "raw.png")
    pix.save(tmp)
    im = Image.open(tmp).convert("RGBA")
    cnt = Counter()
    for y in range(0, im.height, 4):
        for x in range(0, im.width, 5):
            p = im.getpixel((x, y))
            if p[3] > 200:
                cnt[p[:3]] += 1
    bg = cnt.most_common(1)[0][0] if cnt else fallback
    base = Image.new("RGBA", im.size, bg + (255,))
    Image.alpha_composite(base, im).convert("RGB").save(out_path)
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

# ① 主窗底部状态栏（截取底部 90px，放大 2 倍）
h = win.height()
to_rgb(win.grab(QRect(0, h - 90, win.width(), 90)),
       os.path.join(OUT, "v1434_statusbar.png"))
im = Image.open(os.path.join(OUT, "v1434_statusbar.png"))
im = im.resize((im.width // 2 * 2, im.height * 2), Image.LANCZOS)
im.save(os.path.join(OUT, "v1434_statusbar.png"))
print("saved v1434_statusbar.png  statusbar h=%d" % win.statusBar().height())

# ② 外观页色卡
dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
for _ in range(10):
    app.processEvents()
dlg._show("个性化设置")
for _ in range(12):
    app.processEvents()
btns = list(dlg._accent_btns.values())
g = btns[0]
row = g.parentWidget()          # 色卡所在的那一行
_t = os.path.join(TMP, "row.png"); row.grab().save(_t)
_im = Image.open(_t).convert("RGBA")
_cv = Image.new("RGBA", _im.size, (23, 19, 15, 255))
_cv.alpha_composite(_im)
_cv.convert("RGB").save(os.path.join(OUT, "v1434_accents.png"))
im2 = Image.open(os.path.join(OUT, "v1434_accents.png"))
im2 = im2.resize((im2.width, im2.height * 3), Image.LANCZOS)
im2.save(os.path.join(OUT, "v1434_accents.png"))
print("saved v1434_accents.png  swatch=%dx%d count=%d"
      % (g.width(), g.height(), len(btns)))
print("RENDER_DONE")
