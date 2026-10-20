# -*- coding: utf-8 -*-
"""Round16：JavDB 姓名→女优页正确路径。/actors?q= 是否按姓名过滤？/search?q= 里的 actress 卡？"""
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


def actors_links(t):
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href=["\'](/actors/[A-Za-z0-9]{4,12})["\'][^>]*>(.*?)</a>', t, re.S | re.I):
        slug, inner = m.group(1), m.group(2)
        if not re.search(r"[A-Z0-9]", slug.rsplit("/", 1)[-1]):
            continue
        if slug in seen:
            continue
        seen.add(slug)
        nm = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner)).strip()
        out.append((slug, nm[:30]))
    return out


def main():
    for u in ("https://javdb.com/actors?q=" + up.quote(NAME),
              "https://javdb.com/search?q=" + up.quote(NAME),
              "https://javdb.com/search?q=" + up.quote(NAME) + "&f=actress"):
        try:
            t = get(u).text or ""
            links = actors_links(t)
            print(f"\n{u}\n  len={len(t)} 含'三上悠亜'={'三上悠亜' in t} /actors/卡={len(links)}")
            for slug, nm in links[:8]:
                mark = " ★" if "三上" in nm else ""
                print(f"    {slug}  {nm}{mark}")
        except Exception as e:
            print(u, "EXC", type(e).__name__, str(e)[:100])

    # 若 /search?q= 有 actress 卡，看它周围标记（找「演員/Actress」结果盒）
    print("\n---- /search?q= 的 actress 结果盒标记 ----")
    try:
        t = get("https://javdb.com/search?q=" + up.quote(NAME)).text or ""
        i = t.find("三上悠亜")
        # 找第一个 /actors/ 链接的位置，看它附近有没有「演員」标题
        for m in re.finditer(r'/actors/[A-Za-z0-9]{4,12}', t):
            j = m.start()
            seg = re.sub(r"\s+", " ", t[max(0, j - 160):j + 40])
            print("  ", seg[-180:])
            break
    except Exception as e:
        print("EXC", type(e).__name__, str(e)[:100])

    print("\n=== Round16 完成 ===")


main()
