# -*- coding: utf-8 -*-
"""只读检查真实索引 / 配置 / 日志（不写任何东西）。"""
import io
import json
import os
import sqlite3

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
dbp = os.path.join(ROOT, "index_data", "media_center.db")

print("== 真实索引（只读） ==")
uri = "file:" + dbp.replace("\\", "/") + "?mode=ro"
con = sqlite3.connect(uri, uri=True, timeout=8)
try:
    print("  integrity:", con.execute("PRAGMA integrity_check").fetchone()[0])
    for t in ("media", "people", "media_people", "vector_overrides"):
        try:
            print("  %-16s %d" % (t, con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]))
        except Exception as e:
            print("  %-16s ERR %s" % (t, e))
    print("  media favorite:", con.execute(
        "SELECT COUNT(*) FROM media WHERE COALESCE(favorite,0)=1").fetchone()[0])
    print("  media rating>0:", con.execute(
        "SELECT COUNT(*) FROM media WHERE COALESCE(user_rating,0)>0").fetchone()[0])
    print("  people fav/pin:", con.execute(
        "SELECT COUNT(*) FROM people WHERE COALESCE(favorite,0)=1 OR COALESCE(pinned,0)=1"
    ).fetchone()[0])
    q = ("SELECT COUNT(*) FROM (SELECT p.id FROM people p "
         "LEFT JOIN media_people mp ON mp.person_id=p.id "
         "WHERE p.role_type=? GROUP BY p.id HAVING COUNT(mp.media_id)=0)")
    print("  Actor 无作品:", con.execute(q, ("Actor",)).fetchone()[0])
    print("  Director 无作品:", con.execute(q, ("Director",)).fetchone()[0])
    idx = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")]
    print("  索引数:", len(idx))
finally:
    con.close()

print()
print("== settings.json ==")
sp = os.path.join(ROOT, "settings.json")
print("  exists", os.path.exists(sp), "size", os.path.getsize(sp) if os.path.exists(sp) else -1)
s = json.load(io.open(sp, encoding="utf-8"))
print("  keys:", sorted(s.keys()))
print("  scraper.sources:", s.get("scraper", {}).get("sources"))
print("  sources_enabled:", s.get("scraper", {}).get("sources_enabled"))
print("  gfriends_photo:", s.get("scraper", {}).get("gfriends_photo"),
      "| theporndb_token 非空:", bool((s.get("scraper", {}).get("theporndb_token") or "").strip()))
print("  appearance:", {k: s.get("appearance", {}).get(k)
                        for k in ("mode", "level", "accent", "language")})
print("  window_opacity:", s.get("window_opacity"))
print("  libraries:", [(x.get("name"), len(x.get("paths") or [])) for x in s.get("libraries", [])])

print()
print("== app.log 错误统计（全量） ==")
lp = os.path.join(ROOT, "index_data", "logs", "app.log")
lines = io.open(lp, encoding="utf-8", errors="replace").read().splitlines()
from collections import Counter
errs = Counter()
for i, l in enumerate(lines):
    if "[ERROR]" in l:
        key = l.split("[ERROR]", 1)[1].strip()[:80]
        nxt = lines[i + 1].strip()[:90] if i + 1 < len(lines) else ""
        errs[(key, nxt)] += 1
print("  总行数:", len(lines), "| ERROR 行数:", sum(errs.values()), "| 种类:", len(errs))
for (k, nxt), n in errs.most_common(12):
    print("   %4d × %s" % (n, k))
    if nxt:
        print("          └ %s" % nxt)
