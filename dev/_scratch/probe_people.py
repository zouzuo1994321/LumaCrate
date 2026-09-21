# -*- coding: utf-8 -*-
"""只读体检：演员信息到底存了什么（不写库）。"""
import json
import sqlite3
import sys

db = r"Z:/【01】自研软件/【26-19】本地影视中心/index_data/media_center.db"
con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
con.row_factory = sqlite3.Row
out = []

cols = [r["name"] for r in con.execute("PRAGMA table_info(people)")]
out.append("people 列: " + ", ".join(cols))
n = con.execute("SELECT COUNT(*) FROM people").fetchone()[0]
out.append("people 行数: %d" % n)

for f in ("birthday", "alias", "romaji", "photo", "thumb", "meta", "status", "size", "height"):
    if f in cols:
        c = con.execute("SELECT COUNT(*) FROM people WHERE TRIM(COALESCE(%s,''))<>''" % f).fetchone()[0]
        out.append("  非空 %-9s %d/%d" % (f, c, n))

out.append("\n--- ひなの花音 ---")
for r in con.execute("SELECT * FROM people WHERE name LIKE '%ひなの花音%'"):
    for k in r.keys():
        v = r[k]
        if v is None:
            continue
        s = str(v)
        if len(s) > 400:
            s = s[:400] + " …(len=%d)" % len(str(v))
        out.append("  %-12s = %r" % (k, s))

out.append("\n--- meta 非空的样例行（前 8 条）---")
for r in con.execute("SELECT id,name,meta FROM people WHERE TRIM(COALESCE(meta,''))<>'' LIMIT 8"):
    out.append("  [%s] %s" % (r["id"], r["name"]))
    out.append("       meta = %s" % (r["meta"] or "")[:500])

out.append("\n--- meta 里出现过的键（采样 300 条统计）---")
from collections import Counter
c = Counter()
bad = 0
for r in con.execute("SELECT meta FROM people WHERE TRIM(COALESCE(meta,''))<>'' LIMIT 300"):
    m = r["meta"] or ""
    try:
        d = json.loads(m)
        if isinstance(d, dict):
            for k in d:
                c[k] += 1
    except Exception:
        bad += 1
out.append("  非法 JSON: %d" % bad)
for k, v in c.most_common(30):
    out.append("  %-16s %d" % (k, v))

out.append("\n--- 出生/身高/三围 是否有别的列 ---")
out.append("  列清单: " + ", ".join(cols))

con.close()
open(r"C:/Users/zouzu/AppData/Local/Temp/people_probe.txt", "w", encoding="utf-8").write("\n".join(out))
print("done")
