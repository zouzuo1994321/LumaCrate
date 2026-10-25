# -*- coding: utf-8 -*-
"""v1.46.3 验证：窗口尺寸/最小尺寸、横向滚动条为 0、卡片右边缘不出界。"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")

import database as db
import config as cfg

db.db_path = lambda: os.path.join(ROOT, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(tempfile.mkdtemp(), "s.json")
cfg._SETTINGS = None
db.init_db()

import main_window as mw

mw.load_style(app)
w = mw.MainWindow()
w.setAttribute(Qt.WA_DontShowOnScreen, True)
w.resize(1920, 1080)
w.show()
for _ in range(10):
    app.processEvents()

print("窗口: %dx%d | 最小: %dx%d" % (w.width(), w.height(),
                                    w.minimumWidth(), w.minimumHeight()))

for size in ((1920, 1080), (1680, 960), (2560, 1300)):
    w.resize(*size)
    for _ in range(6):
        app.processEvents()
    w.go(lambda: w._wall_page("全部"))
    for _ in range(12):
        app.processEvents()
    pg = w.stack.currentWidget()
    lg = pg.widget().findChildren(mw.LazyGrid)[0]
    hb = pg.horizontalScrollBar()
    lg._render()
    for _ in range(4):
        app.processEvents()
    body = lg._body
    # 最后一列卡片的右边缘
    right = 0
    for idx, c in lg._cards.items():
        right = max(right, c.x() + c.width())
    print("  %dx%d → hbar.max=%d | cols=%d card_w=%d | body=%d | 右缘=%d | 余量=%d"
          % (size[0], size[1], hb.maximum(), lg._cols_now, lg._card_w,
             body.width(), right, body.width() - right))

w.resize(1200, 700)
for _ in range(4):
    app.processEvents()
print("尝试缩到 1200x700 → 实际 %dx%d（应被最小尺寸限制）" % (w.width(), w.height()))
w.close()
print("PROBE3_DONE")
