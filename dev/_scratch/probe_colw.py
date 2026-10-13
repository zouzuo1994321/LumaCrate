# -*- coding: utf-8 -*-
"""修复验证：列 0 宽 46→62，indicator 是否完整落进列内。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_colw_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QStyledItemDelegate,
                               QStyle, QStyleOptionViewItem)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

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

def grab():
    app.processEvents(); app.processEvents()
    return tree.grab().toImage()

def diff_bbox(img1, img2):
    n = 0
    x1, y1, x2, y2 = None, None, None, None
    for y in range(min(img1.height(), img2.height())):
        for x in range(min(img1.width(), img2.width())):
            p1, p2 = img1.pixel(x, y), img2.pixel(x, y)
            d = max(abs((p1 >> 16 & 0xFF) - (p2 >> 16 & 0xFF)),
                    abs((p1 >> 8 & 0xFF) - (p2 >> 8 & 0xFF)),
                    abs((p1 & 0xFF) - (p2 & 0xFF)))
            if d > 10:
                n += 1
                if x1 is None:
                    x1, y1, x2, y2 = x, y, x, y
                else:
                    x1, y1 = min(x1, x), min(y1, y)
                    x2, y2 = max(x2, x), max(y2, y)
    return n, (x1, y1, x2, y2)

def measure(tag):
    img0 = grab()
    tree.blockSignals(True)
    it0.setCheckState(0, Qt.Checked)
    img1 = grab()
    it0.setCheckState(0, Qt.Unchecked)
    tree.blockSignals(False)
    n, bb = diff_bbox(img0, img1)
    print("[%-14s] Checked可见面积=%4d bbox=%s" % (tag, n, bb))
    return img1

measure("列宽46(现状)")
tree.setColumnWidth(0, 62)
img = measure("列宽62")
tree.setColumnWidth(0, 60)
img2 = measure("列宽60")
img.save("C:/Users/zouzu/AppData/Local/Temp/ck_col62.png")
print("PROBE_COLW_DONE")
