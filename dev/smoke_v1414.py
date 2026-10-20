# -*- coding: utf-8 -*-
"""v1.40.14 冒烟（离屏，不截图）：右键搜索点选 = 替换本片该位演员/导演
============================================================================
本轮（v1.40.14，用户反馈「点击联想结果就应该改变影片内演员/导演信息，而不是跳到工具界面」）：
  · 详情页演职人员信息区右键 → 「输入框 + 演员库/导演库联想」搜索框（v1.40.13 已交付）；
  · **点选结果（单击项 / 回车）不再跳「工具」界面**，而是把**当前影片该位**演员/导演
    就地替换为所选人：
      - `db.replace_media_person(media_id, old, new)` 只改这一部作品的 media_people 关联；
      - `HeroView._apply_person_replace` → 就地重建「演职人员信息」区（`_refresh_cast`）；
      - `on_person_replaced(old, new)` → 主窗状态栏提示。
  · 三种情况：old==new 无操作；new 已在本片 → 删 old 去重（merged）；否则就地改指（replaced）。

本脚本以**数据断言**取代肉眼截图（交付不再附截图）。
  ① 源码层：database.py / ui_hero.py / ui_home.py / main_window.py / version.py 改动到位，
     且旧的 on_open_context / _open_person_tool 路径已移除；
  ② 真建控件（临时索引库）：
       · db.replace_media_person 的 replaced / merged / noop / missing 四种语义 + 其它作品不受影响；
       · HeroView._apply_person_replace → 本片关联改指 + 「演职人员信息」块就地刷新（新名出现、旧名消失）；
       · CastAvatar.contextMenuEvent（桩 PersonSearchDialog）→ on_context(old, new) 同时带回新旧两人。
  ③ 版本号 MINOR_ITER = 14 / BUILD_SEQ = "0077"。

跑法（务必用 E 盘绝对路径）：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/smoke_v1414.py"
"""
import os
import sys
import tempfile

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QFontDatabase, QContextMenuEvent

OK = []
BAD = []


def chk(cond, msg):
    (OK if cond else BAD).append(msg)
    print(("[OK ] " if cond else "[FAIL] ") + msg)


# ---------- ① 源码层 ----------
print("=" * 72)
print("① 源码层断言")
print("=" * 72)

HSRC = open(os.path.join(ROOT, "src", "ui_hero.py"), encoding="utf-8").read()
DBSRC = open(os.path.join(ROOT, "src", "database.py"), encoding="utf-8").read()
HMSRC = open(os.path.join(ROOT, "src", "ui_home.py"), encoding="utf-8").read()
MWSRC = open(os.path.join(ROOT, "src", "main_window.py"), encoding="utf-8").read()
VSRC = open(os.path.join(ROOT, "src", "version.py"), encoding="utf-8").read()

# ---- 数据层 ----
chk("def replace_media_person(media_id: int, old_person_id: int, new_person_id: int) -> dict:" in DBSRC,
    "database.py 新增 replace_media_person(media_id, old, new)")
chk('UPDATE media_people SET person_id=?' in DBSRC,
    "replace_media_person 就地改指（UPDATE media_people SET person_id）")
chk('DELETE FROM media_people WHERE media_id=? AND person_id=?' in DBSRC,
    "replace_media_person 对「new 已在本片」做去重删除")

# ---- 详情页：点选即替换本片该位 + 就地刷新 ----
chk("def _apply_person_replace(self, old_person, new_person):" in HSRC,
    "HeroView 新增 _apply_person_replace(old, new)")
chk("def _refresh_cast(self):" in HSRC,
    "HeroView 新增 _refresh_cast（就地重建演职人员信息块）")
chk("db.replace_media_person(mid, old_id, new_id)" in HSRC,
    "_apply_person_replace 调 db.replace_media_person")
chk("on_context=self._apply_person_replace" in HSRC,
    "_cast_section 把 CastAvatar 的 on_context 接到 _apply_person_replace")
chk("on_pick=lambda p: self.on_context(self.person, p)" in HSRC,
    "CastAvatar 右键点选 → on_context(old_person, new_person)")
chk("self._cast_box = self._cast_section(m)" in HSRC,
    "_build 保存 _cast_box 引用（供就地刷新）")
