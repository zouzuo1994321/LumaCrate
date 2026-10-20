# -*- coding: utf-8 -*-
"""Round15：avbase 女优头像 URL；JavDB /actors?q= 结果的名+slug 结构。"""
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
    print("############ avbase 女优头像 ############")
    try:
        t = get("https://avbase.net/talents/" + up.quote("糸井瑠花")).text or ""
        # actjpgs 直链
        act = re.findall(r'(https?://pics\.dmm\.co\.jp/mono/actjpgs/[^"\'\s\\]+)', t)
        print("actjpgs 直链:", act[:3])
        # next/image 里编码的头像
        ni = re.findall(r'/_next/image\?url=([^&"]+)', t)
        decoded = []
        for u in ni[:8]:
            try:
                decoded.append(up.unquote(u))
            except Exception:
                pass
        print("next/image url(解码前8):", decoded[:8])
        # 名字附近的第一个 img（头像通常紧贴姓名）
        i = t.find("糸井瑠花")
        seg = t[max(0, i - 1500):i]
        segimg = re.findall(r'(?:src|url)=["\']([^"\']*(?:actjpg|pics\.dmm[^"\']*act|[^"\']*avatar)[^"\']*)["\']', seg)
        print("姓名附近头像线索:", segimg[:5])
    except Exception as e:
        print("avbase EXC", type(e).__name__, str(e)[:160])

    print("\n############ JavDB /actors?q= 名+slug 结构 ############")
    try:
        t = get("https://javdb.com/actors?q=" + up.quote("三上悠亜")).text or ""
        # 结果卡片：<a href="/actors/<slug>">...名字...</a>
        cards = []
        seen = set()
        for m in re.finditer(r'<a[^>]+href=["\'](/actors/[A-Za-z0-9]{4,8})["\'][^>]*>(.*?)</a>', t, re.S | re.I):
            slug, inner = m.group(1), m.group(2)
            if slug in seen:
                continue
            seen.add(slug)
            nm = re.sub(r"<[^>]+>", " ", inner)
            nm = re.sub(r"\s+", " ", nm).strip()
            cards.append((slug, nm[:40]))
        print("卡片(前8):", cards[:8])
        # 备用：从 actors/ 容器看结构
        i = t.find("/actors/")
        if i > 0:
            print("结构样本:", re.sub(r"\s+", " ", t[i - 40:i + 260]))
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n=== Round15 完成 ===")


main()
