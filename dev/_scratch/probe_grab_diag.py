# -*- coding: utf-8 -*-
"""诊断：离屏下怎么拿到「只有自绘内容、不透明底为透明」的位图。

对 RoundPlus(28,24) 实测 4 种取图法，打印 (0,0) 与 (13,11) 的 ARGB。
(0,0) 在圆角框外，理想值 = 全 0 alpha；(13,11) 是加号交点，理想值 = 亮白。
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
TEMP = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "lmc_probe_v209")
os.makedirs(TEMP, exist_ok=True)
os.environ["LMC_CONFIG"] = os.path.join(TEMP, "settings.json")
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import Qt, QPoint                                  # noqa: E402
from PySide6.QtGui import (QFontDatabase, QFont, QColor, QPainter, QImage,  # noqa: E402
                           QRegion)
from PySide6.QtWidgets import QApplication, QWidget                     # noqa: E402

app = QApplication(sys.argv)
QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\msyh.ttc")
app.setFont(QFont("Microsoft YaHei", 9))

import ui_hero as uh          # noqa: E402


def probe(img, tag):
    c00 = QColor(img.pixel(0, 0))
    c11 = QColor(img.pixel(13, 11))
    print("  %-26s (0,0)=a%3d %s   (13,11)=a%3d %s"
          % (tag, c00.alpha(), c00.name(), c11.alpha(), c11.name()))


def fresh():
    w = uh.RoundPlus(28, 24, tip="x")
    w.resize(28, 24)
    return w


print("=== A: 裸 grab() ===")
w = fresh()
pm = w.grab()
probe(pm.toImage(), "grab()")
print("  pixmap.hasAlphaChannel() =", pm.hasAlphaChannel())

print("=== B: grab() 前关掉背景填充 ===")
w = fresh()
w.setAttribute(Qt.WA_NoSystemBackground, True)
w.setAutoFillBackground(False)
pm = w.grab()
probe(pm.toImage(), "NoSystemBackground+grab")

print("=== C: render + DrawChildren only ===")
w = fresh()
img = QImage(28, 24, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
w.render(p, QPoint(0, 0), QRegion(), QWidget.RenderFlag.DrawChildren)
p.end()
probe(img, "render(DrawChildren)")

print("=== D: render 默认（对照） ===")
w = fresh()
img = QImage(28, 24, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
w.render(p, QPoint(0, 0))
p.end()
probe(img, "render(default)")

print("=== E: 调色板 Window 设透明 + grab ===")
w = fresh()
pal = w.palette()
pal.setColor(w.backgroundRole(), Qt.transparent)
w.setPalette(pal)
pm = w.grab()
probe(pm.toImage(), "palette.transparent+grab")

print("=== F: WA_TranslucentBackground + grab ===")
w = fresh()
w.setAttribute(Qt.WA_TranslucentBackground, True)
pm = w.grab()
probe(pm.toImage(), "WA_Translucent+grab")

print("DONE")
