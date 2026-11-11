# -*- coding: utf-8 -*-
"""v2.0.13 探针：QLineEdit 标准右键菜单 —— 文本语言 + 四角是否露黑。

要回答三件事（全部真窗口 + `grabWindow(0)` 合成后像素）：
  ① 不装 QTranslator 时，标准菜单的 action 文本是英文（复现用户截图）；
  ② 装上 `qtbase_zh_CN.qm` 之后变成「撤销/重做/剪切/复制/粘贴/删除/全选」；
  ③ 这个**不是我们创建的** QMenu（Qt 内建）圆角外到底是什么色 ——
     垫亮蓝底一看就知道：是蓝（透明）还是近黑（窗口表面）。
"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import QLibraryInfo, QLocale, QPoint, QTimer, Qt, QTranslator  # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QPainter           # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget                       # noqa: E402

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw          # noqa: E402

mw.load_style(app)

BG = (0x1f, 0x7a, 0xe0)
FAIL = []


def pump(ms=400):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot():
    return QGuiApplication.primaryScreen().grabWindow(0).toImage()


def px(img, x, y):
    if 0 <= x < img.width() and 0 <= y < img.height():
        return img.pixelColor(x, y)
    return QColor(0, 0, 0)


def texts(menu):
    return [a.text().replace("&", "") for a in menu.actions() if not a.isSeparator()]


class Host(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("v2013 ctx probe")
        self.resize(760, 420)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(*BG))


host = Host()
host.move(80, 80)
host.show()
pump(600)
g = host.frameGeometry()

le = QLineEdit(host)
le.setGeometry(60, 60, 420, 38)
le.setPlaceholderText("在列表中搜索片名…")
le.show()
pump(300)

print("=== 1. 未装 QTranslator：标准右键菜单文本 ===")
m0 = le.createStandardContextMenu()
t0 = texts(m0)
print("   ", t0)
m0.deleteLater()
pump(100)

print("\n=== 2. 装 qtbase_zh_CN.qm 之后 ===")
tr_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
print("    TranslationsPath =", tr_dir, os.path.isdir(tr_dir))
tr = QTranslator(app)
ok = tr.load(QLocale("zh_CN"), "qtbase", "_", tr_dir)
print("    load(qtbase, zh_CN) =", ok, "| file=", tr.filePath())
if ok:
    app.installTranslator(tr)

m1 = le.createStandardContextMenu()
t1 = texts(m1)
print("   ", t1)

EXPECT = ["撤销", "重做", "剪切", "复制", "粘贴", "删除", "全选"]
print("\n=== 3. 真弹出，量四角（亮蓝底） ===")
m1.popup(QPoint(g.x() + 120, g.y() + 130))
pump(500)
mg = m1.geometry()
img = shot()
c_tl = px(img, mg.x() + 2, mg.y() + 2)
c_tr = px(img, mg.x() + mg.width() - 3, mg.y() + 2)
c_in = px(img, mg.x() + 30, mg.y() + 30)
print("    菜单 %dx%d @ (%d,%d)  左上=%s 右上=%s 内侧=%s"
      % (mg.width(), mg.height(), mg.x(), mg.y(),
         c_tl.name(), c_tr.name(), c_in.name()))
img.copy(mg.x() - 12, mg.y() - 12, mg.width() + 24, mg.height() + 24) \
   .save(r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots\v2013_ctx_menu.png")
m1.close()
pump(200)

print("\n=== 4. 判定 ===")
print("    撤销" in t1 or t1[:1] == ["撤销"] and "  文本已中文" or "  文本仍英文")


def check(label, cond, detail=""):
    print(("  OK  " if cond else "  FAIL") + "  " + label + ("  | " + str(detail) if detail else ""))
    if not cond:
        FAIL.append(label)


check("英文原文可复现（未装翻译 = Undo/Redo…）", t0[:1] == ["Undo"], t0[:2])
check("装翻译后 = 撤销/重做/剪切/复制/粘贴/删除/全选", t1 == EXPECT, t1)
check("菜单圆角外是蓝色底（透明），不是黑", c_tl.blue() > c_tl.red() + 20, c_tl.name())

print("\n失败项 = %d" % len(FAIL))
for f in FAIL:
    print("  · " + f)
QTimer.singleShot(0, app.quit)
app.exec()
