# -*- coding: utf-8 -*-
"""v2.0.10 现场取证：点表头漏斗之后，进程里到底多了什么窗口？

不预设任何尺寸/类名过滤，全量 dump；再抓一张点完之后的整窗截图。
"""
import ctypes
import ctypes.wintypes
import os
import subprocess
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA"), "Temp", "lmc_exe_v2010")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["LMC_NO_SYSMON"] = "1"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv          # noqa: E402
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication          # noqa: E402
from PySide6.QtGui import QImage                    # noqa: E402
from PIL import Image                               # noqa: E402

u32 = lv.u32
EXE = os.path.join(TEMP, "LMC-probe-2611050131.exe")
EXE_NAME = os.path.basename(EXE).lower()
print("exe:", EXE, os.path.exists(EXE))


def screen_of(win, x, y):
    pt = ctypes.wintypes.POINT(int(x), int(y))
    u32.ClientToScreen(ctypes.wintypes.HWND(win), ctypes.byref(pt))
    return pt.x, pt.y


def dump_quiet(pid):
    """只返回 (hwnd, w, h, cls, txt, ex)，不打印。"""
    rows = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def _cb(h, _l):
        q = ctypes.wintypes.DWORD()
        u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(h), ctypes.byref(q))
        if q.value != pid or not u32.IsWindowVisible(h):
            return True
        rc = ctypes.wintypes.RECT()
        u32.GetWindowRect(ctypes.wintypes.HWND(h), ctypes.byref(rc))
        cls = ctypes.create_unicode_buffer(96)
        u32.GetClassNameW(ctypes.wintypes.HWND(h), cls, 96)
        txt = ctypes.create_unicode_buffer(128)
        u32.GetWindowTextW(ctypes.wintypes.HWND(h), txt, 128)
        rows.append((int(h), rc.right - rc.left, rc.bottom - rc.top, cls.value,
                     txt.value, hex(u32.GetWindowLongW(ctypes.wintypes.HWND(h), -20))))
        return True

    u32.EnumWindows(_cb, 0)
    return rows


def dump(pid, tag):
    rows = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def _cb(h, _l):
        q = ctypes.wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(q))
        if q.value != pid:
            return True
        if not u32.IsWindowVisible(h):
            return True
        rc = ctypes.wintypes.RECT()
        u32.GetWindowRect(h, ctypes.byref(rc))
        cls = ctypes.create_unicode_buffer(96)
        u32.GetClassNameW(h, cls, 96)
        txt = ctypes.create_unicode_buffer(128)
        u32.GetWindowTextW(h, txt, 128)
        ex = u32.GetWindowLongW(h, -20)
        rows.append((int(h), rc.right - rc.left, rc.bottom - rc.top,
                     cls.value, txt.value, hex(ex)))
        return True

    u32.EnumWindows(_cb, 0)
    print("---- %s：%d 个可见顶层窗口 ----" % (tag, len(rows)))
    for r in rows:
        print("   hwnd=%-9s %4dx%-4d %-34s ex=%-10s %r" % r)
    return rows


app = QApplication.instance() or QApplication(sys.argv)
subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
time.sleep(0.8)
proc = subprocess.Popen([EXE], cwd=TEMP, env=dict(os.environ))
print("pid:", proc.pid)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=120, title_sub="Build")
print("main hwnd:", hwnd)
time.sleep(4.5)


def pid_of(h):
    """⚠ PyInstaller onefile 会再 fork 一个子进程跑真正的 app —— 窗口属于**子进程**，
    按 `proc.pid`（bootloader）枚举永远是 0 个窗口。必须问主窗自己。"""
    q = ctypes.wintypes.DWORD()
    u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(h), ctypes.byref(q))
    return q.value


APP_PID = pid_of(hwnd)
print("bootloader pid=%s  真正跑 UI 的 pid=%s" % (proc.pid, APP_PID))

