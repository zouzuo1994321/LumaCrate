# -*- coding: utf-8 -*-
"""v1.46.6 诊断：演员库 / 导演库的 列数自适应 / 两侧留白 / 滚动是否续载。

只读真实索引库（不写任何东西），离屏跑三种窗口宽度 + 滚动到 50% 再量。
"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1466"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import applog

# 只重定向日志，**不动 db_path**（要读真实库）
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import main_window as mw

mw.load_style(app)
win = mw.MainWindow()
win.show()


def settle(n=25):
    for _ in range(n):
        app.processEvents()


def dump(tag, page, grid):
    sb = grid._scrollbar
    vp = grid._viewport
    cards = len(getattr(grid, "_cards", {}) or {})
    xs = []
    for idx, w in (getattr(grid, "_cards", {}) or {}).items():
        g = w.geometry()
        if g.left() not in xs:
            xs.append(g.left())
    xs.sort()
    cw = (getattr(grid, "_card_w", 0), getattr(grid, "_card_h", 0))
    print("\n[%s]" % tag)
    print("  视口  %dx%d   页面宽 %d" % (vp.width(), vp.height(), page.width()))
    print("  body  %dx%d" % (grid._body.width(), grid._body.height()))
    print("  列数  _cols=%s  _cols_now=%s  卡片 %dx%d" %
          (grid._cols, getattr(grid, "_cols_now", None), cw[0], cw[1]))
    print("  卡片数 %d   x 列表 %s   x_off=%s" %
          (cards, xs[:12], getattr(grid, "_x_off", None)))
    print("  总行高 %d  行高 %s  滚动 max=%d value=%d" %
          (grid._body.height(), grid._row_h, sb.maximum(), sb.value()))
    if xs:
        left_gap = xs[0]
        right_gap = grid._body.width() - (xs[-1] + cw[0])
        print("  两侧留白  左=%d  右=%d" % (left_gap, right_gap))


for w, h in ((1920, 1080), (1680, 960), (2560, 1440)):
    win.resize(w, h)
    settle(6)
    page = win._view_actors()
    win.stack.addWidget(page)
    win.stack.setCurrentWidget(page)
    settle(30)
    grid = page.findChildren(mw.LazyGrid)[0]
    dump("演员库 %dx%d" % (w, h), page, grid)
    if w == 1920:
        sb = grid._scrollbar
        sb.setValue(int(sb.maximum() * 0.5))
        settle(20)
        dump("演员库 滚到 50%", page, grid)
        sb.setValue(int(sb.maximum() * 0.95))
        settle(20)
        dump("演员库 滚到 95%", page, grid)
    win.stack.removeWidget(page)
    page.deleteLater()
    settle(5)

print("\nPROBE_V1466_DONE")
