# -*- coding: utf-8 -*-
"""深挖三源：真实女优名检索，解析卡片结构 + 详情页字段；R18.dev 找真实 API 路径。"""
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


def get(url):
    r = creq.request("GET", url, impersonate=IMP, proxies=PROXIES,
                     timeout=25, allow_redirects=True)
    return r


def dump_links(text, pat, base, limit=12):
    seen, out = set(), []
    for m in re.finditer(pat, text, re.I | re.S):
        u = m.group(1)
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= limit:
            break
    return out


def main():
    print("################ JavDB 检索（f=actress）################")
    try:
        r = get("https://javdb.com/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C&f=actress")
        t = r.text or ""
        print("status", r.status_code, "len", len(t))
        # 女优卡片：链接到 /actresses/<slug>
        links = dump_links(t, r'href=["\'](/actresses/[^"\']+)["\']', "javdb")
        print("actress links:", links[:12])
        # 抓第一个女优页
        if links:
            prof = "https://javdb.com" + links[0]
            print("\n---- 女优详情页:", prof)
            rp = get(prof)
            tp = rp.text or ""
            print("status", rp.status_code, "len", len(tp))
            print("title:", (re.search(r"<title[^>]*>(.*?)</title>", tp, re.S | re.I) or [None, "?"])[1][:80])
            # JSON-LD
            for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', tp, re.S | re.I):
                print("JSON-LD:", m.group(1).strip()[:400])
            # og:image / 生日等线索
            for k in ("og:image", "og:title", "description"):
                mm = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']*)' % k, tp, re.I)
                if mm:
                    print(f"meta {k}:", mm.group(1)[:120])
            # 出生 / 生日字段
            for kw in ("Birthday", "birthday", "生年月日", "出生", "Height", "Bust", "Measurements"):
                mm = re.search(r'%s[^<\n]{0,40}' % re.escape(kw), tp)
                if mm:
                    print(f"kw[{kw}]:", re.sub(r"\s+", " ", mm.group(0))[:80])
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n################ avbase /search ################")
    try:
        r = get("https://avbase.net/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C")
        t = r.text or ""
        print("status", r.status_code, "len", len(t))
        has_next = "__NEXT_DATA__" in t
        print("has __NEXT_DATA__:", has_next)
        # 女优链接
        links = dump_links(t, r'href=["\'](/actresses/[^"\']+|/actress/[^"\']+)["\']', "avbase")
        print("actress links:", links[:12])
        # NEXT_DATA 里看结构
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
        if m:
            try:
                obj = json.loads(m.group(1))
                print("NEXT_DATA propsPage keys:", list(obj.get("props", {}).get("pageProps", {}).keys()))
                pp = obj.get("props", {}).get("pageProps", {})
                s = json.dumps(pp, ensure_ascii=False)
                print("pageProps snippet:", s[:600])
            except Exception as e:
                print("NEXT_DATA parse fail", e)
    except Exception as e:
        print("avbase EXC", type(e).__name__, str(e)[:160])

    print("\n################ R18.dev 找 API ################")
    try:
        r = get("https://www.r18.dev/")
        t = r.text or ""
        print("status", r.status_code, "len", len(t))
        # 找 api / script / link 线索
        for pat in (r'/(api/[a-zA-Z0-9_/\-]+)', r'href=["\']([^"\']*(?:actress|search)[^"\']*)["\']',
                    r'src=["\']([^"\']+\.js[^"\']*)["\']'):
            print("pat", pat, "->", dump_links(t, pat, "r18", 15))
    except Exception as e:
        print("R18 EXC", type(e).__name__, str(e)[:160])

    print("\n=== 深挖完成 ===")


main()
