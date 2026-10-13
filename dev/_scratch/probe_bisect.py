# -*- coding: utf-8 -*-
"""规则块剔除矩阵：完整 QSS 里到底哪条规则让树复选框指示器不渲染。"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_bisect_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem, QDialog, QVBoxLayout
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint

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

GROUPS = {
    "QTreeView::indicator": "QTreeView::indicator",
    "QListWidget::indicator": "QListWidget::indicator",
    "QListWidget::item": "QListWidget::item",
    "QHeaderView::section": "QHeaderView::section",
    "通用选择器 *": "\n* {",
    "QWidget,QDialog 透明底": "QWidget, QDialog {",
    "QListWidget,QTreeWidget": "QListWidget, QTreeWidget {",
    "QTableWidget,QTableView": "QTableWidget, QTableView {",
}


def strip(qss, needle):
    """删掉包含 needle 的连续行（规则块常跨行，连带的后续行到 } 为止）。"""
    out, skip = [], False
    for line in qss.splitlines():
        if needle in line:
            skip = True
        if skip and "}" in line:
            skip = False
            continue
        if not skip:
            out.append(line)
    return "\n".join(out)


def measure(qss):
    """在对话框里建树（贴近真实 App），返回列0非背景像素数与树底色。"""
    app.setStyleSheet(qss)
    dlg = QDialog()
    lv = QVBoxLayout(dlg); lv.setContentsMargins(0, 0, 0, 0)
    t = QTreeWidget()
    t.setHeaderLabels(["选择", "候选"])
    t.setColumnWidth(0, 46); t.setColumnWidth(1, 160)
    top = QTreeWidgetItem(["建议合并（3 簇）", ""])
    t.addTopLevelItem(top)
    for i in range(3):
        it = QTreeWidgetItem(["", "候选人%d" % i])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(0, Qt.Unchecked)
        top.addChild(it)
    top.setExpanded(True)
    lv.addWidget(t)
    dlg.resize(420, 300)
    dlg.show()
    app.processEvents(); app.processEvents()
    img = t.grab().toImage()
    r = t.visualItemRect(top.child(0))
    off = t.viewport().mapTo(t, QPoint(0, 0))
    rx, ry = r.left() + off.x(), r.top() + off.y()

    def px(x, y):
        p = img.pixel(x, y)
        return ((p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF)

    bg = px(min(rx + 200, img.width() - 1), ry + r.height() // 2)   # 行内中后段=行底色
    n = 0
    for y in range(ry, ry + r.height()):
        for x in range(rx, rx + 46):
            if px(x, y) != bg:
                n += 1
    return n, bg


n0, bg0 = measure(FULL)
print("完整 QSS（含全部规则）: 列0非底像素=%d  行底色=%s" % (n0, bg0))
for name, needle in GROUPS.items():
    q = strip(FULL, needle)
    n, bg = measure(q)
    print("去掉 %-24s: 列0非底像素=%-4d 行底色=%s" % (name, n, bg))
