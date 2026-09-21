# -*- coding: utf-8 -*-
"""探针：为什么「深层翻页 / 最近添加倒序」慢 —— 看 SQLite 到底用没用索引。

只读：EXPLAIN QUERY PLAN 不执行查询。
"""
import os
import sys

SRC = r"Z:/【01】自研软件/【26-19】本地影视中心/src"
sys.path.insert(0, SRC)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import applog
applog.log_dir = lambda: os.path.join(
    os.environ.get("TEMP", "."), "lmc_bench_logs")

import database as db

conn = db.get_conn()
print("--- sqlite", conn.execute("SELECT sqlite_version()").fetchone()[0])
print("--- 索引 ---")
for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' "
                      "AND tbl_name='media'").fetchall():
    print("   ", r[0], "|", r[1])

CASES = [
    ("首屏 名称升序",
     "SELECT m.id FROM media m ORDER BY m.sort_title COLLATE NOCASE ASC, "
     "m.year DESC, m.id ASC LIMIT 60 OFFSET 0"),
    ("深翻页 名称升序",
     "SELECT m.id FROM media m ORDER BY m.sort_title COLLATE NOCASE ASC, "
     "m.year DESC, m.id ASC LIMIT 60 OFFSET 47963"),
    ("去掉 COLLATE NOCASE",
     "SELECT m.id FROM media m ORDER BY m.sort_title ASC, "
     "m.year DESC, m.id ASC LIMIT 60 OFFSET 47963"),
    ("最近添加 desc",
     "SELECT m.id FROM media m ORDER BY m.added_time DESC, "
     "m.year DESC, m.id ASC LIMIT 60 OFFSET 0"),
    ("纯 added_time desc",
     "SELECT m.id FROM media m ORDER BY m.added_time DESC LIMIT 60 OFFSET 0"),
    ("随机排序 深 offset",
     "SELECT m.id FROM media m ORDER BY ((m.id * 2654435761 + 12345) % 2147483647) "
     "ASC LIMIT 60 OFFSET 24000"),
]
for name, sql in CASES:
    print("\n###", name)
    for r in conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall():
        print("    ", " | ".join(str(x) for x in tuple(r)[1:]))

# 顺带确认 sort_title 索引的 collation
print("\n--- PRAGMA index_xinfo(idx_media_sort_title) ---")
for r in conn.execute("PRAGMA index_xinfo(idx_media_sort_title)").fetchall():
    print("    ", tuple(r))
