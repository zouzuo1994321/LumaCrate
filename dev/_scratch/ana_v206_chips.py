# -*- coding: utf-8 -*-
"""离线分析：详情页截图里「标签芯片」那一排到底长什么样（坐标 / 颜色 / 亮度）。

用来给 live_v206b_exe.py 的 chip_row 定标 —— 之前两次都是在别的行上撞了对子
（文件信息区那条更靠下的深色行）。
"""
import sys
from PIL import Image

p = r"E:/【01】自研软件/【26-19】本地影视中心/dev/screenshots/v206b_exe_cast_after_x.png"
im = Image.open(p).convert("RGB")
print("size", im.size)
px = im.load()


def runs_of(y, pred, x0=200, x1=1400):
    out, cur = [], None
    for x in range(x0, x1):
        if pred(px[x, y]):
            if cur is None:
                cur = [x, x]
            else:
                cur[1] = x
        else:
            if cur:
                out.append(tuple(cur))
                cur = None
    if cur:
        out.append(tuple(cur))
    return out


print("\n--- 每 4 行扫一次「亮度<95」的连续段（宽度 >=15 才打印）---")
for y in range(690, 1000, 4):
    r = [t for t in runs_of(y, lambda c: sum(c) // 3 < 95) if t[1] - t[0] >= 15]
    if r:
        print(y, r[:8])

print("\n--- 采样几个位置的颜色 ---")
for (x, y) in ((220, 805), (240, 805), (270, 805), (300, 805), (330, 805),
               (220, 790), (220, 820), (500, 805)):
    print((x, y), px[x, y], "bright=%d" % (sum(px[x, y]) // 3))
