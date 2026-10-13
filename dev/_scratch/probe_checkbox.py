# -*- coding: utf-8 -*-
"""真机复现：为什么「选择」列的复选框一个都画不出来？

v1.39.0 只把列宽 46→62 并断言「Checked 态可见面积 46→279px」——
那是**离屏 + 已勾选**两项条件下测的。真机（打包 exe、真实字体）**未勾选态
一格都没画**，用户的原始反馈根本没被修掉。

本探针逐项排除，找出真正原因：
  A. QSS `QTreeView::indicator` 给了 width/height 但**未勾选态没有 image**
     → Qt 走 QSS 分支，无 image 可画 → 画空。
  B. 列宽仍不够（subElementRect 超出列边界被裁）。
  C. QSS 根本没命中（该走默认绘制分支）。
判据：把同一棵树分别用「有 QSS / 无 QSS」「勾选 / 未勾选」渲染，
逐像素数「选择」列里与背景不同的像素数。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_cb_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QTreeWidget, QTreeWidgetItem,
                               QStyledItemDelegate, QStyleOptionViewItem,
                               QStyle)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import applog

db.db_path = lambda: os.path.join(TMP, "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

from main_window import load_style

load_style(app)          # 装上真实 style.qss（含 QTreeView::indicator）


def build(width):
    tree = QTreeWidget()
    tree.setColumnCount(5)
    tree.setHeaderLabels(["选择", "候选", "人数", "匹配度", "判定依据"])
    tree.setColumnWidth(0, width)
    tree.setColumnWidth(1, 190)
    root = QTreeWidgetItem(["", "", "", "", ""])
    tree.addTopLevelItem(root)
    for _ in range(6):
        it = QTreeWidgetItem(["", "よしい美希 / よし美希", "2 人", "94 标注", "姓名去括号后缀后完全…"])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(0, Qt.Unchecked)
        root.addChild(it)
    root.setExpanded(True)
    tree.resize(560, 300)
    tree.show()
    for _ in range(6):
        app.processEvents()
    return tree


def _grab_sel_col(tree, state, rows=3):
    """抓「选择」列的像素；state=None 表示树里不放任何子行（空基准）。"""
    root = tree.topLevelItem(0)
    if state is None:
        for i in range(root.childCount() - 1, -1, -1):
            root.removeChild(root.child(i))
    else:
        for i in range(min(rows, root.childCount())):
            root.child(i).setCheckState(0, state)
    for _ in range(6):
        app.processEvents()
    img = tree.grab().toImage()
    x0, x1 = 20, 20 + tree.columnWidth(0)
    y0 = tree.header().height() + 4
    y1 = y0 + 22 * rows
    return [img.pixelColor(xx, yy).rgba()
            for yy in range(y0, y1) for xx in range(x0, x1)]


def indicator_pixels(_unused, state):
    """量「选择」列里被真正画了东西的像素数（与**空树**逐像素差分）。

    ⚠⚠ 基准必须是**空树**（无子行），不能是「同样 Unchecked 的树」——
    那样两次画的是同一批复选框，差分**恒为 0**，什么也证明不了
    （第一版探针就栽在这，害得误以为「未勾选确实不画」，其实是我基准选错）。
    """
    base_tree = build(62)
    base = _grab_sel_col(base_tree, None)
    base_tree.close()

    tree = build(62)
    pix = _grab_sel_col(tree, state)
    tree.close()
    return sum(1 for a, b in zip(pix, base) if a != b)


print("=== 判定：未勾选态到底画没画（基准=空树）===")
for w in (46, 62, 80):
    def bw(w=w):
        t = build(w)
        return t
    tree = bw()
    tree.close()
    # 按列宽分别测
    res = {}
    for st, nm in ((Qt.Unchecked, "未勾选"), (Qt.Checked, "已勾选")):
        base_tree = build(w)
        base = _grab_sel_col(base_tree, None)
        base_tree.close()
        t = build(w)
        pix = _grab_sel_col(t, st)
        t.close()
        res[nm] = sum(1 for a, b in zip(pix, base) if a != b)
    print("  列宽 %2d：未勾选差异像素=%4d   已勾选差异像素=%4d" %
          (w, res["未勾选"], res["已勾选"]))

# 问 Qt：indicator 矩形落在哪、有多大（用 style 直接问，delegate 没有该方法）
tree = build(62)
item = tree.topLevelItem(0).child(0)
idx = tree.indexFromItem(item)
opt = QStyleOptionViewItem()
opt.initFrom(tree)
opt.rect = tree.visualRect(idx)
opt.state = QStyle.State_Enabled
print("\n=== subElementRect(CheckIndicator) 实际矩形 ===")
print("  item rect      =", opt.rect)
rect = tree.style().subElementRect(
    QStyle.SE_ItemViewItemCheckIndicator, opt, None)
print("  indicator rect =", rect, " 宽高", rect.width(), rect.height())
col_right = opt.rect.left() + tree.columnWidth(0)
print("  → indicator 右缘 x=%d；列 0 右边界 x=%d → %s"
      % (rect.right(), col_right,
         "在列内" if rect.right() <= col_right else "★ 超出列宽被裁！"))
tree.close()
print("PROBE_CB_DONE")
