# -*- coding: utf-8 -*-
"""v1.46.6 预览出图：演员库 / 导演库铺满整行（1920 与 1680 两档）。"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_shot_v1466"
os.makedirs(SHOTS, exist_ok=True)
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import applog

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import main_window as mw

mw.load_style(app)
win = mw.MainWindow()
win.show()


def settle(n=30):
    for _ in range(n):
        app.processEvents()


def grab(w, path):
    """grab() 是透明底 PNG —— 必须合成到底色，否则半透明层会显示成纯白。"""
    img = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    iw, ih = img.width(), img.height()
    bg = Image.new("RGB", (iw, ih), (22, 19, 16))
    raw = Image.frombytes("RGBA", (iw, ih), bytes(img.constBits()))
    out = Image.alpha_composite(bg.convert("RGBA"), raw).convert("RGB")
    out.save(path)
    print("  → %s (%dx%d)" % (path, iw, ih))


for w, h, tag in ((1920, 1080, "1920"), (1680, 960, "1680")):
    win.resize(w, h)
    settle(8)
    page = win._view_actors()
    win.stack.addWidget(page)
    win.stack.setCurrentWidget(page)
    settle(35)
    grab(page, os.path.join(SHOTS, "v1466_actors_%s.png" % tag))
    win.stack.removeWidget(page)
    page.hide()
    page.deleteLater()
    settle(6)

win.resize(1920, 1080)
settle(8)
page = win._view_directors()
win.stack.addWidget(page)
win.stack.setCurrentWidget(page)
settle(35)
grab(page, os.path.join(SHOTS, "v1466_directors_1920.png"))
print("SHOT_V1466_DONE")
