# -*- coding: utf-8 -*-
"""v1.42.2 探针 3：定位空档带 / y23..35 带里 41 个非背景像素的 x 位置。"""
from PIL import Image

PATH = r"C:/Users/zouzu/.workbuddy/clipboard-images/clipboard-2026-10-18T05-27-56-497Z-62ba8166.png"
im = Image.open(PATH).convert("RGB")
W, H = im.size
px = im.load()
BG = (20, 18, 14)


def close(a, b, tol=6):
    return abs(a[0]-b[0]) <= tol and abs(a[1]-b[1]) <= tol and abs(a[2]-b[2]) <= tol


for label, y0, y1 in (("空档带 80..123", 80, 123), ("y23..35 带", 23, 35)):
    print("=== %s ===" % label)
    for y in (y0, (y0 + y1) // 2, y1):
        xs = [x for x in range(W) if not close(px[x, y], BG)]
        # 汇总成区间
        segs = []
        for x in xs:
            if segs and x - segs[-1][1] <= 2:
                segs[-1][1] = x
            else:
                segs.append([x, x])
        print("y=%3d nonbg=%d  segs=%s" % (y, len(xs), [(a, b) for a, b in segs][:20]))

# 顺便：IMDB 行（36..79）的像素结构对照（按钮在哪）
print("\n=== IMDB 行 y=55 对照 ===")
y = 55
xs = [x for x in range(W) if not close(px[x, y], BG)]
segs = []
for x in xs:
    if segs and x - segs[-1][1] <= 2:
        segs[-1][1] = x
    else:
        segs.append([x, x])
print("y=%3d nonbg=%d  segs=%s" % (y, len(xs), [(a, b) for a, b in segs][:30]))

# minnano 行 y=10 对照
print("\n=== minnano 行 y=10 对照 ===")
y = 10
xs = [x for x in range(W) if not close(px[x, y], BG)]
segs = []
for x in xs:
    if segs and x - segs[-1][1] <= 2:
        segs[-1][1] = x
    else:
        segs.append([x, x])
print("y=%3d nonbg=%d  segs=%s" % (y, len(xs), [(a, b) for a, b in segs][:30]))
