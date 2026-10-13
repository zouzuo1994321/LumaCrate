# -*- coding: utf-8 -*-
"""定位 indicator y=18 超出 17px 行高的成因 + 验证候选修法。

1. 阳性对照：Unchecked → Checked（必须 diff>0，否则 grab 差分法本身失效）
2. 阴性复证：去掉 checkable flag（已知 diff=0）
3. rect 高度扫描：opt.rect 高 17/20/22/24/30 → sr.y 怎么变
4. 修法 A：item setSizeHint(0, 26) 加大行高 → sr.y + grab diff
5. 修法 B：QSS indicator 加 subcontrol-position: left top → sr + grab diff
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_rect_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout,
                               QStyleOptionViewItem, QStyle, QTreeWidget)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint, QRect, QSize

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
print("item rect（视口坐标）: %dx%d, top=%d" % (r.width(), r.height(), r.top()))

def sr_of(rect_h):
    opt = QStyleOptionViewItem()
    opt.features |= QStyleOptionViewItem.HasCheckIndicator
    opt.checkState = Qt.Unchecked
    opt.rect = QRect(r.left(), r.top(), r.width(), rect_h)
    s = tree.style().subElementRect(QStyle.SE_ItemViewItemCheckIndicator, opt, tree)
    return s.left(), s.top(), s.width(), s.height()

print("-- rect 高度扫描（x,y,w,h 相对 rect 左上）--")
for h in (17, 18, 20, 22, 24, 26, 30, 40):
    print("  h=%2d -> (%d, %d) %dx%d" % (h, *sr_of(h)))

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

# ---- 1. 阳性对照：Checked ----
imgA = grab()
tree.blockSignals(True)
it0.setCheckState(0, Qt.Checked)
imgD = grab()
it0.setCheckState(0, Qt.Unchecked)
tree.blockSignals(False)
print("阳性对照 Unchecked->Checked diff =", diff(imgA, imgD))

# ---- 4. 修法 A：setSizeHint 加大行高 ----
it0.setSizeHint(0, QSize(0, 26))
app.processEvents(); app.processEvents()
r2 = tree.visualItemRect(it0)
print("setSizeHint(26) 后 item rect: %dx%d" % (r2.width(), r2.height()))
print("  sr = (%d, %d) %dx%d" % sr_of(r2.height()))
imgE = grab()
print("diff(imgA, imgE) =", diff(imgA, imgE))
it0.setSizeHint(0, QSize())

# ---- 5. 修法 B：QSS indicator 强制 subcontrol-position ----
cur = app.styleSheet()
for _tag, _extra in (("left top", "subcontrol-position: left top;"),
                     ("left center", "subcontrol-position: left center;"),
                     ("top center", "subcontrol-position: top center;")):
    app.setStyleSheet(cur + "\nQTreeView::indicator { %s subcontrol-origin: padding; }\n" % _extra)
    app.processEvents(); app.processEvents()
    print("QSS subcontrol-position:%-12s -> sr = (%d, %d) %dx%d" % ((_tag,) + sr_of(r.height())))
    imgF = grab()
    print("   diff(imgA, imgF) =", diff(imgA, imgF))
app.setStyleSheet(cur)
print("PROBE_RECT_DONE")
