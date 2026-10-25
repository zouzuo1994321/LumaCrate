# -*- coding: utf-8 -*-
"""v1.36.0 离屏冒烟（构建期）。

① 真机缺陷回归：PosterCard / ActorCard / FolderCard 的鼠标处理器在
   「**回调把本卡销毁**」之后不再触碰 self —— 即 v1.24.1 的入口判活拦不住的
   `RuntimeError: Internal C++ object (PosterCard) already deleted`。
   用 `shiboken6.delete(card)` 真释构 C++ 对象来断言，不靠肉眼看日志。
② 引导向量「中文 → 日文」：guide_translate 模块（术语表 / 字形对照 / 多词拆分）、
   config 偏好落盘与脏值归一、设置页复选框、_add_guide 的端到端合并。

使用临时数据库与临时配置，绝不读写真实索引 / 真实 settings.json。
"""
import os
import sys
import shutil
import tempfile
import faulthandler

faulthandler.enable()      # 原生崩溃（segfault / abort）也要留下栈，别只看到日志戛然而止

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1360_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QGroupBox, QCheckBox
from PySide6.QtGui import QImage, QPainter, QColor, QLinearGradient, QFontDatabase, QMouseEvent
from PySide6.QtCore import Qt, QEvent, QPoint, QPointF
from PIL import Image

app = QApplication(sys.argv)

import shiboken6
import database as db
import scanner as scanner_mod
import applog
import version as ver
import config as cfg
import recommend as rec_mod
import guide_translate as gt_mod
from main_window import MainWindow, PosterCard, ActorCard, FolderCard, load_style
from ui_settings import SettingsDialog
import main_window as mw_mod

# `_add_guide` 在「一条都没命中」时会弹模态 QInputDialog 让用户指定维度 ——
# 离屏下模态框会**永远等不到输入**（第一次跑就是这么被 SIGTERM 掉的）。
# 这里直接打桩成「用户选了『标签』」（用户的确认过「没命中就给下拉框」的既有行为）。
mw_mod.QInputDialog.getItem = staticmethod(lambda *a, **k: ("标签", True))

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

# 量几何 / 出图前必须先注册中文字体 + 套 QSS（见 skill 第十节）
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

FAIL = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("   -> " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(name)


# ================================================================ 样本库
def _poster(path, c1, c2, w=300, h=450):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(c1))
    g.setColorAt(1, QColor(c2))
    p.fillRect(0, 0, w, h, g)
    p.end()
    img.save(path)


PALETTE = [("#2b3a55", "#7a4a86"), ("#5a4326", "#c08a3e"), ("#1b2a4a", "#3d6a9e"),
           ("#26332b", "#5f7d63"), ("#4a2530", "#a6506a"), ("#31304a", "#6a6f9e")]
# 标签刻意用**日文原文**（这正是本版要解决的事：中文输入匹配不到它们）
GENRES = ["輪姦,巨乳", "輪姦,人妻", "中出し,人妻", "緊縛,巨乳", "時間停止,人妻", "中出し,巨乳"]
ACTORS = ["三上悠亜", "橋本有菜", "深田詠美", "三上悠亜", "滝沢ローラ", "橋本有菜"]

root = os.path.join(TMP, "lib")
for i in range(6):
    d = os.path.join(root, f"MV-{i:03d}")
    os.makedirs(d, exist_ok=True)
    c1, c2 = PALETTE[i % len(PALETTE)]
    _poster(os.path.join(d, "poster.jpg"), c1, c2)
    with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0"?>\n<movie>'
            f"<title>样本影片 {i}</title><year>{2010 + i}</year><runtime>120</runtime>"
            "<country>日本</country>"
            f"<genre>{GENRES[i]}</genre>"
            "<plot>预览用简介。</plot><thumb>poster.jpg</thumb>"
            f"<actor><name>{ACTORS[i]}</name></actor>"
            f"<uniqueid type='tmdb'>{i}</uniqueid></movie>")
    with open(os.path.join(d, "MV-%03d.mp4" % i), "w") as f:
        f.write("x" * 1024)

