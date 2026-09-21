# -*- coding: utf-8 -*-
"""v1.11.0 卡片渲染自检：用**真实索引库的副本**离屏渲染，肉眼校验卡片是否还异常。

注意：绝不碰真实库 —— 先把 index_data/media_center.db 复制到临时目录再指向它。
"""
import os
import sys
import shutil
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, _HERE)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import config as cfg

OUT = os.path.join(_HERE, "screenshots")
os.makedirs(OUT, exist_ok=True)

tmp = tempfile.mkdtemp(prefix="lmc_render11_")
os.makedirs(os.path.join(tmp, "index_data"), exist_ok=True)
REAL = os.path.join(ROOT, "index_data", "media_center.db")
print("真实库:", REAL, os.path.exists(REAL))
if os.path.exists(REAL):
    shutil.copy2(REAL, os.path.join(tmp, "index_data", "media_center.db"))
db.db_path = lambda: os.path.join(tmp, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(tmp, "settings.json")
cfg._SETTINGS = None

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase

app = QApplication.instance() or QApplication([])

# 离屏默认没有中文字形（截图里全是方块）；显式加载系统字体让文字可读
for fp in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhl.ttc",
           "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"):
    if not os.path.exists(fp):
        continue
    fid = QFontDatabase.addApplicationFont(fp)
    fams = QFontDatabase.applicationFontFamilies(fid)
    print("载入字体", fp, fams)
    if fams:
        app.setFont(QFont(fams[0], 10))
        break

import main_window as mw
mw.load_style(app, cfg.get_settings().appearance)

w = mw.MainWindow()
w.resize(1900, 1060)
w.show()
for _ in range(6):
    app.processEvents()


def shot(name):
    for _ in range(6):
        app.processEvents()
    p = os.path.join(OUT, name)
    ok = w.grab().save(p)
    print("saved", name, ok, os.path.getsize(p) if os.path.exists(p) else -1)


# 1) 演员库（本次问题最集中的页面）
w.go(w._view_actors)
shot("12_actors_v111.png")

# 2) 影片网格（全部）
people = db.all_people_ordered("Actor")
print("演员数:", len(people))
print("有 status 的:", sum(1 for p in people if (p.get("status") or "").strip()))
print("有 meta 的:", sum(1 for p in people if (p.get("meta") or "").strip()))
print("有 last_year 的:", sum(1 for p in people if p.get("last_year")))
cr = db.cast_crew_map()
print("cast_crew_map 条目:", len(cr))
dirs = [v["directors"] for v in cr.values() if v.get("directors")]
print("有导演的影片数:", len(dirs), dirs[:3])

w.go(w._view_recent)
shot("13_grid_v111.png")

# 3) 演员详情页
if people:
    w.go(lambda: w._view_actor_detail(people[0]["id"]))
    shot("14_actor_detail_v111.png")

# 4) 单个演员卡特写（放大看 ☆/▲ 与六项信息）
from main_window import ActorCard, ACTOR_CARD_W, ACTOR_CARD_H
p0 = db.get_person(people[0]["id"]) if people else {"name": "测试", "id": 0}
ac = ActorCard(p0, on_open=lambda p: None, on_fav=lambda p: None,
               on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
ac.resize(ACTOR_CARD_W, ACTOR_CARD_H)
ac.show()
for _ in range(4):
    app.processEvents()
img = ac.grab()
img.scaled(ACTOR_CARD_W * 3, ACTOR_CARD_H * 3).save(os.path.join(OUT, "15_actor_card_zoom.png"))
print("saved 15_actor_card_zoom.png", img.size())

# 5) 单个影片卡特写（优先挑「有导演」的，验证小字两行都出得来）
withdir = [mid for mid, v in cr.items() if v.get("directors")]
pick = withdir[0] if withdir else (db.search_media(limit=1)[0]["id"] if db.search_media(limit=1) else None)
for idx, mid2 in enumerate([pick] + [m["id"] for m in db.search_media(limit=3)]):
    m = db.get_media(mid2)
    if not m:
        continue
    c = cr.get(m["id"], {})
    pc = mw.PosterCard(m, lambda x: None, c.get("actors", ""), c.get("directors", ""))
    pc.show()
    for _ in range(4):
        app.processEvents()
    pi = pc.grab()
    name = "16_poster_card_zoom.png" if idx == 0 else "17_poster_card_%d.png" % idx
    pi.scaled(pc.width() * 3, pc.height() * 3).save(os.path.join(OUT, name))
    print("saved", name, pi.size(), "| crew:", repr(pc._facts.text()),
          "| title:", repr(pc.findChildren(type(pc._facts))[1].text()))
    pc.close()

shutil.rmtree(tmp, ignore_errors=True)
print("DONE")
