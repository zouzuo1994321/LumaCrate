# -*- coding: utf-8 -*-
"""v1.40.15 冒烟（离屏）：右键搜索弹层「去系统标题栏 + 标题融入正文 + 放弃修改按钮」
============================================================================
本轮（v1.40.15，用户反馈「把顶部关闭栏融入下方，单独做一个放弃修改的按钮」）：
  · 详情页演员/导演头像右键弹出的 `PersonSearchDialog` 原本还带一条**系统标题栏**
    （「替换「XX」」+ 右侧 ×），与正文割裂；
  · 现改为**无边框统一面板**：显式 `Qt.Popup | Qt.FramelessWindowHint` 干掉标题栏，
    标题「替换「XX」」融入面板正文首行，右侧新增明确的 **「放弃修改」** 按钮
    （= 取消 / 不改动本片，等同 Esc / 点面板外）。
  · 点选结果替换本片该位（v1.40.14 语义）**保持不变**。

本脚本以**数据/几何断言**取代肉眼截图（交付不再附截图），另出一张预览图供肉眼核对。
  ① 源码层：ui_hero.py 的窗口旗标、正文标题行、「放弃修改」按钮接线到位，旧单旗标已移除；
  ② 真建控件（临时索引库）：
       · 窗口旗标含 Qt.Popup + Qt.FramelessWindowHint，windowType()==Qt.Popup（无系统标题栏）；
       · 正文首行 = 标题 QLabel（替换「XX」）+ 「放弃修改」QPushButton（#Ghost/compact，高 26）；
       · 布局顺序：标题行 → 输入框 → 提示 → 列表；
       · 点「放弃修改」→ dialog Rejected 且**不触发 on_pick**（本片不被改动）；
       · 点选列表项 / 回车 → Accept + on_pick(person)，替换语义照旧可用；按钮不裁字。
  ③ 版本号 MINOR_ITER = 15 / BUILD_SEQ = "0078"。

跑法（务必用 E 盘绝对路径）：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/smoke_v1415.py"
"""
import os
import sys
import tempfile

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

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
VSRC = open(os.path.join(ROOT, "src", "version.py"), encoding="utf-8").read()

chk("self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)" in HSRC,
    "ui_hero.py：PersonSearchDialog 用 Qt.Popup | Qt.FramelessWindowHint（无边框统一面板）")
chk("self.setWindowFlag(Qt.Popup)" not in HSRC,
    "旧的单旗标 setWindowFlag(Qt.Popup)（仍带系统标题栏）已移除")
chk('self._cancel_btn = QPushButton("放弃修改")' in HSRC,
    "新增正文内的「放弃修改」按钮")
chk("self._cancel_btn.clicked.connect(self.reject)" in HSRC,
    "「放弃修改」→ self.reject()（取消，不改动本片）")
chk('self._cancel_btn.setObjectName("Ghost")' in HSRC,
    "「放弃修改」复用全局次级按钮样式 #Ghost")
chk('self._cancel_btn.setProperty("compact", "1")' in HSRC,
    "「放弃修改」走 compact 窄按钮（避免全局 padding 把字裁掉）")
chk("head.addWidget(self._title)" in HSRC and "head.addWidget(self._cancel_btn)" in HSRC,
    "标题与「放弃修改」同处正文首行（顶部关闭栏融入下方）")
chk("lay.addLayout(head)" in HSRC,
    "标题行作为正文布局的一员（不是独立标题栏）")
chk("MINOR_ITER = 15" in VSRC, "version.py MINOR_ITER = 15")
chk('BUILD_SEQ = "0078"' in VSRC, 'version.py BUILD_SEQ = "0078"')
chk('BUILD_DATE = "261015"' in VSRC, 'version.py BUILD_DATE = "261015"')

# ---------- ② 真建控件 ----------
print()
print("=" * 72)
print("② 真建控件断言（临时索引库）")
print("=" * 72)

_tmp = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1415", "index_data")
os.makedirs(_tmp, exist_ok=True)
_db_path = os.path.join(_tmp, "media_center.db")

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QImage, QPainter, QColor, QPixmap

import database as db
import applog as applog_mod
db.db_path = lambda: _db_path
applog_mod.log_dir = lambda: _tmp
db.init_db()

_conn = db.get_conn()
_conn.execute("DELETE FROM media_people")
_conn.execute("DELETE FROM media")
_conn.execute("DELETE FROM people")
for nm, rt in [("未知演员", "Actor"), ("张伟", "Actor"), ("张艺谋", "Director")]:
    _conn.execute("INSERT INTO people (name, role_type) VALUES (?,?)", (nm, rt))
_conn.commit()
_pid = {r["name"]: r["id"] for r in _conn.execute("SELECT id, name FROM people").fetchall()}

app = QApplication([])
try:
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
except Exception:
    pass

# 离屏渲染必须显式加载全局 QSS，否则子控件走系统浅色默认样式、预览图会骗人。
# （传 DEFAULT_APPEARANCE，避免 render_style 去读真实 settings.json。）
try:
    import config as cfg
    import main_window as mw
    mw.load_style(app, cfg.DEFAULT_APPEARANCE)
    print("[ok ] 已加载全局 QSS（DEFAULT_APPEARANCE）")
except Exception as _e:
    print("[warn] 加载全局 QSS 失败（不影响断言）：", _e)

import ui_hero as uh

# ---- 窗口旗标：无系统标题栏 ----
picked = []
dlg = uh.PersonSearchDialog(initial="未知演员", old_name="未知演员",
                            on_pick=lambda p: picked.append(p))
