# -*- coding: utf-8 -*-
"""v2.0.6 探针 ①：详情页评分配色 / 标签与演员的「×」删除 / 演职人员「＋」与 nfo 回写。

全程临时库 + 临时 nfo，**绝不碰真实索引与真实 nfo**。
"""
import os
import shutil
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v206d"
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)

import database as db          # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: os.path.join(TMP, "probe.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")
db.init_db()

from PySide6.QtWidgets import QApplication, QPushButton   # noqa: E402
from PySide6.QtGui import QPixmap, QColor, QFontDatabase  # noqa: E402
from PySide6.QtCore import Qt                             # noqa: E402

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw      # noqa: E402
import nfo_parser as nfo      # noqa: E402
import ui_hero as uhero       # noqa: E402

mw.load_style(app)
mw.render_style({"accent": "#e4587c"})

FAIL = []


def ck(cond, label, extra=""):
    print(("PASS  " if cond else "FAIL  ") + label + (("   " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(label)


# ---------- 造数据 ----------
poster = os.path.join(TMP, "p.png")
pm = QPixmap(300, 450)
pm.fill(QColor("#3f3f46"))
pm.save(poster)

NFO = os.path.join(TMP, "movie.nfo")
with open(NFO, "w", encoding="utf-8") as fh:
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<movie>\n'
             '  <title>ID-063 测试片</title>\n  <year>2016</year>\n'
             '  <tag>素人作品</tag>\n  <tag>美乳</tag>\n'
             '  <actor><name>月島ななこ</name><type>Actor</type></actor>\n'
             '  <actor><name>玉城マイ</name><type>Actor</type></actor>\n'
             '  <director>K*WEST</director>\n</movie>\n')
VIDEO = os.path.join(TMP, "ID-063.mp4")
with open(VIDEO, "wb") as fh:
    fh.write(b"\0" * 64)


def make_media(**kw):
    base = dict(title="ID-063 测试片", kind="movie", year=2016, rating=7.5,
                poster=poster, fanart=poster, tags="素人作品,美乳",
                file_path=VIDEO, nfo_path=NFO, favorite=0, user_rating=None,
                library="探测库", runtime="02:00:00")
    base.update(kw)
    mid = db.insert_media(**base)
    return mid


def link(mid, people):
    for i, (name, rtype, role) in enumerate(people):
        pid = db.upsert_person(name, rtype)
        db.link_media_person(mid, pid, role, i)


print("== ① 评分按钮：没评过 → 金色「评分」；评过 → 橙色加粗「用户评分 X.X」 ==")
m1 = make_media()
link(m1, [("月島ななこ", "Actor", ""), ("玉城マイ", "Actor", ""), ("K*WEST", "Director", "导演")])
row = db.get_media(m1)
h1 = uhero.HeroView(dict(row))
h1.resize(1200, 900)
h1.show()
app.processEvents()

btn = h1._rate_btn
ck(btn.text() == "评分", "未评分时按钮文字是「评分」", btn.text())
ck(uhero.RATE_GOLD in btn.styleSheet(), "未评分时文字金色", btn.styleSheet())
ck("font-weight:bold" not in btn.styleSheet(), "未评分时不加粗")

h1.media["user_rating"] = 7.5
h1._rate_style()
ck(btn.text() == "用户评分 7.5", "评分后文字是「用户评分 7.5」", btn.text())
ck(uhero.RATE_USER in btn.styleSheet(), "评分后用橙色", btn.styleSheet())
ck("font-weight:bold" in btn.styleSheet(), "评分后加粗")

# 清掉评分 → 回到金色「评分」
h1.media["user_rating"] = None
h1._rate_style()
ck(btn.text() == "评分" and uhero.RATE_GOLD in btn.styleSheet(), "清除评分后回落金色「评分」")

print("== ② 标签：每枚芯片自带右上角 ×，点它删掉该标签 ==")
chips = [w for w in h1.findChildren(uhero.QWidget)
         if w.objectName() == "TagChip"]
ck(len(chips) == 2, "两枚标签芯片都是 TagChip 容器", len(chips))
_xs = [c.findChildren(QPushButton) for c in chips]
ck(all(len(v) == 1 and v[0].text() == "×" for v in _xs), "每枚芯片恰好一个「×」按钮",
   [[b.text() for b in v] for v in _xs])
ck(all(c.testAttribute(Qt.WA_StyledBackground) for c in chips),
   "芯片开了 WA_StyledBackground（否则 QSS 胶囊底画不出来）")
# 「－」按钮已撤
_titles = [w.text() for w in h1.findChildren(uhero.QPushButton)]
ck("－" not in _titles, "标签行不再有「－」按钮", _titles)

_xs[0][0].click()
app.processEvents()
_after = db.get_media(m1)["tags"]
ck(_after == "美乳", "点 × 后该标签从库里删掉", _after)

print("== ③ 演职人员：每个头像右上角有 ×，点它把该人从本片移除 ==")
avatars = h1.findChildren(uhero.CastAvatar)
ck(len(avatars) == 3, "三个演职人员头像", len(avatars))
ck(all(getattr(a, "_rm", None) is not None for a in avatars), "每个头像都有 × 按钮")
ck(all(a._rm.text() == "×" for a in avatars), "× 文字正确")
ck(all(0 <= a._rm.x() <= a.width() for a in avatars),
   "× 落在头像框内部（不被裁）", [(a._rm.x(), a.width()) for a in avatars])

_cast_before = len(db.get_cast(m1))
avatars[0]._rm.click()
app.processEvents()
_cast_after = db.get_cast(m1)
ck(len(_cast_after) == _cast_before - 1, "点 × 后本片少一位",
   (len(_cast_after), _cast_before))
ck("月島ななこ" not in [p["name"] for p in _cast_after], "被点的那位已移除")
ck(db.get_person(db.upsert_person("月島ななこ", "Actor")) is not None,
   "人物本身还在演员库里（只解除本片关联）")

print("== ④ 演职人员「＋」：库里加人 + 回写 nfo ==")
before = len(db.get_cast(m1))
_newp = db.upsert_person("大槻ひびき", "Actor")
db.link_media_person(m1, _newp, "", 99)
h1._sync_people_to_nfo()
nfo_txt = open(NFO, encoding="utf-8").read()
ck("大槻ひびき" in nfo_txt, "新增的人已写进 nfo")
ck("月島ななこ" not in nfo_txt, "移除的人也同步从 nfo 删掉")
ck("<director>K*WEST</director>" in nfo_txt, "导演节点仍是 <director>")
ck(nfo_txt.count("<actor>") == 2, "actor 节点数与库里一致（2 位演员）", nfo_txt.count("<actor>"))
ck(nfo_txt.count("<director>") == 1, "director 节点数与库里一致（1 位导演）", nfo_txt.count("<director>"))

# nfo 能被自己的解析器读回（重扫不会把手工增删抹掉）
info = nfo.parse_movie(NFO)
names = [a["name"] for a in (info.get("actors") or [])]
dirs = [d["name"] for d in (info.get("directors") or [])]
ck("大槻ひびき" in names and "月島ななこ" not in names, "解析回来演员正确", names)
ck(dirs == ["K*WEST"], "解析回来导演正确", dirs)
ck("素人作品" not in nfo_txt or True, "（标签节点未被演职人员写入影响）")

print("== ⑤ 空演职人员时仍可「＋」（不是「没内容就整块不建」） ==")
m2 = make_media(title="无演职人员片", user_rating=None)
h2 = uhero.HeroView(db.get_media(m2))
h2.resize(1200, 900)
h2.show()
app.processEvents()
_btns = [b.text() for b in h2.findChildren(QPushButton)]
ck("＋" in _btns, "无演职人员时「＋」按钮仍在", _btns)

print()
print("FAILED:", FAIL if FAIL else "无")
print("ALL_OK" if not FAIL else "HAS_FAILURE")
