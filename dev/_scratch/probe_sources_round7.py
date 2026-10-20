# -*- coding: utf-8 -*-
"""Round7：JavDB 真实 profile 字段；avbase talent 详情路由 + 检索 API（含 JS 内 API base）。"""
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
BUILD = "JiPk6qKFgeRGhpRDGAHzr"


def get(url):
    return creq.request("GET", url, impersonate=IMP, proxies=PROXIES, timeout=25)


def main():
    print("############ JavDB 真实女优 profile 字段 ############")
    try:
        # 用搜索结果里的一个 slug
        r = get("https://javdb.com/actors/AzvOe")
        t = r.text or ""
        print("status", r.status_code, "len", len(t))
        ti = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
        print("title:", ti.group(1).strip()[:80] if ti else "?")
        for kw in ("Birthday", "生日", "Height", "身高", "Bust", "Waist", "Hip",
                   "Cup", "Blood", "Debut", "Birthplace", "Measurements"):
            for mm in re.finditer(re.escape(kw) + r"[^<\n]{0,60}", t):
                print(f"  [{kw}]:", re.sub(r"\s+", " ", mm.group(0))[:70])
                break
        og = re.search(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)', t, re.I)
        print("  og:image:", (og.group(1)[:110] if og else "-"))
        for m in re.finditer(r'application/ld\+json[^>]*>(.*?)</script>', t, re.S | re.I):
            print("  JSON-LD:", m.group(1).strip()[:300])
    except Exception as e:
        print("JavDB prof EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase talent 详情路由 ############")
    try:
        r = get("https://avbase.net/")
        t = r.text or ""
        # talent 详情链接
        for pat in (r'href=["\'](/talents?/[^"\']+)["\']', r'href=["\'](/[^"\']*talent[^"\']*)["\']'):
            ls, seen = [], set()
            for m in re.finditer(pat, t, re.I):
                u = m.group(1)
                if u not in seen:
                    seen.add(u)
                    ls.append(u)
            if ls:
                print(f"pat {pat} ->", ls[:12])
        # 直接试 talent 详情 _next/data 与 HTML（id=67596）
        for u in ("https://avbase.net/_next/data/%s/talents/67596.json" % BUILD,
                  "https://avbase.net/talents/67596",
                  "https://avbase.net/_next/data/%s/talent/67596.json" % BUILD):
            try:
                rr = get(u)
                ct = rr.headers.get("content-type", "")
                body = rr.text or ""
                info = ""
                if body.strip()[:1] == "{":
                    try:
                        o = rr.json()
                        info = "pageProps keys=%s" % list(o.get("pageProps", {}).keys())
                    except Exception:
                        info = "unparse"
                print(f"  {u} -> {rr.status_code} ct={ct[:22]} len={len(body)} {info}")
            except Exception as e:
                print(f"  {u} EXC {type(e).__name__}")
    except Exception as e:
        print("avbase EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase JS 里的 API base ############")
    try:
        r = get("https://avbase.net/")
        t = r.text or ""
        scripts = re.findall(r'src=["\'](/_next/static/[^"\']+\.js)["\']', t)
        print("JS chunk 数:", len(scripts), "样本:", scripts[:3])
        apis = set()
        for s in scripts[:6]:
            try:
                js = get("https://avbase.net" + s).text or ""
            except Exception:
                continue
            for m in re.finditer(r'["\'`](/(?:api|_next/data)/[^"\'`]{2,60})["\'`]', js):
                apis.add(m.group(1))
            for m in re.finditer(r'baseUrl[^,}]{0,40}', js):
                apis.add("BASEURL:" + m.group(0)[:60])
        print("JS 内 API/路径线索:", list(apis)[:30])
    except Exception as e:
        print("avbase JS EXC", type(e).__name__, str(e)[:160])

    print("\n=== Round7 完成 ===")


main()
