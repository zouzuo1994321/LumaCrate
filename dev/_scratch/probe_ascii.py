# -*- coding: utf-8 -*-
"""把 v2 探针里发白的区域按亮度画成 ASCII，看白色区域的形状。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_ascii_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import applog
db.db_path = lambda: os.path.join(TMP, "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")
from main_window import load_style
import main_window as mw


def build_tree():
    t = QTreeWidget()
    t.setHeaderLabels(["选择", "候选", "人数", "匹配度", "判定依据"])
    t.setRootIsDecorated(True)
    t.setUniformRowHeights(True)
    t.setColumnWidth(0, 46)
    t.setColumnWidth(1, 190)
    t.setColumnWidth(2, 44)
    t.setColumnWidth(3, 52)
    top = QTreeWidgetItem(["建议合并（3 簇，共可减少 6 条演员记录）", "", "", "", ""])
    t.addTopLevelItem(top)
    for i in range(3):
        it = QTreeWidgetItem(["", "候选人%d / 名字%d" % (i, i), "3 人", "100 铁证", "罗马音相同"])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(0, Qt.Unchecked)
        top.addChild(it)
    top.setExpanded(True)
    t.resize(460, 240)
    return t, top


def ascii_region(img, x0, y0, x1, y1, label):
    print("== %s (x %d..%d, y %d..%d) ==" % (label, x0, x1, y0, y1))
    for y in range(y0, y1):
        line = ""
        for x in range(x0, x1):
            p = img.pixel(x, y)
            r, g, b = (p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF
            lum = (r + g + b) // 3
            line += " " if lum < 40 else ("." if lum < 90 else ("+" if lum < 160 else ("*" if lum < 220 else "#")))
        print(line)


def widget_rect(t, item):
    r = t.visualItemRect(item)
    off = t.viewport().mapTo(t, QPoint(0, 0))
    r.translate(off.x(), off.y())
    return r


for tag, qss in (("A 完整QSS", load_style(app)),
                 ("C 无指示器规则", "\n".join(
                     l for l in mw.render_style().splitlines()
                     if "QTreeView::indicator" not in l))):
    app.setStyleSheet(qss)
    t, top = build_tree()
    t.show()
    app.processEvents(); app.processEvents()
    img = t.grab().toImage()
    r = widget_rect(t, top.child(0))
    ascii_region(img, r.left() - 2, r.top() - 1, r.left() + 80, r.bottom() + 1,
                 "%s 子行列0" % tag)
    # 空白处（最后一行下面）
    rl = widget_rect(t, top.child(2))
    ascii_region(img, rl.left() - 2, rl.bottom() + 6, rl.left() + 80, rl.bottom() + 22,
                 "%s 行下方空白" % tag)
    print()
