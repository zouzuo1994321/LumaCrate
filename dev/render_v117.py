# -*- coding: utf-8 -*-
"""v1.17.0 定向渲染：文件夹卡片视图 / 筛选排序可收缩 / 卡片直接播放按钮。

全部用临时库 + 临时 settings.json + 临时日志目录，不污染真实数据。
运行：python -u -c "import runpy; runpy.run_path(r'<本文件>', run_name='__main__')"
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor, QLinearGradient, QPainter, QFontDatabase, QFont
from PySide6.QtCore import QRect

app = QApplication(sys.argv)

TMP = tempfile.mkdtemp(prefix="lmc_render_v117_")
import database as db
import config as cfg

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")

import applog
_LOG_TMP = os.path.join(TMP, "logs")
os.makedirs(_LOG_TMP, exist_ok=True)
applog.log_dir = lambda: _LOG_TMP

from main_window import MainWindow, load_style, LazyGrid, FacetBar, PosterCard

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

OUT = os.path.join(ROOT, "dev", "screenshots_v117")
os.makedirs(OUT, exist_ok=True)


def poster(path, c1, c2, w=158, h=236):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(c1)); g.setColorAt(1, QColor(c2))
    p.fillRect(QRect(0, 0, w, h), g); p.end()
    img.save(path)


LIB = os.path.join(TMP, "我的影视")
os.makedirs(LIB, exist_ok=True)
GHOST = os.path.join(TMP, "已搬迁的盘")  # 故意不存在 → 演示红色「!」

MOVIES = [
    ("盗梦空间", 2010, "剧情", "美国", 8.8, 1),
    ("千与千寻", 2001, "动画", "日本", 9.4, 0),
    ("寄生虫", 2019, "剧情", "韩国", 8.6, 1),
    ("教父", 1972, "犯罪", "美国", 9.3, 0),
    ("霸王别姬", 1993, "剧情", "中国大陆", 9.6, 1),
    ("肖申克的救赎", 1994, "剧情", "美国", 9.7, 1),
]
for i, (t, y, g, c, r, fav) in enumerate(MOVIES):
    d = os.path.join(LIB, f"{t}.{y}")
    os.makedirs(d, exist_ok=True)
    poster(os.path.join(d, "poster.jpg"), "#3a2b4a", "#0f0d0c")
    open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8").write(
        f"<movie><title>{t}</title><year>{y}</year><rating>{r}</rating>"
        f"<genre>{g}</genre><country>{c}</country><plot>预览用简介。</plot>"
        f"<thumb>poster.jpg</thumb></movie>")
    if fav:
        open(os.path.join(d, f"{t}.mkv"), "w").write("x" * 1000)

db.init_db()
for i, (t, y, g, c, r, fav) in enumerate(MOVIES):
    db.upsert_media_by_path(
        mode="overwrite", title=t, sort_title=t, kind="movie",
        file_path=os.path.join(LIB, f"{t}.{y}", f"{t}.mkv"),
        library="我的影视", year=y or None, genres=g, country=c,
        rating=r, favorite=1 if fav else 0,
        poster=os.path.join(LIB, f"{t}.{y}", "poster.jpg"),
        nfo_path=os.path.join(LIB, f"{t}.{y}", "movie.nfo"),
        collection=("经典合集" if fav else ""))

s = cfg.get_settings()
s.add_library("我的影视", "电影", [LIB.replace(os.sep, "/"), GHOST.replace(os.sep, "/")])
s.save()
cfg._SETTINGS = None

load_style(app)
win = MainWindow()
win.resize(1920, 1000)
win.show()
app.processEvents()


def shot(widget, name, wait_ms=300):
    t0 = time.time()
    while (time.time() - t0) * 1000 < wait_ms:
        app.processEvents()
        time.sleep(0.01)
    widget.grab().save(os.path.join(OUT, name))
    print("saved", name, flush=True)


def pump_until(widget, cond, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


# 1) 文件夹页：Emby 风格文件夹卡片（拼贴封面 + 朱红名 + 共 N 部），不存在目录标红「!」
cfg.get_settings().set_facet_open(False)
cfg._SETTINGS = None
win.go(lambda: win._view_folders())
app.processEvents()
shot(win, "01_folder_cards.png")

# 2) 影片墙（默认收缩）：头部只留「排序」「筛选」两个小按钮，维度面板收起
cfg.get_settings().set_wall_prefs("sort_title", True, {})
cfg.get_settings().set_facet_open(False)
cfg._SETTINGS = None
win.go(lambda: win._wall_page("我的影视", {"library": "我的影视"}))
page = win.stack.currentWidget()
inner = page.widget()
bar = inner.findChild(FacetBar)
grid = inner.findChild(LazyGrid)
pump_until(win, lambda: grid and grid._loaded >= 1)
shot(win, "02_wall_facet_collapsed.png")
shot(bar, "02b_facet_collapsed_only.png", wait_ms=120)

# 3) 影片墙（展开）：点「筛选」展开维度面板（已无状态/进度两类）
cfg.get_settings().set_facet_open(True)
cfg._SETTINGS = None
win.go(lambda: win._wall_page("我的影视", {"library": "我的影视"}))
page = win.stack.currentWidget()
inner = page.widget()
bar = inner.findChild(FacetBar)
grid = inner.findChild(LazyGrid)
pump_until(win, lambda: grid and grid._loaded >= 1)
shot(win, "03_wall_facet_expanded.png")
shot(bar, "03b_facet_expanded_only.png", wait_ms=120)

# 4) 卡片右下角播放按钮：直接调本地播放器，不进详情页
cards = page.findChildren(PosterCard)
playable = [c for c in cards if c.play_btn is not None]
if playable:
    shot(playable[0], "04_card_play_button.png", wait_ms=120)
    print("playable cards:", len(playable), flush=True)
else:
    print("WARN: 没有可播放卡片", flush=True)

print("OUT:", OUT, flush=True)
