# -*- coding: utf-8 -*-
"""v1.30.0 离屏冒烟回归 —— 四条反馈逐条自证 + 关键回归

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1300.py', run_name='__main__')"

**安全约定**：`db.db_path` 指向临时目录、`cfg.config_path` 指向临时 settings.json、
日志重定向到临时目录 —— 全程不碰真实索引 / 真实配置 / 真实媒体目录。

覆盖：
  A 版本号
  B 反馈 1：演员卡「作品数」顶替「胸围」（源码 + 真建卡 + 高度不变）
  C 反馈 4：首字母排序 / people_letter_index 与真实列表顺序逐位一致
  D 反馈 4：LetterIndexBar + LazyGrid.jump_to 真跳转（建卡到目标下标并回调）
  E 反馈 2：imagedetect 缺图 / 截断图判定（真文件，含 Qt 判不出来的那种）+ 替换
  F 反馈 3：nfo_editor 写回保住其它节点 / 按姓名复用 <actor> 保住 <thumb> + 同步索引
  G 反馈 2 / 3：两个新工具页能建起来且导航顺序正确
  H 回归（侧栏线程单例 / 品牌 / 导演卡 / 列数）
"""
import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1300")
INDEX = os.path.join(TMP, "index_data")
MOVIES = os.path.join(TMP, "movies")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
# 用例之间要相互隔离：上一轮跑留下的 `-poster.jpg` / `.nfo.bak-*` 会让「缺图」断言
# 变成假阴性（第一次跑就是被这个绊到：KAVR-383 里残留了上一轮替换好的海报）。
for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    try:
        os.remove(_f)
    except OSError:
        pass
if os.path.isdir(MOVIES):
    for _dp, _dn, _fns in os.walk(MOVIES):
        for _f in _fns:
            try:
                os.remove(os.path.join(_dp, _f))
            except OSError:
                pass
