# -*- coding: utf-8 -*-
"""v1.17.0 离线冒烟：覆盖三条反馈。

反馈 1（文件夹卡片视图）：新增 `_media_where(path_prefix=…)` 按 file_path 前缀筛，
  兼容「设置里用 /、索引里用 \\」两种分隔符，且 LIKE 元字符（_ %）被转义；
  `db.folder_stats()` 给出每个目录的影片数与代表海报；`FolderCard` 卡片名/数量/
  「目录不存在」标记正确；文件夹页标题带目录数。
反馈 2（筛选排序可收缩）：`FacetBar` 默认收缩（面板不可见）、点「筛选」才展开、
  `MEDIA_FACETS` 已删除「状态」(ident) /「进度」(progress) 两类；
  展开态经 `wall_prefs.facet_open` 持久化；`WALL_FILTER_KEYS` 不再接受这两个键。
反馈 3（卡片直接播放）：`PosterCard` 右下角生成圆形播放按钮，点击回调被触发且
  不进详情页；非视频文件（无扩展名）不生成按钮；`playable_media` 大小写不敏感。

全部使用临时库 + 临时 settings.json，绝不触碰真实索引 / 配置。
运行：python -u -c "import runpy; runpy.run_path(r'<本文件>', run_name='__main__')"
"""
import os
import sys
import time
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v117_")
import database as db
import config as cfg

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")

app = QApplication.instance() or QApplication([])
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import version as ver
import applog
_LOG_TMP = os.path.join(TMP, "logs")
os.makedirs(_LOG_TMP, exist_ok=True)
applog.log_dir = lambda: _LOG_TMP

import main_window as mw
from main_window import (MainWindow, load_style, FacetBar, PosterCard, FolderCard,
                         playable_media, MEDIA_FACETS, POSTER_W, POSTER_H,
                         POSTER_CARD_W, _CARD_PAD, _PLAY_BTN)

ERRORS = []


def check(ok, msg, extra=None):
    line = ("OK   - " if ok else "FAIL - ") + msg + (f"   {extra}" if extra is not None else "")
    print(line, flush=True)
    if not ok:
        ERRORS.append(msg)


def pump_ms(ms=120):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()


# ---------------------------------------------------------------- 准备
db.init_db()
cfg.get_settings().save()
load_style(app)

check(ver.VERSION == "v1.17.0", "版本号为 v1.17.0", ver.FULL_VERSION)
check(ver.BUILD == "2609190019", "内部构建号为 2609190019", ver.BUILD)

# ================================================================ 反馈 2：配置层（白名单 / 默认值 / 持久化）
check("ident" not in cfg.WALL_FILTER_KEYS, "WALL_FILTER_KEYS 已移除 ident（状态筛选下线）")
check("progress" not in cfg.WALL_FILTER_KEYS, "WALL_FILTER_KEYS 已移除 progress（进度筛选下线）")
check(cfg.DEFAULT_WALL_PREFS.get("facet_open") is False, "wall_prefs.facet_open 默认 False（收缩）")

_cleaned = cfg._clean_prefs(
    {"sort": "year", "asc": False,
     "filters": {"ident": "nfo", "progress": "watched", "genre": "剧情"}, "facet_open": True},
    cfg.DEFAULT_WALL_PREFS, cfg.WALL_FILTER_KEYS)
check(_cleaned["filters"] == {"genre": "剧情"},
      "旧偏好里的 ident/progress 在加载时被丢弃（只留 genre）", _cleaned["filters"])
check(_cleaned["facet_open"] is True, "facet_open 能穿过 _clean_prefs 保留")

s0 = cfg.get_settings()
s0.set_facet_open(True)
cfg._SETTINGS = None
check(cfg.get_settings().wall_prefs.get("facet_open") is True, "set_facet_open 持久化到 settings.json")
cfg.get_settings().set_wall_prefs("sort_title", True, {})     # 重建 filters 时不得丢掉 facet_open
cfg._SETTINGS = None
check(cfg.get_settings().wall_prefs.get("facet_open") is True,
      "set_wall_prefs 重建 filters 后 facet_open 仍保留")
