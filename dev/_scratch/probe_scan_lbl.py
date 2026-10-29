# -*- coding: utf-8 -*-
"""v1.46.13：真 MainWindow 里 `_scan_library_cat` 之后，底部 ScanNote 到底有没有
文字、有没有被挤成 0 宽。离屏跑，不碰真实索引。
"""
import os
import sys
import time
import json
import shutil

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSPLASH"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"

TMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                   "lmc_probe_scanlbl")
os.makedirs(TMP, exist_ok=True)

import database as db
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
import applog
applog.log_dir = lambda: os.path.join(TMP, "index_data", "logs")

CFG = os.path.join(TMP, "settings.json")
if os.path.exists(CFG):
    os.remove(CFG) if False else None
with open(CFG, "w", encoding="utf-8") as f:
    json.dump({"libraries": []}, f)
os.environ["LMC_CONFIG"] = CFG

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEventLoop, QTimer

import main_window as mw
import config as cfg

app = QApplication([])
mw.load_style(app)

# 造目录
paths = []
for pi in range(3):
    p = os.path.join(TMP, "lib", "p%d" % (pi + 1))
    for i in range(40):
        d = os.path.join(p, "F%d_%02d" % (pi + 1, i))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0"?><movie><title>演示%d-%02d</title><year>2021</year></movie>'
                    % (pi + 1, i))
        with open(os.path.join(d, "%d_%02d.mp4" % (pi + 1, i)), "wb") as f:
            f.write(b"\0" * 512)
    paths.append(p)

s = cfg.get_settings()
s.add_library("演示库", "电影", paths)
db.init_db()
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
app.processEvents()

lib = cfg.get_settings().library("演示库")
print("library:", lib["name"], lib["paths"])

win._scan_library_cat(lib, "new")

lbl = win._scan_lbl
sb = win.statusBar()
print("statusbar h:", sb.height(), "children:", [(c.objectName(), c.width()) for c in sb.children()
                                                 if hasattr(c, "width")][:8])
print("lbl after begin: text=%r visible=%s w=%d h=%d geo=%s" % (
    lbl.text(), lbl.isVisible(), lbl.width(), lbl.height(), lbl.geometry()))
print("scan_busy_owned:", getattr(win, "_scan_busy_owned", None))

t0 = time.time()
while time.time() - t0 < 6.0:
    app.processEvents(QEventLoop.AllEvents, 50)
    time.sleep(0.05)

print("lbl mid: text=%r visible=%s w=%d  tip=%r" % (
    lbl.text(), lbl.isVisible(), lbl.width(), lbl.toolTip()))
print("ring text:", win._lib_rings["演示库"].isVisible() if "演示库" in win._lib_rings else "n/a")
print("media count:", db.count_media())
print("PROBE_DONE")
