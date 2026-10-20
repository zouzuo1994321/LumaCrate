# -*- coding: utf-8 -*-
"""v1.40.15 真机启动自检：跑真实 exe，确认进程存活且起出顶层窗口，然后清理。
（真实 windows 平台 —— 本版改的是窗口旗标，必须走真实平台才有意义。）
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

sys.stdout = sys.stderr = open(
    r"C:/Users/zouzu/AppData/Local/Temp/exe_selfcheck_v1415.log", "w", encoding="utf-8"
)

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
EXE = os.path.join(ROOT, "流明盒-v1.40.15-2610150078.exe")
EXE_NAME = os.path.basename(EXE).lower()
u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def pids():
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=20).stdout or b""
    res = []
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == EXE_NAME and parts[1].isdigit():
            res.append(int(parts[1]))
    return res


def windows_of(pidset):
    rows = []

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            n = u32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                pid = wt.DWORD()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in pidset:
                    rows.append(buf.value)
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return rows


def main():
    print("[EXE]", EXE, flush=True)
    proc = subprocess.Popen([EXE], close_fds=True, cwd=ROOT)
    print("[Popen pid]", proc.pid, flush=True)
    alive_ok = False
    titles = []
    for i in range(1, 9):
        time.sleep(1.2)
        cur = set(pids())
        titles = windows_of(cur)
        print("t=%.1fs pids=%s poll=%s windows=%s" % (i * 1.2, sorted(cur), proc.poll(), titles),
              flush=True)
        if proc.poll() is None:
            alive_ok = True
    print("存活自检：", "ALIVE_OK" if alive_ok else "DEAD", flush=True)
    print("顶层窗口：", titles, flush=True)
    for pid in pids():
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    print("[清理完成] 残留:", pids(), flush=True)


main()