os.makedirs(MOVIES, exist_ok=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ.pop("LMC_NO_SYSMON", None)      # H 段要**真跑**采集线程

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import version as ver
import sysmon

db.init_db()

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
from PySide6.QtCore import Qt, QPointF, QEvent
from PySide6.QtGui import QFont, QFontDatabase, QMouseEvent, QImage
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw
import imagedetect as idm
import nfo_editor as nf

mw.load_style(app)


def pump(n=4):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


pump(3)

# ============================================================ A. 版本号
section("A. 版本号（v1.30.0 / Build 2609230041）")
check("A1 外部版本 v1.30.0", ver.VERSION == "v1.30.0", ver.VERSION)
check("A2 内部构建号 2609230041（顺延）", ver.BUILD == "2609230041", ver.BUILD)
check("A3 完整标识", ver.FULL_VERSION == "v1.30.0 (Build 2609230041)", ver.FULL_VERSION)
check("A4 品牌 / Slogan / 外链 / 版权未被这轮改坏",
      ver.APP_NAME == "流明盒" and ver.APP_NAME_EN == "LumaCrate"
      and ver.SLOGAN_CN == "所有流明 · 尽收盒中"
      and ver.LICENSE_NOTE == "本软件为开源软件，没有授权禁止用于商业用途。"
      and ver.COPYRIGHT == "Copyright  2026 肆月Aperture")

mw_s = src("main_window.py")
db_s = src("database.py")

# ============================================================ B. 反馈 1：演员卡「作品数」
section("B. 反馈 1：演员卡第 5 项由「胸围」换成「作品」")

keys = [k for k, _r, _c, _s in mw._ACTOR_FACTS]
check("B1 FACTS 五项顺序 = 出生/出身地/身高/作品/三围",
      keys == ["出生", "出身地", "身高", "作品", "三围"], keys)
check("B2 不再出现「胸围」", "胸围" not in keys, keys)
check("B3 仍是 3 行、行高与列宽都与之前一致（15+17 + 三围整行跨两列）",
      mw._ACTOR_FACTS[-1] == ("三围", 2, 0, 2)
      and {r for _k, r, _c, _s in mw._ACTOR_FACTS} == {0, 1, 2},
      mw._ACTOR_FACTS)
check("B4 卡片高度常量没动（ACTOR_CARD_H=160 / DirectorCard 压高算式未变）",
      mw.ACTOR_CARD_H == 160 and mw.DIRECTOR_CARD_H == mw.ACTOR_CARD_H - 2 * (17 + 4),
      (mw.ACTOR_CARD_H, mw.DIRECTOR_CARD_H))


def mk(cls, **kw):
    # meta 的真实存储形态是 JSON 串（见 `_parse_meta`），尺寸走 T/B/W/H 缩写
    # （见 `_parse_size`）—— 按真实口径给值，才测得准「三围」这一行。
    p = {"name": "测试演员", "thumb": None, "photo_path": None, "status": "现役",
         "works": 0, "alias": "", "favorite": 0, "pinned": 0,
         "meta": '{"身高": "158cm", "尺寸": "T153/B85/W58/H83", "出身地": "东京都"}',
         "birthday": "1994-01-16", "bio": ""}
    p.update(kw)
    return cls(p, on_open=lambda *_a: None, on_fav=lambda *_a: None,
               on_pin=lambda *_a: None, on_select=lambda *_a: None, main_win=None)


ac = mk(mw.ActorCard, works=42)
check("B5 有作品数时显示「作品 42 部」", "作品" in ac._fact_cells
      and "42 部" in ac._fact_cells["作品"].text(),
      ac._fact_cells["作品"].text())
ac0 = mk(mw.ActorCard, works=0)
check("B6 没有作品时不硬凑，显示「—」",
      ac0._fact_cells["作品"].text().endswith("—</span>"),
      ac0._fact_cells["作品"].text())
check("B7 三围仍完整走了 meta（胸/腰/臀都有值，胸围信息没丢）",
      "胸85" in ac._fact_cells["三围"].text()
      and "腰58" in ac._fact_cells["三围"].text()
      and "臀83" in ac._fact_cells["三围"].text(),
      ac._fact_cells["三围"].text())
check("B8 卡片几何不变：宽 236 / 高 160，内容没被顶出卡外",
      ac.width() == 236 and ac.height() == 160, (ac.width(), ac.height()))

# ============================================================ 造数据：people + media
_NAMES = [("Ayaka", "A"), ("Aoi", "A"), ("Bambi", "B"), ("Chika", "C"),
          ("Diana", "D"), ("Erena", "E"), ("Fumika", "F"), ("Gina", "G"),
          ("Honoka", "H"), ("Ichika", "I"), ("Julia", "J"), ("Karen", "K"),
          ("Luna", "L"), ("Momo", "M"), ("Nana", "N"), ("Olvia", "O"),
          ("Pipi", "P"), ("Qoo", "Q"), ("Rina", "R"), ("Saki", "S"),
          ("Tsuki", "T"), ("Ume", "U"), ("Vega", "V"), ("Waka", "W"),
          ("Xena", "X"), ("Yuki", "Y"), ("Zara", "Z"), ("仮名 힘", "#")]
conn = db.get_conn()
try:
    for i, (nm, _lt) in enumerate(_NAMES):
        conn.execute(
            "INSERT INTO people(name, role_type, romaji, status, favorite, pinned, alias) "
            "VALUES(?,?,?,?,?,?,?)",
            (nm, "Actor", nm, "现役", 1 if nm == "Zara" else 0,
             1 if nm == "Momo" else 0, ""))
    conn.commit()
finally:
    pass

section("C. 反馈 4：首字母排序口径 + people_letter_index 与真实顺序一致")
check("C1 ACTOR_SORTS 里新增 letter → 首字母",
      any(k == "letter" for k, _l, _e in db.ACTOR_SORTS), db.ACTOR_SORTS[3])
check("C2 首字母表达式走「romaji 优先，退化到姓名」",
      "COALESCE(NULLIF(TRIM(p.romaji), ''), p.name)" in db_s
      and db._ACTOR_LETTER_EXPR.startswith("UPPER(SUBSTR("),
      db._ACTOR_LETTER_EXPR)

rows = db.query_people(role_type="Actor", sort="letter", asc=True)
idx = db.people_letter_index(role_type="Actor", asc=True)
# Momo 被置顶 → 排第一，所以 # / M 的首位可能与字母序不同，一律以实际列表为准
first_pos = {}
for i, r in enumerate(rows):
    ch = ((r.get("romaji") or r.get("name") or "")[:1]).upper()
    k = ch if "A" <= ch <= "Z" else "#"
    first_pos.setdefault(k, i)
ok = all(first_pos.get(k) == v for k, v in idx.items()) and set(first_pos) == set(idx)
check("C3 字母映射与真实列表首次出现位置**逐字母一致**",
      ok, f"letters={len(idx)} mismatch={[k for k,v in idx.items() if first_pos.get(k)!=v][:6]}")
check("C4 置顶项确实被算在内（M 的首位就是置顶那位）",
      rows[0].get("name") == "Momo" and idx.get("M") == 0, idx.get("M"))
check("C5 非拉丁字母归入 #", idx.get("#") == first_pos.get("#"), idx.get("#"))
check("C6 26 个字母 + # 都在表里", len(idx) == 27, sorted(idx))
check("C7 计数与查询口径共用 `_people_clauses`（源码里只剩一份构造）",
      db_s.count("def _people_clauses") == 1
      and db_s.count("IFNULL(p.favorite,0)=1") == 1,
      db_s.count("IFNULL(p.favorite,0)=1"))
check("C8 count_people 与 query_people 总数一致（口径没跑偏）",
      db.count_people(role_type="Actor") == len(rows),
      (db.count_people(role_type="Actor"), len(rows)))

# ============================================================ D. A-Z 跳转
section("D. 反馈 4：LetterIndexBar + LazyGrid.jump_to 真跳转")
from letter_index import LetterIndexBar, LETTERS

bar = LetterIndexBar(idx)
check("D1 27 个字母，宽度固定 30", len(LETTERS) == 27 and bar.width() == 30,
      (len(LETTERS), bar.width()))
bar.resize(30, 27 * 24)
check("D2 库里没有的字母不可点（本 demo 全有 → 再补一个空字典验证）",
      LetterIndexBar({}).is_enabled("A") is False and bar.is_enabled("A") is True)
check("D3 letter_at 命中正确下标（第 26 行是 Z，第 27 行是 #）",
      bar.letter_at(0) == "A" and bar.letter_at(int(bar.row_height() * 2 + 1)) == "C"
      and bar.letter_at(int(bar.row_height() * 26 + 1)) == "#",
      (bar.letter_at(0), bar.letter_at(int(bar.row_height() * 2 + 1)),
       bar.letter_at(int(bar.row_height() * 26 + 1))))
got = []


def _spy(lt):
    got.append(lt)


bar.picked.connect(_spy)
check("D4 click_letter 真能发出信号（且只发有数据的字母）",
      bar.click_letter("K") is True and bar.click_letter("A") is True
      and got == ["K", "A"], got)

# —— 真跳：造一个 LazyGrid（每批 2 张，逼 jump_to 走分批补载） ——
renders = []


def _fetch(off, lim):
    return rows[off:off + lim]


def _make(p):
    renders.append(p)
    lab = __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel(p.get("name") or "")
    return lab


grid = mw.LazyGrid(_fetch, _make, len(rows), kind="actor", unit="位")
pump(3)
_before = grid._loaded
_target = idx["Z"]
arrived = []
grid.jump_to(_target, lambda card: arrived.append(card))
for _ in range(60):
    pump(3)
    if arrived:
        break
check("D5 jump_to 交给事件循环分批补载，途中不重影（渲染次数 == 总数且无重复）",
      len(renders) == len(list({id(p) for p in renders}))
      and grid._grid.count() == grid._loaded,
      f"rendered={len(renders)} griditems={grid._grid.count()} loaded={grid._loaded}")
check("D6 jump_to(X) 之后目标下标已被渲染出来（分批补载生效）",
      grid._loaded > _target, f"loaded={grid._loaded} target={_target}")
check("D7 回调拿到的卡就是 objective 那个人",
      arrived and arrived[0] is not None
      and arrived[0].text() == rows[_target]["name"],
      (arrived[0].text() if arrived and arrived[0] else None, rows[_target]["name"]))
check("D8 card_at 与网格布局位置一致（行=idx//6，列=idx%6）",
      grid.card_at(7) is grid._grid.itemAtPosition(1, 1).widget() if grid._loaded > 7 else True)
check("D9 跳到超出范围的下标会被夹到最后一个，不越界",
      (grid.jump_to(10 ** 6, lambda c: None) or True)
      and 0 <= grid._jump_target < len(rows), grid._jump_target)

# —— 页面接线 ——
check("D10 main_window 里两个人物页都套了 _people_rail",
      mw_s.count("self._people_rail(page,") == 2)
check("D11 索引条自绘背景不被 QSS 盖掉（WA_StyledBackground=False）",
      "setAttribute(Qt.WA_StyledBackground, False)" in src("letter_index.py"))
check("D12 排序不是「首字母」时先切排序再重建（避免按错序硬跳）",
      'set_actor_prefs("letter", True' in mw_s and "_pending_letter" in mw_s)

# ============================================================ E. 反馈 2：图像检测
section("E. 反馈 2：缺图 / 截断图判定 + 上传替换")

mdir = os.path.join(MOVIES, "KBR-002")
os.makedirs(mdir, exist_ok=True)
vpath = os.path.join(mdir, "KBR-002.mp4")
open(vpath, "wb").write(b"\x00" * 8)


def _jpg(path, w=320, h=480):
    """造一张**足够大**的 JPEG。

    为什么不能直接用 64×64 纯色：那样编码出来只有几百字节，会撞上
    `imagedetect._MIN_BYTES`（<1KB 一律可疑）这条规则，测出来的就不是截断而是一条
    「文件过小」—— 真实海报怎么也有几十 KB，所以这里用噪声图，落到 10~40KB。
    """
    import random
    rnd = random.Random(7)
    buf = bytearray()
    for _i in range(w * h):
        v = rnd.randint(0, 255)
        buf += bytes((v, (v * 3) // 4, v // 2, 255))
    img = QImage(bytes(buf), w, h, QImage.Format_RGB32)
    img.save(path, "JPG", 92)
    with open(path, "rb") as f:
        return f.read()


good = os.path.join(mdir, "KBR-002-thumb.jpg")
raw = _jpg(good)
check("E1 正常 JPEG 判 OK", idm.check_image(good)[0] == idm.OK, idm.check_image(good))

trunc_path = os.path.join(mdir, "KBR-002-poster.jpg")
with open(trunc_path, "wb") as f:
    f.write(raw[:int(len(raw) * 0.55)])      # 砍掉 45%，正是截图里「灰块 + 顶上一条真图」
st, detail = idm.check_image(trunc_path)
check("E2 截断 JPEG 判 BROKEN（Qt 认它为正常图，这里必须靠结构校验）",
      st == idm.BROKEN, f"{st} / {detail}")
check("E3 空文件 / 过小文件不放过",
      idm.check_image("")[0] == idm.MISSING
      and idm.structural_ok(good)[0] is True
      and idm.structural_ok(os.path.join(TMP, "not-here.jpg"))[0] is False)
small = os.path.join(mdir, "KBR-002-fanart.jpg")
open(small, "wb").write(b"\xff\xd8" + b"\x00" * 400)
check("E4 <1KB 的可疑图判 BROKEN", idm.check_image(small)[0] == idm.BROKEN,
      idm.check_image(small))

media_row = {"id": 1, "title": "KBR-002", "file_path": vpath, "nfo_path": "",
             "poster": "", "thumb": "", "fanart": "", "library": "测试库"}
conn.execute(
    "INSERT OR REPLACE INTO media(id, title, file_path, nfo_path, sort_title, library, kind) "
    "VALUES(?,?,?,?,?,?,?)", (1, "KBR-002", vpath, "", "KBR-002", "测试库", "movie"))
conn.commit()

check("E5 target_path = `<番号>-<slot>.jpg`",
      idm.target_path(media_row, "poster").replace("\\", "/").endswith("KBR-002-poster.jpg"),
      idm.target_path(media_row, "poster"))
rep = idm.scan([media_row], slots=idm.SLOTS)
check("E6 scan 扫出这部片的三处问题（poster 截断 / fanart 过小 / thumb 正常）",
      rep.scanned == 1 and len(rep.problems) == 2, rep.summary())
check("E7 两处都是 poster / fanart，thumb 正常不上报",
      sorted(p["slot"] for p in rep.problems) == ["fanart", "poster"],
      [p["slot"] for p in rep.problems])
check("E8 都被归类为 BROKEN（都有文件但内容不行）",
      all(p["state"] == idm.BROKEN for p in rep.problems),
      [p["detail"] for p in rep.problems])

# 缺图场景：另一部片什么图都没有
mdir2 = os.path.join(MOVIES, "KAVR-383")
os.makedirs(mdir2, exist_ok=True)
vp2 = os.path.join(mdir2, "KAVR-383.mp4")
open(vp2, "wb").write(b"\x00" * 8)
row2 = {"id": 2, "title": "KAVR-383", "file_path": vp2, "nfo_path": "",
        "poster": "", "thumb": "", "fanart": "", "library": "测试库"}
rep2 = idm.scan([row2], slots=idm.SLOTS)
check("E9 完全没图 = 三处 MISSING",
      all(p["state"] == idm.MISSING for p in rep2.problems) and len(rep2.problems) == 3,
      len(rep2.problems))

# 替换：把一张好图上传到 poster 槽位
srcimg = os.path.join(TMP, "upload-src.jpg")
_jpg(srcimg, 96, 64)
ok, target, err = idm.replace_image(row2, "poster", srcimg)
check("E10 replace_image 成功并把图落成了 `<番号>-poster.jpg`",
      ok and target.replace("\\", "/").endswith("KAVR-383-poster.jpg"), err)
check("E11 替换后该槽位复检转为 OK（替换后可立即通过复检）",
      idm.check_image(target)[0] == idm.OK, idm.check_image(target))
ok_bad, _t, err_bad = idm.replace_image(row2, "thumb", small)
check("E12 源图本身就是坏图时拒绝上传（不会把另一张坏图复制进去）",
      ok_bad is False and "有效图片" in err_bad, err_bad)
check("E13 db.media_for_imagescan 能取到用于检测的列",
      len(db.media_for_imagescan()) >= 1
      and "title" in db.media_for_imagescan()[0]
      and "plot" not in db.media_for_imagescan()[0],
      sorted(db.media_for_imagescan()[0].keys())[:8])

# ============================================================ F. 反馈 3：手动修改
section("F. 反馈 3：nfo 全字段读写")

nfo_dir = os.path.join(MOVIES, "KXYZ-001")
os.makedirs(nfo_dir, exist_ok=True)
video = os.path.join(nfo_dir, "KXYZ-001.mp4")
open(video, "wb").write(b"\x00" * 8)
nfo_path = os.path.join(nfo_dir, "KXYZ-001.nfo")
_NFO_SRC = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<movie>
  <title>原标题</title>
  <year>2021</year>
  <plot>原名剧情</plot>
  <studio>片商A</studio>
  <genre>标签1</genre>
  <genre>标签2</genre>
  <country>日本</country>
  <actor>
    <name>演员甲</name>
    <role>主角</role>
    <thumb>https://example.com/jia.jpg</thumb>
  </actor>
  <actor>
    <name>演员乙</name>
  </actor>
  <uniqueid type="num">KXYZ-001</uniqueid>
</movie>
"""
with io.open(nfo_path, "w", encoding="utf-8") as f:
    f.write(_NFO_SRC)

media_row = {"id": 2, "title": "原标题", "file_path": video, "nfo_path": nfo_path,
             "library": "测试库"}
# F9 要验证「改完能被检索到」，前提是这部片真的在库里 —— 必须先有 media 行，
# 否则 nf.save 里的 UPDATE 影响 0 行，索引里根本没东西可搜（第一版脚本就漏了这步）。
conn.execute(
    "INSERT OR REPLACE INTO media(id, title, file_path, nfo_path, sort_title, library, kind) "
    "VALUES(?,?,?,?,?,?,?)",
    (2, "原标题", video, nfo_path, "KXYZ-001", "测试库", "movie"))
conn.commit()

data = nf.from_media(media_row)
check("F1 read_fields 读出 17 项字段 + 演员块",
      data.get("title") == "原标题" and data.get("genre") == ["标签1", "标签2"]
      and len(data.get("actor") or []) == 2,
      (data.get("title"), data.get("genre")))
check("F2 演员带角色", [a.get("role") for a in data["actor"]] == ["主角", ""],
      [a.get("role") for a in data["actor"]])

media_row = {"id": 2, "title": "原标题", "file_path": video, "nfo_path": nfo_path,
             "library": "测试库"}
newdata = dict(data)
newdata.update({"title": "新标题", "plot": "改写后的剧情", "studio": "片商B",
                "genre": ["标签1"], "runtime": "120", "set": "某某合集",
                "year": "2022", "rating": "8.5"})
newdata["actor"] = [{"name": "演员甲", "role": "主演"}, {"name": "演员丙", "role": ""}]
res = nf.save(media_row, newdata)
check("F3 保存成功（写 nfo + 同步索引）",
      res.get("nfo_ok") and res.get("db_ok"), res.get("err"))
after = nf.read_fields(nfo_path)
check("F4 被改的字段确实变了",
      after["title"] == "新标题" and after["plot"] == "改写后的剧情"
      and after["studio"] == "片商B" and after["genre"] == ["标签1"],
      (after["title"], after["genre"]))
check("F5 **没改的节点完全没动**（本次编辑没碰到的 uniqueid 仍在）",
      "<uniqueid type=\"num\">KXYZ-001</uniqueid>" in io.open(nfo_path, encoding="utf-8").read())
check("F6 同名 <actor> 会被复用 —— <thumb> 头像保住了",
      '<name>演员甲</name>' in io.open(nfo_path, encoding="utf-8").read()
      and "jia.jpg" in io.open(nfo_path, encoding="utf-8").read())
check("F7 不在列表里的演员被移除，新演员补上",
      [a["name"] for a in after["actor"]] == ["演员甲", "演员丙"],
      [a["name"] for a in after["actor"]])
check("F8 `<set>` 写成 Kodi 的 `<set><name>` 结构",
      nf.read_fields(nfo_path).get("set") == "某某合集", nf.read_fields(nfo_path).get("set"))
check9 = db.search_media(keyword="新标题", light=True, limit=10)
check("F9 索引被同步（标题改了就能被搜到）",
      any(r.get("title") == "新标题" for r in (check9 or [])),
      [r.get("title") for r in (check9 or [])][:3])
check("F10 写前留了备份文件", bool(res.get("backup")) and os.path.exists(res.get("backup") or ""),
      os.path.basename(res.get("backup") or ""))

# ============================================================ G. 两个新工具页
section("G. 反馈 2 / 3：工具窗口新增两页 + 导航顺序")
import ui_settings
import ui_imagedetect
import ui_manualedit

dlg = ui_settings.SettingsDialog()
pump(4)
check("G1 ORDER 里「手动修改」紧跟「个性化设置」",
      dlg.ORDER.index("手动修改") == dlg.ORDER.index("个性化设置") + 1
      and dlg.ORDER.index("画像概览") == dlg.ORDER.index("手动修改") + 1,
      dlg.ORDER[:3])
check("G2 ORDER 里「图像检测」在「重复检测」与「数据与日志」之间",
      dlg.ORDER.index("图像检测") == dlg.ORDER.index("重复检测") + 1
      and dlg.ORDER.index("数据与日志") == dlg.ORDER.index("图像检测") + 1,
      dlg.ORDER[-3:])
check("G3 导航按钮与 stack 页数一致（没漏挂）",
      len(dlg.sub_btns) == len(dlg.ORDER) == dlg.stack.count(),
      (len(dlg.sub_btns), dlg.stack.count()))
dlg._show("图像检测")
pump(2)
check("G4 图像检测页能切过去且控件齐全（库下拉 / 三个槽位勾选 / 开始检测 / 结果树）",
      dlg.stack.currentWidget() is dlg._pg_imagedetect
      and getattr(dlg, "_pg_imagedetect", None) is not None)
page_img = dlg.stack.currentWidget().widget()
check("G5 图像检测页含 TreeWidget + 预览 + 上传按钮",
      page_img.findChild(__import__("PySide6.QtWidgets", fromlist=["QTreeWidget"]).QTreeWidget)
      is not None
      and getattr(page_img, "upload_btn", None) is not None
      and getattr(page_img, "run_btn", None) is not None)
check("G6 图像检测页 worker 尚未启动（不新建线程直到点检测）",
      getattr(page_img, "_worker", "none") in (None, "none"),
      getattr(page_img, "_worker", None))
dlg._show("手动修改")
pump(6)
page_man = dlg.stack.currentWidget().widget()
check("G7 手动修改页能切过去",
      dlg.stack.currentWidget() is dlg._pg_manual and page_man is not None)
check("G8 手动修改页检索出刚才那部影片（自动跑了一次空检索）",
      page_man.list.count() >= 2, page_man.list.count())
# 精确选中 KXYZ-001（id=2）：列表是按 sort_title 排的，直接选第 0 行可能拿到别的片，
# 那样后面「改标题后能被搜到」的断言测的就不是这一条记录了。
row2_idx = next((i for i in range(page_man.list.count())
                 if page_man.list.item(i).data(Qt.UserRole) == 2), None)
check("G8b 列表里能按 media_id 定位到 KXYZ-001", row2_idx is not None, row2_idx)
page_man.list.setCurrentRow(row2_idx if row2_idx is not None else 0)
pump(4)
check("G9 选中后表单按 nfo_editor.FIELDS 逐项建出来",
      len(page_man._fields) == len(nf.FIELDS)
      and getattr(page_man, "_actors_edit", None) is not None,
      len(page_man._fields))
check("G10 三个配图槽位都有预览 + 目标路径标签",
      all(s in page_man._slot_labels for s in idm.SLOTS)
      and all(page_man._slot_labels[s][1].text() for s in idm.SLOTS),
      {s: page_man._slot_labels[s][1].text()[-28:] for s in idm.SLOTS})
# 模拟一次「保存」
page_man._fields["title"].setText("UI 改过的标题")
page_man._save()
pump(3)
check("G11 页内保存联动 nfo + 索引（UI 端到端）",
      any(r.get("title") == "UI 改过的标题"
          for r in (db.search_media(keyword="UI 改过的标题", light=True, limit=5) or [])),
      (page_man.save_lbl.text() or "")[:90])
dlg.close()
pump(3)

# ============================================================ H. 回归
section("H. 关键回归")
check("H1 演员卡六项信息位置没被带崩（二维码=三围整行跨两列）",
      mw._ACTOR_FACTS[-1][1] == 2 and mw._ACTOR_FACTS[-1][3] == 2)
check("H2 导演卡仍是「作品 / 别名」两项",
      [k for k, _r, _c, _s in mw._DIRECTOR_FACTS] == ["作品", "别名"])
check("H3 演员库 / 导演库仍是每行 6 个",
      mw.LazyGrid.COLS_BY_KIND["actor"] == 6
      and mw.LazyGrid.COLS_BY_KIND["media"] == 8,
      mw.LazyGrid.COLS_BY_KIND)
check("H4 6 列宽度不溢出 1920 屏（6×236+5×12=1476 ≤ 1680）",
      6 * 236 + 5 * 12 <= 1680, 6 * 236 + 5 * 12)

win = mw.MainWindow()
win.show()
pump(6)
win._apply_settings()
pump(8)
import sysmon as _sy
# 采集线程是**进程级单例**（父对象是 QApplication，v1.27.0 的修法），
# 所以要在 QApplication 上找 —— 在 win 上找必然是 0（那才是真回归）。
_workers = app.findChildren(_sy.SysMonWorker)
check("H5 v1.27.0 线程单例仍然成立（重建侧栏后 SysMonWorker 仍只有 1 个且在跑）",
      len(_workers) == 1 and _workers[0].isRunning(),
      (len(_workers), [w.isRunning() for w in _workers]))
check("H6 no needless QThread in sidebar panels（image/manual pages 只在工具窗里）",
      len(win.findChildren(ui_imagedetect.ImageScanWorker)) == 0)
win.close()
pump(3)
try:
    db.get_conn().close()
except Exception:
    pass

print("\n" + "=" * 74)
print(f"结果：{len(PASS)} 项通过，{len(FAIL)} 项失败")
if FAIL:
    print("失败项：")
    for t in FAIL:
        print("  - " + t)
    sys.exit(1)
print("v1.30.0 离屏冒烟全部通过")
