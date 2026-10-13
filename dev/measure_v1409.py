# -*- coding: utf-8 -*-
"""v1.40.9 量化探针：测 画像概览 各块高度 + 演员刮削 子模块是否随窗口变化。
离屏 + 假屏幕 2560x1392。用量，不截图。
"""
import os, sys
ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication, QScrollArea, QGroupBox
from PySide6.QtCore import QRect
from PySide6.QtGui import QFontDatabase

app = QApplication([])
try:
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
except Exception:
    pass

import main_window as mw
import ui_settings as uis

class _FakeScr:
    def availableGeometry(self): return QRect(0, 0, 2560, 1392)
    def geometry(self): return QRect(0, 0, 2560, 1440)

uis.SettingsDialog.screen = lambda self: _FakeScr()
mw.load_style(app)

d = uis.SettingsDialog()
d.show()
for _ in range(10):
    app.processEvents()

def settle(n=12):
    for _ in range(n):
        app.processEvents()

def child_groups(page):
    out = {}
    for w in page.findChildren(QGroupBox):
        t = w.title().strip()
        if t:
            out.setdefault(t, w)
    return out

def pagesc(name):
    return getattr(d, {"画像概览": "_pg_insight", "演员刮削": "_pg_scraper"}[name])

# ===== 画像概览：注入合成数据，量各块高度 =====
d._show("画像概览")
settle(10)
ov = dict(scope="全部媒体库", media=48000, favorite=10000, actors=5000,
          actor_links=90000, directors=3000, director_links=40000, series=2000,
          studios=500, tags=3000, avg_rating=7.52, total_hours=90000,
          total_size=50_000_000_000)
