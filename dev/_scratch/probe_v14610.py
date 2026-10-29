# -*- coding: utf-8 -*-
"""v1.46.10 探针：①演职人员信息并到「基本信息」右侧 ②右键搜索框可激活（输入法前提）。"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v14610"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QFontDatabase, QImage, QMouseEvent
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
DB = os.path.join(DBDIR, "media_center.db")
if os.path.exists(DB):
    DB = os.path.join(DBDIR, "media_center_%d.db" % __import__("time").time())
db.db_path = lambda: DB
db.init_db()
db._MEDIA_COLS = None

MOV = os.path.join(TMP, "LMC-900")
os.makedirs(os.path.join(MOV, "extrafanart"), exist_ok=True)
for i in range(4):
    im = Image.new("RGB", (320, 180), (60 + i * 20, 34, 28))
    im.save(os.path.join(MOV, "extrafanart", "f%d.jpg" % i))
fan = Image.new("RGB", (1200, 500), (52, 38, 30))
d = ImageDraw.Draw(fan)
d.ellipse([700, 40, 1100, 440], fill=(180, 130, 70))
FAN = os.path.join(MOV, "fanart.jpg")
fan.save(FAN)
POS = os.path.join(MOV, "poster.jpg")
fan.crop((760, 60, 1000, 420)).resize((300, 450)).save(POS)

VIDEO = os.path.join(MOV, "LMC-900.mp4")
open(VIDEO, "wb").write(b"\x00" * 512)

mid = db.upsert_media_by_path(
    mode="overwrite", kind="movie", title="LMC-900 三栏布局验证", year=2026,
    plot="简介一行。", file_path=VIDEO, library="演示库", genres="剧情",
    tags="已看", file_size=512, poster=POS, fanart=FAN,
    certification="JP-18+", runtime="01:57:00", studio="ディープス",
)

# 造 3 位演职人员
for i, (nm, role) in enumerate([("枳アリス", "Actor"), ("赤井彗星", "Director"), ("三佳詩", "Actor")]):
    pid = db.upsert_person(nm, role_type=role)
    db.link_media_person(mid, pid, "", i)

db.update_media_fields(mid, poster=POS, fanart=FAN, tags="已看")
row = db.get_media(mid)
cast = db.get_cast(mid)
print("cast:", [(c.get("name"), c.get("role_type")) for c in cast], flush=True)

mw.load_style(app)


def settle(n=25):
    for _ in range(n):
        app.processEvents()


def img_of(w):
    im = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    iw, ih = im.width(), im.height()
    bg = Image.new("RGB", (iw, ih), (16, 13, 11))
    raw = Image.frombytes("RGBA", (iw, ih), bytes(im.constBits()))
    return Image.alpha_composite(bg.convert("RGBA"), raw).convert("RGB")


FAILS = []


def check(name, ok, detail=""):
    print(("[OK]   " if ok else "[FAIL] ") + name + ("  " + str(detail) if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


hv = ui_hero.HeroView(dict(row))
hv.resize(1200, 1500)
hv.show()
settle(30)

# ---- ① 布局 ----
intro_h_box = hv._cast_layout
check("① 演职人员区块存在", hv._cast_box is not None)
check("① 它在横向布局（intro）里", intro_h_box is not None and intro_h_box.indexOf(hv._cast_box) >= 0,
      intro_h_box.indexOf(hv._cast_box) if intro_h_box else None)
check("① 主体竖向布局里不再有它",
      hv._body_layout.indexOf(hv._cast_box) < 0)

hero_win = hv.widget()
cast_geo = hv._cast_box.mapTo(hero_win, QPoint(0, 0))
poster = None
facts = None
for w in hv.findChildren(ui_hero.QLabel):
    if w.text() == "基本信息":
        facts = w
    if w.pixmap() is not None and not w.pixmap().isNull() and w.width() == 150 and w.height() == 225:
        poster = w

check("① 找得到海报与「基本信息」标题", poster is not None and facts is not None)
if poster is not None and facts is not None:
    poster_x = poster.mapTo(hero_win, QPoint(0, 0)).x()
    facts_x = facts.mapTo(hero_win, QPoint(0, 0)).x()
    facts_y = facts.mapTo(hero_win, QPoint(0, 0)).y()
    cast_x = cast_geo.x()
    cast_y = cast_geo.y()
    print("几何: poster.x=%d facts.x=%d facts.y=%d cast.x=%d cast.y=%d" %
          (poster_x, facts_x, facts_y, cast_x, cast_y), flush=True)
    check("① 演员栏在「基本信息」右侧（不是下面）",
          cast_x > facts_x + 100 and abs(cast_y - facts_y) <= 24,
          "cast_x=%d facts_x=%d dy=%d" % (cast_x, facts_x, cast_y - facts_y))
    check("① 顺序：海报 → 基本信息 → 演职人员",
          poster_x < facts_x < cast_x)
    check("① 演员栏没有挤到海报下方（同一行）", cast_y < poster.mapTo(hero_win, QPoint(0, 0)).y() + 225)

# 文件信息仍在底部：它应是主体布局里的最后几项之一，且 y 在演员栏下方
file_lbl = None
for w in hv.findChildren(ui_hero.QLabel):
    if w.text() == "文件信息":
        file_lbl = w
check("① 「文件信息」仍在（底部）", file_lbl is not None)
if file_lbl is not None:
    fy = file_lbl.mapTo(hero_win, QPoint(0, 0)).y()
    check("① 文件信息在演员栏下方", fy > cast_geo.y() + 60, "file.y=%d cast.y=%d" % (fy, cast_geo.y()))

im = img_of(hv)
im.save(os.path.join(TMP, "hero_intro_v14610.png"))
im.crop((0, 430, im.width, 430 + 420)).save(os.path.join(TMP, "intro_only.png"))

# 窄面板（首页右侧详情栏约 700px）：不能撑出页面级横向滚动条
hv.resize(700, 1400)
settle(25)
check("① 700px 窄栏没有横向滚动条",
      hv.horizontalScrollBar().maximum() == 0, hv.horizontalScrollBar().maximum())
narrow = img_of(hv)
narrow.crop((0, 430, narrow.width, 430 + 430)).save(os.path.join(TMP, "intro_narrow.png"))

# 右键替换演员后要能就地重建（布局换了地方，索引必须还在同一个 HBox 里）
_old_box = hv._cast_box
_idx_before = hv._cast_layout.indexOf(_old_box)
hv._refresh_cast()
settle(10)
check("① 右键替换后就地重建仍在同一栏位",
      hv._cast_box is not _old_box and hv._cast_layout.indexOf(hv._cast_box) == _idx_before,
      "idx=%s" % hv._cast_layout.indexOf(hv._cast_box))

# ---- ② 右键搜索框：能激活 + 输入法可用 ----
dlg = ui_hero.PersonSearchDialog(initial="", old_name="八森わかな", parent=hv.window())
flags = dlg.windowFlags()
# Qt.Popup 的枚举值是 0x9（Window|Popup），直接 `flags & Qt.Popup` 会被 Window 位干扰，
# 必须先用 WindowType_Mask 取「基类型」再比。
_base = int(flags) & int(Qt.WindowType_Mask)
check("② 基类型是 Dialog，不是 Popup（Popup 不激活 → 输入法挂不上）",
      _base == int(Qt.Dialog) and _base != (int(Qt.Popup) & int(Qt.WindowType_Mask)),
      "base=0x%x flags=0x%x" % (_base, int(flags)))
check("② 无边框保留", (int(flags) & int(Qt.FramelessWindowHint)) != 0)
check("② 窗口允许激活（没有被 WA_ShowWithoutActivating 关掉）",
      not dlg.testAttribute(Qt.WA_ShowWithoutActivating))
check("② 输入框启用了输入法事件",
      dlg._edit.testAttribute(Qt.WA_InputMethodEnabled)
      and dlg._edit.inputMethodHints() == Qt.ImhNone,
      "attr=%s hints=%s" % (dlg._edit.testAttribute(Qt.WA_InputMethodEnabled),
                            dlg._edit.inputMethodHints()))

dlg.move_to(QPoint(600, 400))
dlg.show()
settle(15)
check("② 显示后装了「点外面关闭」过滤器", dlg._outside is not None)
check("② 输入框拿到焦点", dlg._edit.hasFocus(), dlg._edit.hasFocus())

# 点面板外面 → 关闭
before = dlg.isVisible()
ev = QMouseEvent(QEvent.MouseButtonPress, QPoint(-50, -50), QPoint(-50, -50),
                 Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
dlg._outside.eventFilter(dlg, ev)
settle(5)
check("② 点面板外面会关闭（原本 Qt.Popup 自带的能力已补回）",
      before and not dlg.isVisible(), "before=%s after=%s" % (before, dlg.isVisible()))
check("② 关闭后过滤器已摘除", dlg._outside is None)

# 中文输入走的是 inputMethodEvent：只要控件接受输入法事件就不会被 Qt 丢掉
check("② 源码里不再用 Qt.Popup 做输入弹层",
      "Qt.Popup | Qt.FramelessWindowHint" not in open(
          os.path.join(ROOT, "src", "ui_hero.py"), encoding="utf-8").read())

print("FAILS:", FAILS, flush=True)
print("PROBE_V14610_DONE", flush=True)
