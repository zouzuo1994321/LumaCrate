# -*- coding: utf-8 -*-
"""Round9：JavDB section-meta 字段；avbase /api/public/ talents 检索与详情。"""
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
    print("############ JavDB .section-meta 字段 ############")
    try:
        r = get("https://javdb.com/actors/AzvOe")
        t = r.text or ""
        # 抓 section-meta 整块
        for m in re.finditer(r'<div[^>]*class="[^"]*section-meta[^"]*"[^>]*>(.*?)</div>\s*</div>', t, re.S):
            blk = re.sub(r"<[^>]+>", " ", m.group(1))
            blk = re.sub(r"\s+", " ", blk).strip()
            print("section-meta 文本:", blk[:400])
        # 直接找含 Height/Birthday 的行（可能是 <strong>Label</strong> value）
        i = t.find("section-meta")
        if i >= 0:
            print("原始标记:", re.sub(r"\s+", " ", t[i:i + 700]))
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase /api/public/ 探测 ############")
    base = "https://avbase.net/api/public"
    cands = [
        "/talents?query=" + "糸井瑠花",
        "/talents?q=" + "糸井瑠花",
        "/talents/" + "糸井瑠花",
        "/talents",
        "/actresses?query=ab",
        "/search/talents?q=ab",
        "/talents/search?q=ab",
    ]
    for c in cands:
        try:
            import urllib.parse as up
            # 只编码查询值部分
            if "?" in c:
                path, _, qs = c.partition("?")
                k, _, v = qs.partition("=")
                url = base + path + "?" + k + "=" + up.quote(v)
            else:
                url = base + up.quote(c)
            rr = get(url)
            ct = rr.headers.get("content-type", "")
            body = rr.text or ""
            info = ""
            if body.strip()[:1] in "{[":
                try:
                    o = rr.json()
                    if isinstance(o, dict):
                        info = "dict keys=%s" % list(o.keys())[:8]
                    else:
                        info = "list[%d]" % len(o)
                        if o and isinstance(o[0], dict):
                            info += " item0 keys=%s" % list(o[0].keys())[:8]
                except Exception:
                    info = "unparse"
            print(f"  {url}\n    -> {rr.status_code} ct={ct[:24]} len={len(body)} {info}")
            if rr.status_code == 200 and ("糸井" in body):
                print("    ★命中女优名")
        except Exception as e:
            print(f"  {c} EXC {type(e).__name__} {str(e)[:80]}")

    print("\n=== Round9 完成 ===")


main()
