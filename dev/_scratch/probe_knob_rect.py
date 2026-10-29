# -*- coding: utf-8 -*-
"""量「窗口透明度」滑块把手白芯的尺寸：修前（无高度设置、QSS 也没 min-height）vs 修后。

做法：把 style.qss 读进来，按 tag 决定是否剥掉 `QSlider { min-height: 24px; }`，
再给 QSlider 设/不设 24px 固定高 —— 两条路都走一遍才看得出差别。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QSlider, QStyleFactory
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QColor

app = QApplication(sys.argv)
app.setStyle(QStyleFactory.create("Fusion"))
import main_window as mw

TAG = sys.argv[1] if len(sys.argv) > 1 else "after"
qss = mw.render_style()
if TAG == "before":
    qss = qss.replace("QSlider { min-height: 24px; }", "")
app.setStyleSheet(qss)

host = QWidget()
host.setObjectName("H")
host.setStyleSheet("QWidget#H{background:#18181b;}")
host.setAttribute(Qt.WA_StyledBackground, True)
v = QVBoxLayout(host)
v.setContentsMargins(0, 0, 0, 0)
v.setSpacing(0)
sl = QSlider(Qt.Horizontal)
if TAG != "before":
    sl.setFixedHeight(24)
sl.setRange(30, 100)
sl.setValue(100)
sl.setFixedWidth(400)
v.addWidget(sl)
host.resize(400, max(24, sl.height()))
host.show()
app.processEvents()
h = sl.height()
im = host.grab().toImage().convertToFormat(QImage.Format_ARGB32)
print("[%s] slider height=%d img=%dx%d" % (TAG, h, im.width(), im.height()))

xs, ys = [], []
for y in range(im.height()):
    for x in range(im.width()):
        c = im.pixelColor(x, y)
        if c.red() > 232 and c.green() > 232 and c.blue() > 232:
            xs.append(x); ys.append(y)
if xs:
    print("[%s] 白芯 bbox %dx%d  (x %d..%d, y %d..%d)"
          % (TAG, max(xs) - min(xs) + 1, max(ys) - min(ys) + 1,
             min(xs), max(xs), min(ys), max(ys)))
else:
    print("[%s] 没找到白色把手" % TAG)
out = os.path.join(r"C:/Users/zouzu/AppData/Local/Temp", "knob2_%s.png" % TAG)
canvas = QImage(im.width(), im.height(), QImage.Format_ARGB32)
canvas.fill(QColor("#18181b"))
p = QPainter(canvas); p.drawImage(0, 0, im); p.end()
canvas.save(out)
print("saved", out)
