# -*- coding: utf-8 -*-
"""检查用户提供的三张联系 logo png 的真实像素构成。"""
import os
from PIL import Image

D = r"C:\Users\zouzu\Desktop\联系logo"
for fn in sorted(os.listdir(D)):
    if not fn.lower().endswith(".png"):
        continue
    p = os.path.join(D, fn)
    im = Image.open(p)
    print("=" * 70)
    print("%-22s mode=%-6s size=%s  %d B" % (fn, im.mode, im.size, os.path.getsize(p)))
    rgba = im.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    # 统计：完全透明 / 不透明 / 中间
    n_tr = n_op = n_mid = 0
    lum_min, lum_max = 999, -1
    alpha_min, alpha_max = 999, -1
    colors = {}
    step = max(1, min(w, h) // 64)
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b, a = px[x, y]
            if a == 0:
                n_tr += 1
            elif a == 255:
                n_op += 1
            else:
                n_mid += 1
            alpha_min = min(alpha_min, a)
            alpha_max = max(alpha_max, a)
            if a > 8:
                lum = (r + g + b) / 3.0
                lum_min = min(lum_min, lum)
                lum_max = max(lum_max, lum)
            colors[(r, g, b, a)] = colors.get((r, g, b, a), 0) + 1
    print("  采样点 透明 %d / 半透明 %d / 不透明 %d" % (n_tr, n_mid, n_op))
    print("  alpha 范围 %d..%d   可见像素亮度 %.0f..%.0f" % (alpha_min, alpha_max, lum_min, lum_max))
    top = sorted(colors.items(), key=lambda kv: -kv[1])[:5]
    print("  主要颜色：")
    for c, n in top:
        print("     RGBA%-22s x%d" % (str(c), n))
