# -*- coding: utf-8 -*-
"""把真机截图降采样成 ASCII 亮度图，用于在无法读图的环境里判断画面内容。"""
import os, sys
from PySide6.QtGui import QImage

D = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1300/dev/screenshots_v1300_live"
NAMES = ["91_live_actors_az.png", "92_live_actors_jump_C.png", "93_live_directors_az.png"]
CW, CH = 96, 40          # ASCII 网格
RAMP = " .:-=+*#%@"

def show(name):
    p = os.path.join(D, name)
    img = QImage(p)
    if img.isNull():
        print("%s  读不出来" % name); return
    w, h = img.width(), img.height()
    print("\n=== %s  %dx%d  %d B ===" % (name, w, h, os.path.getsize(p)))
    cw = w / CW; chh = h / CH
    tot = 0
    for r in range(CH):
        line = []
        for c in range(CW):
            x0, x1 = int(c*cw), max(int(c*cw)+1, int((c+1)*cw))
            y0, y1 = int(r*chh), max(int(r*chh)+1, int((r+1)*chh))
            s = n = 0
            for y in range(y0, min(y1, h), max(1, (y1-y0)//6)):
                for x in range(x0, min(x1, w), max(1, (x1-x0)//6)):
                    px = img.pixelColor(x, y)
                    s += (px.red()*299 + px.green()*587 + px.blue()*114)//1000
                    n += 1
            v = s // max(1, n)
            tot += v
            line.append(RAMP[min(len(RAMP)-1, v*len(RAMP)//256)])
        print("".join(line))
    print("平均亮度 %d" % (tot // (CW*CH)))

for n in NAMES:
    show(n)
