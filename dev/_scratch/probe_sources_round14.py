# -*- coding: utf-8 -*-
"""Round14：锁定 avbase 解析——头图 img、基本情報 正则自测、name/ruby 提取。"""
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


def get(url):
    return creq.request("GET", url, impersonate=IMP, proxies=PROXIES, timeout=25)


def strip(html):
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main():
    r = get("https://avbase.net/talents/" + up.quote("糸井瑠花"))
    t = r.text or ""
    print("status", r.status_code, "len", len(t))

    # 头图候选：所有 img
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', t)
    imgs = [u for u in imgs if not any(x in u for x in ("logo", "icon", ".svg", "favicon"))]
    print("img src 前 12:", imgs[:12])
    # og:image 兼容属性顺序
    for m in re.finditer(r'<meta[^>]*>', t):
        tag = m.group(0)
        if re.search(r'og:image|twitter:image', tag, re.I):
            c = re.search(r'content=["\']([^"\']+)', tag)
            if c:
                print("meta image:", c.group(1)[:120])

    # 基本情報 正则自测（在剥离文本上）
    txt = strip(t)
    i = txt.find("基本情報")
    seg = txt[i:i + 260] if i >= 0 else ""
    print("\n基本情報 文本段:", seg)
    mb = re.search(r"生年月日\s*(\d{4}-\d{2}-\d{2})", txt)
    mp = re.search(r"出身地\s*([^\s]+(?:\s*[^\s]+)?)\s*身長", txt)
    mh = re.search(r"身長\s*(\d{2,3})\s*cm", txt)
    ms = re.search(r"サイズ\s*B(\d{2,3})(?:\(([A-Z])\))?\s*W(\d{2,3})\s*H(\d{2,3})", txt)
    mhob = re.search(r"趣味\s*([^\s]+)", txt)
    print("\n-- 正则自测 --")
    print("生日:", mb.group(1) if mb else None)
    print("出身地:", mp.group(1).strip() if mp else None)
    print("身高:", (mh.group(1) + "cm") if mh else None)
    print("三围:", (f"B{ms.group(1)}({ms.group(2)}) W{ms.group(3)} H{ms.group(4)}") if ms else None)
    print("趣味:", mhob.group(1) if mhob else None)
    # name + ruby
    mt = re.search(r"<title[^>]*>(.*?)\s*\|", t, re.S | re.I)
    print("name:", mt.group(1).strip() if mt else None)
    # ruby：名字后面紧跟的假名
    mr = re.search(r"糸井瑠花\s*(いといるか)", txt)
    print("ruby:", mr.group(1) if mr else "(需按实际名动态取)")

    print("\n=== Round14 完成 ===")


main()
