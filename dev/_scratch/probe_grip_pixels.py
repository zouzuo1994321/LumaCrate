# -*- coding: utf-8 -*-
"""像素级核对 grip：① normal/hover 圆点中心 alpha 差；② 贴回页面底色后出图。"""
import os

from PIL import Image

D = r"C:/Users/zouzu/AppData/Local/Temp/lmc_grip_fzoca008"
n = Image.open(os.path.join(D, "grip_normal.png")).convert("RGBA")
h = Image.open(os.path.join(D, "grip_hover.png")).convert("RGBA")
pg = Image.open(os.path.join(D, "grip_page.png")).convert("RGBA")

W, H = n.size
print("handle size:", W, H)
x0 = (W - 36) / 2.0
y0 = (H - 4) / 2.0
for i in range(5):
    cx = int(x0 + i * 8 + 2)
    cy = int(y0 + 2)
    print(f"dot{i} normal={n.getpixel((cx, cy))} hover={h.getpixel((cx, cy))}")

# 页面底色：扫一排找不透明像素（组框内深色）
from collections import Counter
cnt = Counter()
for y in range(0, pg.height, 7):
    for x in range(0, pg.width, 11):
        px = pg.getpixel((x, y))
        if px[3] > 200:
            cnt[px[:3]] += 1
bg = cnt.most_common(1)[0][0] if cnt else (26, 22, 18)
print("page bg sample:", bg, "votes:", cnt.most_common(3))
base = Image.new("RGBA", n.size, bg + (255,))

# 把手中心 400px 宽贴到底色上，放大 3 倍看
cx = W // 2
strip_n = n.crop((cx - 200, 0, cx + 200, H))
strip_h = h.crop((cx - 200, 0, cx + 200, H))
out_n = Image.alpha_composite(base.crop((cx - 200, 0, cx + 200, H)), strip_n)
out_h = Image.alpha_composite(base.crop((cx - 200, 0, cx + 200, H)), strip_h)
out_n = out_n.resize((out_n.width * 3, out_n.height * 3), Image.NEAREST)
out_h = out_h.resize((out_h.width * 3, out_h.height * 3), Image.NEAREST)
out_n.convert("RGB").save(os.path.join(D, "grip_on_bg_normal.png"))
out_h.convert("RGB").save(os.path.join(D, "grip_on_bg_hover.png"))

# 整页里把手那一带也贴底色出一张（splitter 布局：y=12+sizes[0]）
y_handle = 12 + 465
band = pg.crop((0, y_handle, W, y_handle + 14))
band_bg = Image.new("RGBA", band.size, bg + (255,))
out_band = Image.alpha_composite(band_bg, band)
out_band = out_band.resize((out_band.width // 2, out_band.height * 4), Image.NEAREST)
out_band.convert("RGB").save(os.path.join(D, "grip_band_in_page.png"))
print("SAVED")
