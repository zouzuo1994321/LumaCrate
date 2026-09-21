# -*- coding: utf-8 -*-
"""真机诊断：扫描侧边栏每一行的真实 y，逐行点击并统计内容区亮像素，
定位「哪些页面空白」。不比文字、只看密度，避开 OCR。
"""
import ctypes
import ctypes.wintypes as wt
import glob
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_wall.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"
SHOT = os.path.join(ROOT, "dev", "screenshots_v121_cards")
os.makedirs(SHOT, exist_ok=True)

u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE = 0x0201, 0x0202, 0x0200


def newest_exe():
    cand = sorted(glob.glob(os.path.join(ROOT, "流明盒-v*.exe"))
                  + glob.glob(os.path.join(ROOT, "本地影视中心-v*.exe")),
                  key=os.path.getmtime)
    return cand[-1]


def pids_of_exe(name):
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, timeout=15).stdout or b""
    res = set()
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == name and parts[1].isdigit():
            res.add(int(parts[1]))
    return res


def wpid(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def wtitle(h):
    n = u32.GetWindowTextLengthW(h)
    if n <= 0:
        return ""
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def find_window(name, extra, timeout=60):
    hits, pids = [], [set(extra)]

    def cb(h, _):
        if u32.IsWindowVisible(h) and wpid(h) in pids[0]:
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            if (r.right - r.left) > 400 and (r.bottom - r.top) > 300:
                hits.append(((r.right - r.left) * (r.bottom - r.top), h))
        return True

    t0 = time.time()
    while time.time() - t0 < timeout:
        pids[0] = pids_of_exe(name) | set(extra)
        hits.clear()
        u32.EnumWindows(EnumWindowsProc(cb), 0)
        if hits:
            hits.sort(reverse=True)
            return hits[0][1]
        time.sleep(1)
    return None


def click(h, x, y):
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    for m, w in ((WM_MOUSEMOVE, 0), (WM_LBUTTONDOWN, 1), (WM_LBUTTONUP, 0)):
        u32.PostMessageW(h, m, w, lp)
        time.sleep(0.08)


def grab(app, h, tries=20):
    from PySide6.QtGui import QPixmap
    pm = app.primaryScreen().grabWindow(h)
    for _ in range(tries):
        if pm.width() > 1 and pm.height() > 1:
            break
        u32.SetForegroundWindow(h)
        time.sleep(0.4)
        app.processEvents()
        pm = app.primaryScreen().grabWindow(h)
    return pm


def content_density(path_png, x0=200, x1=1500, y0=120, y1=900):
    from PySide6.QtGui import QImage
    img = QImage(path_png)
    bright = tot = 0
    for y in range(y0, min(y1, img.height()), 3):
        for x in range(x0, min(x1, img.width()), 3):
            c = img.pixelColor(x, y)
            tot += 1
            if c.red() > 100 or c.green() > 100 or c.blue() > 100:
                bright += 1
    return bright, tot


def scan_sidebar(im_path):
    from PySide6.QtGui import QImage
    img = QImage(im_path)
    bands, cur = [], None
    for y in range(60, 700):
        bright = 0
        for x in range(10, 135):
            c = img.pixelColor(x, y)
            if c.red() > 90 or c.green() > 90 or c.blue() > 90:
                bright += 1
        if bright >= 3 and cur is None:
            cur = y
        elif bright < 3 and cur is not None:
            if y - cur >= 6:
                bands.append((cur + y - 1) // 2)
            cur = None
    return bands


def main():
    exe = newest_exe()
    name = os.path.basename(exe).lower()
    print("[EXE]", exe, flush=True)
    proc = subprocess.Popen([exe], close_fds=True)
    hwnd = find_window(name, {proc.pid})
    if not hwnd:
        print("[失败] 无窗口")
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        return 1
    print(f"[窗口] {wtitle(hwnd)!r}", flush=True)
    u32.ShowWindow(hwnd, 9)
    u32.SetForegroundWindow(hwnd)
    time.sleep(3.5)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    base = os.path.join(SHOT, "probe_baseline.png")
    grab(app, hwnd).save(base)
    rows = scan_sidebar(base)
    print("[侧边栏行 y]", rows, flush=True)

    for i, y in enumerate(rows):
        click(hwnd, 60, y)
        time.sleep(5.0)
        p = os.path.join(SHOT, f"probe_row{i:02d}_y{y}.png")
        grab(app, hwnd).save(p)
        b, t = content_density(p)
        print(f"[行{i}] y={y}  亮像素={b}/{t} ({100.0*b/t:.1f}%)  title={wtitle(hwnd)!r}", flush=True)

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    time.sleep(1.5)
    print("[结束] 残留:", sorted(pids_of_exe(name)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
