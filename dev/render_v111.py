# -*- coding: utf-8 -*-
"""v1.11.1 定向渲染校验：把用户 5 条反馈对应的界面逐块渲染成 PNG。

只读 + 纯离屏，数据库走临时文件（**不碰** index_data/media_center.db）。

产出（dev/screenshots_v111/）：
  01_topbar.png          顶栏 ← → 按钮（反馈 3：字形是否可见）
  02_settings_nav.png    设置·个性化设置整页（反馈 4：导航菜单 ↑↓）
  03_settings_cards.png  「内容卡片」分组 6 项开关（反馈 2）
  04_settings_scraper.png 演员刮削页（数据源 ↑↓ / 测试 / 修复历史资料）
  05_toggle_zoom.png     开关三态放大 4×（反馈 5：轨道色 + 圆点位置随进度）
  06_poster_all_on.png   影片卡：内容卡片全开
  07_poster_all_off.png  影片卡：内容卡片全关（不留空白）
  08_actor_card.png      演员卡：真机刮削样本数据（反馈 1）
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QGroupBox, QFrame
from PySide6.QtGui import QImage, QColor, QPainter, QFontDatabase, QFont
from PySide6.QtCore import Qt, QPoint

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
           "C:/Windows/Fonts/simsun.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei UI", 9))

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_r111_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

# 离屏不需要磨砂玻璃（真机才有的原生效果），挡掉以免原生调用
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

import main_window as mw
from main_window import MainWindow, PosterCard, ActorCard, load_style
from ui_settings import SettingsDialog, ToggleSwitch

OUT = os.path.join(_HERE, "screenshots_v111")
os.makedirs(OUT, exist_ok=True)
made = []


def save(widget, name, pad=0):
    """把控件渲染到 PNG（先填底色：未覆盖区域否则是未初始化内存）。"""
    w = widget.width() + pad * 2
    h = widget.height() + pad * 2
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("#14100e"))
    widget.render(img, QPoint(pad, pad))
    path = os.path.join(OUT, name)
    img.save(path)
    made.append((name, w, h))
    return path


def show(w, ww, hh):
    w.setAttribute(Qt.WA_DontShowOnScreen, True)
    w.resize(ww, hh)
    w.show()
    app.processEvents()
    return w


win = MainWindow()
show(win, 1920, 1080)
app.processEvents()

# ---------------------------------------------------------- 01 顶栏
bar = win.findChild(QFrame, "TopBar")
save(bar, "01_topbar.png", pad=6)

# ---------------------------------------------------------- 设置对话框
dlg = SettingsDialog(win)
show(dlg, 1000, 940)
app.processEvents()

save(dlg, "02_settings_nav.png")

cards_gb = None
for g in dlg.findChildren(QGroupBox):
    if "内容卡片" in g.title():
        cards_gb = g
if cards_gb is not None:
    save(cards_gb, "03_settings_cards.png", pad=4)

dlg._show("演员刮削")
app.processEvents()
save(dlg, "04_settings_scraper.png")

# ---------------------------------------------------------- 05 开关三态放大
sw_off = ToggleSwitch(checked=False)
sw_mid = ToggleSwitch(checked=False)
sw_mid.set_pos(0.5)
sw_on = ToggleSwitch(checked=True)
Z = 4
strip = QImage((46 * 3 + 16 * 4) * Z, (26 + 16) * Z, QImage.Format_RGB32)
strip.fill(QColor("#14100e"))
p = QPainter(strip)
for i, (sw, label_t) in enumerate(((sw_off, 0.0), (sw_mid, 0.5), (sw_on, 1.0))):
    sub = QImage(46, 26, QImage.Format_RGB32)
    sub.fill(QColor("#14100e"))
    sw.render(sub, QPoint(0, 0))
    x = (16 + i * (46 + 16)) * Z
    p.drawImage(x, 8 * Z, sub.scaled(46 * Z, 26 * Z, Qt.IgnoreAspectRatio, Qt.FastTransformation))
p.end()
strip.save(os.path.join(OUT, "05_toggle_zoom.png"))
made.append(("05_toggle_zoom.png", strip.width(), strip.height()))

# ---------------------------------------------------------- 06/07 影片卡
OK_MEDIA = {"title": "沙丘：第二部 IMAX 特別版", "year": 2024, "rating": 8.6,
            "quality": "2160P HDR", "poster": None, "thumb": None}


def rebuild_cards(**flags):
    cc = dict(cfg.DEFAULT_CONTENT_CARDS)
    cc.update(flags)
    s = cfg.get_settings()
    s.content_cards = cc
    card = PosterCard(OK_MEDIA, lambda *a: None,
                      actor_text="提莫西·查拉梅 / 赞达亚 / 丽贝卡·弗格森",
                      director_text="丹尼斯·维伦纽瓦")
    show(card, card.width(), card.height())
    app.processEvents()
    return card


c_on = rebuild_cards()
save(c_on, "06_poster_all_on.png", pad=6)
c_off = rebuild_cards(show_rating=False, show_year=False, show_quality=False,
                      show_actors=False, show_directors=False)
save(c_off, "07_poster_all_off.png", pad=6)

# ---------------------------------------------------------- 08 演员卡（真机样本）
PERSON = {
    "id": 1, "name": "音琴るい", "alias": "", "status": "现役",
    "birthday": "1994-01-16", "favorite": 0, "pinned": 0,
    "thumb": None, "photo_path": None,
    "meta": {"身高": "158cm", "尺寸": "T158 / B92(E) / W58 / H89",
             "出身地": "山梨県", "事务所": "ACT(アクト)",
             "出演期間": "2025年 -", "出道作": "テスト（2025年09月05日）",
             "罩杯": "E"},
    "bio": "生日 1994-01-16 | 身高 158cm | 出身地 山梨県 | 三围 — | 胸围 —",
}
ac = ActorCard(PERSON, lambda *a: None, lambda *a: None, lambda *a: None,
               lambda *a: None, win)
show(ac, ac.width(), ac.height())
app.processEvents()
save(ac, "08_actor_card.png", pad=6)

print("输出目录:", OUT)
for n, w, h in made:
    print("  %-24s %4d x %4d" % (n, w, h))
print("done, %d files" % len(made))
