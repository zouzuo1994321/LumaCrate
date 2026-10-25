# -*- coding: utf-8 -*-
"""探测 3：gfriends 图片 URL 真取（download_photo）+ theporndb API 返回体。"""
import json
import os
import sys
import tempfile

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"

import scraper as sc

TMP = tempfile.mkdtemp(prefix="gf_")
raw = sc.http_get("https://raw.githubusercontent.com/gfriends/gfriends/master/Filetree.json", 20, "")
d = json.loads(raw)
content = d.get("Content") or {}

# 优先文件夹顺序（挑覆盖率高、画质好的）：y-Minnano / z-DMM(步) / z-DMM(骑) / 其余
PREF = ["y-Minnano", "z-DMM(步)", "z-DMM(骑)", "y-AVDC", "9-Javrave", "z-Derekhsu"]

targets = ["三上悠亜", "河北彩花", "深田えいみ"]
for t in targets:
    found = []
    for folder in PREF + [f for f in content.keys() if f not in PREF]:
        files = content.get(folder) or {}
        if t + ".jpg" in files:
            found.append((folder, files[t + ".jpg"]))
    print("==", t, "候选", found[:3])
    for folder, fn in found[:2]:
        clean = fn.split("?")[0]
        url = ("https://raw.githubusercontent.com/gfriends/gfriends/master/Content/"
               + folder + "/" + clean)
        p = sc.download_photo(url, TMP, "t_%d" % (abs(hash(url)) % 100000), 20, "")
        print("   ", url)
        print("    ->", ("OK %d KB" % (os.path.getsize(p) // 1024)) if p else "FAIL")

print()
print("== theporndb API 探测 ==")
for url in ("https://api.theporndb.net/performers?q=test",
            "https://api.theporndb.net/performers?q=%E4%B8%89%E4%B8%8A",
            "https://theporndb.net/graphql"):
    print(" 试:", url)
    try:
        t = sc.http_get(url, 15, "")
        print("   OK len=%d body=%s" % (len(t), t[:300].replace("\n", " ")))
    except Exception as e:
        print("   FAIL", type(e).__name__, str(e)[:200])
print("PROBE3_DONE")
