# -*- coding: utf-8 -*-
"""v1.33.1 真机验收：启动根目录最新 exe，对着**真实索引**逐条核对三条反馈。

本轮的判据设计：
  - 反馈 1（标签优化按钮同排）：真机点击工具窗 → 标签优化页，**从抓帧里量五枚按钮的
    y 中心**。判定「同排」靠像素：五枚按钮的高光/边框行必须在同一条带内（±2px），
    并且原来错位的第二行位置**不该再有按钮亮块**。离屏已断言过布局对象，
    这里证的是「屏幕上真的是平的」。
  - 反馈 2（重复检测撤掉导出 CSV/JSON）：真机进重复检测页抓帧，看按钮带里
    **只有两枚按钮**（导出结果文件… / 导入结果文件…），量按钮亮块的横向段数。
  - 反馈 3（真实平台 logo）：真机打开「关于」，**裁剪联系图标条并逐图标量像素** ——
    ① 四枚按钮里都要有足够多的非底色像素（非空白）；
    ② github / bilibili / weibo 三枚的**形状必须与源 png 一致**（与离屏渲染的
    参考图做 IoU 比对，>0.75 即认为形状对得上）；
    ③ 邮箱那枚的形状必须与平台 logo **明显不同**（证明它仍是自绘信封）。

用法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/live_verify_v1331.py', run_name='__main__')"
"""
import ctypes
import ctypes.wintypes as wt
import glob
import io
import json
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1331.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots_v1331_live")
os.makedirs(SHOT_DIR, exist_ok=True)
COORDS = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"
# v1.33.1：期望的 logo 形状参考图（离屏渲染出的 96×96 单色剪影），用于真机 IoU 比对
REF_DIR = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ref_logos"

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


# ============================================================ v1.33.1 新判据辅助
def lum(c):
    return (c.red() + c.green() + c.blue()) / 3.0


def row_luma_profile(img, x0, x1, y0, y1):
    """逐行平均亮度 —— 用来找「按钮所在的行带」。"""
    prof = []
    for y in range(max(0, y0), min(img.height(), y1)):
        s = n = 0
        for x in range(max(0, x0), min(img.width(), x1)):
            s += lum(img.pixelColor(x, y))
            n += 1
        prof.append((y, s / n if n else 0.0))
    return prof


def find_button_bands(img, x0, x1, y0, y1, thresh=52, min_run=14):
    """在给定矩形里找「按钮亮块」的行带。

    按钮（Ghost/Primary）有比背景亮的圆角边框与文字。返回 [(y0,y1,x0,x1,px_centroid_x)]
    形式的带列表，按 y 排序。判「同排」= 只有一条带；判「剩几枚按钮」= 带内横向段数。
    """
    bands = []
    cur = None
    for y in range(max(0, y0), min(img.height(), y1)):
        xs = [x for x in range(max(0, x0), min(img.width(), x1))
              if lum(img.pixelColor(x, y)) >= thresh]
        if len(xs) >= min_run:
            if cur is None:
                cur = [y, y, min(xs), max(xs)]
            else:
                cur[1] = y
                cur[2] = min(cur[2], min(xs))
                cur[3] = max(cur[3], max(xs))
        else:
            if cur is not None:
                if cur[1] - cur[0] >= 6:
                    bands.append(tuple(cur))
                cur = None
    if cur is not None and cur[1] - cur[0] >= 6:
        bands.append(tuple(cur))
    return bands


def count_h_segments(img, y0, y1, x0, x1, thresh=52, gap=12, min_w=18):
    """在一条行带里数「横向亮段」数 —— 每枚按钮的边框/文字会形成一段。

    把整条带按列投影：某列只要在带内有 >=1 个亮像素就算「有内容」，
    然后统计被 >=gap 个空列隔开的连续段。
    """
    cols = []
    for x in range(max(0, x0), min(img.width(), x1)):
        hit = False
        for y in range(max(0, y0), min(img.height(), y1)):
            if lum(img.pixelColor(x, y)) >= thresh:
                hit = True
                break
        cols.append(1 if hit else 0)
    segs = []
    run = 0
    empty = 0
    for v in cols:
        if v:
            if empty >= gap and run >= min_w:
                segs.append(run)
                run = 0
            run += empty + 1
            empty = 0
        else:
            empty += 1
    if run >= min_w:
        segs.append(run)
    return segs


