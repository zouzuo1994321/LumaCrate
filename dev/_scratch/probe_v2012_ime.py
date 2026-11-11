# -*- coding: utf-8 -*-
"""v2.0.12：半透明之后，替换弹层**还是不是前台窗口**（v2.0.10 打中文的前提）。

v2.0.10 的结论：输入法只肯把输入上下文交给**前台窗口**。这一版给弹层开了
`WA_TranslucentBackground`（Windows 下 = WS_EX_LAYERED + 逐像素 alpha），
必须确认它仍然能被激活成前台窗口，否则「能打中文」会悄悄退化。
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import Qt                       # noqa: E402
from PySide6.QtGui import QFontDatabase             # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw      # noqa: E402
import ui_hero                # noqa: E402
import ui_home                # noqa: E402

mw.load_style(app)

u32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
FAIL = []


def check(label, cond, detail=""):
    print(("  OK  " if cond else "  FAIL") + "  " + label + ("  | " + str(detail) if detail else ""))
    if not cond:
        FAIL.append(label)


def pump(ms=400):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


class Host(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(760, 520)
        self.setStyleSheet("background:#151517;")


host = Host()
host.show()
host.raise_()
pump(500)


def hwnd_of(w):
    return int(w.winId())


def fg():
    return u32.GetForegroundWindow()


def exstyle(h):
    return u32.GetWindowLongW(h, GWL_EXSTYLE)


print("=== 替换弹层（半透明 + 无边框） ===")
dlg = ui_hero.PersonSearchDialog(initial="", old_name="月野江すい", parent=host)
dlg.move(host.geometry().x() + 160, host.geometry().y() + 110)
dlg.show()
pump(700)
h = hwnd_of(dlg)
ex = exstyle(h)
print("    EXSTYLE = 0x%X  (WS_EX_LAYERED=0x80000)  前台=%s  自己=%s" %
      (ex, fg(), h))
check("弹层带 WS_EX_LAYERED（半透明窗口的标志）", bool(ex & WS_EX_LAYERED), hex(ex))
check("弹层是**前台窗口**（输入法能把上下文交给它）", fg() == h, "%s vs %s" % (fg(), h))
print("    style = 0x%X (WS_POPUP=%s)" % (u32.GetWindowLongW(h, -16),
                                          bool(u32.GetWindowLongW(h, -16) & 0x80000000)))
dlg.close()
pump(400)

print("\n=== 表头筛选浮层 ===")
pop = ui_home.ColumnFilterPopup("favorite", "收藏", None, [("是", "1"), ("否", "0")], host)
pop.move(host.geometry().x() + 200, host.geometry().y() + 160)
pop.show()
pump(700)
hp = hwnd_of(pop)
check("筛选浮层是前台窗口", fg() == hp, "%s vs %s" % (fg(), hp))
check("筛选浮层带 WS_EX_LAYERED", bool(exstyle(hp) & WS_EX_LAYERED), hex(exstyle(hp)))
pop.close()
pump(300)

print("\n=== 对照组：**不**开半透明的无边框 QDialog（v2.0.11 的写法） ===")
from PySide6.QtWidgets import QDialog as _QD      # noqa: E402
ctl = _QD(host)
ctl.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
ctl.resize(300, 180)
ctl.move(host.geometry().x() + 60, host.geometry().y() + 60)
ctl.show()
pump(700)
hc = hwnd_of(ctl)
print("    前台=%s  自己=%s  一致=%s" % (fg(), hc, fg() == hc))
check("对照：不开半透明也抢不到前台（说明是脚本进程的前台锁，不是本轮回归）",
      fg() != hc, "%s vs %s" % (fg(), hc))
ctl.close()
pump(300)

print("\n失败项 = %d" % len(FAIL))
for f in FAIL:
    print("  · " + f)
