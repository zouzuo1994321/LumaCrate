# -*- coding: utf-8 -*-
"""v1.46.11 探针：首页悬停到底弹出了几个浮层？（真机窗口，不用离屏）

做法：临时库 + HomeListView 真窗口 → SetCursorPos 把鼠标停在一行上
→ 1.5s 后枚举「本进程的所有可见顶层窗口」→ 抓整屏。
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/hover_probe_v14611"
os.makedirs(TMP, exist_ok=True)
os.environ.pop("QT_QPA_PLATFORM", None)
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QMainWindow

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import applog

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import database as db
import main_window as mw
import ui_home

db.db_path = lambda: os.path.join(TMP, "index_data", "probe.db")
os.makedirs(os.path.join(TMP, "index_data"), exist_ok=True)
db.init_db()

POSTER = os.path.join(TMP, "poster.jpg")
if not os.path.exists(POSTER):
    pm = QPixmap(300, 450)
    pm.fill(QColor(90, 60, 50))
    pm.save(POSTER)

titles = [("DOJN-031 テスト作品 出演者A", 2026, "01:12:00"),
          ("DOJN-027 二番目の作品 出演者B", 2026, "00:57:00"),
          ("DMVE-457 [4K] 三番目の作品", 2025, "01:30:00"),
          ("ABC-123 四番目の作品", 2024, "02:00:00"),
          ("XYZ-999 五番目の作品", 2023, "01:45:00")]
for i, (t, y, rt) in enumerate(titles):
    db.upsert_media_by_path(mode="overwrite", kind="movie", title=t, year=y,
                            runtime=rt, file_path=os.path.join(TMP, "%02d.mp4" % i),
                            library="演示库", genres="アイドル,巨乳", studio="同人配信",
                            premiere="2026-10-01", rating=4.5, poster=POSTER,
                            file_size=1234567)

mw.load_style(app, cfg.DEFAULT_APPEARANCE)
lv = ui_home.HomeListView()
win = QMainWindow()
win.setCentralWidget(lv)
win.resize(1600, 900)
win.show()
win.move(120, 80)
for _ in range(40):
    app.processEvents()
    time.sleep(0.02)

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32

# 光标停在第 3 行
for _ in range(200):
    app.processEvents(); time.sleep(0.02)
    if getattr(lv, "_filled", 0) >= 5:
        break
_old = lv.table.verticalScrollBar().value()
lv.table.scrollToItem(lv.table.item(2, 0))
for _ in range(20):
    app.processEvents(); time.sleep(0.02)
rect = lv.table.visualItemRect(lv.table.item(2, 0))
gp = lv.table.viewport().mapToGlobal(rect.center())
u32.SetCursorPos(gp.x(), gp.y())
print("光标:", gp.x(), gp.y(), flush=True)
_vp = wt.HWND(int(lv.table.viewport().winId()))
_cp = lv.table.viewport().mapFromGlobal(gp)
_lp = ((_cp.y() & 0xFFFF) << 16) | (_cp.x() & 0xFFFF)
for _ in range(4):
    u32.SendMessageW(_vp, 0x0200, 0, _lp)     # WM_MOUSEMOVE
    time.sleep(0.08)
print("行数=%d 已填=%s" % (lv.table.rowCount(), getattr(lv, "_filled", None)), flush=True)
if not lv._preview.isVisible():
    print("[直接驱动] _on_cell_entered(2, 0)", flush=True)
    lv._on_cell_entered(2, 0)


def settle(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.015)


settle(1800)

PID = os.getpid()
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
rows = []


def cb(hwnd, _):
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == PID and u32.IsWindowVisible(hwnd):
        rc = wt.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(rc))
        cls = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(hwnd, cls, 256)
        n = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        rows.append((int(hwnd), cls.value, buf.value,
                     (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top),
                     bool(u32.IsWindowEnabled(hwnd))))
    return True


u32.EnumWindows(EnumProc(cb), 0)
print("== 本进程可见窗口 %d 个 ==" % len(rows), flush=True)
for r in rows:
    print("  hwnd=%s cls=%-38s title=%-22r box=%s" % (r[0], r[1], r[2][:20], r[3]), flush=True)

# 浮层（HoverPreview）自己的状态
pv = lv._preview
print("HoverPreview: visible=%s geo=%s size=%s" %
      (pv.isVisible(), pv.geometry(), (pv.width(), pv.height())), flush=True)
print("HoverPreview 子标签高度: title=%d sub=%d info=%d" %
      (pv.title.height(), pv.sub.height(), pv.info.height()), flush=True)
print("hover_media =", (lv._hover_media or {}).get("title"), flush=True)

# 抓整屏（含浮层，浮层是独立顶层窗口，窗口内 grab 抓不到）
class BIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

g32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
g32.CreateCompatibleDC.restype = ctypes.c_void_p
g32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
g32.CreateCompatibleBitmap.restype = ctypes.c_void_p
g32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
g32.SelectObject.restype = ctypes.c_void_p
g32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                       ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, wt.DWORD]
g32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.UINT, wt.UINT,
                          ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u32.GetDC.argtypes = [wt.HWND]; u32.GetDC.restype = ctypes.c_void_p
u32.ReleaseDC.argtypes = [wt.HWND, ctypes.c_void_p]
u32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.SendMessageW.restype = ctypes.c_void_p
g32.DeleteObject.argtypes = [ctypes.c_void_p]
g32.DeleteDC.argtypes = [ctypes.c_void_p]

wr = wt.RECT()
u32.GetWindowRect(wt.HWND(int(win.winId())), ctypes.byref(wr))
x, y, w, h = wr.left, wr.top, wr.right - wr.left, wr.bottom - wr.top
from PIL import Image
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
g32.SelectObject(mdc, old); g32.DeleteObject(bmp); g32.DeleteDC(mdc); u32.ReleaseDC(0, hdc)
out = os.path.join(TMP, "hover_screen.png")
img.save(out)
print("截图:", out, img.size, flush=True)

win.close()
print("PROBE_DONE", flush=True)
