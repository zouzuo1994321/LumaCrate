# -*- coding: utf-8 -*-
"""在**真实库的副本**上试索引：找出能让影片墙 ORDER BY 走索引的定义。

真实库只读（用 sqlite3 backup API 拷到 %TEMP%），所有 CREATE INDEX 都发生在副本上。
"""
import os
import shutil
import sqlite3
import sys
import time

SRC = r"Z:/【01】自研软件/【26-19】本地影视中心/src"
sys.path.insert(0, SRC)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import applog
applog.log_dir = lambda: os.path.join(os.environ.get("TEMP", "."), "lmc_bench_logs")
import database as db

TMP = os.path.join(os.environ.get("TEMP", "."), "lmc_bench_copy")
os.makedirs(TMP, exist_ok=True)
COPY = os.path.join(TMP, "copy.db")

srcc = sqlite3.connect(db.db_path())
if os.path.exists(COPY):
    try:
        os.remove(COPY)
    except OSError:
        pass
dst = sqlite3.connect(COPY)
t0 = time.perf_counter()
srcc.backup(dst)
print("副本已生成：%.1f MB / %.2fs" % (os.path.getsize(COPY) / 1048576.0,
                                   time.perf_counter() - t0))
srcc.close()

CASES = {
    "名称升序 深翻页":
        "SELECT m.id FROM media m ORDER BY m.sort_title COLLATE NOCASE ASC, "
        "m.year DESC, m.id ASC LIMIT 60 OFFSET 47963",
    "最近添加 倒序":
        "SELECT m.id FROM media m ORDER BY m.added_time DESC, "
        "m.year DESC, m.id ASC LIMIT 60 OFFSET 0",
}


def report(conn, title):
    print("\n=== %s ===" % title)
    for name, sql in CASES.items():
        plan = [tuple(r)[-1] if len(tuple(r)) < 4 else tuple(r)[3]
                for r in conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()]
        # 计时
        conn.execute(sql).fetchall()
        ts = []
        for _ in range(3):
            t = time.perf_counter()
            conn.execute(sql).fetchall()
            ts.append((time.perf_counter() - t) * 1000)
        print("  %-14s %7.1f ms   计划: %s" % (name, min(ts), " / ".join(plan)))


report(dst, "现状（无新索引）")

CANDIDATES = [
    ("idx_wall_title_v2",
     "CREATE INDEX idx_wall_title_v2 ON media(sort_title COLLATE NOCASE, year DESC, id ASC)"),
    ("idx_wall_time_v2",
     "CREATE INDEX idx_wall_time_v2 ON media(added_time DESC, year DESC, id ASC)"),
]
for name, sql in CANDIDATES:
    t = time.perf_counter()
    try:
        dst.execute(sql)
        dst.commit()
        print("\n[建索引] %s  %.1fs" % (name, time.perf_counter() - t))
    except sqlite3.Error as e:
        print("\n[建索引失败] %s -> %s" % (name, e))

report(dst, "加上两个复合索引后")

# 再试：只保留「两列」的简化版，看 SQLite 是否满足于 (sort_title, id)
print("\n=== 追加试验：更简的复合索引 ===")
for name, sql in [
    ("idx_try_a", "CREATE INDEX idx_try_a ON media(sort_title COLLATE NOCASE, id)"),
    ("idx_try_b", "CREATE INDEX idx_try_b ON media(sort_title COLLATE NOCASE, year)"),
]:
    try:
        dst.execute(sql)
        dst.commit()
        print("  %s 已建" % name)
    except sqlite3.Error as e:
        print("  %s 失败 %s" % (name, e))
report(dst, "再加简化复合索引后")

# 反向验证：删掉 v2 两个索引看是否退化
for n in ("idx_wall_title_v2", "idx_wall_time_v2", "idx_try_a", "idx_try_b"):
    try:
        dst.execute("DROP INDEX " + n)
        dst.commit()
    except sqlite3.Error:
        pass
dst.commit()

print("\n=== 对照试验：把 ORDER BY 的附加项去掉（看是不是它们挡住了索引）===")
for name, sql in [
    ("只有 sort_title NOCASE",
     "SELECT m.id FROM media m ORDER BY m.sort_title COLLATE NOCASE ASC LIMIT 60 OFFSET 47963"),
    ("只有 sort_title（BINARY）",
     "SELECT m.id FROM media m ORDER BY m.sort_title ASC LIMIT 60 OFFSET 47963"),
]:
    plan = [tuple(r)[3] for r in dst.execute("EXPLAIN QUERY PLAN " + sql).fetchall()]
    t = time.perf_counter()
    dst.execute(sql).fetchall()
    print("  %-26s %7.1f ms   %s" % (name, (time.perf_counter() - t) * 1000,
                                     " / ".join(plan)))

dst.close()
print("\n副本保留在：%s（可重复试验）" % COPY)
