# -*- coding: utf-8 -*-
"""Round17：JavDB 搜索结果里女优名的真实链接格式（姓名→profile）。"""
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
NAME = "三上悠亜"


def get(url):
    return creq.request("GET", url, impersonate=IMP, proxies=PROXIES, timeout=25)


def main():
    t = get("https://javdb.com/search?q=" + up.quote(NAME)).text or ""
    print("len", len(t))
    # 女优名每次出现的上下文
    idxs = [m.start() for m in re.finditer("三上悠亜", t)]
    print("三上悠亜 出现次数:", len(idxs))
    for i in idxs[:4]:
        seg = re.sub(r"\s+", " ", t[max(0, i - 220):i + 40])
        print("\n  上下文:", seg)
    # 全页找指向 profile 的链接（任意含 actress/actor 的 href + 姓名附近）
    print("\n-- 姓名被 <a> 包裹的形态 --")
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*三上悠亜', t):
        print("  姓名链接 ->", m.group(1))
    # 结果盒标题（是否有 Actors/演員 分区）
    for kw in ("actor-box", "actress-box", "Actors", "演員", "女优", "cast"):
        j = t.find(kw)
        print(f"  含[{kw}]:", j >= 0)

    print("\n=== Round17 完成 ===")


main()
