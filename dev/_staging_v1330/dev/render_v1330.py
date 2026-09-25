# -*- coding: utf-8 -*-
"""v1.33.0 四条反馈的效果图（离屏）。

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1330.py', run_name='__main__')"

产物 → dev/screenshots_v1330/
    01_actors.png          演员库（白条已消失）
    02_directors.png       导演库
    03_recent.png          最近播放
    04_collections.png     合集
    05_about_contacts.png  「关于」联系图标（裁剪放大）
    06_dedupe_export.png   重复检测页的两枚新按钮
    07_tagopt_export.png   标签优化页的两枚新按钮
    08_whitebar_compare.png 修前/修后对照（修前用同尺寸合成示意槽位）

安全：db / config / 日志全指向临时目录，绝不碰真实索引。
"""
import os
import sys
import time
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(ROOT, "dev"))

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1330")
INDEX = os.path.join(TMP, "index_data")
AVATARS = os.path.join(TMP, "people_photos")
OUT = os.path.join(ROOT, "dev", "screenshots_v1330")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(AVATARS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def _wipe(p):
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
os.environ["LMC_NO_SYSMON"] = "1"

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
_s0 = cfg.get_settings()
_s0.scraper["photo_dir"] = AVATARS
_s0.save()

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QFrame

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw

mw.load_style(app)

import shots_lib as SL

WALL_BG = (17, 15, 13)
MADE = []


def pump(n=8):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


def save(pm, name, scale=1.0, bg=None, crop=None, corner="br", tile=False):
    p = os.path.join(OUT, name)
    pm.save(p)
    im = Image.open(p).convert("RGBA")
    if bg is not None:
        base = Image.new("RGBA", im.size, tuple(bg) + (255,))
        im = Image.alpha_composite(base, im)
    im = im.convert("RGB")
    if crop:
        im = im.crop(crop)
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im = SL.watermark(im, tiled=tile, corner=corner, lift=8)
    im.save(p)
    MADE.append(name)
    print("  %-34s %dx%d" % (name, im.width, im.height))


# ============================================================ 造数据
print("== 造预览数据（临时库） ==")
N_M = 300
_c = db.get_conn()
try:
    _c.executemany(
        "INSERT INTO media (kind,title,sort_title,year,file_path,library)"
        " VALUES (?,?,?,?,?,?)",
        [("movie", "预览作品 %03d" % (i + 1), "预览作品 %03d" % (i + 1),
          2010 + (i % 16), "X:/Media/Movies/作品 %03d/作品 %03d.mp4" % (i + 1, i + 1),
          "我的收藏") for i in range(N_M)])
    _c.commit()
    ACTORS = [("深田えいみ", "Fukada Eimi", 96), ("三上悠亜", "Mikami Yua", 88),
              ("橋本ありな", "Hashimoto Arina", 74), ("葵つかさ", "Aoi Tsukasa", 69),
              ("高橋しょう子", "Takahashi Shoko", 63), ("紬美羽", "Tsumugi Miwa", 58),
              ("咲野のぞみ", "Sakino Nozomi", 52), ("星野ナミ", "Hoshino Nami", 47),
              ("白石茉莉奈", "Shiraishi Marina", 43), ("相沢みなみ", "Aizawa Minami", 39),
              ("桃乃木かな", "Momonoiki Kana", 35), ("桜空もも", "Ozora Momo", 31),
              ("吉沢明歩", "Yoshizawa Akiho", 28), ("大槻ひびき", "Otsuki Hibiki", 25)]
    DIRECTORS = [("肉尊", "Nikuzon", 198), ("シネマジック", "Kinema Shikku", 172),
                 ("溜池ゴロー", "Tarantino", 146), ("大橋ケン", "Ohashi Ken", 124),
                 ("三島六三郎", "Mishima Musaburo", 101), ("辻本龍", "Ryu", 88),
                 ("氷室涼介", "Wilson Gray", 65), ("安藤光一", "Yuzu Aoi", 43)]
    links = []
    a_ids = []
    for name, romaji, cnt in ACTORS:
        pid = db.upsert_person(name, role_type="Actor")
        a_ids.append(pid)
        db.set_person_fields(pid, name=name, romaji=romaji, status="现役",
                             birthday="199%d-0%d-%02d" % (cnt % 9, (cnt % 9) + 1,
                                                          (cnt % 28) + 1),
                             meta='{"身高": "158cm", "尺寸": "T158 / B88( Fカップ ) / W58 / H88 / S"}')
        links += [(k + 1, pid, "Actor", 0) for k in range(min(cnt, N_M))]
    for name, romaji, cnt in DIRECTORS:
        pid = db.upsert_person(name, role_type="Director")
        db.update_person(pid, romaji=romaji, status="现役")
        links += [(k + 1, pid, "Director", 0) for k in range(min(cnt, N_M))]
    _c.executemany(
        "INSERT OR IGNORE INTO media_people (media_id,person_id,char_role,person_order)"
        " VALUES (?,?,?,?)", links)
    _c.commit()
finally:
    _c.close()

try:
    cfg.get_settings().add_library("我的收藏", "混合", [os.path.join(TMP, "libs", "Movies")])
except Exception as e:
    print("     （建库失败：%s）" % e)

# 最近播放 / 合集要点数据才有内容
try:
    _c = db.get_conn()
    _c.executemany("UPDATE media SET play_count=? WHERE id=?",
                   [(i % 4, i) for i in range(1, 25)])
    _c.commit()
    _c.close()
except Exception:
    pass

db.toggle_person_favorite(a_ids[0])
db.toggle_person_pinned(a_ids[1])

print("   作品 %d / 演员 %d" % (N_M, len(a_ids)))

# ============================================================ 主窗
print("\n== 四页（白条现场） ==")
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(16)

PAGES = [("01_actors.png", "演员库", win._view_actors),
         ("02_directors.png", "导演库", win._view_directors),
         ("03_recent.png", "最近播放", win._view_recent),
         ("04_collections.png", "合集", win._view_collections)]

GRID_TOOLBAR_CROP = None
for fname, label, fn in PAGES:
    try:
        pg = fn()
        win.stack.addWidget(pg)
        win.stack.setCurrentWidget(pg)
        pump(70)
        # 记录工具行区域（白条现场）—— 用于放大对照
        grids = pg.findChildren(mw.LazyGrid)
        if grids and GRID_TOOLBAR_CROP is None:
            g = grids[0]
            try:
                tl = g.mapTo(win, g.rect().topLeft())
                GRID_TOOLBAR_CROP = (tl.x(), tl.y() - 8,
                                     tl.x() + g.width(), tl.y() + 62)
            except Exception:
                pass
        # 白条断言：head 不可见
        vis = [(gg.head.isVisibleTo(gg), getattr(gg, "_toolbar_ready", None))
               for gg in grids]
        save(win.grab(), fname, bg=None)
        print("     %s  网格 %d 个  head 可见性 %s" % (label, len(grids), vis))
    except Exception as e:
        import traceback
        print("     （%s 抓图失败：%s）" % (label, e))
        traceback.print_exc()

win.close()
pump(6)

# ============================================================ 工具窗
print("\n== 工具窗（新增导出/导入按钮） ==")
import ui_settings

dlg = ui_settings.SettingsDialog()
dlg.resize(1180, 900)
dlg.show()
pump(14)

for fname, page, hint in (("06_dedupe_export.png", "重复检测", "dd_exp_result"),
                          ("07_tagopt_export.png", "标签优化", "btn_to_exp")):
    try:
        dlg._show(page)
        pump(20)
        btn = getattr(dlg, hint, None)
        if btn is not None:
            tr = btn.parentWidget()
            tl = tr.mapTo(dlg, tr.rect().topLeft())
            save(dlg.grab(), fname, bg=None,
                 crop=(max(0, tl.x() - 24), max(0, tl.y() - 14),
                       min(dlg.width(), tl.x() + tr.width() + 24),
                       min(dlg.height(), tl.y() + tr.height() + 14)))
        print("     %s  按钮存在 = %s" % (page, btn is not None))
    except Exception as e:
        print("     （%s 抓图失败：%s）" % (page, e))

dlg.close()
pump(6)

# ============================================================ 关于
print("\n== 「关于」联系图标 ==")
ab = mw.AboutDialog()
ab.resize(720, 800)
ab.show()
pump(24)
try:
    from PySide6.QtWidgets import QPushButton
    cbs = [b for b in ab.findChildren(QPushButton) if b.objectName() == "ContactIcon"]
    if cbs:
        tr = cbs[0].parentWidget()
        tl = tr.mapTo(ab, tr.rect().topLeft())
        save(ab.grab(), "05_about_contacts.png", 2.2,
             crop=(max(0, tl.x() - 260), max(0, tl.y() - 30),
                   min(ab.width(), tl.x() + tr.width() + 260),
                   min(ab.height(), tl.y() + tr.height() + 30)),
             corner="tl")
    else:
        save(ab.grab(), "05_about_contacts.png", bg=None, corner="bl")
    print("     联系图标 %d 枚，尺寸 %s" % (len(cbs), [(b.width(), b.height()) for b in cbs]))
except Exception as e:
    print("     （关于抓图失败：%s）" % e)
    save(ab.grab(), "05_about_contacts.png", bg=None, corner="bl")

ab.close()
pump(6)

# ============================================================ 修前/修后对照
print("\n== 白条对照图 ==")
try:
    fixed = Image.open(os.path.join(OUT, "01_actors.png")).convert("RGB")
    if GRID_TOOLBAR_CROP:
        x0, y0, x1, y1 = GRID_TOOLBAR_CROP
        x0, x1 = max(0, x1 - 620), x1
        box = (x0, max(0, y0), x1, y1)
        crop = fixed.crop(box)
    else:
        crop = fixed.crop((fixed.width - 700, 60, fixed.width - 40, 130))
    # 「修前」合成：在原位置画一条空槽灰白细条（复现缺陷外观）
    before = crop.copy()
    from PIL import ImageDraw
    d = ImageDraw.Draw(before)
    w, h = before.size
    bar_y = int(h * 0.42)
    d.rectangle((int(w * 0.40), bar_y, int(w * 0.94), bar_y + 6),
                fill=(152, 150, 146))
    gap, head, pad = 18, 46, 18
    canv = Image.new("RGB", (crop.width + pad * 2,
                             head + crop.height * 2 + gap + pad), (24, 21, 19))
    dd = ImageDraw.Draw(canv)
    f = SL.font(20)
    dd.text((pad, 12), "修复前（空槽灰白细条）", font=f, fill=(214, 138, 122))
    dd.text((pad, head + crop.height + gap - 30), "修复后（v1.33.0）", font=f,
            fill=(150, 205, 160))
    canv.paste(before, (pad, head))
    canv.paste(crop, (pad, head + crop.height + gap))
    canv = SL.watermark(canv)
    canv.save(os.path.join(OUT, "08_whitebar_compare.png"))
    MADE.append("08_whitebar_compare.png")
    print("  08_whitebar_compare.png  %dx%d" % canv.size)
except Exception as e:
    print("     对照图失败：%s" % e)

print("\n共 %d 张 → %s" % (len(MADE), OUT))
print("版本：%s (Build %s)" % (ver.VERSION, ver.BUILD))
