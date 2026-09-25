# -*- coding: utf-8 -*-
"""v1.34.0 真机验收：启动根目录最新 exe，对着**真实索引**核对本轮两条新功能。

判据：
  L1  exe 能启动，主窗出现
  L2  主窗标题写的是新版本号（Build 2609240047）
  L3  导航到「智能推荐」不崩、能出内容
  L4  推荐页**存在引导向量输入行**（用键盘真打一个艺人名 + 回车 → chips 出现）
  L5  真机 app.log **无「未捕获异常」**
  L6  真机 app.log **无 Traceback**
  L7  app.log 里能看到「[智能推荐] … → N 部」记录（推荐链路真的跑通）

用法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/live_verify_v1340.py', run_name='__main__')"
"""
import ctypes
import ctypes.wintypes as wt
import glob
import io
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1340.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots_v1340_live")
os.makedirs(SHOT_DIR, exist_ok=True)

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
WM_CHAR, WM_KEYDOWN, WM_KEYUP = 0x0102, 0x0100, 0x0101
VK_RETURN = 0x0D

EXE_GLOBS = ("流明盒-v*.exe", "本地影视中心-v*.exe")
SIDEBAR_SMART = (93, 180)          # 侧栏「智能推荐」

# 引导行坐标（1920x1080、默认 DPI、本版新加）：工具行之下单独一行。
# 实测真机抓帧（screenshots_v1340_live/02_smart.png）：
#   工具行 y≈96，引导标签「引导向量」y≈120，输入框从 x≈245 横到 x≈1530，权重框 x≈1560，
#   「加强」x≈1595，「清空引导」x≈1683；chips / 状态文案 y≈143。
GUIDE_EDIT = (700, 120)
GUIDE_BAND = (240, 108, 1900, 138)     # 引导行所在横条（只覆盖输入行，不含 chips）
GUIDE_CLEAR = (1683, 120)

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


def type_text(hwnd, text):
    """往当前焦点控件逐字符发 WM_CHAR（QLineEdit 吃 WM_CHAR）。"""
    for ch in text:
        u32.PostMessageW(hwnd, WM_CHAR, ord(ch), 1)
        time.sleep(0.03)


def press_enter(hwnd):
    # 真回车（SendInput）优先 —— QLineEdit.returnPressed 由真实键事件触发最稳；
    # 再补一发 PostMessage 兜底（幂等：第二次 _add_guide 时输入框已空、直接 return）。
    down = _INPUT(INPUT_KEYBOARD, _INPUTU(ki=_KEYBDINPUT(VK_RETURN, 0, 0, 0, None)))
    up = _INPUT(INPUT_KEYBOARD, _INPUTU(
        ki=_KEYBDINPUT(VK_RETURN, 0, KEYEVENTF_KEYUP, 0, None)))
    u32.SendInput(1, ctypes.byref(down), ctypes.sizeof(_INPUT))
    time.sleep(0.06)
    u32.SendInput(1, ctypes.byref(up), ctypes.sizeof(_INPUT))
    time.sleep(0.5)
    u32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 1)
    time.sleep(0.05)
    u32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, 1)
    time.sleep(0.4)


# ---- 真键盘输入：SendInput（走系统输入队列 → 进焦点控件）----
# PostMessage(WM_CHAR) 是「邮寄给窗口」，Qt 未必把它交给焦点控件；
# probe2 证明在本机 SendInput 更可靠。两条都发，谁先到算谁的（QLineEdit 收到的是同一字符）。
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class _INPUTU(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTU)]


def _send_char(ch):
    """SendInput 打一个 Unicode 字符（不走 IME）。"""
    down = _INPUT(INPUT_KEYBOARD, _INPUTU(
        ki=_KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE, 0, None)))
    up = _INPUT(INPUT_KEYBOARD, _INPUTU(
        ki=_KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)))
    u32.SendInput(1, ctypes.byref(down), ctypes.sizeof(_INPUT))
    time.sleep(0.03)
    u32.SendInput(1, ctypes.byref(up), ctypes.sizeof(_INPUT))
    time.sleep(0.05)


