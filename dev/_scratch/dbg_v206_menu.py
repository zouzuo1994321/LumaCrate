# -*- coding: utf-8 -*-
"""调参用：把「重复检测 → 删除…」弹出的顶层小窗都列出来（类名/尺寸/标题/样式），
再逐个试点击，看哪一个能点出确认框。用完即弃。
"""
import ctypes
import ctypes.wintypes
import os
import subprocess
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v206b")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"
_out, _err = sys.stdout, sys.stderr
import live_verify as lv          # noqa: E402
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication      # noqa: E402

os.environ["LMC_CONFIG"] = os.path.join(TEMP, "settings.json")
exe = os.path.join(TEMP, "LMC-probe-2611010127.exe")
EXE_NAME = os.path.basename(exe).lower()
app = QApplication.instance() or QApplication([])
u32 = lv.u32

COORDS = __import__("json").load(open(lv.COORDS, encoding="utf-8"))
TOOLS = tuple(COORDS["main_settings_btn"])
DD_NAV = (72, 404)
DD_START = (1234, 255)
DD_DEL = (482, 774)
DD_TREE = (192, 435, 1086, 320)


def cls_of(h):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(h, buf, 256)
    return buf.value


def rect_of(h):
    r = ctypes.wintypes.RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def style_of(h):
    GWL_EXSTYLE = -20
    ex = u32.GetWindowLongW(h, GWL_EXSTYLE)
    return hex(ex & 0xFFFFFFFF)


def list_win(exclude=()):
    pids = lv.pids_of_exe(EXE_NAME)
    out = []

    def cb(h, _):
        if h in exclude or not u32.IsWindowVisible(h):
            return True
        if lv.wpid(h) not in pids:
            return True
        _x, _y, w, hh = rect_of(h)
        if w >= 80 and hh >= 20:
            out.append((h, w, hh, lv.wtitle(h), cls_of(h), style_of(h)))
        return True

    u32.EnumWindows(lv.EnumWindowsProc(cb), 0)
    return out


subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=120, title_sub="Build")
print("main", hwnd, flush=True)
time.sleep(5)

lv.click(hwnd, TOOLS[0], TOOLS[1])
dlg = lv.find_window_ex(EXE_NAME, [proc.pid], exclude=(hwnd,), timeout=25, title_sub="工具")
print("dlg", dlg, rect_of(dlg), flush=True)
time.sleep(2.6)
lv.click(dlg, DD_NAV[0], DD_NAV[1])
time.sleep(1.6)
lv.click(dlg, DD_START[0], DD_START[1])
time.sleep(6)
tx0, ty0, tw, th = DD_TREE
lv.click(dlg, tx0 + 90, ty0 + 26 + 14)
time.sleep(0.5)
u32.PostMessageW(dlg, lv.WM_KEYDOWN, 0x28, 0)
time.sleep(0.1)
u32.PostMessageW(dlg, lv.WM_KEYUP, 0x28, 0)
time.sleep(0.8)

lv.click(dlg, DD_DEL[0], DD_DEL[1])
u32.PostMessageW(dlg, lv.WM_MOUSEMOVE, 0, ((5 & 0xFFFF) << 16) | 5)
time.sleep(1.2)
ws = list_win(exclude=(hwnd, dlg))
print("=== 弹窗清单 ===", flush=True)
for w in ws:
    print("  hwnd=%s size=%sx%s title=%r class=%s exstyle=%s"
          % (w[0], w[1], w[2], w[3], w[4], w[5]), flush=True)

for i, w in enumerate(ws):
    print("--- 试第 %d 个 hwnd=%s (%sx%s) ---" % (i, w[0], w[1], w[2]), flush=True)
    before = set(x[0] for x in list_win(exclude=(hwnd, dlg)))
    lv.click(w[0], 60, 16)
    time.sleep(1.8)
    now = list_win(exclude=(hwnd, dlg))
    print("  点后窗口:", [(x[0], "%sx%s" % (x[1], x[2]), x[3], x[4]) for x in now], flush=True)
    new = [x for x in now if x[0] not in before]
    if new:
        print("  新增:", [(x[0], "%sx%s" % (x[1], x[2]), x[3], x[4]) for x in new], flush=True)
        break
    # 重开菜单
    lv.click(dlg, DD_DEL[0], DD_DEL[1])
    u32.PostMessageW(dlg, lv.WM_MOUSEMOVE, 0, ((5 & 0xFFFF) << 16) | 5)
    time.sleep(1.2)

print("=== 关掉 ===", flush=True)
for _w in list_win(exclude=(hwnd, dlg)):
    u32.PostMessageW(_w[0], lv.WM_CLOSE, 0, 0)
    time.sleep(0.6)
u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
time.sleep(1.0)
u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
time.sleep(2)
if proc.poll() is None:
    proc.kill()
print("rc", proc.poll())
