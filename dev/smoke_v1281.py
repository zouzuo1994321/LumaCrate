# -*- coding: utf-8 -*-
"""v1.28.1 离屏冒烟回归 —— 两条反馈逐条自证 + 关键回归

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1281.py', run_name='__main__')"

**安全约定**：`db.db_path` 指向临时目录、`cfg.config_path` 指向临时 settings.json、
日志重定向到临时目录 —— 全程不碰真实索引 / 真实配置 / 真实媒体目录。

覆盖：
  A 版本号
  B 反馈 1：导演卡去掉「简介」+ 卡片高度压实（源码 + 真建卡 + 几何不裁）
  C 反馈 2：演员库 / 导演库每行 6 个（源码 + 真建网格逐行数卡 + 宽度校验）
  D 回归（演员卡不变 / 侧栏 / 外链 / 线程单例 / 品牌）
  E 文档
"""
import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1281")
INDEX = os.path.join(TMP, "index_data")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
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
os.environ.pop("LMC_NO_SYSMON", None)      # 回归段要**真跑**采集线程

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
import json

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
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QFont, QFontDatabase, QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QWidget

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw

mw.load_style(app)


def pump(n=4):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


def click(w):
    """向控件发一个左键按下（合成事件，会走它自己的 eventFilter）。"""
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(4.0, 4.0), QPointF(4.0, 4.0),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(w, ev)
    pump(2)


pump(3)

# ============================================================ A. 版本号
section("A. 版本号（v1.28.1 / Build 2609210040）")
check("A1 外部版本 v1.28.1", ver.VERSION == "v1.28.1", ver.VERSION)
check("A2 内部构建号 2609210040（顺延，不复用已擦除记录）",
      ver.BUILD == "2609210040", ver.BUILD)
check("A3 完整标识", ver.FULL_VERSION == "v1.28.1 (Build 2609210040)", ver.FULL_VERSION)
check("A4 品牌名 / Slogan / 外链未被这轮改坏",
      ver.APP_NAME == "流明盒" and ver.APP_NAME_EN == "LumaCrate"
      and ver.SLOGAN_CN == "所有流明 · 尽收盒中"
      and ver.REPO_URL == "https://github.com/zouzuo1994321/LumaCrate"
      and ver.AUTHOR_URL == "https://github.com/zouzuo1994321")
check("A5 开源声明与版权文案保持原样",
      ver.LICENSE_NOTE == "本软件为开源软件，没有授权禁止用于商业用途。"
      and ver.COPYRIGHT == "Copyright  2026 肆月Aperture")

mw_s = src("main_window.py")

# ============================================================ B. 反馈 1
section("B. 反馈 1：导演卡去掉「简介」+ 卡片高度压实")


def mk(cls, **kw):
    """造一张卡（回调全用空函数；ActorCard 的 _build 不读 self._main）。"""
    p = {"name": "肉尊", "thumb": None, "photo_path": None, "status": "现役",
         "works": 498, "alias": "", "favorite": 0, "pinned": 0,
         "meta": "", "birthday": "", "bio": ""}
    p.update(kw)
    return cls(p, on_open=lambda *_a: None, on_fav=lambda *_a: None,
               on_pin=lambda *_a: None, on_select=lambda *_a: None, main_win=None)


# —— 源码层 ——
_check_facts = mw._DIRECTOR_FACTS
check("B1 导演卡 FACTS 只剩「作品 / 别名」两项",
      len(_check_facts) == 2
      and [k for k, _r, _c, _s in _check_facts] == ["作品", "别名"],
      _check_facts)
check("B2 源码里导演信息区**不再有**「简介」这一项",
      "简介" not in mw_s.split("_DIRECTOR_FACTS =")[1].split("\n")[0],
      mw_s.split("_DIRECTOR_FACTS =")[1].split("\n")[0].strip())
check("B3 DirectorCard._fact_values 不再产出「简介」字段",
      '"简介": bio' not in mw_s and '"简介":' not in
      mw_s.split("class DirectorCard")[1].split("class AboutDialog")[0])
check("B4 压高常量按「少两行」推导（ACTOR_CARD_H - 2*(17+4)）",
      "DIRECTOR_CARD_H = ACTOR_CARD_H - 2 * (17 + 4)" in mw_s
      and "CARD_H = DIRECTOR_CARD_H" in mw_s)
check("B5 ActorCard 改用可覆盖的 self.CARD_H（子类才能改高）",
      "self.setFixedSize(ACTOR_CARD_W, self.CARD_H)" in mw_s
      and "CARD_H = ACTOR_CARD_H" in mw_s)

# —— 几何 ——
check("B6 常量值：演员 160 / 导演 118",
      (mw.ACTOR_CARD_H, mw.DIRECTOR_CARD_H) == (160, 118),
      "actor=%d director=%d" % (mw.ACTOR_CARD_H, mw.DIRECTOR_CARD_H))

