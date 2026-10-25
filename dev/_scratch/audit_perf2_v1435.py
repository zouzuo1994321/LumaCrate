# -*- coding: utf-8 -*-
"""验证：强制走 idx_wall_title 后深翻页是否明显变快（只读）。"""
import os
import sqlite3
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
dbp = os.path.join(ROOT, "index_data", "media_center.db")
uri = "file:" + dbp.replace("\\", "/") + "?mode=ro"
con = sqlite3.connect(uri, uri=True, timeout=8)

names = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='media'")]
print("media 索引:", names)

base = ("SELECT m.* FROM media m {idx} WHERE m.parent_id IS NULL "
        "ORDER BY m.sort_title COLLATE NOCASE ASC, m.year DESC, m.id ASC "
        "LIMIT 60 OFFSET {off}")


def bench(label, sql):
    t0 = time.perf_counter()
    n = len(con.execute(sql).fetchall())
    print("  %-42s %8.1f ms  (%d 行)" % (label, (time.perf_counter() - t0) * 1000, n))


for off in (0, 30000):
    print("\nOFFSET %d" % off)
    bench("默认（planner 自选）", base.format(idx="", off=off))
    try:
        bench("INDEXED BY idx_wall_title", base.format(idx="INDEXED BY idx_wall_title", off=off))
    except Exception as e:
        print("  INDEXED BY 失败:", e)
    try:
        bench("INDEXED BY idx_media_parent", base.format(idx="INDEXED BY idx_media_parent", off=off))
    except Exception as e:
        print("  INDEXED BY parent 失败:", e)

print("\n== 若把 ORDER BY 改成 sort_title 不带 COLLATE ==")
bench("默认（BINARY 排序）",
      "SELECT m.* FROM media m WHERE m.parent_id IS NULL "
      "ORDER BY m.sort_title ASC, m.year DESC, m.id ASC LIMIT 60 OFFSET 30000")
con.close()
