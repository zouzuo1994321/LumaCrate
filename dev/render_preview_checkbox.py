# -*- coding: utf-8 -*-
"""未勾选 / 已勾选 两态并排出图，肉眼确认复选框与对勾都画出来了。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_prev_cb_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem
from PySide6.QtGui import QFontDatabase, QImage, QPainter, QColor
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import applog

db.db_path = lambda: os.path.join(TMP, "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")
from main_window import load_style

load_style(app)

BG = QColor("#0e0c0a")
NAMES = ["よしい美希 / よし美希", "川上Gallery / 加藤ツバキ", "坂田蒼乃美",
         "滝村レイコ / 滝村レイコ", "星藤", "あいり / 朱雀あいみ"]


def make(checked):
    t = QTreeWidget()
    t.setColumnCount(5)
    t.setHeaderLabels(["选择", "候选", "人数", "匹配度", "判定依据"])
    t.setColumnWidth(0, 62)
    t.setColumnWidth(1, 240)
    t.setColumnWidth(2, 44)
    t.setColumnWidth(3, 52)
    root = QTreeWidgetItem(["", "", "", "", ""])
    t.addTopLevelItem(root)
    for i, n in enumerate(NAMES):
        it = QTreeWidgetItem(["", n, "2 人", "94 标注", "姓名去括号后缀后完全一致"])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(0, Qt.Checked if (checked and i % 2 == 0) else Qt.Unchecked)
        root.addChild(it)
    root.setExpanded(True)
    t.resize(700, 230)
    t.show()
    for _ in range(8):
        app.processEvents()
    return t


def save(t, name):
    img = t.grab().toImage()
    out = QImage(img.size(), QImage.Format_RGB32)
    out.fill(BG)
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    outp = os.path.join(ROOT, "dev", "screenshots", name)
    out.save(outp)
    print("[出图]", name, img.width(), "x", img.height())
    t.close()
    return outp


save(make(False), "v1391_cb_unchecked.png")
save(make(True), "v1391_cb_checked.png")
print("PREVIEW_CB_DONE")
