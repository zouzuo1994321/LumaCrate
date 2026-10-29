# -*- coding: utf-8 -*-
"""从扫描中帧里裁出状态栏右侧，4 倍放大看清文字。"""
import os
from PIL import Image

base = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
src = sys_name = None
for i in (1, 3, 5):
    p = os.path.join(base, "_exe2_scan_%d.png" % i)
    im = Image.open(p).convert("RGB")
    W, H = im.size
    c = im.crop((1180, H - 26, W, H - 2)).resize(((W - 1180) * 4, 24 * 8), Image.LANCZOS)
    out = os.path.join(base, "v14613_exe_during_right_%d.png" % i)
    c.save(out)
    print(out, c.size)
