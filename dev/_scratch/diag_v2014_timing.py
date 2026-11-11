# -*- coding: utf-8 -*-
"""v2.0.14 诊断四：清空小叉到底什么时候出现？

诊断三里「打完字立刻抓图」量不到叉（≥140 只有 0 像素），**按了回车之后**才量到 16 像素。
两种可能：
  A. 叉的显隐是**延迟更新**的，1.2s 还不够 / 需要一次重绘才画出来；
  B. 顶栏搜索框是「回车才提交」，叉也跟着在那时才出现。

本脚本打完字后每 250ms 量一次右端亮像素，连续 12 次（3 秒），再按回车继续量 6 次。
一眼就能看出是「过一会儿自己出现」还是「必须回车」。
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
                    "lmc_diag4_v2014")
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
exe = os.path.join(TEMP, "LMC-diag4.exe")
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
for _i, _t in enumerate(["AAA-001 老片一", "ZZZ-005 老片五", "MIDA-210 机器猫"]):
    db.insert_media(title=_t, kind="movie", year=2026 - _i, rating=7.0, poster=POSTER,
                    file_path=os.path.join(LIB, "A", "X", "%s.mp4" % _t.split()[0]),
                    library="诊断库", sort_title=_t, tags="人妻",
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
SX0, SY0 = SCX - SW // 2, SCY - SH // 2
BAND = (SX0 + SW - 40, SY0 + 3, SX0 + SW - 3, SY0 + SH - 3)
print("搜索框 left=%d top=%d  BAND=%s" % (SX0, SY0, BAND), flush=True)


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
    time.sleep(0.2)


app = QApplication.instance() or QApplication(sys.argv)
hwnd = None


def _pm2pil(pm):
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    buf = img.constBits()
    if buf is None:
        return None
    return Image.frombytes("RGB", (img.width(), img.height()), bytes(buf), "raw", "BGRX")


def measure(tag=""):
    """⚠ 量法：**整屏抓再裁**，不用 `lv.grab(hwnd)`。

    窗口抓到的是窗口 DC，界面上有磨砂/半透明合成层时，刚显示的**子控件**可能不在里面
    → 会误判成「叉没出现」。整屏抓到的才是用户真正看到的那一帧（v2.0.12 的老教训）。
    """
    x0, y0 = screen_of(hwnd, BAND[0], BAND[1])
    x1, y1 = screen_of(hwnd, BAND[2], BAND[3])
    full = app.primaryScreen().grabWindow(0).toImage()
    n140 = n120 = 0
    xs, ys = [], []
    for yy in range(max(0, y0), min(full.height(), y1)):
        for xx in range(max(0, x0), min(full.width(), x1)):
            c = full.pixelColor(xx, yy)
            L = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
            if L >= 140:
                n140 += 1
                xs.append(xx)
                ys.append(yy)
            if L >= 120:
                n120 += 1
    bb = (min(xs), min(ys), max(xs), max(ys)) if xs else None
    print("   %-10s ≥140=%-4d ≥120=%-4d 屏幕bbox=%s" % (tag, n140, n120, bb), flush=True)
    if bb:
        full.copy(max(0, x0 - 6), max(0, y0 - 6), min(full.width(), x1 + 6),
                  min(full.height(), y1 + 6)).resize(
                      ((x1 - x0 + 12) * 6, (y1 - y0 + 12) * 6),
                      Image.NEAREST).save(
                          os.path.join(SHOTS, "v2014h_band_%s.png" % tag.replace("+", "_").replace(".", "_")))
    return full, n140, bb


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

print("\n打之前：", flush=True)
measure("空")

sx, sy = screen_of(hwnd, SCX, SCY)
u32.SetCursorPos(int(sx), int(sy))
time.sleep(0.25)
u32.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.06)
u32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(0.5)
for _ in range(3):
    key_tap(0x5A)

print("\n打完字后每 250ms 量一次（不按回车）：", flush=True)
for i in range(8):
    time.sleep(0.25)
    measure("t+%.2fs" % (0.25 * (i + 1)))

print("\n把鼠标挪到搜索框上（触发 :hover 重绘）后再量：", flush=True)
u32.SetCursorPos(*screen_of(hwnd, SCX - 200, SCY))
time.sleep(0.15)
u32.SetCursorPos(*screen_of(hwnd, SCX, SCY))
for i in range(4):
    time.sleep(0.25)
    measure("hover+%.2fs" % (0.25 * (i + 1)))

print("\n按回车后继续量：", flush=True)
key_tap(0x0D)
for i in range(4):
    time.sleep(0.25)
    measure("enter+%.2fs" % (0.25 * (i + 1)))

im, _, _ = measure("终局")
if im is not None:
    crop = im.crop((max(0, SX0 + SW - 90), max(0, SY0),
                    min(im.width, SX0 + SW), min(im.height, SY0 + SH)))
    crop.resize((crop.width * 6, crop.height * 6), Image.NEAREST).save(
        os.path.join(SHOTS, "v2014f_final_right.png"))
    print("图 v2014f_final_right.png", flush=True)

subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
print("\nDIAG4_DONE", flush=True)
