# -*- coding: utf-8 -*-
"""核心逻辑冒烟测试(无 UI)：构造样本 nfo，扫描入库，验证演员独立存储与关联搜索。"""
import os
import sys
import tempfile
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import database as db
import nfo_parser as nfo
import scanner as scanner_mod

TMP = tempfile.mkdtemp(prefix="lmc_test_")
# 使用临时数据库，避免清空真实索引（本脚本会调用 clear_media）
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")

# 电影
movie_dir = os.path.join(TMP, "盗梦空间 Inception (2010)")
os.makedirs(movie_dir, exist_ok=True)
open(os.path.join(movie_dir, "movie.nfo"), "w", encoding="utf-8").write("""<?xml version="1.0"?>
<movie>
  <title>盗梦空间</title>
  <sorttitle>Inception</sorttitle>
  <year>2010</year>
  <premiered>2010-07-16</premiered>
  <plot>一场关于梦境潜入的科幻故事。</plot>
  <rating>9.4</rating>
  <genre>科幻</genre>
  <genre>悬疑</genre>
  <thumb>poster.jpg</thumb>
  <actor><name>莱昂纳多·迪卡普里奥</name><role>多姆·柯布</role><type>Actor</type></actor>
  <actor><name>约瑟夫·高登-莱维特</name><role>阿瑟</role><type>Actor</type></actor>
  <actor><name>克里斯托弗·诺兰</name><role></role><type>Director</type></actor>
</movie>""")
open(os.path.join(movie_dir, "dummy.mkv"), "w").write("VIDEO")

# 剧集
tv_dir = os.path.join(TMP, "怪奇物语 Stranger Things (2016)")
os.makedirs(os.path.join(tv_dir, "Season 1"), exist_ok=True)
open(os.path.join(tv_dir, "tvshow.nfo"), "w", encoding="utf-8").write("""<?xml version="1.0"?>
<tvshow>
  <title>怪奇物语</title>
  <year>2016</year>
  <plot>小镇孩童离奇失踪事件。</plot>
  <rating>8.8</rating>
  <genre>科幻</genre>
  <genre>恐怖</genre>
  <actor><name>米莉·博比·布朗</name><role>十一</role><type>Actor</type></actor>
</tvshow>""")
open(os.path.join(tv_dir, "Season 1", "S01E01.nfo"), "w", encoding="utf-8").write("""<?xml version="1.0"?>
<episodedetails>
  <title>第一章：失踪</title>
  <season>1</season>
  <episode>1</episode>
  <plot>威尔失踪。</plot>
  <actor><name>米莉·博比·布朗</name><role>十一</role><type>Actor</type></actor>
</episodedetails>""")
open(os.path.join(tv_dir, "Season 1", "S01E01.mkv"), "w").write("VIDEO")

db.init_db()
db.clear_media()
counts = scanner_mod.scan_library(TMP)
print("SCAN COUNTS:", counts)

s = db.stats()
print("STATS:", s)

m = db.movies()[0]
print("MOVIE:", m["title"], m["year"], "genres=", m["genres"])
cast = db.get_cast(m["id"])
print("CAST:", [(c["name"], c["char_role"], c["role_type"]) for c in cast])

# 关联搜索：科幻 + 演员 莱昂纳多
res = db.search_media("", genre="科幻")
print("SEARCH genre=科幻 ->", [x["title"] for x in res])
res2 = db.search_media("", person="莱昂纳多")
print("SEARCH person=莱昂纳多 ->", [x["title"] for x in res2])

# 独立演员反查
people = db.all_people()
print("PEOPLE:", [(p["name"], p["works"]) for p in people])
leo = [p for p in people if "莱昂纳多" in p["name"]][0]
print("LEO WORKS:", [w["title"] for w in db.person_works(leo["id"])])

shutil.rmtree(TMP, ignore_errors=True)
print("SMOKE_OK")
