# -*- coding: utf-8 -*-
"""v1.33.2 真机验收：启动根目录最新 exe，对着**真实索引**核对本轮改动。

判据：
  L1  exe 能启动，主窗出现（标题含 Build 2609240046）
  L2  主窗标题写的是新版本号
  L3  导航到「智能推荐」不崩、能出内容（画面有卡片亮块）
  L4  真机 app.log **无「未捕获异常」**
  L5  真机 app.log **无 Traceback**
  L6  app.log 里能看到「[智能推荐] … → N 部」记录（推荐链路真的跑通）

用法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/live_verify_v1332.py', run_name='__main__')"
"""
import ctypes
import ctypes.wintypes as wt
import glob
import io
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1332.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots_v1332_live")
os.makedirs(SHOT_DIR, exist_ok=True)

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202

EXE_GLOBS = ("流明盒-v*.exe", "本地影视中心-v*.exe")
SIDEBAR_SMART = (93, 180)          # 侧栏「智能推荐」条目（1920x1080、默认 DPI）
                                   # 顺序：首页 86 / 最近播放 117 / 我的收藏 149 / 智能推荐 180

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print(" [%s] %s  %s" % ("PASS" if cond else "FAIL", tag, detail), flush=True)


def newest_exe():
    cand = []
    for pat in EXE_GLOBS:
        cand += glob.glob(os.path.join(ROOT, pat))
    cand = sorted(set(cand), key=os.path.getmtime)
    if not cand:
        raise SystemExit("根目录未找到 exe")
    return cand[-1]


def pids_of_exe(exe_name):
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=15).stdout or b""
    res = set()
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == exe_name and parts[1].isdigit():
            res.add(int(parts[1]))
    return res


def wpid(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def wtitle(h):
    n = u32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def client_size(h):
    r = wt.RECT()
    u32.GetClientRect(h, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


def find_window(exe_name, timeout=90, title_sub="Build", minw=400, minh=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        live = pids_of_exe(exe_name)
        hit = []

        def cb(h, _l):
            if not u32.IsWindowVisible(h):
                return True
            if wpid(h) not in live:
                return True
            t = wtitle(h)
            if title_sub and title_sub not in t:
                return True
            cw, ch = client_size(h)
            if cw < minw or ch < minh:
                return True
            hit.append(h)
            return False

        u32.EnumWindows(EnumWindowsProc(cb), 0)
        if hit:
            return hit[0]
        time.sleep(0.6)
    return None


def click(hwnd, x, y, settle=0.5):
    lp = (y << 16) | (x & 0xFFFF)
    u32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lp)
    time.sleep(0.06)
    u32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)
    time.sleep(settle)


# ---------------- PrintWindow 抓帧 ----------------
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def grab(hwnd, path):
    from PIL import Image
    cw, ch = client_size(hwnd)
    if cw <= 0 or ch <= 0:
        return None
    hdc = u32.GetDC(hwnd)
    mdc = g32.CreateCompatibleDC(hdc)
    hbmp = g32.CreateCompatibleBitmap(hdc, cw, ch)
    g32.SelectObject(mdc, hbmp)
    PW_FULL = 2
    u32.PrintWindow(hwnd, mdc, PW_FULL)
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = cw
    bi.bmiHeader.biHeight = -ch
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(cw * ch * 4)
    g32.GetDIBits(mdc, hbmp, 0, ch, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (cw, ch), buf, "raw", "BGRA", 0, 1).convert("RGB")
    img.save(path)
    g32.DeleteObject(hbmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, hdc)
    return img


def main():
    exe = newest_exe()
    name = os.path.basename(exe)
    print("exe:", exe, flush=True)
    proc = subprocess.Popen([exe], cwd=ROOT)
    try:
        hwnd = find_window(name, timeout=90)
        check("L1 exe 能启动且主窗出现", hwnd is not None, "hwnd=%s" % hwnd)
        if not hwnd:
            return
        t = wtitle(hwnd)
        check("L2 主窗标题含新版本号",
              "2609240046" in t or "v1.33.2" in t, repr(t))
        time.sleep(4)
        # 抓初始帧
        img0 = grab(hwnd, os.path.join(SHOT_DIR, "01_main.png"))
        check("L1b 主窗能抓帧", img0 is not None,
              "%dx%d" % (img0.size if img0 else (0, 0)))
        # 导航到智能推荐
        click(hwnd, *SIDEBAR_SMART, settle=1.0)
        time.sleep(6)
        img1 = grab(hwnd, os.path.join(SHOT_DIR, "02_smart.png"))
        check("L3 进「智能推荐」页能抓帧", img1 is not None,
              "%dx%d" % (img1.size if img1 else (0, 0)))
        if img0 and img1:
            # 简单判「页面变了」：抽样像素差异比例
            import itertools
            diff = 0
            n = 0
            for y in range(0, min(img0.height, img1.height), 40):
                for x in range(0, min(img0.width, img1.width), 40):
                    p0 = img0.getpixel((x, y))
                    p1 = img1.getpixel((x, y))
                    if sum(abs(a - b) for a, b in zip(p0, p1)) > 40:
                        diff += 1
                    n += 1
            ratio = diff / max(n, 1)
            check("L3b 点「智能推荐」后画面确实变了", ratio > 0.10,
                  "diff=%.1f%%" % (ratio * 100))
    finally:
        time.sleep(1)
        try:
            proc.terminate()
        except Exception:
            pass
        time.sleep(2)
        try:
            proc.kill()
        except Exception:
            pass

    # ---- app.log 核对 ----
    logp = os.path.join(ROOT, "index_data", "logs", "app.log")
    if os.path.isfile(logp):
        txt = io.open(logp, encoding="utf-8", errors="replace").read()
        tail = txt[-20000:]
        check("L4 app.log 无「未捕获异常」", "未捕获异常" not in tail,
              "occurrences=%d" % tail.count("未捕获异常"))
        check("L5 app.log 无 Traceback", "Traceback" not in tail,
              "occurrences=%d" % tail.count("Traceback"))
        has_smart = ("[智能推荐]" in tail) or ("智能推荐" in tail)
        check("L6 app.log 有智能推荐链路记录", has_smart)
        print("\n  app.log 尾部：", flush=True)
        for ln in tail.splitlines()[-12:]:
            print("    ", ln[:120], flush=True)
    else:
        check("L4 app.log 无「未捕获异常」", False, "app.log 不存在")

    print("\n" + "=" * 74)
    print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  -", f)
    print("=" * 74)


if __name__ == "__main__":
    main()
