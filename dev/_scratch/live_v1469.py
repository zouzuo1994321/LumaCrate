# -*- coding: utf-8 -*-
"""v1.46.9 真机驱动：找/启动 v1.46.9 主窗，按需点击，PrintWindow 抓图。

用法：
    python live_v1469.py --exe "<exe路径>"          # 启动（若没在跑）并抓首屏
    python live_v1469.py --click 250,300 --shot d1  # 点一下再抓，命名 d1.png
    python live_v1469.py --kill                     # 关掉本次启动的实例
"""
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
OUT = r"C:/Users/zouzu/AppData/Local/Temp/live_v1469"
os.makedirs(OUT, exist_ok=True)
TAG = "v1.46.9"

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u32.GetWindowDC.argtypes = [wt.HWND]
u32.GetWindowDC.restype = ctypes.c_void_p
u32.ReleaseDC.argtypes = [wt.HWND, ctypes.c_void_p]
u32.PrintWindow.argtypes = [wt.HWND, ctypes.c_void_p, wt.UINT]
u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.SetForegroundWindow.argtypes = [wt.HWND]
g32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
g32.CreateCompatibleDC.restype = ctypes.c_void_p
g32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
g32.CreateCompatibleBitmap.restype = ctypes.c_void_p
g32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
g32.SelectObject.restype = ctypes.c_void_p
g32.DeleteObject.argtypes = [ctypes.c_void_p]
g32.DeleteDC.argtypes = [ctypes.c_void_p]
g32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.UINT, wt.UINT,
                          ctypes.c_void_p, ctypes.c_void_p, wt.UINT]


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


def find_wins():
    out = []

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd) and not u32.IsIconic(hwnd):
            n = u32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                if TAG in buf.value:
                    rc = wt.RECT()
                    u32.GetWindowRect(hwnd, ctypes.byref(rc))
                    if rc.right - rc.left > 200:
                        out.append((hwnd, buf.value, rc))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def grab(hwnd, path):
    from PIL import Image
    rc = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(rc))
    w, h = rc.right - rc.left, rc.bottom - rc.top
    hdc = u32.GetWindowDC(hwnd)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, h)
    old = g32.SelectObject(mdc, bmp)
    u32.PrintWindow(hwnd, mdc, 2)
    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth, bi.biHeight = w, -h
    bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    g32.SelectObject(mdc, old)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, hdc)
    img.save(path)
    return img


def main():
    args = sys.argv[1:]
    exe = args[args.index("--exe") + 1] if "--exe" in args else ""
    name = args[args.index("--shot") + 1] if "--shot" in args else "shot"
    click = None
    if "--click" in args:
        click = tuple(int(v) for v in args[args.index("--click") + 1].split(","))

    wins = find_wins()
    if "--kill" in args:
        for hwnd, title, _rc in wins:
            u32.PostMessageW(hwnd, 0x0010, 0, 0)     # WM_CLOSE
        print("[关闭]", len(wins), "个窗口", flush=True)
        return

    if not wins and exe:
        print("[启动]", exe, flush=True)
        subprocess.Popen([exe], cwd=ROOT)
        for _ in range(120):
            time.sleep(0.5)
            wins = find_wins()
            if wins:
                break
    if not wins:
        print("[未找到窗口]", TAG, flush=True)
        return

    hwnd, title, rc = wins[0]
    w, h = rc.right - rc.left, rc.bottom - rc.top
    print("[窗口]", hwnd, repr(title), "size=%dx%d" % (w, h), flush=True)

    if click is not None:
        u32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        lp = (click[1] << 16) | click[0]
        u32.PostMessageW(hwnd, 0x0200, 0, lp)        # WM_MOUSEMOVE
        time.sleep(0.05)
        u32.PostMessageW(hwnd, 0x0201, 1, lp)        # WM_LBUTTONDOWN
        time.sleep(0.09)
        u32.PostMessageW(hwnd, 0x0202, 0, lp)        # WM_LBUTTONUP
        print("[点击]", click, flush=True)
        time.sleep(2.0)                              # 详情页要读图/建卡

    time.sleep(0.6)
    path = os.path.join(OUT, name + ".png")
    img = grab(hwnd, path)
    print("[抓图]", path, img.size, flush=True)

    # 顺带统计「朱红像素」（判断返回按钮/播放按钮区域是否真画出来，防抓到空窗）
    n = 0
    px = img.load()
    for y in range(0, img.height, 2):
        for x in range(0, img.width, 2):
            r, g, b = px[x, y]
            if r > 110 and r - g > 40 and r - b > 35:
                n += 1
    print("[朱红像素(1/4采样)]", n, flush=True)


main()
