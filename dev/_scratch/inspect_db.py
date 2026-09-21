# -*- coding: utf-8 -*-
"""只读检查真实索引库的 people 表：数据完整性 / meta 乱码情况。绝不写入。"""
import os
import sqlite3
import json
import re

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"
DB = os.path.join(ROOT, "index_data", "media_center.db")
print("DB:", DB, "exists=", os.path.exists(DB))

uri = "file:" + DB.replace("\\", "/") + "?mode=ro"
conn = sqlite3.connect(uri, uri=True)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def q(sql, args=()):
    try:
        return cur.execute(sql, args).fetchall()
    except Exception as e:
        print("SQL ERR", sql, e)
        return []

print("\n--- people 表结构 ---")
for r in q("PRAGMA table_info(people)"):
    print(" ", r["name"], r["type"])

print("\n--- 统计 ---")
for r in q("SELECT role_type, COUNT(*) n FROM people GROUP BY role_type"):
    print("  role_type=%s  n=%d" % (r["role_type"], r["n"]))

print("\n--- 字段填充率 (role_type=Actor) ---")
cols = ["thumb", "photo_path", "birthday", "status", "favorite", "pinned", "meta", "alias", "romaji", "source"]
for c in cols:
    r = q("SELECT COUNT(*) n FROM people WHERE role_type='Actor' AND %s IS NOT NULL AND TRIM(%s)<>''" % (c, c))
    print("  %-12s filled=%s" % (c, r[0]["n"] if r else "?"))

print("\n--- Actor 前 25 条关键字段 ---")
rows = q("SELECT id,name,birthday,status,favorite,pinned,substr(meta,1,220) meta FROM people "
         "WHERE role_type='Actor' ORDER BY pinned DESC, favorite DESC, name LIMIT 25")
for r in rows:
    print("  #%-4s %-14s bd=%-11s st=%-4s fav=%s pin=%s" % (
        r["id"], (r["name"] or "")[:14], (r["birthday"] or "-")[:10], r["status"] or "-",
        r["favorite"], r["pinned"]))
    if r["meta"]:
        print("        meta:", r["meta"].replace("\n", " "))

print("\n--- meta 中含 HTML 标签的演员数 ---")
n_html = 0
samples = []
for r in q("SELECT id,name,meta FROM people WHERE meta IS NOT NULL AND TRIM(meta)<>''"):
    m = r["meta"] or ""
    if re.search(r"<[a-zA-Z/][^>]*>|&#\d+;|&quot;|&amp;", m):
        n_html += 1
        if len(samples) < 6:
            samples.append((r["id"], r["name"], m[:300]))
print("  含 HTML 的 meta 记录数:", n_html)
for sid, sname, sm in samples:
    print("  --- #%s %s" % (sid, sname))
    try:
        d = json.loads(sm)
        for k, v in d.items():
            vs = str(v)
            bad = bool(re.search(r"<[a-zA-Z/][^>]*>", vs))
            print("      %-8s %s%s" % (k, vs[:150], "   <<< HTML!" if bad else ""))
    except Exception as e:
        print("      (非 JSON)", sm[:200], e)

print("\n--- 影片卡小字：media_people 关联 ---")
for r in q("SELECT role_type, COUNT(DISTINCT media_id) medias, COUNT(*) links FROM media_people mp "
           "JOIN people p ON p.id=mp.person_id GROUP BY p.role_type"):
    print("  role_type=%s  media=%s  links=%s" % (r["role_type"], r["medias"], r["links"]))

print("\n--- 有导演关联的影片数 ---")
r = q("SELECT COUNT(DISTINCT mp.media_id) n FROM media_people mp JOIN people p ON p.id=mp.person_id WHERE p.role_type='Director'")
print("  ", r[0]["n"] if r else "?")
print("\n--- 样例：某影片的演员/导演 ---")
for r in q("SELECT m.id, m.title, m.nfo_path FROM media m LIMIT 3"):
    print("  #%s %s" % (r["id"], (r["title"] or "")[:30]))
    print("      nfo:", r["nfo_path"])
conn.close()
print("\nDONE (read-only)")
