# -*- coding: utf-8 -*-
"""v1.39.5 复现探针（rewrite）：真机尺寸下量复选框间隙与下半被压扁。"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QStyleFactory, QStyle,
                               QStyleOptionViewItem, QGroupBox, QSplitter)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
app.setStyle(QStyleFactory.create("Fusion"))
for f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

from main_window import load_style
load_style(app)
import ui_actorcheck as ack

# 工具窗真机客户区 1318x900；页面外层还有一点边距 → 用 1318x866 近似
W, H = 1318, 866
page = ack.ActorCheckPage()
page.resize(W, H)
page.show()
app.processEvents()

CLUSTERS = [
    {"members": [{"name": "よいし美希"}, {"name": "よいし美希（伊藤）"}],
     "ids": [1, 2], "score": 94, "tier": "铁证",
     "reasons": ["姓名去掉包装后缀后完全一致"], "profile_consistent": True},
    {"members": [{"name": "加藤ツバキ"}, {"name": "加藤ツバキ（夏希）"}],
     "ids": [3, 4], "score": 94, "tier": "铁证",
     "reasons": ["姓名去掉包装后缀后完全一致"], "profile_consistent": True},
    {"members": [{"name": "川上ゆう"}, {"name": "川上ゆう（森野雰）"}],
     "ids": [5, 6], "score": 94, "tier": "铁证",
     "reasons": ["姓名去掉包装后缀后完全一致"], "profile_consistent": True},
    {"members": [{"name": "広瀬奈々美"}, {"name": "広瀬奈々美（堀…）"}],
     "ids": [7, 8], "score": 94, "tier": "铁证",
     "reasons": ["姓名去掉包装后缀后完全一致"], "profile_consistent": True},
    {"members": [{"name": "碧しの"}, {"name": "碧しの（篠めぐみ）"}],
     "ids": [9, 10], "score": 94, "tier": "铁证",
     "reasons": ["姓名去掉包装后缀后完全一致"], "profile_consistent": True},
]
res = {"clusters": CLUSTERS, "suspects": [], "scanned": 6562, "pairs": 291,
       "merge_people": 5, "elapsed": 0.3, "ai_review": {}}
page._on_done(res)
app.processEvents()

tree = page.tree
style = tree.style()
print("=" * 68)
print("页面 =", page.size(), " 树行数 =", tree.topLevelItemCount())
print("=" * 68)

print("\n① 第 0 列几何（复选框 vs 文本）")
print("-" * 68)
print("列宽 =", [tree.columnWidth(i) for i in range(tree.columnCount())])
print("indentation =", tree.indentation())
worst = 999
for r in range(tree.topLevelItemCount()):
    item = tree.topLevelItem(r)
    if item is None:
        continue
    vr = tree.visualItemRect(item)
    o = QStyleOptionViewItem(); o.initFrom(tree); o.rect = vr
    o.font = tree.font(); o.widget = tree
    o.features |= QStyleOptionViewItem.HasDisplay
    chk = style.subElementRect(QStyle.SE_ItemViewItemCheckIndicator, o, tree)
    txt = style.subElementRect(QStyle.SE_ItemViewItemText, o, tree)
    gap = txt.left() - chk.right()
    if chk.height() > 0:
        worst = min(worst, gap)
        print("  %-34s check=%s text_left=%-4d 间隙=%d"
              % (item.text(1)[:32], "%dx%d@%d" % (chk.width(), chk.height(),
                                                  chk.left()),
                 txt.left(), gap))
        for c in range(item.childCount()):
            ch = item.child(c)
            vr2 = tree.visualItemRect(ch)
            o2 = QStyleOptionViewItem(); o2.initFrom(tree); o2.rect = vr2
            o2.font = tree.font(); o2.widget = tree
            o2.features |= QStyleOptionViewItem.HasDisplay
            ck = style.subElementRect(QStyle.SE_ItemViewItemCheckIndicator, o2, tree)
            tx = style.subElementRect(QStyle.SE_ItemViewItemText, o2, tree)
            g2 = tx.left() - ck.right()
            if ck.height() > 0:
                worst = min(worst, g2)
                print("    子行 check=%s text_left=%-4d 间隙=%d"
                      % ("%dx%d@%d" % (ck.width(), ck.height(), ck.left()),
                         tx.left(), g2))
print("  → 最小间隙 = %d px  %s" % (worst, "太挤(<10)" if worst < 10 else "OK"))
if worst == 999:
    print("  ⚠ worst 仍是初值 999 —— 说明**一个子行复选框都没量到**（根节点无 checkbox）。"
          "这不是「间隙无限大」，而是探针没遍历到子行；请核对树里是否真的有簇行。")

print("\n② 上下两段高度")
print("-" * 68)
sp = page.findChild(QSplitter)
if sp:
    print("  splitter 实际 =", sp.size().width(), "x", sp.size().height())
    print("  splitter sizes =", sp.sizes(), "（请求 430/330）")
    for i in range(sp.count()):
        w = sp.widget(i)
        print("  段%d %-22s 实际高=%-4d hint=%-4d minHint=%-4d"
              % (i, type(w).__name__, w.height(), w.sizeHint().height(),
                 w.minimumSizeHint().height()))
for gb in page.findChildren(QGroupBox):
    print("  QGroupBox %-26r 实际高=%-4d hint=%-4d"
          % (gb.title()[:24], gb.height(), gb.sizeHint().height()))
print("  page.minimumHeight =", page.minimumHeight())

out = os.path.join(ROOT, "dev", "screenshots", "v1395_before.png")
page.grab().save(out)
print("\n出图:", out)

print("\n③ 测连文案")
print("-" * 68)
import scraper
for msg, src in (("HTTP 403", "minnano"),
                 ("UNEXPECTED_EOF_WHILE_READING", "minnano"),
                 ("命中反爬挑战页（WAF 回 202）", "imdb")):
    s = scraper._explain(msg, src)
    ok = ("换网络" in s or "换代理" in s)
    print("  [%s] 有换网络出路=%-5s %s" % (src, ok, s[:150]))