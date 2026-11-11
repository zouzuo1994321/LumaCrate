# -*- coding: utf-8 -*-
"""v2.0.12：剩下两个「圆角 + 顶层窗口」嫌疑犯的实测 —— QToolTip / QComboBox 下拉。

它们由 Qt 内部创建弹窗，拿不到「show 之前」的时机去开 WA_TranslucentBackground，
所以只能先量：圆角外到底是不是黑的。是黑的就要换策略（去掉圆角 / 自绘）。
"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import QPoint, Qt, QTimer                 # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QPainter  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox, QToolTip,  # noqa: E402
                               QVBoxLayout, QWidget)

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw      # noqa: E402

mw.load_style(app)

BG = "#1f7ae0"


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot():
    return QGuiApplication.primaryScreen().grabWindow(0).toImage()


def px(img, x, y):
    if x < 0 or y < 0 or x >= img.width() or y >= img.height():
        return QColor(0, 0, 0)
    return img.pixelColor(x, y)


class Host(QWidget):
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG))


host = Host()
host.resize(700, 460)
host.move(80, 80)
host.show()
pump(400)
g = host.frameGeometry()


def corner_report(tag, rect, img):
    """量左上角 8x8 区域里最黑的像素，以及它旁边 2px 处的底色。"""
    darkest = None
    for y in range(rect.top(), rect.top() + 9):
        for x in range(rect.left(), rect.left() + 9):
            c = px(img, x, y)
            v = max(c.red(), c.green(), c.blue())
            if darkest is None or v < darkest[0]:
                darkest = (v, c, x, y)
    v, c, x, y = darkest
    print("    %s rect=(%d,%d,%dx%d) 角落最黑=%s @(%d,%d)  2px内缩=%s" %
          (tag, rect.left(), rect.top(), rect.width(), rect.height(),
           c.name(), x, y, px(img, rect.left() + 2, rect.top() + 2).name()))
    return v


print("\n=== QToolTip ===")
QToolTip.showText(host.mapToGlobal(QPoint(200, 120)), "悬停提示测试 Tooltip")
pump(700)
img = shot()
# Qt 的 tooltip 是独立顶层窗口，按「非蓝、非纯黑」的矩形区域找它
found = None
for y in range(100, 260):
    for x in range(150, 520):
        c = px(img, x, y)
        if (abs(c.red() - 0x1f) > 24 or abs(c.blue() - 0xe0) > 24) and max(c.red(), c.green(), c.blue()) > 8:
            found = (x, y)
            break
    if found:
        break
print("    首个非底色像素:", found, px(img, *found).name() if found else "")
if found:
    from PySide6.QtCore import QRect
    x0, y0 = found
    x1, y1 = x0, y0
    # 向右/向下扩到边界都是底色为止
    while x1 < 700 and not (abs(px(img, x1 + 1, y0 + 5).red() - 0x1f) < 10 and
                            abs(px(img, x1 + 1, y0 + 5).blue() - 0xe0) < 10):
        x1 += 1
    while y1 < 300 and not (abs(px(img, x0 + 10, y1 + 1).red() - 0x1f) < 10 and
                            abs(px(img, x0 + 10, y1 + 1).blue() - 0xe0) < 10):
        y1 += 1
    print("    tooltip 约 (%d,%d)-(%d,%d)" % (x0, y0, x1, y1))
    corner_report("tooltip", QRect(x0, y0, x1 - x0, y1 - y0), img)
QToolTip.hideText()
pump(200)

print("\n=== QComboBox 下拉 ===")
box = QComboBox(host)
box.addItems(["选项一", "选项二", "选项三选项三选项三"])
box.move(g.x() + 120, g.y() + 90)
box.resize(220, 32)
box.show()
pump(300)
box.showPopup()
pump(500)
img = shot()
win = box.view().window()
r = win.geometry()
print("    popup window =", r, "view =", box.view().geometry())
corner_report("combo-popup", r, img)
box.hidePopup()
pump(200)

print("\n=== 对照：软件自己的面板色 / 真黑 ===")
print("    面板色 #18181b；黑框典型值 #000000~#060608")
QTimer.singleShot(0, app.quit)
app.exec()