chk("self._body_layout = bv" in HSRC,
    "_build 保存 _body_layout 引用（供就地刷新）")

# ---- 回调链改名：on_open_context / _open_person_tool 必须已移除 ----
chk("on_person_replaced" in HSRC and "on_person_replaced" in HMSRC and "on_person_replaced" in MWSRC,
    "on_person_replaced 回调已贯穿 ui_hero / ui_home / main_window")
chk("on_open_context" not in HSRC and "on_open_context" not in HMSRC and "on_open_context" not in MWSRC,
    "旧的 on_open_context 已全部移除")
chk("_open_person_tool" not in MWSRC,
    "旧的 _open_person_tool（跳工具界面）已移除")
chk("def _after_person_replaced(self, old_person, new_person):" in MWSRC,
    "main_window 新增 _after_person_replaced（状态栏提示，不再跳工具）")

# ---- 版本号 ----
chk("MINOR_ITER = 14" in VSRC, "version.py MINOR_ITER = 14")
chk('BUILD_SEQ = "0077"' in VSRC, 'version.py BUILD_SEQ = "0077"')
chk('BUILD_DATE = "261015"' in VSRC, 'version.py BUILD_DATE = "261015"')

# ---------- ② 真建控件 ----------
print()
print("=" * 72)
print("② 真建控件断言（临时索引库）")
print("=" * 72)

_tmp = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1414", "index_data")
os.makedirs(_tmp, exist_ok=True)
_db_path = os.path.join(_tmp, "media_center.db")

import database as db
import applog as applog_mod
db.db_path = lambda: _db_path
applog_mod.log_dir = lambda: _tmp
db.init_db()

_conn = db.get_conn()
_conn.execute("DELETE FROM media_people")
_conn.execute("DELETE FROM media")
_conn.execute("DELETE FROM people")
for nm, rt in [("张伟", "Actor"), ("张敏", "Actor"), ("张艺谋", "Director"), ("李安", "Director")]:
    _conn.execute("INSERT INTO people (name, role_type) VALUES (?,?)", (nm, rt))
_pid = {r["name"]: r["id"] for r in _conn.execute("SELECT id, name FROM people").fetchall()}
# 作品 100（要替换的）、作品 200（不应受影响）
_conn.execute("INSERT INTO media (id, kind, title, year) VALUES (100, 'movie', '测试片100', 2020)")
_conn.execute("INSERT INTO media (id, kind, title, year) VALUES (200, 'movie', '测试片200', 2021)")
_conn.execute("INSERT INTO media (id, kind, title, year) VALUES (300, 'movie', '测试片300', 2022)")
# 100: 张伟(角色A,0) + 张敏(角色B,1)；200: 张伟；300: 张伟 + 张敏
_conn.execute("INSERT INTO media_people (media_id, person_id, char_role, person_order) VALUES (100,?,?,0)",
              (_pid["张伟"], "角色A"))
_conn.execute("INSERT INTO media_people (media_id, person_id, char_role, person_order) VALUES (100,?,?,1)",
              (_pid["张敏"], "角色B"))
_conn.execute("INSERT INTO media_people (media_id, person_id, char_role, person_order) VALUES (200,?,?,0)",
              (_pid["张伟"], "角色X"))
_conn.execute("INSERT INTO media_people (media_id, person_id, char_role, person_order) VALUES (300,?,?,0)",
              (_pid["张伟"], "角色A"))
_conn.execute("INSERT INTO media_people (media_id, person_id, char_role, person_order) VALUES (300,?,?,1)",
              (_pid["张敏"], "角色B"))
_conn.commit()


def _links(mid):
    return {(r["person_id"], r["char_role"], r["person_order"])
            for r in _conn.execute(
                "SELECT person_id, char_role, person_order FROM media_people WHERE media_id=?", (mid,)).fetchall()}


app = QApplication([])
try:
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
except Exception:
    pass
import ui_hero as uh

# ---- replace_media_person：replaced ----
r = db.replace_media_person(100, _pid["张伟"], _pid["张艺谋"])
chk(r.get("ok") and r.get("action") == "replaced",
    "replace_media_person(100, 张伟→张艺谋) → replaced")
chk((_pid["张艺谋"], "角色A", 0) in _links(100) and (_pid["张伟"], "角色A", 0) not in _links(100),
    "本片 100 关联就地改指到 张艺谋，且 char_role/order 保留")
