# -*- coding: utf-8 -*-
"""分析演员库截图：定位卡片矩形的精确边界（行/列亮度 profile）。"""
import os
from PIL import Image

BASE = r"C:\Users\zouzu\.workbuddy\clipboard-images"
OUT = r"Z:\【01】自研软件\【26-19】本地影视中心\dev\_scratch"

S3 = os.path.join(BASE, "clipboard-2026-09-18T10-21-05-564Z-4a836f35.png")
S1 = os.path.join(BASE, "clipboard-2026-09-18T10-21-05-559Z-a393fc95.jpg")

def full_card(src, box, out, scale=2.4):
    im = Image.open(src).convert("RGB")
    c = im.crop(box).resize((int((box[2]-box[0])*scale), int((box[3]-box[1])*scale)), Image.LANCZOS)
    c.save(out); print("->", os.path.basename(out), c.size)

# 演员库：完整第一张卡（含右侧 ☆/▲）
full_card(S3, (250, 135, 640, 420), os.path.join(OUT, "c_actor_card_full.png"), 2.4)
# 影片库：第 1 列整列（含卡片上下边界）
full_card(S1, (250, 130, 430, 1110), os.path.join(OUT, "c_poster_col1.png"), 2.0)

# ---- 行亮度 profile：找卡片水平边界 ----
im = Image.open(S3).convert("L")
W, H = im.size
px = im.load()
# 只统计内容区（避开左侧边栏）
x0, x1 = 250, 1900
print("\n演员库 行平均亮度（每行，仅内容区）:")
rows = []
for y in range(0, H):
    s = 0
    for x in range(x0, x1, 4):
        s += px[x, y]
    rows.append(s / ((x1 - x0) // 4))
# 打印每 10 行的值，标出相对上一行的突变
prev = None
for y in range(60, H, 1):
    v = rows[y]
    if prev is not None and abs(v - prev) > 4.0:
        print("  y=%4d  lum=%.1f  Δ=%+.1f" % (y, v, v - prev))
    prev = v
print("  (结束)")
