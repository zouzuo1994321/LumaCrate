# -*- coding: utf-8 -*-
"""Round10 收尾：avbase 400 错误详情→正确参数；JavDB profile 全文可见文本看真实字段。"""
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


def strip(html):
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def main():
    print("############ avbase /api/public/talents 400 错误详情 ############")
    try:
        r = get("https://avbase.net/api/public/talents")
        print("status", r.status_code)
        print("body:", r.text[:300])
        # 试常见参数名
        for qk in ("keyword", "name", "search", "query", "filter", "actress"):
            rr = get("https://avbase.net/api/public/talents?" + qk + "=" + "糸井瑠花")
            ok = rr.status_code == 200
            body = rr.text or ""
            info = ""
            if body.strip()[:1] in "{[":
                try:
                    o = rr.json()
                    if isinstance(o, dict):
                        info = "keys=%s" % list(o.keys())[:6]
                    else:
                        info = "list[%d]" % len(o)
                except Exception:
                    info = "unparse"
            hit = "糸井" in body
            print(f"  ?{qk}= -> {rr.status_code} len={len(body)} {info} 命中={hit}")
            if ok and hit:
                print("    ★正确参数:", qk, "响应片段:", re.sub(r"\s+", " ", body[:400]))
                break
    except Exception as e:
        print("avbase EXC", type(e).__name__, str(e)[:160])

    print("\n############ JavDB profile 全文可见文本 ############")
    try:
        r = get("https://javdb.com/actors/AzvOe")
        t = r.text or ""
        txt = strip(t)
        # 打印前 900 字可见文本
        print(txt[:900])
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n=== Round10 完成 ===")


main()
