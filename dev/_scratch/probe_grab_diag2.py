# -*- coding: utf-8 -*-
"""诊断②：在**全局样式表已加载**（与冒烟 ㉟ 同环境）下，怎么拿到干净的深底图。

仅离屏时 grab() 是黑的；一上 load_style(app) 之后，同一个 RoundPlus 量出来整块 28×24
都是亮像素 —— 说明底色来源变了。这里把 4 种取图法在「有样式」环境下重新比一遍。
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = tempfile.mkdtemp(prefix="lmc_diag2_")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtCore import Qt                                   # noqa: E402
from PySide6.QtGui import QFontDatabase, QPalette, QColor       # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget             # noqa: E402

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db      # noqa: E402
import config as cfg       # noqa: E402
import applog              # noqa: E402

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP
db.init_db()

import main_window as mw    # noqa: E402
import ui_hero as uh        # noqa: E402

mw.load_style(app)
print("全局样式表已加载：", len(app.styleSheet()), "字符")


def report(img, tag, pts=((0, 0), (13, 11))):
    vals = []
    for (x, y) in pts:
        c = img.pixelColor(x, y)
        vals.append("(%d,%d)=a%d %s" % (x, y, c.alpha(), c.name()))
    print("  %-30s %s" % (tag, "  ".join(vals)))


print("=== A: WA_NoSystemBackground + grab ===")
w = uh.RoundPlus(28, 24, tip="x")
w.setAttribute(Qt.WA_NoSystemBackground, True)
report(w.grab().toImage(), "NoSystemBackground", pts=((0, 0), (13, 11), (1, 20)))

print("=== B: autoFillBackground + 深色调色板 ===")
w = uh.RoundPlus(28, 24, tip="x")
pal = w.palette()
pal.setColor(QPalette.Window, QColor("#0d0d10"))
w.setPalette(pal)
w.setAutoFillBackground(True)
report(w.grab().toImage(), "autoFill+palette")

print("=== C: 控件自己上 QSS 深色底 ===")
w = uh.RoundPlus(28, 24, tip="x")
w.setStyleSheet("background:#0d0d10;")
report(w.grab().toImage(), "setStyleSheet(bg)")

print("=== D: 装进深色容器里 grab 容器 ===")
box = QWidget()
box.setAttribute(Qt.WA_StyledBackground, True)
box.setStyleSheet("background:#0d0d10;")
box.resize(28, 24)
w = uh.RoundPlus(28, 24, tip="x", parent=box)
w.move(0, 0)
box.show()
for _ in range(6):
    app.processEvents()
report(box.grab().toImage(), "container(WA_StyledBackground)")

print("=== 对照：RoundClose(14) 在 A 法下的表现 ===")
rc = uh.RoundClose(14, on_click=lambda: None)
rc.setAttribute(Qt.WA_NoSystemBackground, True)
report(rc.grab().toImage(), "RoundClose A法", pts=((0, 0), (6, 6)))
print("DONE")
