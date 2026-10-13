# -*- coding: utf-8 -*-
"""决定性实验：QTreeView::indicator 规则进完整 QSS 后，
是整张样式表解析失败（所有控件回落原生），还是只有树受影响。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_dec_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QTreeWidget, QTreeWidgetItem,
                               QPushButton, QLineEdit, QWidget, QVBoxLayout)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import applog
db.db_path = lambda: os.path.join(TMP, "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")
import main_window as mw

FULL = mw.render_style()
NOIND = "\n".join(l for l in FULL.splitlines() if "QTreeView::indicator" not in l)


def probe(qss, tag):
    app.setStyleSheet(qss)
    host = QWidget()
    v = QVBoxLayout(host)
    t = QTreeWidget()
    t.setHeaderLabels(["选择", "候选"])
    t.setColumnWidth(0, 46)
    t.setColumnWidth(1, 160)
    top = QTreeWidgetItem(["建议合并（3 簇）", ""])
    t.addTopLevelItem(top)
    for i in range(3):
        it = QTreeWidgetItem(["", "候选人%d" % i])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(0, Qt.Unchecked)
        top.addChild(it)
    top.setExpanded(True)
    btn = QPushButton("主按钮")
    btn.setObjectName("Primary")
    edit = QLineEdit()
    v.addWidget(t); v.addWidget(btn); v.addWidget(edit)
    host.resize(360, 420)
    host.show()
    app.processEvents(); app.processEvents()

    def px(w, x, y):
        img = w.grab().toImage()
        p = img.pixel(x, y)
        return ((p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF)

    print("[%s]" % tag)
    print("  树空白处底色:", px(t, 300, 300))
    print("  主按钮底色:  ", px(btn, 20, 12))
    print("  输入框底色:  ", px(edit, 20, 12))


probe(FULL, "完整 QSS + QTreeView::indicator（现行）")
probe(NOIND, "完整 QSS - QTreeView::indicator 三行")
