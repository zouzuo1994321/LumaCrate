# -*- coding: utf-8 -*-
"""v1.46.12 真机验收（精简版）：只验「数据管理 → 偏好管理」这条改动。

launch exe → 点顶栏「工具」→ 点左侧「数据管理」→ PrintWindow 抓图 →
关闭两窗 → 退出。全程只按本次启动的 PID 找窗口，绝不按进程名批杀。
"""
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import subprocess
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
OUT = r"C:/Users/zouzu/AppData/Local/Temp/live_v14612_exe"
os.makedirs(OUT, exist_ok=True)
COORDS = json.load(open(r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json",
                        encoding="utf-8"))

u32 = ctypes.windll.user32
u32.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
u32.PrintWindow.restype = ctypes.c_bool
gdi = ctypes.windll.gdi32
gdi.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi.CreateCompatibleDC.restype = ctypes.c_void_p
gdi.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
gdi.CreateCompatibleBitmap.restype = ctypes.c_void_p
gdi.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi.SelectObject.restype = ctypes.c_void_p
u32.GetDC.argtypes = [ctypes.c_void_p]
u32.GetDC.restype = ctypes.c_void_p
gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
gdi.DeleteObject.argtypes = [ctypes.c_void_p]
gdi.DeleteDC.argtypes = [ctypes.c_void_p]
u32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.DWORD)]
u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                             ctypes.c_void_p, ctypes.c_void_p]

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
WM_CLOSE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0010, 0x0201, 0x0202


def as_int(v):
    if isinstance(v, (bytes, bytearray)):
        return int.from_bytes(v[:8], "little")
    return int(v)


def wpid(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(ctypes.c_void_p(h), ctypes.byref(p))
    return p.value


def wtitle(h):
    n = u32.GetWindowTextLengthW(ctypes.c_void_p(h))
    buf = ctypes.create_unicode_buffer(n + 2)
    u32.GetWindowTextW(ctypes.c_void_p(h), buf, n + 2)
    return buf.value


def wrect(h):
    r = wt.RECT()
    u32.GetWindowRect(ctypes.c_void_p(h), ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def visible_windows(pids):
    out = []

    def cb(h, _l):
        if not u32.IsWindowVisible(ctypes.c_void_p(h)):
            return True
        if wpid(h) not in pids:
            return True
        x, y, w, hh = wrect(h)
        if w < 60 or hh < 60:
            return True
        out.append((as_int(h), wtitle(h), x, y, w, hh))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def click(hwnd, x, y):
    lp = ctypes.c_void_p((y << 16) | (x & 0xFFFF))
    u32.PostMessageW(ctypes.c_void_p(hwnd), WM_LBUTTONDOWN, ctypes.c_void_p(1), lp)
    time.sleep(0.05)
    u32.PostMessageW(ctypes.c_void_p(hwnd), WM_LBUTTONUP, ctypes.c_void_p(0), lp)


def grab(hwnd, path):
    x, y, w, h = wrect(hwnd)
    hdc = u32.GetDC(ctypes.c_void_p(hwnd))
    mem = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, h)
    old = gdi.SelectObject(mem, bmp)
    # 关键：后台窗口的 GetDC 内容可能是未绘制的黑块，先让系统把窗口画进 memDC
    _ok = u32.PrintWindow(ctypes.c_void_p(hwnd), ctypes.c_void_p(mem), 2)

    class _BIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG),
                    ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                    ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                    ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]

    class _BMI(ctypes.Structure):
        _fields_ = [("bmiHeader", _BIH), ("bmiColors", wt.DWORD * 3)]

    bi = _BMI()
    bi.bmiHeader.biSize = ctypes.sizeof(_BIH)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
    with open(path, "wb") as f:
        import struct
        hdr = b"BM" + struct.pack("<IHHI", 14 + 40 + w * h * 4, 0, 0, 54)
        f.write(hdr)
        f.write(struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, w * h * 4,
                            0, 0, 0, 0))
        f.write(buf.raw)
    gdi.SelectObject(mem, old)
    gdi.DeleteObject(ctypes.c_void_p(bmp))
    gdi.DeleteDC(ctypes.c_void_p(mem))
    u32.ReleaseDC(ctypes.c_void_p(hwnd), ctypes.c_void_p(hdc))
    return w, h


def newest_exe():
    cand = []
    for pat in ("流明盒-v*.exe", "本地影视中心-v*.exe"):
        cand += glob.glob(os.path.join(ROOT, pat))
    cand = sorted(set(cand), key=os.path.getmtime)
    if not cand:
        raise SystemExit("根目录未找到 exe")
    return cand[-1]


exe = newest_exe()
print("exe:", os.path.basename(exe), "%.1f MB" % (os.path.getsize(exe) / 1048576))
cfg = os.path.join(OUT, "settings.json")
if os.path.exists(os.path.join(ROOT, "settings.json")):
    data = json.load(open(os.path.join(ROOT, "settings.json"), encoding="utf-8"))
    data.setdefault("background", {})["enabled"] = False
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
env = dict(os.environ)
env["LMC_CONFIG"] = cfg
env.pop("QT_QPA_PLATFORM", None)

proc = subprocess.Popen([exe], env=env)
pids = {proc.pid}
t0 = time.time()
main = None
while time.time() - t0 < 90:
    time.sleep(0.4)
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=20).stdout or b""
    for line in out.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == os.path.basename(exe).lower() \
                and parts[1].isdigit():
            pids.add(int(parts[1]))
    for h, t, x, y, w, hh in visible_windows(pids):
        if "流明盒" in t and w >= 1200:
            main = (h, t, w, hh)
            break
    if main:
        break
print("主窗:", main)
assert main, "主窗没出来"

time.sleep(2.0)
sx, sy = COORDS["main_settings_btn"]
print("点顶栏「工具」@", (sx, sy))
click(main[0], sx, sy)

dlg = None
t0 = time.time()
while time.time() - t0 < 20:
    time.sleep(0.4)
    for h, t, x, y, w, hh in visible_windows(pids):
        if h != main[0] and ("工具" in t or "设置" in t) and w > 800:
            dlg = (h, t, w, hh)
            break
    if dlg:
        break
print("工具窗:", dlg)
if dlg:
    time.sleep(1.2)
    nx, ny = COORDS["dialog_nav"]["数据管理"]
    print("点导航「数据管理」@", (nx, ny))
    click(dlg[0], nx, ny)
    time.sleep(1.5)
    p = os.path.join(OUT, "data_page.png")
    print("抓图", grab(dlg[0], p), p)
    u32.PostMessageW(ctypes.c_void_p(dlg[0]), WM_CLOSE, None, None)
    time.sleep(1.0)

u32.PostMessageW(ctypes.c_void_p(main[0]), WM_CLOSE, None, None)
t0 = time.time()
rc = None
while time.time() - t0 < 40:
    rc = proc.poll()
    if rc is not None:
        break
    time.sleep(0.4)
print("退出 rc=%s（%.1fs）" % (rc, time.time() - t0))
