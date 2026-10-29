# -*- coding: utf-8 -*-
"""v2.0.3（反馈 8）出图：演职员名字按身份着色。

女演员 → 粉、男演员 → 蓝、导演 → 黄、未知 → 白；卡片小字与详情页演职人员同一套色。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout,
                               QLabel, QStyleFactory)
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
import ui_hero as uhero       # noqa: E402
mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

TMP = r"C:/Users/zouzu/AppData/Local/Temp/v203probe"
os.makedirs(TMP, exist_ok=True)


def save(w, name, bg="#0a0a0b"):
    pm = w.grab()
    im = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    canvas = QImage(im.width(), im.height(), QImage.Format_ARGB32)
    canvas.fill(QColor(bg))
    p = QPainter(canvas)
    p.drawImage(0, 0, im)
    p.end()
    path = os.path.join(OUT, name)
    canvas.save(path)
    print("saved", path, canvas.width(), "x", canvas.height())
    return path


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

# 三项元组（旧数据）/ 四项元组（v2.0.3 起带 gender）都要能画
CREWS = [
    # 女 + 男 + 未知
    ([("依本しおり", 0, 0, "female"), ("大志", 0, 0, "male"), ("某新人", 0, 0, "")],
     [("K*WEST", 0, 0, "")]),
    # 收藏 / 置顶：颜色仍按身份，标记走加粗 + 下划线
    ([("夏目ゆりか", 1, 0, "female"), ("男優A", 0, 1, "male")],
     [("うさぎぺん", 1, 1, "male")]),
    # 旧三元组：没有性别 → 白
    ([("无性别数据", 0, 0)], [("无性别导演", 0, 0)]),
]

host = QWidget()
host.setObjectName("Host")
host.setStyleSheet("QWidget#Host{background:#0a0a0b;}")
host.setAttribute(Qt.WA_StyledBackground, True)
h = QHBoxLayout(host)
h.setContentsMargins(16, 14, 16, 14)
h.setSpacing(18)
for i, (ac, dc) in enumerate(CREWS):
    m = {"id": i + 1, "title": "TEST-%03d 着色样例" % (i + 1), "poster": POSTER,
         "rating": 8.5, "year": 2025, "quality": "4K", "favorite": 0,
         "file_path": "X:/a/b.mp4", "plot": "", "tags": ""}
    c = mw.PosterCard(m, lambda *_a: None, on_play=lambda *_a: None,
                      on_fav=lambda *_a: None, actor_crew=ac, director_crew=dc)
    h.addWidget(c)
h.addStretch(1)
host.resize(3 * 172 + 18 * 2 + 40, 360)
host.show()
app.processEvents()
for _ in range(3):
    app.processEvents()
save(host, "v203_crew_colors_cards.png")

# 详情页演职人员一排
row_host = QWidget()
row_host.setObjectName("CastRow")
row_host.setStyleSheet("QWidget#CastRow{background:#111113;}")
row_host.setAttribute(Qt.WA_StyledBackground, True)
rl = QHBoxLayout(row_host)
rl.setContentsMargins(12, 10, 12, 10)
rl.setSpacing(8)
PEOPLE = [
    {"name": "依本しおり", "gender": "female", "char_role": "Actor", "role_type": "Actor"},
    {"name": "大志", "gender": "male", "char_role": "Actor", "role_type": "Actor"},
    {"name": "某新人", "gender": "", "char_role": "Actor", "role_type": "Actor"},
    {"name": "K*WEST", "gender": "male", "char_role": "导演", "role_type": "Director"},
    {"name": "夏目ゆりか", "gender": "female", "char_role": "Actor", "role_type": "Actor",
     "favorite": 1},
]
for p in PEOPLE:
    rl.addWidget(uhero.CastAvatar(p, lambda *_a: None, size=88))
rl.addStretch(1)
row_host.show()
app.processEvents()
for _ in range(3):
    app.processEvents()
save(row_host, "v203_crew_colors_cast.png", bg="#111113")

print("--- 判色自检 ---")
for g, d in (("female", False), ("male", False), ("", False), ("male", True), ("female", True)):
    print("  ", g or "<空>", "director" if d else "actor", "->", uhero.crew_name_color(g, d))
print("  卡片 HTML:", mw._crew_names_html(CREWS[1][0], "", "actor"))
print("  卡片 HTML:", mw._crew_names_html(CREWS[0][1], "", "director"))
print("DONE")
