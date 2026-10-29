# -*- coding: utf-8 -*-
"""v1.46.11 复现：首页把鼠标真的移到某一行上，抓「用户实际看到的整个屏幕」。

PrintWindow 只能抓应用自己的窗口，抓不到悬停浮层（它是另一个顶层窗口），
所以这里用 BitBlt(GetDC(0)) 直接抓屏幕，再按窗口矩形裁出来。
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
EXE = os.path.join(ROOT, "流明盒-v1.46.10-2610280112.exe")
OUT = r"C:/Users/zouzu/AppData/Local/Temp/hover_repro"
os.makedirs(OUT, exist_ok=True)

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
g32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
g32.CreateCompatibleDC.restype = ctypes.c_void_p
g32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
g32.CreateCompatibleBitmap.restype = ctypes.c_void_p
g32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
g32.SelectObject.restype = ctypes.c_void_p
g32.DeleteObject.argtypes = [ctypes.c_void_p]
g32.DeleteDC.argtypes = [ctypes.c_void_p]
g32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                       ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, wt.DWORD]
g32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.UINT, wt.UINT,
                          ctypes.c_void_p, ctypes.c_void_p, wt.UINT]


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


def main_win(tag="流明盒", min_w=1200):
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
                    if rc.right - rc.left > min_w:
                        out.append((hwnd, buf.value, rc))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def top_windows():
    """列出所有可见顶层窗口（含悬停浮层这种无标题的小窗）。"""
    out = []

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd) and not u32.IsIconic(hwnd):
            rc = wt.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rc))
            w, h = rc.right - rc.left, rc.bottom - rc.top
            if w > 40 and h > 40:
                n = u32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                cls = ctypes.create_unicode_buffer(256)
                u32.GetClassNameW(hwnd, cls, 256)
                out.append((hwnd, buf.value, cls.value, (rc.left, rc.top, w, h)))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def grab_screen(box, path):
    from PIL import Image
    x, y, w, h = box
    hdc = u32.GetDC(0)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, h)
    old = g32.SelectObject(mdc, bmp)
    g32.BitBlt(mdc, 0, 0, w, h, hdc, x, y, 0x00CC0020)
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
    u32.ReleaseDC(0, hdc)
    img.save(path)
    return img


def main():
    subprocess.run(["taskkill", "/F", "/IM", os.path.basename(EXE)], capture_output=True)
    time.sleep(1.0)
    proc = subprocess.Popen([EXE], cwd=ROOT)
    found = []
    for _ in range(90):
        time.sleep(0.5)
        found = main_win()
        if found:
            break
    if not found:
        print("[失败] 窗口没起来", flush=True)
        return
    hwnd, title, rc = found[0]
    print("[窗口]", hwnd, repr(title), (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top),
          flush=True)
    u32.SetForegroundWindow(hwnd)
    time.sleep(5.0)

    # 列表第一行大约在 (左栏内) y = 客户区 150 左右
    base_x = rc.left + 300
    for i, cy in enumerate((150, 178, 206)):
        u32.SetCursorPos(base_x, rc.top + cy)
        time.sleep(0.1)
        u32.SetCursorPos(base_x + 3, rc.top + cy)
        time.sleep(1.6)                    # 等 320ms 悬停计时 + 出卡片
        for h, t, cls, box in top_windows():
            if box[2] < 320 and box[3] < 700 and box[2] > 180:
                print("   浮层候选:", h, repr(t), cls, box, flush=True)
        p = os.path.join(OUT, "hover_%d.png" % i)
        im = grab_screen((rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top), p)
        print("[抓图]", p, im.size, flush=True)

    u32.PostMessageW(hwnd, 0x0010, 0, 0)
    for _ in range(30):
        time.sleep(0.4)
        if proc.poll() is not None:
            break
    print("[退出码]", proc.poll(), flush=True)


main()
