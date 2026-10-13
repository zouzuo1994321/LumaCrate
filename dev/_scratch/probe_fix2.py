# -*- coding: utf-8 -*-
"""干净判据：Checked 态差异面积 = indicator 真实可见面积。
QSS 解析器对 top:-18 让 sr 变了，但绘制未必跟 —— 用 Checked 差异一锤定音。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_fix2_")
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
# indicator 期望区域（控件坐标）：x=84..101, y=58..75
IX = r.left() + 43 + off.x()
IY = r.top() + off.y()

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

def ascii_region(img, x0, y0, w, h, title):
    print("== %s ==" % title)
    for y in range(y0, y0 + h):
        line = ""
        for x in range(x0, x0 + w):
            if x >= img.width() or y >= img.height():
                line += "?"
                continue
            p = img.pixel(x, y)
            rr, gg, bb = (p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF
            if rr > 120 and gg < 120 and bb < 120:
                line += "R"      # 强调色（Checked 填充）
            else:
                lum = (rr + gg + bb) // 3
                line += " " if lum < 40 else ("." if lum < 90 else ("+" if lum < 160 else ("*" if lum < 220 else "#")))
        print(line)

base = app.styleSheet()

def measure(tag, extra=""):
    if extra:
        app.setStyleSheet(base + "\nQTreeView::indicator { %s }\n" % extra)
    else:
        app.setStyleSheet(base)
    app.processEvents(); app.processEvents()
    img0 = grab()
    tree.blockSignals(True)
    it0.setCheckState(0, Qt.Checked)
    img1 = grab()
    it0.setCheckState(0, Qt.Unchecked)
    tree.blockSignals(False)
    n, bb = diff_bbox(img0, img1)
    print("[%-22s] Checked可见面积=%4d bbox=%s" % (tag, n, bb))
    return img1

img_base = measure("基线(行外)")
img_top = measure("top:-18px", "top: -18px;")
img_mt = measure("margin-top:-18px", "margin-top: -18px;")

print()
print("indicator 期望区域控件坐标: x=%d..%d y=%d..%d" % (IX, IX + 17, IY, IY + 17))
ascii_region(img_base, IX - 2, IY - 2, 40, 26, "基线 Checked 态 indicator 区")
ascii_region(img_top, IX - 2, IY - 2, 40, 26, "top:-18px Checked 态 indicator 区")
print("PROBE_FIX2_DONE")
