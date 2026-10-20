# -*- coding: utf-8 -*-
"""探测 R18.dev / avbase.net / JavDB 的真实女优检索/资料端点。
走系统代理 127.0.0.1:8899（实测 R18/avbase 代理下可达），curl_cffi chrome 指纹。
只读探结构，不写任何东西。
"""
import json
import re
import sys

try:
    from curl_cffi import requests as creq
except Exception as e:
    print("NO_CURL_CFFI", e)
    sys.exit(0)

PROXY = "http://127.0.0.1:8899"
PROXIES = {"http": PROXY, "https": PROXY}
IMP = "chrome124"

CANDS = {
    "r18": [
        ("GET", "https://www.r18.dev/"),
        ("GET", "https://www.r18.dev/api/v1/actresses?query=ab"),
        ("GET", "https://www.r18.dev/search?query=ab"),
        ("GET", "https://www.r18.dev/actresses"),
        ("GET", "https://www.r18.dev/api/v1/actresses/abc"),
    ],
    "avbase": [
        ("GET", "https://avbase.net/"),
        ("GET", "https://avbase.net/actresses"),
        ("GET", "https://avbase.net/api/actresses"),
        ("GET", "https://avbase.net/actresses?q=ab"),
        ("GET", "https://avbase.net/search?q=ab"),
    ],
    "javdb": [
        ("GET", "https://javdb.com/"),
        ("GET", "https://javdb.com/search?q=ab&f=actress"),
        ("GET", "https://javdb.com/actresses/abc"),
    ],
}


def probe(tag, method, url):
    try:
        r = creq.request(method, url, impersonate=IMP, proxies=PROXIES,
                         timeout=20, allow_redirects=True)
    except Exception as e:
        print(f"[{tag}] {method} {url}\n    EXC {type(e).__name__}: {str(e)[:120]}")
        return
    ct = r.headers.get("content-type", "")
    body = r.text or ""
    low = body.lower()
    is_cf = ("cf-challenge" in low or "just a moment" in low
             or "cf-browser-verification" in low or "checking your browser" in low)
    print(f"[{tag}] {method} {url}")
    print(f"    status={r.status_code} ct={ct[:40]} len={len(body)} cf_challenge={is_cf}")
    # 抽一点结构线索
    head = re.sub(r"\s+", " ", body[:400])
    print(f"    head: {head[:300]}")
    # JSON API 的话看看键
    if "json" in ct and body.strip()[:1] in "{[":
        try:
            obj = r.json()
            keys = list(obj.keys()) if isinstance(obj, dict) else "(list len=%d)" % len(obj)
            print(f"    JSON keys: {keys}")
        except Exception as e:
            print(f"    JSON parse fail: {e}")
    print("")


def main():
    for tag, lst in CANDS.items():
        for method, url in lst:
            probe(tag, method, url)
    print("=== 探测完成 ===")


main()
