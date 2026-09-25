# -*- coding: utf-8 -*-
"""把三张 logo 用醒目颜色合成到深底上，确认形状真的是对的。"""
import os
from PIL import Image

D = r"C:\Users\zouzu\Desktop\联系logo"
OUT = r"C:/Users/zouzu/AppData/Local/Temp/logo_check"
os.makedirs(OUT, exist_ok=True)

NAMES = ["github-1.png", "bilibili-1.png", "weibo-1.png"]
tiles = []
for fn in NAMES:
    p = os.path.join(D, fn)
    im = Image.open(p).convert("RGBA")
    # 用 alpha 当遮罩，把形状涂成鎏金 #e8c07a，底用工具窗深色
    mask = im.split()[3]
    solid = Image.new("RGBA", im.size, (232, 192, 122, 255))
    solid.putalpha(mask)
    canvas = Image.new("RGBA", im.size, (28, 23, 20, 255))
    canvas = Image.alpha_composite(canvas, solid)
    canvas = canvas.resize((200, 200), Image.LANCZOS)
    tiles.append((fn, canvas))

gap = 12
W = sum(t[1].width for t in tiles) + gap * (len(tiles) + 1)
H = max(t[1].height for t in tiles) + gap * 2
sheet = Image.new("RGB", (W, H), (24, 21, 19))
x = gap
for fn, t in tiles:
    sheet.paste(t.convert("RGB"), (x, gap))
    x += t.width + gap
sheet.save(os.path.join(OUT, "logo_shapes.png"))
print("已合成 -> %s  %s" % (os.path.join(OUT, "logo_shapes.png"), sheet.size))
