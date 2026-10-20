# -*- coding: utf-8 -*-
"""v1.40.15 真机探针：弹层到底有没有「系统标题栏」（非客户区高度 + Win32 样式）
============================================================================
离屏冒烟只能断言 Qt 层旗标，无法证明 Windows **实际**画了多少非客户区。
本探针用**真实 windows 平台插件**建窗，测量：

  · Win32 窗口样式位：WS_CAPTION / WS_SYSMENU / WS_THICKFRAME
  · **非客户区高度 = GetWindowRect 高 − GetClientRect 高**（有标题栏时约 +30px）

对照三种写法：
  C) `QDialog` 默认（Qt.Dialog）                       → 应当**有**标题栏（校验测量方法有效）
  A) `setWindowFlag(Qt.Popup)`                          → v1.40.13/14 旧写法
  B) `setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)`→ v1.40.15 新写法
  D) ui_hero.PersonSearchDialog 本体                    → v1.40.15 实际交付物

跑法（务必用 E 盘绝对路径；**不要**设 QT_QPA_PLATFORM=offscreen）：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/probe_popup_frame.py"
"""
import os
import sys
import ctypes

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ.pop("QT_QPA_PLATFORM", None)      # 用真实 windows 平台
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt

GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


_u = ctypes.windll.user32


def _style(hwnd):
    try:
        return int(_u.GetWindowLongPtrW(hwnd, GWL_STYLE))
    except Exception:
        return int(_u.GetWindowLongW(hwnd, GWL_STYLE))


def measure(widget):
    """返回 (style, nc_height, data) —— 不跑事件循环，避免 Popup 因失焦自动关。"""
    widget.show()
    hwnd = int(widget.winId())
    if not hwnd:
        widget.hide()
        return None
    st = _style(hwnd)
    wr, cr = RECT(), RECT()
    _u.GetWindowRect(hwnd, ctypes.byref(wr))
    _u.GetClientRect(hwnd, ctypes.byref(cr))
    nc_h = (wr.bottom - wr.top) - (cr.bottom - cr.top)
    cls = ctypes.create_unicode_buffer(256)
    _u.GetClassNameW(hwnd, cls, 256)
    widget.hide()
    return {"style": st, "nc_h": nc_h, "cls": cls.value,
            "caption": bool(st & WS_CAPTION), "sysmenu": bool(st & WS_SYSMENU)}


def report(label, m):
    if m is None:
        print("[%s] 拿不到 HWND" % label)
        return m
    print("[%s] class=%-14s style=0x%08X  WS_CAPTION=%-5s WS_SYSMENU=%-5s  非客户区高=%dpx"
          % (label, m["cls"], m["style"], m["caption"], m["sysmenu"], m["nc_h"]))
    return m


app = QApplication([])

print("=" * 78)
print("C 基线：QDialog 默认（Qt.Dialog）—— 校验测量方法（应约 +30px 标题栏）")
print("=" * 78)
c = report("C 默认Dialog", measure(QDialog()))

print()
print("=" * 78)
print("A 旧写法：QDialog.setWindowFlag(Qt.Popup)")
print("=" * 78)
_da = QDialog()
_da.setWindowFlags(Qt.Popup)
_da.setWindowTitle("替换「未知演员」")
_da.resize(380, 240)
a = report("A 旧-仅Popup", measure(_da))

print()
print("=" * 78)
print("B v1.40.15 写法：Qt.Popup | Qt.FramelessWindowHint")
print("=" * 78)
_db = QDialog()
_db.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
_db.setWindowTitle("替换「未知演员」")
_db.resize(380, 240)
b = report("B 新-无边框", measure(_db))

print()
print("=" * 78)
print("D 实际交付物：ui_hero.PersonSearchDialog")
print("=" * 78)
try:
    import ui_hero as uh
    _dd = uh.PersonSearchDialog(initial=None, old_name="未知演员", on_pick=lambda p: None)
    d = report("D 本体", measure(_dd))
except Exception as e:
    print("[D 本体] 构建失败：", e)
    d = None

print()
print("=" * 78)
print("F 根因复刻：QDialog.setWindowFlag(Qt.Popup)（**单数** = 按位或，非替换类型）")
print("=" * 78)
_df = QDialog()
_df.setWindowFlag(Qt.Popup)          # v1.40.13/14 的写法
_df.setWindowTitle("替换「未知演员」")
_df.resize(380, 240)
f = report("F 旧-单数Popup", measure(_df))
print("     → windowFlags=0x%08X  windowType()=0x%02X（Qt.Popup 应为 0x09，Qt.Tool 为 0x0B）"
      % (int(_df.windowFlags()), int(_df.windowType())))
if f is not None:
    print("     → 非客户区高 %dpx：%s" % (f["nc_h"], "有系统标题栏 ← 就是用户截图那条" if f["nc_h"] > 10 else "无"))

# 对照：**复数** setWindowFlags 才是替换类型
_df2 = QDialog()
_df2.setWindowFlags(Qt.Popup)
print("     对照 setWindowFlags(Qt.Popup)（复数）→ windowType()=0x%02X" % int(_df2.windowType()))

print()
print("=" * 78)
print("E 真实调用路径：ui_hero.PersonSearchDialog + exec()（应用模态，嵌套事件循环内实测）")
print("=" * 78)
try:
    from PySide6.QtCore import QTimer
    _de = uh.PersonSearchDialog(initial=None, old_name="未知演员", on_pick=lambda p: None)

    def _probe_in_exec():
        hwnd = int(_de.winId())
        st = _style(hwnd)
        wr, cr = RECT(), RECT()
        _u.GetWindowRect(hwnd, ctypes.byref(wr))
        _u.GetClientRect(hwnd, ctypes.byref(cr))
        nc_h = (wr.bottom - wr.top) - (cr.bottom - cr.top)
        cls = ctypes.create_unicode_buffer(256)
        _u.GetClassNameW(hwnd, cls, 256)
        print("[E exec()]   class=%-14s style=0x%08X  WS_CAPTION=%-5s WS_SYSMENU=%-5s  非客户区高=%dpx"
              % (cls.value, st, bool(st & WS_CAPTION), bool(st & WS_SYSMENU), nc_h))
        _de.reject()

    QTimer.singleShot(350, _probe_in_exec)
    _de.exec()
except Exception as e:
    print("[E exec()] 失败：", e)

print()
print("=" * 78)
print("结论")
print("=" * 78)
if c is None:
    print("[SKIP] 测量方法不可用（非 Windows？）")
    sys.exit(0)
print("基线 C 非客户区高 = %dpx（%s）" % (c["nc_h"], "有标题栏，测量有效" if c["nc_h"] > 10 else "竟然无标题栏，测量可疑"))
for nm, m in (("A 旧", a), ("B 新", b), ("D 本体", d)):
    if m is None:
        continue
    tag = "有标题栏" if m["nc_h"] > 10 else "无标题栏"
    print("  %s：非客户区高=%dpx → %s（WS_CAPTION=%s）" % (nm, m["nc_h"], tag, m["caption"]))
print("=" * 78)