db.init_db()
scanner_mod.scan_library(root)
rows = db.movies()
print(f"[样本] 入库 {len(rows)} 部")
check("样本库已建好", len(rows) >= 6, len(rows))
_genres = sorted({g for r in rows for g in (r.get("genres") or "").split(",") if g})
print("[样本] 标签池 =", _genres)
check("样本含日文标签「輪姦」", "輪姦" in _genres, _genres)

# ================================================================ ① 模块单测
print("\n---- ① guide_translate 模块 ----")
check("CHAR_MAP 规模合理（> 400）", len(gt_mod.CHAR_MAP) > 400, len(gt_mod.CHAR_MAP))
check("LEXICON 规模合理（> 100）", len(gt_mod.LEXICON) > 100, len(gt_mod.LEXICON))
check("CHAR_MAP 无自映射", all(a != b for a, b in gt_mod.CHAR_MAP.items()))


def _tr(t):
    return gt_mod.translate_zh_to_ja(t)


_CASES = [
    ("轮奸", "輪姦"),          # 字形对照（简体 → 日本新字体）
    ("三上悠亚", "三上悠亜"),   # 字形对照 —— 顺手解决艺人名
    ("桥本有菜", "橋本有菜"),
    ("深田咏美", "深田詠美"),
    ("中出", "中出し"),         # 术语表（字形完全不同）
    ("护士", "ナース"),
    ("捆绑", "緊縛"),
    ("时间停止", "時間停止"),
    ("乱伦", "近親"),
    ("无码", "無修正"),
]
for _src, _want in _CASES:
    _got = _tr(_src)
    check(f"翻译 {_src} 含「{_want}」", _want in _got, _got)

_multi = _tr("孕妇教师")
check("多词输入会拆词（孕妇教师 → 妊婦 + 教師）",
      "妊婦" in _multi and "教師" in _multi, _multi)

check("已是日文写法 → 无需翻译（巨乳）", _tr("巨乳") == [], _tr("巨乳"))
check("已是日文写法 → 无需翻译（輪姦）", _tr("輪姦") == [], _tr("輪姦"))
check("空串 / 单字 → 无候选", _tr("") == [] and _tr("A") == [], (_tr(""), _tr("A")))
_long = _tr("轮奸巨乳人妻中出し捆绑护士")
check("候选条数有上限（<= MAX_VARIANTS）",
      len(_long) <= gt_mod.MAX_VARIANTS, (len(_long), _long))
check("候选里不含原串", "轮奸巨乳人妻中出し捆绑护士" not in _long, _long)

# 真实模糊匹配：中文输入原本一条都命中不了
_raw = rec_mod.resolve_guide_tokens_fuzzy("轮奸")
check("中文「轮奸」原样模糊匹配 = 0 条（这就是本版要解决的痛点）", _raw == [], _raw)
_hits = []
for _ja in _tr("轮奸"):
    _hits += [t for t, _d, _k in rec_mod.resolve_guide_tokens_fuzzy(_ja)]
check("译文「輪姦」能命中真实标签", any("輪姦" in t for t in _hits), _hits)

_actor_hits = []
for _ja in _tr("三上悠亚"):
    _actor_hits += [t for t, _d, _k in rec_mod.resolve_guide_tokens_fuzzy(_ja)]
check("译文「三上悠亜」能命中真实艺人", any(t.startswith("a:") for t in _actor_hits),
      _actor_hits)

# ================================================================ ② 偏好
print("\n---- ② config 偏好 ----")
check("DEFAULT_RECOMMEND 含 guide_ja_translate 且默认关",
      cfg.DEFAULT_RECOMMEND.get("guide_ja_translate") is False,
      cfg.DEFAULT_RECOMMEND.get("guide_ja_translate"))
