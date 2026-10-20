# -*- coding: utf-8 -*-
"""Round4：JavDB 卡片真实结构 / avbase 女优链接模式与 API / R18 女优检索 API 是否存在。"""
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
    print("############ JavDB 搜索 HTML 结构 ############")
    try:
        r = get("https://javdb.com/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C&f=actress")
        t = r.text or ""
        print("len", len(t), "含'三上悠亜':", "三上悠亜" in t)
        # 找 actress 盒子
        for m in re.finditer(r'actress', t):
            i = m.start()
            seg = re.sub(r"\s+", " ", t[max(0, i - 80):i + 120])
            print("  ...", seg)
            if m.start() > 40000:
                break
        # 直接看有没有 /actresses/ 或 actress-box
        print("含 '/actresses/':", "/actresses/" in t, " 含 'actress-box':", "actress-box" in t)
        # 打印 movie-box / actress 容器类名样本
        cls = set(re.findall(r'class=["\']([^"\']*(?:actress|actor|performer)[^"\']*)["\']', t, re.I))
        print("相关 class:", list(cls)[:20])
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase 首页女优链接 + API 探测 ############")
    try:
        r = get("https://avbase.net/")
        t = r.text or ""
        print("home len", len(t))
        links = []
        seen = set()
        for m in re.finditer(r'href=["\'](/[^"\']*(?:actress|actor|performer|star)[^"\']*)["\']', t, re.I):
            u = m.group(1)
            if u not in seen:
                seen.add(u)
                links.append(u)
        print("女优相关链接样本:", links[:15])
        # API 路径猜测
        for api in ("/api/actresses?query=ab", "/api/search?q=ab", "/api/v1/actresses?query=ab",
                    "/api/actress?query=ab", "/api/works?q=ab"):
            try:
                rr = get("https://avbase.net" + api)
                ct = rr.headers.get("content-type", "")
                body = rr.text or ""
                kind = ""
                if body.strip()[:1] in "{[":
                    try:
                        obj = rr.json()
                        kind = "JSON keys=%s" % (list(obj.keys()) if isinstance(obj, dict) else "list[%d]" % len(obj))
                    except Exception:
                        kind = "json-unparse"
                print(f"  API {api} -> {rr.status_code} ct={ct[:30]} len={len(body)} {kind}")
            except Exception as e:
                print(f"  API {api} EXC {type(e).__name__}")
    except Exception as e:
        print("avbase EXC", type(e).__name__, str(e)[:160])

    print("\n############ R18.dev 女优检索 API 是否存在 ############")
    try:
        for u in ("https://www.r18.dev/api/v1/actresses?keyword=ab",
                  "https://www.r18.dev/api/v1/search?q=ab",
                  "https://www.r18.dev/search/?keyword=ab",
                  "https://www.r18.dev/videos/vod/movies/list/?keyword=ab&type=actress"):
            try:
                rr = get(u)
                ct = rr.headers.get("content-type", "")
                body = rr.text or ""
                kind = ""
                if "json" in ct and body.strip()[:1] in "{[":
                    try:
                        obj = rr.json()
                        kind = "JSON keys=%s" % (list(obj.keys()) if isinstance(obj, dict) else "list[%d]" % len(obj))
                    except Exception:
                        kind = "json-unparse"
                print(f"  {u} -> {rr.status_code} ct={ct[:30]} len={len(body)} {kind}")
            except Exception as e:
                print(f"  {u} EXC {type(e).__name__}")
    except Exception as e:
        print("R18 EXC", type(e).__name__, str(e)[:160])

    print("\n=== Round4 完成 ===")


main()
