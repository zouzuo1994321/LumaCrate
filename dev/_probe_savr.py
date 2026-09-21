# -*- coding: utf-8 -*-
"""只读探查：有选集的记录（SAVR 1144/1156/1172）字段为何「信息更少」。不动任何数据。"""
import os
import sqlite3
import sys

DB = r"Z:/【01】自研软件/【26-19】本地影视中心/index_data/media_center.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

cols = [r[1] for r in con.execute("PRAGMA table_info(media)")]
print("media 列:", cols)

for key in ("1144", "1156", "1172"):
    print("\n===== SAVR", key, "=====")
    rows = con.execute(
        "SELECT id,parent_id,episode,title,year,certification,runtime,quality,"
        "studio,collection,user_rating,nfo_path,file_path,library "
        "FROM media WHERE file_path LIKE ? OR title LIKE ?",
        (f"%SAVR%{key}%", f"%SAVR {key}%")).fetchall()
    for r in rows:
        print(f" id={r['id']} parent={r['parent_id']} ep={r['episode']} "
              f"title={r['title']!r} year={r['year']!r} cert={r['certification']!r} "
              f"runtime={r['runtime']!r} quality={r['quality']!r} studio={r['studio']!r} "
              f"coll={r['collection']!r} ur={r['user_rating']!r}")
        print(f"    nfo={r['nfo_path']}")
        print(f"    file={r['file_path']}")
        # 该媒体的演员关联数
        n = con.execute("SELECT COUNT(*) c FROM media_people WHERE media_id=?", (r["id"],)).fetchone()["c"]
        print(f"    演员关联 media_people = {n}")

# 对比：普通无选集记录字段是否更全
print("\n===== 抽样：顶层普通记录（parent_id IS NULL 且无子片）字段填充率 =====")
q = ("SELECT id,title,year,runtime,quality,studio,user_rating FROM media "
     "WHERE parent_id IS NULL AND id NOT IN (SELECT DISTINCT parent_id FROM media WHERE parent_id IS NOT NULL) "
     "LIMIT 5")
for r in con.execute(q):
    print(f" id={r['id']} title={r['title']!r} year={r['year']!r} runtime={r['runtime']!r} "
          f"quality={r['quality']!r} studio={r['studio']!r} ur={r['user_rating']!r}")

# 代表性口径补充：SAVR 1144 组里各片自己的演员关联
print("\n===== SAVR 1144 全组（含子片）各自演员关联与字段 =====")
grp = con.execute("SELECT id,parent_id,episode,file_path,nfo_path,year,title,user_rating"
                  " FROM media WHERE file_path LIKE ?", ("%SAVR%1144%",)).fetchall()
for r in grp:
    n = con.execute("SELECT COUNT(*) c FROM media_people WHERE media_id=?", (r["id"],)).fetchone()["c"]
    print(f" id={r['id']} parent={r['parent_id']} ep={r['episode']} ur={r['user_rating']!r} "
          f"演员={n} file={os.path.basename(r['file_path'] or '')}")

con.close()
