# -*- coding: utf-8 -*-
"""v2.0.5（反馈 2/3）出图：收藏 → 影片名称金黄；卡片标题靠左。

上排：卡片四态（未收藏 / 收藏 × 短标题 / 长标题）。
下排：详情页横幅（收藏态），看大标题的金黄色。
"""
import os
import sys
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = r"C:/Users/zouzu/AppData/Local/Temp/v206title"
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)

import database as db          # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: os.path.join(TMP, "probe.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")
db.init_db()

from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QStyleFactory
from PySide6.QtGui import (QImage, QPainter, QPixmap, QColor, QFontDatabase,
                           QLinearGradient)
from PySide6.QtCore import Qt

OUT = os.path.join(ROOT, "docs", "preview")
os.makedirs(OUT, exist_ok=True)

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setStyle(QStyleFactory.create("Fusion"))

import main_window as mw      # noqa: E402
import ui_hero as uhero       # noqa: E402
mw.load_style(app)
mw.render_style({"accent": "#e4587c"})


def mk_poster(path, c1, c2):
    pm = QPixmap(316, 472)
    g = QLinearGradient(0, 0, 0, 472)
    g.setColorAt(0.0, QColor(c1))
    g.setColorAt(1.0, QColor(c2))
    p = QPainter(pm)
    p.fillRect(pm.rect(), g)
    p.end()
    pm.save(path)
    return path


POSTER = mk_poster(os.path.join(TMP, "p.png"), "#3a3a42", "#141417")

SHORT = "JUL-609 電撃移籍"
LONG = "259LUXU-1903【潮を吹きまくる上品人妻のびしょ濡れ絶叫SEX】"
CREW_A = [("依本しおり", 0, 0, "female"), ("大志", 0, 0, "male")]
CREW_D = [("K*WEST", 0, 0, "")]

CASES = [
    ("未收藏 · 短标题", SHORT, 0),
    ("收藏 · 短标题", SHORT, 1),
    ("未收藏 · 长标题", LONG, 0),
    ("收藏 · 长标题", LONG, 1),
]

host = QWidget()
host.setObjectName("Host")
host.setStyleSheet("QWidget#Host{background:#0a0a0b;}")
host.setAttribute(Qt.WA_StyledBackground, True)
v = QVBoxLayout(host)
v.setContentsMargins(16, 14, 16, 14)
v.setSpacing(16)

row = QHBoxLayout()
row.setSpacing(14)
for i, (_tag, title, fav) in enumerate(CASES):
    m = {"id": i + 1, "title": title, "poster": POSTER, "rating": 8.5,
         "year": 2025, "quality": "4K", "favorite": fav,
         "file_path": "X:/a/b.mp4", "plot": "", "tags": ""}
    c = mw.PosterCard(m, lambda *_a: None, on_play=lambda *_a: None,
                      on_fav=lambda *_a: None, actor_crew=CREW_A, director_crew=CREW_D)
    row.addWidget(c)
    print(_tag, "| 对齐:", int(c._title.alignment()), "| 内联色:", repr(c._title.styleSheet()))
row.addStretch(1)
v.addLayout(row)

# 详情页横幅（收藏态）—— 只看标题那一块
hmedia = {"id": 999, "title": LONG, "favorite": 1, "kind": "movie", "year": 2025,
          "rating": 8.7, "user_rating": None, "genres": "ドラマ", "runtime": "120 分钟",
          "country": "日本", "certification": None, "quality": "8K,60fps,HDR",
          "plot": "（简介省略）", "poster": POSTER, "fanart": POSTER,
          "file_path": "X:/a/b.mp4", "file_size": 1024, "tags": "",
          "collection": None, "tmdb_id": None, "nfo_path": None,
          "premiere": None, "added_date": None}
hero = uhero.HeroView(hmedia)
hero.setFixedSize(760, 300)
hero.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
hero.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
print("详情页标题内联色：", repr(hero._title_lbl.styleSheet()))
v.addWidget(hero)

host.resize(4 * 172 + 14 * 3 + 32, 760)
host.show()
app.processEvents()
for _ in range(4):
    app.processEvents()
pm = host.grab()
im = pm.toImage().convertToFormat(QImage.Format_ARGB32)
canvas = QImage(im.width(), im.height(), QImage.Format_ARGB32)
canvas.fill(QColor("#0a0a0b"))
p = QPainter(canvas)
p.drawImage(0, 0, im)
p.end()
canvas.save(os.path.join(OUT, "v206_fav_title.png"))
print("saved v206_fav_title.png", canvas.width(), "x", canvas.height())

# 像素自证：收藏卡标题带里必须有金像素；未收藏卡没有
def band_has(path_img, x0, y0, x1, y1, rgb, tol=26):
    n = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            c = path_img.pixelColor(x, y)
            if (abs(c.red() - rgb[0]) < tol and abs(c.green() - rgb[1]) < tol
                    and abs(c.blue() - rgb[2]) < tol):
                n += 1
    return n


GOLD = (0xf5, 0xa5, 0x24)
print("DONE")
