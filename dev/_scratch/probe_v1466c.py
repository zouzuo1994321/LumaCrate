# -*- coding: utf-8 -*-
"""v1.46.6 诊断 3：媒体墙 vs 演员库的卡片几何对比 + 滚轮打在卡片上能否续载。"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1466c"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFontDatabase, QWheelEvent
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
for _ in range(25):
    app.processEvents()


def settle(n=25):
    for _ in range(n):
        app.processEvents()


def geom(grid):
    xs, ws = [], {}
    for idx, w in (getattr(grid, "_cards", {}) or {}).items():
        g = w.geometry()
        if g.left() not in xs:
            xs.append(g.left())
            ws[g.left()] = (g.width(), g.height())
    xs.sort()
    return xs, ws


def dump(tag, grid):
    xs, ws = geom(grid)
    cw = (getattr(grid, "_card_w", 0), getattr(grid, "_card_h", 0))
    print("\n[%s]" % tag)
    print("  body=%dx%d  列数=%s  卡片基尺寸=%s  卡片数=%d"
          % (grid._body.width(), grid._body.height(), getattr(grid, "_cols_now", None),
             cw, len(getattr(grid, "_cards", {}) or {})))
    if xs:
        g0 = ws[xs[0]]
        print("  首个 x=%d  卡=%dx%d  末列右=%d  左留白=%d  右留白=%d  列间距≈%d"
              % (xs[0], g0[0], g0[1], xs[-1] + g0[0], xs[0],
                 grid._body.width() - (xs[-1] + g0[0]),
                 (xs[1] - xs[0] - g0[0]) if len(xs) > 1 else -1))
    return xs, ws


# ---------- 媒体墙 ----------
wall = win._wall_page(None)
win.stack.addWidget(wall)
win.stack.setCurrentWidget(wall)
settle(35)
wg = wall.findChildren(mw.LazyGrid)[0]
dump("影片墙 1920", wg)

# ---------- 演员库 ----------
page = win._view_actors()
win.stack.addWidget(page)
win.stack.setCurrentWidget(page)
settle(35)
ag = page.findChildren(mw.LazyGrid)[0]
dump("演员库 1920", ag)

# 滚轮打在**卡片**上（真实用户就是光标停在卡片上滚）
sb = ag._scrollbar
print("\n-- 滚轮打在卡片上 10 次 --")
first = ag._cards[min(ag._cards)]
for i in range(10):
    p = QPointF(first.rect().center())
    ev = QWheelEvent(p, first.mapToGlobal(first.rect().center()), QPoint(0, -120),
                     QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
    app.sendEvent(first, ev)
    settle(3)
    if (i + 1) % 5 == 0:
        idx = sorted(ag._cards.keys())
        print("  轮次 %d 滚动=%d 卡片=%d 索引 %s..%s"
              % (i + 1, sb.value(), len(idx), idx[0], idx[-1]))

# 滚轮打在网格空白处
print("\n-- 滚轮打在 grid 空白区 10 次 --")
for i in range(10):
    p = QPointF(ag.rect().center())
    ev = QWheelEvent(p, ag.mapToGlobal(ag.rect().center()), QPoint(0, -120),
                     QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
    app.sendEvent(ag, ev)
    settle(3)
idx = sorted(ag._cards.keys())
print("  滚动=%d 卡片=%d 索引 %s..%s" % (sb.value(), len(idx), idx[0], idx[-1]))

# ---------- 末尾可达性 ----------
for w, h in ((1920, 1080), (1680, 960), (1500, 900)):
    win.resize(w, h)
    settle(8)
    sb.setValue(sb.maximum())
    settle(20)
    idx = sorted(ag._cards.keys())
    print("窗口 %dx%d：列数=%d 滚动=%d/%d 末尾索引=%d（应为 %d）%s"
          % (w, h, ag._cols_now, sb.value(), sb.maximum(), idx[-1] if idx else -1,
             ag._total - 1, "OK" if idx and idx[-1] >= ag._total - 1 - ag._cols_now else "★截断"))

print("\nPROBE_V1466C_DONE")
