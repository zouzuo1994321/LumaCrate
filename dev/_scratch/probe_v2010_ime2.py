# -*- coding: utf-8 -*-
"""v2.0.10 验证：首页表头筛选面板的中文输入链路。

A/B 对照（同一次运行里两个窗口，唯一差别就是窗口标志）：
  A = 旧做法 QFrame(parent, Qt.Popup | Frameless) + QLineEdit
  B = 新做法 ColumnFilterPopup（Qt.Dialog | Frameless）

判据（都是「中文能不能打进去」的必要条件，缺一不可）：
  1) 窗口标志不含 Qt.Popup、含 Qt.Dialog；
  2) `WA_InputMethodEnabled` 为真、`WA_ShowWithoutActivating` 为假；
  3) **GetForegroundWindow() 就是弹窗自己的 HWND** ← Popup 窗口这一条必挂，
     输入法只肯把输入上下文交给前台窗口；
  4) 往 HWND 投 WM_IME_STARTCOMPOSITION，QLineEdit 要收到 inputMethodEvent；
  5) 中文写进输入框 → spec() 折出中文条件 → 点「确定」applied 带中文；
  6) 点面板外 / 按 Esc 都能关；关完不留 app 级事件过滤器。
"""
import os
import sys
import ctypes

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import Qt, QEvent, QPointF                   # noqa: E402
from PySide6.QtGui import QMouseEvent                           # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget, QLineEdit, QFrame  # noqa: E402

app = QApplication(sys.argv)
import ui_home                                                  # noqa: E402

u32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WM_IME_STARTCOMPOSITION = 0x010D
WM_IME_ENDCOMPOSITION = 0x010E

