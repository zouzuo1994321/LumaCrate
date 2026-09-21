# -*- coding: utf-8 -*-
"""v1.16.0 定向渲染：多维 chip 筛选面板 FacetBar（含随机排序的「刷新一下」按钮）/ 文件夹页显示子目录。

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

TMP = tempfile.mkdtemp(prefix="lmc_render_v116_")
import database as db
import config as cfg

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")

import applog
_LOG_TMP = os.path.join(TMP, "logs")
os.makedirs(_LOG_TMP, exist_ok=True)
applog.log_dir = lambda: _LOG_TMP

from main_window import MainWindow, load_style, LazyGrid, FacetBar

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

OUT = os.path.join(ROOT, "dev", "screenshots_v116")
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
MOVIES = [
    ("盗梦空间", 2010, "剧情", "美国", 8.8, 1),
    ("千与千寻", 2001, "动画", "日本", 9.4, 0),
    ("寄生虫", 2019, "剧情", "韩国", 8.6, 1),
    ("教父", 1972, "犯罪", "美国", 9.3, 0),
    ("霸王别姬", 1993, "剧情", "中国大陆", 9.6, 1),
    ("你的名字", 2016, "动画", "日本", 8.4, 0),
    ("肖申克的救赎", 1994, "剧情", "美国", 9.7, 1),
    ("疯狂的麦克斯", 2015, "动作", "美国", 8.1, 0),
    ("降临", 2016, "科幻", "美国", 7.9, 0),
    ("海蒂和爷爷", 2015, "家庭", "德国", 9.2, 0),
    ("实验短片", 2022, "实验", "巴西", 7.0, 0),   # 触发「风格其他 / 地区其他」
    ("未命名空壳", 0, "", "", 0.0, 0),            # 未识别（无 nfo/年份/画质）
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
        nfo_path=os.path.join(LIB, f"{t}.{y}", "movie.nfo"),
        collection=("经典合集" if fav else ""))

# 大数据库：300 条 → 首批只载一部分，「加载更多」与「刷新一下」并排可见
BIGDIR = os.path.join(TMP, "大数据")
os.makedirs(BIGDIR, exist_ok=True)
for i in range(300):
    db.upsert_media_by_path(
        mode="overwrite", title=f"影片{i:03d}", sort_title=f"{i:03d}", kind="movie",
        file_path=os.path.join(BIGDIR, f"b{i}.mkv"), library="大数据",
        year=2010 + i % 15, genres="剧情", country="美国",
        rating=7.0 + (i % 20) / 10.0,
        nfo_path=os.path.join(BIGDIR, f"b{i}.nfo"))

# 外置硬盘库：1 条 + 一个已被搬走的目录 → 演示红色「目录不存在」
GHOST = os.path.join(TMP, "已搬迁的盘")
db.upsert_media_by_path(
    mode="overwrite", title="外置片", sort_title="外置片", kind="movie",
    file_path=os.path.join(LIB, "外置片.mkv"), library="外置硬盘", year=2023,
    genres="剧情", country="美国", nfo_path=os.path.join(LIB, "外置片.nfo"))

s = cfg.get_settings()
s.add_library("我的影视", "电影", [LIB])
s.add_library("大数据", "电影", [BIGDIR])
# 外置硬盘：含一个不存在的子目录，用于演示红色「目录不存在」提示
s.add_library("外置硬盘", "电影", [LIB, GHOST])
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


# 1) 多维 chip 筛选面板（普通排序）：展示状态/进度/风格/地区/年份/类型/收藏/评分 平铺 chip
cfg.get_settings().set_wall_prefs("sort_title", True, {})
cfg._SETTINGS = None
win.go(lambda: win._wall_page("我的影视", {"library": "我的影视"}))
page = win.stack.currentWidget()
inner = page.widget()
bar = inner.findChild(FacetBar)
grid = inner.findChild(LazyGrid)
pump_until(win, lambda: grid and grid._loaded >= 1)
shot(win, "01_facet_bar_normal.png")
shot(bar, "01b_facet_bar_only.png", wait_ms=120)

# 2) 随机排序：LazyGrid 顶栏出现「刷新一下」按钮（与「加载更多」并排，点它换种子重洗牌）
cfg.get_settings().set_wall_prefs("random", True, {})
cfg._SETTINGS = None
win.go(lambda: win._wall_page("大数据", {"library": "大数据"}))
page = win.stack.currentWidget()
inner = page.widget()
grid = inner.findChild(LazyGrid)
pump_until(win, lambda: grid and grid._loaded >= 1)
shot(win, "02_random_refresh.png")
# 验证「刷新一下」点击后顺序改变（数据层）
ids_before = [r["id"] for r in db.search_media(library="大数据", sort="random", top_only=True, limit=100)]
grid.refresh_requested.emit()
app.processEvents()
ids_after = [r["id"] for r in db.search_media(library="大数据", sort="random", top_only=True, limit=100)]
print("刷新一下 重洗牌:", "顺序改变" if ids_before != ids_after else "未改变", flush=True)

# 3) 文件夹页：列出每个媒体库「里面加入的目录」，不存在的标红
win.go(lambda: win._view_folders())
app.processEvents()
shot(win, "03_folders_subdirs.png")

print("OUT:", OUT, flush=True)
