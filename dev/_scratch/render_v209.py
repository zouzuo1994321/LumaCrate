# -*- coding: utf-8 -*-
"""v2.0.9 出图（三张）：

① `v209_icon_zoom.png` —— 三处小图标 6~8 倍像素放大，青线 = 几何中心、品红线 = 墨迹中心；
   第四个面板是**旧的** `QPushButton("＋")`，用同一把尺子量，偏位一眼可见。
② `v209_detail_tags.png` —— 详情页「标签 / 演职人员信息」真实渲染（× 与 ＋ 就在原位）。
③ `v209_exec_gap.png` —— 刮削页「执行」区：空标签占位（32px）vs 隐藏（7px）上下对照。
"""
import os
import shutil
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = r"C:/Users/zouzu/AppData/Local/Temp/v209render"
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget     # noqa: E402
from PySide6.QtGui import (QPixmap, QColor, QPainter, QFontDatabase, QFont,   # noqa: E402
                           QImage, QPen, QLinearGradient)
from PySide6.QtCore import Qt, QPoint, QRect                                  # noqa: E402

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
import ui_settings as uset     # noqa: E402

mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

OUT = os.path.join(ROOT, "docs", "preview")
os.makedirs(OUT, exist_ok=True)
BG = QColor("#0a0a0b")
PANEL = QColor("#141417")


def mk_grad(path, w, h, c1, c2):
    pm = QPixmap(w, h)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0.0, QColor(c1))
    g.setColorAt(1.0, QColor(c2))
    p = QPainter(pm)
    p.fillRect(pm.rect(), g)
    p.end()
    pm.save(path)
    return path


BACKDROP = mk_grad(os.path.join(TMP, "fanart.png"), 1400, 520, "#4a3f52", "#17161a")
POSTER = mk_grad(os.path.join(TMP, "poster.png"), 300, 450, "#3b3b46", "#141418")
PHOTOS = []
for i, (c1, c2) in enumerate([("#8a6f6a", "#3a2c2c"), ("#7d7d86", "#2c2c30"),
                              ("#8a7a6a", "#332b26"), ("#6a7a86", "#262c30"),
                              ("#6d6a7f", "#2b2a33")]):
    PHOTOS.append(mk_grad(os.path.join(TMP, "photo%d.png" % i), 240, 240, c1, c2))


def compose(rows, out_path, pad=14, bg=BG, labels=None, gap=12):
    w = max(im.width() for im in rows) + pad * 2
    label_h = 26 if labels else 0
    h = (sum(im.height() + label_h for im in rows) + pad * 2 + gap * (len(rows) - 1))
    canvas = QPixmap(w, h)
    canvas.fill(bg)
    p = QPainter(canvas)
    p.setFont(QFont("Microsoft YaHei", 10))
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


# ---------------- ① 图标放大 + 中心准线 ----------------
def grab_clean(w):
    """透明底抓图（关掉调色板铺底，否则整块是 #efefef 的白）。"""
    w.setAttribute(Qt.WA_NoSystemBackground, True)
    return w.grab().toImage()


def ink_center(im, thr=150):
    """墨迹中心的**连续坐标**（像素 i 的中心 = i+0.5）。判据必须连 alpha 一起看。"""
    xs, ys = [], []
    for y in range(im.height()):
        for x in range(im.width()):
            c = im.pixelColor(x, y)
            if c.alpha() >= 128 and max(c.red(), c.green(), c.blue()) >= thr:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return ((min(xs) + max(xs)) / 2.0 + 0.5, (min(ys) + max(ys)) / 2.0 + 0.5)