d_card = mk(mw.DirectorCard)
d_card.show()
pump(4)
check("B7 真建导演卡：宽 236 / 高 118（比演员卡矮 42px）",
      (d_card.width(), d_card.height()) == (236, 118),
      "%dx%d" % (d_card.width(), d_card.height()))
check("B8 导演卡事实区只有「作品 / 别名」两个单元格",
      sorted(d_card._fact_cells.keys()) == ["作品", "别名"],
      sorted(d_card._fact_cells.keys()))
check("B9 导演卡 tooltip 里没有「简介」字样（含 作品/别名）",
      "简介" not in d_card.toolTip()
      and "作品" in d_card.toolTip() and "别名" in d_card.toolTip(),
      d_card.toolTip().replace("\n", " / "))
check("B10 导演卡里也**不再有任何** QLabel 残留「简介」文本",
      not any("简介" in (l.text() or "") for l in d_card.findChildren(QLabel)))

# —— 不裁：最下面一行事实必须在卡片内 ——
_last = d_card._fact_cells["别名"].geometry()
check("B11 末行事实（别名）底边在卡片内（没被压出边界）",
      0 <= _last.y() and _last.y() + _last.height() <= d_card.height(),
      "cell bottom=%d card h=%d" % (_last.y() + _last.height(), d_card.height()))
check("B12 姓名没被压到低于自身 sizeHint（没裁字）",
      d_card._name.height() >= d_card._name.sizeHint().height(),
      "h=%d hint=%d" % (d_card._name.height(), d_card._name.sizeHint().height()))
check("B13 姓名底边在事实行上方（两行姓名也不会压到事实区）",
      d_card._name.geometry().bottom() < d_card._fact_cells["作品"].geometry().top(),
      "name bottom=%d facts top=%d" % (d_card._name.geometry().bottom(),
                                       d_card._fact_cells["作品"].geometry().top()))

# —— 回归：演员卡不受影响 ——
a_card = mk(mw.ActorCard, birthday="1993-05-01", meta="出身地:东京|身高:160|尺寸:B92 W58 H89")
a_card.show()
pump(4)
check("B14 演员卡仍是 5 项信息（出生/出身地/身高/胸围/三围）",
      sorted(a_card._fact_cells.keys()) == ["三围", "出生", "出身地", "胸围", "身高"],
      sorted(a_card._fact_cells.keys()))
check("B15 演员卡高度仍是 160（没被导演卡的压高顺手改矮）",
      a_card.height() == 160, a_card.height())
_a_last = a_card._fact_cells["三围"].geometry()
check("B16 演员卡末行（三围）仍在卡内",
      _a_last.y() + _a_last.height() <= a_card.height(),
      "cell bottom=%d card h=%d" % (_a_last.y() + _a_last.height(), a_card.height()))

# —— 压力：超长姓名（会折成两行）也不裁 ——
d_long = mk(mw.DirectorCard, name="シネマジック東京特殊映像研究所",
            works=1234, alias="CinemaJikku Special")
d_long.show()
pump(4)
_l = d_long._fact_cells["别名"].geometry()
check("B17 超长两行姓名下，导演卡仍不裁（末行在卡内 / 名不矮于 sizeHint）",
      _l.y() + _l.height() <= d_long.height()
      and d_long._name.height() >= d_long._name.sizeHint().height(),
      "card=%d cell_bottom=%d name=%d/%d" % (d_long.height(), _l.y() + _l.height(),
                                             d_long._name.height(),
                                             d_long._name.sizeHint().height()))
d_card.close(); a_card.close(); d_long.close()

# ============================================================ C. 反馈 2
section("C. 反馈 2：演员库 / 导演库每行显示 6 个")

check("C1 COLS_BY_KIND 里 actor = 6", mw.LazyGrid.COLS_BY_KIND.get("actor") == 6,
      mw.LazyGrid.COLS_BY_KIND)
check("C2 其他网格列数没被顺手改（media=8 / folder=6）",
      mw.LazyGrid.COLS_BY_KIND.get("media") == 8
      and mw.LazyGrid.COLS_BY_KIND.get("folder") == 6,
      mw.LazyGrid.COLS_BY_KIND)
check("C3 两库确实共用 kind=\"actor\"（一处改动即覆盖两者）",
      mw_s.count('LazyGrid(fetch, make, total, kind="actor"') == 2
      or mw_s.count('kind="actor"') >= 2,
      mw_s.count('kind="actor"'))

# —— 宽度校验：默认 1920 窗下 6 列放得下 ——
_avail = 1920 - 186 - 40 - 14          # 窗 - 侧栏 - 页面左右边距 - 竖滚动条
_need = 6 * mw.ACTOR_CARD_W + 5 * 12
check("C4 6 列所需宽度 ≤ 默认窗可用宽度（不会挤出可视区）",
      _need <= _avail, "need=%d avail≈%d" % (_need, _avail))

