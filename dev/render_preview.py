# -*- coding: utf-8 -*-
"""把主界面渲染为 PNG，便于肉眼校验布局。

重要：本脚本使用「临时数据库」，不会读写 index_data/media_center.db（真实索引）。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor, QLinearGradient, QPainter
from PySide6.QtCore import Qt, QPoint

app = QApplication(sys.argv)

import database as db
import scanner as scanner_mod
import config as cfg
from main_window import MainWindow, load_style

TMP = tempfile.mkdtemp(prefix="lmc_prev_")
# 把数据库指向临时文件，避免污染真实索引
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")

OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)


def poster(path, c1, c2, w=300, h=450):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, h); g.setColorAt(0, QColor(c1)); g.setColorAt(1, QColor(c2))
    p.fillRect(0, 0, w, h, g); p.end()
    img.save(path)


def fanart(path, c1, c2, w=1200, h=600):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, w, h); g.setColorAt(0, QColor(c1)); g.setColorAt(1, QColor(c2))
    p.fillRect(0, 0, w, h, g); p.end()
    img.save(path)


def actor(path, c):
    img = QImage(200, 200, QImage.Format_RGB32); img.fill(QColor(c)); img.save(path)


MOVIES = [
    ("La.La.Land.2016.2160p.HDR10.Atmos.TrueHD", "乐来越爱你", 2016, "美国", "喜剧,剧情,爱情",
     7.9, "音乐爱情合集", "#2b3a55", "#7a4a86", ["Emma Stone|Mia", "Ryan Gosling|Sebastian", "Damien Chazelle|Director"]),
    ("Dune.2021.2160p.DV.Atmos", "沙丘", 2021, "美国", "科幻,冒险",
     8.0, "沙丘合集", "#5a4326", "#c08a3e", ["Timothée Chalamet|Paul", "Zendaya|Chani"]),
    ("Interstellar.2014.1080p", "星际穿越", 2014, "美国", "科幻,剧情",
     9.4, "诺兰合集", "#1b2a4a", "#3d6a9e", ["Matthew McConaughey|Cooper", "Anne Hathaway|Brand"]),
    ("Parasite.2019.1080p", "寄生虫", 2019, "韩国", "剧情,惊悚",
     8.7, "", "#26332b", "#5f7d63", ["Song Kang-ho|Ki-taek"]),
]

for key, title, year, country, genre, rating, coll, c1, c2, cast in MOVIES:
    d = os.path.join(TMP, key); os.makedirs(d, exist_ok=True)
    poster(os.path.join(d, "poster.jpg"), c1, c2)
    fanart(os.path.join(d, "fanart.jpg"), c1, c2)
    actors_xml = ""
    for i, a in enumerate(cast):
        name, role = a.split("|")
        actor(os.path.join(d, f"a{i}.jpg"), ["#7a4a86", "#3d6a9e", "#c08a3e", "#5f7d63"][i % 4])
        actors_xml += f"<actor><name>{name}</name><role>{role}</role><thumb>a{i}.jpg</thumb><type>Actor</type></actor>"
    setxml = f"<set><name>{coll}</name></set>" if coll else ""
    open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8").write(f"""<?xml version="1.0"?>
<movie><title>{title}</title><year>{year}</year><runtime>128</runtime>
<country>{country}</country><rating>{rating}</rating><genre>{genre}</genre>
<plot>这是一段用于预览的剧情简介，展示详情页的排版效果。故事围绕主人公展开，情节跌宕起伏。</plot>
{setxml}<uniqueid type="tmdb">100</uniqueid><thumb>poster.jpg</thumb><fanart>fanart.jpg</fanart>
{actors_xml}</movie>""")
    open(os.path.join(d, "movie.mkv"), "w").write("x" * 900000)

db.init_db()
scanner_mod.scan_library(TMP)
db.toggle_favorite(db.movies()[0]["id"])

load_style(app)
win = MainWindow(); win.resize(1600, 900); win.show()
app.processEvents()


def shot(widget, name):
    for _ in range(3):
        app.processEvents()
    widget.grab().save(os.path.join(OUT, name))
    print("saved", name)


shot(win, "01_home_list.png")
win.go(lambda: win._view_grid(db.movies(), "电影")); shot(win, "02_movies_grid.png")
win.go(win._view_actors); shot(win, "03_actors.png")
win.go(lambda: win._view_collections()); shot(win, "04_collections.png")
win.go(lambda: win._view_actor_detail(db.all_people()[0]["id"])); shot(win, "05_actor_detail.png")

# 详情页（横幅：确认没有「黑色底框」）
from ui_hero import HeroView
m = db.movies()[0]
win.go(lambda: HeroView(m, on_open_actor=win._open_actor, on_back=win._back,
                        on_changed=win._refresh_stats))
shot(win, "06_hero_detail.png")

# 首页列表 + 悬停缩略图预览卡
win.go(win._view_home)
app.processEvents()
home = win.stack.currentWidget()
if hasattr(home, "_preview"):
    m0 = home._view[0] if home._view else None
    if m0:
        home._preview.set_media(m0)
        home._preview.popup_at(QPoint(600, 400))
        shot(home._preview, "07_hover_card.png")
        home._hide_preview()
shot(win, "08_home_with_hover.png")

# 列设置对话框
from ui_home import ColumnSettingsDialog
dlg = ColumnSettingsDialog(win)
dlg.show()
shot(dlg, "09_column_settings.png")

# 设置 → 演员刮削页
from ui_settings import SettingsDialog
sd = SettingsDialog(win)
sd.resize(1080, 780)
sd.show()
sd._show("演员刮削")
shot(sd, "10_scraper_settings.png")

# 设置 → 外观（磨砂玻璃 / 经典暗色）
sd._show("个性化")
shot(sd, "11_appearance.png")

print("OUT:", OUT)
