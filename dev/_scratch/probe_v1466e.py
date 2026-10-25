# -*- coding: utf-8 -*-
"""v1.46.6 诊断 4：影片墙横向滚动条到底是谁撑出来的。"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1466e"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import applog

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import main_window as mw

mw.load_style(app)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
for _ in range(20):
    app.processEvents()

page = win._wall_page("全部")
win.stack.addWidget(page)
win.stack.setCurrentWidget(page)
for _ in range(35):
    app.processEvents()

host = page.widget()
lg = host.findChildren(mw.LazyGrid)[0]
print("viewport  = %d x %d" % (page.viewport().width(), page.viewport().height()))
print("host      = %d  最小宽 %d" % (host.width(), host.minimumSizeHint().width()))
print("body      = %d" % lg._body.width())
print("h-scroll  max=%d  page=%d" % (page.horizontalScrollBar().maximum(),
                                     page.horizontalScrollBar().pageStep()))
print("\n各子控件最小宽（谁 > viewport-40 就是它挤出来的）：")
for ch in host.findChildren(QWidget)[:40]:
    mn = ch.minimumSizeHint().width()
    if mn >= page.viewport().width() - 60:
        print("  %-28s min=%4d  hint=%4d 实际=%4d"
              % (type(ch).__name__, mn, ch.sizeHint().width(), ch.width()))
print("\nPROBE_V1466E_DONE")
