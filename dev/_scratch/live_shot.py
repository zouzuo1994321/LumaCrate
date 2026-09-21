# -*- coding: utf-8 -*-
"""启动打包好的 exe，按「进程归属」定位其主窗口，截取真实窗口图像，然后关闭该进程。

用途：v1.11.0 卡片修复的真机视觉复核（离屏渲染之外的最后一层验证）。
安全约束：只操作本次启动的进程 PID，绝不做按名字批杀，避免误杀资源管理器等同名窗口。
输出：dev/screenshots/17_live_window.png
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

sys.stdout = sys.stderr = open(
    r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_shot.log", "w", encoding="utf-8"
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXE = os.path.join(ROOT, "本地影视中心-v1.11.0-2609180012.exe")
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots")
OUT_PNG = os.path.join(SHOT_DIR, "17_live_window.png")

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
EXE_NAME = os.path.basename(EXE).lower()

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def _pids_of_exe():
    """当前所有进程名等于 EXE 文件名的 PID 集合（含 onefile 引导器与子进程）。

    注意：tasklist 输出为本地代码页(GBK)，不能按 utf-8 解码，否则抛错。
    """
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=15).stdout or b""
    out = raw.decode("gbk", "replace")
    res = set()
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == EXE_NAME and parts[1].isdigit():
            res.add(int(parts[1]))
    return res


def _window_title(hwnd):
    n = u32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _window_pid(hwnd):
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def find_own_window(extra_pids, timeout=60):
    """在所有可见顶层窗口中，找到属于本 exe 进程族的那个（面积最大者视为主窗口）。

    注意：onefile 下「引导器」与「应用」是两个同名进程，且应用子进程的 pid 在 Popen
    返回之后才出现，所以每轮都要重新采集 PID 集合（tasklist 较慢，故放在循环里做一次）。
    """
    hits = []

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd) and _window_pid(hwnd) in pids_now[0]:
            r = wt.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if w > 200 and h > 200:
                hits.append((w * h, hwnd, _window_title(hwnd)))
        return True

    pids_now = [set(extra_pids)]
    deadline = time.time() + timeout
    while time.time() < deadline:
        pids_now[0] = _pids_of_exe() | set(extra_pids)
        hits.clear()
        u32.EnumWindows(EnumWindowsProc(cb), 0)
        if hits:
            hits.sort(reverse=True)
            return hits[0]
        time.sleep(1)
    return None


def main():
    print("[启动]", EXE, flush=True)
    before = _pids_of_exe()
    print("[既有同名进程]", sorted(before), flush=True)
    proc = subprocess.Popen([EXE], close_fds=True)
    print("[引导器 pid]", proc.pid, flush=True)

    hit = find_own_window({proc.pid})
    if not hit:
        print("[失败] 超时未见属于本 exe 的主窗口", flush=True)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True)
        return 1
    _, hwnd, title = hit
    print(f"[窗口] hwnd={hwnd} pid={_window_pid(hwnd)} title={title!r}", flush=True)

    u32.ShowWindow(hwnd, 9)
    u32.SetForegroundWindow(hwnd)
    time.sleep(2.0)

    rect = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    print(f"[几何] {w}x{h} @ ({rect.left},{rect.top})", flush=True)

    os.makedirs(SHOT_DIR, exist_ok=True)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    pm = app.primaryScreen().grabWindow(hwnd)
    print(f"[抓取] {pm.width()}x{pm.height()}", flush=True)
    print(f"[保存] {OUT_PNG} -> {pm.save(OUT_PNG)}", flush=True)

    # 只关本次启动的引导器（/t 会带走其子进程），不按名字批杀
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    time.sleep(1.5)
    print("[结束] 本次启动的进程已关闭；残留同名进程:", sorted(_pids_of_exe()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
