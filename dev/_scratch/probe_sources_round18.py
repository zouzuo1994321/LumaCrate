# -*- coding: utf-8 -*-
"""Round18：JavDB 影片页演员链接格式，判断能否可靠两跳（搜影片→演员→profile）。"""
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
    # 一部三上悠亜的影片页
    t = get("https://javdb.com/v/WwBMq").text or ""
    print("影片页 len", len(t))
    # 演员区链接
    casts = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href=["\'](/actors/[A-Za-z0-9]{4,12})["\'][^>]*>(.*?)</a>', t, re.S | re.I):
        slug, inner = m.group(1), m.group(2)
        if slug in seen:
            continue
        seen.add(slug)
        nm = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner)).strip()
        casts.append((slug, nm[:30]))
    print("演员链接:", casts[:10])
    # 演员区标记
    for kw in ("Cast", "演員", "女优", "Actor"):
        print(f"  含[{kw}]:", kw in t)
    print("\n=== Round18 完成 ===")


main()
