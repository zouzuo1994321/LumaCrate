# -*- coding: utf-8 -*-
"""v2.0.14 探针（第三轮）：确认「变亮」真是因为换成了我们的图标。

第二轮出现一个必须排除的假象：`qproperty-icon` 和 `image:` 的亮像素数
完全一致（都是 48）。两种可能：
  A. 两条声明都真生效了（同一个 12px 圆头叉，像素自然一致）；
  B. 只要给那个 QToolButton 挂上**任意**样式表，Qt 就换一种绘制方式，
     亮像素自然从 16 跳到 48 —— 跟图标是谁无关。

本探针对照组：只改 padding/margin（不碰图标）的样式表，如果亮像素也跳到 48，
那就是 B，整条 QSS 路线作废，必须改用代码 `setIcon`。

同时量出叉号的实际包围盒（相对按钮右上角），定 icon-size 该给多少。
"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import QPoint, Qt                                   # noqa: E402
from PySide6.QtGui import QFontDatabase                                # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget, QToolButton  # noqa: E402

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import glyphs                     # noqa: E402
import main_window as mw          # noqa: E402

mw.load_style(app)

OUT = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"


def pump(ms=280):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def stats(le, band=26, tag=""):
    """右端 band 像素内：亮像素数 + 亮像素包围盒（相对输入框右上角）。"""
    img = le.grab().toImage()
    x0 = max(0, img.width() - band)
    n = 0
    bx0, by0, bx1, by1 = 9999, 9999, -1, -1
    for y in range(img.height()):
        for x in range(x0, img.width()):
            if img.pixelColor(x, y).lightness() > 120:
                n += 1
                bx0, by0 = min(bx0, x), min(by0, y)
                bx1, by1 = max(bx1, x), max(by1, y)
    box = (bx0, by0, bx1 - bx0 + 1, by1 - by0 + 1) if n else None
    print("    %-22s n=%-4d bbox=%s" % (tag, n, box))
    return img, n, box


class Host(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(520, 200)


host = Host()
host.move(140, 140)
host.show()
pump(400)

le = QLineEdit(host)
le.setGeometry(40, 40, 320, 38)
le.setText("机器")
le.setClearButtonEnabled(True)
le.show()
pump(300)

gl = glyphs.ensure(force=True).get("close")
url = (gl or "").replace("\\", "/")
print("图标 →", gl, os.path.getsize(gl) if gl else "-")

btn = le.findChildren(QToolButton)[0]
print("按钮 →", type(btn).__name__, btn.geometry().getRect(), "iconSize =", btn.iconSize(),
      "可见 =", btn.isVisible())

print("\n=== A. 对照组：不碰图标的样式表 ===")
stats(le, tag="A0 无样式表")
le.setStyleSheet("QLineEdit QToolButton { padding: 0px; margin: 0px; }")
le.update()
pump()
img, nA, _ = stats(le, tag="A1 只改 padding")
img.save(os.path.join(OUT, "v2014c3_padonly.png"))

print("\n=== B. qproperty-icon（默认 icon-size）===")
le.setStyleSheet('QLineEdit QToolButton { qproperty-icon: url("%s"); }' % url)
le.update()
pump()
img, nB, boxB = stats(le, tag="B1 qprop")
img.save(os.path.join(OUT, "v2014c3_qprop.png"))

print("\n=== C. qproperty-icon + icon-size: 12px ===")
le.setStyleSheet('QLineEdit QToolButton { qproperty-icon: url("%s"); icon-size: 12px; }' % url)
le.update()
pump()
img, nC, boxC = stats(le, tag="C1 qprop+12px")
img.save(os.path.join(OUT, "v2014c3_qprop12.png"))

print("\n=== D. 悬停态能不能换图标（qproperty-icon 在 :hover 里）===")
hi = glyphs.ensure().get("close")
le.setStyleSheet(
    'QLineEdit QToolButton { qproperty-icon: url("%s"); icon-size: 12px; }'
    'QLineEdit QToolButton:hover { qproperty-icon: url("%s"); }' % (url, url))
le.update()
pump()
stats(le, tag="D1 hover 同图")

print("\n=== E. 按钮几何 vs 可见叉号几何（对齐检查）===")
bg = btn.geometry()
print("    按钮 %dx%d @ (%d,%d)  右边缘距输入框右边 = %d"
      % (bg.width(), bg.height(), bg.x(), bg.y(), le.width() - (bg.x() + bg.width())))
print("    叉号 bbox（相对输入框右上角，x 从右往左算）= %s" % (boxC,))

print("\n=== F. 无文字时按钮是否隐藏 ===")
le.setText("")
pump()
print("    isVisible =", btn.isVisible(), " 亮像素 =", stats(le, tag="F1 空文本")[1])
le.setText("机器")
pump()
print("    isVisible =", btn.isVisible(), " 亮像素 =", stats(le, tag="F2 有文本")[1])

print("\nDONE")
