# -*- coding: utf-8 -*-
"""Round13：取 avbase 基本情報面板原始 HTML + 头图；JavDB 头图。用于定稿解析器。"""
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


def get(url):
    return creq.request("GET", url, impersonate=IMP, proxies=PROXIES, timeout=25)


def main():
    print("############ avbase 基本情報面板原始 HTML ############")
    try:
        r = get("https://avbase.net/talents/" + up.quote("糸井瑠花"))
        t = r.text or ""
        # og:image / twitter:image
        for k in ("og:image", "twitter:image"):
            m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']+)' % k, t, re.I)
            if m:
                print(f"{k}:", m.group(1)[:120])
        # 基本情報 面板原始 HTML
        i = t.find("基本情報")
        if i >= 0:
            print("基本情報 原始 HTML(前后):")
            print(re.sub(r"\s+", " ", t[i - 60:i + 900]))
        # 女优主名 + ruby
        mt = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
        print("title:", mt.group(1).strip()[:60] if mt else "?")
    except Exception as e:
        print("avbase EXC", type(e).__name__, str(e)[:160])

    print("\n############ JavDB 头图 ############")
    try:
        r = get("https://javdb.com/actors/AzvOe")
        t = r.text or ""
        for k in ("og:image",):
            m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']+)' % k, t, re.I)
            if m:
                print(f"{k}:", m.group(1)[:120])
        av = re.findall(r'(https?://c\d\.jdbstatic\.com/avatars/[^"\']+\.(?:jpg|png|webp))', t)
        print("avatars 图:", av[:3])
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n=== Round13 完成 ===")


main()
