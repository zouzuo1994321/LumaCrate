# -*- coding: utf-8 -*-
"""v2.0.14 诊断八：真平台 + 真 MainWindow + **真键击**（Win32 keybd_event）。

诊断七证明「进程内投 QKeyEvent」按钮会显示；真机上真键击却不显示。
本脚本把两者合起来：窗口是真的、键击是真的（走系统消息队列 → 输入法 → Qt），
但状态可以被内省 —— 打印 `text()`、按钮 `isVisible()`、几何、右端亮像素。
这样若真键击那条路确实不刷新按钮，就能当场看到 `text='ZZZ'` 而 `visible=False`。
"""
import ctypes
import ctypes.wintypes
import os
import sys
import tempfile
import time

os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = tempfile.mkdtemp(prefix="lmc_p2014k_")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtCore import QPoint, Qt                     # noqa: E402
from PySide6.QtGui import QFontDatabase                   # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton   # noqa: E402

app = QApplication(sys.argv)
QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")

import database as db          # noqa: E402
import config as cfg           # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP
db.init_db()

import main_window as mw       # noqa: E402

mw.load_style(app)

u32 = ctypes.windll.user32


def pump(n=10, d=0.02):
    for _ in range(n):
        app.processEvents()
        time.sleep(d)


win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(20, 0.03)

hwnd = int(win.winId())


def force_foreground():
    tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
    fg = u32.GetForegroundWindow()
    tid_fg = u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(fg), None) if fg else 0
    if tid_fg and tid_fg != tid_me:
        u32.AttachThreadInput(tid_me, tid_fg, True)
    u32.BringWindowToTop(ctypes.wintypes.HWND(hwnd))
    u32.SetForegroundWindow(ctypes.wintypes.HWND(hwnd))
    u32.SetFocus(ctypes.wintypes.HWND(hwnd))
    if tid_fg and tid_fg != tid_me:
        u32.AttachThreadInput(tid_me, tid_fg, False)
    pump(8)
    return u32.GetForegroundWindow() == hwnd


def click_at(x, y):
    pt = ctypes.wintypes.POINT(int(x), int(y))
    u32.ClientToScreen(ctypes.wintypes.HWND(hwnd), ctypes.byref(pt))
    u32.SetCursorPos(pt.x, pt.y)
    pump(6)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    u32.mouse_event(0x0004, 0, 0, 0, 0)
    pump(10)


def key_tap(vk):
    u32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.06)
    u32.keybd_event(vk, 0, 2, 0)
    pump(4)


print("抢前台 =", force_foreground())
le = win.search
btn = (le.findChildren(QToolButton) or [None])[0]
print("搜索框 geo =", le.geometry().getRect(), " 按钮 =", btn is not None)
c = le.mapTo(win, QPoint(le.width() // 2, le.height() // 2))
print("搜索框中心(窗口坐标) =", (c.x(), c.y()))

click_at(c.x(), c.y())
pump(10)
print("点击后 焦点控件 =", type(app.focusWidget()).__name__,
      " 是搜索框 =", app.focusWidget() is le)


def report(tag):
    n = 0
    if le is not None:
        img = le.grab().toImage()
        for y in range(img.height()):
            for x in range(max(0, img.width() - 46), img.width()):
                if img.pixelColor(x, y).lightness() > 130:
                    n += 1
    print("  %-14s text=%-8r btn.visible=%-5s geom=%s 右端亮像素=%d"
          % (tag, le.text(), (btn.isVisible() if btn else None),
             (btn.geometry().getRect() if btn else None), n), flush=True)


report("真键击前")
for _ in range(3):
    key_tap(0x5A)
pump(30, 0.03)
report("真键击 ZZZ")
time.sleep(0.8)
pump(20, 0.03)
report("再等 0.8s")

# 打中文不行（没有输入法上下文），但可以试一次真实中文粘贴路径之外的
# 「再打一个字符」看是否刷新
key_tap(0x5A)
pump(20, 0.03)
report("再打一个 Z")

win.close()
pump()
print("\nDONE")