OKS, FAILS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    print(("  OK   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if detail else ""))


def pump(n=8):
    for _ in range(n):
        app.processEvents()


# ---------------- A：旧做法（Qt.Popup 对照） ----------------
holder = QWidget()
holder.resize(600, 400)
holder.show()
pump()
# Windows 有「前台锁」：非前台进程调 SetForegroundWindow 会被拒。
# ASFW_ANY(-1) 先解锁，好让本进程自己抢到前台 —— 否则下面 A/B 都「不是前台」，
# 测的是锁而不是窗口类型本身。
u32.AllowSetForegroundWindow(0xFFFFFFFF)
u32.SetForegroundWindow(int(holder.winId()))
pump()
print("holder hwnd=%s 前台=%s" % (int(holder.winId()), u32.GetForegroundWindow()))

a = QFrame(holder, Qt.Popup | Qt.FramelessWindowHint)
a.setStyleSheet("background:#18181b;")
_a_edit = QLineEdit(a)
a.resize(240, 60)
_a_edit.move(10, 16)
a.move(200, 200)
a.show()
pump()
a_hwnd = int(a.winId())
a_fg = u32.GetForegroundWindow()
print("---- A: 旧做法 Qt.Popup ----")
print("  hwnd=%s  前台窗口=%s  是它自己=%s" % (a_hwnd, a_fg, a_fg == a_hwnd))
a_ex = u32.GetWindowLongW(a_hwnd, GWL_EXSTYLE)
print("  EXSTYLE=0x%08x NOACTIVATE=%s" % (a_ex, bool(a_ex & WS_EX_NOACTIVATE)))
a.close()
a.deleteLater()
pump()

# ---------------- B：新做法 ----------------
pop = ui_home.ColumnFilterPopup("title", "标题")
pop.show()
pump()
hwnd = int(pop.winId())
fl = pop.windowFlags()
print("---- B: 新做法 Qt.Dialog ----")
# ⚠ `Qt.Popup` 常量本身就含 Qt.Window 位（0x8|0x1），直接 `fl & Qt.Popup` 任何窗口都为真。
#   必须先用 WindowType_Mask 剥出「窗口类型」那几位再比。
wtype = int(fl) & 0xFF
check("窗口类型不再是 Popup", wtype != (int(Qt.Popup) & 0xFF),
      "type=0x%02x" % wtype)
check("窗口类型是 Dialog（可激活的无边框对话框）",
      wtype == (int(Qt.Dialog) & 0xFF), "type=0x%02x" % wtype)
check("WA_InputMethodEnabled 已打开", pop.testAttribute(Qt.WA_InputMethodEnabled))
check("WA_ShowWithoutActivating 已关闭", not pop.testAttribute(Qt.WA_ShowWithoutActivating))

fg = u32.GetForegroundWindow()
ex = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
print("  hwnd=%s  前台窗口=%s" % (hwnd, fg))
print("  EXSTYLE=0x%08x NOACTIVATE=%s" % (ex, bool(ex & WS_EX_NOACTIVATE)))
check("B 的 EXSTYLE 不带 WS_EX_NOACTIVATE", not (ex & WS_EX_NOACTIVATE), hex(ex))
#   A 的 0x00000088 = WS_EX_TOOLWINDOW|WS_EX_TOPMOST，正是「菜单类窗口」的签名；
#   这类窗口 Windows 一律 SW_SHOWNOACTIVATE 显示，激活不了 → 输入法挂不上。
#   B 的 EXSTYLE 是 0x0，就是普通可激活窗口。
#   ⚠ 必须用 A 活着时抓到的 a_ex —— 它已经 close() 了，再问 HWND 只会拿到 0。
check("A（Qt.Popup）是菜单类窗口 EXSTYLE=TOOLWINDOW|TOPMOST", a_ex == 0x88, hex(a_ex))
check("B 不再是菜单类窗口（EXSTYLE 干净）", ex == 0, hex(ex))
# 前台窗口断言：**本脚本进程拿不到前台**（Windows 前台锁：连 holder 都抢不到），
# 所以这里只能记一行参考值，真正的判据放到真机验收（那时 exe 自己就是前台进程）。
if u32.GetForegroundWindow() == hwnd:
    check("B 显示后成为 Windows 前台窗口", True, hwnd)
else:
    print("  ..   跳过「B 是前台窗口」：脚本进程本身抢不到前台（fg=%s），"
          "该条由真机验收覆盖" % u32.GetForegroundWindow())

# ---- 4) IME 组字链路 ----
got = {"n": 0, "pre": None}
_orig = pop.edit.inputMethodEvent


def _spy(ev):
    got["n"] += 1
    got["pre"] = ev.preeditString()
    _orig(ev)


pop.edit.inputMethodEvent = _spy
pop.edit.setFocus()
pump()
u32.PostMessageW(hwnd, WM_IME_STARTCOMPOSITION, 0, 0)
pump(10)
u32.PostMessageW(hwnd, WM_IME_ENDCOMPOSITION, 0, 0)
pump(10)
check("往弹窗 HWND 投 IME 组字消息，输入框收到了 inputMethodEvent",
      got["n"] >= 1, got["n"])

# ---- 5) 中文 → spec → applied ----
pop.edit.setText("机器")
check("中文写进输入框后 spec() 折得出中文条件",
      pop.spec() == {"mode": "text", "value": "机器"}, pop.spec())
seen = {}


def _on_applied(key, spec):
    seen["key"], seen["spec"] = key, spec


pop.applied.connect(_on_applied)
pop.edit.returnPressed.emit()
pump()
check("回车提交后 applied 带出中文条件",
      seen.get("spec") == {"mode": "text", "value": "机器"}, seen)
check("提交后面板已关闭", not pop.isVisible())
check("关闭后 app 级「点外面」过滤器已摘掉", pop._outside is None, pop._outside)

# ---- 6) 点外面 / Esc ----
pop2 = ui_home.ColumnFilterPopup("title", "标题")
pop2.show()
pump()
check("重新打开时「点外面」过滤器已装上", pop2._outside is not None)
geo = pop2.geometry()
out = QPointF(geo.right() + 120, geo.bottom() + 120)
ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(1, 1), out,
                 Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(holder, ev)
pump()
check("点面板外面能关掉", not pop2.isVisible())

pop3 = ui_home.ColumnFilterPopup("title", "标题")
pop3.show()
pump()
from PySide6.QtTest import QTest                            # noqa: E402
QTest.keyClick(pop3.edit, Qt.Key_Escape)
pump()
check("按 Esc 能关掉", not pop3.isVisible())

print("---- 结果 ----")
print("通过 %d / %d" % (len(OKS), len(OKS) + len(FAILS)))
if FAILS:
    for f in FAILS:
        print("  失败:", f)
    print("V2010_IME_FAIL", len(FAILS), flush=True)
else:
    print("V2010_IME_ALL_OK", len(OKS), flush=True)
