# -*- coding: utf-8 -*-
"""把真机截图的「选择」列裁出来放大，回答「复选框到底画没画」。"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(ROOT, "screenshots")

src_name = sys.argv[1] if len(sys.argv) > 1 else "40_live_tools_actorcheck_detect.png"
# 「选择」列大致在 x 137..186，表头 y≈190 起，数据行 y≈215 起
box = (130, 180, 340, 300)
scale = 5

img = Image.open(os.path.join(SHOT, src_name)).convert("RGB")
print("[原图]", src_name, img.size)
crop = img.crop(box)
big = crop.resize((crop.width * scale, crop.height * scale), Image.NEAREST)
out = os.path.join(SHOT, "z_zoom_%s" % src_name)
big.save(out)
print("[特写]", os.path.basename(out), big.size, "裁剪区", box)

# 逐行扫「选择」列的像素变化：复选框是 17x17 的方框 + 对勾，
# 若存在，两行之间的像素应有明显变化。
px = crop.load()
prev = None
for y in range(crop.height):
    row = [px[x, y] for x in range(crop.width)]
    if row != prev:
        # 只报告亮度变化剧烈的行
        print("  y=%3d (原图 y=%3d) 首像素=%s" % (y, box[1] + y, row[:3]))
    prev = row
