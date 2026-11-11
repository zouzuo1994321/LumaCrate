# -*- coding: utf-8 -*-
"""v2.0.14 探针：① 标准右键菜单套 uiwin.bare() 后还黑不黑 ② 输入框清空按钮的样子。

三件事要当场看到：
  ① 标准菜单原样弹出：窗口类是 `QWindowPopupDropShadowSaveBits`（Qt 把阴影画进窗口里），
     亮蓝底上四角是**比背景暗的一圈** —— 这就是用户说的「圆角外有黑色的小角」；
  ② 同一个菜单先 `uiwin.bare()` 再 popup：窗口类应变成 `QWindowPopupSaveBits`（无阴影），
     四角应等于亮蓝底原色；
  ③ QLineEdit 开 `setClearButtonEnabled(True)` 后，右侧那颗 × 在暗色主题下长什么样，
     以及 QSS 的哪种选择器能给它换图标。
"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import QPoint, QTimer, Qt                      # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget     # noqa: E402

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw          # noqa: E402
import uiwin                     # noqa: E402
import qtlang                    # noqa: E402

mw.load_style(app)
qtlang.install(app, "zh_CN")

OUT = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
BG = (0x1f, 0x7a, 0xe0)


def pump(ms=400):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot():
    return QGuiApplication.primaryScreen().grabWindow(0).toImage()


def px(img, x, y):
    return img.pixelColor(x, y) if 0 <= x < img.width() and 0 <= y < img.height() else QColor(0, 0, 0)


class Host(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("v2014 probe")
        self.resize(720, 420)
        self.setStyleSheet("")          # 别让全局皮肤把亮蓝底盖掉

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(*BG))


host = Host()
host.move(90, 90)
host.show()
pump(600)
g = host.frameGeometry()

le = QLineEdit(host)
le.setGeometry(60, 60, 420, 38)
le.setPlaceholderText("在列表中搜索片名…")
le.setText("机器")
le.show()
pump(300)


def cls_of(w):
    """取平台窗口的 Win32 类名（Qt 用它区分 Popup 有/无阴影）。"""
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(wintypes.HWND(int(w.winId())), buf, 256)
    return buf.value


def corner_report(tag, rect):
    img = shot()
    pts = [(rect.x() + 2, rect.y() + 2), (rect.x() + rect.width() - 3, rect.y() + 2),
           (rect.x() + 2, rect.y() + rect.height() - 3),
           (rect.x() + rect.width() - 3, rect.y() + rect.height() - 3)]
    vals = [px(img, x, y) for (x, y) in pts]
    print("    %s  %dx%d @ (%d,%d)  四角=%s"
          % (tag, rect.width(), rect.height(), rect.x(), rect.y(),
             [v.name() for v in vals]))
    return img, vals


print("=== 1. 标准菜单（原样） ===")
m1 = le.createStandardContextMenu()
m1.popup(QPoint(g.x() + 100, g.y() + 120))
pump(450)
win1 = m1.windowHandle()
img1, v1 = corner_report("原样", m1.geometry())
print("    windowFlags=0x%08x  class=%s" % (int(m1.windowFlags()), cls_of(m1)))
m1.close()
pump(250)

print("\n=== 2. 同一个菜单，先 uiwin.bare() 再弹 ===")
m2 = le.createStandardContextMenu()
uiwin.bare(m2)
m2.popup(QPoint(g.x() + 100, g.y() + 120))
pump(450)
img2, v2 = corner_report("bare", m2.geometry())
print("    windowFlags=0x%08x  class=%s" % (int(m2.windowFlags()), cls_of(m2)))
m2.close()
pump(250)

for tag, img, m in (("menu_raw", img1, m1), ("menu_bare", img2, m2)):
    geo = m.geometry()
    img.copy(max(0, geo.x() - 10), max(0, geo.y() - 10),
             geo.width() + 20, geo.height() + 20).save(os.path.join(OUT, "v2014_%s.png" % tag))
    print("    图 v2014_%s.png" % tag)

print("\n=== 3. 清空按钮（QSS 选择器对比） ===")
le2 = QLineEdit(host)
le2.setGeometry(60, 130, 300, 36)
le2.setText("机器")
le2.setClearButtonEnabled(True)
le2.show()
pump(300)
img3 = shot()
le2.grab().save(os.path.join(OUT, "v2014_clear_default.png"))
print("    默认：图 v2014_clear_default.png")

# 三种选择器各试一次，看哪一种真能换掉图标
GLYPH = None
try:
    import glyphs
    GLYPH = glyphs.ensure(force=True).get("close")
except Exception as e:
    print("    glyphs 出错：", e)
print("    close 图标 =", GLYPH)

for sel in ("QLineEdit > QAbstractButton", "QLineEdit QToolButton", "QLineEdit QAbstractButton"):
    le2.setStyleSheet("%s { image: url(\"%s\"); }" % (sel, (GLYPH or "").replace("\\", "/")))
    le2.update()
    pump(250)
    tag = sel.replace(" ", "").replace(">", "-")
    le2.grab().save(os.path.join(OUT, "v2014_clear_%s.png" % tag))
    print("    选择器 %-28s → v2014_clear_%s.png" % (sel, tag))

le2.setStyleSheet("")
le2.update()
pump(200)

print("\n=== 4. 亮字/图标像素统计（暗底上能不能看见） ===")
imgd = shot()
box = le2.mapTo(host, QPoint(0, 0))
right = (box.x() + le2.width() - 30, box.y() + 4, box.x() + le2.width(), box.y() + le2.height() - 4)
n = 0
for y in range(right[1], right[3]):
    for x in range(right[0], right[2]):
        c = imgd.pixelColor(x, y)
        if c.lightness() > 120:
            n += 1
print("    右侧 30px 内亮像素 =", n)

print("\nDONE")
