# -*- coding: utf-8 -*-
"""真机窗口截图工具（PrintWindow，不受遮挡影响）+ 状态栏朱红像素统计。

用法：
    python dev/_scratch/grab_window.py                # 抓当前 exe 主窗口
    python dev/_scratch/grab_window.py --click 93,313 # 先点一下（客户区坐标）再抓

为什么要 PrintWindow：`SetForegroundWindow` 对非前台进程无效，`ImageGrab`
抓的是屏幕 → 窗口被遮挡时抓到的是别人的界面（第一次真机验证就踩了这个坑）。
PrintWindow(..., PW_RENDERFULLCONTENT=2) 让窗口把自己画到位图里，与遮挡无关。
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
OUT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_grab_window"
os.makedirs(OUT, exist_ok=True)

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


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


def find_wins(tag=""):
    out = []

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd) and not u32.IsIconic(hwnd):
            n = u32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                if tag in buf.value:
                    rc = wt.RECT()
                    u32.GetWindowRect(hwnd, ctypes.byref(rc))
                    # 最小化窗口的 rect 是 -32000，跳过（否则抓到一张空图）
                    if rc.right > rc.left + 100:
                        out.append((hwnd, buf.value))
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
    ok = u32.PrintWindow(hwnd, mdc, 2)          # 2 = PW_RENDERFULLCONTENT
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth, bi.biHeight = w, -h             # 负高 = top-down
    bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    g32.SelectObject(mdc, old)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, hdc)
    img.save(path)
    return img, ok, (rc.left, rc.top, rc.right, rc.bottom)


def accent(img):
    n = 0
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = px[x, y]
            if r > 110 and r - g > 40 and r - b > 35:
                n += 1
    return n


def main():
    # 默认只认指定版本号，避免抓到用户正在运行的旧实例
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v1.46.8"
    click = None
    if "--click" in sys.argv:
        click = tuple(int(v) for v in sys.argv[sys.argv.index("--click") + 1].split(","))

    wins = find_wins(tag)
    own = False
    proc = None
    exe = sys.argv[sys.argv.index("--exe") + 1] if "--exe" in sys.argv else ""
    if not wins and exe:
        proc = subprocess.Popen([exe], cwd=ROOT)
        own = True
        for _ in range(40):
            time.sleep(0.4)
            wins = find_wins(tag)
            if wins:
                break
    if not wins:
        print("[未找到窗口]", tag, flush=True)
        return
    hwnd, title = wins[0]
    print("[窗口]", hwnd, title, flush=True)
    try:
        time.sleep(2.5)
        if click:
            u32.SetForegroundWindow(hwnd)
            lp = (click[1] << 16) | click[0]
            u32.PostMessageW(hwnd, 0x0201, 1, lp)
            time.sleep(0.08)
            u32.PostMessageW(hwnd, 0x0202, 0, lp)
            print("[点击]", click, flush=True)
            time.sleep(0.5)
        for i in range(10):
            im, ok, rc = grab(hwnd, os.path.join(OUT, "win_%02d.png" % i))
            st = im.crop((max(0, im.width - 260), max(0, im.height - 40), im.width, im.height))
            print("  帧%02d PrintWindow=%s rect=%s 整窗朱红=%d 状态栏朱红=%d"
                  % (i, ok, rc, accent(im), accent(st)), flush=True)
            time.sleep(0.2)
        im, ok, rc = grab(hwnd, os.path.join(OUT, "win_final.png"))
        print("[保存]", OUT, flush=True)
    finally:
        if own and proc is not None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
            print("[已关闭]", flush=True)


main()
