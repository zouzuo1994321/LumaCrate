# -*- coding: utf-8 -*-
"""探针：QSS 下 QSpinBox 上下箭头 / QCheckBox 选中勾 到底由谁画。

用法：QT_QPA_PLATFORM=windows + 参数 raw|probe 各跑一次（QApplication 不能重入）。
"""
import os
import sys

BASE = r"E:/【01】自研软件/【26-19】本地影视中心/src"
sys.path.insert(0, BASE)

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QSpinBox,
                               QCheckBox, QProxyStyle, QStyleFactory, QStyle,
                               QStyleOptionSpinBox)
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QPointF

import main_window as mw

OUT = r"C:/Users/zouzu/AppData/Local/Temp"
MODE = (sys.argv[1] if len(sys.argv) > 1 else "raw").lower()
calls = {"spinup": 0, "spindown": 0, "check": 0}


def draw_chevron(p, rect, up=True, color=QColor("#a1a1aa")):
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    w, h = rect.width(), rect.height()
    pen = QPen(color)
    pen.setWidthF(max(1.6, min(w, h) * 0.30))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    m = pen.widthF() / 2.0 + 0.6
    x0, x1 = rect.left() + m, rect.right() - m
    cy = rect.center().y()
    dy = h * 0.20
    tip = cy - dy if up else cy + dy
    foot = cy + dy if up else cy - dy
    p.drawPolyline([QPointF(x0, foot), QPointF(rect.center().x() + 0.5, tip), QPointF(x1, foot)])
    p.restore()


class ProbeStyle(QProxyStyle):
    def drawPrimitive(self, pe, opt, p, w=None):
        if pe == QStyle.PE_IndicatorSpinUp:
            calls["spinup"] += 1
            draw_chevron(p, opt.rect, True)
            return
        if pe == QStyle.PE_IndicatorSpinDown:
            calls["spindown"] += 1
            draw_chevron(p, opt.rect, False)
            return
        if pe == QStyle.PE_IndicatorCheckBox:
            calls["check"] += 1
        return super().drawPrimitive(pe, opt, p, w)


app = QApplication(sys.argv)
if MODE == "probe":
    app.setStyle(ProbeStyle(QStyleFactory.create("Fusion")))
else:
    app.setStyle(QStyleFactory.create("Fusion"))
mw.load_style(app)

w = QWidget()
w.setObjectName("ProbeHost")
w.setStyleSheet("QWidget#ProbeHost{background:#18181b;}")
w.setAttribute(Qt.WA_StyledBackground, True)
v = QVBoxLayout(w)
v.setContentsMargins(20, 16, 20, 16)
v.setSpacing(14)
sp = QSpinBox()
sp.setRange(0, 999)
sp.setValue(15)
sp.setFixedWidth(140)
v.addWidget(sp, alignment=Qt.AlignLeft)
ck1 = QCheckBox("选中")
ck1.setChecked(True)
v.addWidget(ck1)
ck2 = QCheckBox("未选中")
v.addWidget(ck2)
w.resize(240, 180)
w.show()
app.processEvents()

p = os.path.join(OUT, "probe_ui_%s.png" % MODE)
w.grab().save(p)
print("[%s] saved %s calls=%s" % (MODE, p, calls))

opt = QStyleOptionSpinBox()
opt.initFrom(sp)
opt.rect = sp.rect()
opt.subControls = QStyle.SC_All
for sc, nm in ((QStyle.SC_SpinBoxUp, "up"), (QStyle.SC_SpinBoxDown, "down"),
               (QStyle.SC_SpinBoxEditField, "edit")):
    r = sp.style().subControlRect(QStyle.CC_SpinBox, opt, sc, sp)
    print("[%s] spinbox %-4s rect=%s" % (MODE, nm, r))
print("[%s] spinbox size=%s hi=%s" % (MODE, sp.size(), sp.sizeHint()))
print("[%s] checkbox size=%s" % (MODE, ck1.size()))
