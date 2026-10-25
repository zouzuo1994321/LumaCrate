# -*- coding: utf-8 -*-
"""v1.40.12 冒烟（离屏，不截图）：详情页演员/导演头像交互增强
============================================================================
本轮（v1.40.12，用户需求「左键单击和双击都进入演员/导演；右键可以搜索并编辑」）：
  · 详情页「演职人员信息」区的 CastAvatar：
      - 左键单击 → on_click（进入详情）；
      - 左键双击 → on_click（同样进入详情）；
      - 右键 → contextMenuEvent 弹「搜索并编辑信息」菜单 → on_context(person)。
  · 回调链打通：HeroView.on_open_context → main_window._open_person_tool →
    SettingsDialog.open_person_editor → 切「工具→演员检测」页并按 id 直接载入编辑表单。
  · 演员与导演都支持：db.get_person 按 id 取整行，不区分 role_type（绕开手动编辑列表只收 Actor）。

防回退（保留 v1.40.11 关键断言）：执行日志框样式 == 运行日志框样式（同 LOG_BOX_STYLE + NoWrap）。

本脚本以**数据断言**取代肉眼截图（用户要求：交付不再附截图）。
  ① 源码层：ui_hero.py / ui_settings.py / ui_home.py / main_window.py / version.py 关键改动到位；
  ② 真建控件（假屏幕复刻真机 2560×1392）：
       · CastAvatar 真构造 + 真派发鼠标事件：左键单击→on_click 触发、左键双击→on_click 触发、
         右键→contextMenuEvent→on_context 触发（menu.exec 打桩不阻塞）；
       · 真建 SettingsDialog，调用 open_person_editor(导演) 断言：current_key=="演员检测"、
         kw 文本==姓名、_person 被按 id 载入（db.get_person 打桩）；
  ③ 版本号 MINOR_ITER = 12 / BUILD_SEQ = "0075"。

跑法（务必用 E 盘绝对路径）：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/smoke_v1412.py"
"""
import os
import re
import sys

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import (QApplication, QScrollArea, QGroupBox, QLabel, QVBoxLayout,
                               QMenu)
from PySide6.QtCore import QRect, Qt, QEvent, QPoint, QTimer
from PySide6.QtGui import QFontDatabase, QMouseEvent, QContextMenuEvent

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
SSRC = open(os.path.join(ROOT, "src", "ui_settings.py"), encoding="utf-8").read()
HMSRC = open(os.path.join(ROOT, "src", "ui_home.py"), encoding="utf-8").read()
MWSRC = open(os.path.join(ROOT, "src", "main_window.py"), encoding="utf-8").read()
VSRC = open(os.path.join(ROOT, "src", "version.py"), encoding="utf-8").read()

# ---- CastAvatar：左键单击/双击进入 + 右键菜单 ----
chk('def __init__(self, person, on_click, on_context=None, size=96):' in HSRC,
    "CastAvatar.__init__ 新增 on_context 形参")
chk('def mouseDoubleClickEvent(self, e):' in HSRC,
    "CastAvatar 新增 mouseDoubleClickEvent（双击进入）")
chk('if e.button() == Qt.LeftButton and self.on_click:' in HSRC,
    "CastAvatar.mousePressEvent 仅左键触发 on_click（右键不再误进详情）")
chk('self.on_context(self.person)' in HSRC,
    "CastAvatar.contextMenuEvent 调 on_context(person)（右键搜索编辑）")
chk('QAction("搜索并编辑信息…", self)' in HSRC,
    "CastAvatar 右键菜单项文案 = 「搜索并编辑信息…」")
chk('for _c in self.findChildren(QWidget):' in HSRC
    and '_c.setContextMenuPolicy(Qt.NoContextMenu)' in HSRC,
    "CastAvatar 子控件设 NoContextMenu（右键归到本框，不放过 QLabel 头像/姓名）")

# ---- HeroView：透传 on_open_context ----
chk('def __init__(self, media, on_open_actor=None, on_back=None, on_changed=None, on_open_context=None):' in HSRC,
    "HeroView.__init__ 新增 on_open_context 形参")
chk('self.on_open_context = on_open_context' in HSRC,
    "HeroView 存下 on_open_context")
chk('CastAvatar(p, self.on_open_actor, on_context=self.on_open_context)' in HSRC,
    "HeroView._cast_section 把 on_open_context 透传给 CastAvatar")

# ---- HomeListView：透传 on_open_context ----
chk('def __init__(self, on_open_actor=None, on_open_media=None, on_hover_media=None,\n                 on_changed=None, on_open_context=None):' in HMSRC,
    "HomeListView.__init__ 新增 on_open_context 形参")
chk('self.on_open_context = on_open_context' in HMSRC,
    "HomeListView 存下 on_open_context")
chk('on_open_context=self.on_open_context' in HMSRC,
    "HomeListView 把 on_open_context 透传给 HeroView")

# ---- main_window：回调链 ----
chk('def _open_person_tool(self, person):' in MWSRC,
    "main_window 新增 _open_person_tool(person)")
chk('dlg.open_person_editor(person)' in MWSRC,
    "_open_person_tool 调 SettingsDialog.open_person_editor(person)")
chk('on_open_context=lambda p: self._open_person_tool(p)' in MWSRC,
    "HeroView/HomeListView 的 on_open_context 都接到 _open_person_tool")

