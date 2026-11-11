# -*- coding: utf-8 -*-
"""v2.0.12：PersonSearchDialog 去掉 autoFillBackground 后到底还画不画底色。"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import Qt                      # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw       # noqa: E402
import ui_hero                 # noqa: E402

mw.load_style(app)

dlg = ui_hero.PersonSearchDialog(initial="", old_name="月野江すい")
print("stylesheet      :", dlg.styleSheet()[:80])
print("WA_StyledBackground:", dlg.testAttribute(Qt.WA_StyledBackground))
print("autoFillBackground :", dlg.autoFillBackground())
print("translucent        :", dlg.testAttribute(Qt.WA_TranslucentBackground))
dlg.resize(380, 300)
dlg.show()
end = time.time() + 0.5
while time.time() < end:
    app.processEvents()
    time.sleep(0.01)

pm = dlg.grab()
img = pm.toImage()
print("grab size", img.width(), img.height())
for (x, y) in ((6, 6), (20, 20), (190, 150), (370, 10)):
    c = img.pixelColor(x, y)
    print("  pix(%3d,%3d) = %s  alpha=%d" % (x, y, c.name(), c.alpha()))
# 四角是否有黑
for (x, y) in ((0, 0), (img.width() - 1, 0), (0, img.height() - 1), (img.width() - 1, img.height() - 1)):
    c = img.pixelColor(x, y)
    print("  corner(%3d,%3d) = %s alpha=%d" % (x, y, c.name(), c.alpha()))
dlg.close()