import json
CO = json.load(open(os.path.join(os.environ["LOCALAPPDATA"], "Temp",
                                 "lmc_coords_v208.json"), encoding="utf-8"))
col = [c for c in CO["header"]["cols"] if c["key"] == "title"][0]
fx, fy = col["funnel"]
print("标题列 funnel =", fx, fy, " 列宽", col["w"], " 表 x0 =", CO["header"]["x0"])
dump(APP_PID, "启动后")

def force_foreground(h):
    """把窗口抢到前台。

    ⚠ 光 `SetForegroundWindow` 在本机被「前台锁」拒掉（脚本进程不是前台进程），
    窗口一直不上前台 → 那一下点击会被 Qt 当成「点击激活窗口」吞掉，
    表头连 hover 都收不到（图里一个漏斗图标都不画），更别说弹出面板。
    `AttachThreadInput` 把本线程挂到当前前台线程上，借它的权限切前台。
    """
    h_int = int(h)
    h = ctypes.wintypes.HWND(h_int)
    fg = u32.GetForegroundWindow()
    fg = ctypes.wintypes.HWND(fg) if fg else None
    tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
    tid_fg = u32.GetWindowThreadProcessId(fg, None) if fg else 0
    ok_att = False
    if tid_fg and tid_fg != tid_me:
        ok_att = bool(u32.AttachThreadInput(tid_me, tid_fg, True))
    u32.BringWindowToTop(h)
    u32.SetForegroundWindow(h)
    u32.SetFocus(h)
    if ok_att:
        u32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.35)
    return u32.GetForegroundWindow() == h_int


u32.SetForegroundWindow(hwnd)
print("抢前台：", force_foreground(hwnd), " 前台 =", u32.GetForegroundWindow(), "主窗 =", hwnd)
sx, sy = screen_of(hwnd, fx, fy)
print("set cursor ->", sx, sy)
u32.SetCursorPos(int(sx), int(sy))
time.sleep(0.9)

pm = lv.grab(app, hwnd, tries=20, gap=0.4, settle=4)
if pm is not None:
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    Image.frombytes("RGB", (img.width(), img.height()), bytes(img.constBits()),
                    "raw", "BGRX").save(os.path.join(SHOTS, "v2010_probe_hover.png"))
    print("hover 截图 OK")

u32.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.05)
u32.mouse_event(0x0004, 0, 0, 0, 0)
# ★ 每 100ms 采一次，看弹窗是「压根没出现」还是「出现后立刻被关掉」
seen = None
for _i in range(24):
    time.sleep(0.1)
    rows = dump_quiet(APP_PID)
    if len(rows) > 1:
        if seen is None:
            seen = _i
            print("  [%4dms] 多出窗口：" % (_i * 100), rows[1:])
            pm = lv.grab(app, rows[1][0], tries=10, gap=0.2, settle=2)
            if pm is not None:
                img = pm.toImage().convertToFormat(QImage.Format_RGB32)
                Image.frombytes("RGB", (img.width(), img.height()),
                                bytes(img.constBits()), "raw", "BGRX").save(
                    os.path.join(SHOTS, "v2010_probe_popup_first.png"))
                print("  [%4dms] 弹窗首帧已存" % (_i * 100))
    elif seen is not None:
        print("  [%4dms] 弹窗消失了（存活约 %dms）" % (_i * 100, (_i - seen) * 100))
        seen = -1
print("弹窗出现过？", seen is not None and seen >= 0)
dump(APP_PID, "点击漏斗之后")
print("前台窗口 =", u32.GetForegroundWindow())

pm = lv.grab(app, hwnd, tries=20, gap=0.4, settle=4)
if pm is not None:
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    Image.frombytes("RGB", (img.width(), img.height()), bytes(img.constBits()),
                    "raw", "BGRX").save(os.path.join(SHOTS, "v2010_probe_after.png"))
    print("after 截图 OK")

time.sleep(0.5)
u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
time.sleep(1.2)
subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
print("DONE")
