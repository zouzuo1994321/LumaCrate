# -*- coding: utf-8 -*-
"""量一下演员卡 facts 网格的真实几何：单元格宽 / 每格 sizeHint / 字体大小。"""
import os
import sys
import json
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont, QFontMetrics
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_m_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

import main_window as mw
from main_window import MainWindow, ActorCard, ACTOR_CARD_W, ACTOR_CARD_H, _ACTOR_PAD

LOG = open("C:/Users/zouzu/AppData/Local/Temp/measure.log", "w", encoding="utf-8")


def p(*a):
    print(*a, file=LOG, flush=True)


win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1600, 900)
win.show()
app.processEvents()

p("ACTOR_CARD_W=%s H=%s PAD=%s" % (ACTOR_CARD_W, ACTOR_CARD_H, _ACTOR_PAD))

for size, height in (("T158 / B92(E) / W58 / H89", "158cm"),):
    person = {"id": 1, "name": "音琴るい", "birthday": "1994-01-16", "status": "现役",
              "favorite": 0, "pinned": 0, "thumb": "", "last_year": 2026,
              "meta": json.dumps({"尺寸": size, "身高": height, "出身地": "山梨県"},
                                 ensure_ascii=False)}
    ac = ActorCard(person, lambda *a: None, lambda *a: None, lambda *a: None,
                   lambda *a: None, win)
    ac.show()
    app.processEvents()
    p("\ncard size = %dx%d" % (ac.width(), ac.height()))
    for k, c in ac._fact_cells.items():
        fm = c.fontMetrics()
        p("  %-4s cell=%dx%d  sizeHint=%d  hintH=%d  fontPx=%d pt=%s" % (
            k, c.width(), c.height(), c.sizeHint().width(), c.sizeHint().height(),
            fm.height(), c.font().pointSizeF()))
    # 逐格量文本宽度
    p("\n  文本宽度（当前字体）:")
    for txt in ("出生 1994-01-16", "出身地 山梨県", "身高 158cm", "胸围 92cm",
                "三围 胸92·腰58·臀89"):
        fm = ac._fact_cells["出生"].fontMetrics()
        p("    %-22s %4d px" % (txt, fm.horizontalAdvance(txt)))
    p("\n  不同字号下的宽度:")
    f = QFont(ac.font())
    for px in (14, 13, 12, 11, 10, 9):
        f.setPixelSize(px)
        fm = QFontMetrics(f)
        p("    %2dpx -> 出生=%4d  三围=%4d  出身地=%4d" % (
            px, fm.horizontalAdvance("出生 1994-01-16"),
            fm.horizontalAdvance("三围 胸92·腰58·臀89"),
            fm.horizontalAdvance("出身地 山梨県")))

LOG.close()
print("ok")
