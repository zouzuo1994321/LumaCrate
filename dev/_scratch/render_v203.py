# -*- coding: utf-8 -*-
"""v2.0.3（反馈：收藏外不需要圆形）的离屏出图。

只验这一条：**播放钮仍是圆底**、**收藏钮只剩星形本体 + 沿轮廓柔影**，
两者控件仍 34×34、底边齐平、左右对称。

出三张卡：
  · 亮海报 + 未收藏        → 白描边星在亮底上靠轮廓黑影压得住
  · 暗海报 + 已收藏 + 播放悬停 → 金星 / 播放圆底变高亮色
  · 亮海报 + 收藏悬停       → 星描边变高亮色（不填充、无圆底）
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

import main_window as mw   # noqa: E402
mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

TMP = r"C:/Users/zouzu/AppData/Local/Temp/v203probe"
os.makedirs(TMP, exist_ok=True)


def save(w, name, bg="#0a0a0b", pad=0):
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


LIGHT = mk_poster(os.path.join(TMP, "light.png"), "#f2e6d2", "#d8c3a0")
DARK = mk_poster(os.path.join(TMP, "dark.png"), "#2a2a30", "#141417")


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
for _ in range(3):
    app.processEvents()
save(host, "v203_card_buttons.png", bg="#0a0a0b", pad=0)

# 单卡 2× 放大（看星形轮廓与柔影、播放圆底的阴影环）
one = cards[0]
pm = one.grab().scaled(one.width() * 2, one.height() * 2, Qt.KeepAspectRatio,
                       Qt.SmoothTransformation)
pm.save(os.path.join(OUT, "v203_card_buttons_zoom.png"))
print("saved zoom", pm.size())

# 三个按钮的独立 4× 特写（并排：播放 / 未收藏 / 已收藏 / 收藏悬停）
strip = QWidget()
strip.setObjectName("Strip")
strip.setStyleSheet("QWidget#Strip{background:#0a0a0b;}")
strip.setAttribute(Qt.WA_StyledBackground, True)
row = QHBoxLayout(strip)
row.setContentsMargins(14, 12, 14, 12)
row.setSpacing(16)
probes = []
for label, fav, hover in (("播放", False, False), ("收藏", False, False),
                          ("已收藏", True, False), ("收藏悬停", False, True)):
    col = QVBoxLayout()
    col.setSpacing(6)
    b = mw._FavStarButton() if label != "播放" else mw._PlayGlyphButton()
    if fav:
        b.set_on(True)
    if hover:
        b.setAttribute(Qt.WA_UnderMouse, True)
    b.update()
    probes.append(b)
    wrap = QWidget()
    wrap.setStyleSheet("background:transparent;")
    wl = QHBoxLayout(wrap)
    wl.setContentsMargins(0, 0, 0, 0)
    wl.addStretch(1)
    wl.addWidget(b)
    wl.addStretch(1)
    col.addWidget(wrap)
    ll = QLabel(label)
    ll.setAlignment(Qt.AlignCenter)
    ll.setStyleSheet("color:#a1a1aa;font-size:11px;")
    col.addWidget(ll)
    row.addLayout(col)
strip.show()
app.processEvents()
for _ in range(3):
    app.processEvents()
pm = strip.grab().scaled(strip.width() * 4, strip.height() * 4, Qt.KeepAspectRatio,
                         Qt.SmoothTransformation)
pm.save(os.path.join(OUT, "v203_btn_strip.png"))
print("saved strip", pm.size())

# 几何/像素自检
for c in cards:
    print("  card", c.size(), "play", c.play_btn.size(), "fav", c.fav_btn.size(),
          "sync", c.play_btn.y() == c.fav_btn.y())
for b in probes:
    im = b.grab().toImage()
    print("  btn", b.objectName(), b.__class__.__name__, "HAS_CIRCLE",
          b.HAS_CIRCLE, "corner a=%d" % im.pixelColor(3, 3).alpha())
print("DONE")
