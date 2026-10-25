# -*- coding: utf-8 -*-
"""探测 5：jawiki wikitext 信息框字段 + pageimages；theporndb 详情端点。"""
import json
import os
import sys
import time
import urllib.parse

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"

import scraper as sc

TITLE = "三上悠亜"
q = urllib.parse.quote(TITLE)
url = ("https://ja.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content"
       "&rvslots=main&titles=" + q + "&format=json&formatversion=2")
print("== wikitext ==")
t = sc.http_get(url, 20, "")
d = json.loads(t)
pages = d["query"]["pages"]
wt = pages[0]["revisions"][0]["slots"]["main"]["content"]
i = wt.find("{{Infobox")
print("  长度", len(wt), "| infobox 位置", i)
print(wt[i:i + 2000] if i >= 0 else wt[:1200])

print()
print("== pageimages ==")
u2 = ("https://ja.wikipedia.org/w/api.php?action=query&prop=pageimages&piprop=thumbnail|name"
      "&pithumbsize=600&titles=" + q + "&format=json&formatversion=2")
d2 = json.loads(sc.http_get(u2, 20, ""))
print("  ", json.dumps(d2["query"]["pages"][0], ensure_ascii=False)[:500])

print()
print("== theporndb 详情 ==")
time.sleep(2)
d3 = json.loads(sc.http_get("https://api.theporndb.net/performers?q=Yua%20Mikami", 15, ""))
pid = (d3.get("data") or [{}])[0].get("id")
print("  search id:", pid)
if pid:
    time.sleep(2)
    for u in ("https://api.theporndb.net/performers/" + pid,
              "https://api.theporndb.net/performers/" + pid + "?full=true"):
        try:
            r = json.loads(sc.http_get(u, 15, ""))
            node = r.get("data") or r
            if isinstance(node, list):
                node = node[0] if node else {}
            print("  OK", u)
            print("   ", json.dumps({k: node.get(k) for k in
                  ("name", "full_name", "image", "extras")}, ensure_ascii=False)[:700])
            break
        except Exception as e:
            print("  FAIL", u, type(e).__name__, str(e)[:100])
print("PROBE5_DONE")
