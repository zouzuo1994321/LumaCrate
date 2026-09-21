# -*- coding: utf-8 -*-
"""真实网络端到端验证：用修好的 minnano 解析器抓几位演员，看字段是否被正确填上。

只读网络 + 只打印，不写数据库。
"""
import json
import os
import sqlite3
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

import scraper as sc

LOG = r"C:/Users/zouzu/AppData/Local/Temp/minnano_verify.log"
OUT = open(LOG, "w", encoding="utf-8")


def p(*a):
    print(*a, file=OUT, flush=True)


st = json.load(open(os.path.join(ROOT, "settings.json"), encoding="utf-8"))
proxy = (st.get("scraper") or {}).get("proxy") or ""
p("proxy =", proxy)

db = os.path.join(ROOT, "index_data", "media_center.db")
con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
con.row_factory = sqlite3.Row
# 挑：①原 meta 里带「出身地」的 ②原 meta 里没有的（对照组）
rows = con.execute(
    "SELECT id,name,source_url,meta FROM people WHERE role_type='Actor' "
    "AND COALESCE(source_url,'')<>'' ORDER BY id").fetchall()
with_pref = [r for r in rows if "出身地" in (r["meta"] or "")]
without_pref = [r for r in rows if "出身地" not in (r["meta"] or "")]
out_rows = with_pref[:3] + without_pref[:2]
con.close()
p("库里带出身地关键词的: %d / 有 source_url 的: %d" % (len(with_pref), len(rows)))
p("取样本: %s" % [(r["id"], r["name"]) for r in out_rows])

for r in out_rows:
    p("\n===== %s  (id=%s) =====" % (r["name"], r["id"]))
    p("  url = %s" % r["source_url"])
    try:
        d = sc.minnano_fetch(r["source_url"], 15, proxy)
    except Exception as e:
        p("  !! 失败: %s: %s" % (type(e).__name__, e))
        continue
    for k in ("name", "alias", "birthday", "romaji", "status"):
        p("  %-9s = %r" % (k, d.get(k)))
    for k, v in (d.get("meta") or {}).items():
        p("  meta[%s] = %r" % (k, v))
    p("  bio = %r" % (d.get("bio") or "")[:200])

OUT.close()
print("done ->", LOG)
