# -*- coding: utf-8 -*-
"""把 v1.11.1 的几个关键窄控件「单独放大渲染」，用来看字形是否被裁切。

不读 PNG（离屏下的 PNG 读取插件不可靠），直接在控件上抓。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QPushButton, QFrame
from PySide6.QtGui import QImage, QColor, QFontDatabase, QFont
from PySide6.QtCore import Qt, QPoint

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_zoom_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow
from ui_settings import SettingsDialog

OUT = os.path.join(ROOT, "dev", "screenshots_v111")
os.makedirs(OUT, exist_ok=True)

Z = 4
made = []


def zoom(widget, name, pad=10):
    src = QImage(widget.width(), widget.height(), QImage.Format_RGB32)
    src.fill(QColor("#14100e"))
    widget.render(src, QPoint(0, 0))
    big = QImage((widget.width() + pad * 2) * Z, (widget.height() + pad * 2) * Z,
                 QImage.Format_RGB32)
    big.fill(QColor("#14100e"))
    from PySide6.QtGui import QPainter
    p = QPainter(big)
    p.drawImage(pad * Z, pad * Z,
                src.scaled(widget.width() * Z, widget.height() * Z,
                           Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    p.end()
    big.save(os.path.join(OUT, name))
    made.append((name, widget.width(), widget.height(), widget.text() if hasattr(widget, "text") else ""))


win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()

dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1000, 940)
dlg.show()
app.processEvents()

# 1) 顶栏 ← →（反馈 3）
zoom(win.back_btn, "z1_back_btn.png")
zoom(win.fwd_btn, "z2_fwd_btn.png")

# 2) 设置·演员刮削页里的按钮（反馈 4 的同源窄按钮 + Primary）
dlg._show("演员刮削")
app.processEvents()
for b in dlg.findChildren(QPushButton):
    t = b.text()
    if t in ("开始刮削", "停止") or "修复历史资料" in t:
        nm = {"开始刮削": "z3_scrape_start.png", "停止": "z4_scrape_stop.png"}.get(
            t, "z5_scrape_repair.png")
        zoom(b, nm)

# 3) 数据源行的 ↑ ↓ / 测试（反馈 4）
cnt = 0
for b in dlg.findChildren(QPushButton):
    if b.text() in ("↑", "↓") and b.maximumWidth() <= 32:
        zoom(b, "z6_src_arrow_%d.png" % cnt)
        cnt += 1
        if cnt >= 2:
            break

# 4) 导航菜单 ↑ ↓（反馈 4 的原图）
cnt = 0
for b in dlg.findChildren(QPushButton):
    if b.text() in ("↑", "↓") and b.maximumWidth() >= 28 and cnt < 2:
        zoom(b, "z7_nav_arrow_%d.png" % cnt)
        cnt += 1

print("输出:", OUT)
for m in made:
    print("  %-26s %3dx%-3d  %r" % m)
print("done %d" % len(made))
