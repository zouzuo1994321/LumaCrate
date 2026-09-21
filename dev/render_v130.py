# -*- coding: utf-8 -*-
"""v1.13.0 定向渲染：8 列影片墙 / 文件夹视图 / 设置四页（导航菜单行距·数据源完整描述·名称框样式·数据与日志）。

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

TMP = tempfile.mkdtemp(prefix="lmc_render_v130_")
import database as db
import scanner as scanner_mod
import config as cfg

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")

import applog
_LOG_TMP = os.path.join(TMP, "logs")
os.makedirs(_LOG_TMP, exist_ok=True)
applog.log_dir = lambda: _LOG_TMP

from main_window import MainWindow, load_style

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

OUT = os.path.join(ROOT, "dev", "screenshots_v130")
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
          "肖申克的救赎", "控方证人", "十二怒汉", "美丽人生", "教父", "低俗小说"]
COLORS = ["#2b3a55", "#5a4326", "#1b2a4a", "#26332b", "#3a2b4a", "#4a3a2b",
          "#2b4a3a", "#4a2b3a", "#3a4a2b", "#2b3a4a", "#4a3a4a", "#3a2b2b",
          "#2b4a4a", "#4a4a2b", "#3a3a5a", "#5a2b2b", "#2b5a3a"]

LIB = os.path.join(TMP, "我的电影")
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

db.init_db()
scanner_mod.scan_library(LIB, library_name="我的电影")
cfg.get_settings().add_library("我的电影", "电影", [LIB])
cfg.get_settings().save()

load_style(app)
win = MainWindow()
win.resize(1920, 1000)
win.show()
app.processEvents()


def shot(widget, name):
    for _ in range(3):
        app.processEvents()
    widget.grab().save(os.path.join(OUT, name))
    print("saved", name)


# 1) 影片墙：每行 8 个
win.go(lambda: win._page("我的电影（每行 8 个）", win._grid(db.search_media())))
shot(win, "01_wall_8_cols.png")

# 2) 文件夹视图（含右键提示）
win.go(win._view_folders)
shot(win, "02_folders.png")

# 3-6) 设置四页
from ui_settings import SettingsDialog
sd = SettingsDialog(win)
sd.resize(1080, 860)
sd.show()
app.processEvents()

sd._show("个性化设置"); app.processEvents(); shot(sd, "03_settings_personal.png")
sd._show("演员刮削"); app.processEvents(); shot(sd, "04_settings_scraper.png")
sd._show("服务管理"); app.processEvents(); shot(sd, "05_settings_service.png")
sd._show("数据与日志"); app.processEvents(); shot(sd, "06_settings_data.png")

print("OUT:", OUT)
