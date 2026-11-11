# -*- coding: utf-8 -*-
import os
from PIL import Image

BASE = "C:/Users/zouzu/.workbuddy/clipboard-images"
FILES = [
    "clipboard-2026-11-10T15-39-24-053Z-37861496.png",   # 右键菜单
    "clipboard-2026-11-10T15-39-24-054Z-899ca2e0.png",   # 替换对话框
    "clipboard-2026-11-10T15-39-24-054Z-7c04631a.png",   # 表头（放大）
]
for f in FILES:
    im = Image.open(os.path.join(BASE, f)).convert("RGB")
    W, H = im.size
    px = im.load()
    dark = [(x, y) for y in range(H) for x in range(W) if max(px[x, y]) <= 14]
    print(f, im.size, "near-black<=14:", len(dark))
    if dark:
        xs = [p[0] for p in dark]
        ys = [p[1] for p in dark]
        print("  bbox", min(xs), min(ys), max(xs), max(ys))
        # 按行统计，找「成块」的位置
        from collections import Counter
        cy = Counter(y for x, y in dark)
        cx = Counter(x for x, y in dark)
        print("  rows top", cy.most_common(6))
        print("  cols top", cx.most_common(6))
