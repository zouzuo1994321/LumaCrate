# -*- coding: utf-8 -*-
"""定位 C4c / E4 失败：tagopt 往返后 translated 的真实类型。"""
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_probe_tagopt")
os.makedirs(TMP, exist_ok=True)

import tagopt as tok

plans = [
    {"nfo": "D:/a/AAA-001/AAA-001.nfo", "before": ["中出し", "巨乳"],
     "after": ["中出", "巨乳", "独占"], "added": ["独占"], "error": "",
     "translated": [("中出し", "中出")], "engine": "rules"},
    {"nfo": "D:/b/BBB-002/BBB-002.nfo", "before": [], "after": ["企画"],
     "added": ["企画"], "error": "", "translated": [], "engine": "ollama"},
]

p = os.path.join(TMP, "tag.json")
tok.export_json(plans, p)
raw = json.load(io.open(p, encoding="utf-8"))
print("落盘 translated =", raw["plans"][0]["translated"],
      [type(x).__name__ for x in raw["plans"][0]["translated"]])

back = tok.import_json(p)
t = back[0]["translated"]
print("读回 translated =", t, [type(x).__name__ for x in t])
print("back[0][translated][0][0] =", repr(t[0][0]))
try:
    print("解包 OK:", list(t[0]))
except Exception as e:
    print("解包失败:", type(e).__name__, e)
print("len(t[0]) =", len(t[0]) if hasattr(t[0], "__len__") else "无")
