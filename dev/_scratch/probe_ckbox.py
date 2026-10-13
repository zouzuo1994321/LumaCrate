# -*- coding: utf-8 -*-
"""离屏像素探针 v2：修正视口坐标偏移，并导出 PNG 直接看。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_ck2_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QTreeWidget, QTreeWidgetItem,
                               QAbstractItemView)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import applog
db.db_path = lambda: os.path.join(TMP, "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")
from main_window import load_style
import main_window as mw


def build_tree(checked_first=False):
    t = QTreeWidget()
    t.setHeaderLabels(["选择", "候选", "人数", "匹配度", "判定依据"])
    t.setRootIsDecorated(True)
    t.setUniformRowHeights(True)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setColumnWidth(0, 46)
    t.setColumnWidth(1, 190)
    t.setColumnWidth(2, 44)
    t.setColumnWidth(3, 52)
    top = QTreeWidgetItem(["建议合并（3 簇，共可减少 6 条演员记录）", "", "", "", ""])
    t.addTopLevelItem(top)
    for i in range(3):
        it = QTreeWidgetItem(["", "候选人%d / 名字%d" % (i, i), "3 人", "100 铁证", "罗马音相同"])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(0, Qt.Checked if (checked_first and i == 0) else Qt.Unchecked)
        top.addChild(it)
    top.setExpanded(True)
    t.resize(460, 240)
    return t, top


def grab(t):
    t.show()
    app.processEvents()
    app.processEvents()
    return t.grab().toImage()


def child_row_widget_rect(t, item):
    """子行矩形 → 换算成**控件坐标**（visualItemRect 是视口坐标，要加表头高/边框）。"""
    r = t.visualItemRect(item)
    off = t.viewport().mapTo(t, QPoint(0, 0))
    r.translate(off.x(), off.y())
    return r


def region_colors(img, x0, y0, x1, y1, label=""):
    from collections import Counter
    c = Counter()
    for y in range(max(0, y0), min(img.height(), y1)):
        for x in range(max(0, x0), min(img.width(), x1)):
            p = img.pixel(x, y)
            r, g, b = (p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF
            c[(r // 16 * 16, g // 16 * 16, b // 16 * 16)] += 1
    print("%s top8:" % label, c.most_common(8))
    return c


def img_diff(a, b):
    n = 0
    w, h = min(a.width(), b.width()), min(a.height(), b.height())
    for y in range(h):
        for x in range(w):
            if a.pixel(x, y) != b.pixel(x, y):
                n += 1
    return n


OUT = os.path.join(TMP, "png")
os.makedirs(OUT, exist_ok=True)

# A: 真实 QSS，未勾选
app.setStyleSheet(load_style(app))
tA, topA = build_tree(False)
imgA = grab(tA)
imgA.save(os.path.join(OUT, "A_realqss_unchecked.png"))
rA = child_row_widget_rect(tA, topA.child(0))
print("A 子行控件坐标:", rA, " 表头高:", tA.header().height())
region_colors(imgA, rA.left(), rA.top(), rA.left() + 46, rA.bottom(), "A[未勾选·列0]")

# B: 真实 QSS，首行勾选
tB, topB = build_tree(True)
imgB = grab(tB)
imgB.save(os.path.join(OUT, "B_realqss_checked.png"))
rB = child_row_widget_rect(tB, topB.child(0))
region_colors(imgB, rB.left(), rB.top(), rB.left() + 46, rB.bottom(), "B[已勾选·列0]")

# C: 去掉 QTreeView::indicator 规则
qss = mw.render_style()
lines = [l for l in qss.splitlines() if "QTreeView::indicator" not in l]
app.setStyleSheet("\n".join(lines))
tC, topC = build_tree(False)
imgC = grab(tC)
imgC.save(os.path.join(OUT, "C_norule.png"))
rC = child_row_widget_rect(tC, topC.child(0))
region_colors(imgC, rC.left(), rC.top(), rC.left() + 46, rC.bottom(), "C[无规则·列0]")

print("A vs C 差异像素:", img_diff(imgA, imgC))
print("A vs B 差异像素:", img_diff(imgA, imgB))
print("PNG ->", OUT)
