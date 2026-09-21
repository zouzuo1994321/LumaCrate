# -*- coding: utf-8 -*-
"""诊断探针：离屏构建 MainWindow，渲染「全部」影片墙，统计真实卡片控件与亮像素。

目的：判定真机 exe 里「卡片墙空白」到底是代码问题，还是截图/时序问题。
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_BACKDROP"] = "1"

SRC = r"Z:\【01】自研软件\【26-19】本地影视中心\src"
sys.path.insert(0, SRC)
TMP = tempfile.mkdtemp(prefix="lmc_v121_wall_")

import config as cfg
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
import database as db
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
import applog
applog.log_dir = lambda: os.path.join(TMP, "logs")
db.init_db()

from PySide6.QtGui import QFontDatabase, QFont, QPixmap, QColor
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
FONT = r"C:\Windows\Fonts\msyh.ttc"
if os.path.exists(FONT):
    QFontDatabase.addApplicationFont(FONT)
    app.setFont(QFont("Microsoft YaHei", 9))

import main_window as mw
mw.load_style(app)


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x00" * 16)


for i in range(24):
    p = os.path.join(TMP, "lib", f"M{i:02d}.mp4")
    touch(p)
    db.upsert_media_by_path(mode="overwrite", kind="movie", title=f"片子{i:02d}",
                            file_path=p, library="TestLib")

print("[seed] media =", db.count_media())

w = mw.MainWindow()
w.resize(1400, 900)
w.show()
pump(800)
print("[boot] 首页类型 =", type(w._view_home()).__name__)

# ---- 「全部」影片墙 ----
page = w._wall_page("全部")
page.resize(1200, 800)
page.show()
pump(1500)

cards = page.findChildren(mw.PosterCard)
print("[wall] PosterCard 控件数 =", len(cards))
grids = page.findChildren(mw.LazyGrid)
for g in grids:
    print(f"[wall] LazyGrid loaded={g._loaded} total={g._total} "
          f"body_children={g._body.layout().count() if g._body.layout() else -1} "
          f"head_visible={g.head.isVisible()} err={g._error!r}")

pm = QPixmap(1200, 800)
pm.fill(QColor(10, 10, 10))
page.render(pm, QPoint(0, 0))
img = pm.toImage()
bright = 0
for y in range(0, 800, 2):
    for x in range(0, 1200, 2):
        c = img.pixelColor(x, y)
        if c.red() > 90 or c.green() > 90 or c.blue() > 90:
            bright += 1
print(f"[render] 亮像素 = {bright} / {600*400}")
out = os.path.join(TMP, "wall_render.png")
pm.save(out)
print("[render] saved", out)

# ---- 「最近播放」小列表 ----
page2 = w._grid(db.recent(24))
page2.resize(1200, 800)
page2.show()
pump(1200)
print("[recent] PosterCard 控件数 =", len(page2.findChildren(mw.PosterCard)))
print("DONE")
