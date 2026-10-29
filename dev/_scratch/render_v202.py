# -*- coding: utf-8 -*-
"""v2.0.2 六条反馈的离屏出图（QT_QPA_PLATFORM=windows + Fusion，与真机同路径）。"""
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

import config as cfg
import main_window as mw
mw.load_style(app)


def save(w, name, bg="#18181b", pad=0):
    pm = w.grab()
    im = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    canvas = QImage(im.width() + pad * 2, im.height() + pad * 2, QImage.Format_ARGB32)
    canvas.fill(QColor(bg))
    p = QPainter(canvas)
    p.drawImage(pad, pad, im)
    p.end()
    path = os.path.join(OUT, name)
    canvas.save(path)
    print("saved", path, canvas.width(), "x", canvas.height())
    return path


TMP = r"C:/Users/zouzu/AppData/Local/Temp/v202probe"
os.makedirs(TMP, exist_ok=True)


def mk_poster(path, c1, c2, dark=False):
    """造一张海报：亮底用来验阴影能不能压住，暗底用来验描边。"""
    pm = QPixmap(158, 236)
    g = QLinearGradient(0, 0, 0, 236)
    g.setColorAt(0.0, QColor(c1))
    g.setColorAt(1.0, QColor(c2))
    p = QPainter(pm)
    p.fillRect(pm.rect(), g)
    p.end()
    pm.save(path)
    return path


LIGHT = mk_poster(os.path.join(TMP, "light.png"), "#f2e6d2", "#d8c3a0")
DARK = mk_poster(os.path.join(TMP, "dark.png"), "#2a2a30", "#141417")

# ---------- ① 卡片两个按钮：圆形 / 等大 / 阴影 ----------
def mk_media(poster, fav, title):
    return {"id": 1, "title": title, "poster": poster, "rating": 8.5, "year": 2025,
            "quality": "4K", "favorite": fav, "file_path": "X:/a/b.mp4",
            "plot": "", "tags": ""}


host = QWidget()
host.setObjectName("CardHost")
host.setStyleSheet("QWidget#CardHost{background:#0a0a0b;}")
host.setAttribute(Qt.WA_StyledBackground, True)
h = QHBoxLayout(host)
h.setContentsMargins(16, 14, 16, 14)
h.setSpacing(18)
cards = []
for poster, fav, ttl, hover in ((LIGHT, False, "748SPAY-387 ホテルスタッフN", ""),
                                (DARK, True, "SABA-613 東京OLカレン", "play"),
                                (LIGHT, False, "IENF-371 パンスト直履き", "star")):
    c = mw.PosterCard(mk_media(poster, fav, ttl), lambda *_a: None,
                      on_play=lambda *_a: None, on_fav=lambda *_a: None,
                      actor_crew=[("森下つかさ", False, False)],
                      director_crew=[("FC3@素人パコパコ団", False, False)])
    if hover == "play" and c.play_btn is not None:
        c.play_btn.setAttribute(Qt.WA_UnderMouse, True)
        c.play_btn.update()
    if hover == "star" and c.fav_btn is not None:
        c.fav_btn.setAttribute(Qt.WA_UnderMouse, True)
        c.fav_btn.update()
    cards.append(c)
    h.addWidget(c)
h.addStretch(1)
host.resize(len(cards) * 172 + 18 * 2 + 40, 360)
host.show()
app.processEvents()
save(host, "v202_card_buttons.png", bg="#0a0a0b", pad=0)
for c in cards:
    print("  card", c.size(), "play", c.play_btn.size() if c.play_btn else None,
          "fav", c.fav_btn.size() if c.fav_btn else None)
# 单卡放大（2x）便于看圆与阴影
one = cards[0]
pm = one.grab().scaled(one.width() * 2, one.height() * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
pm.save(os.path.join(OUT, "v202_card_buttons_zoom.png"))
print("saved zoom", pm.size())

# ---------- ③ 我的评分：上下微调按钮回来了 ----------
import ui_hero as uhero
rd = uhero.RateDialog(None, 10.0)
rd.show()
app.processEvents()
print("  rate dialog", rd.size(), "spin", rd.spin.size(),
      "symbols", rd.spin.buttonSymbols())
save(rd, "v202_rate_dialog.png", bg="#18181b", pad=0)

# ---------- ⑤⑥ 标题跟主题色 / 两处白色 ----------
box = QWidget()
box.setObjectName("T")
box.setStyleSheet("QWidget#T{background:#0a0a0b;}")
box.setAttribute(Qt.WA_StyledBackground, True)
v = QVBoxLayout(box)
v.setContentsMargins(20, 16, 20, 16)
v.setSpacing(8)
pink = "#e4587c"
for acc in ("#006fee", pink):
    lab = QLabel("高亮色 = %s" % acc)
    lab.setStyleSheet("color:#71717a;font-size:11px;")
    v.addWidget(lab)
    ctx = QWidget()          # 模拟 render_style 用该色重载样式表
    ctx.setObjectName("Ctx")
    ctx.setStyleSheet("QWidget#Ctx{background:transparent;}")
    ctx.setAttribute(Qt.WA_StyledBackground, True)
    cv = QVBoxLayout(ctx)
    cv.setContentsMargins(0, 0, 0, 6)
    t = mw.MainWindow._h1(None, "最近播放 / 最近添加")
    t.setStyleSheet(t.styleSheet() + "color:%s;" % acc)   # 近似：真机由 QSS 令牌给色
    cv.addWidget(t)
    p1 = QLabel("检索并选择影片"); p1.setObjectName("PlainTitle")
    p2 = QLabel("100%"); p2.setObjectName("PlainValue")
    row = QHBoxLayout(); row.addWidget(p1); row.addStretch(1); row.addWidget(p2)
    cv.addLayout(row)
    v.addWidget(ctx)
box.resize(420, 240)
box.show()
app.processEvents()
save(box, "v202_titles.png", bg="#0a0a0b", pad=0)

print("DONE")
