# -*- coding: utf-8 -*-
"""深挖 avbase 的检索/女优页结构 + R18.dev 的女优端点。"""
import json, re, urllib.request

PROXY = "http://127.0.0.1:8899"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
     "Accept": "text/html,application/json,*/*", "Accept-Language": "ja,en;q=0.8"}

def get(url, n=12000):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    r = op.open(urllib.request.Request(url, headers=H), timeout=15)
    return r.status, r.headers.get("Content-Type", ""), r.read(n).decode("utf-8", "replace")

# avbase 首页所有 href（了解 URL 方案）
try:
    st, ct, txt = get("https://www.avbase.net/")
    print("== avbase home ==", st, ct, "len", len(txt))
    hrefs = re.findall(r'href="([^"]+)"', txt)
    uniq = []
    for h in hrefs:
        if h not in uniq:
            uniq.append(h)
    for h in uniq[:40]:
        print("  href:", h)
except Exception as e:
    print("avbase home err:", type(e).__name__, e)

# avbase 试检索 URL（几种常见形态）
for u in ["https://www.avbase.net/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C",
          "https://www.avbase.net/actresses?keyword=%E4%B8%89%E4%B8%8A",
          "https://www.avbase.net/actress?name=%E4%B8%89%E4%B8%8A"]:
    try:
        st, ct, txt = get(u, 4000)
        has = "三上" in txt or "ゆあ" in txt or "Yua" in txt
        print(f"avbase try {u} -> {st} {ct} len={len(txt)} hit={has}")
    except Exception as e:
        print(f"avbase try {u} -> ERR {type(e).__name__}: {e}")

# R18.dev 女优端点试探
for u in ["https://r18.dev/actresses/1006229",
          "https://r18.dev/actress/1006229",
          "https://r18.dev/videos/vod/movies/detail/-/actress_id=1006229/json"]:
    try:
        st, ct, txt = get(u, 3000)
        print(f"R18 try {u} -> {st} {ct} len={len(txt)} head={txt[:120]!r}")
    except Exception as e:
        print(f"R18 try {u} -> ERR {type(e).__name__}: {e}")