fl = dlg.windowFlags()
chk(bool(fl & Qt.FramelessWindowHint), "窗口旗标含 Qt.FramelessWindowHint（无系统标题栏）")
chk(bool(fl & Qt.Popup), "窗口旗标含 Qt.Popup（点面板外自动关闭）")
chk(dlg.windowType() == Qt.Popup, "windowType() == Qt.Popup")
chk(dlg.minimumWidth() == 380, "最小宽度 380")

# ---- 正文首行 = 标题 + 放弃修改 ----
chk(dlg._title.text() == "替换「未知演员」", "正文标题 QLabel = 「替换「未知演员」」")
btns = [b for b in dlg.findChildren(QPushButton) if b.text() == "放弃修改"]
chk(len(btns) == 1, "正文内恰有一枚「放弃修改」按钮")
cb = dlg._cancel_btn
chk(cb.objectName() == "Ghost", "「放弃修改」objectName == Ghost")
chk(cb.property("compact") == "1", "「放弃修改」property compact == 1")
chk(cb.minimumHeight() == 26 and cb.maximumHeight() == 26,
    "「放弃修改」固定高度 26（min==max==26）")

# ---- 布局顺序：标题行 → 输入框 → 提示 → 列表 ----
lay = dlg.layout()
seq = []
for i in range(lay.count()):
    it = lay.itemAt(i)
    if it.layout() is not None:
        w = it.layout().itemAt(0).widget()
        seq.append(("headrow", w))
    elif it.widget() is not None:
        seq.append((type(it.widget()).__name__, it.widget()))
names = [n for n, _ in seq]
chk(names and names[0] == "headrow", "正文第 1 项是标题行（标题 + 放弃修改）")
i_head = names.index("headrow")
i_edit = next((i for i, w in enumerate(seq) if w[1] is dlg._edit), -1)
i_hint = next((i for i, w in enumerate(seq) if w[1] is dlg._hint), -1)
i_list = next((i for i, w in enumerate(seq) if w[1] is dlg._list), -1)
chk(0 <= i_head < i_edit < i_hint < i_list,
    "布局顺序：标题行 < 输入框 < 提示 < 列表（%d/%d/%d/%d）" % (i_head, i_edit, i_hint, i_list))
chk(dlg._title.parent() is dlg or dlg._title.parentWidget() is dlg,
    "标题控件归属本弹层（非独立窗口）")

# ---- 「放弃修改」= 取消，不触发 on_pick ----
cb.click()
app.processEvents()
chk(dlg.result() == QDialog.Rejected, "点「放弃修改」→ dialog Rejected")
chk(picked == [], "点「放弃修改」→ 未触发 on_pick（本片不被改动）")

# ---- 点选列表项 → Accept + on_pick（替换语义照旧）----
dlg2 = uh.PersonSearchDialog(initial="张", old_name="张伟", on_pick=lambda p: picked.append(p))
app.processEvents()
chk(dlg2._list.count() >= 1, "输入「张」→ 联想列表非空（%d 条）" % dlg2._list.count())
it0 = dlg2._list.item(0)
dlg2._on_item_clicked(it0)
app.processEvents()
chk(dlg2.result() == QDialog.Accepted, "点选列表项 → dialog Accepted")
chk(len(picked) == 1 and picked[0].get("id") == it0.data(Qt.UserRole).get("id"),
    "点选列表项 → on_pick 收到被点选的人（替换语义照旧可用）")

# ---- 回车确认路径 ----
picked.clear()
dlg3 = uh.PersonSearchDialog(initial="张", old_name="张伟", on_pick=lambda p: picked.append(p))
app.processEvents()
dlg3._edit.returnPressed.emit()
app.processEvents()
chk(len(picked) == 1, "输入框回车 → on_pick 收到当前顶部项")

# ---- 按钮不裁字 ----
dlg3.show()
app.processEvents()
cb3 = dlg3._cancel_btn
fm = cb3.fontMetrics()
chk(cb3.width() >= fm.horizontalAdvance("放弃修改") + 2,
    "「放弃修改」按钮宽度 %d ≥ 文本宽 %d（不裁字）"
    % (cb3.width(), fm.horizontalAdvance("放弃修改")))

# ---------- 预览出图（alpha 合成到底色，避免透明底显白） ----------
try:
    pv = uh.PersonSearchDialog(initial="未知演员", old_name="未知演员",
                               on_pick=lambda p: None)
    pv.resize(400, 380)
    pv.show()
    app.processEvents()
    for _ in range(3):
        app.processEvents()
    shot = pv.grab()
    canvas = QImage(shot.size(), QImage.Format_ARGB32)
    canvas.fill(QColor("#141210"))
    _p = QPainter(canvas)
    _p.drawPixmap(0, 0, shot)
    _p.end()
    out_png = os.path.join(ROOT, "dev", "preview_v1415_personsearch.png")
    canvas.save(out_png)
    chk(os.path.exists(out_png) and canvas.width() > 0, "预览图已生成：%s" % out_png)
except Exception as e:  # 预览失败不影响主断言
    print("[warn] 预览出图失败：", e)

# ---------- ③ 汇总 ----------
print()
print("=" * 72)
print("汇总：%d 通过 / %d 失败" % (len(OK), len(BAD)))
print("=" * 72)
for b in BAD:
    print("  FAIL:", b)

sys.exit(1 if BAD else 0)
