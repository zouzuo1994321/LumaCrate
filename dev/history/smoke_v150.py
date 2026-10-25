# -*- coding: utf-8 -*-
"""v1.15.0 离屏冒烟（纯数据层，不依赖 GUI）：

1) CD 连续序号自动归类：cd1/cd2/cd3 归为「一部 + 选集」；
   - 影片墙 top_only 只看到顶层条目；
   - children_of / parts_counts 正确；
   - 代表标题去掉末尾「 CDx」；episode 序号正确；海报借用兄弟分片；
2) 统计口径：stats.movies / stats.parts / library_counts 只数顶层；
3) 扫描并删除失效的：插入一条磁盘文件不存在的记录 → prune_missing 删除它（磁盘不动）；
4) 幂等：物理删除 cd2 后重扫，重新归组（cd1 + cd3 仍归一部，cd2 不再是分片）。

全部用临时库，不污染真实数据。
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

import database as db
import scanner as scanner_mod
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v150_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
import applog
applog.log_dir = lambda: os.path.join(TMP, "logs")
os.makedirs(applog.log_dir(), exist_ok=True)

db.init_db()

LIB = os.path.join(TMP, "cdtest")
d1 = os.path.join(LIB, "普通电影 (2020)")
os.makedirs(d1, exist_ok=True)
open(os.path.join(d1, "movie.nfo"), "w", encoding="utf-8").write(
    "<movie><title>普通电影</title><year>2020</year><rating>7.5</rating></movie>")
open(os.path.join(d1, "poster.jpg"), "w").write("p")
open(os.path.join(d1, "普通电影.mkv"), "w").write("x" * 1000)

d2 = os.path.join(LIB, "OLM-256 (2021)")
os.makedirs(d2, exist_ok=True)
for cd in (1, 2, 3):
    open(os.path.join(d2, f"OLM-256 CD{cd}.mkv"), "w").write("x" * 1000)
# 海报只给 cd1（模拟真实：cd2/cd3 常无封面，代表应借用兄弟分片的海报）
open(os.path.join(d2, "OLM-256 CD1-poster.jpg"), "w").write("p")

scanner_mod.scan_library(LIB, library_name="CD测试")

fails = []


def check(cond, msg):
    print(("PASS" if cond else "FAIL") + " - " + msg)
    if not cond:
        fails.append(msg)


tops = db.search_media(top_only=True, library="CD测试")
check(len(tops) == 2, f"顶层条目应为 2（普通片 + cd 代表），实际 {len(tops)}")
rep = [t for t in tops if "OLM" in (t.get("title") or "")]
check(bool(rep), "OLM 代表缺失")
rep = rep[0]
parts = db.children_of(rep["id"])
check(len(parts) == 2, f"选集应有 2 个分片，实际 {len(parts)}")
pc = db.parts_counts([rep["id"]])
check(pc.get(rep["id"]) == 2, f"parts_counts 应为 2，实际 {pc.get(rep['id'])}")
check("CD" not in (rep["title"] or ""), f"代表标题未清理 CD 标记：{rep['title']!r}")
eps = sorted(p["episode"] for p in parts)
check(eps == [2, 3], f"分片 episode 应为 [2,3]，实际 {eps}")
check(rep.get("poster") is not None, "代表应带上海报（借用兄弟分片）")

# 统计口径
st = db.stats()
check(st["movies"] == 2, f"stats.movies(顶层) 应为 2，实际 {st['movies']}")
check(st["parts"] == 2, f"stats.parts 应为 2，实际 {st['parts']}")
lc = db.library_counts()
check(lc.get("CD测试") == 2, f"library_counts 应为 2，实际 {lc.get('CD测试')}")

# 扫描并删除失效的
db.upsert_media_by_path(mode="overwrite", kind="movie", title="失效片",
                        file_path=os.path.join(LIB, "ghost.mkv"),
                        library="CD测试", parent_id=None, season=None, episode=None)
n_before = db.count_media(library="CD测试")
res = scanner_mod.prune_missing(library_name="CD测试", roots=[LIB])
check(res["removed"] == 1, f"prune 应删除 1 条，实际 {res}")
n_after = db.count_media(library="CD测试")
check(n_after == n_before - 1, f"删除后总数应减 1（{n_before}->{n_after}）")

# 幂等：物理删除 cd2 后重扫，重新归组
os.remove(os.path.join(d2, "OLM-256 CD2.mkv"))
scanner_mod.scan_library(LIB, library_name="CD测试", mode="new")
tops2 = db.search_media(top_only=True, library="CD测试")
rep2 = [t for t in tops2 if "OLM" in (t.get("title") or "")][0]
parts2 = db.children_of(rep2["id"])
check(len(parts2) == 1 and parts2[0]["episode"] == 3,
      f"重扫后选集应为 [cd3]，实际 {[p['episode'] for p in parts2]}")

print("\n" + ("SMOKE_V150 PASS" if not fails else f"SMOKE_V150 FAIL ({len(fails)})"))
sys.exit(1 if fails else 0)
