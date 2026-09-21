# -*- coding: utf-8 -*-
"""调试：为什么详情页状态推断是「未知」。只读真实库副本。"""
import os, sys, shutil, tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import scanner as scanner_mod

tmp = tempfile.mkdtemp(prefix="lmc_dbg_")
os.makedirs(os.path.join(tmp, "index_data"), exist_ok=True)
shutil.copy2(os.path.join(ROOT, "index_data", "media_center.db"),
             os.path.join(tmp, "index_data", "media_center.db"))
db.db_path = lambda: os.path.join(tmp, "index_data", "media_center.db")

print("=== media.year 样本 ===")
rows = db.search_media(limit=5)
for m in rows:
    print("  id=%s title=%s year=%r type=%s" % (m["id"], (m["title"] or "")[:22], m.get("year"), type(m.get("year")).__name__))

print("\n=== 回填前：Director 关联 ===", db.count_people_links("Director"))
st = scanner_mod.backfill_people_links()
print("回填:", st)

import main_window as mw
print("\n=== all_people_ordered 前 6 ===")
for p in db.all_people_ordered("Actor")[:6]:
    gp = db.get_person(p["id"])
    print("  #%-4s %-12s works=%-3s last_year=%-6s get_person.last_year=%-6s status=%r -> %r" % (
        p["id"], (p["name"] or "")[:12], p.get("works"), p.get("last_year"),
        gp.get("last_year"), gp.get("status"), mw._person_status(gp)))

print("\n=== 该演员关联的 media.year 明细 ===")
p0 = db.all_people_ordered("Actor")[0]
for m in db.person_works(p0["id"]):
    print("  id=%s year=%r kind=%s" % (m["id"], m.get("year"), m.get("kind")))

print("\n=== 直接 SQL ===")
import sqlite3
conn = sqlite3.connect("file:" + os.path.join(tmp, "index_data", "media_center.db").replace("\\", "/") + "?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
r = conn.execute("SELECT MAX(m.year) ly, COUNT(*) n FROM media_people mp JOIN media m ON m.id=mp.media_id WHERE mp.person_id=?", (p0["id"],)).fetchone()
print("  MAX(year)=%r  n=%s" % (r["ly"], r["n"]))
print("  media.year 类型:", [dict(x) for x in conn.execute("SELECT typeof(year) t, year FROM media LIMIT 3")])
conn.close()

shutil.rmtree(tmp, ignore_errors=True)
print("DONE")
