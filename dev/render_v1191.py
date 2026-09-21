# -*- coding: utf-8 -*-
"""v1.19.1 离屏渲染：详情面板在「窄 / 宽」两种宽度下的效果（反馈 1/2）。

产物：dev/screenshots_v1191/01_narrow_430.png、02_wide_1200.png
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC = r"Z:\【01】自研软件\【26-19】本地影视中心\src"
sys.path.insert(0, SRC)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dev", "screenshots_v1191")

TMP = tempfile.mkdtemp(prefix="lmc_v1191r_")
import database as db
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
db.init_db()

from PySide6.QtGui import QFontDatabase, QFont, QPixmap, QColor
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
    print("style 加载跳过:", e)

from ui_hero import HeroView

MEDIA = {
    "id": None, "title": "MXGS-1446 【FANZA限定】オフィス相部屋 NTR ～絶対にヤりたくないのに新人と二人きり～",
    "kind": "movie", "year": 2026, "country": "JP", "rating": 4.6, "user_rating": 8.0,
    "genres": "剧情,爱情,职场", "runtime": "02:11:00", "certification": "R-18",
    "quality": "4K,HDR10,Atmos,1080P", "plot": "日韩限定作品，办公室同居题材。" * 8,
    "file_path": r"Z:\【30】VR视频\MXGS-1446【FANZA限定】オフィス相部屋NTR\MXGS-1446-4K-cd1.mp4",
    "file_size": 8 * 1024 ** 3, "added_date": "2026-09-17",
    "studio": "SOD Create-很长的制作公司名称测试", "library": "Jav-library",
    "collection": "NTR系列", "tmdb_id": None, "fanart": None, "poster": None, "parent_id": None,
}

os.makedirs(OUT, exist_ok=True)


def shot(w, h, name):
    hero = HeroView(MEDIA, on_open_actor=None, on_back=None)
    hero.resize(w, h)
    hero.show()
    app.processEvents()
    pm = QPixmap(w, h)
    pm.fill(QColor("#0f0d0c"))
    hero.render(pm)
    path = os.path.join(OUT, name)
    pm.save(path)
    hs = hero.horizontalScrollBar().maximum()
    print(f"{name}: {w}x{h} 横向滚动条最大={hs} 内容最小宽={hero.widget().minimumSizeHint().width()}")
    hero.deleteLater()


shot(430, 900, "01_narrow_430.png")
shot(1200, 900, "02_wide_1200.png")
print("DONE ->", OUT)
