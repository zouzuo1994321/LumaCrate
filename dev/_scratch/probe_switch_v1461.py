# -*- coding: utf-8 -*-
"""v1.46.1 诊断：真实窗口后端下切换「全部 ↔ 媒体库」，抓所有顶层窗口（含 tooltip/popup）。"""
import os
import sys
import time

os.environ.pop("QT_QPA_PLATFORM", None)      # 用真实 windows 后端
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QTimer

app = QApplication(sys.argv)
QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")

import database as db
import config as cfg
import applog

db.db_path = lambda: os.path.join(ROOT, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(os.environ.get("TEMP", "."), "lmc_probe3.json")
cfg._SETTINGS = None
db.init_db()
applog.log_dir = lambda: os.path.join(os.environ.get("TEMP", "."), "lmc_probe3_logs")

import main_window as mw

mw.load_style(app)
w = mw.MainWindow()
w.resize(1600, 950)
w.show()
for _ in range(20):
    app.processEvents()

lib = (cfg.get_settings().libraries or [{}])[0].get("name") or "Javlibrary"


def dump(tag):
    rows = []
    for t in app.topLevelWidgets():
        if t is w or not t.isVisible():
            continue
        rows.append("%s(%r) geo=%dx%d" % (type(t).__name__, t.windowTitle()[:18],
                                          t.width(), t.height()))
    print("[%s] 额外顶层: %s" % (tag, rows or "无"))


for i in range(4):
    w.go(lambda: w._wall_page("全部"))
    for _ in range(12):
        app.processEvents()
    dump("全部#%d" % i)
    w.go(lambda: w._wall_page(lib, {"library": lib}))
    for _ in range(12):
        app.processEvents()
    dump("媒体库#%d" % i)

# 滚动：连续滚 20 步，看是否出现顶层窗口 / 渲染是否稳定
w.go(lambda: w._wall_page("全部"))
for _ in range(12):
    app.processEvents()
pg = w.stack.currentWidget()
lg = pg.widget().findChildren(mw.LazyGrid)[0]
sb = pg.verticalScrollBar()
print("total=%d built=%d row_h=%d" % (lg._total, len(lg._built), lg._row_h))
calls = []
_orig = lg._render
lg._render = lambda: (calls.append(1), _orig())[1]
for k in range(20):
    sb.setValue(sb.value() + 240)
    for _ in range(3):
        app.processEvents()
print("20 步滚动 → render 次数 %d | built=%d | 顶层=%s"
      % (len(calls), len(lg._built),
         [type(t).__name__ for t in app.topLevelWidgets()
          if t is not w and t.isVisible()]))
w.close()
print("PROBE_DONE")
