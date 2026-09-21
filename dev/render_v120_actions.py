# -*- coding: utf-8 -*-
"""v1.20.0 离屏渲染：详情页操作按钮在「明亮剧照」上的可见度对比 + 新增「刷新」按钮。

注意命名：`dev/render_v120.py` 是 v1.12.0 时代的旧脚本，这里用 `_actions` 后缀区分。

产物（dev/screenshots_v120_actions/）：
  01_before_ghost.png   —— 旧样式（#Ghost）：收藏/评分/更多 在亮剧照上几乎看不见（融入背景）
  02_after_heroact.png  —— 新样式（#HeroAct）：深底 + 鎏金描边，清晰可辨（含新增「刷新」）
  03_full_wide.png      —— 宽面板整页
  04_narrow_430.png     —— 窄面板（按钮随流式布局换行）
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC = r"Z:\【01】自研软件\【26-19】本地影视中心\src"
sys.path.insert(0, SRC)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dev", "screenshots_v120_actions")
TMP = os.path.join(os.environ.get("TEMP", "."), "lmc_v120_render")
os.makedirs(TMP, exist_ok=True)

import database as db
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
db.init_db()

from PySide6.QtGui import (QFontDatabase, QFont, QPixmap, QColor, QPainter,
                           QLinearGradient)
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QPushButton

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

from ui_hero import HeroView


# ---------- 造一张「明亮杂乱」的剧照，模拟用户截图里的亮底 ----------
def make_bright_fanart(path, w=1600, h=720):
    pm = QPixmap(w, h)
    p = QPainter(pm)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0.0, QColor(255, 219, 238))
    g.setColorAt(0.5, QColor(243, 165, 205))
    g.setColorAt(1.0, QColor(252, 240, 248))
    p.fillRect(0, 0, w, h, g)
    blocks = [(60, 40, 220, 160), (330, 30, 180, 120), (560, 60, 260, 200),
              (880, 20, 200, 150), (1150, 50, 300, 180), (200, 380, 240, 150),
              (620, 400, 280, 170), (980, 420, 320, 160), (1420, 220, 150, 220)]
    for i, (x, y, bw, bh) in enumerate(blocks):
        p.fillRect(x, y, bw, bh, QColor(255, 255, 255, 90 if i % 2 else 60))
    p.end()
    pm.save(path)
    return path


FANART = make_bright_fanart(os.path.join(TMP, "fanart_bright.jpg"))

MEDIA = {
    "id": None,
    "title": "OLM-355 【FANZA限定】もうノーマルなセックスじゃ満足できない！",
    "kind": "movie", "year": 2026, "country": "OLM", "rating": 4.3, "user_rating": 8.5,
    "genres": "剧情,恋爱,美少女,写真", "runtime": "02:02:00", "certification": "JP-18+",
    "quality": "4K", "plot": "明亮剧照底下的按钮可见度测试。" * 6,
    "file_path": r"Z:\【30】VR视频\OLM-355\OLM-355-8K.mp4",
    "file_size": 6 * 1024 ** 3, "added_date": "2026-09-17",
    "studio": "オリンポス", "library": "Jav-library",
    "collection": "佐藤愛璃", "tmdb_id": None,
    "fanart": FANART, "poster": None, "parent_id": None,
    "nfo_path": None, "play_count": 0, "favorite": 0,
}

os.makedirs(OUT, exist_ok=True)
ACT_TEXTS = ("收藏", "已收藏", "刷新", "更多")


def action_btns(hero):
    out = []
    for b in hero.findChildren(QPushButton):
        t = b.text()
        if t in ACT_TEXTS or t.startswith("评分"):
            out.append(b)
    return out


def restyle(hero, objname):
    for b in action_btns(hero):
        b.setObjectName(objname)
        b.style().unpolish(b)
        b.style().polish(b)
    app.processEvents()


def build(w, h):
    hero = HeroView(MEDIA, on_open_actor=None, on_back=None)
    hero.resize(w, h)
    hero.show()
    app.processEvents()
    return hero


def band(hero, scale=2.0, pad_top=14, pad_bottom=34):
    """截取「操作按钮行」所在横条并放大，便于肉眼查看按钮与亮底的对比。"""
    content = hero.widget()
    cw, ch = content.width(), content.height()
    pm = QPixmap(cw, ch)
    pm.fill(QColor("#0f0d0c"))
    content.render(pm)
    prim = [b for b in hero.findChildren(QPushButton) if b.objectName() == "Primary"]
    y = prim[0].mapTo(content, QPoint(0, 0)).y() if prim else 0
    y0 = max(0, y - pad_top)
    y1 = min(ch, y + pad_bottom)
    crop = pm.copy(0, y0, cw, max(1, y1 - y0))
    return crop.scaled(int(crop.width() * scale), int(crop.height() * scale),
                       Qt.KeepAspectRatio, Qt.SmoothTransformation)


W, H = 1200, 950

h1 = build(W, H)
restyle(h1, "Ghost")
band(h1).save(os.path.join(OUT, "01_before_ghost.png"))
print("01_before_ghost.png 保存")

h2 = build(W, H)
restyle(h2, "HeroAct")
band(h2).save(os.path.join(OUT, "02_after_heroact.png"))
print("02_after_heroact.png 保存")

pm = QPixmap(W, H)
pm.fill(QColor("#0f0d0c"))
h2.render(pm)
pm.save(os.path.join(OUT, "03_full_wide.png"))
print("03_full_wide.png 保存")

h3 = build(430, 950)
restyle(h3, "HeroAct")
pm = QPixmap(430, 950)
pm.fill(QColor("#0f0d0c"))
h3.render(pm)
pm.save(os.path.join(OUT, "04_narrow_430.png"))
print(f"04_narrow_430.png 保存  横向滚动条最大={h3.horizontalScrollBar().maximum()} "
      f"操作按钮数={len(action_btns(h3))}")
print("DONE ->", OUT)
