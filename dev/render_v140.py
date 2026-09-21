# -*- coding: utf-8 -*-
"""v1.14.0 定向渲染：分页影片墙（含进度与筛选排序条）/ 演员库筛选排序 /
设置-媒体库行高（按钮完整）/ 库名后总数 / 全部库页。

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

app = QApplication(sys.argv)

TMP = tempfile.mkdtemp(prefix="lmc_render_v140_")
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

OUT = os.path.join(ROOT, "dev", "screenshots_v140")
os.makedirs(OUT, exist_ok=True)


def poster(path, c1, c2, w=158, h=236):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(c1)); g.setColorAt(1, QColor(c2))
    p.fillRect(0, 0, w, h, g); p.end()
    img.save(path)


TITLES = ["乐来越爱你", "沙丘", "星际穿越", "寄生虫", "千与千寻", "海上钢琴师",
          "这个杀手不太冷", "楚门的世界", "盗梦空间", "搏击俱乐部", "阿甘正传",
          "肖申克的救赎", "控方证人", "十二怒汉", "美丽人生", "教父", "低俗小说",
          "狮子王", "无间道", "花样年华", "阳光灿烂的日子", "大话西游", "活着",
          "霸王别姬", "牯岭街少年杀人事件", "一一", "悲情城市", "卧虎藏龙", "英雄",
          "刺客聂隐娘", "隐入尘烟", "宇宙探索编辑部", "河边的错误", "漫长的季节",
          "平原上的摩西", "路边野餐", "地球最后的夜晚", "日照重庆", "推拿", "风中有朵雨做的云"]
COLORS = ["#2b3a55", "#5a4326", "#1b2a4a", "#26332b", "#3a2b4a", "#4a3a2b",
          "#2b4a3a", "#4a2b3a", "#3a4a2b", "#2b3a4a", "#4a3a4a", "#3a2b2b",
          "#2b4a4a", "#4a4a2b", "#3a3a5a", "#5a2b2b", "#2b5a3a"]

# 两个库：主库 40 部（足够撑出滚动条 → 能看到「读取进度」与「加载更多」）
LIB = os.path.join(TMP, "我的电影")
LIB2 = os.path.join(TMP, "纪录片")
for i, t in enumerate(TITLES):
    d = os.path.join(LIB, f"{t}.{2000 + i}")
    os.makedirs(d, exist_ok=True)
    poster(os.path.join(d, "poster.jpg"), COLORS[i % len(COLORS)], "#0f0d0c")
    open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8").write(
        f"""<?xml version="1.0"?>
<movie><title>{t}</title><year>{2000 + i}</year><rating>{7.0 + (i % 3) * 0.5:.1f}</rating>
<genre>剧情</genre><plot>预览用简介。</plot><thumb>poster.jpg</thumb>
<actor><name>演员{i}</name><role>主角</role></actor></movie>""")
    open(os.path.join(d, f"{t}.mkv"), "w").write("x" * 1000)

os.makedirs(LIB2, exist_ok=True)
for i, t in enumerate(("蓝色星球", "地球脉动", "海豚湾")):
    d = os.path.join(LIB2, f"{t}")
    os.makedirs(d, exist_ok=True)
    poster(os.path.join(d, "poster.jpg"), COLORS[(i + 5) % len(COLORS)], "#0f0d0c")
    open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8").write(
        f"""<?xml version="1.0"?>
<movie><title>{t}</title><year>{2015 + i}</year><rating>9.2</rating>
<genre>纪录片</genre><plot>预览用简介。</plot><thumb>poster.jpg</thumb>
<actor><name>旁白{i}</name><role>旁白</role></actor></movie>""")
    open(os.path.join(d, f"{t}.mkv"), "w").write("x" * 1000)

db.init_db()
scanner_mod.scan_library(LIB, library_name="我的电影")
scanner_mod.scan_library(LIB2, library_name="纪录片")
# 让一部分片子有用户评分 / 收藏，才能看出筛选差异
for i, m in enumerate(db.search_media(limit=100)):
    if i % 3 == 0:
        db.set_user_rating(m["id"], 6.0 + (i % 4))
    if i % 4 == 0:
        db.toggle_favorite(m["id"])

s = cfg.get_settings()
s.add_library("我的电影", "电影", [LIB])
s.add_library("纪录片", "纪录片", [LIB2])
s.save()
cfg._SETTINGS = None

load_style(app)
win = MainWindow()
win.resize(1920, 1000)
win.show()
app.processEvents()


def shot(widget, name, wait_ms=180):
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


# 1) 媒体库页：标题含总数 + 筛选排序条 + 读取进度
win.go(lambda: win._lib_view(cfg.get_settings().library("我的电影")))
page = win.stack.currentWidget()
grid = page.findChild(LazyGrid)
# 只载入首批 → 截图里能看到「正在读取… 已加载 x / 40」与进度条
app.processEvents()
shot(win, "01_lib_wall_progress.png")

# 2) 全部载入后的完整影片墙
pump_until(win, lambda: grid and grid._loaded >= grid._total)
win.go(lambda: win._lib_view(cfg.get_settings().library("我的电影")))
shot(win, "02_lib_wall_loaded.png")

# 3) 筛选生效：只看已收藏
cfg.get_settings().set_wall_prefs("rating", False, {"favorite": True})
cfg._SETTINGS = None
win.go(lambda: win._lib_view(cfg.get_settings().library("我的电影")))
shot(win, "03_lib_wall_filtered.png")

# 4) 演员库（筛选 + 排序条）
win.go(win._view_actors)
shot(win, "04_actors_filter_sort.png")

# 5) 文件夹视图：库名后项数
win.go(win._view_folders)
shot(win, "05_folders_counts.png")

# 6-7) 设置：服务管理（媒体库行高 / 按钮完整）+ 侧边栏库名计数
from ui_settings import SettingsDialog
sd = SettingsDialog(win)
sd.resize(1080, 860)
sd.show()
app.processEvents()
sd._show("服务管理")
app.processEvents()
shot(sd, "06_settings_library_rows.png")

cfg.get_settings().set_wall_prefs("sort_title", True, {})
cfg._SETTINGS = None
win._apply_settings()
app.processEvents()
shot(win, "07_sidebar_counts.png")

print("OUT:", OUT)
