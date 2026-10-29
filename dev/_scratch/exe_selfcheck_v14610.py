# -*- coding: utf-8 -*-
"""v1.46.10 真机一键验收：启动 → 按序列点击 → 每步抓图 → 干净退出。

一次进程内跑完（避免父进程退出时把 exe 一起带走）。
用法：
    python exe_selfcheck_v14610.py --clicks "700,235:detail"
坐标是**客户区**像素；每步抓图存到 TEMP/live_v14610/<name>.png。
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
OUT = r"C:/Users/zouzu/AppData/Local/Temp/live_v14610"
os.makedirs(OUT, exist_ok=True)
TAG = "流明盒"

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


def wins_of(tag, min_w=120):
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


def grab(hwnd, path):
    from PIL import Image
    rc = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(rc))
    w, h = rc.right - rc.left, rc.bottom - rc.top
    if w < 50 or h < 50:
        print("  [跳过] 窗口尺寸异常 %dx%d" % (w, h), flush=True)
        return None
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


def click(hwnd, x, y, right=False):
    lp = (y << 16) | x
    down, up = (0x0204, 0x0205) if right else (0x0201, 0x0202)
    u32.PostMessageW(hwnd, 0x0200, 0, lp)
    time.sleep(0.05)
    u32.PostMessageW(hwnd, down, 2 if right else 1, lp)
    time.sleep(0.09)
    u32.PostMessageW(hwnd, up, 0, lp)


def main():
    args = sys.argv[1:]
    seq = args[args.index("--clicks") + 1] if "--clicks" in args else ""
    steps = []
    for part in [p for p in seq.split(";") if p.strip()]:
        xy, _, nm = part.partition(":")
        x, y = [int(v) for v in xy.split(",")]
        steps.append((x, y, nm or "shot"))

    subprocess.run(["taskkill", "/F", "/IM", os.path.basename(EXE)], capture_output=True)
    time.sleep(1.0)
    print("[启动]", os.path.basename(EXE), flush=True)
    proc = subprocess.Popen([EXE], cwd=ROOT)
    found = []
    for _ in range(90):
        time.sleep(0.5)
        found = wins_of(TAG, min_w=1200)   # 跳过启动画面（只有 440 宽）
        if found:
            break
    if not found:
        print("[失败] 窗口没起来", flush=True)
        return
    hwnd, title, rc = found[0]
    print("[窗口]", hwnd, repr(title), "%dx%d" % (rc.right - rc.left, rc.bottom - rc.top),
          flush=True)
    time.sleep(4.0)                     # 等首页列表铺完

    for x, y, nm in steps:
        right = nm.startswith("r:")
        nm = nm[2:] if right else nm
        u32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        click(hwnd, x, y, right=right)
        print("[%s点击]" % ("右键" if right else ""), nm, (x, y), flush=True)
        time.sleep(2.5)
        p = os.path.join(OUT, nm + ".png")
        im = grab(hwnd, p)
        print("   ->", p, im.size, flush=True)
        # 弹出层是独立顶层窗口：把当前所有可见窗口都数一遍，方便判断有没有新窗
        for hh, tt, rr in wins_of(TAG, min_w=80):
            print("      窗口:", hh, repr(tt), "%dx%d" % (rr.right - rr.left,
                                                          rr.bottom - rr.top), flush=True)

    u32.PostMessageW(hwnd, 0x0010, 0, 0)
    for _ in range(30):
        time.sleep(0.4)
        if proc.poll() is not None:
            break
    print("[退出码]", proc.poll(), flush=True)


main()
