# -*- coding: utf-8 -*-
"""v1.28.1 定向出图 —— 导演卡去「简介」+ 压高 / 两库每行 6 个

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1281.py', run_name='__main__')"

产物：dev/screenshots_v1281/
安全：db / config / 日志全部指向临时目录，不动真实索引与真实配置。

出图清单：
  00 导演卡放大（3x）                  01 演员卡 vs 导演卡 并排对比（2x）
  02 导演库整窗（每行 6 个）            03 演员库整窗（每行 6 个）
  04 导演库前两行放大（数得清 6 列）    05 演员卡放大（2x）
  06 整窗（演员库）
"""
import io
import os
import sys
import time
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1281")
INDEX = os.path.join(TMP, "index_data")
OUT = os.path.join(ROOT, "dev", "screenshots_v1281")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(OUT, exist_ok=True)
for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    try:
        os.remove(_f)
    except OSError:
        pass

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"          # 出图不需要采集线程

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import version as ver

db.init_db()

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw

mw.load_style(app)

WALL_BG = (17, 15, 13)        # 暗色主题下的「墙」底色，透明底抓图要垫它


def pump(n=8):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


def _flat(src, bg):
    im = Image.open(src).convert("RGBA")
    if bg is not None:
        base = Image.new("RGBA", im.size, tuple(bg) + (255,))
        im = Image.alpha_composite(base, im)
    return im.convert("RGB")


def save(pm, name, scale=1.0, bg=None, crop=None):
    p = os.path.join(OUT, name)
    pm.save(p)
    im = _flat(p, bg)
    if crop:
        im = im.crop(crop)
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im.save(p)
    print("  %-38s %dx%d  %d B" % (name, im.width, im.height, os.path.getsize(p)))
    return p


def font(size):
    for f in ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


# ============================================================ 造数据（临时库）
print("== 造预览数据（临时库，不碰真实索引） ==")
N_M = 520
_c = db.get_conn()
try:
    _c.executemany(
        "INSERT INTO media (kind,title,sort_title,year,file_path) VALUES (?,?,?,?,?)",
        [("movie", "预览作品 %03d" % (i + 1), "预览作品 %03d" % (i + 1),
          2010 + (i % 16), "X:/__preview__/%03d.mp4" % (i + 1)) for i in range(N_M)])
    _c.commit()

    DIRECTORS = [("肉尊", 498, "肉ズン", "现役"), ("シネマジック", 512, "", "现役"),
                 ("溜池ゴロー", 386, "", "现役"), ("大橋ケン", 274, "", "现役"),
                 ("三島六三郎", 231, "", "退役"), ("辻本龍", 198, "", "现役"),
                 ("氷室涼介", 165, "", "现役"), ("安藤光一", 143, "", "未知"),
                 ("佐藤健二", 121, "", "现役"), ("森田芳光", 98, "", "退役"),
                 ("中村誠", 76, "", "现役"), ("山口修", 61, "", "现役"),
                 ("早瀬亮", 44, "", "未知"), ("井上大輔", 33, "", "现役")]
    ACTORS = [("深田えいみ", 96), ("三上悠亜", 88), ("橋本ありな", 74), ("葵つかさ", 69),
              ("高橋しょう子", 63), ("紬美羽", 58), ("咲野のぞみ", 52), ("星野ナミ", 47),
              ("白石茉莉奈", 43), ("相沢みなみ", 39), ("桃乃木かな", 35), ("桜空もも", 31),
              ("吉沢明歩", 28), ("大槻ひびき", 25), ("初川みなみ", 22), ("天使もえ", 19),
              ("里美ゆりあ", 17), ("君島みお", 15), ("加藤ももか", 13), ("波多野結衣", 11)]

    links = []
    d_ids = []
    for name, cnt, alias, status in DIRECTORS:
        pid = db.upsert_person(name, role_type="Director")
        d_ids.append(pid)
        db.update_person(pid, alias=alias, status=status)
        links += [(k + 1, pid, "Director", 0) for k in range(min(cnt, N_M))]
    a_ids = []
    for name, cnt in ACTORS:
        pid = db.upsert_person(name, role_type="Actor")
        a_ids.append(pid)
        links += [(k + 1, pid, "Actor", 0) for k in range(min(cnt, N_M))]
    _c.executemany(
        "INSERT OR IGNORE INTO media_people (media_id,person_id,char_role,person_order)"
        " VALUES (?,?,?,?)", links)
    _c.commit()
finally:
    _c.close()

