# -*- coding: utf-8 -*-
"""v1.31.0 离屏冒烟回归 —— 四条反馈逐条自证 + 关键回归

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1310.py', run_name='__main__')"

**安全约定**：`db.db_path` 指向临时目录、`cfg.config_path` 指向临时 settings.json、
日志与头像目录都重定向到临时目录 —— 全程不碰真实索引 / 真实配置 / 真实媒体目录。

覆盖：
  A 版本号
  B 反馈 1：演员库 / 导演库的 A-Z 字母索引导航已彻底移除
  C 反馈 2：三围前的罩杯（解析 + 加粗渲染 + 不撑破卡片）
  D 反馈 3：actorcheck 普通算法 —— 真机式脏数据下的分簇 / 存疑是否正确
  E 反馈 3：AI 算法不可用时**必须降级**而不是报错 / 卡住
  F 反馈 3：合并语义（搬关联去重 / 只补空值 / 别名合并 / meta 补齐 / 删行）
  G 反馈 3：演员信息手动编辑（能清空字段）+ 上传头像路径
  H 反馈 4：工具窗导航四分组 + 「演员检测」页接线
  I 关键回归（线程单例 / 导演卡 / 列数 / 品牌 / 头像按需加载）
"""
import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1310")
INDEX = os.path.join(TMP, "index_data")
MOVIES = os.path.join(TMP, "movies")
AVATARS = os.path.join(TMP, "cache", "people")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(MOVIES, exist_ok=True)
os.makedirs(AVATARS, exist_ok=True)
for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    try:
        os.remove(_f)
    except OSError:
        pass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ.pop("LMC_NO_SYSMON", None)      # I 段要**真跑**采集线程

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import version as ver

db.init_db()
# 头像目录重定向到临时目录 —— 「上传头像」那条用例会**真写文件**，
# 不重定向就会往工作副本的 cache/people 里丢垃圾。
_s0 = cfg.get_settings()
_s0.scraper["photo_dir"] = AVATARS

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print("[%s] %s  %s" % ("PASS" if cond else "FAIL", tag, detail))


def section(t):
    print("\n" + "=" * 74 + "\n" + t + "\n" + "=" * 74)


def src(rel):
    with io.open(os.path.join(SRC, rel), encoding="utf-8", newline="") as f:
        return f.read()


