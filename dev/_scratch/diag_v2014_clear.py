# -*- coding: utf-8 -*-
"""v2.0.14 诊断三：把「有没有叉」量准，顺便问清顶栏搜索是不是要回车才筛。

诊断二撞了两个口径问题（都是量法错，不是功能错）：
  ① 清空叉是 `#a1a1aa`，亮度 ≈ 161，我却用 170 当阈值 → 恒报 0；
  ② 打进去 ZZZ 后列表没变 —— 可能顶栏搜索是**回车才筛**，也可能我的墨迹采样区不对。

本脚本：打字 → 量右端亮度分布（多档阈值）→ 把最右 80px 放大 6 倍存图 → 回车再量列表。
"""
import ctypes
import ctypes.wintypes
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_diag3_v2014")
COORDS_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                           "Temp", "lmc_coords_v208.json")
sys.path.insert(0, DEV)
os.environ["LMC_NO_SYSMON"] = "1"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv        # noqa: E402
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication          # noqa: E402
from PySide6.QtGui import QImage                    # noqa: E402
from PIL import Image                               # noqa: E402

u32 = lv.u32
CHECK = os.path.join(ROOT, "流明盒-v2.0.14-2611110135.exe")
os.makedirs(TEMP, exist_ok=True)
exe = os.path.join(TEMP, "LMC-diag3.exe")
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(CHECK):
    shutil.copy2(CHECK, exe)
EXE_NAME = os.path.basename(exe).lower()
LIB = os.path.join(TEMP, "lib")
os.makedirs(os.path.join(LIB, "A", "X"), exist_ok=True)
CFG = os.path.join(TEMP, "settings.json")
with open(CFG, "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "诊断库", "kind": "电影", "paths": [LIB], "filter": {}}],
               "appearance": {"accent": "#e4587c", "mode": "磨砂玻璃", "level": "低"}},
              f, ensure_ascii=False)

sys.path.insert(0, os.path.join(ROOT, "src"))
import database as db          # noqa: E402
import applog                  # noqa: E402

IDX = os.path.join(TEMP, "index_data")
os.makedirs(os.path.join(IDX, "logs"), exist_ok=True)
DBF = os.path.join(IDX, "media_center.db")
for _fn in os.listdir(IDX):
    if _fn.lower().endswith((".db", ".db-wal", ".db-shm")):
        _p = os.path.join(IDX, _fn)
        ctypes.windll.kernel32.SetFileAttributesW(_p, 0x80)
        ctypes.windll.kernel32.DeleteFileW(_p)
db.db_path = lambda: DBF
applog.log_dir = lambda: os.path.join(IDX, "logs")
db.init_db()
POSTER = os.path.join(TEMP, "poster.png")
Image.new("RGB", (300, 450), (90, 150, 110)).save(POSTER)
for _i, _t in enumerate(["AAA-001 老片一", "BBB-002 老片二", "CCC-003 老片三",
                         "DDD-004 老片四", "ZZZ-005 老片五", "MIDA-209 真机验收",
                         "MIDA-210 机器猫"]):
    db.insert_media(title=_t, kind="movie", year=2026 - _i, rating=7.0, poster=POSTER,
                    file_path=os.path.join(LIB, "A", "X", "%s.mp4" % _t.split()[0]),
                    library="诊断库", sort_title=_t, tags="人妻,高清",
                    added_time="2026-11-05 12:00:00", added_date="2026-11-05")
db.close_conn()

env = dict(os.environ)
env["LMC_CONFIG"] = CFG
env["QT_QPA_PLATFORM"] = "offscreen"
subprocess.run([sys.executable, "-c",
                "import runpy; runpy.run_path(r'%s', run_name='__main__')"
                % os.path.join(DEV, "_scratch", "coords_v208.py")],
               env=env, capture_output=True, text=True, encoding="utf-8",
               errors="replace", cwd=DEV)
CO = json.load(open(COORDS_JSON, encoding="utf-8"))
SCX, SCY, SW, SH = CO["search"]
HDR, TBL = CO["header"], CO["table"]
SX0, SY0 = SCX - SW // 2, SCY - SH // 2
print("搜索框 left=%d top=%d w=%d h=%d" % (SX0, SY0, SW, SH), flush=True)


def screen_of(win, x, y):
    pt = ctypes.wintypes.POINT(int(x), int(y))
    u32.ClientToScreen(ctypes.wintypes.HWND(int(win)), ctypes.byref(pt))
    return pt.x, pt.y


def pid_of(h):
    q = ctypes.wintypes.DWORD()
    u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(int(h)), ctypes.byref(q))
    return q.value


def force_foreground(h):
    hw = ctypes.wintypes.HWND(int(h))
    tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
    fg = u32.GetForegroundWindow()
    tid_fg = u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(fg), None) if fg else 0
    tid_t = u32.GetWindowThreadProcessId(hw, None)
    o1 = bool(u32.AttachThreadInput(tid_me, tid_fg, True)) if tid_fg and tid_fg != tid_me else False
    o2 = bool(u32.AttachThreadInput(tid_me, tid_t, True)) if tid_t and tid_t != tid_me else False
    u32.BringWindowToTop(hw)
    u32.SetForegroundWindow(hw)
    u32.SetFocus(hw)
    if o2:
        u32.AttachThreadInput(tid_me, tid_t, False)
    if o1:
        u32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.4)
    return u32.GetForegroundWindow() == int(h)


