# -*- coding: utf-8 -*-
"""v1.40.13 冒烟（离屏，不截图）：详情页演员/导演头像右键「输入框 + 演员/导演库联想」
============================================================================
本轮（v1.40.13，用户需求「右键出现输入框，根据输入在演员库/导演库联想，输全确认
或单击选中 → 编辑该演员/导演」）：
  · 详情页 CastAvatar.contextMenuEvent 不再弹 QMenu 单动作，改为弹
    PersonSearchDialog（QLineEdit + QListWidget）：
      - 输入即查 db.search_people(kw)（跨 Actor + Director 两库按 name/alias/romaji 子串联想）；
      - 单击列表项 或 输入框回车（自动选中顶部项）→ 选中该人，回调 on_context(person_dict)；
      - 选中的 person dict 透传 _open_person_tool → open_person_editor（按 id 载入，演员/导演通用）。
  · 新增 database.search_people(keyword, role_types, limit)：默认跨 Actor+Director。

防回退（保留 v1.40.12 关键断言）：
  · CastAvatar 左键单击/双击仍进入详情（on_click）；
  · open_person_editor 对导演按 id 载入（演员/导演通用）；
  · 执行日志框样式 == 运行日志框样式（同 LOG_BOX_STYLE + NoWrap）。

本脚本以**数据断言**取代肉眼截图（交付不再附截图）。
  ① 源码层：ui_hero.py / database.py / ui_settings.py / version.py 关键改动到位；
  ② 真建控件（假屏幕复刻真机 2560×1392）：
       · 真建临时索引库，插入演员 + 导演若干（共享「张」字），断言 db.search_people 跨两库返回；
       · 真建 PersonSearchDialog，断言 _refresh(关键字) 列表同时含 Actor 与 Director，
         且 _pick(选中项) 触发 on_pick 回调并带回 id/name/role_type；
       · CastAvatar.contextMenuEvent 用桩 PersonSearchDialog 替换（exec 不阻塞），
         断言右键打开的是「搜索框」且选中人回传到 on_context（导演亦可编辑）；
  ③ 版本号 MINOR_ITER = 13 / BUILD_SEQ = "0076"。

跑法（务必用 E 盘绝对路径）：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/smoke_v1413.py"
"""
import os
import re
import sys
import tempfile

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import (QApplication, QScrollArea, QGroupBox, QLabel, QVBoxLayout)
from PySide6.QtCore import QRect, Qt, QEvent, QPoint, QTimer
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
SSRC = open(os.path.join(ROOT, "src", "ui_settings.py"), encoding="utf-8").read()
MWSRC = open(os.path.join(ROOT, "src", "main_window.py"), encoding="utf-8").read()
VSRC = open(os.path.join(ROOT, "src", "version.py"), encoding="utf-8").read()

# ---- 右键交互改为「输入框 + 联想」对话框 ----
chk("class PersonSearchDialog(QDialog):" in HSRC,
    "ui_hero.py 新增 PersonSearchDialog（输入框 + 联想列表）")
chk("def __init__(self, initial=None, on_pick=None, parent=None):" in HSRC,
    "PersonSearchDialog.__init__ 收 initial / on_pick 形参")
chk('self._edit = QLineEdit()' in HSRC,
    "PersonSearchDialog 含输入输入框 QLineEdit")
chk('self._list = QListWidget()' in HSRC,
    "PersonSearchDialog 含联想列表 QListWidget")
chk("def search_people(" in DBSRC,
    "database.py 新增 search_people(keyword, role_types, limit)")
chk("db.search_people(" in HSRC,
    "PersonSearchDialog._refresh 调 db.search_people 做联想")

# 旧 QMenu 单动作路径必须已移除
chk("搜索并编辑信息" not in HSRC,
    "旧的「搜索并编辑信息」QMenu 单动作已移除（右键改为搜索框）")
chk("self.on_context(self.person)" not in HSRC,
    "contextMenuEvent 不再直接调 self.on_context(person)（改走对话框 on_pick）")
chk("on_pick=self.on_context" in HSRC,
    "contextMenuEvent 把 on_context 作为 on_pick 传给 PersonSearchDialog")
chk("PersonSearchDialog(initial=(self.person or {}).get(\"name\")" in HSRC,
    "contextMenuEvent 以当前人姓名作为搜索框初始值弹出")

# ---- 选中回调落到编辑链路（演员/导演通用）----
chk("def open_person_editor(self, person):" in SSRC,
    "SettingsDialog 仍有 open_person_editor(person)")