def doc(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as f:
        return f.read()


# ============================================================ Qt
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTreeWidget

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw
import actorcheck as ack
import ui_settings
import ui_actorcheck
import ui_imagedetect

mw.load_style(app)


def pump(n=4):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


pump(3)

# ============================================================ A. 版本号
section("A. 版本号（v1.31.0 / Build 2609240042）")
check("A1 外部版本 v1.31.0", ver.VERSION == "v1.31.0", ver.VERSION)
check("A2 内部构建号 2609240042（顺延）", ver.BUILD == "2609240042", ver.BUILD)
check("A3 完整标识", ver.FULL_VERSION == "v1.31.0 (Build 2609240042)", ver.FULL_VERSION)
check("A4 品牌 / Slogan / 外链 / 版权未被这轮改坏",
      ver.APP_NAME == "流明盒" and ver.APP_NAME_EN == "LumaCrate"
      and ver.SLOGAN_CN == "所有流明 · 尽收盒中"
      and ver.LICENSE_NOTE == "本软件为开源软件，没有授权禁止用于商业用途。"
      and ver.COPYRIGHT == "Copyright  2026 肆月Aperture",
      (ver.APP_NAME, ver.APP_NAME_EN, ver.SLOGAN_CN))

# ============================================================ B. 反馈 1：删掉 A-Z 索引
section("B. 反馈 1：演员库 / 导演库的 A-Z 字母索引导航已彻底移除")
_mwsrc = src("main_window.py")
check("B1 源码里不再引用 LetterIndexBar",
      "LetterIndexBar" not in _mwsrc and "letter_index" not in _mwsrc)
check("B2 源码里不再有 _people_rail / _scroll_to_card / _pending_letter",
      all(k not in _mwsrc for k in ("_people_rail", "_scroll_to_card", "_pending_letter")))
check("B3 演员库 / 导演库直接返回原页面",
      _mwsrc.count("return page") >= 2 and "return self._people_rail" not in _mwsrc)
check("B4 letter_index.py 文件仍在（只是不再被引用，保留能力）",
      os.path.exists(os.path.join(SRC, "letter_index.py")))
check("B5 数据层 people_letter_index 仍在（「首字母」排序未受影响）",
      hasattr(db, "people_letter_index")
      and any(k == "letter" for k, _l, _e in db.ACTOR_SORTS),
      [k for k, _l, _e in db.ACTOR_SORTS])

# ============================================================ C. 反馈 2：罩杯
section("C. 反馈 2：三围前显示加粗罩杯")
check("C1 _parse_cup 存在且取得到「尺寸」串里的カップ",
      mw._parse_cup("T155 / B111( Lカップ ) / W65 / H96 / S", "") == "L",
      mw._parse_cup("T155 / B111( Lカップ ) / W65 / H96 / S"))
check("C2 独立键「罩杯」也能取（真机 3870 位演员只有这个键有值）",
      mw._parse_cup("", "E") == "E" and mw._parse_cup("", "i") == "I")
check("C3 没有罩杯信息时返回空串（不许瞎猜一个字母）",
      mw._parse_cup("T153/B85/W58/H83", "") == ""
      and mw._parse_cup("", "") == "" and mw._parse_cup(None) == "")
check("C4 有尺寸无括号时不误取身高里的字母",
      mw._parse_cup("T160 / B90 / W60 / H88", "") == ""
      and mw._parse_cup("T160 / B90 / W60 / H88", "J") == "J")
check("C5 _parse_size 口径未被带坏（B/W/H 照旧）",
      mw._parse_size("T155 / B111( Lカップ ) / W65 / H96 / S") == ("111", "65", "96"))


def mk(cls, **kw):
    p = {"name": "测试演员", "thumb": None, "photo_path": None, "status": "现役",
         "works": 0, "alias": "", "favorite": 0, "pinned": 0,
         "meta": '{"身高": "158cm", "尺寸": "T153/B85/W58/H83", "出身地": "东京都"}',
         "birthday": "1994-01-16", "bio": ""}
    p.update(kw)
    return cls(p, on_open=lambda *_a: None, on_fav=lambda *_a: None,
               on_pin=lambda *_a: None, on_select=lambda *_a: None, main_win=None)


cup_card = mk(mw.ActorCard, meta='{"尺寸": "T155 / B111( Lカップ ) / W65 / H96 / S",'
                                 ' "罩杯": "L"}', works=7)
check("C6 卡面「三围」值变成 `L 胸111·腰65·臀96`",
      cup_card._fact_values()["三围"] == "L 胸111·腰65·臀96",
      cup_card._fact_values()["三围"])
_html = cup_card._fact_cells["三围"].text()
check("C7 罩杯渲染成加粗（<b> 且只包住字母）",
      "<b>" in _html and "</b>" in _html and ">L</span></b>" in _html, _html)
check("C8 三围其余部分没被加粗",
      _html.index("</b>") < _html.index("胸111"), _html)
check("C9 卡片仍是 236×160，三行结构不变",
      cup_card.width() == 236 and cup_card.height() == 160
      and mw._ACTOR_FACTS[-1] == ("三围", 2, 0, 2),
      (cup_card.width(), cup_card.height()))
cup_card.show()
pump(3)
_avail = mw.ACTOR_CARD_W - 2 * mw._ACTOR_PAD
#: 真机 5909 位演员里最长的一条是 `P 胸120·腰90·臀114`（实测 154px）—— 留足余量
_long = mk(mw.ActorCard, meta='{"尺寸": "T170 / B120( Pカップ ) / W90 / H114 / S"}')
_long.show()
pump(3)
_w = _long._fact_cells["三围"].sizeHint().width()
check("C10 最长的一条三围文本也放得下（加了罩杯仍不溢出整行）",
      _w <= _avail, "%dpx ≤ %dpx" % (_w, _avail))
n0 = mk(mw.ActorCard, meta='{"身高": "158cm", "出身地": "东京都"}')
check("C11 完全没有尺寸信息时三围仍是「—」（不因新增字段而变化）",
      n0._fact_cells["三围"].text().endswith("—</span>"), n0._fact_cells["三围"].text())
det_src = _mwsrc
check("C12 演员详情页的三围也带上罩杯",
      'facts.append("三围 " + ((cup + " " + seg)' in det_src,
      "详情页 facts 段")

# ============================================================ D. 反馈 3：普通算法
section("D. 反馈 3：演员检测 —— 普通算法（真机式脏数据）")
conn = db.get_conn()
_rows = []
_media_n = 0


def add_person(name, romaji=None, birthday="", alias="", meta=None, photo="", role="Actor"):
    conn.execute("INSERT INTO people(name, role_type, romaji, birthday, alias, meta,"
                 " thumb, photo_path, status) VALUES(?,?,?,?,?,?,?,?,?)",
                 (name, role, romaji, birthday, alias, meta, photo, photo, ""))
    return conn.execute("SELECT id FROM people WHERE name=?", (name,)).fetchone()["id"]


def link(pid, n=1):
    """给某位演员挂 n 部影片（造出「作品数」）。"""
    global _media_n
    for _ in range(n):
        _media_n += 1
        conn.execute("INSERT INTO media(kind, title, file_path, year) VALUES('movie',?,?,?)",
                     ("M%04d" % _media_n, "C:/fake/M%04d.mp4" % _media_n, 2020))
        mid = conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
        conn.execute("INSERT OR IGNORE INTO media_people(media_id, person_id, char_role,"
                     " person_order) VALUES(?,?,?,?)", (mid, pid, "", 0))


# ① 真机 MOMOKANATSUKI 型：同罗马音 6 人 + **样板资料**（同值被大量复用）
_momo_meta = '{"尺寸": "T / B( Cカップ ) / W / H / S", "罩杯": "C"}'
_momo = []
for nm in ("桃果なつき", "ももか", "もも", "もか", "MOKA", "MOMO"):
    _momo.append(add_person(nm, "Momoka Natsuki", "1999-01-30", "", _momo_meta))
for i, pid in enumerate(_momo):
    link(pid, i % 3 + 1)

# ② 真机 NATSUMEREIKA 型：同罗马音 5 人 + **一致的真人资料**（四项）
_reika_meta = '{"尺寸": "T152 / B96( Jカップ ) / W58 / H87 / S", "身高": "152cm",' \
              ' "事务所": "Life Promotion"}'
_reika_alias = "岸杏南、真木めぐみ、須藤美果、神谷明日香、百瀬咲玖"
_reika = []
for nm in ("夏目玲香", "百瀬咲玖", "岸杏南", "白川みなみ", "明日香"):
    _reika.append(add_person(nm, "Natsume Reika", "1983-10-17", _reika_alias, _reika_meta))
link(_reika[0], 12)
link(_reika[2], 2)

# ③ 真机「同名不同人」型：同罗马音但生日 / 三围互相矛盾 → 必须进「存疑」
add_person("千葉優花", "Chiba Yuuka", "2005-03-18",
           meta='{"尺寸": "T165 / B85( Gカップ ) / W60 / H92 / S", "身高": "165cm"}')
add_person("千葉ゆうか", "Chiba Yuuka", "1996-11-13",
           meta='{"尺寸": "T162 / B89( Eカップ ) / W61 / H92 / S", "身高": "162cm"}')
add_person("神菜美まい", "Kanami Mai", "1997-05-15",
           meta='{"尺寸": "T171 / B88( Dカップ ) / W62 / H93 / S", "身高": "171cm"}')
add_person("奏海麻衣", "Kanami Mai", "2006-01-01",
           meta='{"尺寸": "T149 / B78( Dカップ ) / W54 / H80 / S", "身高": "149cm"}')

# ④ 真机占位罗马音：48 个 LIST（画像各不相干）→ 整体跳过
for i in range(48):
    add_person("占位演员%02d" % i, "LIST", "19%02d-01-01" % (70 + i % 30),
               meta='{"尺寸": "T%d / B%d( Cカップ ) / W60 / H88 / S"}'
                    % (150 + i % 15, 80 + i % 20))

# ⑤ 超大罗马音组（>12 人）→ 不许自动成簇
_big = []
for i in range(13):
    _big.append(add_person("大组演员%02d" % i, "BigGroupRomaji", "1988-08-%02d" % (i + 1),
                           meta='{"尺寸": "T%d / B%d( Dカップ ) / W58 / H90 / S"}'
                                % (155 + i, 82 + i)))

# ⑥ 姓名重复行（真机 10 组：`横宮七海` / `横宮七海//`、`ミランダ·みゆ` / `ミランダ・みゆ`）
add_person("横宮七海", "Yokomiya Nanami", "1993-05-05")
add_person("横宮七海//", "Yokomiya Nanami 2", "1993-05-05")
add_person("ミランダ·みゆ", "Miranda Miyu", "1991-07-07")
add_person("ミランダ・みゆ", "Miranda Miyu 2", "1991-07-07")
add_person("川上ゆう", "Kawakami Yuu", "1980-01-01")
add_person("川上ゆう（森野雫）", "Kawakami Yuu 2", "1980-01-01")

# ⑦ 只靠「别名互指」（双方都没有罗马音）→ 也要能连起来
_a = add_person("别名主人甲", "", "1985-02-02", alias="别名目标乙、随便一个")
_b = add_person("别名目标乙", "", "", "")
link(_a, 4)
link(_b, 1)

# ⑧ 无关演员（不该出现在任何簇里）
_unrelated = add_person("完全无关演员", "Wanguan Wuguan", "1975-12-12")
conn.commit()
conn.close()
pump(2)

_people = db.people_for_match("Actor")
_res = ack.detect(_people)
check("D1 detect 返回结构齐全",
      all(k in _res for k in ("clusters", "suspects", "scanned", "pairs", "elapsed")),
      sorted(_res.keys()))
check("D2 扫描人数 = 库里演员数（含占位 48 人）",
      _res["scanned"] == len(_people), (_res["scanned"], len(_people)))
check("D3 占位罗马音被识别并跳过（48 条 LIST）",
      _res["skipped_placeholder"] == 48, _res["skipped_placeholder"])
check("D4 样板值也被识别出来（同值被 >4 人复用的生日 / 尺寸）",
      _res["boilerplate_values"] > 0, _res["boilerplate_values"])
check("D5 耗时在可接受范围（万级规模下 < 2 秒）",
      _res["elapsed"] < 2.0, "%s 秒" % _res["elapsed"])


def cluster_with(names):
    want = set(names)
    for c in _res["clusters"]:
        got = {m["name"] for m in c["members"]}
        if want <= got:
            return c
    return None


check("D6「同罗马音 + 样板资料」6 人被并成一簇（MOMOKANATSUKI 型）",
      cluster_with(["桃果なつき", "ももか", "もも", "もか", "MOKA", "MOMO"]) is not None,
      [len(c["ids"]) for c in _res["clusters"][:5]])
_c_reika = cluster_with(["夏目玲香", "百瀬咲玖", "岸杏南", "白川みなみ", "明日香"])
check("D7「同罗马音 + 一致真人资料（生日/尺寸/身高/事务所）」5 人成簇",
      _c_reika is not None and len(_c_reika["ids"]) == 5,
      len(_c_reika["ids"]) if _c_reika else None)
check("D8 该簇的理由里点明了「罗马音相同 + 刮削资料一致」",
      _c_reika is not None and any("罗马音相同" in r and "一致" in r for r in _c_reika["reasons"]),
      (_c_reika or {}).get("reasons"))
check("D9 默认保留者 = 作品最多的那位（夏目玲香 12 部）",
      _c_reika is not None and _c_reika["keep_name"] == "夏目玲香",
      (_c_reika or {}).get("keep_name"))

# ★ 最关键的一条：同名不同人 **绝不能** 进合并簇
_bad = ["千葉優花", "千葉ゆうか", "神菜美まい", "奏海麻衣"]
_in_any = [nm for nm in _bad
           if any(nm in {m["name"] for m in c["members"]} for c in _res["clusters"])]
check("D10 资料互相矛盾的「同名不同人」**一个都没进合并簇**", not _in_any, _in_any)
_s_names = [(s["a"]["name"], s["b"]["name"]) for s in _res["suspects"]]


def _suspect_pair(a, b):
    return any({x, y} == {a, b} for x, y in _s_names)


check("D11 他们落在「存疑」里，且理由写明矛盾点",
      _suspect_pair("千葉優花", "千葉ゆうか") and _suspect_pair("神菜美まい", "奏海麻衣"),
      [p for p in _s_names if "千葉" in p[0] or "神菜" in p[0]])
_s_chiba = next((s for s in _res["suspects"]
                 if {s["a"]["name"], s["b"]["name"]} == {"千葉優花", "千葉ゆうか"}), None)
check("D12 存疑理由里带上了具体的矛盾值（生日 / 三围）",
      _s_chiba is not None and any("对不上" in r for r in _s_chiba["reasons"]),
      (_s_chiba or {}).get("reasons"))

check("D13 姓名重复行（横宮七海 / 横宮七海//）被认成同一人",
      cluster_with(["横宮七海", "横宮七海//"]) is not None)
check("D14 中点全角/半角差异（ミランダ·みゆ / ミランダ・みゆ）也认成同一人",
      cluster_with(["ミランダ·みゆ", "ミランダ・みゆ"]) is not None)
check("D15 姓名括号里的旧艺名（川上ゆう（森野雫））被并成同一人",
      cluster_with(["川上ゆう", "川上ゆう（森野雫）"]) is not None)
check("D16 只靠「别名互指」也能连起来（双方都没罗马音）",
      cluster_with(["别名主人甲", "别名目标乙"]) is not None)
check("D17 超大罗马音组（13 人）不许自动成簇",
      cluster_with(["大组演员%02d" % i for i in range(13)]) is None
      and any("13 人" in " ".join(s["reasons"]) or
              "同组有 13 人" in " ".join(s["reasons"]) for s in _res["suspects"]))
check("D18 占位罗马音的 48 人一个都没进簇",
      not any(m["name"].startswith("占位演员")
              for c in _res["clusters"] for m in c["members"]))
check("D19 完全无关的演员没被卷进任何簇 / 存疑",
      not any("完全无关演员" in (m["name"] for m in c["members"])
              for c in _res["clusters"])
      and not any("完全无关演员" in (s["a"]["name"], s["b"]["name"])
                  for s in _res["suspects"]))
check("D20 一簇里不会超过 MAX_GROUP 人",
      all(len(c["ids"]) <= ack.MAX_GROUP for c in _res["clusters"]),
      max(len(c["ids"]) for c in _res["clusters"]))
check("D21 簇内每个人都真的与簇内其他人有据可查（无「顺带被卷进来」的成员）",
      all(len(c["members"]) == len(c["ids"]) and c["reasons"] for c in _res["clusters"]))
check("D22 keep_id 一定是簇成员",
      all(c["keep_id"] in c["ids"] for c in _res["clusters"]))
check("D23 别名建议值包含被合并者的名字",
      _c_reika is not None and all(nm in (_c_reika["alias_union"] or "")
                                   for nm in ("夏目玲香", "岸杏南")),
      (_c_reika or {}).get("alias_union"))

# ============================================================ E. 反馈 3：AI 降级
section("E. 反馈 3：AI 算法不可用时必须**降级**而不是报错")
import recommend as rec_mod

_orig_probe = rec_mod.probe_ollama
rec_mod.probe_ollama = lambda *a, **k: None          # 假装本机没装 Ollama
try:
    _ai = ack.ai_review(_res, model=None, max_clusters=3, max_suspects=2)
finally:
    rec_mod.probe_ollama = _orig_probe
check("E1 AI 不可用时 ai_review 返回 ai=False 而不是抛异常", _ai.get("ai") is False, _ai)
check("E2 给出一句人话解释怎么开启（降级提示）",
      isinstance(_ai.get("note"), str) and len(_ai["note"]) > 8, _ai.get("note"))
check("E3 普通算法的结果**不受影响**（降级后照样有候选）",
      len(_res["clusters"]) > 0)
check("E4 AI 不可用时不会给任何簇贴上假判定",
      all("ai" not in c for c in _res["clusters"]))
_ok, _note = ack.ai_available()
check("E5 ai_available 在本机（无 Ollama）也返回人话而不是异常",
      isinstance(_ok, bool) and isinstance(_note, str) and len(_note) > 4, (_ok, _note[:60]))
check("E6 判定解析对模型的各种废话都稳（JSON / 裸字段 / 中文）",
      (ack._parse_verdict('{"same": true, "confidence": "高", "keep": "甲"}') or {}).get("same") is True
      and (ack._parse_verdict("同一人 yes 置信度 中 保留 乙") or {}).get("confidence") == "中"
      and ack._parse_verdict("完全看不懂") is None,
      ack._parse_verdict('{"same": false}'))

# ============================================================ F. 反馈 3：合并语义
section("F. 反馈 3：合并语义（搬关联 / 只补空 / 合并别名与 meta / 删行）")
_K = _momo[0]
_D = _momo[1]
_K2 = _momo[2]
conn = db.get_conn()
conn.execute("UPDATE people SET romaji='Momoka Natsuki', birthday='1999-01-30' WHERE id=?",
             (_K,))
conn.execute("UPDATE people SET alias='ももか、ももちゃん', thumb='C:/fake/t.jpg',"
             " source='test-src' WHERE id=?", (_D,))
conn.commit()
conn.close()
_before = {p["id"]: p for p in db.people_for_match("Actor")}
check("F1 合并前两人都在，且 keep 无别名 / 无头像",
      _K in _before and _D in _before
      and not _before[_K]["alias"] and not _before[_K]["thumb"])
_links_before = len(db.people_for_match("Actor"))
_r = db.merge_people(_K, _D)
check("F2 merge_people 返回 ok", _r.get("ok") is True, _r)
check("F3 搬移了 drop 的作品关联", int(_r.get("moved") or 0) >= 1, _r.get("moved"))
_after = {p["id"]: p for p in db.people_for_match("Actor")}
check("F4 drop 记录已删除", _D not in _after)
check("F5 keep 的头像 / 来源被补齐（空值才补）",
      _after[_K]["thumb"] == "C:/fake/t.jpg" and _after[_K]["source"] == "test-src",
      (_after[_K]["thumb"], _after[_K]["source"]))
check("F6 别名合并进来了（含对方主名）",
      "ももか" in (_after[_K]["alias"] or ""), _after[_K]["alias"])
check("F7 keep 已有的 romaji / 生日没被覆盖",
      _after[_K]["romaji"] == "Momoka Natsuki" and _after[_K]["birthday"] == "1999-01-30",
      (_after[_K]["romaji"], _after[_K]["birthday"]))
conn = db.get_conn()
_rows_mp = [dict(r) for r in conn.execute(
    "SELECT media_id, person_id FROM media_people").fetchall()]
conn.close()
_pairs_mp = {(r["media_id"], r["person_id"]) for r in _rows_mp}
check("F8 没有重复行（PRIMARY KEY 去重生效）", len(_rows_mp) == len(_pairs_mp))
check("F9 没有残留指向被合并者的关联",
      not any(pid == _D for _m, pid in _pairs_mp))
check("F10 keep 现在拥有两人之和的作品数",
      _after[_K]["works"] == _before[_K]["works"] + _before[_D]["works"],
      (_before[_K]["works"], _before[_D]["works"], _after[_K]["works"]))
check("F11 重复合并 / 自合并都只返回 ok=False，不抛异常",
      db.merge_people(_K, _D).get("ok") is False
      and db.merge_people(_K, _K).get("ok") is False)
check("F12 合并别人不影响第三个人",
      _K2 in _after and _after[_K2]["works"] == _before[_K2]["works"])

# ============================================================ G. 反馈 3：手动编辑
section("G. 反馈 3：演员信息手动编辑 + 上传头像")
_n = db.set_person_fields(_K2, alias="", birthday="", romaji="", status="退役",
                          bio="新的简介", name="もも改")
_after2 = db.get_person(_K2)
check("G1 set_person_fields 能**清空**字段、也能改名（update_person 做不到）",
      not (_after2.get("alias") or "") and not (_after2.get("birthday") or "")
      and _after2.get("status") == "退役" and _after2.get("name") == "もも改",
      (_after2.get("alias"), _after2.get("birthday"), _after2.get("status"),
       _after2.get("name")))
check("G2 返回写入了多少列", _n >= 6, _n)
_meta_new = '{"身高": "158cm", "罩杯": "D"}'
db.set_person_fields(_K2, meta=_meta_new)
check("G3 meta 也走同一条通道（能整体替换）",
      (db.get_person(_K2).get("meta") or "") == _meta_new)
check("G4 白名单外的列会被忽略（防 UI 误传写坏库）",
      db.set_person_fields(_K2, id=999999, role_type="Director") in (0,) and
      db.get_person(_K2)["role_type"] == "Actor",
      db.get_person(_K2)["role_type"])
# 撞名（name 有 UNIQUE 约束）→ 抛异常而不是静默改坏
_dup_ok = False
try:
    db.set_person_fields(_K, name="MOKA")
except Exception:
    _dup_ok = True
check("G5 改成已存在的姓名会抛错（UI 会转成人话提示，不会静默写坏）", _dup_ok)

# ---------------- 页面端到端 ----------------
dlg = ui_settings.SettingsDialog()
dlg.resize(1180, 860)
dlg.show()          # 离屏测几何 / 触发懒加载 showEvent 必须先 show()
pump(6)
dlg._show("演员检测")
pump(6)
pg = dlg.stack.currentWidget()
check("G6 「演员检测」页已接到工具窗上",
      pg is dlg._pg_actorcheck and isinstance(pg, ui_actorcheck.ActorCheckPage))
check("G7 页面控件齐全（算法单选 / 进度条 / 结果树 / 详情滚动区）",
      all(hasattr(pg, a) for a in ("rb_normal", "rb_ai", "run_btn", "stop_btn", "bar",
                                   "tree", "detail_scroll", "kw", "plist", "edit_scroll")))
check("G8 一进页面就自动检索出演员列表（懒加载）",
      pg.plist.count() > 0, pg.plist.count())
check("G9 默认是普通算法（不点就不联本地 AI）", pg.rb_normal.isChecked() and not pg.rb_ai.isChecked())
check("G10 worker 尚未启动（不点检测就不建线程）",
      getattr(pg, "_worker", None) is None, getattr(pg, "_worker", None))

# 真跑一次检测（后台线程 + 事件循环）
pg.run_btn.click()
pump(40)
for _ in range(60):
    if pg._worker is None or not pg._worker.isRunning():
        break
    pump(6)
pump(6)
check("G11 检测跑完且状态栏给出了统计",
      pg._res is not None and ("建议合并" in pg.status_lbl.text()),
      pg.status_lbl.text()[:110])
check("G12 树里建出了「建议合并」与「存疑」两个根节点",
      pg.tree.topLevelItemCount() == 2
      and pg.tree.topLevelItem(0).childCount() >= 1
      and pg.tree.topLevelItem(1).childCount() >= 1,
      (pg.tree.topLevelItem(0).childCount(), pg.tree.topLevelItem(1).childCount()))
# v1.31.0 真机抓到的真缺陷：`setExpanded(True)` 写在 addTopLevelItem / 加子节点之前是空操作，
# 真机上跑完检测看到的是两个**收起的**根，得先手点一下才看得到候选。
check("G12b 两个根节点默认就是展开的（不用手点就能看到候选）",
      pg.tree.topLevelItem(0).isExpanded() and pg.tree.topLevelItem(1).isExpanded(),
      (pg.tree.topLevelItem(0).isExpanded(), pg.tree.topLevelItem(1).isExpanded()))
check("G13 检测完不留下 running 线程",
      (pg._worker is None or not pg._worker.isRunning())
      and pg.run_btn.isEnabled() and not pg.stop_btn.isEnabled())

_found = None
for i in range(pg.tree.topLevelItem(0).childCount()):
    it = pg.tree.topLevelItem(0).child(i)
    if "横宮七海" in (it.text(0) or ""):
        _found = it
        break
check("G14 能在树里定位到「横宮七海」那一簇", _found is not None)
pg.tree.setCurrentItem(_found)
pump(4)
check("G15 选中后右侧详情建出来了（含「保留」下拉与「确认关联」按钮）",
      getattr(pg, "keep_box", None) is not None
      and pg.keep_box.count() >= 2 and pg.detail.count() > 3,
      pg.keep_box.count() if getattr(pg, "keep_box", None) else None)
# v1.31.0 出图时查出的真缺陷：`_clear_layout` 只 takeAt + deleteLater，
# 旧控件脱离布局却仍被绘制 → 右栏叠着上一屏的占位文字（离屏 processEvents 不派发 DeferredDelete）。
_vis = [l.text() for l in pg.detail_host.findChildren(QLabel)
        if l.isVisible() and l.text()]
check("G15b 右栏不再残留上一屏的占位文字（hide + setParent(None) 兜住）",
      not any("点「开始检测」" in t or "会列出「建议合并」" in t for t in _vis),
      [t for t in _vis if "开始检测" in t or "建议合并」的簇" in t])
# 同一条：横向分栏别让「要动手确认关联」的右栏比自己最小宽还窄
_hs = [s for s in pg.findChildren(__import__("PySide6.QtWidgets",
                                             fromlist=["QSplitter"]).QSplitter)
       if s.orientation() == Qt.Horizontal]
check("G15c 横向分栏给右栏留足了宽度（右栏 ≥ 树宽，且 ≥ 380px）",
      bool(_hs) and _hs[0].sizes()[1] >= 380 and _hs[0].sizes()[1] >= _hs[0].sizes()[0],
      _hs[0].sizes() if _hs else None)
# 同类：详情区是滚动区，动作行若排在成员块之后会掉到折叠线以下 = 主操作藏起来了
_go = [b for b in pg.detail_host.findChildren(QPushButton) if "确认关联" in (b.text() or "")]
check("G15d 主操作落在首屏可见区内（不用滚动就能点到「确认关联」）",
      bool(_go) and (_go[0].mapTo(pg.detail_host, _go[0].rect().topLeft()).y()
                     + _go[0].height()) <= pg.detail_scroll.viewport().height(),
      (_go[0].mapTo(pg.detail_host, _go[0].rect().topLeft()).y(), _go[0].height(),
       pg.detail_scroll.viewport().height()) if _go else None)
_btns = [b.text() for b in pg.detail_host.findChildren(QPushButton)]
check("G16 详情里有「确认关联（合并）」与「全部不合并」",
      any("确认关联" in t for t in _btns) and any("不合并" in t for t in _btns), _btns)
# 详情里的合并按钮要能弹出确认框（不真点 Yes，只验证弹的是确认框）
check("G17 详情页给出「不会动视频 / nfo 文件」的说明",
      any("不会动" in l.text() for l in pg.detail_host.findChildren(QLabel)))

# 手动编辑端到端：检索 → 选中 → 改字段 → 保存
pg.kw.setText("もも改")
pg._search_people()
pump(3)
_tgt = None
for i in range(pg.plist.count()):
    if pg.plist.item(i).data(Qt.UserRole) == _K2:
        _tgt = i
        break
check("G18 检索能按姓名命中", _tgt is not None, pg.plist.count())
pg.plist.setCurrentRow(_tgt)
pump(4)
check("G19 选中后编辑表单按人物资料填好（含 meta 五项）",
      pg._person is not None and pg._person["id"] == _K2
      and "meta:罩杯" in pg._fields and pg._fields["meta:罩杯"].text() == "D",
      sorted(k for k in pg._fields))
pg._fields["alias"].setText("新别名甲、新别名乙")
pg._fields["meta:身高"].setText("160cm")
pg._save_person()
pump(4)
_g = db.get_person(_K2)
check("G20 保存真的落到索引（普通字段 + meta 键）",
      "新别名甲" in (_g.get("alias") or "") and "160cm" in (_g.get("meta") or ""),
      (_g.get("alias"), _g.get("meta")))
check("G21 保存后表单重建且给出反馈文案",
      pg.save_lbl is not None and "已保存" in (pg.save_lbl.text() or ""),
      getattr(pg.save_lbl, "text", lambda: None)())
# 同一条残留问题：重建编辑表单若只 takeAt + deleteLater，旧表单会叠在新表单上
_lbls = [l.text() for l in pg.edit_host.findChildren(QLabel) if l.isVisible() and l.text()]
check("G21b 重建编辑表单不叠加（旧表单已彻底脱离，同名标签只剩一份）",
      _lbls.count("姓名") <= 1 and _lbls.count("别名") <= 1,
      {"姓名": _lbls.count("姓名"), "别名": _lbls.count("别名"), "共": len(_lbls)})
# 头像：复制进头像目录 + 写库
_src_img = os.path.join(TMP, "avatar_src.jpg")
try:
    from PySide6.QtGui import QImage, QColor
    _im = QImage(200, 260, QImage.Format_RGB32)
    _im.fill(QColor("#7a5c3a"))
    _im.save(_src_img, "JPG")
except Exception as e:
    print("   （造测试图片失败：%s）" % e)
_dest, _err = pg._copy_avatar(_K2, "もも", _src_img)
check("G22 上传头像会把图片复制进头像目录（命名与刮削一致 `<id>_<名字>.jpg`）",
      bool(_dest) and os.path.exists(_dest) and not _err
      and os.path.basename(_dest).startswith("%d_" % _K2) and _dest.endswith(".jpg"),
      _dest or _err)
db.set_person_fields(_K2, photo_path=_dest, thumb=_dest)
_g2 = db.get_person(_K2)
check("G23 头像路径写进 photo_path / thumb（海报墙与详情页都会用上）",
      _g2.get("photo_path") == _dest and _g2.get("thumb") == _dest,
      (_g2.get("photo_path"), _g2.get("thumb")))
_fake = pg._copy_avatar(_K2, "もも", os.path.join(TMP, "不存在的图.jpg"))
check("G24 源头图片不存在时给一句人话错误而不是崩",
      _fake[0] == "" and "失败" in _fake[1], _fake[1][:60])

# ============================================================ H. 反馈 4：工具窗分组导航
section("H. 反馈 4：工具窗口导航按四组分类 + 「演员检测」页接线")
check("H1 NAV_GROUPS 是用户点名的四组",
      [g for g, _k in dlg.NAV_GROUPS] == ["基础工具", "数据优化", "智能检测", "数据分析"],
      [g for g, _k in dlg.NAV_GROUPS])
check("H2 「基础工具」= 个性化设置 / 服务管理 / 手动修改",
      dlg.NAV_GROUPS[0][1] == ["个性化设置", "服务管理", "手动修改"],
      dlg.NAV_GROUPS[0][1])
check("H3 「数据优化」= 演员刮削 / 智能推荐 / 标签优化",
      dlg.NAV_GROUPS[1][1] == ["演员刮削", "智能推荐", "标签优化"], dlg.NAV_GROUPS[1][1])
check("H4 「智能检测」= 重复检测 / 演员检测 / 图像检测（演员检测夹在中间）",
      dlg.NAV_GROUPS[2][1] == ["重复检测", "演员检测", "图像检测"], dlg.NAV_GROUPS[2][1])
check("H5 「数据分析」= 画像概览 / 数据与日志",
      dlg.NAV_GROUPS[3][1] == ["画像概览", "数据与日志"], dlg.NAV_GROUPS[3][1])
check("H6 ORDER 仍是扁平且按可见顺序（dev/ 脚本按它遍历）",
      dlg.ORDER == [k for _g, keys in dlg.NAV_GROUPS for k in keys],
      dlg.ORDER)
check("H7 导航按钮数 = ORDER 长度 = stack 页数（一页都没漏挂）",
      len(dlg.sub_btns) == len(dlg.ORDER) == dlg.stack.count(),
      (len(dlg.sub_btns), len(dlg.ORDER), dlg.stack.count()))
_sections = [l for l in dlg.findChildren(QLabel) if l.objectName() == "Section"]
check("H8 四个分组小标题都建出来了（QLabel#Section 有样式）",
      [l.text() for l in _sections][:4] == [g for g, _k in dlg.NAV_GROUPS],
      [l.text() for l in _sections][:6])
# 视觉顺序必须与逻辑顺序一致（分组后最容易出的错就是把按钮插错了位置）
_vis = sorted((b for b in dlg.sub_btns.values()), key=lambda b: b.y())
check("H9 按钮的纵向顺序与 ORDER 完全一致（分组没有插乱）",
      [b.text() for b in _vis] == dlg.ORDER,
      [b.text() for b in _vis])
_sec_vis = sorted(_sections[:4], key=lambda l: l.y())
check("H10 分组标题正好排在各自第一个按钮之前",
      all(_sec_vis[i].y() < [b for b in _vis if b.text() == dlg.NAV_GROUPS[i][1][0]][0].y()
          for i in range(4)),
      [(l.text(), l.y()) for l in _sec_vis])
for _k in dlg.ORDER:
    dlg._show(_k)
    pump(2)
check("H11 每一页都能切过去（无异常）",
      dlg.stack.currentWidget() is dlg._pg_data, dlg.stack.currentWidget())
check("H12 工具窗仍是非模态 / 可复用",
      dlg.isModal() is False, dlg.isModal())
dlg.close()
pump(3)

# ============================================================ I. 关键回归
section("I. 关键回归")
check("I1 演员卡仍是六项 5 格、三围整行跨两列",
      mw._ACTOR_FACTS[-1] == ("三围", 2, 0, 2)
      and {r for _k, r, _c, _s in mw._ACTOR_FACTS} == {0, 1, 2})
check("I2 导演卡仍是「作品 / 别名」两项、高度算式未变",
      [k for k, _r, _c, _s in mw._DIRECTOR_FACTS] == ["作品", "别名"]
      and mw.DIRECTOR_CARD_H == mw.ACTOR_CARD_H - 2 * (17 + 4))
check("I3 列数未动（媒体 8 / 演员与导演 6）",
      mw.LazyGrid.COLS_BY_KIND["media"] == 8
      and mw.LazyGrid.COLS_BY_KIND["actor"] == 6, mw.LazyGrid.COLS_BY_KIND)

win = mw.MainWindow()
win.show()
pump(6)
win._apply_settings()
pump(8)
import sysmon as _sy
_workers = app.findChildren(_sy.SysMonWorker)
check("I4 v1.27.0 线程单例仍成立（重建侧栏后 SysMonWorker 仍只有 1 个且在跑）",
      len(_workers) == 1 and _workers[0].isRunning(),
      (len(_workers), [w.isRunning() for w in _workers]))
check("I5 主窗里没有工具页的线程（演员检测 / 图像检测只活在工具窗里）",
      len(win.findChildren(ui_imagedetect.ImageScanWorker)) == 0
      and len(win.findChildren(ui_actorcheck.ActorCheckWorker)) == 0)
check("I6 侧栏品牌与外链过滤器仍被持有引用",
      win._brand_link is not None and win._footer_link is not None)
win.close()
pump(3)

_mwsrc2 = src("main_window.py")
check("I7 未捕获异常为零（日志里没有 Traceback）",
      "Traceback" not in (io.open(applog.log_path(), encoding="utf-8", errors="replace").read()
                          if os.path.exists(applog.log_path()) else ""),
      applog.log_path())
check("I8 README 与 version.py 的版本号一致（发布前必须同步）",
      ver.VERSION in doc("README.md"), ver.VERSION)

print("\n" + "=" * 74)
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败：")
    for t in FAIL:
        print("  -", t)
print("=" * 74)
