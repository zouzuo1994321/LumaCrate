# -*- coding: utf-8 -*-
"""生成真机验收用的参考剪影：把 `_contact_icon` 的四种图标渲染成
**深底浅色**的 96×96 PNG（模拟真机「关于」里图标条的外观），供真机 IoU 比对。

产物 → C:/Users/zouzu/AppData/Local/Temp/lmc_ref_logos/{github,bilibili,weibo,mail}.png
"""
import os
import sys

sys.path.insert(0, r"C:\Users\zouzu\AppData\Local\Temp\lmc_v1310\src")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtGui import QGuiApplication, QPixmap, QPainter, QColor  # noqa: E402

app = QGuiApplication.instance() or QGuiApplication([])

import main_window as mw  # noqa: E402

OUT = r"C:\Users\zouzu\AppData\Local\Temp\lmc_ref_logos"
os.makedirs(OUT, exist_ok=True)

SZ = 96
# 真机图标条底色（深色卡片 #262220 附近）+ 图标着色 #e8e0d4
BG = QColor("#262220")
TINT = "#e8e0d4"

for kind in ("github", "bilibili", "weibo", "mail"):
    pm = QPixmap(SZ, SZ)
    pm.fill(BG)
    p = QPainter(pm)
    ic = mw.AboutDialog._contact_icon(kind, SZ, TINT)
    ic.paint(p, 0, 0, SZ, SZ)
    p.end()
    pth = os.path.join(OUT, "%s.png" % kind)
    pm.save(pth)
    print("  %-9s -> %s" % (kind, pth))

print("done")
