# -*- coding: utf-8 -*-
"""真实页面探针：ActorCheckPage + 真实 QSS，复选框指示器到底渲不渲染。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_page_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QDialog
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
print("簇行数:", len(items))
it0 = items[0]
print("flags & ItemIsUserCheckable =", bool(it0.flags() & Qt.ItemIsUserCheckable),
      "| checkState =", it0.checkState(0))

dlg = QDialog()
from PySide6.QtWidgets import QVBoxLayout
lv = QVBoxLayout(dlg)
lv.setContentsMargins(0, 0, 0, 0)
lv.addWidget(page)
dlg.resize(1100, 860)
dlg.show()
app.processEvents(); app.processEvents()

img = page.tree.grab().toImage()
r = page.tree.visualItemRect(it0)
off = page.tree.viewport().mapTo(page.tree, QPoint(0, 0))
rx, ry = r.left() + off.x(), r.top() + off.y()
print("簇行控件坐标: (%d,%d) %dx%d" % (rx, ry, r.width(), r.height()))

print("== 簇行列0 区域 ASCII（x %d..%d）==" % (rx - 2, rx + 90))
for y in range(ry - 1, ry + r.height() + 1):
    line = ""
    for x in range(rx - 2, rx + 90):
        if x >= img.width() or y >= img.height():
            line += "?"
            continue
        p = img.pixel(x, y)
        rr, gg, bb = (p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF
        lum = (rr + gg + bb) // 3
        line += " " if lum < 40 else ("." if lum < 90 else ("+" if lum < 160 else ("*" if lum < 220 else "#")))
    print(line)

# 统计列0 区域颜色
from collections import Counter
c = Counter()
for y in range(ry, ry + r.height()):
    for x in range(rx, rx + 46):
        p = img.pixel(x, y)
        c[((p >> 16) & 0xFF) // 16 * 16, ((p >> 8) & 0xFF) // 16 * 16, (p & 0xFF) // 16 * 16] += 1
print("列0区域颜色 top6:", c.most_common(6))
