# -*- coding: utf-8 -*-
"""检查打包 exe 的「扫描中」帧：状态栏文字 + 朱红进度条 + 实时卡片。"""
import os
from PIL import Image

base = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
n = "_exe2_scan_0"
p = os.path.join(base, n + ".png")
im = Image.open(p).convert("RGB")
W, H = im.size
px = im.load()
y0, y1 = H - 24, H - 2
bright = red = 0
for y in range(y0, y1):
    for x in range(1200, 1790):
        r, g, b = px[x, y]
        if (r + g + b) // 3 > 90:
            bright += 1
    for x in range(1795, 1900):
        r, g, b = px[x, y]
        if r > 120 and g < 110 and b < 100:
            red += 1
print(n, im.size, "文字亮点", bright, "朱红px", red)

# 交付用：整条状态栏 2 倍放大（含左侧版权 + 右侧扫描文字与进度条）
c = im.crop((0, H - 32, W, H)).resize((W, 32 * 4), Image.LANCZOS)
c.save(os.path.join(base, "v14613_exe_during_bar.png"))
# 右下角局部 3 倍
d = im.crop((1300, H - 32, W, H)).resize(((W - 1300) * 3, 32 * 6), Image.LANCZOS)
d.save(os.path.join(base, "v14613_exe_during_right.png"))
print("已出图")