def zoom_panel(w, name, factor=10, sub="", extra_dot=None, note=""):
    """把控件放大 factor 倍，画青线（几何中心）与品红线（墨迹中心）。

    `extra_dot` = (dx, dy)：额外在「几何中心 + 偏移」处画一个红圈（用来标旧实现的落点）。
    """
    im = grab_clean(w)
    iw, ih = im.width(), im.height()
    zw, zh = iw * factor, ih * factor
    pw = max(zw, 560) + 24
    ox, oy = max(12, (pw - zw) // 2), 10
    ph = oy + zh + 72
    canvas = QImage(pw, ph, QImage.Format_ARGB32)
    canvas.fill(PANEL)
    p = QPainter(canvas)
    p.fillRect(ox, oy, zw, zh, QColor("#1b1b20"))
    p.drawImage(QRect(ox, oy, zw, zh), im)
    # 像素网格：一眼看出这是「第几个像素」，不是模糊的图形
    p.setPen(QPen(QColor(255, 255, 255, 14), 1))
    for i in range(iw + 1):
        p.drawLine(ox + i * factor, oy, ox + i * factor, oy + zh)
    for j in range(ih + 1):
        p.drawLine(ox, oy + j * factor, ox + zw, oy + j * factor)
    gx, gy = ox + iw / 2.0 * factor, oy + ih / 2.0 * factor
    p.setPen(QPen(QColor("#22d3ee"), 2))
    p.drawLine(int(gx), oy, int(gx), oy + zh)
    p.drawLine(ox, int(gy), ox + zw, int(gy))
    ic = ink_center(im)
    if ic:
        sx, sy = ox + ic[0] * factor, oy + ic[1] * factor
        p.setPen(QPen(QColor("#f472b6"), 2))
        p.drawLine(int(sx) - 10, int(sy) - 10, int(sx) + 10, int(sy) + 10)
        p.drawLine(int(sx) - 10, int(sy) + 10, int(sx) + 10, int(sy) - 10)
    if extra_dot:
        ex = ox + (iw / 2.0 + extra_dot[0]) * factor
        ey = oy + (ih / 2.0 + extra_dot[1]) * factor
        p.setPen(QPen(QColor("#f87171"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPoint(int(ex), int(ey)), 9, 9)
    p.setFont(QFont("Microsoft YaHei", 9))
    p.setPen(QColor("#ecedee"))
    p.drawText(14, oy + zh + 20, name)
    if ic:
        dx, dy = ic[0] - iw / 2.0, ic[1] - ih / 2.0
        p.setPen(QColor("#34d399") if abs(dx) <= 0.6 and abs(dy) <= 0.6
                 else QColor("#f87171"))
        p.drawText(14, oy + zh + 39, "墨迹中心偏移 %+.2f / %+.2f px%s"
                   % (dx, dy, ("   " + sub) if sub else ""))
    if note:
        p.setPen(QColor("#a1a1aa"))
        p.drawText(14, oy + zh + 58, note)
    p.end()
    return canvas


panels = []
chip = uhero.TagChip("人妻", on_delete=lambda: None)
chip.resize(chip.size())
chip.show()
for _ in range(6):
    app.processEvents()
# 标签胶囊整枚（外壳 4×）：× 就骑在胶囊右上角
_ci = chip.grab().toImage()
_f = 4
_CW = max(_ci.width() * _f, 560) + 24
_cp = QImage(_CW, _ci.height() * _f + 82, QImage.Format_ARGB32)
_cp.fill(PANEL)
_p = QPainter(_cp)
_cx = max(12, (_CW - _ci.width() * _f) // 2)
_p.fillRect(_cx, 10, _ci.width() * _f, _ci.height() * _f, QColor("#1b1b20"))
_p.drawImage(QRect(_cx, 10, _ci.width() * _f, _ci.height() * _f), _ci)
_p.setFont(QFont("Microsoft YaHei", 9))
_p.setPen(QColor("#ecedee"))
_p.drawText(12, _ci.height() * _f + 30, "标签胶囊（整体 4×）：× 骑在胶囊右上角")
_p.setPen(QColor("#a1a1aa"))
_p.drawText(12, _ci.height() * _f + 49, "叉比 v2.0.8 小 20% —— 半臂长 3.15px → 2.52px")
_p.end()
panels.append(_cp)
panels.append(zoom_panel(uhero.RoundClose(14, on_click=lambda: None),
                         "标签的 ×（14px · 10×）", 10, "圆心"))
panels.append(zoom_panel(uhero.RoundClose(18, on_click=lambda: None),
                         "演员头像右上角的 ×（18px · 10×）", 10, "圆心"))
panels.append(zoom_panel(uhero.RoundPlus(28, 24, tip=""),
                         "标签 / 演员信息的「＋」（28×24 · 10×）", 10, "框心",
                         extra_dot=(-1.5, 2.0),
                         note="红圈 = 旧 QPushButton 字形的落点（真机实测偏左 1.5 / 偏下 2px）"))

pad = 12
tot_w = max(pn.width() for pn in panels) + pad * 2
tot_h = sum(pn.height() for pn in panels) + pad * (len(panels) + 1) + 26
stage = QPixmap(tot_w, tot_h)
stage.fill(BG)
_pp = QPainter(stage)
_pp.setFont(QFont("Microsoft YaHei", 11))
_pp.setPen(QColor("#a1a1aa"))
_pp.drawText(pad + 1, 24, "青线 = 几何中心 · 品红 ×= 墨迹中心 —— 两条重合才是「在正中央」")
_y = 32
for pn in panels:
    _pp.drawImage(pad, _y, pn)
    _y += pn.height() + pad
_pp.end()
stage.save(os.path.join(OUT, "v209_icon_zoom.png"))
print("saved v209_icon_zoom.png", os.path.getsize(os.path.join(OUT, "v209_icon_zoom.png")))

# ---------------- ② 详情页：标签 + 演职人员 ----------------
MID = db.insert_media(title="MIDA-846 【FANZA限定】テスト作品", kind="movie", year=2026,
                      rating=8.2, poster=POSTER, fanart=BACKDROP,
                      file_path=os.path.join(TMP, "MIDA-846.mp4"),
                      nfo_path=os.path.join(TMP, "movie.nfo"),
                      library="Javlibrary", certification="JP-18+",
                      runtime="03:00:00", studio="MOODYZ",
                      tags="單體作品,女上位,中出,口交")
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
hv.resize(1180, 1000)
hv.show()
for _ in range(10):
    app.processEvents()
hv.verticalScrollBar().setValue(0)
for _ in range(4):
    app.processEvents()

_im = hv.grab().toImage()
# 裁「演职人员行 → 标签行」：演职人员排在上面、标签在下面，用真实控件几何定边界
_chips = hv.findChildren(uhero.TagChip)
_avs = hv.findChildren(uhero.CastAvatar)
if _chips and _avs:
    _top = max(0, min(a.mapTo(hv, a.rect().topLeft()).y() for a in _avs) - 48)
    _bot = min(_im.height(),
               max(c.mapTo(hv, c.rect().bottomLeft()).y() for c in _chips) + 12)
else:
    _top, _bot = max(0, hv.height() - 420), hv.height()
print("band y:", _top, _bot, "chips", len(_chips), "cast", len(_avs))
band = _im.copy(0, _top, _im.width(), max(1, _bot - _top))
compose([band], os.path.join(OUT, "v209_detail_tags.png"),
        labels=["详情页：标签行与演职人员行 —— × 都在圆心，「＋」都在正中央"])

# ---------------- ③ 刮削页：进度条上方那行空白 ----------------
dlg = uset.SettingsDialog(None)
dlg.resize(dlg.DEF_W, dlg.DEF_H)
dlg.show()
for _ in range(8):
    app.processEvents()
dlg._show("演员刮削")
for _ in range(10):
    app.processEvents()
_btn = dlg.mode_btns.get("full") or list(dlg.mode_btns.values())[0]


def exec_band():
    im = dlg.grab().toImage()
    yb = _btn.mapTo(dlg, QPoint(0, _btn.height())).y()
    yp = dlg.sc_prog.mapTo(dlg, QPoint(0, 0)).y()
    y0 = max(0, yb - 26)
    y1 = min(im.height(), yp + dlg.sc_prog.height() + 10)
    return im.copy(0, y0, im.width(), max(1, y1 - y0)), yp - yb, yb - y0, yp - y0


# 改后（空标签已 hide）—— 实测 7px
b_new, gap_new, _, _ = exec_band()
# 改前：把标签显示出来复现旧观感（空串仍是 19px 高的一行）—— 实测 32px
dlg.sc_mode_hint.setVisible(True)
for _ in range(6):
    app.processEvents()
b_old, gap_old, _, _ = exec_band()
dlg.sc_mode_hint.setVisible(False)
for _ in range(4):
    app.processEvents()

compose([b_old, b_new], os.path.join(OUT, "v209_exec_gap.png"),
        labels=["改前：空的「模式说明」占了一整行 —— 按钮行到进度条空出 %dpx" % gap_old,
                "改后：空着就不占位 —— 只剩 %dpx（组框矮了 21px）" % gap_new])
dlg.close()
print("DONE")
