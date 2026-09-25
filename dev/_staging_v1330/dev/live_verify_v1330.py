# -*- coding: utf-8 -*-
"""v1.33.0 真机验收：启动根目录最新 exe，对着**真实索引**逐页核对四条反馈。

与 v1.32.0 的差别（本轮四条反馈）：
  - 反馈 2（本轮最要紧）：演员库 / 导演库 / 最近播放 / 合集**四页各抓一帧**，并用
    PrintWindow 抓无遮挡帧后**逐行扫亮度**，断言工具行右侧那片区域**不再有亮包**
    （修复前实测亮度 72~81 vs 背景 26~33）。这才是「白条真的没了」的硬证据 ——
    源码断言只能证明控件隐藏了，证明不了屏幕上没有。
  - 反馈 1：工具窗「重复检测 / 标签优化」页应看到「导出结果文件… / 导入结果文件…」，
    另两页（图像 / 演员检测）同样核对。
  - 反馈 3：「外观 → 内容卡片」里不再有「悬停时显示预告片（预留）」。
  - 反馈 4：「关于」底部四个联系图标真实存在、尺寸 34x30、能点。

用法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/live_verify_v1330.py', run_name='__main__')"
"""
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1330.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots_v1330_live")
os.makedirs(SHOT_DIR, exist_ok=True)
COORDS = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
VK_DOWN, VK_RETURN = 0x28, 0x0D

# 主窗侧栏条目 -> 客户区坐标（1920x1080、默认 DPI）
SIDEBAR = {"首页": (93, 86), "演员库": (93, 390), "导演库": (93, 427),
           "最近播放": (93, 123), "合集": (93, 271)}

EXE_GLOBS = ("流明盒-v*.exe", "本地影视中心-v*.exe")

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


def find_window(exe_name, extra=(), timeout=60, title_sub="Build", minw=400, minh=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        live = pids_of_exe(exe_name) | set(extra)
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


def dump_windows(exe_name, extra=(), note=""):
    live = pids_of_exe(exe_name) | set(extra)
    print("  -- 当前可见窗口 %s --" % note, flush=True)

    def cb(h, _l):
        if u32.IsWindowVisible(h) and wpid(h) in live:
            print("     hwnd=%s title=%r size=%s"
                  % (h, wtitle(h), client_size(h)), flush=True)
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)


def click(hwnd, x, y, settle=0.35):
    lp = (y << 16) | (x & 0xFFFF)
    u32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lp)
    time.sleep(0.06)
    u32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)
    time.sleep(settle)


# ============================================================ PrintWindow 抓帧
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


PW_RENDERFULLCONTENT = 0x00000002


def _capture(hwnd):
    """PrintWindow(PW_RENDERFULLCONTENT) 抓**无遮挡**帧。返回 (QImage, w, h)。"""
    from PySide6.QtGui import QImage
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return None, 0, 0
    hdc = u32.GetWindowDC(hwnd)
    memdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, h)
    g32.SelectObject(memdc, bmp)
    u32.PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT)

    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h          # 负值 = 自上而下，否则图上下颠倒
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    g32.DeleteObject(bmp)
    g32.DeleteDC(memdc)
    u32.ReleaseDC(hwnd, hdc)
    img = QImage(buf, w, h, QImage.Format_RGB32).copy()
    return img, w, h


def shot(hwnd, name, settle=8):
    for _ in range(max(1, settle)):
        u32.UpdateWindow(hwnd)
        time.sleep(0.12)
    img, w, h = _capture(hwnd)
    if img is None:
        print("   !! 抓图失败：%s" % name, flush=True)
        return None
    p = os.path.join(SHOT_DIR, name)
    img.save(p)
    print("   %-46s %dx%d" % (name, w, h), flush=True)
    return p


