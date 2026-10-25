# -*- coding: utf-8 -*-
"""真机确认：点击侧栏「全部影片」是否生效，并打印状态栏区域的朱红峰值。"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
EXE = os.path.join(ROOT, "流明盒-v1.46.8-2610230110.exe")
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_click_shot"
os.makedirs(TMP, exist_ok=True)
u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.SetForegroundWindow.argtypes = [wt.HWND]
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]


def find_win(tag="v1.46.8"):
    out = []

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            n = u32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                if tag in buf.value:
                    out.append((hwnd, buf.value))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def accent(img):
    n = 0
    px = img.convert("RGB").load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = px[x, y]
            if r > 110 and r - g > 40 and r - b > 35:
                n += 1
    return n


from PIL import ImageGrab

proc = subprocess.Popen([EXE], cwd=ROOT)
try:
    hwnd = None
    for i in range(30):
        time.sleep(0.4)
        ws = find_win()
        if ws:
            hwnd = ws[0][0]
            if "Build" in ws[0][1]:
                break
    print("hwnd:", hwnd, find_win(), flush=True)
    time.sleep(2.0)
    u32.SetForegroundWindow(hwnd)
    time.sleep(0.6)
    rc = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(rc))
    print("rect:", rc.left, rc.top, rc.right, rc.bottom, flush=True)
    ImageGrab.grab(bbox=(rc.left, rc.top, rc.right, rc.bottom)).save(
        os.path.join(TMP, "before_click.png"))
    # 点击「全部影片」
    lp = (313 << 16) | 93
    u32.PostMessageW(hwnd, 0x0201, 1, lp)
    time.sleep(0.10)
    u32.PostMessageW(hwnd, 0x0202, 0, lp)
    print("clicked", flush=True)

    peak, hits, frames = 0, 0, 0
    for i in range(20):
        time.sleep(0.15)
        u32.GetWindowRect(hwnd, ctypes.byref(rc))
        box = (rc.right - 260, rc.bottom - 40, rc.right, rc.bottom)
        im = ImageGrab.grab(bbox=box)
        n = accent(im)
        frames += 1
        if n:
            hits += 1
            im.save(os.path.join(TMP, "hit_%02d.png" % i))
        peak = max(peak, n)
    print("状态栏抓屏：帧=%d 含朱红=%d 峰值=%d" % (frames, hits, peak), flush=True)
    ImageGrab.grab(bbox=(rc.left, rc.top, rc.right, rc.bottom)).save(
        os.path.join(TMP, "after_click.png"))
    ImageGrab.grab(bbox=(rc.left, rc.top, rc.right, rc.bottom)).resize(
        (960, int((rc.bottom - rc.top) * 960 / (rc.right - rc.left)))).save(
        os.path.join(TMP, "after_click_small.png"))
    print("saved", TMP, flush=True)
finally:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    print("done", flush=True)
