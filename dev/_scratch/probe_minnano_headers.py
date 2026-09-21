# -*- coding: utf-8 -*-
"""复现 minnano-av 连通性：对比 http_get 与浏览器式请求头，定位 HTTP 500 根因。"""
import os, sys, time, urllib.request, urllib.error, ssl

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
BASE = "https://www.minnano-av.com/"
URL = BASE + "search_result.php?search_scope=actress&search_word=" + urllib.parse.quote("新村あかり", encoding="utf-8")

def ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c

def fetch(label, headers):
    t0 = time.time()
    try:
        req = urllib.request.Request(URL, headers=headers)
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx()))
        raw = opener.open(req, timeout=15).read()
        print(f"[OK]   {label}: {int((time.time()-t0)*1000)}ms  bytes={len(raw)}")
    except urllib.error.HTTPError as e:
        print(f"[HTTP] {label}: {e.code}  {int((time.time()-t0)*1000)}ms")
        try:
            body = e.read().decode("utf-8", "replace")
            print("        body前200:", body[:200].replace("\n"," "))
        except Exception:
            pass
    except Exception as e:
        print(f"[ERR]  {label}: {type(e).__name__}: {e}  {int((time.time()-t0)*1000)}ms")

import urllib.parse

print("== A: 当前应用默认头（UA/Accept/Accept-Language/Accept-Encoding/Connection）==")
fetch("A", {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "close",
})

print("== B: 去掉 deflate/Connection，仅 gzip ==")
fetch("B", {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip",
})

print("== C: 浏览器式完整头（含 sec-fetch / Upgrade-Insecure-Requests / sec-ch-ua）==")
fetch("C", {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
})