# —— 造数据：让两库都真的有卡片 ——
for _i in range(14):
    db.upsert_person("导演%02d" % _i, role_type="Director")
for _i in range(14):
    db.upsert_person("演员%02d" % _i, role_type="Actor")

win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(10)


def row0_count(g):
    """第 0 行实际摆了几张卡。"""
    n = 0
    for i in range(g._grid.count()):
        r, _c, _rs, _cs = g._grid.getItemPosition(i)
        if r == 0:
            n += 1
    return n


for _tag, _builder, _card_cls in (("演员库", win._view_actors, mw.ActorCard),
                                  ("导演库", win._view_directors, mw.DirectorCard)):
    pg = _builder()
    pump(24)
    g = pg.findChild(mw.LazyGrid)
    ok = g is not None
    check("C5 %s：页面真的造出了 LazyGrid" % _tag, ok)
    if not ok:
        continue
    check("C6 %s：网格列数 = 6" % _tag, g._cols == 6, g._cols)
    check("C7 %s：已加载满 14 张卡" % _tag, g._loaded == 14, g._loaded)
    check("C8 %s：第 0 行确实摆了 6 张卡" % _tag, row0_count(g) == 6, row0_count(g))
    check("C9 %s：网格里用的是预期卡片类" % _tag,
          len(pg.findChildren(_card_cls)) == 14,
          len(pg.findChildren(_card_cls)))
    _cards = pg.findChildren(_card_cls)
    if _cards:
        _h = _cards[0].height()
        check("C10 %s：卡片实际高度 = %d" % (_tag, 118 if _card_cls is mw.DirectorCard else 160),
              _h == (118 if _card_cls is mw.DirectorCard else 160), _h)
    pg.deleteLater()
    pump(4)

# ============================================================ D. 回归
section("D. 回归（v1.27.0 / v1.28.0 的成果不能被这轮带回来）")

secs = [l.text() for l in win.sidebar.findChildren(QLabel) if l.objectName() == "Section"]
check("D1 侧栏「媒体库」分组还在", "媒体库" in secs, secs)
check("D2 侧栏两块面板默认都建",
      win.sysmon is not None and win.stat_label is not None)
check("D3 采集线程仍是进程级单例（只有 1 个且在跑）",
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)) == 1
      and QApplication.instance().findChildren(sysmon.SysMonWorker)[0].isRunning(),
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)))
check("D4 closeEvent 停的仍是共享线程", "sysmon.stop_shared_worker()" in mw_s
      and "sm.stop()" not in mw_s)

brand = win.sidebar.findChild(QWidget, "BrandBox")
check("D5 侧栏品牌区仍可点（挂了过滤器 + 主窗持有引用）",
      brand is not None and win._brand_link is not None
      and win._brand_link.url == ver.REPO_URL)
check("D6 底部状态栏仍可点（作者主页）",
      win._footer_link is not None and win._footer_link.url == ver.AUTHOR_URL)
check("D7 底部文案仍是 版本 | 版权 | 开源声明",
      win.statusBar().currentMessage()
      == f"{ver.FULL_VERSION}  |  {ver.COPYRIGHT}  |  {ver.LICENSE_NOTE}",
      win.statusBar().currentMessage())

# —— 运行时改设置重建侧栏：不得弄死线程（v1.27.0 血泪） ——
win._apply_settings()
pump(10)
check("D8 改设置重建侧栏后，采集线程仍活着且只有 1 个",
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)) == 1
      and QApplication.instance().findChildren(sysmon.SysMonWorker)[0].isRunning(),
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)))

_tsk = QApplication.instance().findChildren(sysmon.SysMonWorker)
_w = _tsk[0] if _tsk else None
check("D9 窗口标题带新版本号",
      f"{ver.APP_NAME}  {ver.FULL_VERSION}" in win.windowTitle(), win.windowTitle())
win.close()
pump(8)
check("D10 关窗后采集线程已停（不留后台线程）",
      _w is None or not _w.isRunning(),
      "None" if _w is None else _w.isRunning())

# ============================================================ E. 文档
section("E. 文档回归")
rd = doc("README.md")
check("E1 README 有 v1.28.1 迭代记录", "### v1.28.1" in rd)
check("E2 README 记录了这两条改动",
      "导演" in rd and "简介" in rd and "6 个" in rd)
check("E3 README 标题仍是流明盒", rd.startswith("# 流明盒 (LumaCrate)"))
try:
    rden = doc("README_EN.md")
    check("E4 英文 README 同步加了 v1.28.1",
          "v1.28.1" in rden and "bio" in rden.lower(), "")
except OSError:
    check("E4 英文 README 存在", False, "README_EN.md 缺失")

# ============================================================ 汇总
print("\n" + "=" * 74)
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for t in FAIL:
        print("  -", t)
print("=" * 74)
sys.exit(1 if FAIL else 0)