cfg.get_settings().set_facet_open(False)
cfg._SETTINGS = None

# ================================================================ 反馈 1：path_prefix 筛选
# 故意混用分隔符：DIRA 的行存成反斜杠，DIRB 的行存成正斜杠（模拟真实库里两种都可能有）。
PF_ROWS = [
    (r"Y:\PF\DIRA\a1.mkv", "a1", "pa1"),
    (r"Y:\PF\DIRA\a2.mkv", "a2", "pa2"),
    ("Y:/PF/DIRB/b1.mkv", "b1", "pb1"),
    (r"Y:\PF\A_B\c1.mkv", "c1", "pc1"),
    (r"Y:\PF\AXB\c2.mkv", "c2", "pc2"),
]
for fp, st, poster in PF_ROWS:
    db.upsert_media_by_path(mode="overwrite", title=f"PF-{st}", sort_title=st, kind="movie",
                            file_path=fp, library="PF", poster=f"{TMP}/{poster}.jpg")

check(db.count_media(library="PF") == 5, "PF 库共 5 条", db.count_media(library="PF"))
check(db.count_media(library="PF", path_prefix=r"Y:\PF\DIRA") == 2,
      "path_prefix 反斜杠前缀命中反斜杠路径", db.count_media(library="PF", path_prefix=r"Y:\PF\DIRA"))
check(db.count_media(library="PF", path_prefix="Y:/PF/DIRA") == 2,
      "path_prefix 正斜杠前缀（设置里的写法）也能命中反斜杠路径",
      db.count_media(library="PF", path_prefix="Y:/PF/DIRA"))
check(db.count_media(library="PF", path_prefix="Y:/PF/DIRB") == 1,
      "path_prefix 正斜杠前缀命中正斜杠路径", db.count_media(library="PF", path_prefix="Y:/PF/DIRB"))
check(db.count_media(library="PF", path_prefix=r"Y:\PF\DIRB") == 1,
      "path_prefix 反斜杠前缀命中正斜杠路径", db.count_media(library="PF", path_prefix=r"Y:\PF\DIRB"))
check(db.count_media(library="PF", path_prefix="Y:/PF/DIRA/") == 2,
      "path_prefix 末尾多余的 / 被忽略", db.count_media(library="PF", path_prefix="Y:/PF/DIRA/"))
# LIKE 元字符必须被转义：A_B 只能命中 A_B，不能把 AXB 也算进来
check(db.count_media(library="PF", path_prefix="Y:/PF/A_B") == 1,
      "path_prefix 里的 _ 已转义（A_B 不会误命中 AXB）",
      db.count_media(library="PF", path_prefix="Y:/PF/A_B"))
check(db.count_media(library="PF", path_prefix="Y:/PF/A%B") == 0,
      "path_prefix 里的 % 已转义（A%B 不会当成通配）",
      db.count_media(library="PF", path_prefix="Y:/PF/A%B"))
_pl = db.search_media(library="PF", path_prefix="Y:/PF/DIRA", limit=50)
check(len(_pl) == db.count_media(library="PF", path_prefix="Y:/PF/DIRA"),
      "path_prefix 的列表与计数口径一致", f"{len(_pl)}")

# 数据层的 ident / progress SQL 支持仍保留（UI 已下线，但别让旧库 / 其它调用炸掉）
check(db.count_media(library="PF", ident="none") >= 0, "ident 的 SQL 支持仍可用（向后兼容）")
check(db.count_media(library="PF", progress="unwatched") == 5,
      "progress 的 SQL 支持仍可用（5 条都未观看）",
      db.count_media(library="PF", progress="unwatched"))

