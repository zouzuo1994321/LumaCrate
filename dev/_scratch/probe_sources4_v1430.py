# -*- coding: utf-8 -*-
"""探测 4：gfriends LFS 媒体域 + URL 编码；theporndb API 字段与详情端点。"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"

import scraper as sc

name = "三上悠亜"
q = urllib.parse.quote(name)
folder = "y-Minnano"
fn = "三上悠亜.jpg"
raw_path = f"Content/{folder}/{fn}"
enc_path = f"Content/{urllib.parse.quote(folder)}/{urllib.parse.quote(fn)}"
cands = [
    "https://raw.githubusercontent.com/gfriends/gfriends/master/" + enc_path,
    "https://media.githubusercontent.com/media/gfriends/gfriends/master/" + enc_path,
    "https://github.com/gfriends/gfriends/raw/master/" + enc_path,
    "https://cdn.jsdelivr.net/gh/gfriends/gfriends@master/" + enc_path,
    "https://raw.githubusercontent.com/gfriends/gfriends/master/" + enc_path + "?raw=true",
]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}

print("== gfriends 候选直链 ==")
for url in cands:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            ct = r.headers.get("Content-Type", "")
            cl = r.headers.get("Content-Length", "?")
            print("  OK %-6s %-9s ct=%-24s %s" % (len(raw), type(raw), ct, url[:110]))
            if len(raw) > 500:
                print("     -> 真图，落盘测试")
                open(os.path.join(ROOT, "dev", "_scratch", "gf_sample.jpg"), "wb").write(raw)
    except Exception as e:
        print("  FAIL %-40s %s" % (type(e).__name__ + " " + str(e)[:80], url[:110]))

print()
print("== theporndb API ==")
for i, qq in enumerate(["test", "三上", name, "sannomiya", "yua"]):
    time.sleep(1.2)
    url = "https://api.theporndb.net/performers?q=" + urllib.parse.quote(qq)
    try:
        t = sc.http_get(url, 15, "")
        d = json.loads(t)
        rows = d.get("data") or []
        print("  q=%-10s rows=%d %s" % (qq, len(rows), [r.get("name") for r in rows[:3]]))
        if rows and i in (0, 2):
            r0 = rows[0]
            print("    字段:", sorted(r0.keys()))
            print("    sample:", json.dumps({k: r0.get(k) for k in
                  ("id", "name", "full_name", "slug", "image", "extras")},
                  ensure_ascii=False)[:600])
    except Exception as e:
        print("  q=%-10s FAIL %s %s" % (qq, type(e).__name__, str(e)[:120]))
print("PROBE4_DONE")
