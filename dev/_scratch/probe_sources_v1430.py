# -*- coding: utf-8 -*-
"""v1.43.0 新源探测：gfriends / javdb / wikipedia / theprondb 可达性与结构。
只做 GET + 关键特征匹配，不写任何库。"""
import json
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"

import scraper as sc

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def probe(label, url, keys, referer=""):
    print("=" * 70)
    print(label, url)
    try:
        text = sc.http_get(url, 15, "", referer=referer or None)
        print("  OK  len=%d" % len(text))
        for k in keys:
            print("    %-28s %s" % (k, ("命中" if k in text else "—")))
        return text
    except Exception as e:
        print("  FAIL %s: %s" % (type(e).__name__, str(e)[:200]))
        return ""


# ---------- 1) gfriends ----------
t = probe("gfriends Filetree.json",
          "https://raw.githubusercontent.com/gfriends/gfriends/master/Filetree.json",
          ['"Content"', "三上悠亜", '"File"'])
if t:
    try:
        d = json.loads(t)
        print("    JSON 顶层键:", list(d.keys())[:5])
        # 打印前两个结构样本
        s = json.dumps(d, ensure_ascii=False)
        print("    片段:", s[:400].replace("\n", " "))
    except Exception as e:
        print("    JSON 解析失败:", e)

probe("gfriends 仓库首页",
      "https://github.com/gfriends/gfriends", ["gfriends", "Content"])

# ---------- 2) javdb ----------
t = probe("javdb 演员搜索", "https://javdb.com/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C&f=actor",
          ["actor", "/actors/", "三上"])
if t:
    import re
    m = re.findall(r'href="(/actors/[^"]+)"[^>]*>(.{0,80}?)<', t)
    print("    /actors/ 链接样本:", m[:5])

# ---------- 3) wikipedia ----------
t = probe("jawiki API 搜索",
          "https://ja.wikipedia.org/w/api.php?action=query&list=search&srsearch=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C&format=json&srlimit=3",
          ["query", "三上悠亜"])
if t:
    try:
        d = json.loads(t)
        print("    搜索结果:", [x["title"] for x in d["query"]["search"]])
    except Exception as e:
        print("    解析失败:", e)

probe("jawiki 页面", "https://ja.wikipedia.org/wiki/%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C",
      ["生年月日", "infobox", "身長"])

# ---------- 4) theporndb ----------
probe("theporndb 搜索", "https://theporndb.net/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C",
      ["performer", "三上"])
probe("theporndb 首页", "https://theporndb.net/", ["ThePornDB", "performer"])

print("PROBE_DONE")