db.toggle_person_favorite(d_ids[0])       # 导演「肉尊」收藏
db.toggle_person_pinned(d_ids[1])         # 导演「シネマジック」置顶
db.toggle_person_favorite(a_ids[0])       # 演员「深田えいみ」收藏
print("   导演 %d 位 / 演员 %d 位 / 关联 %d 条" % (len(d_ids), len(a_ids), len(links)))

# ============================================================ 单卡
print("\n== 出图 ==")
p_dir = {"name": "肉尊", "thumb": None, "photo_path": None, "status": "现役",
         "works": 498, "alias": "肉ズン", "favorite": 1, "pinned": 0,
         "meta": "", "birthday": "", "bio": "（导演 bio 在真机库里几乎全空 → 卡片不再为它留行）"}
p_act = {"name": "深田えいみ", "thumb": None, "photo_path": None, "status": "现役",
         "works": 96, "alias": "", "favorite": 0, "pinned": 0,
         "meta": "出身地:东京|身高:158|尺寸:B85 W58 H88",
         "birthday": "1998-08-16", "bio": ""}

_dc = mw.DirectorCard(p_dir, on_open=lambda *_a: None, on_fav=lambda *_a: None,
                     on_pin=lambda *_a: None, on_select=lambda *_a: None, main_win=None)
_dc.show()
pump(6)
save(_dc.grab(), "00_director_card_3x.png", 3.0, bg=WALL_BG)
print("     导演卡 %dx%d（原 236x160）" % (_dc.width(), _dc.height()))

_ac = mw.ActorCard(p_act, on_open=lambda *_a: None, on_fav=lambda *_a: None,
                   on_pin=lambda *_a: None, on_select=lambda *_a: None, main_win=None)
_ac.show()
pump(6)
save(_ac.grab(), "05_actor_card_2x.png", 2.0, bg=WALL_BG)

# 并排对比 + 文字标注
a2 = _flat(os.path.join(OUT, "05_actor_card_2x.png"), WALL_BG)
b = _flat(os.path.join(OUT, "00_director_card_3x.png"), WALL_BG)
gap, pad, head = 24, 16, 34
cmp_im = Image.new("RGB", (pad * 2 + a2.width + gap + b.width,
                           head + max(a2.height, b.height) + pad), (24, 21, 19))
d = ImageDraw.Draw(cmp_im)
f = font(20)
d.text((pad, 8), "演员卡 236x160（5 项信息）", font=f, fill=(201, 189, 167))
d.text((pad + a2.width + gap, 8), "导演卡 236x118（作品 / 别名，无简介）", font=f, fill=(201, 189, 167))
cmp_im.paste(a2, (pad, head))
cmp_im.paste(b, (pad + a2.width + gap, head))
cmp_im.save(os.path.join(OUT, "01_cards_actor_vs_director_2x.png"))
print("  %-38s %dx%d  %d B" % ("01_cards_actor_vs_director_2x.png", cmp_im.width, cmp_im.height,
                               os.path.getsize(os.path.join(OUT, "01_cards_actor_vs_director_2x.png"))))
_dc.close(); _ac.close()
pump(4)

# ============================================================ 两库整窗
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(14)
win.stat_label.setText("电影 520 · 剧集 0\n分集 0 · 演员 20 · 导演 14")
pump(4)

for _tag, _name, _shot in (("导演库", "02_director_library_6col.png", "04_director_grid_zoom.png"),
                           ("演员库", "03_actor_library_6col.png", None)):
    pg = win._view_directors() if _tag == "导演库" else win._view_actors()
    win.stack.addWidget(pg)
    win.stack.setCurrentWidget(pg)
    pump(40)
    g = pg.findChild(mw.LazyGrid)
    save(win.grab(), _name, bg=None)
    if g is not None:
        rows = 0
        for i in range(g._grid.count()):
            r, _cc, _rs, _cs = g._grid.getItemPosition(i)
            rows = max(rows, r)
        r0 = sum(1 for i in range(g._grid.count())
                 if g._grid.getItemPosition(i)[0] == 0)
        print("     %s：列数 %d · 第 0 行 %d 张 · 总卡 %d" % (_tag, g._cols, r0, g._grid.count()))
        if _shot:
            body = g._body.grab()
            h = 2 * mw.DIRECTOR_CARD_H + 12
            save(body, _shot, 1.45, bg=WALL_BG, crop=(0, 0, body.width(), min(h, body.height())))
    win.stack.removeWidget(pg)
    pg.deleteLater()
    pump(6)

save(win.grab(), "06_window_1600.png", bg=None)
win.close()
pump(6)
print("\n输出目录：", OUT)
