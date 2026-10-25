# -*- coding: utf-8 -*-
"""探测 2：gfriends 图片直链构造 + theporndb 正确检索路径 + javdb 其他入口。"""
import json
import os
import re
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"

import scraper as sc


def get(url, referer=None):
    return sc.http_get(url, 15, "", referer=referer)


print("== gfriends Filetree 结构 ==")
raw = get("https://raw.githubusercontent.com/gfriends/gfriends/master/Filetree.json")
d = json.loads(raw)
content = d.get("Content") or {}
print("  Content 文件夹数:", len(content))
print("  文件夹样本:", list(content.keys())[:8])
print("  Information:", json.dumps(d.get("Information"), ensure_ascii=False)[:300])

# 找 三上悠亜 所在文件夹
hits = []
for folder, files in content.items():
    if not isinstance(files, dict):
        continue
    for name, fn in files.items():
        if "三上悠亜" in name:
            hits.append((folder, name, fn))
print("  三上悠亜 命中:", hits[:5])

if hits:
    folder, name, fn = hits[0]
    for url in (
        f"https://raw.githubusercontent.com/gfriends/gfriends/master/Content/{folder}/{fn}",
        f"https://raw.githubusercontent.com/gfriends/gfriends/master/Content/{folder}/{name}",
    ):
        print("  试取:", url)
        try:
            b = sc.http_get_bytes(url, 15, "") if hasattr(sc, "http_get_bytes") else None
            print("    bytes fn 存在:", b is not None)
        except Exception as e:
            print("    FAIL", type(e).__name__, str(e)[:120])

print()
print("== theporndb 首页结构 ==")
home = get("https://theporndb.net/")
print("  len", len(home))
for pat in (r'<form[^>]+action="([^"]+)"', r'href="(/performers[^"]*)"',
            r'href="(/search[^"]*)"', r'href="(/movies[^"]*)"'):
    print(" ", pat, "->", re.findall(pat, home)[:6])

for url in ("https://theporndb.net/performers?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C",
            "https://theporndb.net/performers?search=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C",
            "https://theporndb.net/search?query=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C",
            "https://api.theporndb.net/performers?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C"):
    print("  试:", url)
    try:
        t = get(url)
        print("    OK len=%d | 含三上:%s | 含performer:%s"
              % (len(t), "三上" in t, "performer" in t.lower()))
        m = re.findall(r'href="(/performers/[^"]+)"', t)[:4]
        print("    /performers/ 链接:", m)
    except Exception as e:
        print("    FAIL", type(e).__name__, str(e)[:120])

print()
print("== javdb 其他入口 ==")
for url in ("https://javdb.com/", "https://javdb.com/actors",
            "https://javdb.com/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C"):
    print("  试:", url)
    try:
        t = get(url)
        print("    OK len=%d" % len(t))
    except Exception as e:
        print("    FAIL", type(e).__name__, str(e)[:100])

print("PROBE2_DONE")
