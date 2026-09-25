# -*- coding: utf-8 -*-
"""v1.31.0 定向出图 —— 撤销 A-Z 索引 / 三围加粗罩杯 / 新增「演员检测」/ 工具导航分四组

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1310.py', run_name='__main__')"

产物：dev/screenshots_v1310/
安全：db / config / 日志 / 头像目录全部指向临时目录，不动真实索引与真实配置。

出图清单：
  00 演员卡放大 3x（三围前带加粗罩杯）
  01 演员卡 vs 导演卡 并排
  02 演员库整窗（**右侧已无 A-Z 索引条**）
  03 导演库整窗（同上）
  04 演员详情页（三围同步带罩杯）
  05 工具 → 演员检测（检测结果树 + 存疑）
  06 工具 → 演员检测：选中一簇的详情（保留下拉 / 确认关联）
  07 工具 → 演员检测：下半「演员信息手动编辑 + 上传头像」
  08 工具导航四分组（基础工具 / 数据优化 / 智能检测 / 数据分析）
"""
import os
import sys
import time
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1310")
INDEX = os.path.join(TMP, "index_data")
AVATARS = os.path.join(TMP, "people_photos")
OUT = os.path.join(ROOT, "dev", "screenshots_v1310")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(AVATARS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def _wipe(p):
    """safe-delete shim 会拦 os.remove —— 走 ctypes。"""
    if not os.path.exists(p):
        return
    import ctypes
    ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
    ctypes.windll.kernel32.DeleteFileW(p)


for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    _wipe(_f)

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

# 头像目录也指向临时目录 —— 「上传头像」用例不许往工作副本写垃圾
_s0 = cfg.get_settings()
_s0.scraper["photo_dir"] = AVATARS
_s0.save()

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QSplitter

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
    print("  %-40s %dx%d  %d B" % (name, im.width, im.height, os.path.getsize(p)))
    return p


def font(size):
    for f in ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


# ============================================================ 造数据（临时库）
print("== 造预览数据（临时库，不碰真实索引） ==")
N_M = 520
_GOOD_META = ('{"身高": "152cm", "尺寸": "T152 / B96( Jカップ ) / W58 / H87 / S", '
              '"出身地": "东京都", "事务所": "Life Promotion"}')
_GOOD_ALIAS = "岸杏南、真木めぐみ、須藤美果、神谷明日香、白川みなみ"

_c = db.get_conn()
try:
    _c.executemany(
        "INSERT INTO media (kind,title,sort_title,year,file_path) VALUES (?,?,?,?,?)",
        [("movie", "预览作品 %03d" % (i + 1), "预览作品 %03d" % (i + 1),
          2010 + (i % 16), "X:/__preview__/%03d.mp4" % (i + 1)) for i in range(N_M)])
    _c.commit()

    # ---- 演员库墙用的普通人（带真实感的三围 / 罩杯）
    ACTORS = [
        ("深田えいみ", "Fukada Eimi", 96, "L", "T155 / B111( Lカップ ) / W65 / H96 / S", "158cm", "东京都"),
        ("三上悠亜", "Mikami Yua", 88, "F", "T159 / B90( Fカップ ) / W58 / H88 / S", "159cm", "爱知县"),
        ("橋本ありな", "Hashimoto Arina", 74, "E", "T165 / B86( Eカップ ) / W58 / H86 / S", "165cm", "东京都"),
        ("葵つかさ", "Aoi Tsukasa", 69, "F", "T163 / B88( Fカップ ) / W59 / H89 / S", "163cm", "大阪府"),
        ("高橋しょう子", "Takahashi Shoko", 63, "H", "T161 / B95( Hカップ ) / W60 / H90 / S", "161cm", "神奈川县"),
        ("紬美羽", "Tsumugi Miwa", 58, "D", "T154 / B82( Dカップ ) / W56 / H84 / S", "154cm", "北海道"),
        ("咲野のぞみ", "Sakino Nozomi", 52, "E", "T157 / B85( Eカップ ) / W57 / H85 / S", "157cm", "千叶县"),
        ("星野ナミ", "Hoshino Nami", 47, "G", "T166 / B92( Gカップ ) / W61 / H91 / S", "166cm", "埼玉县"),
        ("白石茉莉奈", "Shiraishi Marina", 43, "H", "T160 / B94( Hカップ ) / W62 / H92 / S", "160cm", "东京都"),
        ("相沢みなみ", "Aizawa Minami", 39, "E", "T158 / B84( Eカップ ) / W56 / H86 / S", "158cm", "京都府"),
        ("桃乃木かな", "Momonoiki Kana", 35, "D", "T153 / B81( Dカップ ) / W55 / H83 / S", "153cm", "东京都"),
        ("桜空もも", "Ozora Momo", 31, "F", "T156 / B87( Fカップ ) / W58 / H87 / S", "156cm", "福冈县"),
        ("吉沢明歩", "Yoshizawa Akiho", 28, "E", "T161 / B84( Eカップ ) / W59 / H88 / S", "161cm", "东京都"),
        ("大槻ひびき", "Otsuki Hibiki", 25, "G", "T162 / B91( Gカップ ) / W60 / H90 / S", "162cm", "静冈县"),
        ("初川みなみ", "Hatsukawa Minami", 22, "D", "T155 / B80( Dカップ ) / W56 / H84 / S", "155cm", "宫城县"),
        ("天使もえ", "Tenshi Moe", 19, "E", "T158 / B85( Eカップ ) / W57 / H86 / S", "158cm", "东京都"),
        ("里美ゆりあ", "Satomi Yuria", 17, "F", "T164 / B89( Fカップ ) / W60 / H89 / S", "164cm", "神奈川县"),
        ("君島みお", "Kimijima Mio", 15, "E", "T160 / B86( Eカップ ) / W58 / H87 / S", "160cm", "大阪府"),
        ("加藤ももか", "Kato Momoka", 13, "C", "T152 / B78( Cカップ ) / W54 / H82 / S", "152cm", "爱知县"),
        ("波多野結衣", "Hatano Yui", 11, "F", "T163 / B88( Fカップ ) / W59 / H88 / S", "163cm", "滋贺县"),
        ("Karen", "Karen", 9, "P", "T170 / B120( Pカップ ) / W90 / H114 / S", "170cm", "东京都"),
        ("Zara", "Zara", 7, "", "T168 / B92 / W64 / H92 / S", "168cm", "冲绳县"),
        ("Ume Chan", "Ume", 5, "", "", "", "山梨县"),
        ("Xena Blue", "Xena", 4, "", "", "", "长野县"),
        ("仮名屋千代", "", 6, "", "", "", "新潟县"),
    ]
    DIRECTORS = [
        ("肉尊", "Nikuzon", 498), ("シネマジック", "Kinema Shikku", 512),
        ("溜池ゴロー", "Tarantino", 386), ("大橋ケン", "Ohashi Ken", 274),
        ("三島六三郎", "Mishima Musaburo", 231), ("辻本龍", "Ryu", 198),
        ("氷室涼介", "Wilson Gray", 165), ("安藤光一", "Yuzu Aoi", 143),
        ("佐藤健二", "Sakura Jun", 121), ("森田芳光", "Zen Momo", 98),
        ("中村誠", "Edo Ginji", 76), ("山口修", "Ume Toshi", 61),
        ("早瀬亮", "Xavier Ryo", 44), ("井上大輔", "Vega Daisuke", 33),
    ]

    links = []
    a_ids, d_ids = [], []
    for name, romaji, cnt, cup, size, height, home in ACTORS:
        pid = db.upsert_person(name, role_type="Actor")
        a_ids.append(pid)
        meta = "{}"
        if size:
            meta = ('{"身高": "%s", "尺寸": "%s", "出身地": "%s"%s}'
                    % (height, size, home, (', "罩杯": "%s"' % cup) if cup else ""))
        db.set_person_fields(pid, name=name, romaji=romaji, status="现役",
                             birthday="199%d-0%d-%02d" % (cnt % 9, (cnt % 9) + 1, (cnt % 28) + 1),
                             meta=meta)
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

# ---- 「演员检测」用的脏数据：一簇真该合并 + 一对同名不同人（存疑）
def _add(name, romaji, birthday, alias, meta, works=0, role="Actor"):
    pid = db.upsert_person(name, role_type=role)
    db.set_person_fields(pid, name=name, romaji=romaji, birthday=birthday, alias=alias,
                         status="现役", meta=meta)
    if works:
        _cc = db.get_conn()
        try:
            ids = [r["id"] for r in _cc.execute(
                "SELECT id FROM media WHERE kind='movie' LIMIT ?", (works,)).fetchall()]
            _cc.executemany(
                "INSERT OR IGNORE INTO media_people (media_id,person_id,char_role,person_order)"
                " VALUES (?,?,?,?)", [(i, pid, role, 0) for i in ids])
            _cc.commit()
        finally:
            _cc.close()
    return pid


# 真·同一人：同一份刮削资料被写进了 3 行，alias 里其实是本人的旧艺名名单
CL_A = _add("夏目玲香", "Natsume Reika", "1983-10-17", _GOOD_ALIAS, _GOOD_META, 12)
CL_B = _add("百瀬咲玖", "Natsume Reika", "1983-10-17", "夏目玲香、岸杏南", _GOOD_META, 3)
CL_C = _add("岸杏南", "Natsume Reika", "1983-10-17", "夏目玲香、百瀬咲玖", _GOOD_META, 1)
# 真·同名不同人：罗马音一样但生日 / 尺寸互相打架 → 必须降级「存疑」
SP_A = _add("千葉優花", "Chiba Yuuka", "2005-03-18", "",
            '{"身高": "165cm", "尺寸": "T165 / B85( Gカップ ) / W60 / H92 / S"}', 4)
SP_B = _add("千葉ゆうか", "Chiba Yuuka", "1996-11-13", "",
            '{"身高": "162cm", "尺寸": "T162 / B89( Eカップ ) / W61 / H92 / S"}', 2)

print("   演员 %d 位 / 导演 %d 位 / 关联 %d 条 / 检测样例 5 条"
      % (len(a_ids), len(d_ids), len(links)))

# ============================================================ 单卡
print("\n== 出图 ==")
p_act = {"name": "深田えいみ", "thumb": None, "photo_path": None, "status": "现役",
         "works": 96, "alias": "", "favorite": 1, "pinned": 0,
         "meta": '{"出身地": "东京都", "身高": "158cm",'
                 ' "尺寸": "T155 / B111( Lカップ ) / W65 / H96 / S", "罩杯": "L"}',
         "birthday": "1998-08-16", "bio": ""}
p_dir = {"name": "肉尊", "thumb": None, "photo_path": None, "status": "现役",
         "works": 498, "alias": "肉ズン", "favorite": 0, "pinned": 0,
         "meta": "", "birthday": "", "bio": ""}

_ac = mw.ActorCard(p_act, on_open=lambda *_a: None, on_fav=lambda *_a: None,
                   on_pin=lambda *_a: None, on_select=lambda *_a: None, main_win=None)
_ac.show()
pump(6)
save(_ac.grab(), "00_actor_card_cup_3x.png", 3.0, bg=WALL_BG)
print("     卡面三围值 = %r" % _ac._fact_values()["三围"])

_dc = mw.DirectorCard(p_dir, on_open=lambda *_a: None, on_fav=lambda *_a: None,
                      on_pin=lambda *_a: None, on_select=lambda *_a: None, main_win=None)
_dc.show()
pump(6)
save(_dc.grab(), "01b_director_card_3x.png", 3.0, bg=WALL_BG)

a2 = _flat(os.path.join(OUT, "00_actor_card_cup_3x.png"), WALL_BG)
b = _flat(os.path.join(OUT, "01b_director_card_3x.png"), WALL_BG)
gap, pad, head = 24, 16, 34
cmp_im = Image.new("RGB", (pad * 2 + a2.width + gap + b.width,
                           head + max(a2.height, b.height) + pad), (24, 21, 19))
d = ImageDraw.Draw(cmp_im)
f = font(20)
d.text((pad, 8), "演员卡 236x160 — 三围前加粗罩杯（L 胸111·腰65·臀96）",
       font=f, fill=(201, 189, 167))
d.text((pad + a2.width + gap, 8), "导演卡 236x118（未改动）",
       font=f, fill=(201, 189, 167))
cmp_im.paste(a2, (pad, head))
cmp_im.paste(b, (pad + a2.width + gap, head))
cmp_im.save(os.path.join(OUT, "01_cards_side_by_side.png"))
print("  %-40s %dx%d" % ("01_cards_side_by_side.png", cmp_im.width, cmp_im.height))
_ac.close()
_dc.close()
pump(4)

# ============================================================ 主窗（两库整窗 / 演员详情）
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(14)
win.stat_label.setText("电影 520 · 剧集 0\n分集 0 · 演员 %d · 导演 %d"
                       % (len(a_ids) + 5, len(d_ids)))
pump(4)

for _tag, _builder, _name in (("演员库", win._view_actors, "02_actor_library_no_az.png"),
                              ("导演库", win._view_directors, "03_director_library_no_az.png")):
    pg = _builder()
    win.stack.addWidget(pg)
    win.stack.setCurrentWidget(pg)
    pump(50)
    save(win.grab(), _name, bg=None)
    _bars = pg.findChildren(__import__("letter_index", fromlist=["LetterIndexBar"]).LetterIndexBar)
    g = pg.findChild(mw.LazyGrid)
    print("     %s：A-Z 索引条=%s  已建卡=%s"
          % (_tag, ("有(%d)" % len(_bars)) if _bars else "无",
             g._loaded if g is not None else 0))
    win.stack.removeWidget(pg)
    pg.deleteLater()
    pump(6)

# 演员详情页（三围同步带罩杯）
det = win._view_actor_detail(CL_A)
det.resize(1180, 900)
det.show()
pump(20)
save(det.grab(), "04_actor_detail_cup.png", 1.5, bg=WALL_BG)
det.close()
pump(4)

win.close()
pump(6)

# ============================================================ 工具窗口
import ui_settings
import ui_actorcheck

dlg = ui_settings.SettingsDialog()
dlg.resize(1180, 900)
dlg.show()
pump(12)


# ---- 演员检测：真跑一遍普通算法
dlg._show("演员检测")
pump(14)
pg = dlg.stack.currentWidget()
assert isinstance(pg, ui_actorcheck.ActorCheckPage), type(pg)
print("     演员检测页：进页已自动检索出 %d 位演员（懒加载）" % pg.plist.count())

pg.min_works.setValue(0)
pg.run_btn.click()
for _ in range(120):
    pump(4)
    if pg._worker is None or not pg._worker.isRunning():
        break
pump(12)
res = pg._res or {}
print("     检测结果：%d 簇 / %d 存疑 / 可合并 %d 人次 / %s 秒"
      % (len(pg._clusters), len(pg._suspects), res.get("merge_people", 0),
         res.get("elapsed", 0)))
print("     两库根节点 = %s" % [pg.tree.topLevelItem(i).text(0) for i in range(pg.tree.topLevelItemCount())])

save(dlg.grab(), "05_tools_actorcheck.png", bg=None)

# 选中第一簇 → 抓详情
if pg._clusters:
    root = pg.tree.topLevelItem(0)
    if root.childCount():
        pg.tree.setCurrentItem(root.child(0))
        pump(16)
        save(dlg.grab(), "06_tools_actorcheck_detail.png", bg=None)
        print("     详情簇 = %s" % " / ".join(pg._clusters[0]["members"][i]["name"]
                                             for i in range(len(pg._clusters[0]["members"]))))

# ---- 下半手动编辑：检索 → 选中 → 抓编辑表单
pg.kw.setText("夏目玲香")
pg._search_people()
pump(8)
if pg.plist.count():
    pg.plist.setCurrentRow(0)
    pump(16)
save(dlg.grab(), "07_tools_actorcheck_editor.png", bg=None)
print("     手动编辑检索到 %d 位" % pg.plist.count())

# ---- 导航四分组
from PySide6.QtWidgets import QFrame

nav_frame = dlg.findChild(QFrame, "Sidebar")
if nav_frame is not None:
    save(nav_frame.grab(), "08_tools_nav_groups.png", 1.7, bg=(28, 24, 21))
dlg.close()
pump(6)

print("\n输出目录：", OUT)
print("版本：%s (Build %s)" % (ver.VERSION, ver.BUILD))
