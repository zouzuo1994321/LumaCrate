# -*- coding: utf-8 -*-
"""v1.15.0 定向渲染：分组影片墙（选集角标）/ 详情页选集区块 / 普通片（无选集对比）。

全部用临时库 + 临时 settings.json + 临时日志目录，不污染真实数据。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor, QLinearGradient, QPainter, QFontDatabase, QFont
from PySide6.QtCore import QRect

app = QApplication(sys.argv)

TMP = tempfile.mkdtemp(prefix="lmc_render_v150_")
import database as db
import scanner as scanner_mod
import config as cfg

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")

import applog
_LOG_TMP = os.path.join(TMP, "logs")
os.makedirs(_LOG_TMP, exist_ok=True)
applog.log_dir = lambda: _LOG_TMP

from main_window import MainWindow, load_style, LazyGrid

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

OUT = os.path.join(ROOT, "dev", "screenshots_v150")
os.makedirs(OUT, exist_ok=True)


def poster(path, c1, c2, w=158, h=236):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(c1)); g.setColorAt(1, QColor(c2))
    p.fillRect(QRect(0, 0, w, h), g); p.end()
    img.save(path)


LIB = os.path.join(TMP, "我的电影")
os.makedirs(LIB, exist_ok=True)

# 6 部普通电影
NORMAL = ["乐来越爱你", "沙丘", "星际穿越", "寄生虫", "千与千寻", "海上钢琴师"]
NC = ["#2b3a55", "#5a4326", "#1b2a4a", "#26332b", "#3a2b4a", "#4a3a2b"]
for i, t in enumerate(NORMAL):
    d = os.path.join(LIB, f"{t}.{2000 + i}")
    os.makedirs(d, exist_ok=True)
    poster(os.path.join(d, "poster.jpg"), NC[i], "#0f0d0c")
    open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8").write(
        f"<movie><title>{t}</title><year>{2000 + i}</year><rating>8.0</rating>"
        f"<genre>剧情</genre><plot>预览用简介。</plot><thumb>poster.jpg</thumb>"
        f"<actor><name>演员{i}</name><role>主角</role></actor></movie>")
    open(os.path.join(d, f"{t}.mkv"), "w").write("x" * 1000)

# CD 连续序号自动归类（选集）：两组
CDSETS = [
    ("OLM-256", 3, "#7a2b4a"),
    ("ABP-123", 2, "#2b5a3a"),
]
for code, n, col in CDSETS:
    d = os.path.join(LIB, f"{code} ({2021})")
    os.makedirs(d, exist_ok=True)
    for cd in range(1, n + 1):
        open(os.path.join(d, f"{code} CD{cd}.mkv"), "w").write("x" * 1000)
    # 海报只给 cd1（模拟真实：cd2… 常无封面，代表应借用兄弟分片的海报）
    poster(os.path.join(d, f"{code} CD1-poster.jpg"), col, "#0f0d0c")

db.init_db()
scanner_mod.scan_library(LIB, library_name="我的电影")

s = cfg.get_settings()
s.add_library("我的电影", "电影", [LIB])
s.save()
cfg._SETTINGS = None

load_style(app)
win = MainWindow()
win.resize(1920, 1000)
win.show()
app.processEvents()


def shot(widget, name, wait_ms=220):
    import time
    t0 = time.time()
    while (time.time() - t0) * 1000 < wait_ms:
        app.processEvents()
        time.sleep(0.01)
    widget.grab().save(os.path.join(OUT, name))
    print("saved", name)


def pump_until(widget, cond, timeout=20):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


# 1) 分组影片墙：cd 代表卡片带「选集 N」角标
win.go(lambda: win._lib_view(cfg.get_settings().library("我的电影")))
page = win.stack.currentWidget()
grid = page.findChild(LazyGrid)
pump_until(win, lambda: grid and grid._loaded >= grid._total)
shot(win, "01_grouped_wall.png")

# 2) 详情页：选集区块（CD1/CD2/CD3 可点击播放）
repA = [m for m in db.search_media(top_only=True, library="我的电影")
        if "OLM" in (m.get("title") or "")][0]
win._open_media(repA)
app.processEvents()
shot(win, "02_detail_parts.png")

# 3) 普通片（无选集，对比）
normal = [m for m in db.search_media(top_only=True, library="我的电影")
          if (m.get("title") or "") == "沙丘"][0]
win._open_media(normal)
app.processEvents()
shot(win, "03_detail_normal.png")

print("OUT:", OUT)