_s = cfg.get_settings()
check("初始读出来是 False", _s.recommend.get("guide_ja_translate") is False,
      _s.recommend.get("guide_ja_translate"))
_s.set_recommend(guide_ja_translate=True)
check("set_recommend 能写入", _s.recommend.get("guide_ja_translate") is True)
cfg._SETTINGS = None                       # 走真实 load() 路径重新读盘
_s2 = cfg.get_settings()
check("落盘 + 重读后仍为 True", _s2.recommend.get("guide_ja_translate") is True,
      _s2.recommend.get("guide_ja_translate"))

# 脏值归一：绝不能写 bool(v)（bool("0") 是 True）
_DIRTY = [("0", False), ("false", False), ("no", False), ("off", False), ("", False),
          ("1", True), ("true", True), ("yes", True), (None, False), (0, False), (1, True)]
_dirty_bad = []
for _raw_v, _want in _DIRTY:
    _s2.recommend["guide_ja_translate"] = _raw_v
    _s2._sanitize_recommend()
    if _s2.recommend.get("guide_ja_translate") is not _want:
        _dirty_bad.append((_raw_v, _s2.recommend.get("guide_ja_translate"), _want))
check("脏配置归一正确（'0'/'false'/null → 关）", not _dirty_bad, _dirty_bad)
_s2.recommend["guide_ja_translate"] = True    # 后面端到端测试要用「开」

# ================================================================ ③ 主窗 + 双机回归
print("\n---- ③ 鼠标处理器：回调销毁自身 ----")
logo_path = os.path.join(ROOT, "logo-4.png")
load_style(app)
win = MainWindow(logo_path=logo_path)
win.resize(1920, 1080)
win.show()
app.processEvents()


def _dbl_ev():
    return QMouseEvent(QEvent.MouseButtonDblClick, QPointF(6, 6), QPointF(6, 6),
                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)


def _press_ev():
    return QMouseEvent(QEvent.MouseButtonPress, QPointF(6, 6), QPointF(6, 6),
                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)


MEDIA = {"id": 1, "title": "样本影片 0", "year": 2010, "poster": rows[0].get("poster"),
         "file_path": rows[0].get("file_path"), "favorite": 0}

# --- 3.1 双击：回调内部把本卡销毁（v1.35.1 真机上就是这条链） ---
_fired = []
_holder = {}
_card = PosterCard(MEDIA, on_open=lambda m: (_fired.append(m),
                                             shiboken6.delete(_holder["c"])),
                   on_select=None)
_holder["c"] = _card
_err = None
try:
    _card.mouseDoubleClickEvent(_dbl_ev())
except Exception as e:      # noqa: BLE001
    _err = f"{type(e).__name__}: {e}"
check("双击：回调销毁自身后不再抛异常", _err is None, _err)
check("双击：回调确实被调用了一次", len(_fired) == 1, len(_fired))

# --- 3.2 事件投给「已经死掉」的卡 ---
_fired2 = []
_card2 = PosterCard(MEDIA, on_open=lambda m: _fired2.append(m), on_select=None)
shiboken6.delete(_card2)
_err2 = None
try:
    _card2.mouseDoubleClickEvent(None)      # 守卫生效时根本不会碰 e
    _card2.mousePressEvent(None)
except Exception as e:      # noqa: BLE001
    _err2 = f"{type(e).__name__}: {e}"
check("已析构的 PosterCard 收到鼠标事件 → 静默返回", _err2 is None, _err2)
check("已析构的卡不会再触发回调", _fired2 == [], _fired2)

# --- 3.3 单击：回调销毁自身 ---
_fired3 = []
_block = {}


def _kill_on_select(_c):
    shiboken6.delete(_block["c"])


_card3 = PosterCard(MEDIA, on_open=None, on_select=_kill_on_select)
_block["c"] = _card3
_err3 = None
try:
    _card3.mousePressEvent(_press_ev())
except Exception as e:      # noqa: BLE001
    _err3 = f"{type(e).__name__}: {e}"
