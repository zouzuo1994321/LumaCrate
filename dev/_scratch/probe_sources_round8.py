# -*- coding: utf-8 -*-
"""Round8 收口：JavDB profile 字段标记；avbase 按姓名取详情 + 检索 + 全 JS API 扫描。"""
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
    print("############ JavDB profile 字段标记（希月あまね）############")
    try:
        r = get("https://javdb.com/actors/AzvOe")
        t = r.text or ""
        # 定位 profile 区块：找 actress 信息面板
        # JavDB 用 <div class="actor-profile"> 或 table；dump 含 "Birthday"/"生日" 的上下文
        for kw in ("Birthday", "Height", "Bust", "Waist", "Hip", "Blood", "Cup"):
            i = t.find(kw)
            if i >= 0:
                print(f"[{kw}] ->", re.sub(r"\s+", " ", t[i:i + 90]))
        # 面板 class
        for cls in set(re.findall(r'class=["\']([^"\']*(?:profile|meta|detail|info)[^"\']*)["\']', t, re.I)):
            print("class:", cls)
        # 图片
        imgs = re.findall(r'(https?://[^"\']+\.(?:jpg|jpeg|png|webp))', t)
        imgs = [u for u in imgs if "javdb" not in u and "icon" not in u and "logo" not in u]
        print("外链图片样本:", imgs[:6])
    except Exception as e:
        print("JavDB EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase 按姓名取详情 ############")
    try:
        for u in ("https://avbase.net/_next/data/%s/talents/%E7%B3%B8%E4%BA%95%E7%91%A0%E8%8A%B1.json" % BUILD,
                  "https://avbase.net/talents/%E7%B3%B8%E4%BA%95%E7%91%A0%E8%8A%B1"):
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
            if rr.status_code == 200 and "糸井" in body:
                i = body.find("糸井")
                print("    含女优名，片段:", re.sub(r"\s+", " ", body[i:i + 200]))
    except Exception as e:
        print("avbase EXC", type(e).__name__, str(e)[:160])

    print("\n############ avbase 检索页是否内嵌结果 + 全 JS API ############")
    try:
        r = get("https://avbase.net/search?q=%E7%B3%B8%E4%BA%95%E7%91%A0%E8%8A%B1")
        t = r.text or ""
        print("search 页 len", len(t), "含女优名:", "糸井" in t, " 含 talent:", "talent" in t.lower())
        scripts = re.findall(r'src=["\'](/_next/static/[^"\']+\.js)["\']', t)
        apis = set()
        for s in scripts:
            try:
                js = get("https://avbase.net" + s).text or ""
            except Exception:
                continue
            for m in re.finditer(r'["\'`]((?:https?:)?//[a-zA-Z0-9\.\-]*avbase[^"\'`]{2,50}|/api/[^"\'`]{2,50}|/_next/data/[^"\'`]{2,60})["\'`]', js):
                apis.add(m.group(1))
            for m in re.finditer(r'(?:fetch|axios|\.get)\(["\'`]([^"\'`]{3,60})["\'`]', js):
                apis.add("CALL:" + m.group(1)[:60])
        print("全 JS API/CALL 线索:", list(apis)[:40])
    except Exception as e:
        print("avbase JS EXC", type(e).__name__, str(e)[:160])

    print("\n=== Round8 完成 ===")


main()
