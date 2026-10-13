# -*- coding: utf-8 -*-
"""隔离实验：到底哪种 indicator 写法会把 QTreeWidget 的背景打白。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_iso_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QTreeWidget, QTreeWidgetItem,
                               QAbstractItemView)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)


def build_tree():
    t = QTreeWidget()
    t.setHeaderLabels(["选择", "候选"])
    t.setColumnWidth(0, 46)
    t.setColumnWidth(1, 190)
    top = QTreeWidgetItem(["建议合并（3 簇）", ""])
    t.addTopLevelItem(top)
    for i in range(3):
        it = QTreeWidgetItem(["", "候选人%d" % i])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(0, Qt.Unchecked)
        top.addChild(it)
    top.setExpanded(True)
    t.resize(300, 200)
    return t, top


TESTS = [
    ("T1 仅 QTreeWidget 背景",
     "QTreeWidget { background: #202020; color: #dddddd; }"),
    ("T2 + QTreeView::indicator（v1.38.0 现行）",
     "QTreeWidget { background: #202020; color: #dddddd; } "
     "QTreeView::indicator { width:15px; height:15px; border:1px solid rgba(255,255,255,0.22); background: rgba(255,255,255,0.05); }"),
    ("T3 + QTreeWidget::indicator",
     "QTreeWidget { background: #202020; color: #dddddd; } "
     "QTreeWidget::indicator { width:15px; height:15px; border:1px solid rgba(255,255,255,0.22); background: rgba(255,255,255,0.05); }"),
    ("T4 仅 QTreeView::indicator",
     "QTreeView::indicator { width:15px; height:15px; }"),
    ("T5 QTreeView 背景 + QTreeView::indicator",
     "QTreeView { background: #202020; color: #dddddd; } "
     "QTreeView::indicator { width:15px; height:15px; }"),
    ("T6 QTreeWidget 背景 + ::branch 也限定 QTreeWidget",
     "QTreeWidget { background: #202020; color: #dddddd; } "
     "QTreeWidget::indicator { width:15px; height:15px; } "
     "QTreeWidget::branch { background: transparent; }"),
]


def px(img, x, y):
    p = img.pixel(x, y)
    return ((p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF)


for name, qss in TESTS:
    app.setStyleSheet(qss)
    t, top = build_tree()
    t.show()
    app.processEvents(); app.processEvents()
    img = t.grab().toImage()
    # 空白处（行下方）取背景色；子行列0 区域扫一遍找非背景像素
    bg = px(img, 250, 150)
    r = t.visualItemRect(top.child(0))
    from PySide6.QtCore import QPoint
    off = t.viewport().mapTo(t, QPoint(0, 0))
    rx, ry = r.left() + off.x(), r.top() + off.y()
    found = []
    for y in range(ry, ry + r.height()):
        for x in range(rx, min(rx + 46, img.width())):
            c = px(img, x, y)
            if c != bg and sum(c) < 600:      # 与背景不同且非白
                found.append((x - rx, y - ry, c))
    print("%-42s 背景=%s  列0非背景像素数=%d  样例=%s"
          % (name, bg, len(found), found[:3]))
