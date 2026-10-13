# -*- coding: utf-8 -*-
"""决定性实验：探针 delegate 打印绘制时真实 option.rect / subElementRect / features。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_dlgt_")
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


class ProbeDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        st = option.widget.style()
        # 复刻 QStyledItemDelegate::paint 内部的第一步：initStyleOption
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        has = bool(opt.features & QStyleOptionViewItem.HasCheckIndicator)
        sr = st.subElementRect(QStyle.SE_ItemViewItemCheckIndicator, opt, option.widget)
        print("paint row=%d col=%d rect=(%d,%d %dx%d) init后 hasCheck=%s checkState=%s sr=(%d,%d %dx%d)"
              % (index.row(), index.column(), opt.rect.left(), opt.rect.top(),
                 opt.rect.width(), opt.rect.height(), has, opt.checkState,
                 sr.left(), sr.top(), sr.width(), sr.height()))
        super().paint(painter, option, index)


tree.setItemDelegate(ProbeDelegate())

dlg = QDialog()
lv = QVBoxLayout(dlg)
lv.setContentsMargins(0, 0, 0, 0)
lv.addWidget(page)
dlg.resize(1100, 860)
dlg.show()
app.processEvents(); app.processEvents()

print("--- grab 触发重绘 ---")
img = tree.grab().toImage()
img.save("C:/Users/zouzu/AppData/Local/Temp/ck_dlgt.png")
print("PROBE_DLGT_DONE")
