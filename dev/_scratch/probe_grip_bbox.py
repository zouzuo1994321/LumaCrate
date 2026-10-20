# -*- coding: utf-8 -*-
"""量每个圆点的真实 alpha 包围盒（不做任何缩放，排除显示失真）。"""
import os

from PIL import Image

D = r"C:/Users/zouzu/AppData/Local/Temp/lmc_grip_fzoca008"
n = Image.open(os.path.join(D, "grip_normal.png")).convert("RGBA")
W, H = n.size
alpha = n.split()[3]
px = alpha.load()

cols = [x for x in range(W) if any(px[x, y] > 0 for y in range(H))]
print("non-transparent cols:", (cols[0], cols[-1]) if cols else None, "count:", len(cols))

# 按列聚类成 5 个点
groups = []
cur = [cols[0]]
for x in cols[1:]:
    if x - cur[-1] <= 1:
        cur.append(x)
    else:
        groups.append(cur)
        cur = [x]
groups.append(cur)
print("dot column groups:", [(g[0], g[-1]) for g in groups])

for gi, g in enumerate(groups):
    x0, x1 = g[0], g[-1]
    rows = [y for y in range(H) if any(px[x, y] > 0 for x in range(x0, x1 + 1))]
    if rows:
        print(f"dot{gi}: x={x0}..{x1} (w={x1-x0+1})  y={rows[0]}..{rows[-1]} (h={rows[-1]-rows[0]+1})")
