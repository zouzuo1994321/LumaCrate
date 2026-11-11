# -*- coding: utf-8 -*-
"""v2.0.12：把 QToolTip 真机抓下来存 png，肉眼/像素两路确认圆角外是不是黑的。"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import QPoint, Qt, QTimer                 # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget            # noqa: E402

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw      # noqa: E402

mw.load_style(app)

BG = "#1f7ae0"
OUT = r"E:\【01】自研软件\【26-19】本地影视中心\dev\_scratch\tooltip_shot.png"


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


class Host(QWidget):
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG))


host = Host()
host.resize(700, 460)
host.move(80, 80)
host.show()
host.raise_()
host.activateWindow()
pump(500)

QTimer.singleShot(80, lambda: None)
from PySide6.QtWidgets import QToolTip   # noqa: E402
QToolTip.showText(host.mapToGlobal(QPoint(200, 150)), "悬停提示测试 Tooltip 圆角")
pump(900)

img = QGuiApplication.primaryScreen().grabWindow(0).toImage()
img.save(OUT)
print("saved", OUT, img.width(), img.height())
QToolTip.hideText()
pump(150)
QTimer.singleShot(0, app.quit)
app.exec()
