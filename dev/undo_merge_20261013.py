# -*- coding: utf-8 -*-
"""把 2026-10-13 验收脚本误触造成的 543 次演员合并**精确反向拆分**回去。

背景：`live_verify_v1390.py` 因离屏坐标与真机工具窗宽度不符（1000 vs 1318），
把「全选建议合并」点到了「批量确认关联」上，对真实索引跑了 543 次
`db.merge_people`。`merge_people` 把被并者 `drop` 的作品关联搬进 `keep`、
把 `drop` 的主名追加进 `keep.alias`、然后删掉 `drop` 行。

⚠ 本脚本**默认不执行任何写操作**，只打印将要做什么（dry-run）。
确认真要回滚再加 `--apply`。

回滚需要的信息全在 `dev/_scratch/merge_undo_20261013.json`（从 app.log 解析出的
543 条 keep/drop/moved）。

⚠⚠ 已知限制，请先读：
  ① **关联无法自动还原到「原始人」**。合并时 `media_people` 的主键是
     `(media_id, person_id)`，同一部片子两人都在场时 `INSERT OR IGNORE`
     会去重 —— 那一部分关联本来就无法区分归属，回滚只能整体留在 `keep` 名下。
     能还原的是「**人**」这一层：把 drop 从 alias 里摘出来、重建成独立行。
  ② `keep` 与 `drop` 之间的 `alias` / `meta` 合并（字段补全）**无法拆回**，
     因为那些值可能来自被并者，且没有标记来源。
  ③ `people.name` 是 UNIQUE —— 若 drop 的名字在库里已被别人占用，跳过并报告。
  ④ 库必须没有别的进程在跑（先关掉流明盒）。

所以本脚本的定位是「**恢复可检索性**」（那些名字重新能搜到、能作为独立演员页出现），
而不是「逐字节还原历史」。如果你觉得当前合并结果本身可以接受
（merge_people 本来就是设计给「同一人合并」用的，且 533/543 的名字都进了 alias），
**最省事的做法是什么都不做** —— 演员库少 543 个重复条目，作品关联一条没丢。
"""
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, "dev", "_scratch", "merge_undo_20261013.json")
DB = os.path.join(ROOT, "index_data", "media_center.db")

APPLY = "--apply" in sys.argv

rows = json.load(open(MAP, encoding="utf-8"))
print("[映射] %d 条合并记录（%s）" % (len(rows), "APPLY" if APPLY else "DRY-RUN"))
if not os.path.exists(DB):
    sys.exit("找不到数据库 %s" % DB)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row


def split_names(alias, drop):
    """在 alias 串里找出 drop 所列的各个名字。

    ⚠ 日志里 `drop` **本身可能是顿号分隔的多个名字** —— 因为上游那次批量操作
    可能又把一个已合并的人当成了 drop（日志实测 543 条里有 50 条属于这种）。
    所以要按分隔符逐个名字判存在性，返回实际命中的那些。
    """
    seps = "、,，;；|/"
    def parts(s):
        out, cur = [], ""
        for ch in s or "":
            if ch in seps:
                out.append(cur)
                cur = ""
            else:
                cur += ch
        out.append(cur)
        return [p.strip() for p in out if p.strip()]

    return [n for n in parts(drop) if n in parts(alias)], parts(alias)


plan, skip = [], []
for r in rows:
    keep, drop = r["keep"], r["drop"]
    k = conn.execute("SELECT id, alias FROM people WHERE name=?", (keep,)).fetchone()
    if k is None:
        skip.append((keep, drop, "保留者不存在"))
        continue
    hit, aparts = split_names(k["alias"], drop)
    if not hit:
        skip.append((keep, drop, "alias 里找不到这些名字（可能已被再次合并）"))
        continue
    free = [n for n in hit
            if not conn.execute("SELECT 1 FROM people WHERE name=?", (n,)).fetchone()]
    if not free:
        skip.append((keep, drop, "这些名字已被别人占用（UNIQUE 冲突）"))
        continue
    plan.append({"keep_id": k["id"], "keep": keep, "names": free,
                 "drop": drop,
                 "old_alias": k["alias"],
                 "new_alias": "、".join(p for p in aparts
                                        if p not in hit)})

print("[可回滚] %d 条" % len(plan))
print("[跳过]   %d 条" % len(skip))
for s in skip[:15]:
    print("   ", s)

if not APPLY:
    print("\n这是 DRY-RUN，什么都没改。确认要回滚就加 --apply。")
    sys.exit(0)

# 反向拆分：新建 drop 行 → 把 media_people 里属于 keep 的关联**不动**
# （见脚本 docstring 限制①：关联无法区分归属）→ 从 keep.alias 摘掉名字
conn.execute("BEGIN")
_n = 0
for p in plan:
    for name in p["names"]:
        conn.execute(
            "INSERT INTO people(name, alias, status) VALUES(?,?,?)",
            (name, "", ""))
        _n += 1
    if p["new_alias"] != (p["old_alias"] or ""):
        conn.execute("UPDATE people SET alias=? WHERE id=?",
                     (p["new_alias"], p["keep_id"]))
conn.commit()
print("[完成] 已重建 %d 个独立演员行（涉及 %d 个保留者）；"
      "作品关联仍留在保留者名下（见限制①）" % (_n, len(plan)))
print("       库文件：%s（建议现在跑一次软件内的「工具 → 演员检测」看结果）" % DB)
conn.close()
