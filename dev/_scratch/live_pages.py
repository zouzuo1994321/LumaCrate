# -*- coding: utf-8 -*-
"""真机验收：启动打包 exe，点击侧边栏切到「全部 / 演员库」，逐页截图。

用于 v1.11.0 卡片修复的最终真机视觉复核（真实字体、真实渲染管线、真实索引库）。
安全约束：只操作本次启动的进程 PID；不按进程名批杀。
输出：dev/screenshots/18_live_grid.png / 19_live_actors.png（含首页 17_live_window.png）
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

sys.stdout = sys.stderr = open(
    r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_pages.log", "w", encoding="utf-8"
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXE = os.path.join(ROOT, "本地影视中心-v1.11.0-2609180012.exe")
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots")
EXE_NAME = os.path.basename(EXE).lower()

u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202


def pids_of_exe():
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=15).stdout or b""
    res = set()
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == EXE_NAME and parts[1].isdigit():
            res.add(int(parts[1]))
    return res


def wtitle(h):
    n = u32.GetWindowTextLengthW(h)
    if n <= 0:
        return ""
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def wpid(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def find_window(extra, timeout=60):
    hits = []
    pids = [set(extra)]

    def cb(h, _):
        if u32.IsWindowVisible(h) and wpid(h) in pids[0]:
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            w, ht = r.right - r.left, r.bottom - r.top
            if w > 400 and ht > 300:
                hits.append((w * ht, h))
        return True

    t0 = time.time()
    while time.time() - t0 < timeout:
        pids[0] = pids_of_exe() | set(extra)
        hits.clear()
        u32.EnumWindows(EnumWindowsProc(cb), 0)
        if hits:
            hits.sort(reverse=True)
            return hits[0][1]
        time.sleep(1)
    return None


def click(hwnd, x, y):
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    for msg, wp in ((WM_MOUSEMOVE, 0), (WM_LBUTTONDOWN, 1), (WM_LBUTTONUP, 0)):
        u32.PostMessageW(hwnd, msg, wp, lp)
        time.sleep(0.08)


def grab(hwnd, app, path):
    pm = app.primaryScreen().grabWindow(hwnd)
    print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(path)} {pm.save(path)}",
          flush=True)
    return pm.width(), pm.height()


def main():
    print("[启动]", EXE, flush=True)
    proc = subprocess.Popen([EXE], close_fds=True)
    hwnd = find_window({proc.pid})
    if not hwnd:
        print("[失败] 未见主窗口", flush=True)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        return 1
    print(f"[窗口] hwnd={hwnd} pid={wpid(hwnd)} title={wtitle(hwnd)!r}", flush=True)

    u32.ShowWindow(hwnd, 9)
    u32.SetForegroundWindow(hwnd)
    time.sleep(2.5)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    os.makedirs(SHOT_DIR, exist_ok=True)

    # 侧边栏坐标来自 17_live_window.png 的像素扫描（图像即客户区，1:1）：
    # 首页85 最近播放122 我的收藏159 文件夹196 合集233 (分类284) 全部315 演员库352 (媒体库403) 电影434
    pages = [
        ("全部", 60, 315, "18_live_grid.png"),
        ("演员库", 60, 352, "19_live_actors.png"),
        ("首页", 60, 85, "20_live_home.png"),
    ]
    for name, x, y, out in pages:
        print(f"[点击] {name} @({x},{y})", flush=True)
        click(hwnd, x, y)
        time.sleep(4.0)
        grab(hwnd, app, os.path.join(SHOT_DIR, out))

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    time.sleep(1.5)
    print("[结束] 残留同名进程:", sorted(pids_of_exe()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