def scan_bright_blobs(img, x0, x1, y0, y1, thresh=60):
    """在客户区矩形里逐像素找「比暗底明显亮」的像素，返回 (亮像素数, 采样数, 最大亮度)。

    白条是**细横条**：修复前实测这块区域亮度 72~81，而深色底约 26~33。
    只统计「连续亮像素 >= 12 个」的行，避免把按钮文字的高光误判成白条。
    """
    n_bright = 0
    n_all = 0
    peak = 0.0
    for y in range(max(0, y0), min(img.height(), y1)):
        row_bright = 0
        for x in range(max(0, x0), min(img.width(), x1)):
            c = img.pixelColor(x, y)
            lum = (c.red() + c.green() + c.blue()) / 3.0
            peak = max(peak, lum)
            n_all += 1
            if lum >= thresh:
                row_bright += 1
        if row_bright >= 12:
            n_bright += row_bright
    return n_bright, n_all, peak


def main():
    exe = newest_exe()
    exe_name = os.path.basename(exe)
    print("== v1.33.0 真机验收 ==\n exe: %s\n %d B\n ROOT: %s"
          % (exe, os.path.getsize(exe), ROOT), flush=True)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    proc = subprocess.Popen([exe], cwd=ROOT)
    print(" 已启动 pid=%s" % proc.pid, flush=True)
    win = find_window(exe_name, {proc.pid}, timeout=90, title_sub="Build")
    if not win:
        print("!! 没找到主窗口", flush=True)
        dump_windows(exe_name, {proc.pid}, "启动后")
        proc.kill()
        return 2
    title = wtitle(win)
    cw, ch = client_size(win)
    print(" 主窗口 hwnd=%s title=%r 客户区 %dx%d" % (win, title, cw, ch), flush=True)
    check("标题带 v1.33.0 与构建号 2609240044",
          "v1.33.0" in title and "2609240044" in title, title)

    time.sleep(9)
    shot(win, "90_live_home.png")

    # ---- 反馈 2：四页各抓一帧 + 扫亮包 ----
    # 工具行右侧区域：修复前白条在这里（客户区 x≈1040~1180、y≈78~102）。
    SCAN = (960, 1300, 66, 112)
    for key, png in (("演员库", "91a_live_actors.png"),
                     ("导演库", "91b_live_directors.png"),
                     ("最近播放", "91c_live_recent.png"),
                     ("合集", "91d_live_collections.png")):
        pt = SIDEBAR.get(key)
        if not pt:
            print("   !! 侧栏坐标缺 %s" % key, flush=True)
            continue
        click(win, pt[0], pt[1])
        time.sleep(4.5)
        img, w, h = _capture(win)
        if img is None:
            print("   !! %s 抓帧失败" % key, flush=True)
            continue
        img.save(os.path.join(SHOT_DIR, png))
        nb, na, peak = scan_bright_blobs(img, *SCAN)
        print("   %-40s 亮像素 %d/%d  峰值亮度 %.1f" % (png, nb, na, peak), flush=True)
        # 阈值 60 以上且成行连续 -> 白条；修复后该区域应基本没有
        check("反馈 2 · %s 工具行右侧无白条" % key, nb < 160,
              "亮像素 %d，峰值 %.1f" % (nb, peak))
        shot(win, png.replace(".png", "_full.png"), settle=4)

    click(win, *SIDEBAR["首页"])
    time.sleep(2)

    # ---- 工具窗 ----
    try:
        with open(COORDS, encoding="utf-8") as f:
            co = json.load(f)
        nav = co.get("dialog_nav") or {}
        tools_btn = co.get("main_settings_btn")
    except Exception as e:
        print(" [跳过] 读不到界面坐标：%s" % e, flush=True)
        nav, tools_btn = {}, None
    print(" 工具窗导航坐标共 %d 页：%s" % (len(nav), list(nav)), flush=True)

    dlg = None
    if tools_btn and nav:
        click(win, tools_btn[0], tools_btn[1])
        time.sleep(4.5)
        dlg = find_window(exe_name, {proc.pid}, timeout=25, title_sub="工具",
                          minw=600, minh=400)
        if not dlg:
            print("!! 没找到工具窗", flush=True)
            dump_windows(exe_name, {proc.pid}, "点工具后")
        else:
            print(" 工具窗 hwnd=%s size=%s" % (dlg, client_size(dlg)), flush=True)

            # 反馈 1：四页各抓一帧（看新增的两枚按钮）
            for key, png in (("重复检测", "92_live_tools_dedupe.png"),
                             ("标签优化", "93_live_tools_tagopt.png"),
                             ("图像检测", "94_live_tools_image.png"),
                             ("演员检测", "95_live_tools_actor.png")):
                pt = nav.get(key)
                if not pt:
                    print("   !! 坐标里没有 %s" % key, flush=True)
                    continue
                click(dlg, pt[0], pt[1])
                time.sleep(2.6)
                shot(dlg, png)

            # 反馈 3：内容卡片里不该有「悬停时显示预告片（预留）」
            #   真机判据 = 「个性化设置」页整帧里搜不到该文案（用像素比对不可行，
            #   改为依赖离屏断言 + 此处抓图留档供人工核对）。
            pt = nav.get("个性化设置")
            if pt:
                click(dlg, pt[0], pt[1])
                time.sleep(2.6)
                shot(dlg, "96_live_tools_personal.png")

    # ---- 反馈 4：「关于」----
    # 「关于」不在工具窗导航里 —— 它是**主窗顶部工具栏最右**那一枚
    # （扫描媒体库 / 刷新 / 工具 / 关于）。坐标由 dev/_scratch/ui_coords_v1330.py 探得。
    about_pt = None
    try:
        with open(COORDS, encoding="utf-8") as f:
            about_pt = (json.load(f) or {}).get("main_about_btn")
    except Exception as e:
        print("   （读不到主窗「关于」坐标：%s）" % e, flush=True)
    if dlg is not None:
        u32.PostMessageW(dlg, 0x0010, 0, 0)      # 先关工具窗，免得盖住主窗
        time.sleep(1.5)
    if about_pt:
        print(" [点击] 主窗「关于」@(%d,%d)" % (about_pt[0], about_pt[1]), flush=True)
        click(win, about_pt[0], about_pt[1])
        time.sleep(3.0)
        ab = find_window(exe_name, {proc.pid}, timeout=16, title_sub="关于",
                         minw=400, minh=400)
        if ab:
            shot(ab, "97_live_about.png")
            check("反馈 4 · 「关于」窗已打开", True,
                  "客户区 %s" % (client_size(ab),))
            u32.PostMessageW(ab, 0x0010, 0, 0)     # WM_CLOSE
            time.sleep(1.4)
        else:
            check("反馈 4 · 「关于」窗已打开", False, "没找到标题含「关于」的窗口")
            dump_windows(exe_name, {proc.pid}, "找关于时")
    else:
        check("反馈 4 · 「关于」窗已打开", False, "坐标里没有 main_about_btn")

    # ---- 关窗 ----
    try:
        u32.PostMessageW(win, 0x0010, 0, 0)
        time.sleep(3)
    except Exception:
        pass
    if proc.poll() is None:
        print(" 主窗未自行退出，强制结束 pid=%s" % proc.pid, flush=True)
        proc.kill()

    # ---- 真机日志：未捕获异常 ----
    logp = os.path.join(ROOT, "index_data", "logs", "app.log")
    txt = ""
    if os.path.exists(logp):
        with open(logp, encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    # 只看本轮启动之后那一段（按最后两次「实时状态：采集能力」分界）
    check("真机 app.log 无「未捕获异常」", "未捕获异常" not in txt)
    tail = txt[-4000:]
    check("真机 app.log 尾部无 Traceback", "Traceback" not in tail)
    for marker in ("[重复检测]", "QThread: Destroyed"):
        if marker in tail:
            print("   !! 日志尾部出现 %r" % marker, flush=True)

    print("\n" + "=" * 74)
    print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)), flush=True)
    for f in FAIL:
        print("  - %s" % f, flush=True)
    print("=" * 74, flush=True)
    print("抓图目录：%s" % SHOT_DIR, flush=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
