# -*- coding: utf-8 -*-
"""ColumnFilterPopup 为什么不自绘底色？逐步隔离。"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import Qt                                    # noqa: E402
from PySide6.QtGui import QFontDatabase                          # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QLabel  # noqa: E402

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw      # noqa: E402
import ui_home                # noqa: E402

mw.load_style(app)

QSS = ("QFrame#ColFilter{background:#18181b;border:1px solid #3f3f46;"
       "border-radius:8px;}"
       "QLabel{background:transparent;color:#ecedee;font-size:12px;}")


def pump(ms=350):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def show_probe(tag, w, pts):
    w.show()
    pump()
    img = w.grab().toImage()
    out = []
    for (x, y) in pts:
        if 0 <= x < img.width() and 0 <= y < img.height():
            c = img.pixelColor(x, y)
            out.append("(%d,%d)=%s/a%d" % (x, y, c.name(), c.alpha()))
    print("%-28s %dx%d styled=%s  %s" % (tag, img.width(), img.height(),
                                        w.testAttribute(Qt.WA_StyledBackground),
                                        "  ".join(out)))
    w.close()
    pump(100)


# 1) 普通 QFrame + objectName + 局部样式（无窗口旗标、无半透明）
f1 = QFrame()
f1.setObjectName("ColFilter")
f1.setStyleSheet(QSS)
f1.resize(200, 80)
show_probe("plain QFrame / opaque", f1, [(4, 4), (20, 40)])

# 2) 同上但 WA_TranslucentBackground（模拟 uiwin.bare）
f2 = QFrame()
f2.setObjectName("ColFilter")
f2.setAttribute(Qt.WA_TranslucentBackground, True)
f2.setWindowFlags(Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
f2.setStyleSheet(QSS)
f2.resize(200, 80)
show_probe("QFrame / translucent", f2, [(4, 4), (20, 40)])

# 3) 真正的 ColumnFilterPopup（已带 uiwin.bare）
pop = ui_home.ColumnFilterPopup("favorite", "收藏", None, [("是", "1"), ("否", "0")])
show_probe("ColumnFilterPopup", pop, [(4, 4), (20, 60), (120, 90)])

# 4) 打印它自己的样式表前 160 字 + objectName
print("objectName =", pop.objectName(), "| class =", pop.metaObject().className())
print("styleSheet[:160] =", pop.styleSheet()[:160])
