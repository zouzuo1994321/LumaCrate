# -*- coding: utf-8 -*-
"""v2.0.5（反馈 1）出图：底部状态栏的扫描文案 —— 分母是「本条路径」的片数。

上排：正在统计本条路径（不定长）
中排：本条路径扫描中（1203/8000 + 新增/变更/减少）
下排：本条路径扫完、准备下一条
"""
import os
import sys
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = r"C:/Users/zouzu/AppData/Local/Temp/v206bar"
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)

import database as db          # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: os.path.join(TMP, "probe.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")
db.init_db()

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QStyleFactory,
                               QStatusBar, QLabel, QProgressBar)
from PySide6.QtGui import QImage, QPainter, QColor, QFontDatabase
from PySide6.QtCore import Qt

OUT = os.path.join(ROOT, "docs", "preview")
app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setStyle(QStyleFactory.create("Fusion"))

import main_window as mw      # noqa: E402
mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

ROOT_DIR = r"D:/jav/[01] Jav精选-10"


def make_worker(done, total, new, changed, gone):
    w = mw.ScanWorker([ROOT_DIR], library_name="Javlibrary")
    w._i_path, w._n_paths = 5, 14
    w._root = ROOT_DIR
    w._path_done, w._path_total = done, total
    w._new, w._changed, w._gone = new, changed, gone
    return w


CASES = [
    ("统计本条路径（不定长）", None, 0, 0),
    ("扫描中（本条 + 累计增减）", make_worker(1203, 8000, 94, 12, 3), -1, 1),
    ("本条扫完", make_worker(8000, 8000, 94, 12, 3), 100, 1),
]

host = QWidget()
host.setObjectName("Host")
host.setStyleSheet("QWidget#Host{background:#0a0a0b;}")
host.setAttribute(Qt.WA_StyledBackground, True)
v = QVBoxLayout(host)
v.setContentsMargins(0, 12, 0, 12)
v.setSpacing(14)

for tag, wk, pct, bar_mode in CASES:
    sb = QStatusBar()
    copy = QLabel("© 2026 肆月Aperture")
    copy.setObjectName("FooterNote")
    sb.addWidget(copy)
    lbl = QLabel("")
    lbl.setObjectName("ScanNote")
    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    sb.addPermanentWidget(lbl, 0)
    bar = QProgressBar()
    bar.setObjectName("BusyBar")
    bar.setTextVisible(False)
    bar.setFixedSize(110, 6)
    if wk is None:
        lbl.setText("正在统计路径 5/14 的文件数… 已找到 3200 个")
        bar.setRange(0, 0)                      # 不定长 → 循环块
    else:
        lbl.setText(wk._msg())
        bar.setRange(0, 100)
        bar.setValue(pct if pct >= 0 else int(100 * wk._path_done / wk._path_total))
    bar.setProperty("busy", bar_mode == 1)
    print("%-14s | %s" % (tag, lbl.text()))
    v.addWidget(sb)

host.resize(1180, 3 * 34 + 2 * 14 + 24)
host.show()
app.processEvents()
for _ in range(4):
    app.processEvents()
pm = host.grab()
im = pm.toImage().convertToFormat(QImage.Format_ARGB32)
canvas = QImage(im.width(), im.height(), QImage.Format_ARGB32)
canvas.fill(QColor("#0a0a0b"))
p = QPainter(canvas)
p.drawImage(0, 0, im)
p.end()
canvas.save(os.path.join(OUT, "v206_scan_bar.png"))
print("saved v206_scan_bar.png", canvas.width(), "x", canvas.height())
print("DONE")
