# -*- coding: utf-8 -*-
"""v1.42.2 探针 2：全宽扫描 image#3 —— 空档带是否有任何结构、粉块/按钮精确定位。"""
from PIL import Image

PATH = r"C:/Users/zouzu/.workbuddy/clipboard-images/clipboard-2026-10-18T05-27-56-497Z-62ba8166.png"
im = Image.open(PATH).convert("RGB")
W, H = im.size
px = im.load()

BG = (20, 18, 14)          # 列表底（空档带实测色）


def close(a, b, tol=6):
    return abs(a[0]-b[0]) <= tol and abs(a[1]-b[1]) <= tol and abs(a[2]-b[2]) <= tol


def is_pink(p):
    r, g, b = p
    return r > 150 and g < 150 and b > 90 and (r - g) > 50 and (b - g) > 15


print("=== 每行非背景像素数（tol=6，跳过文字行另计）===")
for y in range(H):
    n = sum(1 for x in range(W) if not close(px[x, y], BG))
    pink = sum(1 for x in range(W) if is_pink(px[x, y]))
    bar = "#" * min(60, n // 8)
    print("y=%3d  nonbg=%4d pink=%3d %s" % (y, n, pink, bar))

print("\n=== 粉色像素 x 范围（按 y 分段汇总）===")
segs = []
cur = None
for y in range(H):
    xs = [x for x in range(W) if is_pink(px[x, y])]
    if xs:
        if cur and y - cur[1] <= 1 and abs(min(xs) - cur[2]) < 30:
            cur[1] = y
            cur[2] = min(cur[2], min(xs))
            cur[3] = max(cur[3], max(xs))
        else:
            if cur:
                segs.append(cur)
            cur = [y, y, min(xs), max(xs)]
if cur:
    segs.append(cur)
for y0, y1, x0, x1 in segs:
    print("pink block y %d..%d (h=%d)  x %d..%d (w=%d)" % (y0, y1, y1-y0+1, x0, x1, x1-x0+1))