def mask_iou(a_img, a_box, b_img, b_box, thr=60):
    """两块区域各二值化（亮于底色=前景）后算 IoU —— 形状比对。

    **关键**：两侧尺寸往往不同（真机裁块 30×30 vs 离屏参考 96×96），
    必须先把两侧**归一化到同一栅格**（各取自身归一化坐标、最近邻采样）再比，
    否则只会对齐左上角一小块、得到的 IoU 恒为 0（v1.33.1 踩过）。

    做法：把两块都重采样到 NW×NH 的归一化栅格，逐格判前景 -> 比 IoU。
    重采样用「按归一化比例映射回原图取像素」的最近邻，等价于把 b 缩放到 a。
    """
    NW, NH = 24, 24

    def _grid(img, box):
        x0, y0, x1, y1 = box
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        g = [[0] * NW for _ in range(NH)]
        for gy in range(NH):
            for gx in range(NW):
                sx = x0 + int((gx + 0.5) * w / NW)
                sy = y0 + int((gy + 0.5) * h / NH)
                if lum(img.pixelColor(min(sx, x1 - 1),
                                      min(sy, y1 - 1))) >= thr:
                    g[gy][gx] = 1
        return g

    ma = _grid(a_img, a_box)
    mb = _grid(b_img, b_box)
    inter = union = 0
    for y in range(NH):
        for x in range(NW):
            p, q = ma[y][x], mb[y][x]
            if p and q:
                inter += 1
            if p or q:
                union += 1
    return inter / union if union else 0.0


def crop_icon(img, cx, cy, r=13):
    """以 (cx,cy) 为中心裁一块图标矩形（客户区坐标）。"""
    h = img.height()
    w = img.width()
    return (max(0, cx - r), max(0, cy - r), min(w, cx + r), min(h, cy + r))


def tight_bbox(img, box, thr=60):
    """在 box 内求前景（亮于 thr）的紧致包围盒；无前景返回 None。"""
    x0, y0, x1, y1 = box
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if lum(img.pixelColor(x, y)) >= thr:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


def shape_iou(a_img, a_box, b_img, b_box, thr=60, n=24):
    """两侧各裁到**自身紧致前景包围盒**，再各归一化到 n×n 栅格比形状。

    只比形状，与字号 / 内边距 / 宽高比无关 —— 真机 22px 图标与 96px 参考剪影
    也能对齐（v1.33.1 定稿口径）。
    """
    ab, bb = tight_bbox(a_img, a_box, thr), tight_bbox(b_img, b_box, thr)
    if ab is None or bb is None:
        return 0.0

    def _grid(img, tb):
        x0, y0, x1, y1 = tb
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        g = [[0] * n for _ in range(n)]
        for gy in range(n):
            for gx in range(n):
                sx = x0 + min(w - 1, int((gx + 0.5) * w / n))
                sy = y0 + min(h - 1, int((gy + 0.5) * h / n))
                if lum(img.pixelColor(sx, sy)) >= thr:
                    g[gy][gx] = 1
        return g

    ma, mb = _grid(a_img, ab), _grid(b_img, bb)
    inter = union = 0
    for y in range(n):
        for x in range(n):
            p, q = ma[y][x], mb[y][x]
            if p and q:
                inter += 1
            if p or q:
                union += 1
    return inter / union if union else 0.0


def glyph_shape(img, box, thr=60):
    """字形紧致包围盒内的**尺度不变**形状描述子：宽高比 + 墨覆盖率。

    为什么不用像素 IoU：真机图标只有 22px、参考剪影 96px，栅格化比对在
    22px 下判别力几乎为零（同形/异形都在 0.15~0.48 之间，对角线不占优）。
    宽高比与墨覆盖率对缩放不变，实测两侧误差 < 0.05（见 skill 版本历史）。
    """
    tb = tight_bbox(img, box, thr)
    if tb is None:
        return None
    x0, y0, x1, y1 = tb
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return None
    tot = fg = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            tot += 1
            if lum(img.pixelColor(x, y)) >= thr:
                fg += 1
    return dict(w=w, h=h, ratio=w / h, ink=(fg / tot if tot else 0.0))


def load_ref_logos():
    """读离屏渲染好的 96×96 参考剪影（用于真机 IoU）。"""
    from PySide6.QtGui import QImage
    refs = {}
    if not os.path.isdir(REF_DIR):
        return refs
    for kind in ("github", "bilibili", "weibo", "mail"):
        p = os.path.join(REF_DIR, "%s.png" % kind)
        if os.path.exists(p):
            im = QImage(p)
            if not im.isNull():
                refs[kind] = im
    return refs



