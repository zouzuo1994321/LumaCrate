# -*- coding: utf-8 -*-
"""v1.46.8 预览出图：状态栏进度条四态对比（4 倍放大 + 中文标签）。

四态：空闲空槽 / 载入中(-1) / 缓存中 45% / 快闪后 30ms（修复前这一格必定全空）。
"""
import os
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_shot_v1468"
os.makedirs(SHOTS, exist_ok=True)
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image, ImageDraw, ImageFont
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
win.resize(1920, 1080)
win.show()


def settle(n=20):
    for _ in range(n):
        app.processEvents()


def spin(ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.004)


def img_of(w):
    im = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    iw, ih = im.width(), im.height()
    bg = Image.new("RGB", (iw, ih), (24, 20, 17))
    raw = Image.frombytes("RGBA", (iw, ih), bytes(im.constBits()))
    return Image.alpha_composite(bg.convert("RGBA"), raw).convert("RGB")


bar = win._busy_bar
shots = []

mw.set_busy(None, "")
spin(700)
shots.append(("空闲（空槽）", img_of(bar)))
mw.set_busy(-1, "载入中")
settle(12)
shots.append(("载入中（不确定态）", img_of(bar)))
mw.set_busy(45, "缓存中")
settle(12)
shots.append(("缓存中 45%", img_of(bar)))
mw.set_busy(None, "")
spin(700)
mw.set_busy(-1, "载入中")
mw.set_busy(None, "")
spin(30)
shots.append(("快闪后 30ms（修复前必空）", img_of(bar)))

SCALE = 5
PAD_X, PAD_Y, GAP = 22, 16, 14
fnt = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
title = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 24)
row_h = 6 * SCALE + PAD_Y * 2
W = 110 * SCALE + PAD_X * 2 + 300
H = 56 + row_h * len(shots) + GAP * (len(shots) - 1) + 20
canvas = Image.new("RGB", (W, H), (26, 22, 19))
d = ImageDraw.Draw(canvas)
d.text((PAD_X, 14), "状态栏进度条：载入 / 缓存中切主题高亮朱红（v1.46.8）",
       font=title, fill=(212, 175, 55))
y = 56
for label, im in shots:
    big = im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)
    canvas.paste(big, (PAD_X, y + PAD_Y - 2))
    d.text((PAD_X + big.width + 24, y + PAD_Y + 4), label, font=fnt, fill=(200, 184, 146))
    y += row_h + GAP
out = os.path.join(SHOTS, "v1468_busybar_states.png")
canvas.save(out)
print("  → %s (%dx%d)" % (out, canvas.width, canvas.height), flush=True)
print("SHOT_V1468_DONE", flush=True)
