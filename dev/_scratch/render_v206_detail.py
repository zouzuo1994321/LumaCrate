# -*- coding: utf-8 -*-
"""v2.0.6 出图：

① 详情页 —— 评分按钮两态（金色「评分」/ 橙色加粗「用户评分 7.5」）、
   标签芯片右上角「×」、演职人员头像右上角「×」与标题旁「＋」。
② 重复检测结果区 —— 「播放 / 定位文件 / 打开文件夹 / 删除…」按钮排。
"""
import os
import sys
import shutil
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = r"C:/Users/zouzu/AppData/Local/Temp/v206render"
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtWidgets import QApplication                # noqa: E402
from PySide6.QtGui import (QPixmap, QColor, QPainter, QFontDatabase,
                           QLinearGradient)               # noqa: E402
from PySide6.QtCore import Qt, QRect                      # noqa: E402

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db          # noqa: E402
import config as cfg           # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP
db.init_db()

import main_window as mw       # noqa: E402
import ui_hero as uhero        # noqa: E402
import duplicates as dup       # noqa: E402
import ui_settings as uis      # noqa: E402

mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

OUT = os.path.join(ROOT, "docs", "preview")
os.makedirs(OUT, exist_ok=True)
BG = QColor("#0a0a0b")


def mk_grad(path, w, h, c1, c2, vertical=True):
    pm = QPixmap(w, h)
    g = QLinearGradient(0, 0, 0, h) if vertical else QLinearGradient(0, 0, w, 0)
    g.setColorAt(0.0, QColor(c1))
    g.setColorAt(1.0, QColor(c2))
    p = QPainter(pm)
    p.fillRect(pm.rect(), g)
    p.end()
    pm.save(path)
    return path


BACKDROP = mk_grad(os.path.join(TMP, "fanart.png"), 1400, 520, "#4a3f52", "#17161a")
POSTER = mk_grad(os.path.join(TMP, "poster.png"), 300, 450, "#3b3b46", "#141418")


def mkphoto(path, c1, c2):
    return mk_grad(path, 220, 220, c1, c2)


PHOTOS = [mkphoto(os.path.join(TMP, "a%d.png" % i), c1, c2) for i, (c1, c2) in enumerate([
    ("#8a6f6a", "#3a2c2c"), ("#7d7d86", "#2c2c30"), ("#8a7a6a", "#332b26"), ("#6a7a86", "#262c30")])]

CAST = [("月島ななこ", "female", PHOTOS[0]), ("玉城マイ", "female", PHOTOS[1]),
        ("葉月七瀬", "female", PHOTOS[2]), ("大槻ひびき", "female", PHOTOS[3]),
        ("K*WEST", "", PHOTOS[1])]
TAGS = "素人作品,4小時以上作品,美乳,內衣,美少女電影,中出"


def build(media_id):
    row = db.get_media(media_id)
    h = uhero.HeroView(dict(row))
    h.resize(1180, 980)
    h.show()
    app.processEvents()
    h.verticalScrollBar().setValue(0)
    app.processEvents()
    return h


def grab_widget(w, w_px=None, h_px=None):
    pm = w.grab()
    img = pm.toImage()
    if w_px and h_px:
        img = img.copy(0, 0, min(w_px, img.width()), min(h_px, img.height()))
    return img


def compose(rows, out_path, pad=14, bg=BG):
    """rows: [(QImage, ...)] 竖向堆叠，统一底色（否则 alpha 会被 convert 成纯白）。"""
    w = max(im.width() for im in rows) + pad * 2
    h = sum(im.height() for im in rows) + pad * 2 + 12 * (len(rows) - 1)
    canvas = QPixmap(w, h)
    canvas.fill(bg)
    p = QPainter(canvas)
    y = pad
    for im in rows:
        p.drawImage(pad, y, im)
        y += im.height() + 12
    p.end()
    canvas.save(out_path)
    print("saved", out_path, os.path.getsize(out_path))


# ---------- 造媒体 ----------
def make_media(title, user_rating, favorite=0):
    mid = db.insert_media(title=title, kind="movie", year=2016, rating=7.5,
                          poster=POSTER, fanart=BACKDROP, tags=TAGS,
                          file_path=os.path.join(TMP, "ID-063.mp4"),
                          nfo_path=os.path.join(TMP, "movie.nfo"),
                          favorite=favorite, user_rating=user_rating,
                          library="Javlibrary", certification="JP-18+",
                          runtime="06:01:00", studio="TMA",
                          collection="可愛すぎるランジュリー娘10人と中出し性交",
                          plot=("可愛すぎるランジュリー娘10人と中出し性交 PREMIUM BEST 6時間。"
                                "素人作品・4小時以上作品・美乳・內衣・美少女電影・中出。"))
    for i, (name, gender, photo) in enumerate(CAST):
        pid = db.upsert_person(name, "Actor")
        db.set_person_fields(pid, gender=gender, photo_path=photo)
        db.link_media_person(mid, pid, "" if i < 4 else "导演", i)
    return mid


