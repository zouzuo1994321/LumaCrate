# -*- coding: utf-8 -*-
"""v1.46.9 探针：详情页三条反馈的离屏自证。

① 标题只有 1 行时，高度必须只是 1 行（与简介之间的空白消失）；
② 片源目录下 extrafanart/ 的剧照被识别，并做成可左右滑的横条（横向滚动范围 > 0）；
③ 标签行渲染 + 「＋/-」落库（media.tags）与写回 nfo（<tag>）。
"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1469"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtWidgets import QApplication, QLabel

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import applog

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import database as db
import nfo_parser as nfo
import ui_hero

DBDIR = os.path.join(TMP, "index_data")
os.makedirs(DBDIR, exist_ok=True)
DB = os.path.join(DBDIR, "media_center.db")
if os.path.exists(DB):
    try:
        os.remove(DB)
    except OSError:
        os.rename(DB, DB + ".old")
db.db_path = lambda: DB
db.init_db()

db._MEDIA_COLS = None   # 加列后让列投影重新读一次（真实进程里是首次调用才读）

# ---- 造一部片子：一个目录 + extrafanart/3 张剧照 + movie.nfo（含 <tag>） ----
MOV = os.path.join(TMP, "movie_LMC-001")
STILLS = os.path.join(MOV, "extrafanart")
os.makedirs(STILLS, exist_ok=True)
for i in range(3):
    im = Image.new("RGB", (480, 270), (40 + i * 30, 30, 25))
    d = ImageDraw.Draw(im)
    d.text((20, 120), "still %d" % (i + 1), fill=(240, 220, 180))
    im.save(os.path.join(STILLS, "fanart%d.jpg" % (i + 1)))

NFO = os.path.join(MOV, "movie.nfo")
open(NFO, "w", encoding="utf-8").write(
    '<?xml version="1.0" encoding="utf-8"?>\n<movie>\n'
    "  <title>LMC-001</title>\n  <year>2024</year>\n"
    "  <plot>简介占位文本</plot>\n"
    "  <genre>剧情</genre>\n"
    "  <tag>已看</tag>\n  <tag>收藏向</tag>\n"
    "</movie>\n")

VIDEO = os.path.join(MOV, "LMC-001.mp4")
open(VIDEO, "wb").write(b"\x00" * 1024)

SHORT = "短标题"
LONG = "这是一个非常非常长的标题用来验证两行折行效果并且需要足够长才能折成两行以上 LMC-001"

mid = db.upsert_media_by_path(
    mode="overwrite", kind="movie", title=SHORT, sort_title=SHORT.lower(),
    year=2024, plot="简介第一行。", file_path=VIDEO, nfo_path=NFO,
    library="测试库", genres="剧情", tags="已看,收藏向", file_size=1024,
)
print("media id:", mid, flush=True)

db.update_media_fields(mid, tags="已看,收藏向")
row = db.get_media(mid)
print("库中 tags:", row.get("tags"), flush=True)

import main_window as mw

mw.load_style(app)


def settle(n=20):
    for _ in range(n):
        app.processEvents()


def img_of(w):
    im = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    iw, ih = im.width(), im.height()
    bg = Image.new("RGB", (iw, ih), (20, 17, 15))
    raw = Image.frombytes("RGBA", (iw, ih), bytes(im.constBits()))
    return Image.alpha_composite(bg.convert("RGBA"), raw).convert("RGB")


FAILS = []


def check(name, ok, detail=""):
    print(("[OK]   " if ok else "[FAIL] ") + name + ("  " + str(detail) if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


# ---------------- ① 标题高度 ----------------
def hero_for(title):
    r = dict(row)
    r["title"] = title
    h = ui_hero.HeroView(r)
    h.resize(1200, 900)
    h.show()
    settle(30)
    return h


short_hero = hero_for(SHORT)
long_hero = hero_for(LONG)

labels = short_hero.findChildren(ui_hero.ElidedLabel)
print("ElidedLabel 数量:", len(labels), flush=True)
for l in labels:
    print("  text=%r px=%d lines=%d h=%d w=%d" % (l.full_text()[:18], l._px, l._lines, l.height(), l.width()),
          flush=True)

t_short = [l for l in short_hero.findChildren(ui_hero.ElidedLabel) if l._px == 34][0]
t_long = [l for l in long_hero.findChildren(ui_hero.ElidedLabel) if l._px == 34][0]
ls = t_short._eff_font_metrics().lineSpacing()
check("① 单行标题只占 1 行高度", t_short._lines == 1 and t_short.height() <= ls + 6 + 2,
      "lines=%d h=%d lineSpacing=%d" % (t_short._lines, t_short.height(), ls))
check("① 长标题占 2 行高度", t_long._lines == 2 and t_long.height() > ls + 6,
      "lines=%d h=%d" % (t_long._lines, t_long.height()))
check("① 单行比双行矮约 1 行", (t_long.height() - t_short.height()) >= ls - 2,
      "diff=%d" % (t_long.height() - t_short.height()))

# 标题「文字底边」到简介顶部的间隙：这才是用户看到的空白。
# 注意不能量控件矩形 —— 2 行高度里只有 1 行有字时，空白在**标题框内部**，
# 框与框之间的布局间距是恒定的（spacing），量框只会得出「两者一样」的假结论。
def ink_gap(hero):
    t = [l for l in hero.findChildren(ui_hero.ElidedLabel) if l._px == 34][0]
    plot = [l for l in hero.findChildren(ui_hero.ElidedLabel) if l._px == 12][0]
    banner = t.parentWidget()
    ink_bottom = t.mapTo(banner, t.rect().topLeft()).y() + t._lines * t._eff_font_metrics().lineSpacing()
    plot_top = plot.mapTo(banner, plot.rect().topLeft()).y()
    return plot_top - ink_bottom


g1 = ink_gap(short_hero)
g2 = ink_gap(long_hero)
print("标题文字底边→简介顶部间隙: 单行=%d 双行=%d" % (g1, g2), flush=True)
check("① 单行标题下方不再留一整行空白（间隙 < 1 行高）", g1 < ls,
      "gap=%d lineSpacing=%d（修复前这条会是 %d）" % (g1, ls, g1 + ls))
check("① 单行/双行的「文字到简介」间距一致", abs(g1 - g2) <= 2,
      "short=%d long=%d" % (g1, g2))

# ---------------- ② extrafanart ----------------
found = ui_hero.find_extrafanart(row)
check("② 识别到 extrafanart 的 3 张剧照", len(found) == 3, found)
check("② 按自然序（fanart1..3）", [os.path.basename(p) for p in found] ==
      ["fanart1.jpg", "fanart2.jpg", "fanart3.jpg"], [os.path.basename(p) for p in found])

strip = short_hero.findChild(ui_hero.StillStrip)
check("② 剧照横条已建立", strip is not None)
if strip is not None:
    strip.setFixedWidth(520)       # 强制窄视口 → 必须能横向滚动
    settle(10)
    bar = strip.horizontalScrollBar()
    print("横条: viewport=%d content=%d scrollbar max=%d" % (
        strip.viewport().width(), strip.widget().width(), bar.maximum()), flush=True)
    check("② 剧照可左右滑（横向滚动范围 > 0）", bar.maximum() > 0,
          "max=%d" % bar.maximum())
    check("② 竖向滚动条不出现", strip.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff)
    im = img_of(strip)
    im.save(os.path.join(TMP, "extrafanart_strip.png"))
    check("② 横条真的画出了图（非空像素）", len(set(im.getdata())) > 40,
          "colors=%d" % len(set(im.getdata())))

# 没有 extrafanart 的片子：整块不该出现（两个路径都指到空目录，否则会沿 nfo 目录找到同一份剧照）
EMPTY = os.path.join(TMP, "no_stills")
os.makedirs(EMPTY, exist_ok=True)
r2 = dict(row)
r2["file_path"] = os.path.join(EMPTY, "nothing.mp4")
r2["nfo_path"] = os.path.join(EMPTY, "nothing.nfo")
check("② 无 extrafanart 时不建该区块", ui_hero.find_extrafanart(r2) == [],
      ui_hero.find_extrafanart(r2))

# ---------------- ③ 标签 ----------------
chips = [l for l in short_hero.findChildren(QLabel) if l.text() in ("已看", "收藏向")]
check("③ 两个标签芯片都渲染出来", len(chips) == 2, [c.text() for c in chips])
btns = [b.text() for b in short_hero.findChildren(ui_hero.QPushButton) if b.text() in ("＋", "－")]
check("③ ＋ / － 按钮都在", "＋" in btns and "－" in btns, btns)

short_hero._apply_tags(["已看", "收藏向", "新增标签"])
settle(10)
row2 = db.get_media(mid)
check("③ 标签落库", (row2.get("tags") or "") == "已看,收藏向,新增标签", row2.get("tags"))
tags_in_nfo = nfo.read_tags(NFO)
check("③ 标签写回 nfo <tag>", tags_in_nfo == ["已看", "收藏向", "新增标签"], tags_in_nfo)

# 删除一个
short_hero._apply_tags([t for t in short_hero._tag_values() if t != "已看"])
settle(10)
row3 = db.get_media(mid)
check("③ 删除标签生效", (row3.get("tags") or "") == "收藏向,新增标签", row3.get("tags"))
check("③ 删除后 nfo 同步", nfo.read_tags(NFO) == ["收藏向", "新增标签"], nfo.read_tags(NFO))

# 清空
short_hero._apply_tags([])
settle(10)
check("③ 清空标签", (db.get_media(mid).get("tags") or "") == "", db.get_media(mid).get("tags"))
check("③ 清空后 nfo 无 <tag>", nfo.read_tags(NFO) == [], nfo.read_tags(NFO))

# 落库归一化（去重 / 去空白）
val = db.set_media_tags(mid, [" x ", "x", "", "y"])
check("③ 归一化去重去空白", val == "x,y", val)

# 截图（标签 + 剧照整体）
short_hero._apply_tags(["已看", "收藏向"])
settle(20)
short_hero.resize(1200, 1400)
settle(20)
im = img_of(short_hero)
im.save(os.path.join(TMP, "hero_v1469.png"))
print("截图:", os.path.join(TMP, "hero_v1469.png"), im.size, flush=True)

print("FAILS:", FAILS, flush=True)
print("PROBE_V1469_DONE", flush=True)
