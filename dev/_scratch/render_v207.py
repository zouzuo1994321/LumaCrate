# -*- coding: utf-8 -*-
"""v2.0.7 出图（三张）：

① 演员详情页「别名」—— 改前是链接蓝、改后是白，上下拼一张对比；
② 详情页「演职人员信息」—— 职务名已是中文（演员 / 导演），且顺序是
   女 > 男 > 未知、演员 > 导演；
③ 首页列表表头 —— 每列「左漏斗 + 右三角」，一列已筛选（漏斗实心）、
   一列在排序（三角实心朝下），下面接上真正弹出的筛选面板。
"""
import os
import shutil
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = r"C:/Users/zouzu/AppData/Local/Temp/v207render"
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem  # noqa: E402
from PySide6.QtGui import (QPixmap, QColor, QPainter, QFontDatabase,      # noqa: E402
                           QLinearGradient, QFont)
from PySide6.QtCore import Qt                                             # noqa: E402

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
import ui_home as uhome        # noqa: E402

mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

OUT = os.path.join(ROOT, "docs", "preview")
os.makedirs(OUT, exist_ok=True)
BG = QColor("#0a0a0b")


def mk_grad(path, w, h, c1, c2):
    pm = QPixmap(w, h)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0.0, QColor(c1))
    g.setColorAt(1.0, QColor(c2))
    p = QPainter(pm)
    p.fillRect(pm.rect(), g)
    p.end()
    pm.save(path)
    return path


BACKDROP = mk_grad(os.path.join(TMP, "fanart.png"), 1400, 520, "#4a3f52", "#17161a")
POSTER = mk_grad(os.path.join(TMP, "poster.png"), 300, 450, "#3b3b46", "#141418")
PHOTO = mk_grad(os.path.join(TMP, "photo.png"), 240, 240, "#8a6f6a", "#3a2c2c")
PHOTOS = []
for i, (c1, c2) in enumerate([("#8a6f6a", "#3a2c2c"), ("#7d7d86", "#2c2c30"),
                              ("#8a7a6a", "#332b26"), ("#6a7a86", "#262c30"),
                              ("#6d6a7f", "#2b2a33")]):
    PHOTOS.append(mk_grad(os.path.join(TMP, "photo%d.png" % i), 240, 240, c1, c2))


def compose(rows, out_path, pad=14, bg=BG, labels=None, gap=12):
    """rows: [QImage...] 竖向堆叠；labels: 与 rows 等长的说明文字（画在每张图左上）。"""
    w = max(im.width() for im in rows) + pad * 2
    label_h = 26 if labels else 0
    h = (sum(im.height() + label_h for im in rows) + pad * 2 + gap * (len(rows) - 1))
    canvas = QPixmap(w, h)
    canvas.fill(bg)
    p = QPainter(canvas)
    f = QFont("Microsoft YaHei", 10)
    p.setFont(f)
    y = pad
    for i, im in enumerate(rows):
        if labels:
            p.setPen(QColor("#a1a1aa"))
            p.drawText(pad + 2, y + 17, labels[i])
            y += label_h
        p.drawImage(pad, y, im)
        y += im.height() + gap
    p.end()
    canvas.save(out_path)
    print("saved", out_path, os.path.getsize(out_path))


# ---------------- ① 演员详情页：别名白 ----------------
PID = db.upsert_person("相音さな", "Actor")
db.set_person_fields(PID, gender="female", photo_path=PHOTO,
                     alias="あい【デリ嬢】、さな", birthday="2006-03-25",
                     romaji="Aine Sana", status="现役",
                     meta='{"身高": "145", "出身地": "東京"}')

win = mw.MainWindow()
win.resize(1500, 950)
win.show()
for _ in range(8):
    app.processEvents()

page = win._view_actor_detail(PID)
page.resize(1180, 420)
page.show()
for _ in range(8):
    app.processEvents()

from PySide6.QtWidgets import QLabel   # noqa: E402

alias_lbl = None
for lb in page.findChildren(QLabel):
    if (lb.text() or "").startswith("别名："):
        alias_lbl = lb
        break
print("alias label:", None if alias_lbl is None else alias_lbl.styleSheet())


def band(img, widget, host, up=16, down=16):
    p = widget.mapTo(host, widget.rect().topLeft())
    y0 = max(0, p.y() - up)
    y1 = min(img.height(), p.y() + widget.height() + down)
    return img.copy(0, y0, img.width(), max(1, y1 - y0))


def band_zoom(img, widget, host, x0, x1, up=16, down=16, factor=2):
    """按控件真实几何裁一条横带 → 只留左侧文字区 → 放大，方便肉眼比颜色。"""
    b = band(img, widget, host, up, down)
    w = min(x1, b.width()) - x0
    b = b.copy(x0, 0, max(1, w), b.height())
    return b.scaled(b.width() * factor, b.height() * factor,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation)