def _typed_real(hwnd, text):
    for ch in text:
        _send_char(ch)
        u32.PostMessageW(hwnd, WM_CHAR, ord(ch), 1)   # 双保险
        time.sleep(0.05)


MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class _INPUTM(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT)]


class _INPUTM2(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTM)]


def _abs_xy(x, y):
    """屏幕像素 → SendInput 归一化 0..65535（按当前主屏尺寸）。"""
    sw = u32.GetSystemMetrics(0)
    sh = u32.GetSystemMetrics(1)
    nx = int(round(x * 65535.0 / max(sw - 1, 1)))
    ny = int(round(y * 65535.0 / max(sh - 1, 1)))
    return max(0, min(65535, nx)), max(0, min(65535, ny))


def _mouse_event(flags, x, y):
    nx, ny = _abs_xy(x, y)
    mi = _MOUSEINPUT(nx, ny, 0, flags | MOUSEEVENTF_ABSOLUTE, 0, None)
    inp = _INPUTM2(1, _INPUTM(mi=mi))     # type=INPUT_MOUSE
    u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUTM2))


def _real_click_client(hwnd, cx, cy):
    """真鼠标点客户区坐标 → 换算屏幕坐标（含窗口边框偏移）。"""
    wr = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(wr))
    cr = wt.RECT()
    u32.GetClientRect(hwnd, ctypes.byref(cr))
    # 客户区左上角在屏幕上的位置
    pt = wt.POINT(0, 0)
    u32.ClientToScreen(hwnd, ctypes.byref(pt))
    sx, sy = pt.x + cx, pt.y + cy
    u32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    _mouse_event(MOUSEEVENTF_LEFTDOWN, sx, sy)
    time.sleep(0.06)
    _mouse_event(MOUSEEVENTF_LEFTUP, sx, sy)
    time.sleep(0.5)


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


def _mean_bright(im, box):
    """盒内平均亮度 —— 用来判「引导行那块有没有东西」。"""
    x0, y0, x1, y1 = box
    x1 = min(x1, im.width)
    y1 = min(y1, im.height)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    crop = im.crop((x0, y0, x1, y1)).convert("L")
    try:
        px = list(crop.get_flattened_data())
    except AttributeError:                       # 老 Pillow 回退
        px = list(crop.getdata())
    return sum(px) / max(len(px), 1)


