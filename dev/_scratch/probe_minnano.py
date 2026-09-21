# -*- coding: utf-8 -*-
"""只读诊断：抓一个 minnano 女优页，dump 各标签在 HTML 里的**结构**上下文。

目的：确认「生年月日 / 尺寸」等标签在正文里的真实 HTML 形态，
从而把 scraper._label_value 修对（v1.11.0 的修法显然没覆盖真实形态）。
不写数据库、不做任何修改。
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

import scraper as sc

LOG = r"C:/Users/zouzu/AppData/Local/Temp/minnano_struct.log"
OUT = open(LOG, "w", encoding="utf-8")


def p(*a):
    print(*a, file=OUT, flush=True)


st = json.load(open(os.path.join(ROOT, "settings.json"), encoding="utf-8"))
proxy = (st.get("scraper") or {}).get("proxy") or ""
p("proxy =", proxy)

url = "https://www.minnano-av.com/actress272292.html"      # ひなの花音
try:
    text = sc.http_get(url, 15, proxy, referer=sc.MINNANO_BASE)
except Exception as e:
    p("!! http_get 失败:", type(e).__name__, e)
    OUT.close()
    sys.exit(1)

p("HTML 长度 =", len(text))
mh = re.search(r"</head\s*>", text, re.I)
p("找到 </head>:", bool(mh), "at", mh.end() if mh else None)
p("</head> 后长度 =", len(text) - mh.end() if mh else -1)

# 1) 各标签在全文里的出现位置（前 8 次）
for label in ("生年月日", "サイズ", "出身地", "所属事務所", "別名", "趣味・特技",
              "AV出演期間", "デビュー作品"):
    idxs = [m.start() for m in re.finditer(re.escape(label), text)][:8]
    p("\n=== 标签 %r 出现 %d 次: %s" % (label, len(idxs), idxs))

# 2) 正文里每个标签的上下文：把标签与紧随其后 160 字符原样打印（含标签记号化）
p("\n########## 正文上下文（仅 </head> 之后）##########")
body = text[mh.end():] if mh else text
for label in ("生年月日", "サイズ", "出身地", "所属事務所", "別名"):
    p("\n---------- %s ----------" % label)
    for i, m in enumerate(list(re.finditer(re.escape(label), body))[:5]):
        seg = body[m.start(): m.start() + 190]
        seg = seg.replace("\n", " ").replace("\r", " ")
        p("  [%d] @%d  %s" % (i, m.start(), seg))

# 3) 找找正文里的资料表：形如 <th>/<td> 包住标签
p("\n########## 资料表候选（<th> 或 <td> 内含标签）##########")
for label in ("生年月日", "サイズ", "出身地"):
    pat = r"<(th|td|dt|span|div)\b[^>]*>[^<]{0,12}%s[^<]{0,12}</\1>" % re.escape(label)
    for m in list(re.finditer(pat, text, re.S | re.I))[:4]:
        p("  %s -> %r" % (label, m.group(0)[:120]))

# 4) 正文里是否还有 og:description 字样
p("\n########## 正文中 'og:description' 出现次数: %d" %
  len(re.findall(r"og:description", body, re.I)))
for m in list(re.finditer(r"og:description", body, re.I))[:3]:
    p("  @%d  %s" % (m.start(), body[max(0, m.start() - 60): m.start() + 120].replace("\n", " ")))

# 5) 现有解析器在当前实现下的产出
p("\n########## 当前解析结果 ##########")
for label in ("生年月日", "サイズ", "出身地", "所属事務所", "趣味・特技", "AV出演期間"):
    raw = sc._label_value(text, label)
    p("  %-8s -> %r" % (label, raw))
p("  _clean_value(尺寸 raw) -> %r" % sc._clean_value(sc._label_value(text, "サイズ")))
p("  _valid_value(尺寸 raw) -> %r" % sc._valid_value(sc._label_value(text, "サイズ")))

OUT.close()
print("done ->", LOG)
