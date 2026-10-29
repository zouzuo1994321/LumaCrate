# -*- coding: utf-8 -*-
"""探针：QSS 的 image: url("中文路径") 能不能加载；勾 + 箭头出图效果。"""
import os
import sys

BASE = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(BASE, "src"))

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QSpinBox,
                               QCheckBox, QStyleFactory)
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap
from PySide6.QtCore import Qt, QPointF

OUT = r"C:/Users/zouzu/AppData/Local/Temp"
GD = os.path.join(BASE, "index_data", "_glyph_probe")
os.makedirs(GD, exist_ok=True)


def make_check(path, size=11, color="#ffffff", thick=1.9):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(thick)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    m = thick / 2 + 0.6
    p.drawPolyline([QPointF(m, size * 0.52), QPointF(size * 0.38, size - m),
                    QPointF(size - m, m + 0.4)])
    p.end()
    pm.save(path)
    return path


def make_chev(path, size=9, up=True, color="#a1a1aa", thick=1.9):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(thick)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    m = thick / 2 + 0.6
    cy = size / 2.0
    dy = size * 0.20
    tip = cy - dy if up else cy + dy
    foot = cy + dy if up else cy - dy
    p.drawPolyline([QPointF(m, foot), QPointF(size / 2.0, tip), QPointF(size - m, foot)])
    p.end()
    pm.save(path)
    return path


app = QApplication(sys.argv)
app.setStyle(QStyleFactory.create("Fusion"))

# ⚠ QPixmap 必须在 QApplication 之后才能构造（否则 qFatal 直接 abort，无任何输出）
ck = make_check(os.path.join(GD, "check.png"))
up = make_chev(os.path.join(GD, "up.png"), up=True)
dn = make_chev(os.path.join(GD, "down.png"), up=False)
print("glyph dir:", GD)
for f in (ck, up, dn):
    print("  ", os.path.exists(f), os.path.getsize(f))

app.setStyleSheet("""
QWidget#Host { background:#18181b; }
QCheckBox::indicator { width:17px; height:17px; border-radius:5px;
    border:1px solid rgba(255,255,255,0.22); background:#27272a; }
QCheckBox::indicator:checked { background:#7828c8; border-color:#9a55e0;
    image: url("%s"); }
QSpinBox { background:rgba(39,39,42,0.72); color:#ecedee; border:1px solid rgba(255,255,255,0.08);
    border-radius:10px; padding:6px 11px; }
QSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:18px;
    margin:1px 1px 0 0; border-left:1px solid rgba(255,255,255,0.08);
    border-top-right-radius:9px; background:rgba(255,255,255,0.04); }
QSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:18px;
    margin:0 1px 1px 0; border-left:1px solid rgba(255,255,255,0.08);
    border-bottom-right-radius:9px; background:rgba(255,255,255,0.04); }
QSpinBox::up-arrow { image: url("%s"); width:9px; height:9px; }
QSpinBox::down-arrow { image: url("%s"); width:9px; height:9px; }
""" % (ck.replace("\\", "/"), up.replace("\\", "/"), dn.replace("\\", "/")))

w = QWidget()
w.setObjectName("Host")
w.setAttribute(Qt.WA_StyledBackground, True)
v = QVBoxLayout(w)
v.setContentsMargins(20, 16, 20, 16)
v.setSpacing(12)
sp = QSpinBox(); sp.setRange(0, 999); sp.setValue(15); sp.setFixedWidth(140)
v.addWidget(sp, alignment=Qt.AlignLeft)
c1 = QCheckBox("选中"); c1.setChecked(True); v.addWidget(c1)
c2 = QCheckBox("未选中"); v.addWidget(c2)
w.resize(230, 170)
w.show()
app.processEvents()
p = os.path.join(OUT, "probe_glyph_img.png")
w.grab().save(p)
print("saved", p)
