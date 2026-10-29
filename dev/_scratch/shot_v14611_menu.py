# -*- coding: utf-8 -*-
"""v1.46.11 出图：把右键菜单真的画出来（真窗口 + 真实 QSS），供人工确认。"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/shot_v14611"
os.makedirs(TMP, exist_ok=True)
os.environ.pop("QT_QPA_PLATFORM", None)
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import QPoint, QItemSelectionModel as QISM
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
DB = os.path.join(TMP, "index_data", "p.db")
os.makedirs(os.path.join(TMP, "index_data"), exist_ok=True)
if os.path.exists(DB):
    DB = os.path.join(TMP, "index_data", "p_%d.db" % time.time())
db.db_path = lambda: DB
db.init_db()

import main_window as mw
import ui_home

POSTER = os.path.join(TMP, "poster.jpg")
pm = QPixmap(300, 450)
pm.fill(QColor(96, 66, 56))
pm.save(POSTER)

for i, t in enumerate([("SSIS-872 激イキ92回！痙攣3600cc！", 2023),
                       ("MIDE-823 三上悠亜と相沢みなみ", 2024),
                       ("ABF-394 理不尽インモラルNTR 三佳詩", 2026),
                       ("DMVE-457 [4K] クラスの1軍ギャル", 2025)]):
    db.upsert_media_by_path(mode="overwrite", kind="movie", title=t[0], year=t[1],
                            runtime="01:59:00", rating=4.4,
                            file_path=os.path.join(TMP, "%02d.mp4" % i),
                            library="Javlibrary", genres="アイドル,巨乳",
                            studio="エスワン", premiere="2026-10-01", poster=POSTER)

mw.load_style(app, cfg.DEFAULT_APPEARANCE)
lv = ui_home.HomeListView()
win = QMainWindow()
win.setCentralWidget(lv)
win.resize(1300, 820)
win.show()
win.move(140, 90)
for _ in range(80):
    app.processEvents()
    time.sleep(0.01)

# 先把自己顶到前台，否则截图里全是别的窗口
_u = ctypes.windll.user32
_u.keybd_event(0x12, 0, 0, 0)
_u.keybd_event(0x12, 0, 2, 0)
win.raise_()
win.activateWindow()
_u.BringWindowToTop(int(win.winId()))
_u.SetForegroundWindow(int(win.winId()))
for _ in range(40):
    app.processEvents()
    time.sleep(0.02)

# 选 3 行 → 菜单应带「（3 项）」
lv.table.clearSelection()
_sel = lv.table.selectionModel()
for r in (1, 2, 3):
    _sel.select(lv.table.model().index(r, 0), QISM.Select | QISM.Rows)
for _ in range(30):
    app.processEvents()

medias = lv.selected_medias()
print("选中 %d 项" % len(medias), flush=True)
menu = lv._build_context_menu(medias)
menu.move(win.x() + 420, win.y() + 250)
menu.show()
for _ in range(40):
    app.processEvents()
    time.sleep(0.02)
print("菜单尺寸", menu.size(), "条目", [a.text() for a in menu.actions() if not a.isSeparator()],
      flush=True)

# 抓整屏（菜单是独立顶层窗口）
u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u32.GetDC.argtypes = [wt.HWND]
u32.GetDC.restype = ctypes.c_void_p
u32.ReleaseDC.argtypes = [wt.HWND, ctypes.c_void_p]
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


from PIL import Image
x, y, w, h = win.x() - 20, win.y() - 20, win.width() + 40, win.height() + 40
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
out = os.path.join(TMP, "bulk_menu.png")
img.save(out)
print("截图:", out, img.size, flush=True)

menu.close()
win.close()
print("SHOT_DONE", flush=True)
