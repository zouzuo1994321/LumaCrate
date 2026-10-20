# -*- coding: utf-8 -*-
"""R18.dev 搜索能力探查：能否按关键词（女优名）检索。"""
import json, re, urllib.request, urllib.error

PROXY = "http://127.0.0.1:8899"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
     "Accept": "text/html,application/json,*/*", "Accept-Language": "ja,en;q=0.8"}

def get(url, n=6000):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    r = op.open(urllib.request.Request(url, headers=H), timeout=15)
    return r.status, r.headers.get("Content-Type", ""), r.read(n).decode("utf-8", "replace")

# 1) 首页找 search 表单
try:
    st, ct, txt = get("https://r18.dev/")
    print("== r18 home ==", st, "len", len(txt))
    for m in re.finditer(r'<form[^>]*>', txt):
        print("  FORM:", m.group(0)[:160])
    for m in re.finditer(r'action="([^"]*search[^"]*)"', txt, re.I):
        print("  SEARCH_ACTION:", m.group(1))
    for m in list(re.finditer(r'/search[^"\'\s]*', txt))[:6]:
        print("  SEARCH_HREF:", m.group(0))
except Exception as e:
    print("home err:", type(e).__name__, e)

# 2) 试几种检索 URL（看是否返回可按名解析的结果）
import urllib.parse as up
q = up.quote("三上悠亜")
for u in [f"https://r18.dev/search?keyword={q}",
          f"https://r18.dev/search?q={q}",
          f"https://r18.dev/videos/vod/movies/list/?keyword={q}",
          f"https://r18.dev/videos/vod/search/-/keyword={q}/json"]:
    try:
        st, ct, txt = get(u, 3000)
        hit = ("三上" in txt) or ("ゆあ" in txt) or ("Yua" in txt) or ("search_word" in txt.lower())
        print(f"try {u}\n   -> {st} {ct} len={len(txt)} hit={hit} head={txt[:90]!r}")
    except urllib.error.HTTPError as e:
        print(f"try {u} -> HTTP {e.code}")
    except Exception as e:
        print(f"try {u} -> ERR {type(e).__name__}: {e}")
