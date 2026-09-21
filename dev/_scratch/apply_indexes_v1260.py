# -*- coding: utf-8 -*-
"""把 v1.26.0 新增的两条复合索引补进真实索引库。

说明：这就是 `database.init_db()` 每次应用启动都会跑的迁移（`CREATE INDEX IF NOT EXISTS`），
幂等、可回滚（`DROP INDEX`），且**不碰任何数据行**。这里只是提前把它跑掉，
好让随后生成的《性能基线》反映的是修复后的状态。
"""
import os
import sys
import time

SRC = r"Z:/【01】自研软件/【26-19】本地影视中心/src"
sys.path.insert(0, SRC)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import applog
applog.log_dir = lambda: os.path.join(os.environ.get("TEMP", "."), "lmc_bench_logs")
import database as db

path = db.db_path()
before = os.path.getsize(path) / 1048576.0
conn = db.get_conn()
rows_before = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
idx_before = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='index'").fetchall()]

t0 = time.perf_counter()
db.init_db()
elapsed = time.perf_counter() - t0

conn = db.get_conn()
rows_after = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
idx_after = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
after = os.path.getsize(path) / 1048576.0

print("init_db 耗时 %.2fs" % elapsed)
print("media 行数 %d -> %d （必须不变）" % (rows_before, rows_after))
print("索引 %d -> %d 条" % (len(idx_before), len(idx_after)))
print("新增：", sorted(set(idx_after) - set(idx_before)) or "（无）")
print("体积 %.1f MB -> %.1f MB" % (before, after))

for q in (
    "SELECT m.id FROM media m ORDER BY m.sort_title COLLATE NOCASE ASC, m.year DESC, m.id ASC LIMIT 60 OFFSET 47963",
    "SELECT m.id FROM media m ORDER BY m.added_time DESC, m.year DESC, m.id ASC LIMIT 60 OFFSET 0",
):
    for r in conn.execute("EXPLAIN QUERY PLAN " + q).fetchall():
        print("   计划:", tuple(r)[3])
