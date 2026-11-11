# -*- coding: utf-8 -*-
"""把三张截图的角部放大，便于肉眼确认「黑框」。"""
import os
from PIL import Image

BASE = "C:/Users/zouzu/.workbuddy/clipboard-images"
OUT = r"E:/【01】自研软件/【26-19】本地影视中心/dev/_scratch"
JOBS = [
    ("ctx_menu_tl.png", "clipboard-2026-11-10T15-39-24-053Z-37861496.png", (495, 25, 555, 85), 6),
    ("ctx_menu_br.png", "clipboard-2026-11-10T15-39-24-053Z-37861496.png", (690, 215, 729, 262), 6),
    ("dlg_full.png", "clipboard-2026-11-10T15-39-24-054Z-899ca2e0.png", (0, 0, 458, 336), 2),
    ("dlg_tl.png", "clipboard-2026-11-10T15-39-24-054Z-899ca2e0.png", (10, 5, 60, 55), 8),
    ("dlg_blk.png", "clipboard-2026-11-10T15-39-24-054Z-899ca2e0.png", (400, 180, 458, 240), 8),
    ("hdr_zoom.png", "clipboard-2026-11-10T15-39-24-054Z-7c04631a.png", (0, 0, 105, 78), 6),
]
for name, src, box, k in JOBS:
    im = Image.open(os.path.join(BASE, src)).convert("RGB")
    c = im.crop(box)
    c = c.resize((c.width * k, c.height * k), Image.NEAREST)
    c.save(os.path.join(OUT, name))
    print(name, c.size)
