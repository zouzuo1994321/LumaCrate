# -*- coding: utf-8 -*-
"""v1.43.0 新源功能验证（不写库）：假名转写 / wikipedia / theporndb / gfriends。"""
import os
import sys
import tempfile

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"

import scraper as sc

print("== 假名转写 ==")
for s in ("みかみ ゆあ", "ミカミ ユア", "いとい るか", "きょうこ", "っか"):
    print("  %-14s -> %r" % (s, sc.kana_to_romaji(s)))
print("  _romaji_queries(三上悠亜) ->", sc._romaji_queries("三上悠亜"))

print()
print("== wikipedia ==")
hits = sc.wikipedia_search("三上悠亜")
print("  search:", hits)
if hits:
    d = sc.wikipedia_fetch(hits[0]["url"])
    print("  name=%r birthday=%r alias=%r romaji=%r" %
          (d["name"], d["birthday"], d["alias"], d["romaji"]))
    print("  photo=%s" % (d["photo_url"] or "")[:110])
    print("  bio=%s" % d["bio"][:120])
    print("  meta=%s" % d["meta"])

print()
print("== theporndb ==")
hits2 = sc.theporndb_search("三上悠亜")
print("  search:", hits2[:2])
if hits2:
    d2 = sc.theporndb_fetch(hits2[0]["url"])
    print("  name=%r birthday=%r" % (d2["name"], d2["birthday"]))
    print("  photo=%s" % (d2["photo_url"] or "")[:110])
    print("  meta=%s" % d2["meta"])
    print("  bio=%s" % d2["bio"][:140])

print()
print("== gfriends ==")
TMP = tempfile.mkdtemp(prefix="gf2_")
u = sc.gfriends_photo_url("三上悠亜", cache_dir=TMP)
print("  url:", u)
if u:
    p = sc.download_photo(u, TMP, "gf_test", 25, "")
    print("  download:", ("OK %.1f KB" % (os.path.getsize(p) / 1024)) if p else "FAIL")
u2 = sc.gfriends_photo_url("不存在的名字xyz", cache_dir=TMP)
print("  不存在名 ->", repr(u2))

print()
print("== test_source 扩展 ==")
for k in ("wikipedia", "gfriends", "theporndb"):
    try:
        r = sc.test_source(k, timeout=20)
        print("  %-10s ok=%s %s" % (k, r.get("ok"), r.get("msg")[:80]))
    except Exception as e:
        print("  %-10s EXC %s %s" % (k, type(e).__name__, str(e)[:80]))
print("NEW_SOURCES_DONE")
