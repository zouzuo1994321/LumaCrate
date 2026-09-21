# -*- coding: utf-8 -*-
"""诊断：从 Bash 工具里启动 exe 后，子进程是否存活、是否产生顶层窗口。"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

sys.stdout = sys.stderr = open(
    r"C:/Users/zouzu/AppData/Local/Temp/lmc_diag.log", "w", encoding="utf-8"
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXE = os.path.join(ROOT, "本地影视中心-v1.11.0-2609180012.exe")
EXE_NAME = os.path.basename(EXE).lower()
u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def pids():
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=15).stdout or b""
    res = []
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == EXE_NAME and parts[1].isdigit():
            res.append(int(parts[1]))
    return res


def all_windows():
    rows = []

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            n = u32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                pid = wt.DWORD()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                rows.append((buf.value, pid.value))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return rows


def main():
    print("[EXE]", EXE, flush=True)
    proc = subprocess.Popen([EXE], close_fds=True)
    print("[Popen pid]", proc.pid, flush=True)
    for i in range(1, 16):
        time.sleep(2)
        cur = pids()
        mine = [w for w in all_windows() if w[1] in cur]
        print(f"t={i*2}s pids={cur} poll={proc.poll()} my_windows={mine}", flush=True)
    for pid in pids():
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    print("[清理完成] 残留:", pids(), flush=True)


if __name__ == "__main__":
    main()
