# -*- coding: utf-8 -*-
"""真机探针：只盯「演员库」一页，等足够久再抓帧，统计内容区亮像素密度。

背景：v1.23.0 真机验收里 19_recent / 20_actors 两张图只有**头部 71~204 行**不同，
      下面内容区完全相同 → 怀疑抓到「卡片还没画出来」的帧。
      本脚本点开演员库后**等 12 秒**（LazyGrid 分批渲染需要时间），连拍多帧取最亮的一帧再判定。
"""
import ctypes
import os
import subprocess
import sys
import time

from ctypes import wintypes as wt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots")
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_actors.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

u32 = ctypes.windll.user32
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def wpid(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def wtitle(h):
    n = u32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def pids_of_exe(exe_name):
    """按**镜像名**收集 pid。

    坑：PyInstaller onefile 的 GUI 跑在**子进程**里（父进程只是 bootloader，
        只有一个 'PyInstaller Onefile Hidden Window'），只认 Popen 拿到的 pid 永远找不到主窗口。
    """
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=15).stdout or b""
    res = set()
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == exe_name and parts[1].isdigit():
            res.add(int(parts[1]))
    return res


def find_window(pid, timeout=60, exe_name=None):
    """按 pid 找可见顶层窗口；找不到就把该 pid 下所有窗口打出来便于诊断。

    坑：别用标题过滤 —— 单文件 exe 启动慢，首帧标题可能还没设好，
        直接判 pid + 可见即可（与 live_verify 的 find_window 一致）。
    """
    hits = []
    diag = []

    def cb(h, _):
        if wpid(h) in watch:
            vis = u32.IsWindowVisible(h)
            diag.append((h, wtitle(h), vis))
            if vis and "PyInstaller" not in wtitle(h):
                hits.append(h)
        return True

    for _ in range(int(timeout / 0.5)):
        hits.clear()
        diag.clear()
        watch = {pid}
        if exe_name:
            watch |= pids_of_exe(exe_name)
        u32.EnumWindows(EnumWindowsProc(cb), 0)
        if hits:
            return hits[0]
        time.sleep(0.5)
    print("[诊断] 监视 pid=%s 下的窗口: %s" % (sorted(watch), diag))
    return None


def click(h, x, y):
    lp = (y << 16) | x
    u32.SendMessageW(h, WM_LBUTTONDOWN, 1, lp)
    u32.SendMessageW(h, WM_LBUTTONUP, 0, lp)


def main():
    import glob
    exe = sorted(glob.glob(os.path.join(ROOT, "流明盒-v*.exe"))
                 + glob.glob(os.path.join(ROOT, "本地影视中心-v*.exe")),
                 key=os.path.getmtime)[-1]
    print("[EXE]", exe)
    proc = subprocess.Popen([exe], close_fds=True)
    hwnd = find_window(proc.pid, exe_name=os.path.basename(exe).lower())
    if not hwnd:
        print("[失败] 未发现主窗口")
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        return 1
    print("[窗口] hwnd=%s title=%r" % (hwnd, wtitle(hwnd)))
    u32.ShowWindow(hwnd, 9)
    u32.SetForegroundWindow(hwnd)
    time.sleep(3.0)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    os.makedirs(SHOT_DIR, exist_ok=True)

    # 用法：python _probe_live_actors.py [侧栏y] [页面名]，默认 354 / 演员库
    y_click = int(sys.argv[1]) if len(sys.argv) > 1 else 354
    page = sys.argv[2] if len(sys.argv) > 2 else "演员库"
    tag = sys.argv[3] if len(sys.argv) > 3 else "actors"
    click(hwnd, 60, y_click)
    print("[点击] %s @(60,%d)" % (page, y_click))
    time.sleep(12.0)               # 等 LazyGrid 分批渲染完

    best, best_n = None, -1
    for i in range(8):
        app.processEvents()
        pm = app.primaryScreen().grabWindow(hwnd)
        if pm.width() <= 1:
            time.sleep(0.5)
            continue
        out = os.path.join(SHOT_DIR, "_probe_%s_%d.png" % (tag, i))
        pm.save(out)
        from PIL import Image
        im = Image.open(out).convert("L")
        px = im.load()
        # 只统计内容区（排除左侧栏与顶部 210px 头部）
        n = 0
        for y in range(220, 1080, 3):
            for x in range(200, 1900, 3):
                if px[x, y] > 60:
                    n += 1
        print("  帧%d 内容区亮像素=%d" % (i, n))
        if n > best_n:
            best, best_n = out, n
        time.sleep(0.6)
    print("[最佳帧]", best, "亮像素=", best_n)
    print("[判定]", "演员墙有内容 ✅" if best_n > 3000 else "内容区近乎空白 ❌")

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
