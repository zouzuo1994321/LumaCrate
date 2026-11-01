# -*- coding: utf-8 -*-
"""v2.0.6 真机验收要用的坐标（离屏算，输出 JSON）。

只算本轮**新增/改动**的三处：
  1. 工具窗「重复检测」页 —— 结果树下新增的四枚按钮 + 树本身的矩形
     （真机验收要点它们，验证「没选中时全灰 / 选中后可点」）。
  2. 详情页「评分」按钮 —— 金色 / 橙色加粗两种状态的中心点。
  3. 详情页第一枚标签芯片的 ×、第一位演职员的 ×（真机点一下，看库里的行是否真的没了）。

布局前提与 ui_coords.py 相同：主窗 1920×1080、工具窗 1320×960、中文字体已注册。
"""
import json
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QPushButton, QWidget   # noqa: E402
from PySide6.QtGui import QFontDatabase                            # noqa: E402
from PySide6.QtCore import Qt, QPoint, QRect                       # noqa: E402

OUT = "C:/Users/zouzu/AppData/Local/Temp/lmc_coords_v206.json"

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db      # noqa: E402
import config as cfg       # noqa: E402

TMP = tempfile.mkdtemp(prefix="lmc_coords_v206_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow      # noqa: E402
import ui_settings as uis               # noqa: E402


def center(widget, ref):
    p = widget.mapTo(ref, QPoint(widget.width() // 2, widget.height() // 2))
    return [int(p.x()), int(p.y())]


def rect_of(widget, ref):
    p = widget.mapTo(ref, QPoint(0, 0))
    return [int(p.x()), int(p.y()), int(widget.width()), int(widget.height())]


res = {}

# ---------------- 主窗 + 详情页 ----------------
CAS = os.path.join(TMP, "cast")
os.makedirs(CAS, exist_ok=True)
_cast = [("检测女优", "Actor", "Actor"), ("检测男优", "Actor", "Actor"),
         ("检测导演", "Director", "Director")]
_mid = db.insert_media(title="坐标测量用片", kind="movie", year=2024, rating=7.5,
                       file_path=os.path.join(TMP, "x.mp4"), library="坐标库",
                       sort_title="zuobiao", tags="标签甲,标签乙,标签丙")
_people = []
for _i, (_n, _r, _cr) in enumerate(_cast):
    _pid = db.upsert_person(_n, _r)
    db.link_media_person(_mid, _pid, _cr, _i)
    _people.append(_pid)
_row = db.get_media(_mid)
print("[预置] media id=%s people=%s" % (_mid, _people))

win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
res["main_size"] = [win.width(), win.height()]

win._open_media(dict(_row))
app.processEvents()
for _ in range(3):
    app.processEvents()

hero = None
for w in win.findChildren(QWidget):
    if w.__class__.__name__ == "HeroView":
        hero = w
        break
res["hero_found"] = hero is not None
if hero is not None:
    rate = getattr(hero, "_rate_btn", None)
    res["rate_btn"] = center(rate, win) if rate is not None else None
    res["rate_btn_rect"] = rect_of(rate, win) if rate is not None else None
    # 标签芯片的 × ：TagChip 容器里那个 16×16 的按钮
    chips = []
    for w in hero.findChildren(QWidget):
        if w.objectName() == "TagChip":
            chips.append(w)
    res["tag_chips"] = [rect_of(c, win) for c in chips]
    dels = []
    for c in chips:
        for b in c.findChildren(QPushButton):
            dels.append(center(b, win))
    res["tag_x_btns"] = dels
    # 演职员的 × ：CastAvatar 里那个 18×18 的按钮
    avs = []
    for w in hero.findChildren(QWidget):
        if w.__class__.__name__ == "CastAvatar":
            avs.append(w)
    res["cast_avatars"] = [rect_of(a, win) for a in avs]
    cxs = []
    for a in avs:
        btns = a.findChildren(QPushButton)
        cxs.append(center(btns[-1], win) if btns else None)
    res["cast_x_btns"] = cxs
    # 「演职人员信息」旁边的 ＋（添加）
    add_btn = None
    for b in hero.findChildren(QPushButton):
        if b.text() == "＋" and "添加一位" in (b.toolTip() or ""):
            add_btn = b
            break
    res["cast_add_btn"] = center(add_btn, win) if add_btn is not None else None

# ---------------- 工具窗「重复检测」 ----------------
class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


uis.SettingsDialog.screen = lambda self: _FakeScr()
dlg = uis.SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
app.processEvents()
res["dialog_size"] = [dlg.width(), dlg.height()]
res["dedupe_nav"] = center(dlg.sub_btns["重复检测"], dlg)

dlg._show("重复检测")
app.processEvents()
for _k in ("dd_play", "dd_reveal", "dd_open_dir", "dd_del"):
    _w = getattr(dlg, _k, None)
    res[_k] = center(_w, dlg) if _w is not None else None
    if _w is None:
        print("[警告] dlg.%s 不存在" % _k)
res["dd_tree"] = rect_of(dlg.dd_tree, dlg)
res["dd_status"] = rect_of(dlg.dd_status, dlg)
_start = [b for b in dlg.findChildren(QPushButton) if b.text() == "开始检测"]
res["dd_start_btn"] = center(_start[0], dlg) if _start else None

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
