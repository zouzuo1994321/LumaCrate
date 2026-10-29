# -*- coding: utf-8 -*-
"""v1.46.9 预览图：① 单行/两行标题的间隙对比 ② 标签行 ③ extrafanart 剧照横条。"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_shot_v1469"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtWidgets import QApplication

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
import ui_hero
import main_window as mw

DBDIR = os.path.join(TMP, "index_data")
os.makedirs(DBDIR, exist_ok=True)
import time as _t
DB = os.path.join(DBDIR, "media_center_%d.db" % int(_t.time()))   # 每次跑用新库，避免 rename 冲突
db.db_path = lambda: DB
db.init_db()
db._MEDIA_COLS = None

MOV = os.path.join(TMP, "LMC-742")
ST = os.path.join(MOV, "extrafanart")
os.makedirs(ST, exist_ok=True)

# 合成一张「像样」的 fanart（渐变 + 光斑），避免占位图看不出层次
fan = Image.new("RGB", (1600, 700))
d = ImageDraw.Draw(fan)
for y in range(700):
    t = y / 700.0
    d.line([(0, y), (1600, y)], fill=(int(46 + 30 * t), int(34 + 12 * t), int(28 + 8 * t)))
for i, (cx, cy, r, col) in enumerate([(1180, 240, 330, (198, 148, 74)), (420, 420, 240, (120, 70, 46))]):
    for k in range(r, 0, -6):
        a = 1 - k / r
        d.ellipse([cx - k, cy - k, cx + k, cy + k],
                  fill=(int(col[0] * a + 40 * (1 - a)), int(col[1] * a + 30 * (1 - a)),
                        int(col[2] * a + 24 * (1 - a))))
FAN = os.path.join(MOV, "fanart.jpg")
fan.save(FAN, quality=92)

POSTER = os.path.join(MOV, "poster.jpg")
pos = fan.crop((900, 60, 1420, 840)).resize((420, 630))
pos.save(POSTER, quality=92)

# 6 张剧照
for i in range(6):
    im = Image.new("RGB", (640, 360))
    dd = ImageDraw.Draw(im)
    for y in range(360):
        t = y / 360.0
        dd.line([(0, y), (640, y)],
                fill=(int(50 + 26 * t + i * 6), int(38 + 10 * t), int(32 + 8 * t)))
    dd.ellipse([120 + i * 30, 90, 420 + i * 30, 300], fill=(150 + i * 8, 92, 56))
    dd.text((24, 320), "still %02d" % (i + 1), fill=(240, 224, 190))
    im.save(os.path.join(ST, "fanart%02d.jpg" % (i + 1)), quality=90)

NFO = os.path.join(MOV, "movie.nfo")
open(NFO, "w", encoding="utf-8").write(
    '<?xml version="1.0" encoding="utf-8"?>\n<movie>\n  <title>LMC-742</title>\n'
    "  <year>2026</year>\n  <plot>简介：这是一段用于演示详情页的简介文本，最多显示两行，超出用省略号收尾。</plot>\n"
    "  <genre>剧情</genre>\n  <tag>已看</tag>\n  <tag>收藏向</tag>\n  <tag>4K 修复</tag>\n</movie>\n")

VIDEO = os.path.join(MOV, "LMC-742.mp4")
open(VIDEO, "wb").write(b"\x00" * 2048)

SHORT = "LMC-742"
LONG = "LMC-742 完整标题特别加长版本用来验证两行折行与标题框高度是否随行数收缩"

mid = db.upsert_media_by_path(
    mode="overwrite", kind="movie", title=SHORT, sort_title=SHORT.lower(),
    year=2026, plot="简介：这是一段用于演示详情页的简介文本，最多显示两行，超出用省略号收尾。",
    file_path=VIDEO, nfo_path=NFO, library="演示库", genres="剧情",
    tags="已看,收藏向,4K 修复", file_size=2048, poster=POSTER, fanart=FAN,
)
db.update_media_fields(mid, poster=POSTER, fanart=FAN, tags="已看,收藏向,4K 修复")

mw.load_style(app)


def settle(n=25):
    for _ in range(n):
        app.processEvents()


def img_of(w):
    im = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    iw, ih = im.width(), im.height()
    bg = Image.new("RGB", (iw, ih), (13, 11, 10))
    raw = Image.frombytes("RGBA", (iw, ih), bytes(im.constBits()))
    return Image.alpha_composite(bg.convert("RGBA"), raw).convert("RGB")


row = db.get_media(mid)


def banner_shot(title, w=1500, h=430):
    r = dict(row)
    r["title"] = title
    hv = ui_hero.HeroView(r)
    hv.resize(w, h + 120)
    hv.show()
    settle(30)
    im = img_of(hv)
    # 只取横幅那一段（顶部 430px + 一点点）
    return im.crop((0, 0, w, h))


a = banner_shot(SHORT, 1500)
b = banner_shot(LONG, 1080)      # 收窄 → 长标题必然折成两行

# 主体：标签 + 剧照
hv = ui_hero.HeroView(dict(row))
hv.resize(1500, 1300)
hv.show()
settle(30)
full = img_of(hv)
body = full.crop((0, 430, 1500, min(full.height, 430 + 640)))

W = 1500
GAP = 14
F_TITLE = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 20)
OUT = Image.new("RGB", (W, 40 + a.height + GAP + b.height + GAP + 30 + body.height + 16),
                (13, 11, 10))
dd = ImageDraw.Draw(OUT)
dd.text((16, 10), "v1.46.9  ① 标题按实际行数收高：单行只占一行（上）/ 两行照常两行（下）",
        fill=(232, 214, 176), font=F_TITLE)
OUT.paste(a, (0, 40))
OUT.paste(b, (0, 40 + a.height + GAP))
F_NOTE = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
NOTE = ["同一台机器、同一份数据，",
        "只把预览宽度收到 1080px：",
        "长标题折成两行，第二行",
        "下方直接接元数据 ——",
        "框高跟着行数走，",
        "不再固定占两行。"]
for i, line in enumerate(NOTE):
    dd.text((1096, 60 + a.height + GAP + 24 + i * 26), line, fill=(168, 156, 138), font=F_NOTE)
y = 40 + a.height + GAP + b.height + GAP
dd.text((16, y), "② 标签行（＋ 添加 / － 删除）   ③ extrafanart 剧照横条（可左右划）",
        fill=(232, 214, 176), font=F_TITLE)
OUT.paste(body, (0, y + 30))
out = os.path.join(TMP, "preview_v1469.png")
OUT.save(out)
print("OK", out, OUT.size, flush=True)
print("SHOT_DONE", flush=True)
