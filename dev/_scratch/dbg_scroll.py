# -*- coding: utf-8 -*-
import io, os, sys, tempfile, time
ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
TMP = os.path.join(tempfile.gettempdir(), "lmc_dbg_scroll")
INDEX = os.path.join(TMP, "index_data")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ.pop("LMC_NO_SYSMON", None)
import applog
applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")
import config as cfg, database as db
db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
import version as ver
import sysmon
db.init_db()
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication, QWidget, QScrollArea, QVBoxLayout, QHBoxLayout)
app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
import main_window as mw
mw.load_style(app)

class FakeCard(QWidget):
    def __init__(self, pair):
        super().__init__()
        m, _, _ = pair
        self.media = m
        self.setFixedHeight(300)
        self.setGeometry(0, 0, 180, 300)
    def set_selected(self, s):
        self._selected = bool(s)

_BIG = 5000
def _fetch_big(o, l):
    return [({"id": i, "title": "影片%d" % i, "year": 2000 + (i % 25)}, {}, 0)
            for i in range(o, min(o + l, _BIG))]

grid = mw.LazyGrid(_fetch_big, FakeCard, _BIG, kind="media", batch=60)
grid._pump = lambda: None
scroll = QScrollArea()
scroll.setWidget(grid)
grid.attach_scroll(scroll.verticalScrollBar())
grid._card_h = 300; grid._row_h = 312; grid._recompute_body_height()
host = QWidget(); host.setFixedSize(1000, 820)
hl = QHBoxLayout(host); hl.setContentsMargins(0,0,0,0); hl.addWidget(scroll)
host.show()
for _ in range(3):
    app.processEvents(); time.sleep(0.05)
sb = scroll.verticalScrollBar()
print("after show: sb.min/max/val =", sb.minimum(), sb.maximum(), sb.value())
print("  viewport.h =", scroll.viewport().height())
print("  grid.height =", grid.height(), " body.height =", grid._body.height())
print("  _virtual =", grid._virtual, " _cards =", len(grid._cards))
# 离屏下原生滚动条范围被压成 0，显式对齐 body 高度
_vmax = max(0, grid._body.height() - scroll.viewport().height())
sb.setRange(0, _vmax)
print("forced sb range: 0 ..", sb.maximum())
sb.setValue(sb.maximum())
print("after setValue(max): sb.val =", sb.value(), " max =", sb.maximum())
for _ in range(3):
    app.processEvents(); time.sleep(0.05)
print("after pump: sb.val =", sb.value())
print("  _cards =", len(grid._cards), " max id =", max((c.media['id'] for c in grid._cards.values()), default=-1))
sb.setValue(0)
for _ in range(3):
    app.processEvents(); time.sleep(0.05)
print("back to top: sb.val =", sb.value(), " _cards =", len(grid._cards), " 0 in?", 0 in grid._cards)