check("单击：选中回调销毁自身后不再抛异常", _err3 is None, _err3)

# --- 3.4 ActorCard 同构 ---
PERSON = {"id": 1, "name": "三上悠亜", "role_type": "Actor", "favorite": 0, "pinned": 0}
_afired = []
_aholder = {}
_acard = ActorCard(PERSON, on_open=lambda p: (_afired.append(p),
                                              shiboken6.delete(_aholder["c"])),
                   on_fav=None, on_pin=None, on_select=None, main_win=win)
_aholder["c"] = _acard
_aerr = None
try:
    _acard.mouseDoubleClickEvent(_dbl_ev())
except Exception as e:      # noqa: BLE001
    _aerr = f"{type(e).__name__}: {e}"
check("ActorCard 双击：回调销毁自身后不再抛异常", _aerr is None, _aerr)
check("ActorCard 双击回调被调用", len(_afired) == 1, len(_afired))

_afired2 = []
_acard2 = ActorCard(PERSON, on_open=lambda p: _afired2.append(p),
                    on_fav=None, on_pin=None, on_select=None, main_win=win)
shiboken6.delete(_acard2)
_aerr2 = None
try:
    _acard2.mouseDoubleClickEvent(None)
except Exception as e:      # noqa: BLE001
    _aerr2 = f"{type(e).__name__}: {e}"
check("已析构的 ActorCard → 静默返回", _aerr2 is None and _afired2 == [], (_aerr2, _afired2))

# --- 3.5 FolderCard（合集卡）同构 ---
_ffired = []
_fholder = {}
_fcard = FolderCard("合集A", "Y:/nope", 3, [],
                    on_open=lambda p, n: (_ffired.append((p, n)),
                                          shiboken6.delete(_fholder["c"])))
_fholder["c"] = _fcard
_ferr = None
try:
    _fcard.mousePressEvent(_press_ev())
except Exception as e:      # noqa: BLE001
    _ferr = f"{type(e).__name__}: {e}"
check("FolderCard 单击：回调销毁自身后不再抛异常", _ferr is None, _ferr)
check("FolderCard 单击回调被调用", len(_ffired) == 1, _ffired)

_fcard2 = FolderCard("合集B", "Y:/nope2", 1, [], on_open=lambda p, n: None)
shiboken6.delete(_fcard2)
_ferr2 = None
try:
    _fcard2.mousePressEvent(None)
except Exception as e:      # noqa: BLE001
    _ferr2 = f"{type(e).__name__}: {e}"
check("已析构的 FolderCard → 静默返回", _ferr2 is None, _ferr2)

# ================================================================ ④ 端到端：_add_guide
print("\n---- ④ _add_guide 端到端（开关开/关对比） ----")


def _fake_res():
    return {
        "picks": [], "algo": "normal", "engine": "", "pool": 6,
        "meta": {"favorites": 3, "liked": 1, "fav_people_n": 2},
        "profile_top": [("t人妻", 1.0), ("t巨乳", 0.9)],
    }


win._smart_res = _fake_res()
win._smart_picks = list(rows)
win._smart_guides = []
win.go(win._smart_wall)
for _ in range(4):
    app.processEvents()
check("智能推荐页已建好（guide_edit 存在）",
      getattr(win, "guide_edit", None) is not None)

_noop = {"n": 0}
win._replace_current = lambda b=None: _noop.__setitem__("n", _noop["n"] + 1)


def _keys():
    return [g.get("key") or "" for g in (win._smart_guides or [])]


# 4.1 开关关：中文输入一条都进不来
cfg.get_settings().recommend["guide_ja_translate"] = False
win._smart_guides = []
win.guide_edit.setText("轮奸")
print("[trace] 4.1 调用 _add_guide（开关关）…", flush=True)
win._add_guide()
print("[trace] 4.1 返回", flush=True)
app.processEvents()
_off_keys = _keys()
check("开关关：输入中文「轮奸」→ 没有任何含 輪姦 的引导",
      not any("輪姦" in k for k in _off_keys), _off_keys)
