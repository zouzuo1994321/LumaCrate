# -*- coding: utf-8 -*-
"""挑帧：底部文字 / 朱红进度条 / 卡片区是否都非空。"""
import os
from PIL import Image

base = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
for i in range(7):
    n = "_exe2_scan_%d" % i
    p = os.path.join(base, n + ".png")
    im = Image.open(p).convert("RGB")
    W, H = im.size
    px = im.load()
    y0, y1 = H - 24, H - 2
    bright = red = cards = 0
    for y in range(y0, y1):
        for x in range(1200, 1790):
            r, g, b = px[x, y]
            if (r + g + b) // 3 > 90:
                bright += 1
        for x in range(1795, 1900):
            r, g, b = px[x, y]
            if r > 120 and g < 110 and b < 100:
                red += 1
    # 卡片区金色标题像素（y 120..1000, x 130..1800）
    for y in range(120, 1000, 3):
        for x in range(130, 1800, 3):
            r, g, b = px[x, y]
            if r > 180 and g > 150 and b < 120:
                cards += 1
    print("%-14s 文字亮点=%4d 朱红=%4d 卡片金px=%5d" % (n, bright, red, cards))
