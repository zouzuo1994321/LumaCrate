# -*- coding: utf-8 -*-
"""v1.19.1 布局验证：反馈 1（详情面板随窗口宽度自适应，无横向滚动条）/ 反馈 2（四按钮移到标题上方）

离屏 QApplication；注册中文字体后建控件，避免 sizeHint 虚高误判。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = r"Z:\【01】自研软件\【26-19】本地影视中心\src"
sys.path.insert(0, SRC)

TMP = tempfile.mkdtemp(prefix="lmc_v1191_")
DBP = os.path.join(TMP, "index_data", "media_center.db")

import database as db
db.db_path = lambda: DBP
db.init_db()

from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import QPoint

app = QApplication.instance() or QApplication(sys.argv)

# 注册中文字体（否则 offscreen 下 sizeHint 虚高）
FONT = r"C:\Windows\Fonts\msyh.ttc"
if os.path.exists(FONT):
    QFontDatabase.addApplicationFont(FONT)
    app.setFont(QFont("Microsoft YaHei", 9))

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  -> {detail}" if detail else ""))


from ui_hero import HeroView, FlowLayout

# ---------- 反馈 1：FlowLayout 会随宽度换行 ----------
host = QWidget()
fl = FlowLayout(host, spacing=8)
from PySide6.QtWidgets import QFrame
for i in range(8):
    f = QFrame()
    f.setFixedSize(120, 40)
    fl.addWidget(f)
h_wide = fl.heightForWidth(1200)
h_narrow = fl.heightForWidth(300)
check("1.FlowLayout 窄宽度换行变高", h_narrow > h_wide, f"wide={h_wide} narrow={h_narrow}")
check("1.FlowLayout minimumSize 很小(可压缩)", fl.minimumSize().width() <= 130,
      f"minW={fl.minimumSize().width()}")

# ---------- 反馈 1：窄容器下 HeroView 不产生横向滚动条 ----------
LONG_TITLE = "MXGS-1446 【FANZA限定】オフィス相部屋 NTR ～絶対にヤりたくないのに新人と二人きり～"
media = {
    "id": None,
    "title": LONG_TITLE,
    "kind": "movie",
    "year": 2026,
    "country": "JP",
    "rating": 4.6,
    "user_rating": 8.0,
    "genres": "剧情,爱情,职场,剧情,爱情,职场",
    "runtime": "02:11:00",
    "certification": "R-18",
    "quality": "4K,HDR10,Atmos,1080P",
    "plot": "日韩限定作品。" * 20,
    "file_path": r"Z:\【30】VR视频\MXGS-1446【FANZA限定】オフィス相部屋NTR\MXGS-1446-4K-cd1.mp4",
    "file_size": 8 * 1024 ** 3,
    "added_date": "2026-09-17",
    "studio": "SOD Create-スーパー長いスタジオ名テスト",
    "library": "Jav-library",
    "collection": "NTR系列",
    "tmdb_id": None,
    "fanart": None,
    "poster": None,
    "parent_id": None,
}

hero = HeroView(media, on_open_actor=None, on_back=None)
hero.resize(430, 900)
hero.show()
app.processEvents()
vb = hero.viewport().width()
hs = hero.horizontalScrollBar()
check("1.窄面板(430)无横向滚动条", hs.maximum() == 0, f"viewportW={vb} hmax={hs.maximum()}")
minw = hero.widget().minimumSizeHint().width()
check("1.内容最小宽度 <= 面板宽度", minw <= vb, f"contentMinW={minw} viewportW={vb}")

# ---------- 反馈 2：播放/收藏/评分/更多 在标题上方 ----------
btns = {b.text(): b for b in hero.findChildren(QPushButton)}
play = btns.get("播放")
title_lbl = None
for l in hero.findChildren(QLabel):
    if (l.text() or "").startswith("MXGS-1446"):
        title_lbl = l
        break
check("2.存在「播放」按钮", play is not None, f"btns={list(btns)}")
check("2.存在标题标签", title_lbl is not None, "")
if play is not None and title_lbl is not None:
    y_play = play.mapTo(hero.widget(), QPoint(0, 0)).y()
    y_title = title_lbl.mapTo(hero.widget(), QPoint(0, 0)).y()
    check("2.播放按钮在标题上方", y_play < y_title, f"y_play={y_play} y_title={y_title}")
    for name in ("收藏", "评分", "更多"):
        b = btns.get(name)
        if b is not None:
            yb = b.mapTo(hero.widget(), QPoint(0, 0)).y()
            check(f"2.{name}按钮在标题上方", yb < y_title, f"y={yb} y_title={y_title}")
check("2.标题可自动换行", bool(title_lbl is not None and title_lbl.wordWrap()),
      f"wordWrap={title_lbl.wordWrap() if title_lbl else None}")

# ---------- 反馈 2：宽面板下四按钮仍同行于标题上方 ----------
hero.resize(1500, 900)
app.processEvents()
if play is not None and title_lbl is not None:
    y_play = play.mapTo(hero.widget(), QPoint(0, 0)).y()
    y_title = title_lbl.mapTo(hero.widget(), QPoint(0, 0)).y()
    check("2.宽面板下仍在标题上方", y_play < y_title, f"y_play={y_play} y_title={y_title}")

failed = [n for n, ok, _ in results if not ok]
print("\n==== 结果 ====")
print("ALL PASS" if not failed else f"FAILED: {failed}")
sys.exit(0 if not failed else 1)
