# -*- coding: utf-8 -*-
"""高倍裁剪：演员卡姓名行右侧（找 ☆/▲ 按钮）。"""
import os
from PIL import Image

BASE = r"C:\Users\zouzu\.workbuddy\clipboard-images"
OUT = r"Z:\【01】自研软件\【26-19】本地影视中心\dev\_scratch"
S3 = os.path.join(BASE, "clipboard-2026-09-18T10-21-05-564Z-4a836f35.png")
S1 = os.path.join(BASE, "clipboard-2026-09-18T10-21-05-559Z-a393fc95.jpg")

im = Image.open(S3).convert("RGB")
# 第 2 张卡（木村愛心，粉色选中）姓名行：卡片 x≈307..521 → 第2行 y≈404..648
b = (300, 396, 545, 470)
c = im.crop(b).resize(((b[2]-b[0])*7, (b[3]-b[1])*7), Image.LANCZOS)
c.save(os.path.join(OUT, "c_actor_namerow.png")); print("-> c_actor_namerow.png", c.size)

# 影片列：完整一列（含卡片边界）
im1 = Image.open(S1).convert("RGB")
b2 = (250, 120, 440, 1120)
c2 = im1.crop(b2).resize((int((b2[2]-b2[0])*1.9), int((b2[3]-b2[1])*1.9)), Image.LANCZOS)
c2.save(os.path.join(OUT, "c_poster_col1b.png")); print("-> c_poster_col1b.png", c2.size)

# 行 profile（S1）找影片卡上下边界
imL = im1.convert("L"); px = imL.load(); W, H = imL.size
rows = []
for y in range(H):
    s = 0
    for x in range(260, 1900, 4):
        s += px[x, y]
    rows.append(s / ((1900-260)//4))
print("\nS1 行亮度突变点:")
prev = None
for y in range(60, H):
    v = rows[y]
    if prev is not None and abs(v-prev) > 3.5:
        print("  y=%4d lum=%.1f Δ=%+.1f" % (y, v, v-prev))
    prev = v
