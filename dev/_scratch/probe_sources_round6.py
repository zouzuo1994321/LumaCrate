# -*- coding: utf-8 -*-
"""Round6 定稿：JavDB /actors/ 发现与资料解析；avbase talents 结构与检索；R18 影片列表页终检。"""
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
    print("############ JavDB：搜 /actors/ 链接 + /actors?q= ############")
    try:
        for u in ("https://javdb.com/search?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C&f=actress",
                  "https://javdb.com/actors?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C"):
            r = get(u)
            t = r.text or ""
            actors = []
            seen = set()
            for m in re.finditer(r'href=["\'](/actors/[^"\']+)["\']', t):
                a = m.group(1)
                if a not in seen:
                    seen.add(a)
                    actors.append(a)
            print(f"{u}\n  status {r.status_code} len {len(t)} /actors/ 链接: {actors[:10]}")
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n---- JavDB 女优资料页结构（取一个真实 /actors/）----")
    try:
        r = get("https://javdb.com/actors/censored")
        t = r.text or ""
        actors = []
        seen = set()
        for m in re.finditer(r'href=["\'](/actors/[A-Za-z0-9%=/_\-]+)["\']', t):
            a = m.group(1)
            if a not in seen and a.count("/") >= 3:
                seen.add(a)
                actors.append(a)
        print("列表页 /actors/ 样本:", actors[:6])
        if actors:
            prof = "https://javdb.com" + actors[0]
            rp = get(prof)
            tp = rp.text or ""
            print("资料页:", prof, "status", rp.status_code, "len", len(tp))
            ti = re.search(r"<title[^>]*>(.*?)</title>", tp, re.S | re.I)
            print("title:", ti.group(1).strip()[:80] if ti else "?")
            # 字段标签
            for kw in ("Birthday", "Height", "Bust", "Waist", "Hip", "Measurements", "Birthplace", "Blood", "Debut"):
                mm = re.search(re.escape(kw) + r"[^<\n]{0,50}", tp)
                if mm:
                    print(f"  [{kw}]:", re.sub(r"\s+", " ", mm.group(0))[:70])
            og = re.search(r'<meta[^>]+og:image["\'][^>]+content=["\']([^"\']+)', tp, re.I)
            print("  og:image:", (og.group(1)[:100] if og else "-"))
            # JSON-LD
            for m in re.finditer(r'application/ld\+json[^>]*>(.*?)</script>', tp, re.S | re.I):
                print("  JSON-LD:", m.group(1).strip()[:300])
    except Exception as e:
        print("JavDB prof EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase：index.json 的 talents 结构 + 检索 API ############")
    try:
        r = get("https://avbase.net/_next/data/JiPk6qKFgeRGhpRDGAHzr/index.json")
        obj = r.json()
        pp = obj.get("pageProps", {})
        pt = pp.get("popular_talents") or pp.get("newbie_talents") or []
        print("talents 数量:", len(pt))
        if pt:
            print("talent[0] 键:", list(pt[0].keys()))
            print("talent[0]:", json.dumps(pt[0], ensure_ascii=False)[:500])
        # talents 检索 API
        for api in ("/talents.json?q=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C",
                    "/talents.json", "/search/talents.json?q=ab",
                    "/actresses.json?q=ab"):
            try:
                rr = get(f"https://avbase.net/_next/data/JiPk6qKFgeRGhpRDGAHzr{api}")
                ct = rr.headers.get("content-type", "")
                body = rr.text or ""
                info = ""
                if body.strip()[:1] == "{":
                    try:
                        o = rr.json()
                        info = "keys=%s" % list(o.get("pageProps", {}).keys())
                    except Exception:
                        info = "unparse"
                print(f"  {api} -> {rr.status_code} ct={ct[:20]} len={len(body)} {info}")
            except Exception as e:
                print(f"  {api} EXC {type(e).__name__}")
    except Exception as e:
        print("avbase EXC", type(e).__name__, str(e)[:160])

    print("\n############ R18：影片列表页终检 ############")
    try:
        r = get("https://www.r18.dev/videos/vod/movies/list/?id=26225&type=actress")
        t = r.text or ""
        print("status", r.status_code, "len", len(t))
        # 女优名/资料线索
        for kw in ("actress", " Actress", "cast", "profile", "birthday"):
            mm = re.search(re.escape(kw), t, re.I)
            print(f"  含[{kw}]:", bool(mm))
        # 标题
        ti = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
        print("  title:", ti.group(1).strip()[:80] if ti else "?")
    except Exception as e:
        print("R18 EXC", type(e).__name__, str(e)[:160])

    print("\n=== Round6 完成 ===")


main()
