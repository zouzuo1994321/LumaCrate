# -*- coding: utf-8 -*-
"""Round5：JavDB 结果真实 href/女优链接；avbase buildId+_next/data+作品页反推女优路由；R18 关键词结果内容。"""
import json
import re
import sys

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
    print("############ JavDB：全部结果 href + 女优名标记 ############")
    try:
        r = get("https://javdb.com/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C")
        t = r.text or ""
        print("len", len(t))
        hrefs, seen = [], set()
        for m in re.finditer(r'href=["\']([^"\']+)["\']', t):
            u = m.group(1)
            if u.startswith("/search") or u.startswith("http") or "theme" in u or "locale" in u:
                continue
            if u in seen:
                continue
            seen.add(u)
            hrefs.append(u)
        print("内容页 href 样本:", hrefs[:25])
        # 女优名第一次出现的标记
        i = t.find("三上悠亜")
        if i > 0:
            print("女优名处标记:", re.sub(r"\s+", " ", t[max(0, i - 200):i + 60]))
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase：buildId + _next/data + 作品页女优路由 ############")
    try:
        r = get("https://avbase.net/")
        t = r.text or ""
        m = re.search(r'"buildId"\s*:\s*"([^"]+)"', t)
        build = m.group(1) if m else ""
        print("buildId:", build)
        if build:
            for path in ("/search.json?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C",
                         "/actresses.json", "/index.json"):
                try:
                    rr = get(f"https://avbase.net/_next/data/{build}{path}")
                    ct = rr.headers.get("content-type", "")
                    body = rr.text or ""
                    kind = ""
                    if body.strip()[:1] in "{":
                        try:
                            obj = rr.json()
                            kind = "JSON keys=%s" % list(obj.get("pageProps", {}).keys())
                        except Exception:
                            kind = "json-unparse"
                    print(f"  _next/data {path} -> {rr.status_code} ct={ct[:24]} len={len(body)} {kind}")
                except Exception as e:
                    print(f"  _next/data {path} EXC {type(e).__name__}")
        # 作品页里找女优链接
        try:
            rw = get("https://avbase.net/works/firststar:TDMN-003")
            tw = rw.text or ""
            print("作品页 status", rw.status_code, "len", len(tw))
            alinks, seen = [], set()
            for m in re.finditer(r'href=["\'](/[^"\']*(?:actress|actor|performer|cast|star)[^"\']*)["\']', tw, re.I):
                u = m.group(1)
                if u not in seen:
                    seen.add(u)
                    alinks.append(u)
            print("作品页女优链接:", alinks[:15])
        except Exception as e:
            print("作品页 EXC", type(e).__name__, str(e)[:120])
    except Exception as e:
        print("avbase EXC", type(e).__name__, str(e)[:160])

    print("\n############ R18.dev：关键词女优检索结果内容 ############")
    try:
        r = get("https://www.r18.dev/videos/vod/movies/list/?keyword=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C&type=actress")
        t = r.text or ""
        print("len", len(t), "含女优名:", "三上悠亜" in t)
        # 女优名/头像线索
        i = t.find("三上悠亜")
        if i > 0:
            print("女优名处:", re.sub(r"\s+", " ", t[max(0, i - 150):i + 80]))
        # 是否有 actress 详情页链接（非 movies/list）
        for pat in (r'href=["\']([^"\']*actress[^"\']*)["\']',):
            ls = []
            seen = set()
            for m in re.finditer(pat, t, re.I):
                u = m.group(1)
                if u not in seen:
                    seen.add(u)
                    ls.append(u)
            print("actress href:", ls[:12])
    except Exception as e:
        print("R18 EXC", type(e).__name__, str(e)[:160])

    print("\n=== Round5 完成 ===")


main()