def key_tap(vk, ctrl=False):
    if ctrl:
        u32.keybd_event(0x11, 0, 0, 0)
    u32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.06)
    u32.keybd_event(vk, 0, 2, 0)
    if ctrl:
        u32.keybd_event(0x11, 0, 2, 0)
    time.sleep(0.25)


app = QApplication.instance() or QApplication(sys.argv)


def _pm2pil(pm):
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    buf = img.constBits()
    if buf is None:
        return None
    return Image.frombytes("RGB", (img.width(), img.height()), bytes(buf), "raw", "BGRX")


hwnd = None


def shot(tag):
    pm = lv.grab(app, hwnd, tries=24, gap=0.4, settle=3)
    im = _pm2pil(pm) if pm is not None else None
    if im is not None:
        im.save(os.path.join(SHOTS, "v2014e_%s.png" % tag))
    return im


def rows_ink(im, thr=150):
    if im is None:
        return -1
    px, n = im.load(), 0
    y0 = TBL["y"] + HDR["h"]
    for y in range(max(0, y0), min(im.height, y0 + TBL["row_h"] * 9)):
        for x in range(max(0, TBL["x"] + 8), min(im.width, TBL["x"] + 560)):
            c = px[x, y]
            if 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] >= thr:
                n += 1
    return n


def band_report(im, tag):
    """搜索框最右 90px 的亮度分布（多档阈值），并放大存图。"""
    if im is None:
        return
    box = (max(0, SX0 + SW - 90), max(0, SY0), min(im.width, SX0 + SW), min(im.height, SY0 + SH))
    crop = im.crop(box)
    for t in (100, 120, 140, 160, 170, 200):
        px, n = crop.load(), 0
        for y in range(crop.height):
            for x in range(crop.width):
                c = px[x, y]
                if 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] >= t:
                    n += 1
        print("    阈值 %-4d 亮像素 = %d" % (t, n), flush=True)
    big = crop.resize((crop.width * 6, crop.height * 6), Image.NEAREST)
    big.save(os.path.join(SHOTS, "v2014e_%s_right.png" % tag))
    print("    图 v2014e_%s_right.png（最右 90px ×6）" % tag, flush=True)
    # 同时把「叉可能所在的那 22px」单独定位：找出亮度 >140 的像素包围盒
    px = crop.load()
    xs, ys = [], []
    for y in range(crop.height):
        for x in range(crop.width):
            c = px[x, y]
            if 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] >= 140:
                xs.append(x)
                ys.append(y)
    if xs:
        print("    亮像素包围盒(相对最右90px) = x %d..%d  y %d..%d"
              % (min(xs), max(xs), min(ys), max(ys)), flush=True)


subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
time.sleep(0.8)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=200, title_sub="Build")
if not hwnd:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    raise SystemExit(1)
time.sleep(5.0)
APP_PID = pid_of(hwnd)
force_foreground(hwnd)
u32.SetCursorPos(*screen_of(hwnd, 1300, 980))
time.sleep(1.0)

im0 = shot("base")
i0 = rows_ink(im0)
print("\n初始列表墨迹 =", i0, flush=True)
print("空搜索框最右 90px：", flush=True)
band_report(im0, "empty")

print("\n=== 点搜索框 + 打 ZZZ ===", flush=True)
sx, sy = screen_of(hwnd, SCX, SCY)
u32.SetCursorPos(int(sx), int(sy))
time.sleep(0.25)
u32.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.06)
u32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(0.5)
for _ in range(3):
    key_tap(0x5A)
time.sleep(1.2)

im1 = shot("typed")
print("打字后列表墨迹 =", rows_ink(im1), "（初始 %d）" % i0, flush=True)
print("打字后搜索框最右 90px：", flush=True)
band_report(im1, "typed")

print("\n=== 回车（顶栏搜索可能是回车才筛）===", flush=True)
key_tap(0x0D)
time.sleep(1.5)
im2 = shot("enter")
print("回车后列表墨迹 =", rows_ink(im2), flush=True)
print("回车后搜索框最右 90px：", flush=True)
band_report(im2, "enter")

print("\n=== 点那颗叉（若存在）===", flush=True)
# 叉的位置：搜索框右端 - 15px 左右；点两处都试
for dx in (15, 12, 18):
    u32.SetCursorPos(*screen_of(hwnd, SX0 + SW - dx, SCY))
    time.sleep(0.2)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    u32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(1.0)
    imx = shot("cleared_%d" % dx)
    print("  点右端 -%dpx 后：列表墨迹 = %s" % (dx, rows_ink(imx)), flush=True)
    band_report(imx, "cleared_%d" % dx)

subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
print("\nDIAG3_DONE", flush=True)