img_new = page.grab().toImage()
band_new = band_zoom(img_new, alias_lbl, page, 140, 900, up=58, down=36, factor=2)
# 旧样式（链接蓝）就地复现一版，做「改前 / 改后」对比
alias_lbl.setStyleSheet("color:#66a9ff;")
for _ in range(4):
    app.processEvents()
band_old = band_zoom(page.grab().toImage(), alias_lbl, page, 140, 900,
                     up=58, down=36, factor=2)
alias_lbl.setStyleSheet("color:#fafafa;")
for _ in range(4):
    app.processEvents()

compose([band_old, band_new], os.path.join(OUT, "v207_alias_white.png"),
        labels=["改前：别名是链接蓝 #66a9ff（看着像能点）",
                "改后：近白 #fafafa（与正文一致，不再暗示可点）"])

# ---------------- ② 演职人员：职务中文 + 排序 ----------------
MID = db.insert_media(title="MIDA-846 【FANZA限定】テスト作品", kind="movie", year=2026,
                      rating=8.2, poster=POSTER, fanart=BACKDROP,
                      file_path=os.path.join(TMP, "MIDA-846.mp4"),
                      nfo_path=os.path.join(TMP, "movie.nfo"),
                      library="Javlibrary", certification="JP-18+",
                      runtime="03:00:00", studio="MOODYZ",
                      tags="單體作品,女上位,中出,口交")

# 故意按「乱序」入库：男演员在前、导演夹在中间 —— 显示时应被重排
CAST = [("橋本誠吾", "male", "Actor", 0),
        ("K*WEST", "", "Director", 1),
        ("八木奈々", "female", "Actor", 2),
        ("水野朝陽", "female", "Director", 3),
        ("宮島めい", "female", "Actor", 4)]
for i, (name, gender, role, order) in enumerate(CAST):
    pid = db.upsert_person(name, "Director" if role == "Director" else "Actor")
    db.set_person_fields(pid, gender=gender, photo_path=PHOTOS[i])
    db.link_media_person(MID, pid, "导演" if role == "Director" else "", order)

hv = uhero.HeroView(dict(db.get_media(MID)))
hv.resize(1180, 980)
hv.show()
for _ in range(8):
    app.processEvents()
hv.verticalScrollBar().setValue(0)
for _ in range(4):
    app.processEvents()

avs = hv.findChildren(uhero.CastAvatar)
print("cast shown:", [(a.person.get("name"), a.findChildren(QLabel)[-1].text()) for a in avs])
p0 = avs[0].mapTo(hv, avs[0].rect().topLeft())
p1 = avs[-1].mapTo(hv, avs[-1].rect().topLeft())
row = hv.grab().toImage().copy(0, max(0, p0.y() - 44), hv.width(),
                               min(hv.height(), p1.y() + avs[-1].height() + 10) - max(0, p0.y() - 44))
compose([row], os.path.join(OUT, "v207_cast_roles.png"),
        labels=["演职人员：职务中文化（Actor→演员）＋ 女>男>未知、演员>导演"])

# ---------------- ③ 表头漏斗 + 三角 + 筛选面板 ----------------
tw = QTableWidget(0, 4)
tw.setHorizontalHeaderLabels(["收藏", "标题", "用户评分", "上映日期"])
hdr = uhome.FilterHeaderView(Qt.Horizontal, tw)
hdr.setDefaultAlignment(Qt.AlignCenter)
hdr.sort_col = 1              # 正在按「标题」排序
hdr.sort_asc = False
tw.setHorizontalHeader(hdr)
for c, w in ((0, 120), (1, 420), (2, 140), (3, 140)):
    tw.setColumnWidth(c, w)
rows = [("★ 收藏", "MIDA-846 【FANZA限定】中出し特化ASMR", "7.5", "2026-03-01"),
        ("—", "SSIS-001 別の作品タイトル", "5.0", "2019-11-20"),
        ("—", "mida 低評価の作品", "—", "2026-05-12")]
tw.setRowCount(len(rows))
for r, cols in enumerate(rows):
    for c, val in enumerate(cols):
        tw.setItem(r, c, QTableWidgetItem(val))
tw.resize(880, 190)
tw.show()
for _ in range(8):
    app.processEvents()
hdr_img = tw.grab().toImage().copy(0, 0, tw.width(), 44)

pop = uhome.ColumnFilterPopup("year", "上映日期", {"mode": "num", "op": ">=", "value": "2020"},
                              None)
pop.show()
for _ in range(6):
    app.processEvents()
pop_img = pop.grab().toImage()
compose([hdr_img, pop_img], os.path.join(OUT, "v207_header_filter.png"),
        labels=["表头：每列左漏斗 / 右三角（漏斗实心=这列已筛选，三角实心朝下=降序）",
                "点漏斗弹出的筛选面板：数值列给「= ≥ ≤」+ 数值，文本列给输入框，收藏/类型给胶囊"])
print("HDR_OK", hdr_img.size(), pop_img.size())
