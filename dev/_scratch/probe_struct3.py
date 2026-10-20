# -*- coding: utf-8 -*-
"""确认 R18.dev / avbase 是否有「按女优名 → 女优页」的可用路径。"""
import json, re, urllib.request

PROXY = "http://127.0.0.1:8899"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
     "Accept": "text/html,application/json,*/*", "Accept-Language": "ja,en;q=0.8"}

def get(url, n=16000):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    r = op.open(urllib.request.Request(url, headers=H), timeout=15)
    return r.status, r.headers.get("Content-Type", ""), r.read(n).decode("utf-8", "replace")

# R18.dev 首页：女优链接 href 形态
try:
    st, ct, txt = get("https://r18.dev/")
    print("== r18 home ==", st, ct, "len", len(txt))
    for h in dict.fromkeys(re.findall(r'href="([^"]+)"', txt)):
        if any(k in h.lower() for k in ("actress", "act", "star", "cast", "search")):
            print("  link:", h)
except Exception as e:
    print("r18 home err:", type(e).__name__, e)

# avbase：女优路由 + __NEXT_DATA__/api 试探
for u in ["https://www.avbase.net/actresses",
          "https://www.avbase.net/api/actresses?q=%E4%B8%89%E4%B8%8A",
          "https://www.avbase.net/api/search?q=%E4%B8%89%E4%B8%8A"]:
    try:
        st, ct, txt = get(u, 4000)
        print(f"avbase {u} -> {st} {ct} len={len(txt)} next={'__NEXT_DATA__' in txt} head={txt[:100]!r}")
    except Exception as e:
        print(f"avbase {u} -> ERR {type(e).__name__}: {e}")
