# -*- coding: utf-8 -*-
"""v2.0.12 探针：量「圆角外侧黑框」——统计圆角矩形外四角的像素颜色。

用法：python probe_v2012_corner.py <png> [x0 y0 x1 y1]
不给 box 时按「最亮连通区」自动猜（只适合菜单/对话框这种整块）。
"""
import sys
from PIL import Image

BASE = r"C:\Users\zouzu\.workbuddy\clipboard-images"
CHARS = " .:-=+*#%@"


def dump(path, box=None):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = im.load()
    print("size", W, H)
    if box:
        x0, y0, x1, y1 = box
        print("--- 亮度 ASCII  x=%d..%d y=%d..%d ---" % (x0, x1, y0, y1))
        for y in range(y0, y1):
            row = "".join(CHARS[min(9, sum(px[x, y]) // 3 // 26)] for x in range(x0, x1))
            print("%4d %s" % (y, row))
        print("--- 四角原始 RGB ---")
        for name, (x, y) in (("LT", (x0 + 1, y0 + 1)), ("RT", (x1 - 2, y0 + 1)),
                             ("LB", (x0 + 1, y1 - 2)), ("RB", (x1 - 2, y1 - 2))):
            print(name, (x, y), px[x, y])
    return im


if __name__ == "__main__":
    p = sys.argv[1]
    if not p.startswith("C:") and not p.startswith("\\\\"):
        p = BASE + "\\" + p
    box = tuple(int(v) for v in sys.argv[2:6]) if len(sys.argv) >= 6 else None
    dump(p, box)
