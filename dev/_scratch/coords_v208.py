# -*- coding: utf-8 -*-
"""v2.0.8 真机点击坐标（离屏算好写成 JSON）。

为什么要单独一个进程：真机验收脚本里已经有一个**真实平台**的 QApplication，
在里面再建窗口会真的弹窗、还会和待验收的 exe 抢焦点；离屏算完写 JSON 最干净。

和 `ui_coords.py`（工具窗口那套）同一个套路：`WA_DontShowOnScreen` + `resize(1920,1080)`
+ `show()`（不 show 时 mapTo 全返 0）。读取 `LMC_CONFIG` 指向的**临时**配置，
保证侧栏导航项与首页列宽跟真机这一次运行完全一致。

输出：%TEMP%/lmc_coords_v208.json
  nav        导航按钮文字 -> 窗口内坐标
  header     首页列表表头：每列 漏斗 / 三角 的点击点（列 key 一并给）
  table      表格左上角 + 行高
  main_size  主窗口逻辑尺寸（不是 1920x1080 时 live 脚本会拒绝使用）
"""
import json
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                   "lmc_coords_v208.json")

from PySide6.QtWidgets import QApplication, QPushButton, QWidget   # noqa: E402
from PySide6.QtGui import QFontDatabase                            # noqa: E402
from PySide6.QtCore import Qt, QPoint                              # noqa: E402

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import config as cfg          # noqa: E402
import database as db         # noqa: E402

cfg._SETTINGS = None
print("config:", cfg.config_path(), flush=True)

import main_window as mw      # noqa: E402
import ui_home as uhome       # noqa: E402

mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

res = {}
win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
for _ in range(12):
    app.processEvents()
res["main_size"] = [win.width(), win.height()]

# ---------------- 侧栏导航 ----------------
nav = {}
for b in win.findChildren(QPushButton):
    t = (b.text() or "").strip()
    if t in ("首页", "演员库", "导演库", "全部") and t not in nav:
        p = b.mapTo(win, QPoint(b.width() // 2, b.height() // 2))
        nav[t] = [int(p.x()), int(p.y())]
res["nav"] = nav

# ---------------- 首页列表表头 ----------------
hlv = None
for w in win.findChildren(QWidget):
    if isinstance(w, uhome.HomeListView):
        hlv = w
        break
if hlv is None:
    raise SystemExit("找不到 HomeListView")

hdr = hlv.table.horizontalHeader()
origin = hdr.mapTo(win, QPoint(0, 0))
y_mid = hdr.mapTo(win, QPoint(0, hdr.height() // 2)).y()
cols = []
for i in range(hdr.count()):
    left = hdr.sectionViewportPosition(i)
    w = hdr.sectionSize(i)
    # 与 FilterHeaderView._zones 完全同一套算式：
    #   漏斗中心 = 列左 + PAD(7) + ICON/2(6.5)
    #   三角中心 = 列右 - PAD(7) - ICON/2(6.5) - 1
    fx = origin.x() + left + 7 + 6.5
    tx = origin.x() + left + w - 7 - 6.5 - 1
    cols.append({"logical": i, "key": hlv._col_key(i), "w": int(w),
                 "funnel": [int(fx), int(y_mid)], "tri": [int(tx), int(y_mid)]})
res["header"] = {"x0": int(origin.x()), "y": int(y_mid),
                 "h": int(hdr.height()), "cols": cols}
tp = hlv.table.mapTo(win, QPoint(0, 0))
res["table"] = {"x": int(tp.x()), "y": int(tp.y()),
                "row_h": int(hlv.table.rowHeight(0)),
                "w": int(hlv.table.viewport().width())}
res["cast_cols"] = list(getattr(hlv, "_cols", []))
res["split"] = [int(x) for x in hlv.split.sizes()]

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("COORDS_OK", OUT, flush=True)
print(json.dumps(res, ensure_ascii=False), flush=True)
