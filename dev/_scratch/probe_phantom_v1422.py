# -*- coding: utf-8 -*-
"""v1.42.2 决定性探针：幻影空槽根因。

实验 A：QListWidgetItem(lw) + lw.addItem(li) 会不会重复入列？
实验 B：离屏重建真实 SettingsDialog（用户外观），量 src_list 的 count/高度/几何/逐项 widget。
实验 C：合成「3 行带 widget + 1 个无 widget 项」的列表，渲染看是否复现用户截图图案
        （底部 44px 空槽 + 组框底竖条 + 列表底边框）。
实验 D：sources 传 4 项（重复键 / 未知键）时 count 与 widget 情况。
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QListWidget, QListWidgetItem,
                               QWidget, QHBoxLayout, QLabel, QGroupBox, QVBoxLayout)
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtCore import Qt, QPoint, QRect, QSize

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

print("========== 实验 A：QListWidgetItem(parent) + addItem ==========")
lw = QListWidget()
for i in range(3):
    li = QListWidgetItem(lw)
    li.setText("row%d" % i)
    w = QWidget()
    QHBoxLayout(w).addWidget(QLabel("w%d" % i))
    li.setSizeHint(QSize(200, 44))
    lw.addItem(li)
    lw.setItemWidget(li, w)
print("count =", lw.count(), "（预期 3；若为 6 则构造函数+addItem 重复入列）")
for i in range(lw.count()):
    it = lw.item(i)
    print("  item%d: text=%r widget=%s" % (i, it.text(), lw.itemWidget(it) is not None))

print("\n========== 实验 B：真实对话框 ==========")
import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_phantom_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
st = cfg.Settings()
st.appearance.update({"mode": "磨砂玻璃", "level": "中", "accent": "#e2659a"})
cfg._SETTINGS = st
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow, load_style
from ui_settings import SettingsDialog

load_style(app, st.appearance)


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


SettingsDialog.screen = lambda self: _FakeScr()
win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
app.processEvents()
for k, b in dlg.sub_btns.items():
    if "刮削" in k:
        b.click()
        break
app.processEvents()

sl = dlg.src_list
print("sources in settings:", st.scraper.get("sources"))
print("count =", sl.count(), " fixedH =", sl.height(), " sizeHint =", sl.sizeHint())
print("geometry in dialog:", sl.geometry())
print("viewport:", sl.viewport().geometry(), " frameW:", sl.frameWidth())
for i in range(sl.count()):
    it = sl.item(i)
    w = sl.itemWidget(it)
    print("  item%d: key=%r widget=%s sizeHint=%s visualRect=%s"
          % (i, it.data(Qt.UserRole), w is not None,
             it.sizeHint(), sl.visualRect(sl.indexFromItem(it))))
print("spacing:", sl.spacing())
g0 = sl.parent()
print("g0 geometry in dialog:", g0.geometry() if isinstance(g0, QWidget) else None)

# 量 g0 内各子项几何（在 g0 坐标）
g0v = g0.layout()
print("g0v spacing:", g0v.spacing(), " margins:", g0v.contentsMargins())
for i in range(g0v.count()):
    it2 = g0v.itemAt(i)
    w2 = it2.widget()
    if w2 is not None:
        print("  g0 child%d: %s geo=%s" % (i, w2.__class__.__name__, w2.geometry()))

print("\n========== 实验 D：sources 4 项场景 ==========")
for label, srcs in (("重复键 imdb", ["avbase", "minnano", "imdb", "imdb"]),
                    ("未知键 javdb", ["avbase", "minnano", "imdb", "javdb"]),
                    ("空串键", ["avbase", "minnano", "imdb", ""])):
    st.scraper["sources"] = list(srcs)
    dlg._rebuild_source_list()
    app.processEvents()
    sl2 = dlg.src_list
    nw = sum(1 for i in range(sl2.count()) if sl2.itemWidget(sl2.item(i)) is not None)
    print("%-12s count=%d 有widget行=%d 列表高=%d"
          % (label, sl2.count(), nw, sl2.height()))
st.scraper["sources"] = ["avbase", "minnano", "imdb"]
dlg._rebuild_source_list()
app.processEvents()

print("\n========== 实验 C：合成 3+幻影 渲染 ==========")
box = QGroupBox("演员刮削数据源（自上而下依次尝试，命中后补其缺失字段）")
bv = QVBoxLayout(box)
bv.setSpacing(4)
syn = QListWidget()
syn.setSpacing(2)
syn.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
syn.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
bv.addWidget(syn)
for i, key in enumerate(["avbase", "minnano", "imdb"]):
    li = QListWidgetItem(syn)
    li.setData(Qt.UserRole, key)
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(6, 2, 6, 2)
    h.addWidget(QLabel("%s　描述文字描述文字" % key), 1)
    for t in ("↑", "↓", "测试"):
        h.addWidget(QLabel("[%s]" % t))
    h.addWidget(QLabel("—"))
    h.addWidget(QLabel("●"))
    li.setSizeHint(QSize(row.sizeHint().width(), 44))
    syn.addItem(li)
    syn.setItemWidget(li, row)
# 幻影项：只构造不 setItemWidget
li = QListWidgetItem(syn)
li.setData(Qt.UserRole, "phantom")
syn.addItem(li)
n = syn.count()
syn.setFixedHeight(max(64, 44 * n + 8))
btn = QWidget()
bh = QHBoxLayout(btn)
bh.setContentsMargins(0, 0, 0, 0)
bh.addWidget(QLabel("[测试全部数据源]  [Cloudflare 验证…]"))
bh.addStretch(1)
bh.addWidget(QLabel("提示：……"), 3)
bv.addWidget(btn)
box.resize(1129, 400)
box.show()
app.processEvents()
print("syn count =", syn.count(), " height =", syn.height())
for i in range(syn.count()):
    it = syn.item(i)
    print("  item%d: key=%r widget=%s" % (i, it.data(Qt.UserRole), syn.itemWidget(it) is not None))
print("syn list geometry in box:", syn.geometry())
syn.grab().save(os.path.join(TMP, "syn_list.png"))
box.grab().save(os.path.join(TMP, "syn_box.png"))
print("saved:", os.path.join(TMP, "syn_list.png"))

print("\n========== 实验 B 续：真实列表出图 ==========")
sl.grab().save(os.path.join(TMP, "real_list.png"))
pg = dlg._pg_scraper
seen = 0
while hasattr(pg, "widget") and seen < 4:
    inner = pg.widget()
    if inner is None:
        break
    pg = inner
    seen += 1
lp = sl.mapTo(pg, QPoint(0, 0))
print("list pos in page:", lp.x(), lp.y(), "size:", sl.width(), sl.height())
print("TMP:", TMP)
print("PHANTOM_PROBE_DONE")
