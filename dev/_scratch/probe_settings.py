# -*- coding: utf-8 -*-
"""探针：启动最新 exe，点顶栏「设置」，枚举该 pid 下所有可见顶层窗口，判断设置窗是否真的没开。"""
import ctypes
import ctypes.wintypes as wt
import glob
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202

exe = sorted(glob.glob(os.path.join(ROOT, "流明盒-v*.exe"))
             + glob.glob(os.path.join(ROOT, "本地影视中心-v*.exe")),
             key=os.path.getmtime)[-1]
exe_name = os.path.basename(exe).lower()
print("[EXE]", exe, flush=True)


def pids_of(name):
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, timeout=15).stdout or b""
    out = set()
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == name and parts[1].isdigit():
            out.add(int(parts[1]))
    return out


def wpid(h):
    p = wt.DWORD(); u32.GetWindowThreadProcessId(h, ctypes.byref(p)); return p.value


def wtitle(h):
    n = u32.GetWindowTextLengthW(h)
    if n <= 0:
        return ""
    b = ctypes.create_unicode_buffer(n + 1); u32.GetWindowTextW(h, b, n + 1); return b.value


def dump(pid_set, label):
    print(f"--- {label} ---", flush=True)
    rows = []

    def cb(h, _):
        if wpid(h) in pid_set:
            r = wt.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
            rows.append((h, bool(u32.IsWindowVisible(h)), r.left, r.top,
                         r.right - r.left, r.bottom - r.top, wtitle(h)))
        return True
    u32.EnumWindows(EnumWindowsProc(cb), 0)
    for h, vis, x, y, w, ht, t in rows:
        print(f"  hwnd={h} vis={vis} pos=({x},{y}) size={w}x{ht} title={t!r}", flush=True)
    return rows


proc = subprocess.Popen([exe], close_fds=True)
# 等窗口
hwnd = None
t0 = time.time()
while time.time() - t0 < 60:
    ps = pids_of(exe_name) | {proc.pid}
    hits = []

    def cb(h, _):
        if u32.IsWindowVisible(h) and wpid(h) in ps:
            r = wt.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 400 and r.bottom - r.top > 300:
                hits.append((h, r))
        return True
    u32.EnumWindows(EnumWindowsProc(cb), 0)
    if hits:
        hwnd = hits[0][0]; break
    time.sleep(1)

print("[主窗口]", hwnd, wtitle(hwnd) if hwnd else None, flush=True)
ps = pids_of(exe_name) | {proc.pid}
dump(ps, "点击前")

if hwnd:
    u32.ShowWindow(hwnd, 9); u32.SetForegroundWindow(hwnd); time.sleep(2.5)

    # 与 live_verify 一致：本进程也建一个 QApplication 并 grabWindow 截图
    from PySide6.QtWidgets import QApplication
    qapp = QApplication.instance() or QApplication([])
    qapp.primaryScreen().grabWindow(hwnd).save(os.path.join(os.environ.get("TEMP", "."), "probe_base.png"))
    print("[grab] base ok", flush=True)

    def click(x, y):
        for msg, wp in ((WM_MOUSEMOVE, 0), (WM_LBUTTONDOWN, 1), (WM_LBUTTONUP, 0)):
            lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
            u32.PostMessageW(hwnd, msg, wp, lp); time.sleep(0.08)

    # 复刻 live_verify 的页面点击序列
    for name, (x, y) in (("全部", (60, 315)), ("最近播放", (60, 122)),
                         ("演员库", (60, 352)), ("首页", (60, 85))):
        print(f"[点击] {name} @({x},{y})", flush=True)
        click(x, y); time.sleep(4)

    # 打印主窗口几何，确认客户区尺寸
    r = wt.RECT(); u32.GetWindowRect(hwnd, ctypes.byref(r))
    print(f"[主窗口几何] pos=({r.left},{r.top}) size={r.right - r.left}x{r.bottom - r.top}", flush=True)

    print("[点击] 设置 @(1816,25)", flush=True)
    click(1816, 25)
    time.sleep(6)
    ps = pids_of(exe_name) | {proc.pid}
    dump(ps, "点击后")

subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
time.sleep(1)
print("[结束] 残留:", sorted(pids_of(exe_name)), flush=True)
