# -*- coding: utf-8 -*-
"""v2.0.14 诊断二：输入到底有没有送进应用？坐标映射准不准？

诊断一已经证明：点搜索框 / Ctrl+V / 右键之后，进程里**一个窗口都没多**。
两种可能：
  A. 键鼠事件根本没送进应用（焦点/坐标问题）；
  B. 送进去了但那个点不是搜索框。

本脚本做四个对照，全部只看「应用有没有反应」：
  ① 点 (950,25) 后打一个 'Z' → 列表应筛到只剩 ZZZ-005（墨迹骤降）；
  ② 点 (950,64)（下移 39px，怀疑客户区原点偏了）后再打 'Z'；
  ③ 键盘菜单键 VK_APPS(0x5D) → 应弹出聚焦控件的右键菜单；
  ④ 两个高度各右键一次，各 dump 一次窗口。
每一步都打印 ClientToScreen 的实际结果，便于回头核对坐标。
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
                    "lmc_diag2_v2014")
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
exe = os.path.join(TEMP, "LMC-diag2.exe")
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
print("搜索框 中心=(%d,%d) 尺寸=%dx%d" % (SCX, SCY, SW, SH), flush=True)
print("表格 left=%s top=%s row_h=%s" % (TBL["x"], TBL["y"], TBL["row_h"]), flush=True)

# ⚠ 必须真插片：诊断一那版库里是空的，列表墨迹恒为 0 → 「打字有没有反应」量不出来，
#   白白把 ① ② 两段判成「应用没反应」。
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
    db.insert_media(
        title=_t, kind="movie", year=2026 - _i, rating=7.0, poster=POSTER,
        file_path=os.path.join(LIB, "A", "X", "%s.mp4" % _t.split()[0]),
        library="诊断库", sort_title=_t, tags="人妻,高清",
        added_time="2026-11-05 12:00:00", added_date="2026-11-05")
print("已插 7 部片：",
      db.get_conn().execute("SELECT COUNT(*) FROM media").fetchone()[0], flush=True)
db.close_conn()


def screen_of(win, x, y):
    pt = ctypes.wintypes.POINT(int(x), int(y))
    u32.ClientToScreen(ctypes.wintypes.HWND(int(win)), ctypes.byref(pt))
    return pt.x, pt.y


def pid_of(h):
    q = ctypes.wintypes.DWORD()
    u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(int(h)), ctypes.byref(q))
    return q.value


def win_class(h):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(ctypes.wintypes.HWND(int(h)), buf, 256)
    return buf.value


def popups(pid):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def _cb(h, _l):
        q = ctypes.wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(q))
        if q.value != pid or not u32.IsWindowVisible(h):
            return True
        rc = ctypes.wintypes.RECT()
        u32.GetWindowRect(h, ctypes.byref(rc))
        w, hh = rc.right - rc.left, rc.bottom - rc.top
        if w >= 100 and hh >= 50:
            out.append((int(h), w, hh, win_class(h)))
        return True

    u32.EnumWindows(_cb, 0)
    return out


def force_foreground(h):
    """抢前台 + 抢**键盘焦点**。

    ⚠ 只 `SetForegroundWindow` 是不够的：`SetFocus` 只对**调用线程自己的**窗口生效，
    目标窗口在别的线程/进程里 → 那一句静默失败，键盘事件照样送不进去
    （实测：右键能弹出菜单，但打任何键都没反应）。
    必须先 `AttachThreadInput(我的线程, 目标窗口线程)` 再 SetFocus。
    """
    hw = ctypes.wintypes.HWND(int(h))
    tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
    fg = u32.GetForegroundWindow()
    tid_fg = u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(fg), None) if fg else 0
    tid_target = u32.GetWindowThreadProcessId(hw, None)
    ok1 = ok2 = False
    if tid_fg and tid_fg != tid_me:
        ok1 = bool(u32.AttachThreadInput(tid_me, tid_fg, True))
    if tid_target and tid_target != tid_me:
        ok2 = bool(u32.AttachThreadInput(tid_me, tid_target, True))
    u32.BringWindowToTop(hw)
    u32.SetForegroundWindow(hw)
    u32.SetFocus(hw)
    if ok2:
        u32.AttachThreadInput(tid_me, tid_target, False)
    if ok1:
        u32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.4)
    return u32.GetForegroundWindow() == int(h)


def key_tap(vk, shift=False, ctrl=False):
    if ctrl:
        u32.keybd_event(0x11, 0, 0, 0)
    if shift:
        u32.keybd_event(0x10, 0, 0, 0)
    u32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.06)
    u32.keybd_event(vk, 0, 2, 0)
    if shift:
        u32.keybd_event(0x10, 0, 2, 0)
    if ctrl:
        u32.keybd_event(0x11, 0, 2, 0)
    time.sleep(0.3)


def left_click_at(sx, sy):
    u32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.25)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    u32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.5)


def right_click_at(sx, sy):
    u32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.25)
    u32.mouse_event(0x0008, 0, 0, 0, 0)
    time.sleep(0.09)
    u32.mouse_event(0x0010, 0, 0, 0, 0)
    time.sleep(0.8)


app = QApplication.instance() or QApplication(sys.argv)


def _pm2pil(pm):
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    buf = img.constBits()
    if buf is None:
        return None
    return Image.frombytes("RGB", (img.width(), img.height()), bytes(buf), "raw", "BGRX")


def shot(tag):
    pm = lv.grab(app, hwnd, tries=24, gap=0.4, settle=3)
    if pm is None:
        return None
    im = _pm2pil(pm)
    if im is not None:
        im.save(os.path.join(SHOTS, "v2014d_%s.png" % tag))
        print("  图 v2014d_%s.png %dx%d" % (tag, im.width, im.height), flush=True)
    return im


def ink(im):
    if im is None:
        return -1
    px, n = im.load(), 0
    y0 = TBL["y"] + HDR["h"]
    for y in range(max(0, y0), min(im.height, y0 + TBL["row_h"] * 8)):
        for x in range(max(0, TBL["x"] + 8), min(im.width, TBL["x"] + 520)):
            c = px[x, y]
            if 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] >= 150:
                n += 1
    return n


def type_wchar(h, text):
    """往窗口投 WM_CHAR —— Qt 只有一个 HWND，字符由它转交给焦点控件。

    比剪贴板干净：诊断一里用本进程 Qt 的剪贴板去粘，exe 取的是**延迟渲染**数据，
    我们的进程又没在跑事件循环 → 对方的粘贴会等我们（UI 线程被拖住好几秒），
    那几秒里所有输入都被吞掉，看起来像「键鼠根本送不进去」。
    """
    for ch in text:
        u32.PostMessageW(ctypes.wintypes.HWND(int(h)), 0x0102, ord(ch), 1)
        time.sleep(0.09)
    time.sleep(0.6)


def bright_right(im, band=46):
    """搜索框右端亮像素（清空小叉的代理量）。"""
    if im is None:
        return -1
    px, n = im.load(), 0
    for y in range(max(0, SCY - SH // 2), min(im.height, SCY + SH // 2)):
        for x in range(max(0, SCX + SW // 2 - band), min(im.width, SCX + SW // 2)):
            c = px[x, y]
            if 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] >= 170:
                n += 1
    return n


subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
time.sleep(0.8)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=200, title_sub="Build")
print("主窗 =", hwnd, flush=True)
if not hwnd:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    raise SystemExit(1)
time.sleep(5.0)
APP_PID = pid_of(hwnd)
wr = ctypes.wintypes.RECT()
u32.GetWindowRect(ctypes.wintypes.HWND(int(hwnd)), ctypes.byref(wr))
cr = ctypes.wintypes.RECT()
u32.GetClientRect(ctypes.wintypes.HWND(int(hwnd)), ctypes.byref(cr))
print("window rect=%s  client=%dx%d" % ((wr.left, wr.top, wr.right, wr.bottom),
                                        cr.right - cr.left, cr.bottom - cr.top), flush=True)
print("ClientToScreen(950,25) =", screen_of(hwnd, SCX, SCY), flush=True)
print("ClientToScreen(0,0)    =", screen_of(hwnd, 0, 0), flush=True)

print("\n前台 =", force_foreground(hwnd), flush=True)
u32.SetCursorPos(*screen_of(hwnd, 1300, 980))
time.sleep(1.0)
im = shot("base")
i0 = ink(im)
print("① 初始列表墨迹 =", i0, " 右端亮像素 =", bright_right(im), flush=True)
print("  弹窗窗口 =", popups(APP_PID), flush=True)

for tag, dy in (("A y=25", 0), ("B y=64", 39)):
    sx, sy = screen_of(hwnd, SCX, SCY + dy)
    print("\n=== %s  client=(%d,%d) screen=(%d,%d) ===" % (tag, SCX, SCY + dy, sx, sy), flush=True)
    left_click_at(sx, sy)
    type_wchar(hwnd, "机器")
    time.sleep(0.9)
    im2 = shot(tag.replace(" ", "").replace("=", ""))
    i2 = ink(im2)
    b2 = bright_right(im2)
    print("  投字后墨迹=%s（初始 %s）右端亮像素=%s → 应用%s反应"
          % (i2, i0, b2, "有" if abs(i2 - i0) > 60 or b2 > 6 else "没"), flush=True)
    key_tap(0x41, ctrl=True)           # Ctrl+A
    key_tap(0x2E)                      # Delete 清空
    time.sleep(0.8)

print("\n=== ⑥ 真键盘打字（keybd_event，非 WM_CHAR 投消息）===", flush=True)
key_tap(0x1B)
time.sleep(0.5)
sx, sy = screen_of(hwnd, SCX, SCY)
left_click_at(sx, sy)
for _ in range(3):
    key_tap(0x5A)                      # 'Z' ×3 → 应筛到 ZZZ-005
    time.sleep(0.15)
time.sleep(1.0)
im3 = shot("realtyped")
i3 = ink(im3)
b3 = bright_right(im3)
print("  真键盘打 ZZZ 后：列表墨迹=%s（初始 %s）右端亮像素=%s" % (i3, i0, b3), flush=True)
if im3 is not None:
    box = (max(0, SCX - SW // 2), max(0, SCY - SH // 2),
           min(im3.width, SCX + SW // 2), min(im3.height, SCY + SH // 2))
    im3.crop(box).save(os.path.join(SHOTS, "v2014d_searchbox.png"))
    print("  图 v2014d_searchbox.png（搜索框本体）", flush=True)

print("\n=== ⑦ 右键搜索框（此时框里有字）===", flush=True)
key_tap(0x1B)
time.sleep(0.4)
b = popups(APP_PID)
right_click_at(*screen_of(hwnd, SCX, SCY))
time.sleep(0.8)
a = popups(APP_PID)
print("  窗口数 %d → %d，新增 %s" % (len(b), len(a), [x for x in a if x not in b]), flush=True)

log = os.path.join(TEMP, "index_data", "logs", "app.log")
if os.path.exists(log):
    print("\n---- app.log（尾部 12 行）----", flush=True)
    for ln in open(log, encoding="utf-8", errors="replace").read().splitlines()[-12:]:
        print("  ", ln, flush=True)

key_tap(0x1B)
subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
print("\nDIAG2_DONE", flush=True)
