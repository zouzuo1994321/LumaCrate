# -*- coding: utf-8 -*-
"""v2.0.10 诊断：首页表头漏斗弹窗（ColumnFilterPopup）到底是不是可激活窗口。

判据链：
  1) 窗口标志里有没有 Qt.Popup（Windows 下 Qt 对它强制 SW_SHOWNOACTIVATE）
  2) HWND 的 EXSTYLE 有没有 WS_EX_NOACTIVATE(0x08000000)
  3) show() 之后 isActiveWindow() / QApplication.activeWindow() 是不是它
  4) 往里 post 一条 WM_IME_STARTCOMPOSITION，看 QLineEdit 有没有收到 inputMethodEvent
     —— IME 的汉字上屏全靠这条链路；收不到就是「中文打不进去」的根因。
"""
import os
import sys
import ctypes

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import Qt, QEvent                     # noqa: E402
from PySide6.QtGui import QGuiApplication                 # noqa: E402
from PySide6.QtWidgets import QApplication                # noqa: E402

app = QApplication(sys.argv)

import ui_home                                            # noqa: E402

u32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WM_IME_STARTCOMPOSITION = 0x010D
WM_IME_ENDCOMPOSITION = 0x010E


class SpyLineEdit:
    pass


def report(tag, pop):
    hwnd = int(pop.winId())
    ex = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    fl = pop.windowFlags()
    print("---- %s ----" % tag)
    print("  flags        :", hex(int(fl)) if hasattr(int, "__call__") else fl)
    print("  Qt.Popup     :", bool(fl & Qt.Popup),
          " Qt.Tool:", bool(fl & Qt.Tool),
          " Frameless:", bool(fl & Qt.FramelessWindowHint))
    print("  EXSTYLE      : 0x%08x  NOACTIVATE=%s TOOLWINDOW=%s TOPMOST=%s"
          % (ex, bool(ex & WS_EX_NOACTIVATE), bool(ex & WS_EX_TOOLWINDOW),
             bool(ex & WS_EX_TOPMOST)))
    print("  isActiveWindow:", pop.isActiveWindow())
    print("  app.activeWin :", type(app.activeWindow()).__name__ if app.activeWindow() else None)
    print("  app.focusWgt  :", type(app.focusWidget()).__name__ if app.focusWidget() else None)
    print("  edit hasFocus :", None if pop.edit is None else pop.edit.hasFocus())
    return hwnd


pop = ui_home.ColumnFilterPopup("title", "标题")
pop.show()
app.processEvents()
hwnd = report("show() 之后", pop)

# ---- IME 链路探测：往这个 HWND 投一条「开始组字」 ----
class Probe(QApplication):
    pass


got = {"ime": 0}


class Watcher:
    pass


orig = pop.edit.inputMethodEvent


def _spy(ev):
    got["ime"] += 1
    print("    ★ inputMethodEvent 收到：preedit=%r commit=%r"
          % (ev.preeditString(), ev.commitString()))
    orig(ev)


pop.edit.inputMethodEvent = _spy
pop.edit.setFocus()
pop.edit.setAttribute(Qt.WA_InputMethodEnabled, True)
app.processEvents()

u32.PostMessageW(hwnd, WM_IME_STARTCOMPOSITION, 0, 0)
for _ in range(6):
    app.processEvents()
u32.PostMessageW(hwnd, WM_IME_ENDCOMPOSITION, 0, 0)
for _ in range(6):
    app.processEvents()
print("  IME 链路：inputMethodEvent 次数 =", got["ime"])

# ---- 再试一次「激活它」看能不能救 ----
pop.activateWindow()
pop.edit.setFocus()
app.processEvents()
report("activateWindow() 之后", pop)

# ---- 键盘能不能进 ----
pop.edit.setText("")
from PySide6.QtTest import QTest                        # noqa: E402
QTest.keyClicks(pop.edit, "abc")
app.processEvents()
print("  QTest 打字结果:", repr(pop.edit.text()))
print("  Qt 平台输入上下文:", type(QGuiApplication.inputMethod()).__name__)

pop.close()
print("DONE")