check("开关关：只剩「没命中 → 指定维度」那一条兜底引导", len(_off_keys) == 1, _off_keys)

# 4.2 开关开：译文命中并被合并进来
cfg.get_settings().recommend["guide_ja_translate"] = True
win._smart_guides = []
win.guide_edit.setText("轮奸")
print("[trace] 4.2 调用 _add_guide（开关开）…", flush=True)
win._add_guide()
print("[trace] 4.2 返回", flush=True)
app.processEvents()
_on_keys = _keys()
_ja_entries = [g for g in (win._smart_guides or []) if g.get("_ja")]
check("开关开：输入「轮奸」→ 出现含 輪姦 的引导",
      any("輪姦" in k for k in _on_keys), _on_keys)
check("译文贡献的条目被标记 _ja", len(_ja_entries) >= 1, len(_ja_entries))

# 4.3 艺人名：三上悠亚 → 三上悠亜
win._smart_guides = []
win.guide_edit.setText("三上悠亚")
win._add_guide()
app.processEvents()
_actor_guides = [g for g in (win._smart_guides or []) if (g.get("token") or "").startswith("a:")]
check("开关开：输入「三上悠亚」→ 命中艺人引导 a:三上悠亜",
      any("三上悠亜" in (g.get("token") or "") for g in _actor_guides),
      [(g.get("token"), g.get("_ja")) for g in _actor_guides])

# 4.4 状态行标注来源
_ja_n = len([g for g in (win._smart_guides or []) if g.get("_ja")])
_st = win.guide_state.text()
check("状态行标出「其中 N 条由中文→日文翻译得到」",
      _ja_n == 0 or f"其中 {_ja_n} 条由中文→日文翻译得到" in _st, (_ja_n, _st))

# 4.5 开关关时同一输入不该出现艺人引导
cfg.get_settings().recommend["guide_ja_translate"] = False
win._smart_guides = []
win.guide_edit.setText("三上悠亚")
win._add_guide()
app.processEvents()
_actor_guides_off = [g for g in (win._smart_guides or [])
                     if (g.get("token") or "").startswith("a:")]
check("开关关：输入「三上悠亚」→ 不出现艺人引导", not _actor_guides_off,
      [g.get("token") for g in _actor_guides_off])

# 4.6 已是日文写法时开关无副作用
cfg.get_settings().recommend["guide_ja_translate"] = True
win._smart_guides = []
win.guide_edit.setText("輪姦")
win._add_guide()
app.processEvents()
_direct = [g for g in (win._smart_guides or []) if g.get("_ja")]
check("输入已是日文 → 不产生额外的 _ja 条目", not _direct, _direct)

check("_replace_current 被正常调用（流程没被打断）", _noop["n"] >= 5, _noop["n"])

# ================================================================ ⑤ 设置页
print("\n---- ⑤ 设置页复选框 ----")
# 先把单例规范化：`SettingsDialog` 会在构造时抓住 `cfg.get_settings()`，
# 中途再 `_SETTINGS = None` 会造出第二个实例 → 「写进设置」那一条会假 FAIL
# （曾经真发生过：对话框写盘成功、但断言读的是另一个实例）。
cfg._SETTINGS = None
dlg = SettingsDialog(win, on_changed=None)
dlg.show()
app.processEvents()
check("对话框与全局读的是同一个 Settings 实例", dlg.s is cfg.get_settings())
ck = getattr(dlg, "ck_guide_ja", None)
check("设置页存在 ck_guide_ja", isinstance(ck, QCheckBox), type(ck).__name__)
_grp = None
_p = ck
while _p is not None:
    if isinstance(_p, QGroupBox):
        _grp = _p
        break
    _p = _p.parentWidget()
check("复选框位于「推荐范围与偏好」组",
      _grp is not None and "推荐范围与偏好" in _grp.title(),
      _grp.title() if _grp else None)
