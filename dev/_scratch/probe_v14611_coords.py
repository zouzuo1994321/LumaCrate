# -*- coding: utf-8 -*-
"""v1.46.11：右键坐标口径验证 —— customContextMenuRequested 给的 pos 到底是
表格坐标还是 viewport 坐标？（表头有 ~30px 偏移，弄错就点到隔壁行，而且是**静默**的）"""
import os
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/probe_v14611b"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QContextMenuEvent, QFontDatabase
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import applog
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import database as db
DB = os.path.join(TMP, "index_data", "p.db")
os.makedirs(os.path.join(TMP, "index_data"), exist_ok=True)
if os.path.exists(DB):
    DB = os.path.join(TMP, "index_data", "p_%d.db" % time.time())
db.db_path = lambda: DB
db.init_db()

import main_window as mw
import ui_home

mw.load_style(app, cfg.DEFAULT_APPEARANCE)

for i in range(6):
    db.upsert_media_by_path(mode="overwrite", kind="movie", title="ROW-%02d" % i,
                            year=2026, file_path=os.path.join(TMP, "%02d.mp4" % i),
                            library="演示库")

GOT = []
lv = ui_home.HomeListView()
lv.table.customContextMenuRequested.disconnect()
lv.table.customContextMenuRequested.connect(lambda p: GOT.append((p.x(), p.y())))
lv.resize(1000, 700)
lv.show()
for _ in range(60):
    app.processEvents()
    time.sleep(0.01)

print("rowCount=%d viewport.pos=%s header.height=%d" %
      (lv.table.rowCount(), lv.table.viewport().pos(), lv.table.horizontalHeader().height()),
      flush=True)

# 取第 3 行在 viewport 里的中心
rect = lv.table.visualItemRect(lv.table.item(3, 0))
vp_pt = rect.center()
print("目标：第 3 行 viewport 坐标 =", (vp_pt.x(), vp_pt.y()), flush=True)

# 真的把「右键事件」送到 viewport（跟用户按键走同一条路）
ev = QContextMenuEvent(QContextMenuEvent.Mouse, vp_pt,
                       lv.table.viewport().mapToGlobal(vp_pt))
QApplication.sendEvent(lv.table.viewport(), ev)
for _ in range(10):
    app.processEvents()

if not GOT:
    print("[FAIL] 信号没发出来（viewport 上的右键事件不会转成 customContextMenu）", flush=True)
else:
    pos = QPoint(*GOT[-1])
    by_vp = lv.table.indexAt(pos).row()
    by_tbl = lv.table.indexAt(lv.table.viewport().mapFrom(lv.table, pos)).row()
    print("收到 pos =", GOT[-1], flush=True)
    print("  当成 viewport 坐标 indexAt → 行", by_vp, flush=True)
    print("  先 mapFrom(table) 再 indexAt → 行", by_tbl, flush=True)
    print("结论：", "pos 是 viewport 坐标" if by_vp == 3 else
          ("pos 是表格坐标" if by_tbl == 3 else "两种都不对"), flush=True)

print("PROBE2_DONE", flush=True)