chk((_pid["张伟"], "角色X", 0) in _links(200),
    "其它作品 200 的关联不受影响（仍指向 张伟）")

# ---- replace_media_person：merged（new 已在本片）----
r = db.replace_media_person(100, _pid["张敏"], _pid["张艺谋"])
chk(r.get("ok") and r.get("action") == "merged",
    "replace_media_person(100, 张敏→张艺谋 已在片内) → merged 去重")
chk(_pid["张敏"] not in {p for p, _, _ in _links(100)},
    "merged 后 张敏 的关联被删除")

# ---- noop / missing ----
r = db.replace_media_person(100, _pid["张艺谋"], _pid["张艺谋"])
chk(r.get("ok") and r.get("action") == "noop", "old==new → noop")
r = db.replace_media_person(100, 999999, _pid["李安"])
chk((not r.get("ok")) and r.get("action") == "missing", "old 不在本片 → missing（ok=False）")

# ---- HeroView._apply_person_replace + _refresh_cast（作品 300）----
fired = []
hv = uh.HeroView({"id": 300, "title": "测试片300", "year": 2022, "kind": "movie"},
                 on_open_actor=lambda p: None,
                 on_person_replaced=lambda old, new: fired.append((old, new)))
hv.resize(1000, 700)
box_before = hv._cast_box


def _names(w):
    return {l.text() for l in w.findChildren(QLabel)}


chk("张伟" in _names(box_before), "刷新前：演职人员信息块含「张伟」")
hv._apply_person_replace({"id": _pid["张伟"], "name": "张伟"},
                         {"id": _pid["张艺谋"], "name": "张艺谋"})
for _ in range(3):
    app.processEvents()
chk(hv._cast_box is not box_before, "_apply_person_replace 后就地重建了演职人员信息块（新对象）")
_nb = _names(hv._cast_box)
chk("张艺谋" in _nb and "张伟" not in _nb,
    "刷新后：本片该位已换成「张艺谋」，旧「张伟」消失")
chk(_pid["张艺谋"] in {p for p, _, _ in _links(300)} and _pid["张伟"] not in {p for p, _, _ in _links(300)},
    "本片 300 的 media_people 关联已改指到 张艺谋")
chk(len(fired) == 1 and fired[0][0]["id"] == _pid["张伟"] and fired[0][1]["id"] == _pid["张艺谋"],
    "on_person_replaced 回调带回 (old=张伟, new=张艺谋)")

# ---- CastAvatar.contextMenuEvent：点选 → on_context(old, new) ----
_orig_dlg = uh.PersonSearchDialog


class _FakeDlg:
    last = None

    def __init__(self, initial=None, old_name=None, on_pick=None, parent=None):
        self.initial = initial
        self.old_name = old_name
        self.on_pick = on_pick
        _FakeDlg.last = self

    def move_to(self, gp):
        pass

    def exec(self):
        # 模拟用户点选「李安（导演）」
        self.on_pick({"id": _pid["李安"], "name": "李安", "role_type": "Director"})


uh.PersonSearchDialog = _FakeDlg
try:
    got = []
    av = uh.CastAvatar({"id": _pid["张伟"], "name": "张伟", "role_type": "Actor", "photo_path": ""},
                       lambda p: None, on_context=lambda old, new: got.append((old, new)))
    av.show()
    rctx = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5))
    av.contextMenuEvent(rctx)
    chk(_FakeDlg.last is not None and _FakeDlg.last.old_name == "张伟",
        "CastAvatar 右键 → 弹出搜索框，old_name = 当前人头像姓名")
    chk(len(got) == 1 and got[0][0]["id"] == _pid["张伟"] and got[0][1]["name"] == "李安"
        and got[0][1]["role_type"] == "Director",
        "CastAvatar 右键点选 → on_context(old, new) 带回旧人 + 所选导演（导演也可替换）")
finally:
    uh.PersonSearchDialog = _orig_dlg

# ---------- ③ 汇总 ----------
print()
print("=" * 72)
print("汇总：%d 通过 / %d 失败" % (len(OK), len(BAD)))
print("=" * 72)
for b in BAD:
    print("  FAIL:", b)

sys.exit(1 if BAD else 0)