check("复选框文案含「中文」与「日文」",
      ck is not None and "中文" in ck.text() and "日文" in ck.text(),
      ck.text() if ck else None)

# ⚠ 必须先归零再勾上：直接 `setChecked(True)` 在「本来就是 True」时是**空操作**，
# `toggled` 根本不发 → 断言会假 PASS（上一版这里就假 PASS 过一次）。
cfg.get_settings().recommend["guide_ja_translate"] = False
ck.setChecked(False)
app.processEvents()
check("取消勾选 → 设置同步为 False",
      cfg.get_settings().recommend.get("guide_ja_translate") is False,
      cfg.get_settings().recommend.get("guide_ja_translate"))

ck.setChecked(True)
app.processEvents()
check("勾选 → 设置同步为 True",
      cfg.get_settings().recommend.get("guide_ja_translate") is True,
      cfg.get_settings().recommend.get("guide_ja_translate"))

# 落盘核对**直接读文件**（不再 `_SETTINGS = None`，那会换掉实例、把上面那条断成立的假象）
import json
with open(cfg.config_path(), encoding="utf-8") as _f:
    _disk = json.load(_f)
check("勾选后已落盘到 settings.json 的 recommend 段",
      (_disk.get("recommend") or {}).get("guide_ja_translate") is True,
      (_disk.get("recommend") or {}).get("guide_ja_translate"))


# ================================================================ 出图
def shot(widget, name, bg=(13, 11, 10)):
    out = os.path.join(ROOT, "dev", "screenshots", name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = os.path.join(TMP, name)
    widget.grab().save(tmp)
    im = Image.open(tmp).convert("RGBA")
    base = Image.new("RGBA", im.size, bg + (255,))
    Image.alpha_composite(base, im).convert("RGB").save(out)
    print("saved", out)


# 智能推荐页：开关开 + 一批中日混合引导
cfg.get_settings().recommend["guide_ja_translate"] = True
win._smart_res = _fake_res()
win._smart_picks = list(rows)
win._smart_guides = [
    {"token": "t:輪姦", "dim": "tag", "key": "輪姦", "weight": 2.0, "_ja": True},
    {"token": "t:人妻", "dim": "tag", "key": "人妻", "weight": 2.0},
    {"token": "t:巨乳", "dim": "tag", "key": "巨乳", "weight": 2.0},
    {"token": "t:中出し", "dim": "tag", "key": "中出し", "weight": 2.0, "_ja": True},
    {"token": "t:緊縛", "dim": "tag", "key": "緊縛", "weight": 2.0, "_ja": True},
    {"token": "t:時間停止", "dim": "tag", "key": "時間停止", "weight": 2.0, "_ja": True},
    {"token": "a:三上悠亜", "dim": "actor", "key": "三上悠亜", "weight": 2.0, "_ja": True},
    {"token": "a:橋本有菜", "dim": "actor", "key": "橋本有菜", "weight": 2.0, "_ja": True},
]
win.go(win._smart_wall)
for _ in range(4):
    app.processEvents()
scroll = win.stack.currentWidget()
shot(scroll, "v1360_smart_ja_chips.png")
shot(win, "v1360_window_1920.png")
if _grp is not None:
    shot(_grp, "v1360_settings_guide_ja.png")

# ================================================================ ⑥ 版本号
print("\n---- ⑥ 版本号 ----")
check("外部版本号 = v1.36.0", ver.VERSION == "v1.36.0", ver.VERSION)
check("内部构建号 = 2609300054", ver.BUILD == "2609300054", ver.BUILD)
_be = open(os.path.join(ROOT, "build_exe.py"), encoding="utf-8").read()
check("build_exe.py 已补 --hidden-import guide_translate",
      '"guide_translate"' in _be)

print("")
print(f"==== v1.36.0 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  (失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAIL:", n)

dlg.close()
try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if FAIL else 0)