chk("pg._load_person(int(pid))" in SSRC,
    "open_person_editor 按 id 调 _load_person 载入（演员/导演通用）")
chk("dlg.open_person_editor(person)" in MWSRC,
    "_open_person_tool 调 open_person_editor(person)")

# ---- 防回退：左键单击/双击仍进入详情 ----
chk('if e.button() == Qt.LeftButton and self.on_click:' in HSRC,
    "[防回退] CastAvatar.mousePressEvent 仅左键触发 on_click")
chk('def mouseDoubleClickEvent(self, e):' in HSRC,
    "[防回退] CastAvatar 仍有 mouseDoubleClickEvent（双击进入）")
chk('for _c in self.findChildren(QWidget):' in HSRC
    and '_c.setContextMenuPolicy(Qt.NoContextMenu)' in HSRC,
    "[防回退] CastAvatar 子控件设 NoContextMenu（右键归到本框）")

# ---- 防回退：执行日志框样式 == 运行日志框 ----
chk("LOG_BOX_STYLE =" in SSRC,
    "[防回退] 模块级 LOG_BOX_STYLE 常量仍存在")
chk("self.sc_log.setStyleSheet(LOG_BOX_STYLE)" in SSRC
    and "self._log_view.setStyleSheet(LOG_BOX_STYLE)" in SSRC,
    "[防回退] 执行日志框与运行日志框仍复用同一 LOG_BOX_STYLE")

# ---- 版本号 ----
chk("MINOR_ITER = 13" in VSRC, "version.py MINOR_ITER = 13")
chk('BUILD_SEQ = "0076"' in VSRC, 'version.py BUILD_SEQ = "0076"')
chk('BUILD_DATE = "261015"' in VSRC, 'version.py BUILD_DATE = "261015"')

# ---------- ② 真建控件 ----------
print()
print("=" * 72)
print("② 真建控件断言（假屏幕复刻真机 2560×1392，临时索引库）")
print("=" * 72)

# 临时索引库（绝不碰真实 index_data）
_tmp = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1413", "index_data")
os.makedirs(_tmp, exist_ok=True)
_db_path = os.path.join(_tmp, "media_center.db")

import database as db
import applog as applog_mod
db.db_path = lambda: _db_path
applog_mod.log_dir = lambda: _tmp   # 重定向运行日志目录（绝不影响真实 index_data）
db.init_db()

# 插入演员 + 导演（共享「张」字便于联想断言）
_conn = db.get_conn()
_conn.execute("DELETE FROM people")
_rows = [
    ("张伟", "Actor", "伟哥", "zhangwei"),
    ("张敏", "Actor", "", "zhangmin"),
    ("王宝强", "Actor", "", "wangbaoqiang"),
    ("张艺谋", "Director", "", "zhangyimou"),
    ("李安", "Director", "", "liang"),
    ("陈凯歌", "Director", "", "chenkaige"),
]
for nm, rt, al, ro in _rows:
    _conn.execute("INSERT INTO people (name, role_type, alias, romaji) VALUES (?,?,?,?)",
                  (nm, rt, al, ro))
_conn.commit()

app = QApplication([])
try:
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
except Exception:
    pass

import ui_hero as uh
import ui_settings as uis

# ---- db.search_people 跨两库联想 ----
res = db.search_people("张", limit=60)
_role = {r["role_type"] for r in res}
_names = {r["name"] for r in res}
chk(_names >= {"张伟", "张敏", "张艺谋"} and res,
    "db.search_people('张') 返回命中结果（含 张伟/张敏/张艺谋）")
chk("Actor" in _role and "Director" in _role,
    "db.search_people 同时覆盖 演员库(Actor) 与 导演库(Director)")

# 别名联想
res_alias = db.search_people("伟哥", limit=60)
chk(any(r["name"] == "张伟" for r in res_alias),
    "db.search_people('伟哥') 经 alias 命中 张伟")

# romaji 联想（大小写不敏感）
res_ro = db.search_people("zhang", limit=60)
chk(any(r["role_type"] == "Director" and r["name"] == "张艺谋" for r in res_ro),
    "db.search_people('zhang') 经 romaji 命中 张艺谋（导演）")

# ---- 真建 PersonSearchDialog：输入框联想 + 选中回调 ----
picked = []
dlg = uh.PersonSearchDialog(initial=None, on_pick=lambda p: picked.append(p))
dlg.show()
for _ in range(4):
    app.processEvents()
dlg._refresh("张")
chk(dlg._list.count() >= 3,
    "PersonSearchDialog._refresh('张') 列表刷新出 >=3 条联想")
