# -*- coding: utf-8 -*-
"""v1.2.1 离屏冒烟：新字段/新视图/智能分类。"""
import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor

app = QApplication(sys.argv)

import database as db
import scanner as scanner_mod
from main_window import MainWindow, load_style
from ui_hero import HeroView

# 使用临时数据库，避免清空真实索引（历史脚本会调用 clear_media）
_TMPDB = tempfile.mkdtemp(prefix="lmc_tmpdb_")
db.db_path = lambda: os.path.join(_TMPDB, "index_data", "media_center.db")

TMP = tempfile.mkdtemp(prefix="lmc_v121_")

# 生成一张占位图
def make_img(path, color):
    img = QImage(300, 450, QImage.Format_RGB32)
    img.fill(QColor(color))
    img.save(path)

# 电影
md = os.path.join(TMP, "La.La.Land.2016.2160p.HDR10.Atmos.TrueHD")
os.makedirs(md, exist_ok=True)
make_img(os.path.join(md, "poster.jpg"), "#3a2e24")
make_img(os.path.join(md, "fanart.jpg"), "#1b2a4a")
open(os.path.join(md, "movie.nfo"), "w", encoding="utf-8").write("""<?xml version="1.0"?>
<movie>
  <title>乐来越爱你</title><sorttitle>La La Land</sorttitle>
  <year>2016</year><runtime>128</runtime>
  <country>美国</country><country>中国香港</country>
  <studio>Lionsgate</studio><mpaa>PG-13</mpaa>
  <plot>一名爵士钢琴师与一名女演员在洛杉矶的爱情故事。</plot>
  <rating>7.9</rating><genre>喜剧</genre><genre>剧情</genre><genre>爱情</genre>
  <set><name>音乐爱情合集</name></set>
  <uniqueid type="tmdb">313369</uniqueid>
  <thumb>poster.jpg</thumb>
  <fanart>fanart.jpg</fanart>
  <actor><name>Emma Stone</name><role>Mia</role><type>Actor</type></actor>
  <actor><name>Ryan Gosling</name><role>Sebastian</role><type>Actor</type></actor>
</movie>""")
open(os.path.join(md, "movie.mkv"), "w").write("x" * 5000)

# 国产片 + R 级
cd = os.path.join(TMP, "国产测试片 2020 1080p")
os.makedirs(cd, exist_ok=True)
open(os.path.join(cd, "movie.nfo"), "w", encoding="utf-8").write("""<?xml version="1.0"?>
<movie>
  <title>国产测试片</title><year>2020</year><runtime>100</runtime>
  <country>中国</country><mpaa>R</mpaa><rating>6.1</rating><genre>动作</genre>
</movie>""")
open(os.path.join(cd, "movie.mp4"), "w").write("x" * 1000)

db.init_db()
db.clear_media()
counts = scanner_mod.scan_library(TMP)
print("SCAN:", counts)

m = db.movies()[0]
print("RUNTIME:", m.get("runtime"), "| COUNTRY:", m.get("country"),
      "| QUALITY:", m.get("quality"), "| COLLECTION:", m.get("collection"),
      "| TMDB:", m.get("tmdb_id"), "| SIZE:", m.get("file_size"), "| ADDED:", m.get("added_date"))

print("COLLECTIONS:", db.collections())
print("LIBS:", len(db.libraries()))
print("国产:", [x["title"] for x in db.search_media(country="中国")])
print("禁片(R):", [x["title"] for x in db.search_media(certification="R")])
print("合集:", [x["title"] for x in db.search_media(collection="音乐爱情合集")])
print("演员搜索 Emma:", [x["title"] for x in db.search_media(person="Emma")])
print("收藏切换:", db.toggle_favorite(m["id"]), "->", len(db.favorites()))

load_style(app)
win = MainWindow()
win.show()
print("MAIN OK:", win.windowTitle())
hv = HeroView(db.get_media(m["id"]), on_open_actor=lambda p: None)
print("HERO OK:", hv.media["title"])
win.close()
shutil.rmtree(TMP, ignore_errors=True)
print("SMOKE_V121_OK")
