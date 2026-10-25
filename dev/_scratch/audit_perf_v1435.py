# -*- coding: utf-8 -*-
"""只读性能抽查：影片墙 / 演员库主查询的索引使用与耗时。"""
import os
import sqlite3
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
dbp = os.path.join(ROOT, "index_data", "media_center.db")
uri = "file:" + dbp.replace("\\", "/") + "?mode=ro"
con = sqlite3.connect(uri, uri=True, timeout=8)

WALL = ("SELECT m.* FROM media m WHERE m.parent_id IS NULL "
        "ORDER BY m.sort_title COLLATE NOCASE ASC, m.year DESC, m.id ASC LIMIT 60 OFFSET 0")
PEOPLE = ("SELECT p.*, COUNT(mp.media_id) AS works, MAX(m.year) AS last_year "
          "FROM people p LEFT JOIN media_people mp ON mp.person_id = p.id "
          "LEFT JOIN media m ON m.id = mp.media_id "
          "WHERE p.role_type='Actor' GROUP BY p.id "
          "ORDER BY p.pinned DESC, works DESC, p.name COLLATE NOCASE LIMIT 60 OFFSET 0")

for name, sql in (("影片墙（名称升序）", WALL), ("演员库（作品数降序）", PEOPLE)):
    print("== %s ==" % name)
    for r in con.execute("EXPLAIN QUERY PLAN " + sql):
        print("   ", r[-1])
    t0 = time.perf_counter()
    rows = con.execute(sql).fetchall()
    dt = (time.perf_counter() - t0) * 1000
    print("   返回 %d 行，耗时 %.2f ms" % (len(rows), dt))

print()
print("== 深翻页（OFFSET 30000）==")
sql = WALL.replace("OFFSET 0", "OFFSET 30000")
t0 = time.perf_counter()
rows = con.execute(sql).fetchall()
print("   %.2f ms / %d 行" % ((time.perf_counter() - t0) * 1000, len(rows)))

print()
print("== 按播放次数排序（较冷门排序键）==")
sql = ("SELECT m.id FROM media m WHERE m.parent_id IS NULL "
       "ORDER BY m.play_count DESC, m.year DESC, m.id ASC LIMIT 60")
for r in con.execute("EXPLAIN QUERY PLAN " + sql):
    print("   ", r[-1])
t0 = time.perf_counter()
con.execute(sql).fetchall()
print("   %.2f ms" % ((time.perf_counter() - t0) * 1000))
con.close()
