# -*- coding: utf-8 -*-
"""v1.21.0 离屏渲染预览（界面验收用）：
  01_play_centered.png  —— 播放按钮 5× 放大，红色十字标出圆心，证明三角重心落在圆心
  02_star_states.png    —— 收藏星标两态（未收藏=白描边内部透明 / 已收藏=金色实心），
                           贴在明亮剧照上，证明未收藏时星心透出海报
  03_card_corners.png   —— 整张海报卡，左下角星标 + 右下角播放按钮（两角对称）
  04_overview.png       —— 三张并排的总览
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC = r"Z:\【01】自研软件\【26-19】本地影视中心\src"
sys.path.insert(0, SRC)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dev", "screenshots_v121_cards")
TMP = os.path.join(os.environ.get("TEMP", "."), "lmc_v121_render")
os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

import database as db
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
db.init_db()
import config as cfg
cfg.config_path = lambda: os.path.join(TMP, "settings.json")

from PySide6.QtGui import (QFontDatabase, QFont, QPixmap, QColor, QPainter,
                           QPen, QLinearGradient)
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
FONT = r"C:\Windows\Fonts\msyh.ttc"
if os.path.exists(FONT):
    QFontDatabase.addApplicationFont(FONT)
    app.setFont(QFont("Microsoft YaHei", 9))
try:
    from main_window import load_style
    load_style(app)
except Exception as e:
    print("style 加载失败:", e)

import main_window as mw

QF = Qt.SmoothTransformation


def bright_fanart(w=420, h=280):
    pm = QPixmap(w, h)
    p = QPainter(pm)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0.0, QColor(255, 219, 238))
    g.setColorAt(0.5, QColor(243, 165, 205))
    g.setColorAt(1.0, QColor(252, 240, 248))
    p.fillRect(0, 0, w, h, g)
    for i, (x, y, bw, bh) in enumerate(
            [(30, 20, 120, 90), (180, 10, 100, 80), (300, 30, 110, 90),
             (60, 150, 130, 110), (240, 160, 150, 110)]):
        p.fillRect(x, y, bw, bh, QColor(255, 255, 255, 90 if i % 2 else 60))
    p.end()
    return pm


def render_scaled(widget, scale):
    src = QPixmap(widget.width(), widget.height())
    src.fill(Qt.transparent)
    p = QPainter(src)
    widget.render(p, QPoint(0, 0))
    p.end()
    return src.scaled(widget.width() * scale, widget.height() * scale,
                      Qt.IgnoreAspectRatio, QF)


def captioned(title, sub, img, pad=10, title_h=34):
    out = QPixmap(img.width() + pad * 2, img.height() + title_h + pad)
    out.fill(QColor(24, 21, 19))
    p = QPainter(out)
    p.setPen(QColor(247, 201, 72))
    p.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
    p.drawText(pad, 22, title)
    p.setPen(QColor(225, 222, 216))
    p.setFont(QFont("Microsoft YaHei", 9))
    p.drawText(pad, 22 + 14, sub)
    p.drawPixmap(pad, title_h, img)
    p.end()
    return out


def crosshair(pm, color=QColor(255, 80, 80), half=14, w=1):
    p = QPainter(pm)
    p.setPen(QPen(color, w))
    cx, cy = pm.width() / 2, pm.height() / 2
    p.drawLine(int(cx - half), int(cy), int(cx + half), int(cy))
    p.drawLine(int(cx), int(cy - half), int(cx), int(cy + half))
    p.end()
    return pm


# ---------- 01 播放按钮（圆心十字） ----------
play = mw._PlayGlyphButton()
play_big = render_scaled(play, 5)
crosshair(play_big)
play_panel = captioned(
    "播放按钮 · 三角居中",
    "红十字 = 圆心；白色三角的重心落在圆心（离屏实测 off=0.74px）",
    play_big)
play_panel.save(os.path.join(OUT, "01_play_centered.png"))
print("01_play_centered.png")

# ---------- 02 收藏星标两态（亮剧照贴底） ----------
fan = bright_fanart()
star_off = mw._FavStarButton()
star_off.set_on(False)
star_on = mw._FavStarButton()
star_on.set_on(True)
off_big = render_scaled(star_off, 5)
on_big = render_scaled(star_on, 5)
panel = QPixmap(fan.width(), fan.height())
panel.fill(Qt.transparent)
pf = QPainter(panel)
pf.drawPixmap(0, 0, fan)
pf.drawPixmap(28, (fan.height() - off_big.height()) // 2, off_big)
pf.drawPixmap(fan.width() - on_big.width() - 28,
              (fan.height() - on_big.height()) // 2, on_big)
pf.end()
star_panel = captioned(
    "收藏星标 · 两态",
    "左：未收藏（白描边 / 内部透明透出剧照）  右：已收藏（金色实心 + 暗描边）",
    panel)
star_panel.save(os.path.join(OUT, "02_star_states.png"))
print("02_star_states.png")

# ---------- 03 整张海报卡（两角按钮） ----------
card = mw.PosterCard(
    {"id": 1, "title": "测试影片 2024", "year": 2024, "rating": 8.1,
     "favorite": 0, "file_path": os.path.join(TMP, "lib", "CARD.mp4")},
    lambda *_: None, "演员甲", "导演乙",
    on_select=None, on_play=lambda m: None, on_fav=lambda m: None)
card.show()
app.processEvents()
card_big = render_scaled(card, 1)
card_panel = captioned(
    "海报卡 · 两角按钮",
    "左下角 = 收藏星标；右下角 = 圆形播放按钮（同一水平线、不重叠、真控件不穿透）",
    card_big)
card_panel.save(os.path.join(OUT, "03_card_corners.png"))
print("03_card_corners.png")

# ---------- 04 总览 ----------
W = max(play_panel.width(), star_panel.width(), card_panel.width())
parts = [play_panel, star_panel, card_panel]
H = sum(p.height() for p in parts) + 20
over = QPixmap(W, H)
over.fill(QColor(24, 21, 19))
p = QPainter(over)
y = 10
for part in parts:
    p.drawPixmap((W - part.width()) // 2, y, part)
    y += part.height() + 5
p.end()
over.save(os.path.join(OUT, "04_overview.png"))
print("04_overview.png")

print("DONE ->", OUT)
