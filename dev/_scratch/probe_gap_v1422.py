# -*- coding: utf-8 -*-
"""v1.42.2 反馈实测：① ActorSplitH（横向 splitter）把手现状；② IMDB 行下方留白构成。"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QGroupBox, QSplitter
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_gap_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow, load_style
import ui_actorcheck as uac
from ui_settings import SettingsDialog

load_style(app)


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

pg = dlg._pg_scraper
seen = 0
while hasattr(pg, "widget") and seen < 4:
    inner = pg.widget()
    if inner is None:
        break
    pg = inner
    seen += 1

g0 = [g for g in pg.findChildren(QGroupBox) if "数据源" in g.title()][0]
sl = dlg.src_list
print("== 数据源组 ==")
print("  src_list h =", sl.height(), " spacing =", sl.spacing(),
      " frame =", sl.frameWidth())
p_list = sl.mapTo(g0, QPoint(0, 0))
print("  src_list y in g0 =", p_list.y(), " bottom =", p_list.y() + sl.height())
# 行 widget 在 g0 坐标里的位置/高
rows = []
for i in range(sl.count()):
    w = sl.itemWidget(sl.item(i))
    p = w.mapTo(g0, QPoint(0, 0))
    rows.append((p.y(), w.height()))
    print(f"  row{i}: y={p.y()} h={w.height()} bottom={p.y()+w.height()}")
last_bottom = rows[-1][0] + rows[-1][1]
print("  末行 bottom =", last_bottom, " -> 列表内底部空 =", p_list.y() + sl.height() - last_bottom)
# srcbtns 行
for w in g0.findChildren(object):
    pass
btns = None
for c in g0.children():
    if type(c).__name__ == "QWidget" and c.layout() is not None:
        kids = [c.layout().itemAt(i).widget() for i in range(c.layout().count())]
        names = [k.text() if hasattr(k, "text") else "" for k in kids if k]
        if any("测试全部数据源" in n for n in names):
            btns = c
            break
if btns is not None:
    p = btns.mapTo(g0, QPoint(0, 0))
    print("  srcbtns y in g0 =", p.y(), " h =", btns.height())
    print("  >> IMDB 行底 -> 按钮行顶 空档 =", p.y() - last_bottom)
# 组框内容边距
m = g0.layout().contentsMargins()
print("  g0 layout margins =", m.left(), m.top(), m.right(), m.bottom(),
      " spacing =", g0.layout().spacing())

print("\n== 演员检测页 横向 splitter（ActorSplitH） ==")
page = uac.ActorCheckPage()
page.setAttribute(Qt.WA_DontShowOnScreen, True)
page.resize(1200, 860)
page.show()
app.processEvents()
for sp in page.findChildren(QSplitter):
    h1 = sp.handle(1) if sp.count() > 1 else None
    print(f"  {sp.objectName():14s} orient={'V' if sp.orientation() == Qt.Vertical else 'H'} "
          f"handleWidth={sp.handleWidth()} handle={type(h1).__name__} "
          f"size={h1.width()}x{h1.height() if h1 else '?'}")
print("GAP_PROBE_DONE")