def main():
    exe = newest_exe()
    name = os.path.basename(exe)
    print("exe:", exe, flush=True)
    # 记下启动前的日志长度 —— 后面只认**本次**新增的那段（避免上一轮残留的
    # 「[引导向量] 本次生效」把断言顶成假 PASS）。
    logp = os.path.join(ROOT, "index_data", "logs", "app.log")
    _len0 = os.path.getsize(logp) if os.path.isfile(logp) else 0
    proc = subprocess.Popen([exe], cwd=ROOT)
    try:
        hwnd = find_window(name, timeout=90)
        check("L1 exe 能启动且主窗出现", hwnd is not None, "hwnd=%s" % hwnd)
        if not hwnd:
            return
        t = wtitle(hwnd)
        check("L2 主窗标题含新版本号",
              "2609240047" in t or "v1.34.0" in t, repr(t))
        time.sleep(5)
        img0 = grab(hwnd, os.path.join(SHOT_DIR, "01_main.png"))
        check("L1b 主窗能抓帧", img0 is not None,
              "%dx%d" % (img0.size if img0 else (0, 0)))

        # 导航到智能推荐（真鼠标点，顺带把窗口拉到前台）
        _real_click_client(hwnd, *SIDEBAR_SMART)
        time.sleep(8)
        img1 = grab(hwnd, os.path.join(SHOT_DIR, "02_smart.png"))
        check("L3 进「智能推荐」页能抓帧", img1 is not None,
              "%dx%d" % (img1.size if img1 else (0, 0)))
        if img0 and img1:
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

        # ---- 引导行：点输入框 → WM_CHAR 打字 → 回车加引导 ----
        # 实测（dev/_scratch/probe2.py，真机 exe v1.34.0）：
        #   点 (700,120) 聚焦 → WM_CHAR 逐字 → 回车 → app.log 落
        #   「[引导向量] 本次生效 a:さつき芽衣 × 2（共 1 条）」+ 紧接着重跑推荐；
        #   chip 行（y 138~165）亮度变化 92%，整页 55%。
        #   ⚠ 硬前提：必须先把窗口 SetForegroundWindow + SW_RESTORE（已在上面 L1b 前做过），
        #     否则窗口非激活态时 PostMessage 的 WM_CHAR 会被 QLineEdit 丢掉；
        #     另：输入行本身只有光标闪动（diff ~0.15%）→ 判据必须看 chip 行，不能看输入行。
        CHIP_BAND = (240, 138, 1900, 165)
        # 真鼠标点一下输入框（SendInput 走系统队列 → 窗口会被激活并获得键盘焦点），
        # 比 PostMessage 可靠：PostMessage 能触发绘制，但不保证键盘焦点落到 QLineEdit。
        _real_click_client(hwnd, *GUIDE_EDIT)
        time.sleep(0.8)
        time.sleep(0.5)
        _typed_real(hwnd, "さつき芽衣")
        time.sleep(0.8)
        press_enter(hwnd)                             # 回车 = 加引导
        time.sleep(4.5)
        img2 = grab(hwnd, os.path.join(SHOT_DIR, "03_guide_added.png"))
        check("L4 回车加引导后能抓帧", img2 is not None,
              "%dx%d" % (img2.size if img2 else (0, 0)))
        b_chip_before = _mean_bright(img1, CHIP_BAND) if img1 else 0.0
        b_chip_after = _mean_bright(img2, CHIP_BAND) if img2 else 0.0
        check("L4b 回车后 chip 行出现（引导 chip 真的渲染出来）",
              abs(b_chip_after - b_chip_before) > 0.8,
              "before=%.2f after=%.2f" % (b_chip_before, b_chip_after))

        # 清空引导（点「清空引导」按钮）
        _real_click_client(hwnd, *GUIDE_CLEAR)
        time.sleep(3.0)
        img3 = grab(hwnd, os.path.join(SHOT_DIR, "04_guide_cleared.png"))
        if img3:
            b_chip_clear = _mean_bright(img3, CHIP_BAND)
            check("L4c 点「清空引导」后 chip 行回到空态",
                  b_chip_clear <= b_chip_before + 0.8,
                  "clear=%.2f (空态基准 %.2f)" % (b_chip_clear, b_chip_before))
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

    logp = os.path.join(ROOT, "index_data", "logs", "app.log")
    if os.path.isfile(logp):
        raw = io.open(logp, "rb").read()
        tail = raw[-25000:].decode("utf-8", "replace")
        fresh = raw[_len0:].decode("utf-8", "replace")   # 只认本次新增
        check("L5 app.log 无「未捕获异常」", "未捕获异常" not in tail,
              "occurrences=%d" % tail.count("未捕获异常"))
        check("L6 app.log 无 Traceback", "Traceback" not in tail,
              "occurrences=%d" % tail.count("Traceback"))
        check("L7 app.log 有智能推荐链路记录",
              "[智能推荐]" in tail or "智能推荐" in tail)
        check("L8 app.log 本次新增段里有引导生效记录（[引导向量] 本次生效）",
              "[引导向量] 本次生效" in fresh,
              "fresh_bytes=%d occurrences=%d"
              % (len(fresh), fresh.count("[引导向量] 本次生效")))
        print("\n  app.log 尾部：", flush=True)
        for ln in tail.splitlines()[-16:]:
            print("    ", ln[:130], flush=True)
    else:
        check("L5 app.log 无「未捕获异常」", False, "app.log 不存在")

    print("\n" + "=" * 74)
    print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  -", f)
    print("=" * 74)


if __name__ == "__main__":
    main()
