# -*- coding: utf-8 -*-
"""v1.46.6 验收探针：列数自适应铺满 / 两侧零留白 / 尾部可达 / 卡片高度不变。"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1466d"
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

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import main_window as mw

mw.load_style(app)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()


def settle(n=25):
    for _ in range(n):
        app.processEvents()


def row_geom(grid):
    xs, ws = [], {}
    for idx, w in (getattr(grid, "_cards", {}) or {}).items():
        g = w.geometry()
        if g.left() not in ws:
            xs.append(g.left())
            ws[g.left()] = (g.width(), g.height())
    xs.sort()
    return xs, ws


def report(tag, grid):
    xs, ws = row_geom(grid)
    if not xs:
        print("[%s] 无卡片" % tag)
        return
    g0 = ws[xs[0]]
    left = xs[0]
    right = grid._body.width() - (xs[-1] + g0[0])
    gaps = [xs[i + 1] - (xs[i] + g0[0]) for i in range(len(xs) - 1)]
    print("[%s] 列数=%d 卡片=%dx%d body=%d 左=%d 右=%d 间距=%s"
          % (tag, len(xs), g0[0], g0[1], grid._body.width(), left, right,
             (gaps[0] if gaps else "-")))


def tail_of(grid):
    sb = grid._scrollbar
    sb.setValue(sb.maximum())
    settle(18)
    idx = sorted((getattr(grid, "_cards", {}) or {}).keys())
    return (idx[-1] if idx else -1), sb.value(), sb.maximum()


# ---------- 媒体墙 ----------
wall = win._wall_page(None)
win.stack.addWidget(wall)
win.stack.setCurrentWidget(wall)
settle(35)
wg = wall.findChildren(mw.LazyGrid)[0]
report("媒体墙 1920", wg)

# ---------- 演员库 ----------
page = win._view_actors()
win.stack.addWidget(page)
win.stack.setCurrentWidget(page)
settle(35)
ag = page.findChildren(mw.LazyGrid)[0]

print("\n== 演员库：三档宽度 ==")
for w, h in ((1920, 1080), (1680, 960), (1500, 900), (2560, 1440)):
    win.resize(w, h)
    settle(10)
    ag._scrollbar.setValue(0)
    settle(12)
    report("演员库 %dx%d" % (w, h), ag)
    last, val, mx = tail_of(ag)
    ok = last >= ag._total - 1 - ag._cols_now
    print("    尾部：滚动 %d/%d 末索引 %d / 应到 %d  %s"
          % (val, mx, last, ag._total - 1, "OK" if ok else "★截断"))

# ---------- 导演库 ----------
win.resize(1920, 1080)
settle(8)
dpage = win._view_directors()
win.stack.addWidget(dpage)
win.stack.setCurrentWidget(dpage)
settle(35)
dg = dpage.findChildren(mw.LazyGrid)[0]
report("导演库 1920", dg)
last, val, mx = tail_of(dg)
print("    尾部：末索引 %d / 应到 %d  %s"
      % (last, dg._total - 1, "OK" if last >= dg._total - 1 - dg._cols_now else "★截断"))

# ---------- 卡片高度不变 ----------
print("\n卡片高度：演员 %d（应 160）  导演 %d（应 118）"
      % (mw.ACTOR_CARD_H, mw.DIRECTOR_CARD_H))
print("PROBE_V1466D_DONE")
