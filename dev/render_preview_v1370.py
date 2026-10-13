# -*- coding: utf-8 -*-
"""v1.37.0 预览出图：把新增的五条行为渲染成 PNG 便于肉眼校验。

使用临时数据库，不读写真实索引。产出：
  v1370_hero_home.png    首页右侧详情（on_back=None）：无顶部空白带 + 演职人员 收藏/置顶 上色
  v1370_cards.png        影片墙卡片：演员/导演 小字 收藏→金、置顶→粗、二者兼有→金粗
  v1370_splash.png       启动画面（默认朱红高亮色）
  v1370_home_border.png  首页（右面板高亮色边框）
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtGui import QImage, QColor, QLinearGradient, QPainter
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

import database as db
import scanner as scanner_mod
import config as cfg
import version as ver
import splash as splash_mod
from main_window import MainWindow, load_style
from ui_hero import HeroView

TMP = tempfile.mkdtemp(prefix="lmc_prev_v1370_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")

OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)


def _img(path, c1, c2, w=300, h=450):
    im = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(im)
    g = QLinearGradient(0, 0, 0, h); g.setColorAt(0, QColor(c1)); g.setColorAt(1, QColor(c2))
    p.fillRect(0, 0, w, h, g); p.end(); im.save(path)


# 一部片：演员 A(收藏) / B(置顶) / 导演 D(收藏+置顶)
d = os.path.join(TMP, "MV")
os.makedirs(d, exist_ok=True)
_img(os.path.join(d, "poster.jpg"), "#2b3a55", "#7a4a86")
_img(os.path.join(d, "fanart.jpg"), "#2b3a55", "#7a4a86", 1200, 600)
actors = [
    "<actor><name>艺人甲</name><role>女主</role><thumb>poster.jpg</thumb><type>Actor</type></actor>",
    "<actor><name>艺人乙</name><role>男主</role><thumb>poster.jpg</thumb><type>Actor</type></actor>",
    "<actor><name>导演丙</name><role>导演</role><thumb>poster.jpg</thumb><type>Director</type></actor>",
]
open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8").write(
    '<?xml version="1.0"?>\n<movie><title>测试影片</title><year>2021</year><runtime>128</runtime>'
    '<country>日本</country><rating>8.3</rating><genre>剧情,爱情</genre>'
    '<plot>一段用于预览的剧情简介，展示详情页排版。情节跌宕起伏，主角是艺人甲与艺人乙。</plot>'
    '<uniqueid type="tmdb">100</uniqueid><thumb>poster.jpg</thumb><fanart>fanart.jpg</fanart>'
    + "".join(actors) + '</movie>')
open(os.path.join(d, "movie.mkv"), "w").write("x" * 900000)

db.init_db()
scanner_mod.scan_library(TMP)

# 给艺人甲 收藏、艺人乙 置顶、导演丙 收藏+置顶
_cast = db.get_cast(db.movies()[0]["id"])
_by_name = {c["name"]: c["id"] for c in _cast}
db.toggle_person_favorite(_by_name["艺人甲"])
db.toggle_person_pinned(_by_name["艺人乙"])
db.toggle_person_favorite(_by_name["导演丙"])
db.toggle_person_pinned(_by_name["导演丙"])

load_style(app)
m = db.movies()[0]

# ---- ① 首页右侧详情（on_back=None）：无顶部空白带 + 演职人员上色 ----
hv = HeroView(m, on_open_actor=None, on_back=None)
box = QWidget(); lay = QVBoxLayout(box); lay.setContentsMargins(0, 0, 0, 0)
lay.addWidget(hv); box.resize(1100, 920); box.show(); app.processEvents()
for _ in range(3):
    app.processEvents()
hv.grab().save(os.path.join(OUT, "v1370_hero_home.png"))
print("saved v1370_hero_home.png")

# ---- ② 影片墙卡片：演员/导演小字上色 ----
win = MainWindow(); win.resize(1600, 900); win.show(); app.processEvents()
win.go(lambda: win._view_grid(db.movies(), "电影"))
for _ in range(4):
    app.processEvents()
win.grab().save(os.path.join(OUT, "v1370_cards.png"))
print("saved v1370_cards.png")

# 单独抓一张卡片放大看小字
card = win.stack.currentWidget()
_cards = card.findChildren(QWidget) if card else []
from main_window import PosterCard
_poster = None
for w in (card.findChildren(PosterCard) if card else []):
    _poster = w
    break
if _poster is not None:
    _pc = QWidget(); _pl = QVBoxLayout(_pc); _pl.setContentsMargins(0, 0, 0, 0)
    _pl.addWidget(_poster); _pc.resize(_poster.width(), _poster.height())
    _pc.show(); app.processEvents()
    _poster.grab().save(os.path.join(OUT, "v1370_card_single.png"))
    print("saved v1370_card_single.png")

# ---- ③ 启动画面（默认朱红高亮色）----
logo = os.path.join(ROOT, "logo-4.png")
sp = splash_mod.SplashScreen(logo_path=logo, title=ver.APP_NAME,
                             version_text=ver.FULL_VERSION, copyright_text=ver.COPYRIGHT)
sp.show(); app.processEvents()
for _ in range(3):
    sp.repaint(); app.processEvents()
sp.grab().save(os.path.join(OUT, "v1370_splash.png"))
print("saved v1370_splash.png")

# ---- ④ 首页（右面板高亮色边框）----
win.go(win._view_home)
for _ in range(4):
    app.processEvents()
win.grab().save(os.path.join(OUT, "v1370_home_border.png"))
print("saved v1370_home_border.png")

print("OUT:", OUT)
