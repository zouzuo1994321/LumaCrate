# -*- coding: utf-8 -*-
"""量一下：Ghost 窄按钮 disabled 与 enabled 的文字亮度到底有没有区别。

用户故事：v2.0.6 新增的四枚按钮（播放/定位文件/打开文件夹/删除…）初始是灰的，
但 `QPushButton:disabled{color:#52525b}` 与 `QPushButton#Ghost{color:#d4d4d8}` 的
选择器权重不同（ID=100 > 伪类），若 ID 那条压过 :disabled，禁用态会「看着能点」。
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:/【01】自研软件/【26-19】本地影视中心/src")

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout   # noqa: E402
from PySide6.QtGui import QFontDatabase                            # noqa: E402

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw      # noqa: E402
from ui_hero import compact_button   # noqa: E402

mw.load_style(app)

w = QWidget()
w.setStyleSheet("background:#18181b;")
w.resize(320, 90)
v = QVBoxLayout(w)
b1 = compact_button("删除…", 72, 26, "enabled")
b2 = compact_button("删除…", 72, 26, "disabled")
b2.setEnabled(False)
v.addWidget(b1)
v.addWidget(b2)
w.show()
app.processEvents()

im = w.grab().toImage()
print("size", im.width(), im.height())
print("b1 geom", b1.x(), b1.y(), b1.width(), b1.height())
print("b2 geom", b2.x(), b2.y(), b2.width(), b2.height())


def maxbright(btn):
    best, where = 0, None
    for y in range(btn.y(), btn.y() + btn.height()):
        for x in range(btn.x(), btn.x() + btn.width()):
            c = im.pixelColor(x, y)
            v_ = (c.red() + c.green() + c.blue()) // 3
            if v_ > best:
                best, where = v_, (x, y)
    return best, where


print("enabled  最亮:", maxbright(b1))
print("disabled 最亮:", maxbright(b2))
im.save("C:/Users/zouzu/AppData/Local/Temp/probe_ghost.png")
