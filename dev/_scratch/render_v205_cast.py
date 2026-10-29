# -*- coding: utf-8 -*-
"""v2.0.5（反馈 10）出图：详情页「演职人员信息」沿用卡片的三档规则。

默认灰 → 收藏才上身份色（女粉 / 男蓝 / 导演黄 / 未知白）→ 置顶只加粗。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QStyleFactory
from PySide6.QtGui import QImage, QPainter, QColor, QFontDatabase
from PySide6.QtCore import Qt

OUT = os.path.join(ROOT, "docs", "preview")
app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setStyle(QStyleFactory.create("Fusion"))

import main_window as mw      # noqa: E402
import ui_hero as uhero       # noqa: E402
mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

CASES = [
    ("未收藏", {"name": "佐藤愛璃", "gender": "female", "char_role": "Actor"}, ""),
    ("未收藏", {"name": "大志", "gender": "male", "char_role": "Actor"}, ""),
    ("收藏", {"name": "佐藤愛璃", "gender": "female", "char_role": "Actor",
              "favorite": 1}, ""),
    ("收藏", {"name": "大志", "gender": "male", "char_role": "Actor", "favorite": 1}, ""),
    ("收藏", {"name": "K*WEST", "gender": "", "char_role": "导演",
              "role_type": "Director", "favorite": 1}, ""),
    ("置顶", {"name": "大志", "gender": "male", "char_role": "Actor", "pinned": 1}, ""),
    ("收藏+置顶", {"name": "佐藤愛璃", "gender": "female", "char_role": "Actor",
                   "favorite": 1, "pinned": 1}, ""),
]

row_host = QWidget()
row_host.setObjectName("CastRow")
row_host.setStyleSheet("QWidget#CastRow{background:#111113;}")
row_host.setAttribute(Qt.WA_StyledBackground, True)
rl = QHBoxLayout(row_host)
rl.setContentsMargins(14, 12, 14, 12)
rl.setSpacing(10)
_keep = []
for tag, p, _ in CASES:
    av = uhero.CastAvatar(p, None, size=84)
    _keep.append(av)
    rl.addWidget(av)
rl.addStretch(1)
row_host.show()
app.processEvents()
for _ in range(3):
    app.processEvents()

pm = row_host.grab()
im = pm.toImage().convertToFormat(QImage.Format_ARGB32)
canvas = QImage(im.width(), im.height(), QImage.Format_ARGB32)
canvas.fill(QColor("#111113"))
p = QPainter(canvas)
p.drawImage(0, 0, im)
p.end()
canvas.save(os.path.join(OUT, "v205_cast_states.png"))
print("saved v205_cast_states.png", canvas.width(), "x", canvas.height())

print("--- 自检 ---")
from PySide6.QtWidgets import QLabel   # noqa: E402
for tag, person, _ in CASES:
    av = uhero.CastAvatar(person, None, size=84)
    _keep.append(av)
    lab = next(l for l in av.findChildren(QLabel) if l.text() == person["name"])
    print("  %-8s %-8s %s" % (tag, person["name"], lab.styleSheet()))
print("DONE")