fake = {
    "overview": ov,
    "line": "这是一句合成的画像总评，用来把一句话画像组框撑到接近真实的行数。",
    "radar": [("剧情", 0.8, "强"), ("演员", 0.6, "中"), ("画质", 0.7, "中"),
              ("评分", 0.9, "强"), ("时长", 0.5, "中"), ("年份", 0.4, "弱"),
              ("系列", 0.6, "中"), ("片商", 0.5, "中")],
    "tags": [("剧情", 3000), ("爱情", 2800), ("喜剧", 2500), ("动作", 2200),
             ("科幻", 2000), ("悬疑", 1800), ("治愈", 1600), ("运动", 1400),
             ("音乐", 1200), ("恐怖", 1000), ("纪录", 900), ("奇幻", 800),
             ("冒险", 700), ("战争", 600), ("历史", 500), ("犯罪", 400)],
    "actors": [("某演员A", 900), ("某演员B", 800), ("某演员C", 700), ("某演员D", 600),
               ("某演员E", 500), ("某演员F", 400), ("某演员G", 300), ("某演员H", 200),
               ("某演员I", 150), ("某演员J", 120), ("某演员K", 100), ("某演员L", 90),
               ("某演员M", 80), ("某演员N", 70), ("某演员O", 60), ("某演员P", 50)],
    "directors": [("导演A", 400), ("导演B", 350), ("导演C", 300), ("导演D", 250),
                  ("导演E", 200), ("导演F", 150), ("导演G", 120), ("导演H", 100),
                  ("导演I", 90), ("导演J", 80), ("导演K", 70), ("导演L", 60),
                  ("导演M", 50), ("导演N", 40), ("导演O", 30), ("导演P", 20)],
    "studios": [("片商A", 500), ("片商B", 450), ("片商C", 400), ("片商D", 350),
                ("片商E", 300), ("片商F", 250), ("片商G", 200), ("片商H", 150),
                ("片商I", 120), ("片商J", 100), ("片商K", 90), ("片商L", 80),
                ("片商M", 70), ("片商N", 60), ("片商O", 50), ("片商P", 40)],
    "series": [("系列A", 300), ("系列B", 280), ("系列C", 260), ("系列D", 240),
               ("系列E", 220), ("系列F", 200), ("系列G", 180), ("系列H", 160),
               ("系列I", 140), ("系列J", 120), ("系列K", 100), ("系列L", 90),
               ("系列M", 80), ("系列N", 70), ("系列O", 60), ("系列P", 50)],
    "dist": {
        "画质": [("1080P", 30000), ("4K", 12000), ("720P", 4000), ("2160P", 2000),
                 ("1080P60", 1000), ("原盘", 800), ("HDR", 600), ("SDR", 500),
                 ("480P", 300), ("2K", 200), ("360P", 100), ("8K", 80),
                 ("1080I", 60), ("准4K", 50), ("480I", 40), ("其他", 30)],
        "评分": [("9+", 5000), ("8+", 9000), ("7+", 12000), ("6+", 8000),
                 ("5+", 4000), ("4+", 2000), ("3+", 1000), ("2+", 500),
                 ("1+", 300), ("0+", 200), ("8.5+", 400), ("9.5+", 300),
                 ("7.5+", 350), ("6.5+", 250), ("5.5+", 150), ("其他", 100)],
        "时长": [("90-120", 15000), ("60-90", 12000), ("120-150", 9000),
                 ("150-180", 6000), ("30-60", 5000), ("180+", 4000),
                 ("<30", 2000), ("120-", 1500), ("90-", 1200), ("60-", 1000),
                 ("45-", 800), ("75-", 700), ("105-", 600), ("135-", 500),
                 ("165-", 400), ("其他", 300)],
        "年份": [("2020", 8000), ("2021", 7500), ("2022", 7000), ("2023", 6500),
                 ("2024", 6000), ("2019", 5500), ("2018", 5000), ("2017", 4500),
                 ("2016", 4000), ("2015", 3500), ("2014", 3000), ("2013", 2500),
                 ("2012", 2000), ("2011", 1500), ("2010", 1000), ("更久", 800)],
        "入库月": [("1月", 4000), ("2月", 3500), ("3月", 4500), ("4月", 5000),
                   ("5月", 5500), ("6月", 6000), ("7月", 6500), ("8月", 6000),
                   ("9月", 5500), ("10月", 5000), ("11月", 4500), ("12月", 7000),
                   ("旺季", 3000), ("淡季", 2500), ("促销月", 2000), ("其他", 1500)],
    },
    "cooc": [(("剧情", "爱情"), 1200), (("喜剧", "治愈"), 900), (("动作", "科幻"), 800),
            (("悬疑", "犯罪"), 700), (("运动", "青春"), 600), (("音乐", "治愈"), 500),
            (("奇幻", "冒险"), 400), (("战争", "历史"), 300), (("恐怖", "惊悚"), 200),
            (("纪录", "真实"), 100)],
}
d._insight_data = fake
d._on_insight_done(fake)
settle(30)
sc = pagesc("画像概览")
pg = sc.widget().layout().itemAt(0).widget()
need = uis.SettingsDialog._content_need_height(pg)
print("=== 画像概览（合成数据，16 条/列，最满）===")
print("画布最小高 min=%d  内容需求 need=%d  视口高=%d" % (
    sc.widget().minimumHeight(), need, sc.viewport().height()))
print("页面 sizeHint 高=%d  minimumSizeHint 高=%d" % (pg.sizeHint().height(), pg.minimumSizeHint().height()))
gs = child_groups(pg)
for t, w in gs.items():
    print("  组框[%s] h=%d  (子项数=%d)" % (t, w.height(), w.layout().count() if w.layout() else -1))
# 顶层布局子项高度（含非组框行）
print("  顶层布局子项数=%d" % pg.layout().count())

# ===== 演员刮削：量子模块在 窗口960 vs 1300 时的高度 =====
print()
print("=== 演员刮削：子模块高度是否随窗口变化 ===")
d._show("演员刮削")
settle(10)
sc = pagesc("演员刮削")
pg = sc.widget().layout().itemAt(0).widget()

def measure(tag):
    d.resize(1320, 960 if tag == "h960" else 1300)
    settle(15)
    gs = child_groups(pg)
    print("[%s] 窗口 %dx%d  画布min=%d 视口=%d" % (
        tag, d.width(), d.height(), sc.widget().minimumHeight(), sc.viewport().height()))
    for t, w in gs.items():
        print("    [%s] h=%d" % (t, w.height()))

measure("h960")
measure("h1300")
measure("h960")
print()
print("done")
sys.exit(0)
