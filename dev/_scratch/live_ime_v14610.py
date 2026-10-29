# -*- coding: utf-8 -*-
"""v1.46.10 真机验证：右键搜索弹层能不能被「激活」（输入法能不能挂上的前提）。

离屏看不到这个 —— 输入法依赖 Windows 前台窗口的输入上下文，所以必须真跑。
对照组：老写法 Qt.Popup（不激活） vs 新写法 Qt.Dialog + FramelessWindowHint。
判据：GetForegroundWindow() 是否等于弹层自己的 HWND + ImmGetContext 能否取到输入上下文。
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/live_v14610"
os.makedirs(TMP, exist_ok=True)
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMainWindow, QVBoxLayout, QWidget

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import config as cfg
import applog

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import main_window as mw
import ui_hero

mw.load_style(app)

u32 = ctypes.windll.user32
imm32 = ctypes.windll.imm32
u32.GetForegroundWindow.restype = wt.HWND
imm32.ImmGetContext.argtypes = [wt.HWND]
imm32.ImmGetContext.restype = ctypes.c_void_p
imm32.ImmReleaseContext.argtypes = [wt.HWND, ctypes.c_void_p]

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


def _as_int(v):
    """ctypes 在不同 Python/版本下可能把 HWND 回成 int 或 bytes，统一成 int。"""
    if isinstance(v, bytes):
        return int.from_bytes(v[:8].ljust(8, b"\x00"), "little")
    return int(v or 0)


def fg_hwnd():
    return _as_int(u32.GetForegroundWindow())

FAILS = []


def check(name, ok, detail=""):
    print(("[OK]   " if ok else "[FAIL] ") + name + ("  " + str(detail) if detail else ""),
          flush=True)
    if not ok:
        FAILS.append(name)


def settle(ms=800):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def hwnd_of(w):
    return int(w.winId())


def probe(w, label):
    hw = hwnd_of(w)
    fg = fg_hwnd()
    ex = u32.GetWindowLongW(wt.HWND(hw), GWL_EXSTYLE)
    ctx = imm32.ImmGetContext(wt.HWND(hw))
    if ctx:
        imm32.ImmReleaseContext(wt.HWND(hw), ctx)
    geo = w.geometry()
    print("  %s: hwnd=%s fg=%s ex=0x%08x imm=%s geo=%s" %
          (label, hw, fg, ex & 0xFFFFFFFF, bool(ctx), geo), flush=True)
    return fg == hw, bool(ctx), (ex & WS_EX_NOACTIVATE) != 0


# ---- 宿主窗口（模拟主程序）----
win = QMainWindow()
body = QWidget()
lay = QVBoxLayout(body)
lay.addWidget(QLabel("宿主窗口：模拟详情页"))
win.setCentralWidget(body)
win.resize(1200, 800)
win.show()
u32.SetForegroundWindow(hwnd_of(win))
settle(600)
check("宿主窗口自己先成为前台", fg_hwnd() == int(hwnd_of(win)),
      fg_hwnd())

# ---- 对照组：老写法 Qt.Popup ----
old = QDialog(win)
old.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
old.resize(420, 300)
old.move(win.geometry().x() + 200, win.geometry().y() + 200)
ed_old = QWidget(old)          # 占位，不需要交互
old.show()
settle(700)
old_active, old_imm, old_noact = probe(old, "对照组 Qt.Popup        ")
check("对照组（Qt.Popup）确实不会被激活 —— 这就是输入法失灵的根因",
      not old_active, "active=%s" % old_active)
old.close()
settle(300)

# ---- 实验组：新写法（真控件本体）----
dlg = ui_hero.PersonSearchDialog(initial="", old_name="八森わかな", parent=win)
dlg.move_to(QPoint(win.geometry().x() + 420, win.geometry().y() + 260))
dlg.show()
settle(900)
new_active, new_imm, new_noact = probe(dlg, "实验组 新 PersonSearchDialog")
check("新弹层真的拿到了前台（输入法可挂上）", new_active, "active=%s" % new_active)
check("新弹层不是 WS_EX_NOACTIVATE", not new_noact)
check("新弹层能取到 IME 输入上下文（ImmGetContext 非空）", new_imm)
check("输入框有焦点", dlg._edit.hasFocus())
check("输入框接受输入法事件", dlg._edit.testAttribute(Qt.WA_InputMethodEnabled))

# 用户视角：弹层面板真画出来了
img = dlg.grab()
img.save(os.path.join(TMP, "person_search_dialog.png"))
print("  截图:", os.path.join(TMP, "person_search_dialog.png"), img.size(), flush=True)

# 中文确实能进输入框：走 Qt 的输入法事件通道（IME 提交时就是这条路径）
from PySide6.QtGui import QInputMethodEvent
ev = QInputMethodEvent("", [])
ev.setCommitString("三上悠亜")
app.sendEvent(dlg._edit, ev)
settle(200)
check("输入法提交串能进输入框（commitString 生效）",
      "三上悠亜" in dlg._edit.text(), repr(dlg._edit.text()))

# 关掉后前台应回到宿主窗口
dlg.reject()
settle(400)
check("关闭后前台交还宿主窗口", fg_hwnd() == int(hwnd_of(win)),
      fg_hwnd())

win.close()
print("FAILS:", FAILS, flush=True)
print("LIVE_IME_V14610_DONE", flush=True)
