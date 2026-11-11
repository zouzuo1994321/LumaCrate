# -*- coding: utf-8 -*-
"""v2.0.14 诊断：右键搜索框之后，进程里到底有没有多出一个菜单窗口？

真机验收里「右键弹出菜单」判 FAIL，但同一套 `editfix` 在进程内的探针
（`probe_v2014_verify.py`，真 windows 平台）是全绿的 —— 所以要么输入没送进去，
要么菜单弹了而找法不对。这个脚本把每一步的**全部顶层窗口**打出来，不再猜。

输出四段：启动后 / 左键点搜索框后 / 右键后 0.3s / 右键后 1.2s。
每段列 hwnd、尺寸、Win32 类名、EXSTYLE、是否可见。
"""
import ctypes
import ctypes.wintypes
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_diag_v2014")
COORDS_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                           "Temp", "lmc_coords_v208.json")
sys.path.insert(0, DEV)
os.environ["LMC_NO_SYSMON"] = "1"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv        # noqa: E402
sys.stdout, sys.stderr = _out, _err

u32 = lv.u32
CHECK = os.path.join(ROOT, "流明盒-v2.0.14-2611110135.exe")
os.makedirs(TEMP, exist_ok=True)
exe = os.path.join(TEMP, "LMC-diag.exe")
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(CHECK):
    shutil.copy2(CHECK, exe)
EXE_NAME = os.path.basename(exe).lower()

LIB = os.path.join(TEMP, "lib")
os.makedirs(os.path.join(LIB, "A", "X"), exist_ok=True)
CFG = os.path.join(TEMP, "settings.json")
with open(CFG, "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "诊断库", "kind": "电影", "paths": [LIB], "filter": {}},
                             ],
               "appearance": {"accent": "#e4587c", "mode": "磨砂玻璃", "level": "低"}},
              f, ensure_ascii=False)

# 坐标
env = dict(os.environ)
env["LMC_CONFIG"] = CFG
env["QT_QPA_PLATFORM"] = "offscreen"
subprocess.run([sys.executable, "-c",
                "import runpy; runpy.run_path(r'%s', run_name='__main__')"
                % os.path.join(DEV, "_scratch", "coords_v208.py")],
               env=env, capture_output=True, text=True, encoding="utf-8",
               errors="replace", cwd=DEV)
CO = json.load(open(COORDS_JSON, encoding="utf-8"))
SCX, SCY, SW, SH = CO["search"]
print("搜索框 中心=(%d,%d) 尺寸=%dx%d" % (SCX, SCY, SW, SH), flush=True)


def screen_of(win, x, y):
    pt = ctypes.wintypes.POINT(int(x), int(y))
    u32.ClientToScreen(ctypes.wintypes.HWND(int(win)), ctypes.byref(pt))
    return pt.x, pt.y


def pid_of(h):
    q = ctypes.wintypes.DWORD()
    u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(int(h)), ctypes.byref(q))
    return q.value


def win_class(h):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(ctypes.wintypes.HWND(int(h)), buf, 256)
    return buf.value


def dump(pid, tag):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def _cb(h, _l):
        q = ctypes.wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(q))
        if q.value != pid:
            return True
        rc = ctypes.wintypes.RECT()
        u32.GetWindowRect(h, ctypes.byref(rc))
        w, hh = rc.right - rc.left, rc.bottom - rc.top
        if w < 40 or hh < 20:
            return True
        out.append((int(h), w, hh, win_class(h),
                    u32.GetWindowLongW(h, -20), u32.IsWindowVisible(h)))
        return True

    u32.EnumWindows(_cb, 0)
    print("\n---- %s（%d 个可见候选）----" % (tag, len(out)), flush=True)
    for (h, w, hh, cls, ex, vis) in sorted(out, key=lambda r: -r[1] * r[2]):
        print("  hwnd=%-9s %4dx%-4d class=%-28s ex=0x%08x vis=%s"
              % (h, w, hh, cls, ex, bool(vis)), flush=True)
    return out


def force_foreground(h):
    hw = ctypes.wintypes.HWND(int(h))
    fg = u32.GetForegroundWindow()
    tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
    tid_fg = u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(fg), None) if fg else 0
    ok_att = False
    if tid_fg and tid_fg != tid_me:
        ok_att = bool(u32.AttachThreadInput(tid_me, tid_fg, True))
    u32.BringWindowToTop(hw)
    u32.SetForegroundWindow(hw)
    u32.SetFocus(hw)
    if ok_att:
        u32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.4)
    return u32.GetForegroundWindow() == int(h)


subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
time.sleep(0.8)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
print("启动 pid=", proc.pid, flush=True)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=200, title_sub="Build")
print("主窗 =", hwnd, flush=True)
if not hwnd:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    raise SystemExit(1)
time.sleep(5.0)
APP_PID = pid_of(hwnd)
print("UI pid =", APP_PID, flush=True)

fgok = force_foreground(hwnd)
print("抢前台成功 =", fgok, flush=True)
dump(APP_PID, "启动后")

# 左键点搜索框
sx, sy = screen_of(hwnd, SCX, SCY)
u32.SetCursorPos(int(sx), int(sy))
time.sleep(0.3)
u32.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.06)
u32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(0.8)
dump(APP_PID, "左键点搜索框之后")

# 先试粘贴（顺便验证剪贴板链路）
from PySide6.QtWidgets import QApplication          # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
app.clipboard().setText("机器")
for _ in range(30):
    app.processEvents()
    time.sleep(0.02)
print("\n剪贴板内容 =", repr(app.clipboard().text()), flush=True)
u32.keybd_event(0x11, 0, 0, 0)
u32.keybd_event(0x56, 0, 0, 0)
time.sleep(0.06)
u32.keybd_event(0x56, 0, 2, 0)
u32.keybd_event(0x11, 0, 2, 0)
time.sleep(1.0)
dump(APP_PID, "Ctrl+V 之后")

# 右键
u32.SetCursorPos(int(sx), int(sy))
time.sleep(0.3)
u32.mouse_event(0x0008, 0, 0, 0, 0)
time.sleep(0.09)
u32.mouse_event(0x0010, 0, 0, 0, 0)
time.sleep(0.35)
dump(APP_PID, "右键后 0.3s")
time.sleep(1.0)
dump(APP_PID, "右键后 1.3s")

log = os.path.join(TEMP, "index_data", "logs", "app.log")
if os.path.exists(log):
    print("\n---- app.log ----", flush=True)
    for ln in open(log, encoding="utf-8", errors="replace").read().splitlines():
        print("  ", ln, flush=True)

u32.keybd_event(0x1B, 0, 0, 0)
time.sleep(0.05)
u32.keybd_event(0x1B, 0, 2, 0)
time.sleep(0.5)
subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
print("\nDIAG_DONE", flush=True)
