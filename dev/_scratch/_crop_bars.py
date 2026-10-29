# -*- coding: utf-8 -*-
import os
from PIL import Image

base = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
for n in ["_exe_scan_0", "_exe_scan_1", "_exe_scan_2", "_exe_scan_3"]:
    p = os.path.join(base, n + ".png")
    im = Image.open(p).convert("RGB")
    c = im.crop((1150, 1030, 1920, 1080)).resize((770 * 2, 50 * 5), Image.LANCZOS)
    c.save(os.path.join(base, n + "_bar.png"))
    print(n, c.size)

p = r"C:\Users\zouzu\AppData\Local\Temp\lmc_exe_v14613\index_data\logs\app.log"
t = open(p, encoding="utf-8", errors="replace").read().splitlines()
print("---log tail---")
for ln in t[-8:]:
    print(ln)