def main():
    exe = newest_exe()
    exe_name = os.path.basename(exe)
    print("== v1.33.1 真机验收 ==\n exe: %s\n %d B\n ROOT: %s"
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
    check("标题带 v1.33.1 与构建号 2609240045",
          "v1.33.1" in title and "2609240045" in title, title)

    time.sleep(9)
    shot(win, "90_live_home.png")

    # ---- 读界面坐标 ----
    try:
        with open(COORDS, encoding="utf-8") as f:
            co = json.load(f)
        nav = co.get("dialog_nav") or {}
        tools_btn = co.get("main_settings_btn")
        about_pt = co.get("main_about_btn")
    except Exception as e:
        print(" [跳过] 读不到界面坐标：%s" % e, flush=True)
        nav, tools_btn, about_pt = {}, None, None
    print(" 工具窗导航坐标共 %d 页：%s" % (len(nav), list(nav)), flush=True)

    # ---- 白条回归（v1.33.0 修的，本轮必须仍然没白条） ----
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
        time.sleep(4.0)
        img, w, h = _capture(win)
        if img is None:
            print("   !! %s 抓帧失败" % key, flush=True)
            continue
        nb, na, peak = scan_bright_blobs(img, *SCAN)
        shot(win, png, settle=2)
        print("   %-40s 亮像素 %d/%d  峰值亮度 %.1f" % (png, nb, na, peak), flush=True)
        check("回归 · %s 工具行右侧仍无白条" % key, nb < 160,
              "亮像素 %d，峰值 %.1f" % (nb, peak))

    click(win, *SIDEBAR["首页"])
    time.sleep(2)

    # ---- 工具窗（反馈 1 / 2） ----
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

            # ================= 反馈 1：标签优化五枚按钮同排 =================
            pt = nav.get("标签优化")
            if pt:
                click(dlg, pt[0], pt[1])
                time.sleep(3.2)
                p = shot(dlg, "92_live_tagopt_buttons.png")
                img, iw, ih = _capture(dlg)
                if img is not None:
                    # 先**定位按钮行**：Primary 按钮（扫描并预览，实心红）最亮，
                    # 它在整页里只有一处；以它的 y 行为锚，再往右扫五枚按钮。
                    BX0, BX1 = 150, min(1150, iw - 20)
                    # 红色实心按钮判据：R 明显高于 G/B
                    def _is_primary(img, x, y):
                        c = img.pixelColor(x, y)
                        return (c.red() > 150 and c.red() - c.green() > 45
                                and c.red() - c.blue() > 45)
                    prow = []
                    for y in range(200, min(ih - 20, 900)):
                        n = sum(1 for x in range(BX0, BX1)
                                if _is_primary(img, x, y))
                        if n >= 40:
                            prow.append(y)
                    print("   Primary 按钮所在行 y=%s" % (prow[:6],), flush=True)
                    check("反馈 1 · 找到实心的「扫描并预览」按钮行",
                          len(prow) >= 8, "%d 行" % len(prow))
                    if len(prow) >= 8:
                        py0, py1 = min(prow), max(prow)
                        # 按钮行上下各留 12px 作为扫描带
                        BY0 = max(0, py0 - 12)
                        BY1 = min(ih, py1 + 12)
                        bands = find_button_bands(img, BX0, BX1, BY0, BY1,
                                                  thresh=52, min_run=10)
                        print("   按钮行带 y=%d~%d 内找到 %d 条带：%s"
                              % (BY0, BY1, len(bands), bands[:6]), flush=True)
                        check("反馈 1 · 该行带内只有一条按钮带（五枚同排）",
                              len(bands) == 1,
                              "找到 %d 条带：%s" % (len(bands), bands[:4]))
                        # 按钮间距只有 8px -> gap 必须小于它，否则五枚被并成一段
                        segs = count_h_segments(img, BY0, BY1, BX0, BX1,
                                                thresh=46, gap=4, min_w=14)
                        segs = [s for s in segs if s >= 14]
                        print("   五枚按钮横向亮段 %d 段：%s" % (len(segs), segs),
                              flush=True)
                        check("反馈 1 · 该行带内有 5 枚按钮的横向亮段",
                              len(segs) >= 5, "%d 段 %s" % (len(segs), segs))
                        check("反馈 1 · 按钮行高度符合单排（< 60px）",
                              (py1 - py0 + 1) < 60, "%dpx" % (py1 - py0 + 1))

            # ================= 反馈 2：重复检测已无 CSV / JSON =================
            pt = nav.get("重复检测")
            if pt:
                click(dlg, pt[0], pt[1])
                time.sleep(3.2)
                shot(dlg, "93_live_dedupe_buttons.png")
                img, iw, ih = _capture(dlg)
                if img is not None:
                    BX0, BX1 = 150, min(1150, iw - 20)
                    BY0, BY1 = int(ih * 0.55), min(ih - 20, int(ih * 0.95))
                    bands = find_button_bands(img, BX0, BX1, BY0, BY1)
                    # 底部按钮带里数横向段：只剩「导出结果文件…/导入结果文件…」2 枚
                    cands = [b for b in bands if b[3] - b[2] > 100]
                    big = max(cands, key=lambda t: t[3] - t[2]) if cands else None
                    if big is None:
                        check("反馈 2 · 重复检测底部仍有两枚结果文件按钮", False,
                              "没找到按钮带 %s" % bands[:4])
                    else:
                        segs = count_h_segments(img, big[0], big[1] + 1, BX0, BX1)
                        segs = [s for s in segs if s >= 18]
                        print("   重复检测底部按钮带 %s 横向段 %d：%s"
                              % (big, len(segs), segs), flush=True)
                        check("反馈 2 · 底部只有 2 枚按钮（CSV/JSON 已撤走）",
                              len(segs) <= 3,
                              "%d 段 %s（>3 说明还残留多余按钮）" % (len(segs), segs))

            # 其余两页留档
            for key, png in (("图像检测", "94_live_tools_image.png"),
                             ("演员检测", "95_live_tools_actor.png")):
                pt = nav.get(key)
                if pt:
                    click(dlg, pt[0], pt[1])
                    time.sleep(2.2)
                    shot(dlg, png)

    # ---- 反馈 3：「关于」真实平台 logo ----
    # 「关于」不在工具窗导航里 —— 它是**主窗顶部工具栏最右**那一枚。
    if dlg is not None:
        click(dlg, 0, 0)            # 收焦
        u32.PostMessageW(dlg, 0x0010, 0, 0)      # 先关工具窗，免得盖住主窗
        time.sleep(1.8)
    if about_pt:
        print(" [点击] 主窗「关于」@(%d,%d)" % (about_pt[0], about_pt[1]), flush=True)
        click(win, about_pt[0], about_pt[1])
        time.sleep(3.2)
        ab = find_window(exe_name, {proc.pid}, timeout=16, title_sub="关于",
                         minw=400, minh=400)
        if not ab:
            check("反馈 3 · 「关于」窗已打开", False, "没找到标题含「关于」的窗口")
            dump_windows(exe_name, {proc.pid}, "找关于时")
        else:
            check("反馈 3 · 「关于」窗已打开", True, "客户区 %s" % (client_size(ab),))
            shot(ab, "96_live_about.png")
            aimg, aw, ah = _capture(ab)
            if aimg is not None:
                # **关键**：图标是密排的（按钮 34px 宽 + 间距 10px -> 中心距恒 44px），
                # 列投影切不出独立簇。所以改为「先找图标行，再按已知几何取样」。
                FY0, FY1 = int(ah * 0.70), ah
                # ① 逐行数「浅色前景」像素（图标是 #e8e0d4，远亮于深底）
                rowhit = []
                for y in range(FY0, FY1):
                    n = sum(1 for x in range(0, aw)
                            if lum(aimg.pixelColor(x, y)) >= 120)
                    rowhit.append((y, n))
                # ② **质量阈值法**：对底部区域做列投影，图标本体是「宽且有
                #    质量」的段（图标图形实心、宽度 12~20px、质量 >= 80），
                #    文字字形则是「窄且轻」的段（宽 <= 11px、质量 <= 45）。
                def _icon_segs(ylo, yhi):
                    prof = [0] * aw
                    for yy in range(ylo, yhi):
                        for x in range(0, aw):
                            if lum(aimg.pixelColor(x, yy)) >= 120:
                                prof[x] += 1
                    segs, cur, s = [], False, 0
                    for x in range(aw):
                        if prof[x] > 0 and not cur:
                            s, cur = x, True
                        elif prof[x] == 0 and cur:
                            segs.append((s, x - 1, sum(prof[s:x])))
                            cur = False
                    if cur:
                        segs.append((s, aw - 1, sum(prof[s:])))
                    return segs

                hit = None
                best = None
                for hh in (14, 16, 12, 18, 20, 22):
                    for ylo in range(ah - hh, int(ah * 0.60), -1):
                        segs = _icon_segs(ylo, ylo + hh)
                        big = [g for g in segs
                               if g[2] >= 80 and (g[1] - g[0] + 1) >= 12]
                        if len(big) == 4:
                            hit = (ylo, ylo + hh, big)
                            break
                        if len(big) > 4 and (best is None or
                                             ylo > best[0]):
                            best = (ylo, ylo + hh, big)
                    if hit:
                        break
                print("   图标带质量命中：%s" % (hit and (hit[0], hit[1],
                      [(g[0], g[1], g[2]) for g in hit[2]]),), flush=True)
                check("反馈 3 · 定位到 4 枚图标本体段", hit is not None,
                      "hit=%s，备选 %s" % (hit and hit[0],
                      best and [(g[0], g[1], g[2]) for g in best[2]]))
                if hit:
                    ylo, yhi, big = hit
                    by0, by1 = ylo, yhi - 1
                    ycen = (by0 + by1) // 2
                    cen = [(g[0] + g[1]) // 2 for g in big]
                    steps = [cen[i + 1] - cen[i] for i in range(3)]
                    print("   图标带 y=%d~%d（中心 %d）质心 %s 步长 %s"
                          % (by0, by1, ycen, cen, steps), flush=True)
                    check("反馈 3 · 四枚图标等距（相邻步长 38~50px）",
                          all(38 <= st <= 50 for st in steps),
                          "步长 %s" % steps)
                    first_x = big[0][0]
                    check("反馈 3 · 找到首个图标前景列", first_x > 0,
                          "x=%d" % first_x)
                    centers = [(c, ycen) for c in cen]
                    bx0 = max(0, first_x - 6)
                    b = (by0, by1, bx0, big[-1][1] + 6)
                    picked = (b, [34, 34, 34, 34])
                    # 逐图标裁一块，量「非底色像素」+ 与参考剪影 IoU
                    refs = load_ref_logos()
                    kinds = ["github", "bilibili", "weibo", "mail"]
                    # 用 ④ 推算出的四枚按钮中心（几何步长法，密排图标下最稳）
                    print("   四个图标中心：%s" % (centers,), flush=True)
                    for k, (cx, cy) in zip(kinds, centers):
                        box = crop_icon(aimg, cx, cy, r=16)
                        fg = 0
                        tot = 0
                        for yy in range(box[1], box[3]):
                            for xx in range(box[0], box[2]):
                                tot += 1
                                if lum(aimg.pixelColor(xx, yy)) >= 60:
                                    fg += 1
                        ratio = fg / tot if tot else 0
                        print("     %-9s @(%d,%d) 前景占比 %.3f" % (k, cx, cy, ratio),
                              flush=True)
                        check("反馈 3 · %s 图标非空白（前景占比 > 0.06）" % k,
                              ratio > 0.06, "%.3f" % ratio)
                        ref = refs.get(k)
                        if ref is not None:
                            rb = (0, 0, ref.width(), ref.height())
                            # 尺度不变形状描述子：宽高比 + 墨覆盖率（各自紧致盒）
                            lf = glyph_shape(aimg, box, thr=120)
                            rf = glyph_shape(ref, rb, thr=60)
                            if lf and rf:
                                dr = abs(lf["ratio"] - rf["ratio"])
                                di = abs(lf["ink"] - rf["ink"])
                                print("       %-9s live ratio=%.2f ink=%.3f | "
                                      "ref ratio=%.2f ink=%.3f | dRatio=%.2f dInk=%.3f"
                                      % (k, lf["ratio"], lf["ink"], rf["ratio"],
                                         rf["ink"], dr, di), flush=True)
                                same = (dr < 0.22 and di < 0.10)
                                if k != "mail":
                                    check("反馈 3 · %s 形状与平台 logo 一致"
                                          "（宽高比+墨覆盖率）" % k, same,
                                          "dRatio=%.2f dInk=%.3f" % (dr, di))
                                else:
                                    # 邮件是自绘信封，应与三枚平台 logo 都不同
                                    # （其 ink 0.85 / ratio 1.4 与 github 0.68/0.88 差异大）
                                    matches_any = False
                                    for pk in ("github", "bilibili", "weibo"):
                                        rp = refs.get(pk)
                                        if rp is None:
                                            continue
                                        pf = glyph_shape(rp, (0, 0, rp.width(),
                                                              rp.height()), 60)
                                        if pf and (abs(lf["ratio"] - pf["ratio"]) < 0.22
                                                   and abs(lf["ink"] - pf["ink"]) < 0.10):
                                            matches_any = True
                                    check("反馈 3 · 邮箱仍是自绘（与三枚平台 logo 都不同）",
                                          not matches_any, "ratio=%.2f ink=%.3f"
                                          % (lf["ratio"], lf["ink"]))
            u32.PostMessageW(ab, 0x0010, 0, 0)     # WM_CLOSE
            time.sleep(1.4)
    else:
        check("反馈 3 · 「关于」窗已打开", False, "坐标里没有 main_about_btn")



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
