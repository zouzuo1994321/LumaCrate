# -*- coding: utf-8 -*-
"""v1.46.6 诊断 2：滚轮到底能不能续载 / 末尾索引是否可达（1680 宽，5 列）。

关键怀疑：`_render()` 里 `total_rows`、`r0/r1`、`body` 高度用的是**标称列数**
（actor=6），而卡片实际按**自适应列数**（1680 下是 5）摆放 →
body 高度按 6 列算（990 行）而内容需要 1188 行 → 尾部 ~987 位**永远滚不到**。
"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1466b"
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
win.resize(1680, 960)
win.show()
for _ in range(25):
    app.processEvents()

page = win._view_actors()
win.stack.addWidget(page)
win.stack.setCurrentWidget(page)
for _ in range(30):
    app.processEvents()

grid = page.findChildren(mw.LazyGrid)[0]
sb, vp = grid._scrollbar, grid._viewport
cols = grid._cols_now
total = grid._total
print("列数=%d 总数=%d body_h=%d 行高=%d 滚动max=%d"
      % (cols, total, grid._body.height(), grid._row_h, sb.maximum()))
need_rows = (total + cols - 1) // cols
print("按实际列数需要的行数=%d，需要高度=%d（body 只有 %d）"
      % (need_rows, need_rows * grid._row_h, grid._body.height()))

# ---- 滚轮 ----
print("\n-- 模拟滚轮 40 次 --")
for i in range(40):
    p = QPointF(vp.rect().center())
    ev = QWheelEvent(p, vp.mapToGlobal(vp.rect().center()), QPoint(0, -120),
                     QPoint(0, -120), Qt.NoButton, Qt.NoModifier,
                     Qt.ScrollUpdate, False)
    app.sendEvent(vp, ev)
    for _ in range(3):
        app.processEvents()
    if (i + 1) % 8 == 0:
        idx = sorted((getattr(grid, "_cards", {}) or {}).keys())
        print("  轮次 %2d  滚动=%6d/%6d  卡片=%3d  索引 %s..%s"
              % (i + 1, sb.value(), sb.maximum(), len(idx),
                 idx[0] if idx else "-", idx[-1] if idx else "-"))

# ---- 直接拉到底 ----
sb.setValue(sb.maximum())
for _ in range(20):
    app.processEvents()
idx = sorted((getattr(grid, "_cards", {}) or {}).keys())
print("\n-- 拉到底 --")
print("  滚动=%d/%d  卡片=%d  索引 %s..%s"
      % (sb.value(), sb.maximum(), len(idx), idx[0] if idx else "-", idx[-1] if idx else "-"))
print("  最后一位演员索引应为 %d；%s" % (total - 1,
      "可达 ✓" if idx and idx[-1] >= total - 1 - cols else "★ 不可达（尾部被截断）"))
print("PROBE_V1466B_DONE")
