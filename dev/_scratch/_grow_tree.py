# -*- coding: utf-8 -*-
"""把临时媒体树扩到 3×3000（只为让打包版扫描慢到能抓「边扫边出片」的帧）。"""
import os

TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v14613")
N = int(os.environ.get("N_PER", "3000"))
total = 0
for pi in range(3):
    p = os.path.join(TEMP, "lib", "path-%d" % (pi + 1))
    os.makedirs(p, exist_ok=True)
    have = len(os.listdir(p))
    for i in range(have, N):
        d = os.path.join(p, "F%d_%03d" % (pi + 1, i))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>'
                    '<movie><title>演示%d-%03d</title><year>2021</year></movie>' % (pi + 1, i))
        with open(os.path.join(d, "F%d_%03d.mp4" % (pi + 1, i)), "wb") as f:
            f.write(b"\0" * 1024)
    total += len(os.listdir(p))
print("目录数:", total)