with open(os.path.join(TMP, "ID-063.mp4"), "wb") as fh:
    fh.write(b"\0" * 64)

M_RATED = make_media("ID-063 可愛すぎるランジュリー娘10人と中出し性交 PREMIUM BEST 6時間", 7.5)
M_PLAIN = make_media("ID-063 可愛すぎるランジュリー娘10人と中出し性交 PREMIUM BEST 6時間", None)

h1 = build(M_RATED)
h2 = build(M_PLAIN)


def band(h, widget, up=26, down=30):
    """按控件的真实几何裁一条横带（不用拍脑袋的固定 y —— 上一版就是这么裁错的）。"""
    p = widget.mapTo(h, widget.rect().topLeft())
    y0 = max(0, p.y() - up)
    y1 = min(h.grab().height(), p.y() + widget.height() + down)
    return h.grab().toImage().copy(0, y0, h.width(), y1 - y0)


def zoom(img, factor=2):
    return img.scaled(img.width() * factor, img.height() * factor,
                      Qt.KeepAspectRatio, Qt.SmoothTransformation)


# ① 操作按钮行（两种评分态）
row_rated = band(h1, h1._rate_btn, 16, 14)
row_plain = band(h2, h2._rate_btn, 16, 14)

# ② 演职人员 + 标签（同一屏内连在一起）
av = h1.findChildren(uhero.CastAvatar)[0]
chips = [w for w in h1.findChildren(uhero.QWidget) if w.objectName() == "TagChip"]
p_av = av.mapTo(h1, av.rect().topLeft())
p_ch = chips[0].mapTo(h1, chips[0].rect().topLeft())
detail = h1.grab().toImage().copy(
    0, max(0, p_av.y() - 40), h1.width(), p_ch.y() + chips[0].height() + 16 - max(0, p_av.y() - 40))

# ③ 放大看两处「×」
z1 = zoom(band(h1, chips[1], 10, 6), 3)
z2 = zoom(band(h1, av, 6, 6), 2)

compose([row_rated, row_plain, detail], os.path.join(OUT, "v206_detail.png"))
compose([z1, z2], os.path.join(OUT, "v206_zoom_x.png"))
print("hero rate btn:", h1._rate_btn.text(), "|", h1._rate_btn.styleSheet())
print("hero2 rate btn:", h2._rate_btn.text(), "|", h2._rate_btn.styleSheet())

# ---------- 重复检测结果区 ----------
LIB = os.path.join(TMP, "lib")
for name in ("A", "B", "C"):
    d = os.path.join(LIB, name, "ID-063")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "ID-063.mp4"), "wb") as fh:
        fh.write(b"\0" * (3000 if name != "C" else 2000))
    db.insert_media(title="ID-063 重複テスト", kind="movie", year=2016, rating=7.5,
                    file_path=os.path.join(d, "ID-063.mp4"), library="探针库",
                    sort_title="ID-063 重複テスト")

rep = dup.find_duplicates(library="探针库", verify_exists=True, exclude_multipart=True)
dlg = uis.SettingsDialog(None)
dlg._dd_report = rep
dlg._dd_removed = set()
dlg._fill_dedupe_tree(rep)
dlg.resize(uis.SettingsDialog.DEF_W, uis.SettingsDialog.DEF_H)
dlg.show()
dlg._show("重复检测")          # 必须真的切到这一页：否则抓出来的是「个性化设置」
app.processEvents()
dlg.dd_tree.setCurrentItem(dlg.dd_tree.topLevelItem(0).child(1))
app.processEvents()

box = dlg.dd_tree.parentWidget()          # 检测结果 GroupBox
geo = box.mapTo(dlg, box.rect().topLeft())
shot = dlg.grab().toImage().copy(geo.x() - 6, geo.y() - 6, box.width() + 12, box.height() + 12)
compose([shot], os.path.join(OUT, "v206_dup_actions.png"))
print("dup tree groups:", dlg.dd_tree.topLevelItemCount(), "box:", box.width(), box.height())
print("PLAY_OK")
