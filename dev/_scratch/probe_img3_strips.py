# -*- coding: utf-8 -*-
"""v1.42.2 探针 4：识别 x=20..42 / x=1135..1151 两条竖带的颜色与纵向跨度。"""
from PIL import Image

PATH = r"C:/Users/zouzu/.workbuddy/clipboard-images/clipboard-2026-10-18T05-27-56-497Z-62ba8166.png"
im = Image.open(PATH).convert("RGB")
W, H = im.size
px = im.load()
BG = (20, 18, 14)


def close(a, b, tol=6):
    return abs(a[0]-b[0]) <= tol and abs(a[1]-b[1]) <= tol and abs(a[2]-b[2]) <= tol


# 1) 两条竖带的颜色（取空档带内多行平均）
for x0, x1, name in ((20, 42, "左竖条"), (1135, 1151, "右竖条"), (2, 5, "左边框")):
    cols = {}
    for y in range(85, 118):
        for x in range(x0, x1 + 1):
            c = px[x, y]
            cols[c] = cols.get(c, 0) + 1
    top = sorted(cols.items(), key=lambda kv: -kv[1])[:4]
    print("%s x=%d..%d 颜色分布(前4)：%s" % (name, x0, x1, top))

# 2) 右竖条 (1135..1151) 的纵向跨度：每行是否有非背景像素
print("\n右竖条纵向跨度（x 1135..1151 有异色的 y 区间）：")
ys = [y for y in range(H) if any(not close(px[x, y], BG) for x in range(1135, 1152))]
if ys:
    segs = []
    for y in ys:
        if segs and y - segs[-1][1] <= 1:
            segs[-1][1] = y
        else:
            segs.append([y, y])
    print([(a, b) for a, b in segs])

print("\n左竖条纵向跨度（x 20..42 有异色的 y 区间）：")
ys = [y for y in range(H) if any(not close(px[x, y], BG) for x in range(20, 43))]
if ys:
    segs = []
    for y in ys:
        if segs and y - segs[-1][1] <= 1:
            segs[-1][1] = y
        else:
            segs.append([y, y])
    print([(a, b) for a, b in segs])

# 3) 对照：列表 hover 行内的颜色采样（确认列表底/组框底）
print("\n采样对照：")
for (x, y, tag) in ((600, 100, "空档中"), (600, 55, "IMDB行(hover)"), (600, 28, "y28 中"),
                    (30, 100, "左竖条@空档"), (1140, 100, "右竖条@空档"),
                    (30, 55, "左竖条@IMDB行"), (1140, 55, "右竖条@IMDB行"),
                    (30, 10, "左竖条@minnano行"), (600, 130, "按钮行")):
    print("  (%4d,%3d) %-16s rgb%s" % (x, y, tag, px[x, y]))