# ---- ui_settings：直达「演员检测」按 id 载入 ----
chk('def open_person_editor(self, person):' in SSRC,
    "SettingsDialog 新增 open_person_editor(person)")
chk('self._show("演员检测")' in SSRC,
    "open_person_editor 切到「演员检测」页")
chk('pg._load_person(int(pid))' in SSRC,
    "open_person_editor 按 id 调 _load_person 载入（演员/导演通用）")

# ---- 版本号 ----
chk("MINOR_ITER = 12" in VSRC, "version.py MINOR_ITER = 12")
chk('BUILD_SEQ = "0075"' in VSRC, 'version.py BUILD_SEQ = "0075"')
chk('BUILD_DATE = "261015"' in VSRC, 'version.py BUILD_DATE = "261015"')

# ---- 防回退：v1.40.11 执行日志框样式 == 运行日志框 ----
chk("LOG_BOX_STYLE =" in SSRC,
    "[防回退] 模块级 LOG_BOX_STYLE 常量仍存在")
chk("self.sc_log.setStyleSheet(LOG_BOX_STYLE)" in SSRC
    and "self._log_view.setStyleSheet(LOG_BOX_STYLE)" in SSRC,
    "[防回退] 执行日志框与运行日志框仍复用同一 LOG_BOX_STYLE（未回退）")

# ---------- ② 真建控件 ----------
print()
print("=" * 72)
print("② 真建控件断言（假屏幕复刻真机 2560×1392）")
print("=" * 72)

app = QApplication([])
try:
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
except Exception:
    pass

import ui_hero as uh
import ui_settings as uis

print("ui_hero:", uh.__file__)
print("ui_settings:", uis.__file__)

# ---- CastAvatar 真派发鼠标事件（menu.exec 打桩：不弹真菜单、同步触发首条 action）----
_orig_qmenu = uh.QMenu


class _FakeMenu(_orig_qmenu):
    # 离屏下不弹真菜单（会阻塞），改为直接触发首条 action 的 triggered -> on_context
    def exec(self, *a):
        acts = self.actions()
        if acts:
            acts[0].triggered.emit()
        return None


uh.QMenu = _FakeMenu


class _Cap:
    def __init__(self):
        self.clicks = []
        self.ctxs = []


cap = _Cap()
fake_person = {"id": 7, "name": "演员X", "role_type": "Actor", "photo_path": ""}
av = uh.CastAvatar(fake_person, lambda p: cap.clicks.append(p),
                  on_context=lambda p: cap.ctxs.append(p))
av.show()

# 左键单击
press = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(5, 5), Qt.LeftButton,
                    Qt.MouseButtons(Qt.LeftButton), Qt.NoModifier)
av.mousePressEvent(press)
chk(len(cap.clicks) == 1 and cap.clicks[0]["id"] == 7,
    "CastAvatar 左键单击 → on_click 触发（进入详情）")

# 左键双击
dblk = QMouseEvent(QEvent.Type.MouseButtonDblClick, QPoint(5, 5), Qt.LeftButton,
                   Qt.MouseButtons(Qt.LeftButton), Qt.NoModifier)
av.mouseDoubleClickEvent(dblk)
chk(len(cap.clicks) == 2 and cap.clicks[1]["id"] == 7,
    "CastAvatar 左键双击 → on_click 触发（同样进入详情）")

# 右键 → contextMenuEvent（menu.exec 已被打桩，会同步触发 action -> on_context）
rctx = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5))
av.contextMenuEvent(rctx)
chk(len(cap.ctxs) == 1 and cap.ctxs[0]["id"] == 7,
    "CastAvatar 右键 → on_context 触发（搜索并编辑信息）")
uh.QMenu = _orig_qmenu

# ---- SettingsDialog 真建 + open_person_editor（db.get_person 打桩）----
import database as _db


def _fake_get_person(pid):
    return {"id": int(pid), "name": "测试导演Z", "role_type": "Director",
            "alias": "", "romaji": "", "birthday": "", "status": "",
            "bio": "", "meta": "", "photo_path": "", "thumb": ""}


_orig_gp = _db.get_person
_db.get_person = _fake_get_person
try:
    # v1.40.11 同款：借用 _FakeScr 让窗口尺寸量准
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

    # 右键一个「导演」头像 → 直达演员检测页并载入
    d.open_person_editor({"id": 5, "name": "测试导演Z", "role_type": "Director"})
    for _ in range(6):
        app.processEvents()

    chk(d._current_key == "演员检测",
        "open_person_editor(导演) 后当前页 == 演员检测（实际 %s）" % d._current_key)
    chk(d._pg_actorcheck.kw.text() == "测试导演Z",
        "open_person_editor 把姓名填入检索框（实际 %r）" % d._pg_actorcheck.kw.text())
    chk(d._pg_actorcheck._person is not None
        and d._pg_actorcheck._person.get("name") == "测试导演Z"
        and d._pg_actorcheck._person.get("role_type") == "Director",
        "open_person_editor 按 id 直接载入导演编辑表单（绕开 Actor 列表限制）")
    del d
finally:
    _db.get_person = _orig_gp

# ---------- ③ 汇总 ----------
print()
print("=" * 72)
print("汇总：%d 通过 / %d 失败" % (len(OK), len(BAD)))
print("=" * 72)
for b in BAD:
    print("  FAIL:", b)

sys.exit(1 if BAD else 0)
