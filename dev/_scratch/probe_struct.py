# -*- coding: utf-8 -*-
"""取样 avbase / R18.dev 的结构，确认「按女优名检索 + 取资料」的可用端点与字段。"""
import json, re, urllib.request, urllib.error

PROXY = "http://127.0.0.1:8899"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
     "Accept": "text/html,application/json,*/*", "Accept-Language": "ja,en;q=0.8"}

def get(url, n=6000):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    req = urllib.request.Request(url, headers=H)
    r = op.open(req, timeout=15)
    return r.status, r.headers.get("Content-Type", ""), r.read(n)

# 1) R18.dev 影片 JSON（看 actress 字段结构）
try:
    st, ct, body = get("https://r18.dev/videos/vod/movies/detail/-/dvd_id=SSIS-001/json", 4000)
    print("== R18 movie JSON ==", st, ct)
    d = json.loads(body.decode("utf-8", "replace"))
    print("keys:", list(d.keys()))
    print("content_id:", d.get("content_id"), "dvd_id:", d.get("dvd_id"))
    print("actresses:", json.dumps(d.get("actresses"), ensure_ascii=False)[:600])
except Exception as e:
    print("R18 movie err:", type(e).__name__, e)

# 2) R18.dev combined（拿更全字段）
try:
    st, ct, body = get("https://r18.dev/videos/vod/movies/detail/-/dvd_id=SSIS-001/json", 4000)
    cid = json.loads(body.decode("utf-8", "replace")).get("content_id")
    if cid:
        st, ct, body = get(f"https://r18.dev/videos/vod/movies/detail/-/combined={cid}/json", 8000)
        print("== R18 combined ==", st, ct)
        d = json.loads(body.decode("utf-8", "replace"))
        print("keys:", list(d.keys()))
        print("actresses:", json.dumps(d.get("actresses"), ensure_ascii=False)[:500])
except Exception as e:
    print("R18 combined err:", type(e).__name__, e)

# 3) avbase 首页：找检索 form / actress 链接
try:
    st, ct, body = get("https://www.avbase.net/", 8000)
    txt = body.decode("utf-8", "replace")
    print("== avbase home ==", st, ct, "len", len(txt))
    for m in re.finditer(r'<form[^>]*>', txt):
        print("FORM:", m.group(0)[:200])
    for m in list(re.finditer(r'href="([^"]*actress[^"]*)"', txt))[:8]:
        print("ACTRESS_LINK:", m.group(1))
    for m in list(re.finditer(r'action="([^"]+)"', txt))[:5]:
        print("ACTION:", m.group(1))
except Exception as e:
    print("avbase home err:", type(e).__name__, e)
