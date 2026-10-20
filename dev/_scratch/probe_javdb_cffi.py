# -*- coding: utf-8 -*-
"""用 curl_cffi 浏览器指纹试闯 JavDB 的 Cloudflare（经系统代理）。"""
import json
PROXY = "http://127.0.0.1:8899"
try:
    from curl_cffi import requests as creq
except Exception as e:
    print("curl_cffi 不可用:", e); raise SystemExit

URLS = [
    ("JavDB search(ja)", "https://javdb.com/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C&f=all"),
    ("JavDB actresses", "https://javdb.com/actresses"),
]
for label, url in URLS:
    try:
        r = creq.get(url, impersonate="chrome124", proxies={"http": PROXY, "https": PROXY},
                     timeout=20, headers={"Accept-Language": "ja,en;q=0.8"})
        body = r.text
        low = body[:3000].lower()
        challenge = any(k in low for k in ("just a moment", "cf-browser-verification",
                                           "challenge-platform", "enable javascript"))
        print(f"[{label}] status={r.status_code} len={len(body)} challenge={challenge}")
        if not challenge and r.status_code == 200:
            print("  HEAD:", body[:400].replace("\n", " ")[:400])
    except Exception as e:
        print(f"[{label}] ERR {type(e).__name__}: {e}")
