# -*- coding: utf-8 -*-
"""差分探针：完整 QSS 下，复选框指示器到底渲不渲染、在哪、被谁压制。

判据（干净，排除候选列文字污染）：
  1. diff_flag：同一棵树，去掉 ItemIsUserCheckable 前后 grab 差分
     → 差集 = 指示器本体（若文字也移位会一并现形，可区分）
  2. subElementRect(SE_ItemViewItemCheckIndicator) → QSS 下指示器的真实几何
  3. diff_qss：完整 QSS vs T2 迷你 QSS（QTreeWidget背景 + QTreeView::indicator）
     → 差集 = 完整 QSS 里多出来的规则对指示器的影响
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_diff_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout,
                               QStyleOptionViewItem, QStyle)
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
import ui_actorcheck as ack_page
from main_window import load_style

load_style(app)

page = ack_page.ActorCheckPage()
page._res = {"merge_people": 2}
page._suspects = []
page._clusters = [
    {"ids": [10, 20], "keep_id": 10, "score": 90, "tier": "铁证",
     "reasons": ["罗马音一致"], "total_works": 6,
     "members": [{"id": 10, "name": "明里つくし", "works": 5, "photo": ""},
                 {"id": 20, "name": "つくし明里", "works": 1, "photo": ""}]},
    {"ids": [11, 21], "keep_id": 11, "score": 85, "tier": "很高",
     "reasons": ["别名互指"], "total_works": 3,
     "members": [{"id": 11, "name": "佐藤さん", "works": 2, "photo": ""},
                 {"id": 21, "name": "サトウ", "works": 1, "photo": ""}]},
]
page._fill_tree()

items = []
for i in range(page.tree.topLevelItemCount()):
    top = page.tree.topLevelItem(i)
    for j in range(top.childCount()):
        it = top.child(j)
        if it.data(0, page.ROLE_KIND) == "cluster":
            items.append(it)
it0 = items[0]
print("簇行 flags & ItemIsUserCheckable =", bool(it0.flags() & Qt.ItemIsUserCheckable),
      "| checkState =", it0.checkState(0))

dlg = QDialog()
lv = QVBoxLayout(dlg)
lv.setContentsMargins(0, 0, 0, 0)
lv.addWidget(page)
dlg.resize(1100, 860)
dlg.show()
app.processEvents(); app.processEvents()

tree = page.tree
r = tree.visualItemRect(it0)
off = tree.viewport().mapTo(tree, QPoint(0, 0))
rx, ry = r.left() + off.x(), r.top() + off.y()
print("簇行控件坐标: (%d,%d) %dx%d" % (rx, ry, r.width(), r.height()))

# ---- 2. subElementRect：QSS 下指示器的真实几何 ----
opt = QStyleOptionViewItem()
opt.features |= QStyleOptionViewItem.HasCheckIndicator
opt.checkState = Qt.Unchecked
opt.rect = r
sr = tree.style().subElementRect(QStyle.SE_ItemViewItemCheckIndicator, opt, tree)
print("subElementRect(indicator) = (%d,%d) %dx%d  (相对 item rect)"
      % (sr.left(), sr.top(), sr.width(), sr.height()))

def grab():
    app.processEvents(); app.processEvents()
    return tree.grab().toImage()

def diff(img1, img2, x0, y0, w, h, thresh=10):
    """返回 (显著像素数, bbox)"""
    n = 0
    x1, y1, x2, y2 = None, None, None, None
    for y in range(y0, min(y0 + h, img1.height())):
        for x in range(x0, min(x0 + w, img1.width())):
            if x >= img2.width() or y >= img2.height():
                continue
            p1, p2 = img1.pixel(x, y), img2.pixel(x, y)
            d = max(abs((p1 >> 16 & 0xFF) - (p2 >> 16 & 0xFF)),
                    abs((p1 >> 8 & 0xFF) - (p2 >> 8 & 0xFF)),
                    abs((p1 & 0xFF) - (p2 & 0xFF)))
            if d > thresh:
                n += 1
                if x1 is None:
                    x1, y1, x2, y2 = x, y, x, y
                else:
                    x1, y1 = min(x1, x), min(y1, y)
                    x2, y2 = max(x2, x), max(y2, y)
    return n, (x1, y1, x2, y2)

def ascii_region(img, x0, y0, w, h, title):
    print("== %s ==" % title)
    for y in range(y0, y0 + h):
        line = ""
        for x in range(x0, x0 + w):
            if x >= img.width() or y >= img.height():
                line += "?"
                continue
            p = img.pixel(x, y)
            lum = ((p >> 16 & 0xFF) + (p >> 8 & 0xFF) + (p & 0xFF)) // 3
            line += " " if lum < 40 else ("." if lum < 90 else ("+" if lum < 160 else ("*" if lum < 220 else "#")))
        print(line)

W, H = 100, r.height() + 4

# ---- 1. diff_flag：去掉 checkable flag 前后差分 ----
imgA = grab()
tree.blockSignals(True)
it0.setFlags(it0.flags() & ~Qt.ItemIsUserCheckable)
imgB = grab()
it0.setFlags(it0.flags() | Qt.ItemIsUserCheckable)
tree.blockSignals(False)
n, bb = diff(imgA, imgB, rx - 2, ry - 2, W, H)
print("diff_flag: 显著像素=%d bbox=%s" % (n, bb))
if n:
    ascii_region(imgA, rx - 2, ry - 2, W, H, "imgA（完整QSS·可勾选）行列0")
    ascii_region(imgB, rx - 2, ry - 2, W, H, "imgB（完整QSS·不可勾选）行列0")

# ---- 3. diff_qss：完整 QSS vs T2 迷你 QSS ----
T2 = ("QTreeWidget { background: #12100c; color: #ece5d8; }\n"
      "QTreeView::indicator { width:15px; height:15px; border-radius:4px; "
      "border:1px solid rgba(255,255,255,0.22); background:rgba(255,255,255,0.05); }\n")
app.setStyleSheet(T2)
app.processEvents(); app.processEvents()
imgC = grab()
n2, bb2 = diff(imgA, imgC, rx - 2, ry - 2, W, H)
print("diff_qss(完整 vs T2): 显著像素=%d bbox=%s" % (n2, bb2))
if n2:
    ascii_region(imgC, rx - 2, ry - 2, W, H, "imgC（T2迷你QSS）行列0")

# T2 下再查 subElementRect
sr2 = tree.style().subElementRect(QStyle.SE_ItemViewItemCheckIndicator, opt, tree)
print("T2 下 subElementRect(indicator) = (%d,%d) %dx%d"
      % (sr2.left(), sr2.top(), sr2.width(), sr2.height()))
print("PROBE_DIFF_DONE")
