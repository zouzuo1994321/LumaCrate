# -*- coding: utf-8 -*-
"""对照实验：定位「窗口为何不透明」。放在彩色棋盘上，逐级加复杂度。

A 纯 QWidget + frameless + WA_TranslucentBackground，paint 50% 红      → 基准：应能看到棋盘
B 同上但不加透明属性                                                   → 基准：应看不到棋盘
C 纯 QMainWindow + frameless + 透明属性，paintEvent 上 57% 暗色          → 看 QMainWindow 是否可透明
D C + 应用本项目的 style.qss（令牌已替换）                              → 看 QSS 是否把它顶回不透明
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QWidget, QMainWindow
from PySide6.QtGui import QGuiApplication, QPainter, QColor
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)

import config as cfg
from main_window import render_style


class Board(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)
        self.setGeometry(60, 60, 2000, 900)

    def paintEvent(self, e):
        p = QPainter(self)
        cols = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#00c7be",
                "#30b0c7", "#007aff", "#5856d6", "#af52de", "#ff2d55"]
        for i in range(0, self.width(), 50):
            p.fillRect(i, 0, 50, self.height(), QColor(cols[(i // 50) % len(cols)]))
        p.end()


class Swatch(QWidget):
    def __init__(self, translucent, x):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)
        if translucent:
            self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(x, 700, 420, 240)

    def paintEvent(self, e):
        p = QPainter(self); p.fillRect(self.rect(), QColor(255, 0, 0, 128)); p.end()


class MW(QMainWindow):
    def __init__(self, translucent, x):
        super().__init__()
        if translucent:
            self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setGeometry(x, 130, 600, 400)
        self.setObjectName("CentralVeil")

    def paintEvent(self, e):
        p = QPainter(self); p.fillRect(self.rect(), QColor(13, 11, 10, 146)); p.end()


WITH_STYLE = (len(sys.argv) > 1 and sys.argv[1] == "style")
if WITH_STYLE:
    app.setStyleSheet(render_style(cfg.get_settings().appearance))

board = Board(); board.show()
a = Swatch(True, 60); a.show()
b = Swatch(False, 520); b.show()
c = MW(True, 980); c.show()
items = [("A 透明 QWidget", a), ("B 不透明 QWidget", b), ("C QMainWindow 透明", c)]
if WITH_STYLE:
    d = MW(True, 1620); d.show()
    items.append(("D 同上 + 本项目样式", d))
for _ in range(10):
    app.processEvents()
time.sleep(1.2)
for _ in range(10):
    app.processEvents()

shot = QGuiApplication.primaryScreen().grabWindow(0).toImage()
shot.save(os.path.join(OUT, "glass_control.png"))

print("WITH_STYLE =", WITH_STYLE)
for name, w in items:
    y = w.y() + w.height() // 2
    row = [shot.pixelColor(w.x() + dx, y).getRgb()[:3] for dx in range(60, w.width() - 40, 60)]
    print(f"{name:26s} 不同颜色数={len(set(row))}  采样={row[:6]}")

print("\ndone")