# ================================================================ 反馈 1：folder_stats
_fl = db.folder_stats([r"Y:\PF\DIRA", "Y:/PF/DIRB", r"Y:\PF\NOPE"], sample=2)
check(set(_fl.keys()) == {r"Y:\PF\DIRA", "Y:/PF/DIRB", r"Y:\PF\NOPE"},
      "folder_stats 返回传入的每个目录")
check(_fl[r"Y:\PF\DIRA"]["count"] == 2, "folder_stats 反斜杠目录计数=2",
      _fl[r"Y:\PF\DIRA"]["count"])
check(_fl["Y:/PF/DIRB"]["count"] == 1, "folder_stats 正斜杠目录计数=1", _fl["Y:/PF/DIRB"]["count"])
check(_fl[r"Y:\PF\NOPE"]["count"] == 0 and _fl[r"Y:\PF\NOPE"]["posters"] == [],
      "folder_stats 空目录计数=0 且无海报")
check([os.path.basename(x) for x in _fl[r"Y:\PF\DIRA"]["posters"]] == ["pa1.jpg", "pa2.jpg"],
      "folder_stats 按 sort_title 取代表海报（最多 sample 张）",
      _fl[r"Y:\PF\DIRA"]["posters"])

# ================================================================ 反馈 2：FacetBar 收缩 + 维度删减
_keys = [k for k, _l, _o in MEDIA_FACETS]
_labels = [l for _k, l, _o in MEDIA_FACETS]
check("ident" not in _keys and "progress" not in _keys,
      "MEDIA_FACETS 已删除「状态」「进度」两类", _keys)
check(_labels == ["风格", "地区", "年份", "类型", "收藏", "评分"],
      "MEDIA_FACETS 剩余 6 个维度且顺序正确", _labels)

bar = FacetBar()
bar.show()
app.processEvents()
check(bar.is_open() is False, "FacetBar 默认收缩")
check(bar._panel.isVisible() is False, "FacetBar 收缩时维度面板不可见")
check(bar.filter_btn.isVisible() is True, "FacetBar 收缩时「筛选」按钮仍可见")
check(bar.sort_btn.isVisible() is True, "FacetBar 收缩时「排序」按钮仍可见")
check(bar.filter_btn.text().startswith("筛选"), "「筛选」按钮文案正确", bar.filter_btn.text())
check(len(bar._groups) == 6, "FacetBar 构造了 6 组 chip", len(bar._groups))

_seen = []
bar.toggled.connect(lambda on: _seen.append(on))
bar.set_open(True)
app.processEvents()
check(bar.is_open() is True, "set_open(True) 后为展开态")
check(bar._panel.isVisible() is True, "展开后维度面板可见")
check(("▴" in bar.filter_btn.text()) and bar.filter_btn.isChecked(),
      "展开后「筛选」按钮高亮（勾选态 + 收起箭头）", bar.filter_btn.text())
check(bar.reset_btn.isVisible() is True, "「重置筛选」在展开区内（展开时可见）")

bar.filter_btn.click()          # 点一下 → 收起
app.processEvents()
check(bar.is_open() is False, "点「筛选」按钮可收起")
check(_seen and _seen[-1] is False, "收起时 toggled 信号发出 False", _seen)

bar_open = FacetBar(open_=True)
bar_open.show()
app.processEvents()
check(bar_open.is_open() is True and bar_open._panel.isVisible() is True,
      "FacetBar(open_=True) 可恢复上次的展开状态")

# ================================================================ 反馈 3：卡片播放按钮
check(playable_media({"file_path": r"Y:\a\b.MKV"}) is True, "playable_media 扩展名大小写不敏感")
check(playable_media({"file_path": r"Y:\a\b.mkv"}) is True, "playable_media 识别 .mkv")
check(playable_media({"file_path": r"Y:\a\b"}) is False, "playable_media 无扩展名 → 不可播放")
check(playable_media({"file_path": r"Y:\a\b.nfo"}) is False, "playable_media 非视频扩展名 → 不可播放")
check(playable_media({}) is False, "playable_media 空条目 → 不可播放")

