# -*- coding: utf-8 -*-
"""量化检查打包 exe 抓图里的底部状态栏：扫描文字区是否有点亮的像素、进度条是否朱红。"""
import os
from PIL import Image

base = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
names = ["_exe_scan_0", "_exe_scan_1", "_exe_scan_2", "_exe_scan_3",
         "_exe_scan_4", "_exe_scan_5", "_exe_scan_6"]

for n in names:
    p = os.path.join(base, n + ".png")
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert("RGB")
    W, H = im.size
    if W < 100:
        print(n, "空图")
        continue
    px = im.load()
    # 状态栏 = 底部 24px
    y0, y1 = H - 24, H - 2
    bright = red = 0
    for y in range(y0, y1):
        for x in range(1200, 1790):            # 扫描文字区
            r, g, b = px[x, y]
            if (r + g + b) // 3 > 90:
                bright += 1
        for x in range(1795, 1900):            # BusyBar 槽
            r, g, b = px[x, y]
            if r > 120 and g < 110 and b < 100:
                red += 1
    print("%-14s %dx%d  文字亮点=%4d  进度条朱红px=%4d" % (n, W, H, bright, red))
