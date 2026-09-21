# -*- coding: utf-8 -*-
"""临时探针3：隔离测试 HeroBanner 是否被自身样式背景覆盖。"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout
from PySide6.QtGui import QImage, QColor

app = QApplication.instance() or QApplication([])
import ui_hero

tmp = tempfile.mkdtemp(prefix="lmc_band_")
red = os.path.join(tmp, "red.jpg")
im = QImage(1600, 900, QImage.Format_RGB32)
im.fill(QColor(200, 40, 40))
im.save(red, "JPG", 95)


def report(tag, banner):
    banner.resize(800, 400)
    banner.show()
    for _ in range(5):
        app.processEvents()
    pm = banner.grab()
    img = pm.toImage()
    prof = []
    for y in range(0, 400, 40):
        vals = [img.pixelColor(x, y).red() for x in range(10, 790, 100)]
        prof.append(f"y={y}:{min(vals)}-{max(vals)}")
    print(tag, "size", banner.width(), banner.height(), "pm", banner._pm.width(), banner._pm.height())
    print("   ", " ".join(prof))


b1 = ui_hero.HeroBanner(400)
b1.set_image(red)
report("A 纯横幅(无子控件)", b1)
b1.hide()

b2 = ui_hero.HeroBanner(400)
b2.set_image(red)
vl = QVBoxLayout(b2)
vl.addStretch(1)
for t in ("标题标题", "meta", "plot"):
    vl.addWidget(ui_hero._label(t, 20, True, "#f3d9a0"))
report("B 横幅+普通标签", b2)
b2.hide()

b3 = ui_hero.HeroBanner(400)
b3.set_image(red)
vl = QVBoxLayout(b3)
vl.addStretch(1)
for t in ("标题标题", "meta", "plot"):
    vl.addWidget(ui_hero._label(t, 20, True, "#f3d9a0", shadow=True))
report("C 横幅+带投影标签", b3)
b3.hide()

b4 = ui_hero.HeroBanner(400)
b4.setStyleSheet("")
b4.set_image(red)
vl = QVBoxLayout(b4)
vl.addStretch(1)
for t in ("标题标题", "meta", "plot"):
    vl.addWidget(ui_hero._label(t, 20, True, "#f3d9a0", shadow=True))
report("D 无样式背景+带投影标签", b4)
b4.hide()

b5 = ui_hero.HeroBanner(400)
b5.set_image(red)
vl = QVBoxLayout(b5)
vl.addStretch(1)
lab = ui_hero._label("标题标题", 20, True, "#f3d9a0", shadow=True)
vl.addWidget(lab)
report("E 横幅+单个带投影标签", b5)
