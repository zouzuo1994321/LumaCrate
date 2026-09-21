# -*- coding: utf-8 -*-
"""真机判定：主窗口是否真的「半透明 / 磨砂」。

原理（二值、不受界面内容干扰）：
  1) 先铺一块**纯白**背景板（frameless 顶级窗口，覆盖屏幕）
  2) 主窗口叠在正中间
  3) 用 Win32 GetWindowRect 拿到窗口的**物理像素**矩形（避开 DPR 换算坑）
  4) 在矩形内部（内缩 80px）密集采样，统计平均亮度：
     - 磨砂玻璃生效 → 白底透上来，平均亮度明显偏高（> 60）
     - 不透明        → 页面底色 rgba(13,11,10) 合成到黑底 ≈ 10~20
  环境变量：
     LMC_FRAMELESS=1    建窗前设 FramelessWindowHint（Qt 在 Windows 上要求无边框才可透明）
     LMC_FORCE_WCA=1    跳过 DWM 系统背景材质，直接走 WCA 亚克力
     LMC_NO_BACKDROP=1  完全不开系统模糊
"""
import ctypes
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QGuiApplication, QPainter, QColor
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

import database as db
import config as cfg
from main_window import MainWindow, load_style

TMP = tempfile.mkdtemp(prefix="lmc_glass_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
db.init_db()

OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)
TAG = (sys.argv[1] if len(sys.argv) > 1 else "run")


class WhiteBoard(QWidget):
    """纯白背景板：任何透出来的东西都会把窗口内部亮度显著抬高。"""

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)
        scr = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(scr.x() + 40, scr.y() + 40, scr.width() - 80, scr.height() - 160)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(255, 255, 255))
        p.end()


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def window_rect(widget):
    r = _RECT()
    ctypes.windll.user32.GetWindowRect(ctypes.c_void_p(int(widget.winId())), ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


board = WhiteBoard()
board.show()
for _ in range(5):
    app.processEvents()

load_style(app, cfg.get_settings().appearance)
win = MainWindow()
win.resize(1100, 680)
win.show()
for _ in range(10):
    app.processEvents()
time.sleep(1.6)
for _ in range(10):
    app.processEvents()

l, t, r, b = window_rect(win)
print(f"[{TAG}] 窗口物理矩形 = ({l},{t})-({r},{b})  尺寸 {r-l}x{b-t}")
print(f"[{TAG}] backdrop = {getattr(win, '_backdrop_info', None)}")

shot = QGuiApplication.primaryScreen().grabWindow(0).toImage()
shot.save(os.path.join(OUT, f"glass_probe_{TAG}.png"))
print(f"[{TAG}] 抓屏尺寸 = {shot.width()}x{shot.height()}")

# 内缩 80px，避开边框与自绘顶部栏，密集采样
lum = []
for y in range(t + 120, b - 80, 24):
    for x in range(l + 80, r - 80, 24):
        if 0 <= x < shot.width() and 0 <= y < shot.height():
            c = shot.pixelColor(x, y)
            lum.append(0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())

avg = sum(lum) / len(lum) if lum else 0
mx = max(lum) if lum else 0
print(f"[{TAG}] 采样 {len(lum)} 点：平均亮度 {avg:.1f}，最高 {mx:.1f}")
print(f"[{TAG}] 判定 -> " + ("★ 半透明/磨砂生效（白底透上来了）" if avg > 60
                            else "不透明（白底完全被挡住）"))

win.close()
board.close()
print(f"[{TAG}] done")
