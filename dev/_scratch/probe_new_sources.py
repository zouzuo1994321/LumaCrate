# -*- coding: utf-8 -*-
"""探测 R18.dev / avbase.net / JavDB 在本机（经系统代理 + 直连）的可达性与反爬强度。"""
import socket, ssl, json, time, urllib.request, urllib.error, sys

PROXY = "http://127.0.0.1:8899"

TARGETS = [
    ("R18.dev API", "https://r18.dev/videos/vod/movies/detail/-/dvd_id=SSIS-001/json"),
    ("avbase home", "https://www.avbase.net/"),
    ("JavDB home", "https://javdb.com/"),
    ("JavDB search", "https://javdb.com/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C&f=all"),
]

def probe(url, via_proxy, timeout=12):
    t0 = time.time()
    handlers = []
    if via_proxy:
        handlers.append(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))  # 直连，忽略环境代理
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept": "text/html,application/json,*/*",
        "Accept-Language": "ja,en;q=0.8",
    })
    try:
        r = opener.open(req, timeout=timeout)
        body = r.read(4000)
        ms = int((time.time() - t0) * 1000)
        low = body[:2000].lower()
        challenge = any(k in low for k in (b"challenge", b"cf-browser-verification",
                                           b"aws-waf", b"just a moment", b"enable javascript"))
        ctype = r.headers.get("Content-Type", "")
        return {"ok": True, "status": r.status, "ms": ms, "len": len(body),
                "ctype": ctype, "challenge": challenge}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "ms": int((time.time()-t0)*1000),
                "err": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "ms": int((time.time()-t0)*1000), "err": f"{type(e).__name__}: {e}"}

for label, url in TARGETS:
    for via in (True, False):
        tag = "代理" if via else "直连"
        r = probe(url, via)
        print(f"[{label} · {tag}] {json.dumps(r, ensure_ascii=False)}", flush=True)
