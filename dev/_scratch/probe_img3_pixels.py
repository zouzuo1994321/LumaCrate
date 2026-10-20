# -*- coding: utf-8 -*-
"""v1.42.2 探针：定量分析用户截图 image#3（IMDB 行下方留白）。

目标：判定 44px 空档的归属——
  A) 列表内「幻影空槽」（第 4 个无 widget 的 item）→ 空档色 = 列表底
  B) 列表与按钮行之间的布局空档            → 空档色 = 组框底
并量出：行槽高度 / pitch / 空档高度 / 按钮行位置，与离屏复现对照。
"""
from PIL import Image

PATH = r"C:/Users/zouzu/.workbuddy/clipboard-images/clipboard-2026-10-18T05-27-56-497Z-62ba8166.png"
im = Image.open(PATH).convert("RGB")
W, H = im.size
px = im.load()
print("image size: %d x %d" % (W, H))


def is_pink(p):
    r, g, b = p
    return r > 150 and g < 150 and b > 90 and (r - g) > 50 and (b - g) > 15


# 每行：粉色像素计数（定位 ToggleSwitch）+ 中间列颜色（定位纯色带）
rows = []
for y in range(H):
    pink = sum(1 for x in range(0, W, 3) if is_pink(px[x, y]))
    mid = px[W // 2, y]
    rows.append((pink, mid))

# 合并成「带」：颜色连续 + 粉色计数连续
bands = []   # (y0, y1, color, pink_total)
for y in range(H):
    pink, mid = rows[y]
    if bands and bands[-1][2] == mid and abs(y - bands[-1][1]) <= 1:
        bands[-1][1] = y
        bands[-1][3] += pink
    else:
        bands.append([y, y, mid, pink])

print("\n=== 横向色带（x=W/2 列）===")
for y0, y1, c, pink in bands:
    print("y %4d..%4d (h=%3d)  rgb(%3d,%3d,%3d)  pink=%d"
          % (y0, y1, y1 - y0 + 1, c[0], c[1], c[2], pink))

# 汇总：各「纯背景带」的颜色（pink=0 且非文字行）
print("\n=== 判定 ===")
for y0, y1, c, pink in bands:
    if pink == 0 and (y1 - y0 + 1) >= 6:
        print("纯色带 y %d..%d h=%d rgb(%d,%d,%d)" % (y0, y1, y1 - y0 + 1, c[0], c[1], c[2]))
