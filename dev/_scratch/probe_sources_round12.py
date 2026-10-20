# -*- coding: utf-8 -*-
"""Round12：avbase 姓名模糊检索端点确认（fresh buildId + search.json + API 猜测）。"""
import json
import re
import sys
import urllib.parse as up

try:
    from curl_cffi import requests as creq
except Exception as e:
    print("NO_CURL_CFFI", e)
    sys.exit(0)

PROXIES = {"http": "http://127.0.0.1:8899", "https": "http://127.0.0.1:8899"}
IMP = "chrome124"
NAME = "糸井瑠花"


def get(url):
    return creq.request("GET", url, impersonate=IMP, proxies=PROXIES, timeout=25)


def main():
    # fresh buildId
    home = get("https://avbase.net/").text or ""
    m = re.search(r'"buildId"\s*:\s*"([^"]+)"', home)
    build = m.group(1) if m else ""
    print("fresh buildId:", build)

    tests = [
        "https://avbase.net/_next/data/%s/search.json?q=%s" % (build, up.quote(NAME)),
        "https://avbase.net/_next/data/%s/search/talents.json?q=%s" % (build, up.quote(NAME)),
        "https://avbase.net/api/public/actresses?keyword=%s" % up.quote(NAME),
        "https://avbase.net/api/public/search?q=%s" % up.quote(NAME),
        "https://avbase.net/api/public/talents?keyword=%s" % up.quote(NAME),
        "https://avbase.net/api/public/talents?name=%s" % up.quote(NAME),
    ]
    for u in tests:
        try:
            r = get(u)
            body = r.text or ""
            ct = r.headers.get("content-type", "")
            hit = NAME in body
            info = ""
            if body.strip()[:1] in "{[":
                try:
                    o = r.json()
                    info = "keys=%s" % (list(o.keys())[:6] if isinstance(o, dict) else "list[%d]" % len(o))
                except Exception:
                    info = "unparse"
            print(f"{r.status_code} ct={ct[:20]} len={len(body)} 命中={hit} {info}\n   {u}")
            if r.status_code == 200 and hit:
                print("   ★片段:", re.sub(r"\s+", " ", body[:400]))
        except Exception as e:
            print("EXC", type(e).__name__, u, str(e)[:80])

    print("\n=== Round12 完成 ===")


main()