_noop = lambda m: None
card_ok = PosterCard({"id": 1, "title": "可播", "file_path": r"Y:\x\a.mkv"},
                     on_open=_noop, on_play=_noop)
check(card_ok.play_btn is not None, "视频条目生成了播放按钮")
_pb = card_ok.play_btn
check(_pb.testAttribute(Qt.WA_TransparentForMouseEvents) is False,
      "播放按钮是真控件（不吃穿透，不会误触发选中/打开详情）")
check((_pb.x(), _pb.y()) == (_CARD_PAD + POSTER_W - _PLAY_BTN - 5,
                             _CARD_PAD + POSTER_H - _PLAY_BTN - 5),
      "播放按钮位于海报区右下角", (_pb.x(), _pb.y()))
check(_pb.x() + _pb.width() <= _CARD_PAD + POSTER_W and
      _pb.y() + _pb.height() <= _CARD_PAD + POSTER_H,
      "播放按钮完全落在海报区内（不越界到标题区）")
check(_pb.width() == _PLAY_BTN and _pb.height() == _PLAY_BTN,
      "播放按钮为正方形（QSS 圆角后可成正圆）", (_pb.width(), _pb.height()))
check(POSTER_CARD_W >= _pb.x() + _pb.width(), "按钮不超出卡片右边界")

_got = []
card_ok._on_play = lambda m: _got.append(m)
_pb.click()
app.processEvents()
check(len(_got) == 1 and _got[0]["id"] == 1, "点播放按钮触发 on_play 回调（不进详情页）", _got and _got[0].get("title"))

card_dir = PosterCard({"id": 2, "title": "目录", "file_path": r"Y:\x\folder"},
                      on_open=_noop, on_play=_noop)
check(card_dir.play_btn is None, "非视频条目（目录）不生成播放按钮")
card_empty = PosterCard({"id": 3, "title": "空", "file_path": ""}, on_open=_noop, on_play=_noop)
check(card_empty.play_btn is None, "无 file_path 的条目不生成播放按钮")
card_nocb = PosterCard({"id": 4, "title": "无回调", "file_path": r"Y:\x\a.mkv"}, on_open=_noop)
check(card_nocb.play_btn is None, "未提供 on_play 时不生成播放按钮")

# ================================================================ 反馈 1：文件夹页卡片
# 用真实目录，且**设置里写正斜杠、索引里存反斜杠**，端到端验证跨分隔符。
# 先清空 path_prefix 测试遗留在库里的 PF 库（它没配置目录 → 会生成 path=None 的兜底卡，
# 导致 sorted(cards.keys()) 撞 None），只保留文件夹页需要的 FP / FP2 两个库。
FP_BASE = os.path.join(TMP, "FolderPage")
dA = os.path.join(FP_BASE, "国产传媒映画")
dB = os.path.join(FP_BASE, "十大禁片")
dGhost = os.path.join(FP_BASE, "已搬迁的盘")
d1 = os.path.join(FP_BASE, "sub1", "【01】A")
d2 = os.path.join(FP_BASE, "sub2", "【01】A")
for _d in (dA, dB, d1, d2):
    os.makedirs(_d, exist_ok=True)
dA_cfg = dA.replace(os.sep, "/")
dB_cfg = dB.replace(os.sep, "/")
dGhost_cfg = dGhost.replace(os.sep, "/")
d1_cfg = d1.replace(os.sep, "/")
d2_cfg = d2.replace(os.sep, "/")

db.clear_media()
for i in (1, 2):
    db.upsert_media_by_path(mode="overwrite", title=f"国传{i}", sort_title=f"g{i}", kind="movie",
                            file_path=os.path.join(dA, f"g{i}.mkv"), library="FP",
                            poster=os.path.join(TMP, f"g{i}.jpg"))