_dlg_roles = set()
for i in range(dlg._list.count()):
    _dlg_roles.add(dlg._list.item(i).data(Qt.UserRole)["role_type"])
chk("Actor" in _dlg_roles and "Director" in _dlg_roles,
    "PersonSearchDialog 联想列表同时含 演员 与 导演")
# 模拟用户单击列表第 0 项 → 选中并回调
_top = dlg._list.item(0).data(Qt.UserRole)
dlg._on_item_clicked(dlg._list.item(0))
chk(len(picked) == 1 and picked[0]["id"] == _top["id"]
    and picked[0].get("name") and picked[0].get("role_type"),
    "单击联想项 → on_pick 回调带回该人（id/name/role_type 齐全）")
# 模拟回车（无显式选中时取顶部项）
picked.clear()
dlg._list.setCurrentRow(-1)
dlg._edit.setText("张艺谋")
for _ in range(3):
    app.processEvents()
dlg._on_return()
chk(len(picked) == 1 and picked[0]["name"] == "张艺谋" and picked[0]["role_type"] == "Director",
    "输入框回车（自动选中顶部）→ 选中 张艺谋（导演）并回调")
del dlg

# ---- CastAvatar.contextMenuEvent：右键打开搜索框、选中人回传 on_context ----
# 用桩替换 PersonSearchDialog，使 exec() 不弹真窗、直接模拟用户选中一名导演
_orig_dlg = uh.PersonSearchDialog


class _FakeDlg:
    last = None

    def __init__(self, initial=None, on_pick=None, parent=None):
        self.initial = initial
        self.on_pick = on_pick
        self.moved = None
        _FakeDlg.last = self

    def move_to(self, gp):
        self.moved = gp

    def exec(self):
        # 模拟用户从联想列表选中一名导演
        self.on_pick({"id": 99, "name": "张艺谋", "role_type": "Director"})


uh.PersonSearchDialog = _FakeDlg
try:
    cap = type("Cap", (), {"ctxs": []})()
    av = uh.CastAvatar({"id": 7, "name": "演员X", "role_type": "Actor"},
                       lambda p: None, on_context=lambda p: cap.ctxs.append(p))
    av.show()
    rctx = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5))
    av.contextMenuEvent(rctx)
    chk(_FakeDlg.last is not None and _FakeDlg.last.initial == "演员X",
        "CastAvatar 右键 → 弹出 PersonSearchDialog，且以当前人姓名作初始值")
    chk(len(cap.ctxs) == 1 and cap.ctxs[0]["role_type"] == "Director"
        and cap.ctxs[0]["name"] == "张艺谋",
        "CastAvatar 右键 → 从联想列表选中导演 → on_context 收到该导演（导演可编辑）")
finally:
    uh.PersonSearchDialog = _orig_dlg

# ---- open_person_editor 对导演按 id 载入（防回退）----
_orig_gp = db.get_person


def _fake_get_person(pid):
    return {"id": int(pid), "name": "张艺谋", "role_type": "Director",
            "alias": "", "romaji": "", "birthday": "", "status": "",
            "bio": "", "meta": "", "photo_path": "", "thumb": ""}


db.get_person = _fake_get_person
try:
    class _FakeScr:
        def availableGeometry(self):
            return QRect(0, 0, 2560, 1392)

        def geometry(self):
            return QRect(0, 0, 2560, 1440)
    uis.SettingsDialog.screen = lambda self: _FakeScr()
    import main_window as mw
    mw.load_style(app)
    d = uis.SettingsDialog()
    d.show()
    for _ in range(10):
        app.processEvents()
    d.open_person_editor({"id": 5, "name": "张艺谋", "role_type": "Director"})
    for _ in range(6):
        app.processEvents()
    chk(d._current_key == "演员检测",
        "open_person_editor(导演) 后当前页 == 演员检测（实际 %s）" % d._current_key)
    chk(d._pg_actorcheck.kw.text() == "张艺谋",
        "open_person_editor 把姓名填入检索框（实际 %r）" % d._pg_actorcheck.kw.text())
    chk(d._pg_actorcheck._person is not None
        and d._pg_actorcheck._person.get("role_type") == "Director",
        "open_person_editor 按 id 直接载入导演编辑表单（绕开 Actor 列表限制）")
    del d
finally:
    db.get_person = _orig_gp

# ---------- ③ 汇总 ----------
print()
print("=" * 72)
print("汇总：%d 通过 / %d 失败" % (len(OK), len(BAD)))
print("=" * 72)
for b in BAD:
    print("  FAIL:", b)

sys.exit(1 if BAD else 0)
