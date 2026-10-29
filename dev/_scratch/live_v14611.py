# -*- coding: utf-8 -*-
"""v1.46.11 真机验收：①首页悬停只留一张卡（不再叠 tooltip）②右键五项菜单。

要点：
- 窗口按**版本号**筛（机器上还挂着旧的 v1.46.8 实例，按「流明盒」找会抓错窗口）；
- 鼠标用 SendInput 发真事件（SetCursorPos 不够：Qt 的 cellEntered / 右键菜单都要真消息）；
- 抓屏用 BitBlt(GetDC(0))，因为浮层/菜单都是独立顶层窗口，PrintWindow 抓不到。
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
EXE = os.path.join(ROOT, "流明盒-v1.46.11-2610280113.exe")
TAG = "v1.46.11"
OUT = r"C:/Users/zouzu/AppData/Local/Temp/live_v14611"
os.makedirs(OUT, exist_ok=True)

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u32.GetDC.argtypes = [wt.HWND]
u32.GetDC.restype = ctypes.c_void_p
u32.ReleaseDC.argtypes = [wt.HWND, ctypes.c_void_p]
u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.SetForegroundWindow.argtypes = [wt.HWND]
u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, wt.UINT]
u32.BringWindowToTop.argtypes = [wt.HWND]
u32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
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


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def send_mouse(flags, dx=0, dy=0):
    inp = INPUT()
    inp.type = 0                                # INPUT_MOUSE
    inp.mi = MOUSEINPUT(dx, dy, 0, flags, 0, None)
    u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def move_to(x, y, steps=6):
    """带小步走位，确保真的产生 WM_MOUSEMOVE（Qt 的 cellEntered 靠它）。"""
    cur = wt.POINT()
    u32.GetCursorPos(ctypes.byref(cur))
    for i in range(1, steps + 1):
        u32.SetCursorPos(int(cur.x + (x - cur.x) * i / steps),
                         int(cur.y + (y - cur.y) * i / steps))
        time.sleep(0.05)


def wins(tag, pid=None, min_w=100):
    out = []

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd) and not u32.IsIconic(hwnd):
            if pid is not None:
                p = wt.DWORD()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
                if p.value != pid:
                    return True
            n = u32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            if tag and tag not in buf.value:
                return True
            rc = wt.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rc))
            if rc.right - rc.left >= min_w:
                cls = ctypes.create_unicode_buffer(256)
                u32.GetClassNameW(hwnd, cls, 256)
                out.append((hwnd, buf.value, cls.value,
                            (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top)))
        return True

    u32.EnumWindows(EnumProc(cb), 0)
    return out


def grab(box, path):
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



def force_foreground(hwnd):
    """把窗口真正顶到前台。

    后台进程的 SetForegroundWindow 会被 Windows 的 foreground lock 吃掉；
    经典解法：模拟一次 Alt 键（给本进程「用户输入」的资格）+ AttachThreadInput 兜底。
    """
    VK_MENU, KEYEVENTF_KEYUP = 0x12, 0x0002
    u32.keybd_event(VK_MENU, 0, 0, 0)
    u32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.1)
    u32.ShowWindow(hwnd, 9)                       # SW_RESTORE
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    if u32.GetForegroundWindow() != hwnd:
        fg = u32.GetForegroundWindow()
        tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
        tid_fg = u32.GetWindowThreadProcessId(fg, None)
        try:
            u32.AttachThreadInput(tid_me, tid_fg, True)
            u32.SetForegroundWindow(hwnd)
            u32.AttachThreadInput(tid_me, tid_fg, False)
        except Exception:
            pass
        time.sleep(0.4)
    return u32.GetForegroundWindow() == hwnd


def main():
    subprocess.run(["taskkill", "/F", "/IM", os.path.basename(EXE)], capture_output=True)
    time.sleep(1.0)
    proc = subprocess.Popen([EXE], cwd=ROOT)
    print("[启动]", os.path.basename(EXE), flush=True)
    found = []
    for _ in range(120):
        time.sleep(0.5)
        found = [w for w in wins(TAG) if w[3][2] > 1200]
        if found:
            break
    if not found:
        print("[失败] 没找到 v1.46.11 窗口（机器上可能只有旧实例）", flush=True)
        return
    hwnd, title, cls, rc = found[0]
    print("[窗口]", hwnd, repr(title), rc, flush=True)
    print("[前台]", force_foreground(hwnd), u32.GetForegroundWindow(), flush=True)
    time.sleep(7.0)                     # 等 4.8 万条列表铺完

    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    box = (rc[0], rc[1], rc[2], rc[3])

    # ---- ① 悬停：只应出现一张卡 ----
    tx, ty = rc[0] + 420, rc[1] + 252
    move_to(tx, ty)
    time.sleep(0.6)
    move_to(tx + 12, ty + 6)
    time.sleep(1.6)
    overlays = [w for w in wins("", pid=pid.value, min_w=150) if w[0] != hwnd]
    print("[悬停] 本进程其它可见窗口 %d 个：" % len(overlays), flush=True)
    for w in overlays:
        print("   ", w[0], w[2], w[3], flush=True)
    im = grab(box, os.path.join(OUT, "hover.png"))
    print("   -> hover.png", im.size, flush=True)

    # ---- ② 右键菜单 ----
    # QMenu.exec() 是**模态循环**：用 SendMessage 发 WM_CONTEXTMENU 会一直阻塞到菜单关闭。
    # 于是开一个线程，1 秒后抓屏 + 点空白处把菜单关掉；主线程被阻塞的时长就是「菜单开没开」的判据。
    import threading
    shot = {}

    def cap_and_close():
        time.sleep(1.0)
        shot["img"] = grab(box, os.path.join(OUT, "menu.png"))
        shot["wins"] = [w for w in wins("", pid=pid.value, min_w=80) if w[0] != hwnd]
        u32.SetCursorPos(tx + 320, ty + 420)
        time.sleep(0.1)
        u32.mouse_event(0x0002, 0, 0, 0, 0)
        u32.mouse_event(0x0004, 0, 0, 0, 0)

    th = threading.Thread(target=cap_and_close, daemon=True)
    th.start()
    lp = ((ty & 0xFFFF) << 16) | (tx & 0xFFFF)
    t0 = time.time()
    u32.SendMessageW(hwnd, 0x007B, wt.WPARAM(hwnd), wt.LPARAM(lp))
    dt = time.time() - t0
    th.join(6)
    print("[右键] SendMessage 阻塞 %.2fs → %s" % (dt, "弹了模态菜单" if dt > 0.3 else "没弹"),
          flush=True)
    for w in shot.get("wins", []):
        print("   ", w[0], w[2], w[3], flush=True)
    if "img" in shot:
        print("   -> menu.png", shot["img"].size, flush=True)
    u32.PostMessageW(hwnd, 0x0010, 0, 0)      # WM_CLOSE
    for _ in range(30):
        time.sleep(0.4)
        if proc.poll() is not None:
            break
    print("[退出码]", proc.poll(), flush=True)


main()