db.upsert_media_by_path(mode="overwrite", title="禁片1", sort_title="j1", kind="movie",
                        file_path=os.path.join(dB, "j1.mkv"), library="FP",
                        poster=os.path.join(TMP, "j1.jpg"))
db.upsert_media_by_path(mode="overwrite", title="同名1", sort_title="s1", kind="movie",
                        file_path=os.path.join(d1, "s1.mkv"), library="FP2",
                        poster=os.path.join(TMP, "s1.jpg"))
db.upsert_media_by_path(mode="overwrite", title="同名2", sort_title="s2", kind="movie",
                        file_path=os.path.join(d2, "s2.mkv"), library="FP2",
                        poster=os.path.join(TMP, "s2.jpg"))

s = cfg.get_settings()
s.libraries = [{"name": "FP", "kind": "电影", "paths": [dA_cfg, dB_cfg, dGhost_cfg]},
               {"name": "FP2", "kind": "电影", "paths": [d1_cfg, d2_cfg]}]
s.save()
cfg._SETTINGS = None

win = MainWindow()
win.resize(1600, 900)
app.processEvents()
page = win._view_folders()
page.show()
app.processEvents()
cards = {c.path: c for c in page.findChildren(FolderCard)}
check(len(cards) == 5, "文件夹页生成 5 张目录卡片（FP 3 + FP2 2，无兜底 None 卡）",
      [c for c in cards.keys() if c])
check(dA_cfg in cards and dB_cfg in cards and dGhost_cfg in cards,
      "卡片覆盖 FP 配置的每个目录")
check(d1_cfg in cards and d2_cfg in cards, "卡片覆盖 FP2 配置的每个目录")

ca = cards.get(dA_cfg)
_ca_sub = [l.text() for l in ca.findChildren(QLabel)] if ca else []
check(ca is not None and f"共 2 部" in _ca_sub, "目录卡片显示「共 N 部」（国产传媒映画=2）", _ca_sub[:3])
check(ca is not None and ca.name == "国产传媒映画", "卡片名 = 目录名", ca and ca.name)
check(ca is not None and ca._missing is False, "存在的目录不标红")
cg = cards.get(dGhost_cfg)
check(cg is not None and cg._missing is True, "不存在的目录被标记（封面右上角红「!」）")
check(cg is not None and "目录不存在" in (cg.toolTip() or ""),
      "不存在的目录在 tooltip 里说明原因", (cg.toolTip() or "").replace("\n", " | "))
check(ca is not None and dA_cfg in (ca.toolTip() or ""), "卡片 tooltip 含完整目录路径")
_titles = [l.text() for l in page.findChildren(QLabel)]
check(any(t == "文件夹（5）" for t in _titles), "文件夹页标题带目录数", [t for t in _titles if "文件夹" in t][:2])

# 点卡片 → 该目录的影片墙（path_prefix 生效，标题带该目录的 2 部）
wall = win._wall_page("国产传媒映画", {"path_prefix": dA_cfg})
wall.show()
app.processEvents()
_wt = [l.text() for l in wall.findChildren(QLabel)]
check(any(t == "国产传媒映画（2 部）" for t in _wt),
      "目录 → 影片墙：标题显示该目录的 2 部（path_prefix 已下推）",
      [t for t in _wt if "国产传媒映画" in t][:2])

# 同名目录要能区分（同盘同名 → 带父目录名）；page 里同时含 FP 与 FP2 卡
_names2 = sorted(c.name for c in page.findChildren(FolderCard) if c.path and "sub" in c.path.replace(os.sep, "/"))
check(len(_names2) == 2 and _names2[0] != _names2[1],
      "同名目录卡片名不重复（自动补盘符/父目录）", _names2)

# ================================================================ 收尾
db.close_all()
win.close()
if ERRORS:
    print(f"\n==== 失败 {len(ERRORS)} 项: {ERRORS} ====", flush=True)
else:
    print("\n==== 全部通过 ====", flush=True)
sys.exit(1 if ERRORS else 0)
