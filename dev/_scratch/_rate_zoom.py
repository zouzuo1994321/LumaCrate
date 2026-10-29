# -*- coding: utf-8 -*-
"""放大「我的评分」对话框截图，量出实际像素与空白区。"""
import os
from PIL import Image

SRC = [r"C:\Users\zouzu\.workbuddy\clipboard-images\clipboard-2026-10-29T12-56-12-744Z-d709d40b.png",
       r"C:\Users\zouzu\.workbuddy\clipboard-images\clipboard-2026-10-29T12-56-12-745Z-dae62a27.png"]
OUT = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"

for i, p in enumerate(SRC):
    im = Image.open(p).convert("RGB")
    W, H = im.size
    print("图%d" % (i + 1), W, H)
    im.resize((W * 4, H * 4), Image.LANCZOS).save(os.path.join(OUT, "_rate_zoom%d.png" % (i + 1)))
    px = im.load()
    # 每行的非背景（深色底 ~ #1b1b1f）像素范围，用来量内容边界
    def row_span(y):
        xs = [x for x in range(W) if max(px[x, y]) > 90]
        return (min(xs), max(xs)) if xs else None
    for y in range(0, H, 4):
        sp = row_span(y)
        if sp:
            print("  y=%3d 内容 x=%s..%s" % (y, sp[0], sp[1]))
