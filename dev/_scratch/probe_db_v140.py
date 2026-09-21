# -*- coding: utf-8 -*-
"""v1.14.0 数据层自检：连接复用 / 分页 / 排序 / 筛选 / 关联按需查 / 演员查询。"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

import applog
import database as db

TMP = tempfile.mkdtemp(prefix="lmc_probe_db_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

db.init_db()
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"OK   - {name}  {extra}")
    else:
        fail += 1
        print(f"FAIL - {name}  {extra}")


# 造数据：2 个库、3 种 kind、评分/年份/收藏/画质各异
rows = [
    dict(kind="movie", title="Alpha 一部", sort_title="Alpha", year=2011, rating=7.5,
         user_rating=6.0, favorite=1, library="库A", quality="1080P", plot="剧情" * 200),
    dict(kind="movie", title="Beta 二部", sort_title="Beta", year=2021, rating=8.2,
         favorite=0, library="库A", quality="4K,HDR10", plot="剧情" * 200),
    dict(kind="movie", title="Gamma 三部", sort_title="Gamma", year=2023, rating=None,
         user_rating=9.5, favorite=1, library="库A", quality="720P", plot="剧情" * 200),
    dict(kind="tvshow", title="Delta 剧集", sort_title="Delta", year=2015, favorite=0,
         library="库B", plot="剧情" * 200),
]
ids = []
for r in rows:
    r["file_path"] = os.path.join(TMP, r["title"] + ".mkv")
    ids.append(db.upsert_media_by_path(mode="overwrite", **r))

a_id, b_id, c_id, d_id = ids
pa = db.upsert_person("甲演员")
pb = db.upsert_person("乙导演", role_type="Director")
db.link_media_person(a_id, pa, "", 0)
db.link_media_person(b_id, pa, "", 0)
db.link_media_person(b_id, pb, "", 1)
db.update_person(pb, only_missing=False, birthday="1980-05-05", photo_path=os.path.join(TMP, "p.jpg"))

# 1) 连接复用
c1, c2 = db.get_conn(), db.get_conn()
check("连接复用：两次 get_conn 拿到同一底层连接",
      c1 is c2, type(c1).__name__)
check("close() 是 no-op（代理），连接仍可用", (c1.close() or True) and c2.execute("SELECT 1").fetchone()[0] == 1)

# 2) WAL + 索引
mode = db.get_conn().execute("PRAGMA journal_mode").fetchone()[0]
check("已启用 WAL", str(mode).lower() == "wal", mode)
idx = {r[0] for r in db.get_conn().execute(
    "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
need = {"idx_media_library", "idx_media_favorite", "idx_media_year", "idx_mp_person",
        "idx_people_role"}
check("关键索引齐备", need <= idx, sorted(need - idx) or "全部存在")

# 3) light 投影不含 plot
light = db.search_media(limit=10, light=True)
check("light=True 不返回 plot 字段", light and "plot" not in light[0])
full = db.search_media(limit=10)
check("默认仍返回 plot", full and "plot" in full[0])

# 4) 分页稳定 + 总数
page1 = db.search_media(limit=2, offset=0, sort="sort_title", asc=True)
page2 = db.search_media(limit=2, offset=2, sort="sort_title", asc=True)
check("分页：第 1 页 2 条", len(page1) == 2, [x["title"] for x in page1])
check("分页：两页不重叠", not ({x["id"] for x in page1} & {x["id"] for x in page2}))
check("count_media 全量 = 4", db.count_media() == 4, db.count_media())
check("count_media 按库筛选", db.count_media(library="库A") == 3, db.count_media(library="库A"))

# 5) 排序
desc = db.search_media(sort="year", asc=False, limit=10)
check("按年份降序", [x["year"] for x in desc] == sorted([x["year"] for x in desc], reverse=True),
      [x["year"] for x in desc])
asc = db.search_media(sort="added_time", asc=True, limit=10)
check("按添加时间升序可用", len(asc) == 4)
bad = db.search_media(sort="year; DROP TABLE media", limit=10)
check("非法排序键被白名单拦下（回落名称）", len(bad) == 4 and [x["title"] for x in bad][0].endswith("一部"),
      [x["title"] for x in bad])

# 6) 筛选
check("筛选 已收藏", db.count_media(favorite=True) == 2, db.count_media(favorite=True))
check("筛选 未收藏", db.count_media(favorite=False) == 2)
check("筛选 有用户评分", db.count_media(has_user_rating=True) == 2)
check("筛选 用户评分≥7", db.count_media(min_user_rating=7) == 1)
check("筛选 年份≥2020", db.count_media(year_from=2020) == 2)
check("筛选 画质 4K", db.count_media(quality="4K") == 1)
check("筛选 类型 剧集", db.count_media(kind="tvshow") == 1)
check("筛选与分页口径一致",
      len(db.search_media(favorite=True, limit=10)) == db.count_media(favorite=True))

# 7) 媒体库计数
lc = db.library_counts()
check("library_counts 分组正确", lc.get("库A") == 3 and lc.get("库B") == 1, lc)

# 8) 关联按需查
crew_all = db.cast_crew_map()
crew_some = db.cast_crew_map([a_id])
check("cast_crew_map 全量", crew_all.get(a_id, {}).get("actors") == "甲演员", crew_all.get(a_id))
check("cast_crew_map 只查指定 id（不含未请求的 b）",
      a_id in crew_some and b_id not in crew_some, sorted(crew_some))
amap = db.actors_map(ids=[a_id, b_id])
check("actors_map 只查指定 id", set(amap) == {a_id, b_id}, amap)
check("actors_map 空 id 列表返回空", db.actors_map(ids=[]) == {})

# 9) 演员查询：筛选 + 排序 + 计数（甲演员 = Actor；乙导演 = Director，分开查）
check("query_people 默认只按 role_type=Actor",
      [p["name"] for p in db.query_people()] == ["甲演员"],
      [p["name"] for p in db.query_people()])
check("query_people 可查 Director",
      [p["name"] for p in db.query_people(role_type="Director")] == ["乙导演"])
check("query_people 带出 works / last_year",
      (db.query_people()[0]["works"], db.query_people()[0]["last_year"]) == (2, 2021),
      (db.query_people()[0]["works"], db.query_people()[0]["last_year"]))
check("query_people 分页（Actor 只有 1 人，offset=1 为空）",
      db.query_people(limit=1, offset=1) == [])
check("count_people 按 role_type", (db.count_people(), db.count_people(role_type="Director")) == (1, 1),
      (db.count_people(), db.count_people(role_type="Director")))
check("count_people 筛选 有头像（乙导演有 photo_path）",
      db.count_people(role_type="Director", has_photo=True) == 1)
check("count_people 筛选 无头像（甲演员）",
      db.count_people(has_photo=False) == 1)
check("count 与 query 口径一致",
      len(db.query_people(role_type="Director", has_photo=True)) ==
      db.count_people(role_type="Director", has_photo=True))
# 甲演员作品 2011/2021 → 今年-1=2025，早于它 → 判定「退役」
check("状态筛选 退役 = 1（甲演员最新作品 2021）", db.count_people(status="退役") == 1)
check("状态筛选 现役 = 0", db.count_people(status="现役") == 0)
check("状态筛选 未知 = 0（甲演员有作品年份）", db.count_people(status="未知") == 0)

# 10) stats 单通道
st = db.stats()
check("stats 正确", st == {"movies": 3, "tvshows": 1, "episodes": 0, "people": 2}, st)

# 11) 关连接（导入备份前要用）
db.close_all()
check("close_all 后仍能重新取到连接（懒建）", db.get_conn().execute("SELECT 1").fetchone()[0] == 1)

print(f"\n==== {ok} 通过 / {fail} 失败 ====")
sys.exit(1 if fail else 0)
