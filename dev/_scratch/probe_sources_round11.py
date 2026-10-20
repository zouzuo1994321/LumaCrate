# -*- coding: utf-8 -*-
"""Round11 定稿：avbase /api/public/works 参数链 + /talents/<姓名> 直达；JavDB profile 中段字段。"""
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
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main():
    print("############ avbase /api/public/works 参数（400 会揭示）############")
    try:
        r = get("https://avbase.net/api/public/works")
        print("works 无参:", r.status_code, r.text[:200])
        for qk in ("query", "q", "keyword", "actress", "actor_id", "talent"):
            import urllib.parse as up
            rr = get("https://avbase.net/api/public/works?" + qk + "=" + up.quote("糸井瑠花"))
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
            print(f"  works?{qk}= -> {rr.status_code} len={len(body)} {info} 命中={hit}")
            if rr.status_code == 200 and hit:
                print("    ★works 检索参数:", qk)
                print("    片段:", re.sub(r"\s+", " ", body[:500]))
                break
    except Exception as e:
        print("avbase works EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase /api/public/talents?actor_id= 拿全量 ############")
    try:
        import urllib.parse as up
        # 从首页 index.json 拿一个真实 actor_id
        idx = get("https://avbase.net/_next/data/JiPk6qKFgeRGhpRDGAHzr/index.json").json()
        pt = idx["pageProps"]["popular_talents"]
        aid = pt[0]["talent"]["actors"][0]["id"]
        print("用 actor_id =", aid)
        rr = get("https://avbase.net/api/public/talents?actor_id=" + str(aid))
        print("status", rr.status_code, "len", len(rr.text or ""))
        print("片段:", re.sub(r"\s+", " ", (rr.text or "")[:700]))
    except Exception as e:
        print("avbase talent EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase /talents/<姓名> 直达 ############")
    try:
        import urllib.parse as up
        rr = get("https://avbase.net/talents/" + up.quote("糸井瑠花"))
        body = rr.text or ""
        print("status", rr.status_code, "len", len(body), "含女优名:", "糸井" in body)
        txt = strip(body)
        print("可见文本片段:", txt[:400])
    except Exception as e:
        print("avbase talents-name EXC", type(e).__name__, str(e)[:160])

    print("\n############ JavDB profile 中段字段 ############")
    try:
        r = get("https://javdb.com/actors/AzvOe")
        txt = strip(r.text or "")
        print("中段(900~2400):", txt[900:2400])
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n=== Round11 完成 ===")


main()
