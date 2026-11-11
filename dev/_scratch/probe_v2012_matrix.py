# -*- coding: utf-8 -*-
"""半透明顶层窗口里，QSS 底色到底谁画？
矩阵：QFrame / QDialog × （基础类选择器 / #objectName 选择器）× 有无内层容器。
"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import Qt                                   # noqa: E402
from PySide6.QtWidgets import (QApplication, QDialog, QFrame,   # noqa: E402
                               QLabel, QVBoxLayout)

app = QApplication([])


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def probe(tag, w, pt=(4, 4)):
    w.show()
    pump()
    img = w.grab().toImage()
    c = img.pixelColor(*pt)
    print("%-44s styled=%-5s  pix%s = %s alpha=%d" %
          (tag, w.testAttribute(Qt.WA_StyledBackground), pt, c.name(), c.alpha()))
    w.close()
    pump(80)


def mk(cls, sel, translucent=True, child=False):
    w = cls()
    if translucent:
        w.setAttribute(Qt.WA_TranslucentBackground, True)
        w.setWindowFlags(Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    w.setObjectName("ColFilter")
    w.resize(200, 90)
    if child:
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        box = QFrame()
        box.setObjectName("Box")
        lay.addWidget(box)
        w.setStyleSheet("QFrame#Box{background:#18181b;border-radius:8px;}")
    else:
        w.setStyleSheet(sel + "{background:#18181b;border-radius:8px;}")
    return w


Q_OBJ = "QFrame#ColFilter"
Q_TYP = "QFrame"
D_OBJ = "QDialog#ColFilter"
D_TYP = "QDialog"

probe("QFrame  opaque  QFrame#ColFilter", mk(QFrame, Q_OBJ, False))
probe("QFrame  transl  QFrame#ColFilter", mk(QFrame, Q_OBJ, True))
probe("QFrame  transl  QFrame", mk(QFrame, Q_TYP, True))
probe("QDialog opaque  QDialog#ColFilter", mk(QDialog, D_OBJ, False))
probe("QDialog transl  QDialog#ColFilter", mk(QDialog, D_OBJ, True))
probe("QDialog transl  QDialog", mk(QDialog, D_TYP, True))
probe("QFrame  transl  + inner box", mk(QFrame, Q_TYP, True, child=True))
