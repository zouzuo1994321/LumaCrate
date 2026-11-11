# -*- coding: utf-8 -*-
"""v2.0.14 探针（第二轮）：把「换图标」和「搬菜单」两条路都当场证死。

上一轮探针得出的结论：QSS 的 `image:` 对清空按钮无效（三张图哈希一致）。
本轮要回答：

  ① 清空按钮到底是哪个类、什么 objectName（`QLineEdit QAbstractButton{image:…}`
     选不中它，得知道它真身才能对症下药）；
  ② QSS 的 `qproperty-icon: url(...)` 能不能换掉它（能 → 纯 QSS 解决，最省事）；
  ③ 不能的话，`findChild` 出来 `setIcon()` 行不行；
  ④ 标准菜单 `createStandardContextMenu()` 的 actions 搬进 `uiwin.menu()` 后
     是否还活着（子菜单析构会不会顺手把 action 一起删掉）。

判据统一用「右侧 26px 内亮像素数」：默认的系统黑叉在暗底上≈0，换成我们的
`#a1a1aa` 圆头叉后应该跳到 60 以上。
"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import QPoint, Qt                                   # noqa: E402
from PySide6.QtGui import QFontDatabase, QGuiApplication, QIcon        # noqa: E402
from PySide6.QtWidgets import (QApplication, QLineEdit, QMenu,          # noqa: E402
                               QToolButton, QWidget)

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import glyphs                     # noqa: E402
import main_window as mw          # noqa: E402
import qtlang                     # noqa: E402
import uiwin                      # noqa: E402

mw.load_style(app)
qtlang.install(app, "zh_CN")

OUT = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def bright_count(le, band=26):
    """输入框右端 band 像素内的亮像素数（>120 亮度），当作「看得见的叉」。"""
    img = le.grab().toImage()
    n = 0
    x0 = max(0, img.width() - band)
    for y in range(img.height()):
        for x in range(x0, img.width()):
            if img.pixelColor(x, y).lightness() > 120:
                n += 1
    return n


class Host(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("v2014 clear probe")
        self.resize(560, 300)


host = Host()
host.move(120, 120)
host.show()
pump(500)

le = QLineEdit(host)
le.setGeometry(40, 40, 340, 38)
le.setText("机器")
le.setClearButtonEnabled(True)
le.show()
pump(300)

print("=== 1. 清空按钮真身 ===")
kids = le.findChildren(QWidget)
for k in kids:
    print("    class=%-28s name=%-24r size=%dx%d  visible=%s"
          % (type(k).__name__, k.objectName(), k.width(), k.height(), k.isVisible()))
btn = le.findChild(QToolButton, "qt_clear_button")
print("    findChild(QToolButton,'qt_clear_button') →", btn)
if btn is None:
    # 退一步：按 objectName 直接从 QWidget 里找
    for k in kids:
        if k.objectName() == "qt_clear_button":
            btn = k
            break
print("    实际拿到 →", type(btn).__name__ if btn else None)

print("\n=== 2. 默认（未动过）===")
print("    亮像素 =", bright_count(le))
le.grab().save(os.path.join(OUT, "v2014c_default.png"))

print("\n=== 3. QSS qproperty-icon ===")
gl = glyphs.ensure(force=True).get("close")
print("    close 图标 →", gl, os.path.getsize(gl) if gl else "-")
url = (gl or "").replace("\\", "/")
le.setStyleSheet('QLineEdit QToolButton { qproperty-icon: url("%s"); }' % url)
le.update()
pump(300)
print("    亮像素 =", bright_count(le))
le.grab().save(os.path.join(OUT, "v2014c_qprop.png"))

print("\n=== 4. QSS image（复测，确认上一轮结论）===")
le.setStyleSheet('QLineEdit QToolButton { image: url("%s"); }' % url)
le.update()
pump(300)
print("    亮像素 =", bright_count(le))
le.grab().save(os.path.join(OUT, "v2014c_image.png"))

print("\n=== 5. 代码 setIcon ===")
le.setStyleSheet('QLineEdit QToolButton { padding: 0px; margin: 0px; }')
if btn is not None:
    btn.setIcon(QIcon(gl))
    btn.setIconSize(btn.sizeHint() if False else btn.iconSize())
    btn.setFixedSize(16, 16)
    le.update()
    pump(300)
    print("    亮像素 =", bright_count(le))
    print("    btn geometry =", btn.geometry().getRect(), "iconSize =", btn.iconSize())
le.grab().save(os.path.join(OUT, "v2014c_seticon.png"))

print("\n=== 6. 标准菜单 actions 搬进 uiwin.menu() ===")
src = le.createStandardContextMenu()
print("    源菜单 items =", [(a.isSeparator() and "---" or a.text(), a.isEnabled()) for a in src.actions()])
acts = src.actions()
our = uiwin.menu(host)
src.setParent(our)          # 让源菜单（及其 action 的父对象）跟着我们的菜单一起活
src.hide()
our.addActions(acts)
print("    搬家后 our.actions() =", len(our.actions()),
      "| 第一条文本 =", our.actions()[0].text() if our.actions() else None)
print("    action 父对象 =", [a.parent().__class__.__name__ if a.parent() else None for a in acts][:3])
our.popup(QPoint(200, 200))
pump(400)
print("    弹出后 actions 仍在 =", len(our.actions()),
      "| 首条 enabled =", our.actions()[0].isEnabled() if our.actions() else None)
img = QGuiApplication.primaryScreen().grabWindow(0).toImage()
geo = our.geometry()
img.copy(max(0, geo.x() - 8), max(0, geo.y() - 8),
         geo.width() + 16, geo.height() + 16).save(os.path.join(OUT, "v2014c_menu.png"))
print("    图 v2014c_menu.png  几何 =", geo.getRect())
our.close()
pump(200)
print("    关闭后 actions =", len(our.actions()))

print("\nDONE")
