# -*- coding: utf-8 -*-
"""v2.0.11 取证 3：多碟分集（cd1/cd2）在**演员 / 导演反查**里是否只剩一部。

用户反馈 1 原话：
    「首页 和 媒体库 中 cd1 cd2 的文件会合并在一起，但是演员和导演中 cd1 cd2 的分集
      还是分开。尝试修复这个问题」

复现链（全部走真实函数，只换临时库）：
  1. 造一个目录 + 两个空文件 `XXX-cd1.mp4` / `XXX-cd2.mp4`（group_cd_sets 要 os.path.exists）
  2. 索引成两条 media；演员 A 同时挂在 cd1 与 cd2 上（同目录共用一份 nfo 的真实形态），
     演员 B **只**挂在 cd2 上（折叠逻辑必须也能把他算进这一部）
  3. `scanner.group_cd_sets(root)` → cd2 的 parent_id 指向 cd1
  4. 断言：
     · `recount_people_works()` 后 A / B 的 works 都是 **1**
     · `person_works(A)` / `person_works(B)` 都只回 **1 行**，且是 cd1（代表分片）
     · `get_person()` 的 works 与 person_works 行数一致（详情页「参演作品 N 部」
       与「全部作品」网格不会再打架）
     · 删掉 cd2 后 A 仍是 1（删分片不该减作品数）

⚠ 只用临时库：`db.db_path` 被指向 <temp>/index_data/media_center.db，
   绝不碰真实索引（见项目记忆里的探针铁律）。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("LMC_NO_SYSMON", "1")

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

TMP = tempfile.mkdtemp(prefix="lmc2011cd_")
IDX = os.path.join(TMP, "index_data")
os.makedirs(IDX, exist_ok=True)

import applog  # noqa: E402
applog.log_dir = lambda *a, **k: TMP          # 日志也重定向，别写真实目录

import database as db  # noqa: E402

db.db_path = lambda: os.path.join(IDX, "media_center.db")
db.init_db()

import scanner  # noqa: E402

ROOT = os.path.join(TMP, "lib", "SAVR-1144")
os.makedirs(ROOT, exist_ok=True)
F1 = os.path.join(ROOT, "SAVR-1144-8K-cd1.mp4")
F2 = os.path.join(ROOT, "SAVR-1144-8K-cd2.mp4")
for f in (F1, F2):
    with open(f, "wb") as fh:
        fh.write(b"\0" * 16)

FAIL = []


def ok(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


# ---------- 造数据 ----------
conn = db.get_conn()
ids = {}
for path, tag in ((F1, "cd1"), (F2, "cd2")):
    cur = conn.execute(
        "INSERT INTO media (kind, title, sort_title, year, file_path, library) "
        "VALUES ('movie', ?, ?, 2024, ?, '测试库')",
        ("SAVR-1144-8K", "savr-1144-8k", path))
    ids[tag] = cur.lastrowid

conn.execute("INSERT INTO people (name, role_type) VALUES ('演员A', 'Actor')")
pa = conn.execute("SELECT id FROM people WHERE name='演员A'").fetchone()["id"]
conn.execute("INSERT INTO people (name, role_type) VALUES ('导演B', 'Director')")
pb = conn.execute("SELECT id FROM people WHERE name='导演B'").fetchone()["id"]
conn.execute("INSERT INTO people (name, role_type) VALUES ('路人C', 'Actor')")
pc = conn.execute("SELECT id FROM people WHERE name='路人C'").fetchone()["id"]

# A 挂在两个分片上（共用 nfo 的真实形态）；B 只挂 cd2；C 只挂别的片（对照，应为 0）
for mid in (ids["cd1"], ids["cd2"]):
    conn.execute("INSERT INTO media_people (media_id, person_id, char_role) "
                 "VALUES (?, ?, '')", (mid, pa))
conn.execute("INSERT INTO media_people (media_id, person_id, char_role) "
             "VALUES (?, ?, '')", (ids["cd2"], pb))
conn.commit()
conn.close()

print("=" * 78)
print("0. 归组之前（模拟老库的口径：一条关联 = 一部作品）")
print("=" * 78)
before = {p["name"]: p["works"] for p in db.all_people("Actor")}
print("  all_people(Actor) works =", before)
ok(before.get("演员A") == 2, "归组前 A 被算成 2 部（复现用户看到的现象）")

# ---------- 归组 ----------
n = scanner.group_cd_sets(TMP)
print("\ngroup_cd_sets 改动记录数 =", n)
db.recount_people_works()

print()
print("=" * 78)
print("1. 归组 + 重算之后")
print("=" * 78)
rows = {r["id"]: r for r in db.media_for_prune(root=TMP)}
ok(rows[ids["cd2"]]["parent_id"] == ids["cd1"],
   "cd2 的 parent_id 指向 cd1（代表分片）")

after = {p["name"]: p["works"] for p in db.all_people("Actor")}
print("  all_people(Actor) works =", after)
d_after = {p["name"]: p["works"] for p in db.all_people("Director")}
print("  all_people(Director) works =", d_after)
ok(after.get("演员A") == 1, "演员库：A 的作品数从 2 降为 1")
ok(d_after.get("导演B") == 1, "导演库：只挂 cd2 的 B 也算 1 部（折叠到代表）")

wa = db.person_works(pa)
wb = db.person_works(pb)
wc = db.person_works(pc)
print("  person_works(A) = %d 行 %s" % (len(wa), [os.path.basename(x["file_path"]) for x in wa]))
print("  person_works(B) = %d 行 %s" % (len(wb), [os.path.basename(x["file_path"]) for x in wb]))
ok(len(wa) == 1, "A 的「全部作品」只剩 1 部")
ok(len(wb) == 1, "B（只挂 cd2）的「全部作品」是 1 部，不是 0 部")
ok(len(wc) == 0, "没有作品的人仍然是 0 部")
if wa:
    ok(os.path.basename(wa[0]["file_path"]).endswith("-cd1.mp4"),
       "返回的是代表分片 cd1（不是 cd2 自己的那条）")
    ok(wa[0]["parent_id"] is None, "返回行的 parent_id 为空（顶层条目，卡片可以正常打开）")

g = db.get_person(pa)
ok(g["works"] == len(wa),
   "get_person().works(%s) 与 person_works 行数(%d) 一致" % (g["works"], len(wa)))

print()
print("=" * 78)
print("2. 删掉一个分片后（删除分片不该让作品数掉到 0）")
print("=" * 78)
db.delete_media(ids["cd2"])
after2 = {p["name"]: p["works"] for p in db.all_people("Actor")}
print("  all_people(Actor) works =", after2)
ok(after2.get("演员A") == 1, "删掉 cd2 后 A 仍是 1 部")
ok(len(db.person_works(pa)) == 1, "person_works 仍是 1 行")

print()
print("库文件：", db.db_path())
print("PROBE_V2011_CD_DONE 失败项=%d" % len(FAIL))
for f in FAIL:
    print("  ✗", f)
