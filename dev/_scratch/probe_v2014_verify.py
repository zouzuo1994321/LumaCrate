# -*- coding: utf-8 -*-
"""v2.0.14 验证探针：改完之后两条需求到底成没成。

要当场看到四件事：
  ① 普通 QLineEdit 有清空按钮，QSpinBox / QComboBox 内部的**没有**（不能出现「框里塞个叉」）；
  ② 点那颗叉真的能把文本清空（不是只有个图形）；
  ③ 右键弹出来的菜单是 Qt 的 **SaveBits** 窗口（无投影），四角在亮蓝底上不黑；
  ④ 菜单里的 action 搬过家之后**点了还有反应**（全选 → 选中文本）。
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import QPoint, Qt                                    # noqa: E402
from PySide6.QtGui import (QColor, QContextMenuEvent, QFontDatabase,     # noqa: E402
                           QGuiApplication, QPainter)
from PySide6.QtWidgets import (QApplication, QComboBox, QLineEdit, QMenu,  # noqa: E402
                               QMessageBox, QPlainTextEdit, QSpinBox,
                               QToolButton, QWidget)

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw          # noqa: E402
import qtlang                     # noqa: E402

mw.load_style(app)                # ← 这里会连带安装 editfix
qtlang.install(app, "zh_CN")

OUT = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
BG = (0x1f, 0x7a, 0xe0)
ok_all = True


def pump(ms=350):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def check(tag, cond, extra=""):
    global ok_all
    ok_all = ok_all and bool(cond)
    print("    [%s] %-46s %s" % ("PASS" if cond else "FAIL", tag, extra))


class Host(QWidget):
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(*BG))


host = Host()
host.move(100, 100)
host.resize(660, 420)
host.show()
pump(600)

le = QLineEdit(host)
le.setGeometry(50, 40, 360, 38)
le.setText("机器猫 剧场版")
le.show()

sp = QSpinBox(host)
sp.setGeometry(50, 100, 140, 34)
sp.setRange(0, 100)
sp.setValue(42)
sp.show()

cb = QComboBox(host)
cb.setGeometry(220, 100, 160, 34)
cb.setEditable(True)
cb.addItems(["全部", "已看"])
cb.show()

pt = QPlainTextEdit(host)
pt.setGeometry(50, 160, 400, 70)
pt.setPlainText("这是一段用来验证右键菜单的文字。")
pt.show()
pump(500)

print("=== 1. 清空按钮该有/不该有 ===")
btns = le.findChildren(QToolButton)
check("普通 QLineEdit 有清空按钮", len(btns) == 1, "child QToolButton = %d" % len(btns))
sp_le = sp.findChildren(QLineEdit)[0]
check("QSpinBox 内部没有清空按钮",
      len(sp_le.findChildren(QToolButton)) == 0,
      "spin lineedit 内 = %d" % len(sp_le.findChildren(QToolButton)))
cb_le = cb.lineEdit()
check("可编辑 QComboBox 内部没有清空按钮",
      cb_le is not None and len(cb_le.findChildren(QToolButton)) == 0,
      "combo lineedit 内 = %s" % (len(cb_le.findChildren(QToolButton)) if cb_le else "-"))

print("\n=== 2. 点叉真的清空 ===")
btn = btns[0] if btns else None
if btn is not None:
    check("有文本时按钮可见", btn.isVisible())
    btn.click()
    pump(200)
    check("点击后文本为空", le.text() == "", repr(le.text()))
    check("空文本时按钮隐藏", not btn.isVisible())
    le.setText("机器猫 剧场版")
    pump(150)

print("\n=== 3. 右键菜单：类名 / 四角 / 条目 ===")
le.setFocus()
pump(150)
gpos = le.mapToGlobal(QPoint(30, 18))
ev = QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(30, 18), gpos)
app.sendEvent(le, ev)
pump(450)

menus = [w for w in app.topLevelWidgets() if isinstance(w, QMenu) and w.isVisible()]
check("弹出了菜单", len(menus) == 1, "topLevel QMenu = %d" % len(menus))
menu = menus[0] if menus else None
if menu is not None:
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(wintypes.HWND(int(menu.winId())), buf, 256)
    cls = buf.value
    check("窗口类不是 DropShadowSaveBits", "DropShadow" not in cls, cls)
    check("条目数 9（含 2 条分隔线）", len(menu.actions()) == 9, "n = %d" % len(menu.actions()))
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    print("        条目 =", texts)
    check("是中文（qtlang 生效）", any("撤消" in t or "复制" in t for t in texts))
    check("action 父对象是我们的菜单",
          all(a.parent() is menu for a in menu.actions()),
          str([type(a.parent()).__name__ for a in menu.actions()][:3]))

    img = QGuiApplication.primaryScreen().grabWindow(0).toImage()
    geo = menu.geometry()
    pts = [(geo.x() + 2, geo.y() + 2), (geo.x() + geo.width() - 3, geo.y() + 2),
           (geo.x() + 2, geo.y() + geo.height() - 3),
           (geo.x() + geo.width() - 3, geo.y() + geo.height() - 3)]
    vals = [img.pixelColor(x, y) for (x, y) in pts]
    print("        四角 =", [v.name() for v in vals], " 几何 =", geo.getRect())
    hi = max(max(v.red(), v.green(), v.blue()) for v in vals)
    check("四角不是黑洞（>8，越接近蓝底越好）", hi > 8, "最大通道 = %d" % hi)
    img.copy(max(0, geo.x() - 10), max(0, geo.y() - 10),
             geo.width() + 20, geo.height() + 20).save(
                 os.path.join(OUT, "v2014_ctx_after.png"))

    print("\n=== 4. 搬过来的 action 还能干活 ===")
    sel_act = [a for a in menu.actions() if "全选" in a.text()]
    check("找到「全选」条目", bool(sel_act), str([a.text() for a in menu.actions()]))
    # ⚠ 必须在菜单**还开着**的时候点：菜单带 WA_DeleteOnClose，一关就连 action
    # 一起删掉（探针第一版就是先 close 再 trigger，报 "already deleted"）。
    if sel_act:
        sel_act[0].trigger()
        pump(200)
        check("触发后确实全选", le.selectedText() == le.text(),
              "选中 = %r" % le.selectedText())
    menu.close()
    pump(250)
    check("关闭后菜单被回收（无泄漏）", menu not in app.topLevelWidgets())

print("\n=== 5. QPlainTextEdit 菜单也接管 ===")
pt.setFocus()
pump(120)
ev2 = QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(30, 18),
                        pt.mapToGlobal(QPoint(30, 18)))
app.sendEvent(pt, ev2)
pump(400)
menus2 = [w for w in app.topLevelWidgets() if isinstance(w, QMenu) and w.isVisible()]
check("文本框也弹出了菜单", len(menus2) == 1, "n = %d" % len(menus2))
if menus2:
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(wintypes.HWND(int(menus2[0].winId())), buf, 256)
    check("文本框菜单同样无投影", "DropShadow" not in buf.value, buf.value)
    menus2[0].close()
pump(200)

print("\n=== 6. 样式表里 __GLYPH_CLOSE__ 被换成了真实路径 ===")
qss = mw.render_style()
check("没有残留占位符", "__GLYPH_CLOSE__" not in qss)
check("close 图标路径已注入", "qproperty-icon: url(" in qss,
      [ln.strip() for ln in qss.splitlines() if ln.strip().startswith("qproperty-icon")][:1])

print("\n结果：%s" % ("全部通过" if ok_all else "有失败项"))
print("DONE")
