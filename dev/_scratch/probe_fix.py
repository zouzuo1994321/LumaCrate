# -*- coding: utf-8 -*-
"""修法验证：负 margin / top 能否把 indicator 拉回行内；Unicode 符号兜底。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_fix_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout,
                               QStyleOptionViewItem, QStyle)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint, QRect

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
tree = page.tree

dlg = QDialog()
lv = QVBoxLayout(dlg)
lv.setContentsMargins(0, 0, 0, 0)
lv.addWidget(page)
dlg.resize(1100, 860)
dlg.show()
app.processEvents(); app.processEvents()

r = tree.visualItemRect(it0)
off = tree.viewport().mapTo(tree, QPoint(0, 0))

def sr_of():
    opt = QStyleOptionViewItem()
    opt.features |= QStyleOptionViewItem.HasCheckIndicator
    opt.checkState = Qt.Unchecked
    opt.rect = r
    s = tree.style().subElementRect(QStyle.SE_ItemViewItemCheckIndicator, opt, tree)
    return s.left(), s.top(), s.width(), s.height()

def grab():
    app.processEvents(); app.processEvents()
    return tree.grab().toImage()

def diff(img1, img2):
    n = 0
    for y in range(min(img1.height(), img2.height())):
        for x in range(min(img1.width(), img2.width())):
            p1, p2 = img1.pixel(x, y), img2.pixel(x, y)
            d = max(abs((p1 >> 16 & 0xFF) - (p2 >> 16 & 0xFF)),
                    abs((p1 >> 8 & 0xFF) - (p2 >> 8 & 0xFF)),
                    abs((p1 & 0xFF) - (p2 & 0xFF)))
            if d > 10:
                n += 1
    return n

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

base = app.styleSheet()
imgA = grab()
print("基线 sr = (%d, %d) %dx%d" % sr_of())

# 候选 indicator 应出现的区域：x=43..60（相对 item rect），y=0..17
IX, IY = r.left() + 43 + off.x(), r.top() + 0 + off.y()
print("indicator 期望位置（控件坐标）: x=%d..%d y=%d..%d"
      % (IX, IX + 17, IY, IY + 17))

def try_qss(tag, extra):
    app.setStyleSheet(base + "\nQTreeView::indicator { %s }\n" % extra)
    app.processEvents(); app.processEvents()
    sr = sr_of()
    img = grab()
    d = diff(imgA, img)
    print("[%s] sr=(%d,%d) %dx%d  diff=%d" % ((tag,) + sr + (d,)))
    return img

for tag, extra in (
    ("margin-top:-18", "margin-top: -18px;"),
    ("top:-18", "top: -18px;"),
    ("margin:-18 0 0 0", "margin: -18px 0 0 0;"),
    ("pos:left top+mt", "subcontrol-position: left top; margin-top: -18px;"),
):
    try_qss(tag, extra)

# 兜底：Unicode 符号 ☑ 的可见性（QSS 不动）
app.setStyleSheet(base)
app.processEvents(); app.processEvents()
tree.blockSignals(True)
it0.setText(0, "\u2611")
imgU = grab()
tree.blockSignals(False)
d = diff(imgA, imgU)
print("[Unicode ☑] diff=%d" % d)
if d:
    ascii_region(imgU, IX - 2, IY - 2, 40, 24, "☑ 符号渲染")
print("PROBE_FIX_DONE")
