# -*- coding: utf-8 -*-
"""v1.39.0 需求 2 验收：复选框可见 + ExtendedSelection + 勾选∪选中计数。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_v_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QAbstractItemView
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
it0, it1 = items[0], items[1]
tree = page.tree

dlg = QDialog()
lv = QVBoxLayout(dlg)
lv.setContentsMargins(0, 0, 0, 0)
lv.addWidget(page)
dlg.resize(1100, 860)
dlg.show()
app.processEvents(); app.processEvents()

ok = True

# 1. 模式与列宽
mode = tree.selectionMode()
print("selectionMode =", mode.value, "(ExtendedSelection=%d)" % QAbstractItemView.SelectionMode.ExtendedSelection.value)
ok &= (mode == QAbstractItemView.SelectionMode.ExtendedSelection)
print("columnWidth(0) =", tree.columnWidth(0))
ok &= (tree.columnWidth(0) == 62)

# 2. 复选框可见面积（Checked diff）
def grab():
    app.processEvents(); app.processEvents()
    return tree.grab().toImage()

def diff_n(img1, img2):
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

imgA = grab()
tree.blockSignals(True)
it0.setCheckState(0, Qt.Checked)
imgB = grab()
it0.setCheckState(0, Qt.Unchecked)
tree.blockSignals(False)
vis = diff_n(imgA, imgB)
print("复选框可见面积 =", vis, "(应 ~279)")
ok &= (vis > 200)

# 3. 勾选 ∪ 选中 计数
tree.blockSignals(True)
it0.setCheckState(0, Qt.Checked)
tree.blockSignals(False)
page._refresh_batch_btn()
print("勾选1行 → 按钮:", page.batch_merge_btn.text(), "enabled =", page.batch_merge_btn.isEnabled())
ok &= ("合并 1 簇" in page.batch_merge_btn.text() and page.batch_merge_btn.isEnabled())

# 选中第二行（不勾选）→ 应计 2
tree.blockSignals(True)
it1.setSelected(True)
tree.blockSignals(False)
page._refresh_batch_btn()
print("再选中1行 → 按钮:", page.batch_merge_btn.text())
ok &= ("合并 2 簇" in page.batch_merge_btn.text())

# _merge_checked 的 picked 口径（弹框前拦截，只验证集合构造）
src_picked = []
for i in range(tree.topLevelItemCount()):
    top = tree.topLevelItem(i)
    for j in range(top.childCount()):
        it = top.child(j)
        if it.data(0, page.ROLE_KIND) == "cluster" \
                and (it.checkState(0) == Qt.Checked or it.isSelected()) \
                and it.text(3) not in ("已合并", "已忽略"):
            src_picked.append(int(it.data(0, page.ROLE_INDEX)))
print("picked 集合 =", src_picked, "(应 [0, 1])")
ok &= (src_picked == [0, 1])

print("ALL_OK" if ok else "FAILED")
print("PROBE_VERIFY_DONE")
