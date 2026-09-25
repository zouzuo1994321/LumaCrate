# -*- coding: utf-8 -*-
"""v1.30.0 定向出图 —— 演员卡作品数 / 两库 A-Z 索引 / 两个新工具页

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1300.py', run_name='__main__')"

产物：dev/screenshots_v1300/
安全：db / config / 日志全部指向临时目录，不动真实索引与真实配置。

出图清单：
  00 演员卡放大 3x（看「作品 N 部」）
  01 演员卡 vs 导演卡 并排
  02 演员库整窗（右侧 A-Z 索引条）
  03 演员库右半放大（看清索引条紧贴滚动条）
  04 导演库整窗（右侧 A-Z 索引条）
  05 工具 → 手动修改
  06 工具 → 图像检测
  07 工具导航列（顺序：个性化 / 手动修改 / 画像概览 … 重复检测 / 图像检测 / 数据与日志）
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

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1300")
INDEX = os.path.join(TMP, "index_data")
OUT = os.path.join(ROOT, "dev", "screenshots_v1300")
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

    # 姓名 + 罗马音 → 让 A-Z 索引条每个字母都有人
    ACTORS = [
        ("深田えいみ", "Fukada Eimi", 96), ("三上悠亜", "Mikami Yua", 88),
        ("橋本ありな", "Hashimoto Arina", 74), ("葵つかさ", "Aoi Tsukasa", 69),
        ("高橋しょう子", "Takahashi Shoko", 63), ("紬美羽", "Tsumugi Miwa", 58),
        ("咲野のぞみ", "Sakino Nozomi", 52), ("星野ナミ", "Hoshino Nami", 47),
        ("白石茉莉奈", "Shiraishi Marina", 43), ("相沢みなみ", "Aizawa Minami", 39),
        ("桃乃木かな", "Momonoiki Kana", 35), ("桜空もも", "Ozora Momo", 31),
        ("吉沢明歩", "Yoshizawa Akiho", 28), ("大槻ひびき", "Otsuki Hibiki", 25),
        ("初川みなみ", "Hatsukawa Minami", 22), ("天使もえ", "Tenshi Moe", 19),
        ("里美ゆりあ", "Satomi Yuria", 17), ("君島みお", "Kimijima Mio", 15),
        ("加藤ももか", "Kato Momoka", 13), ("波多野結衣", "Hatano Yui", 11),
        ("Karen", "Karen", 9), ("Zara", "Zara", 7), ("Ume Chan", "Ume", 5),
        ("Xena Blue", "Xena", 4), ("仮名屋千代", "", 6)]
    DIRECTORS = [
        ("肉尊", "Nikuzon", 498), ("シネマジック", "Kinema Shikku", 512),
        ("溜池ゴロー", "Quentin Tarantino", 386), ("大橋ケン", "Ohashi Ken", 274),
        ("三島六三郎", "Mishima Musaburo", 231), ("辻本龍", "Ryu", 198),
        ("氷室涼介", "Wilson Gray", 165), ("安藤光一", "Yuzu Aoi", 143),
        ("佐藤健二", "Sakura Jun", 121), ("森田芳光", "Zen Momo", 98),
        ("中村誠", "Edo Ginji", 76), ("山口修", "Ume Toshi", 61),
        ("早瀬亮", "Xavier Ryo", 44), ("井上大輔", "Vega Daisuke", 33)]

    links = []
    a_ids, d_ids = [], []
    for name, romaji, cnt in ACTORS:
        pid = db.upsert_person(name, role_type="Actor")
        a_ids.append(pid)
        db.update_person(pid, romaji=romaji, status="现役")
        links += [(k + 1, pid, "Actor", 0) for k in range(min(cnt, N_M))]
    for name, romaji, cnt in DIRECTORS:
        pid = db.upsert_person(name, role_type="Director")
        d_ids.append(pid)
        db.update_person(pid, romaji=romaji, status="现役")
        links += [(k + 1, pid, "Director", 0) for k in range(min(cnt, N_M))]
    _c.executemany(
        "INSERT OR IGNORE INTO media_people (media_id,person_id,char_role,person_order)"
        " VALUES (?,?,?,?)", links)
    _c.commit()
finally:
    _c.close()

db.toggle_person_favorite(a_ids[0])
db.toggle_person_pinned(a_ids[1])
print("   演员 %d 位 / 导演 %d 位 / 关联 %d 条"
      % (len(a_ids), len(d_ids), len(links)))

# ============================================================ 单卡
print("\n== 出图 ==")
p_act = {"name": "深田えいみ", "thumb": None, "photo_path": None, "status": "现役",
         "works": 96, "alias": "", "favorite": 1, "pinned": 0,
         "meta": '{"出身地": "东京都", "身高": "158cm", "尺寸": "T153/B85/W58/H83"}',
         "birthday": "1998-08-16", "bio": ""}
p_dir = {"name": "肉尊", "thumb": None, "photo_path": None, "status": "现役",
         "works": 498, "alias": "肉ズン", "favorite": 0, "pinned": 0,
         "meta": "", "birthday": "", "bio": ""}

_ac = mw.ActorCard(p_act, on_open=lambda *_a: None, on_fav=lambda *_a: None,
                   on_pin=lambda *_a: None, on_select=lambda *_a: None, main_win=None)
_ac.show()
pump(6)
save(_ac.grab(), "00_actor_card_works_3x.png", 3.0, bg=WALL_BG)

_dc = mw.DirectorCard(p_dir, on_open=lambda *_a: None, on_fav=lambda *_a: None,
                      on_pin=lambda *_a: None, on_select=lambda *_a: None, main_win=None)
_dc.show()
pump(6)
save(_dc.grab(), "01b_director_card_3x.png", 3.0, bg=WALL_BG)

a2 = _flat(os.path.join(OUT, "00_actor_card_works_3x.png"), WALL_BG)
b = _flat(os.path.join(OUT, "01b_director_card_3x.png"), WALL_BG)
gap, pad, head = 24, 16, 34
cmp_im = Image.new("RGB", (pad * 2 + a2.width + gap + b.width,
                           head + max(a2.height, b.height) + pad), (24, 21, 19))
d = ImageDraw.Draw(cmp_im)
f = font(20)
d.text((pad, 8), "演员卡 236x160 — 第 5 项由「胸围」换成「作品 96 部」",
       font=f, fill=(201, 189, 167))
d.text((pad + a2.width + gap, 8), "导演卡 236x118（作品 / 别名，未改动）",
       font=f, fill=(201, 189, 167))
cmp_im.paste(a2, (pad, head))
cmp_im.paste(b, (pad + a2.width + gap, head))
cmp_im.save(os.path.join(OUT, "01_cards_side_by_side.png"))
print("  %-38s %dx%d" % ("01_cards_side_by_side.png", cmp_im.width, cmp_im.height))
_ac.close()
_dc.close()
pump(4)

# ============================================================ 两库整窗
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(14)
win.stat_label.setText("电影 520 · 剧集 0\n分集 0 · 演员 %d · 导演 %d"
                       % (len(a_ids), len(d_ids)))
pump(4)

for _tag, _builder, _name, _zoom in (("演员库", win._view_actors,
                                      "02_actor_library_az.png",
                                      "03_actor_library_az_zoom.png"),
                                     ("导演库", win._view_directors,
                                      "04_director_library_az.png", None)):
    pg = _builder()
    win.stack.addWidget(pg)
    win.stack.setCurrentWidget(pg)
    pump(50)
    save(win.grab(), _name, bg=None)
    bar = pg.findChild(__import__("letter_index", fromlist=["LetterIndexBar"]).LetterIndexBar)
    g = pg.findChild(mw.LazyGrid)
    print("     %s：索引条=%s  字母数=%s  已建卡=%s"
          % (_tag, "有" if bar is not None else "无",
             len(bar.index()) if bar is not None else 0,
             g._loaded if g is not None else 0))
    if _zoom and bar is not None:
        # 右半屏放大：看清索引条与滚动条的位置关系
        full = _flat(os.path.join(OUT, _name), None)
        crop = full.crop((full.width // 2, 60, full.width, 880))
        crop = crop.resize((int(crop.width * 1.25), int(crop.height * 1.25)), Image.LANCZOS)
        crop.save(os.path.join(OUT, _zoom))
        print("  %-38s %dx%d" % (_zoom, crop.width, crop.height))
    win.stack.removeWidget(pg)
    pg.deleteLater()
    pump(6)

win.close()
pump(6)

# ============================================================ 工具窗口两个新页
import ui_settings

dlg = ui_settings.SettingsDialog()
dlg.resize(1180, 900)
pump(10)
for _key, _name in (("手动修改", "05_tools_manual_edit.png"),
                    ("图像检测", "06_tools_image_detect.png")):
    dlg._show(_key)
    pump(20)
    pg = dlg.stack.currentWidget()
    if pg is not None and _key == "手动修改":
        w = pg.widget()
        if w.list.count():
            w.list.setCurrentRow(0)
            pump(12)
    save(dlg.grab(), _name, bg=None)
    print("     %s 已切：nav=%d 项" % (_key, len(dlg.ORDER)))

# 导航列单独抓一张（看两页插的位置）
nav_frame = dlg.findChild(__import__("PySide6.QtWidgets", fromlist=["QFrame"]).QFrame, "Sidebar")
if nav_frame is not None:
    save(nav_frame.grab(), "07_tools_nav_order.png", 1.6, bg=(28, 24, 21))
dlg.close()
pump(6)

print("\n输出目录：", OUT)
print("版本：%s (Build %s)" % (ver.VERSION, ver.BUILD))
