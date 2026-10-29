# -*- coding: utf-8 -*-
"""v2.0.4（反馈 9）出图：卡片演职员名字的三档语义。

默认（未收藏）灰 → 收藏才高亮成身份色（女粉 / 男蓝 / 导演黄 / 未知白）→ 置顶加粗。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QStyleFactory
from PySide6.QtGui import QImage, QPainter, QPixmap, QColor, QFontDatabase, QLinearGradient
from PySide6.QtCore import Qt

OUT = os.path.join(ROOT, "docs", "preview")
os.makedirs(OUT, exist_ok=True)

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setStyle(QStyleFactory.create("Fusion"))

import main_window as mw      # noqa: E402
mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

TMP = r"C:/Users/zouzu/AppData/Local/Temp/v204probe"
os.makedirs(TMP, exist_ok=True)


def mk_poster(path, c1, c2):
    pm = QPixmap(158, 236)
    g = QLinearGradient(0, 0, 0, 236)
    g.setColorAt(0.0, QColor(c1))
    g.setColorAt(1.0, QColor(c2))
    p = QPainter(pm)
    p.fillRect(pm.rect(), g)
    p.end()
    pm.save(path)
    return path


POSTER = mk_poster(os.path.join(TMP, "crew.png"), "#2a2a30", "#141417")

# 四种状态各一张卡
CASES = [
    ("① 默认（未收藏）", [("依本しおり", 0, 0, "female"), ("大志", 0, 0, "male")],
     [("K*WEST", 0, 0, "")]),
    ("② 收藏 → 高亮", [("依本しおり", 1, 0, "female"), ("大志", 1, 0, "male")],
     [("K*WEST", 1, 0, "")]),
    ("③ 置顶 → 加粗", [("依本しおり", 0, 1, "female"), ("大志", 0, 1, "male")],
     [("K*WEST", 0, 1, "")]),
    ("④ 收藏 + 置顶", [("依本しおり", 1, 1, "female"), ("大志", 1, 1, "male")],
     [("K*WEST", 1, 1, "")]),
]

host = QWidget()
host.setObjectName("Host")
host.setStyleSheet("QWidget#Host{background:#0a0a0b;}")
host.setAttribute(Qt.WA_StyledBackground, True)
h = QHBoxLayout(host)
h.setContentsMargins(16, 14, 16, 14)
h.setSpacing(18)
for i, (_tag, ac, dc) in enumerate(CASES):
    m = {"id": i + 1, "title": "CASE-%d 着色三档" % (i + 1), "poster": POSTER,
         "rating": 8.5, "year": 2025, "quality": "4K", "favorite": 0,
         "file_path": "X:/a/b.mp4", "plot": "", "tags": ""}
    c = mw.PosterCard(m, lambda *_a: None, on_play=lambda *_a: None,
                      on_fav=lambda *_a: None, actor_crew=ac, director_crew=dc)
    h.addWidget(c)
h.addStretch(1)
host.resize(len(CASES) * 172 + 18 * 2 + 40, 360)
host.show()
app.processEvents()
for _ in range(3):
    app.processEvents()
pm = host.grab()
im = pm.toImage().convertToFormat(QImage.Format_ARGB32)
canvas = QImage(im.width(), im.height(), QImage.Format_ARGB32)
canvas.fill(QColor("#0a0a0b"))
p = QPainter(canvas)
p.drawImage(0, 0, im)
p.end()
canvas.save(os.path.join(OUT, "v204_crew_states.png"))
print("saved v204_crew_states.png", canvas.width(), "x", canvas.height())

print("--- HTML 自检 ---")
for tag, ac, dc in CASES:
    print(" ", tag, "|", mw._crew_names_html(ac, "", "actor"))
print("DONE")
