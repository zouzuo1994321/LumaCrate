# -*- coding: utf-8 -*-
"""v1.18.0 影片墙工具行渲染验证：排序/筛选 左对齐、加载更多/刷新一下 右对齐、同行。

临时库 + 临时 settings + 临时日志，不污染真实数据。
运行：python -u -c "import runpy; runpy.run_path(r'<本文件>', run_name='__main__')"
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

TMP = tempfile.mkdtemp(prefix="lmc_render_v118_")
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

OUT = os.path.join(ROOT, "dev", "screenshots_v118")
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
# 80 部，保证「加载更多」常显（batch=60 < 80），随机排序下「刷新一下」也常显
GENRES = ["剧情", "动作", "动画", "喜剧", "科幻", "犯罪", "爱情", "悬疑"]
COUNTRIES = ["美国", "日本", "韩国", "中国大陆", "英国", "法国"]
MOVIES = []
for i in range(80):
    t = f"影片{i:02d}"
    y = 1990 + (i % 35)
    g = GENRES[i % len(GENRES)]
    c = COUNTRIES[i % len(COUNTRIES)]
    r = round(6.0 + (i % 40) / 10.0, 1)
    fav = 1 if i % 3 == 0 else 0
    MOVIES.append((t, y, g, c, r, fav))
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
s.add_library("我的影视", "电影", [LIB.replace(os.sep, "/")])
s.save()
cfg._SETTINGS = None

load_style(app)
win = MainWindow()
win.resize(1920, 1000)
win.show()
app.processEvents()

# 进影片墙（随机排序 → 刷新一下 常显；收缩态）
cfg.get_settings().set_wall_prefs("random", True, {})
cfg.get_settings().set_facet_open(False)
cfg._SETTINGS = None
win.go(lambda: win._wall_page("我的影视", {"library": "我的影视"}))
app.processEvents()
page = win.stack.currentWidget()
inner = page.widget()
bar = inner.findChild(FacetBar)
grid = inner.findChild(LazyGrid)
sort_btn = bar.sort_btn
filter_btn = bar.filter_btn
more_btn = grid.more_btn
refresh_btn = grid.refresh_btn

# 布局顺序断言（不依赖可见性 / 加载进度，稳健）
toolbar = sort_btn.parent()
lay = toolbar.layout()
assert lay is not None, "工具行无布局"
assert lay.indexOf(sort_btn) == 0, "排序应在工具行最左"
assert lay.indexOf(filter_btn) == 1, "筛选应在排序右侧"
assert lay.indexOf(more_btn) > lay.indexOf(filter_btn), "加载更多应在筛选右侧"
assert lay.indexOf(refresh_btn) == lay.count() - 1, "刷新一下应在工具行最右"
print("LAYOUT_OK count=%d sort@%d filter@%d more@%d refresh@%d"
      % (lay.count(), lay.indexOf(sort_btn), lay.indexOf(filter_btn),
         lay.indexOf(more_btn), lay.indexOf(refresh_btn)))

import time
t0 = time.time()
while time.time() - t0 < 1.5:          # 让卡片完成绘制再截图
    app.processEvents()
    time.sleep(0.02)
cards = page.findChildren(PosterCard)
print("cards=%d loaded=%d" % (len(cards), grid._loaded))
assert len(cards) >= 1, "影片卡未渲染"
win.grab().save(os.path.join(OUT, "01_wall_toolbar.png"))
print("saved 01_wall_toolbar.png")
print("OUT:", OUT)
