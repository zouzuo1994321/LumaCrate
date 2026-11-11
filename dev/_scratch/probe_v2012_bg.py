# -*- coding: utf-8 -*-
"""v2.0.12：三个浮层「自己画不画底色」的体检（grab 的 alpha 是硬判据）。"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import Qt                       # noqa: E402
from PySide6.QtGui import QFontDatabase            # noqa: E402
from PySide6.QtWidgets import QApplication          # noqa: E402

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw        # noqa: E402
import ui_home                  # noqa: E402
import ui_hero                  # noqa: E402

mw.load_style(app)


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def probe(name, w, pts):
    w.show()
    pump()
    img = w.grab().toImage()
    print("\n-- %s  %dx%d  styledBg=%s autoFill=%s" %
          (name, img.width(), img.height(),
           w.testAttribute(Qt.WA_StyledBackground), w.autoFillBackground()))
    for (x, y) in pts:
        if 0 <= x < img.width() and 0 <= y < img.height():
            c = img.pixelColor(x, y)
            print("   (%3d,%3d) %s alpha=%3d" % (x, y, c.name(), c.alpha()))
    w.close()
    pump(120)


dlg = ui_hero.PersonSearchDialog(initial="", old_name="月野江すい")
dlg.resize(380, 300)
probe("PersonSearchDialog", dlg, [(0, 0), (2, 2), (8, 8), (190, 290)])

pop = ui_home.ColumnFilterPopup("favorite", "收藏", None, [("是", "1"), ("否", "0")])
probe("ColumnFilterPopup", pop, [(0, 0), (2, 2), (6, 6), (120, 95)])

h = ui_home.HoverPreview()
h.set_media({"title": "测试标题", "rating": 7.5, "year": 2024})
probe("HoverPreview", h, [(0, 0), (2, 2), (6, 6), (120, 20)])
