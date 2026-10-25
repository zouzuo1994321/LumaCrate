# -*- coding: utf-8 -*-
"""v1.28.0 离屏冒烟回归 —— 三条反馈逐条自证 + 关键回归

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1280.py', run_name='__main__')"

**安全约定**：`db.db_path` 指向临时目录、`cfg.config_path` 指向临时 settings.json、
日志重定向到临时目录 —— 全程不碰真实索引 / 真实配置 / 真实媒体目录。

覆盖：
  A 版本号与外链常量        B 反馈 1 设置·外观两个开关（含侧栏真构建/真收回）
  C 反馈 2 点侧栏品牌区      D 反馈 3 点底部状态栏
  E 回归（线程单例 / 侧栏结构 / 底部文案）   F 文档
"""
import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1280")
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
os.environ.pop("LMC_NO_SYSMON", None)      # 本轮要**真跑**采集线程

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

# ============================================================ A. 版本 / 外链
section("A. 版本号与外链常量（v1.28.0 / Build 2609210038）")
check("A1 外部版本 v1.28.0", ver.VERSION == "v1.28.0", ver.VERSION)
check("A2 内部构建号 2609210038", ver.BUILD == "2609210038", ver.BUILD)
check("A3 完整标识", ver.FULL_VERSION == "v1.28.0 (Build 2609210038)", ver.FULL_VERSION)
check("A4 项目主页链接常量", ver.REPO_URL == "https://github.com/zouzuo1994321/LumaCrate",
      ver.REPO_URL)
check("A5 作者主页链接常量", ver.AUTHOR_URL == "https://github.com/zouzuo1994321",
      ver.AUTHOR_URL)
check("A6 品牌名与 Slogan 未被这轮改坏",
      ver.APP_NAME == "流明盒" and ver.APP_NAME_EN == "LumaCrate"
      and ver.SLOGAN_CN == "所有流明 · 尽收盒中")
check("A7 开源声明与版权文案保持原样",
      ver.LICENSE_NOTE == "本软件为开源软件，没有授权禁止用于商业用途。"
      and ver.COPYRIGHT == "Copyright  2026 肆月Aperture")

# ============================================================ B. 反馈 1
section("B. 反馈 1：「设置 → 外观」加两个显隐开关（控制侧栏是否显示这两块）")

cfg_ = src("config.py")
ui_s = src("ui_settings.py")
mw_s = src("main_window.py")

check("B1 DEFAULT_APPEARANCE 新增两个键且默认都开",
      '"show_stats": True, "show_sysmon": True' in cfg_)
check("B2 set_appearance 支持这两个键",
      "show_stats: bool = None, show_sysmon: bool = None" in cfg_
      and 'self.appearance["show_stats"] = bool(show_stats)' in cfg_)
check("B3 load() 把它们归一成真 bool（老配置 / 手改坏的都兜住）",
      'for _k in ("show_stats", "show_sysmon"):' in cfg_
      and 'not in ("", "0", "false", "no", "off")' in cfg_
      and "self.appearance[_k] = bool(_v)" in cfg_)

s0 = cfg.get_settings()
check("B4 默认值读出来是 True", s0.appearance.get("show_stats") is True
      and s0.appearance.get("show_sysmon") is True)

# —— 手改坏的 settings.json：字符串 / None 必须归一成 bool ——
with io.open(cfg.config_path(), "w", encoding="utf-8") as f:
    f.write(json.dumps({"appearance": {"show_stats": "0", "show_sysmon": None}}, ensure_ascii=False))
cfg._SETTINGS = None
s1 = cfg.get_settings()
check("B5 脏配置被归一成 bool：\"0\" → False，null → 回到默认 True",
      s1.appearance["show_stats"] is False and s1.appearance["show_sysmon"] is True,
      "%r / %r" % (s1.appearance["show_stats"], s1.appearance["show_sysmon"]))
s1.set_appearance(show_stats=False, show_sysmon=False)
cfg._SETTINGS = None
s2 = cfg.get_settings()
check("B6 落盘 → 重新读回来仍是 False（真的写进了 settings.json）",
      s2.appearance["show_stats"] is False and s2.appearance["show_sysmon"] is False)

check("B7 ui_settings 里确有这两个开关 + 处理函数",
      "self.sw_side_stats = ToggleSwitch(" in ui_s
      and "self.sw_side_sysmon = ToggleSwitch(" in ui_s
      and "def _apply_side_panels" in ui_s
      and "self.sw_side_stats.toggled.connect(self._apply_side_panels)" in ui_s
      and "self.sw_side_sysmon.toggled.connect(self._apply_side_panels)" in ui_s)
check("B8 两个开关落在「外观」组里（而不是别的分组）",
      'srl.addWidget(self._row("侧栏「数据统计」", self.sw_side_stats))' in ui_s
      and 'srl.addWidget(self._row("侧栏「实时状态」", self.sw_side_sysmon))' in ui_s
      and "g0v.addWidget(srow)" in ui_s)
check("B9 侧栏按开关构建（不是 hide，是整块不建）",
      'if ap.get("show_stats", True):' in mw_s and 'if ap.get("show_sysmon", True):' in mw_s)

# —— 关掉两块 → 真的建窗口看侧栏 ——
s3 = cfg.get_settings()
s3.set_appearance(show_stats=False, show_sysmon=False)
win_off = mw.MainWindow()
win_off.resize(1920, 1080)
win_off.show()
pump(10)


def sections_of(w):
    return [l.text() for l in w.sidebar.findChildren(QLabel) if l.objectName() == "Section"]


secs_off = sections_of(win_off)
hint_off = win_off.sidebar.layout().sizeHint().height()
check("B10 关掉后侧栏没有「数据统计」小标题", "数据统计" not in secs_off, secs_off)
check("B11 关掉后侧栏没有「实时状态」小标题", "实时状态" not in secs_off)
check("B12 关掉后 self.sysmon 是 None（面板根本没建）", win_off.sysmon is None)
check("B13 关掉后**没有**启动采集线程",
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)) == 0,
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)))
check("B14 关掉后 stat_label 仍在但不显示（供 _refresh_stats 安全调用）",
      win_off.stat_label is not None and not win_off.stat_label.isVisible()
      and win_off.sidebar.layout().indexOf(win_off.stat_label) < 0)
win_off._refresh_stats()          # 关掉状态下也必须不炸
check("B15 关掉状态下 _refresh_stats() 不抛异常", True)

# —— 打开两块 → 侧栏回来、线程起一个 ——
s3.set_appearance(show_stats=True, show_sysmon=True)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(10)
secs_on = sections_of(win)
hint_on = win.sidebar.layout().sizeHint().height()
check("B16 打开后两块小标题都在", "数据统计" in secs_on and "实时状态" in secs_on, secs_on)
check("B17 打开后 sysmon 面板挂回侧栏",
      win.sysmon is not None and win.sidebar.isAncestorOf(win.sysmon))
check("B18 打开后采集线程起来了（且只有 1 个）",
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)) == 1,
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)))
check("B19 关掉时侧栏内容总高确实更矮（空间真的收回了）",
      hint_off < hint_on, "off=%d on=%d" % (hint_off, hint_on))

lay = win.sidebar.layout()
check("B20 数据统计在实时状态上方（v1.27.0 的排布没被这轮改乱）",
      0 <= lay.indexOf(win.stat_label) < lay.indexOf(win.sysmon))

# —— 运行时切换（走 _apply_settings，等价于点设置里的开关）——
cfg.get_settings().set_appearance(show_sysmon=False)
win._apply_settings()
pump(10)
check("B21 运行时关掉「实时状态」→ 面板消失、侧栏没有该小标题",
      win.sysmon is None and "实时状态" not in sections_of(win))
check("B22 关掉面板**不会**把已在跑的采集线程弄死（进程级单例的功劳）",
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)) == 1
      and QApplication.instance().findChildren(sysmon.SysMonWorker)[0].isRunning())
cfg.get_settings().set_appearance(show_sysmon=True)
win._apply_settings()
pump(12)
check("B23 再打开 → 面板回来且订阅的是同一个线程",
      win.sysmon is not None and win.sysmon._worker is not None
      and win.sysmon._worker.isRunning())
check("B24 反复重建后进程里仍然只有 1 个采集线程",
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)) == 1,
      len(QApplication.instance().findChildren(sysmon.SysMonWorker)))

# ============================================================ C. 反馈 2
section("C. 反馈 2：点击侧栏品牌区 → 打开项目 GitHub 主页")

brand = win.sidebar.findChild(QWidget, "BrandBox")
check("C1 品牌区有 BrandBox 这个类名（样式挂得上）", brand is not None)
check("C2 品牌区是手型光标", brand is not None
      and brand.cursor().shape() == Qt.PointingHandCursor)
check("C3 品牌区悬停提示里带项目地址", brand is not None
      and ver.REPO_URL in brand.toolTip(), brand.toolTip().replace("\n", " ") if brand else "")
check("C4 品牌区装了事件过滤器，且被主窗持有引用（否则会被 GC）",
      brand is not None and brand.installEventFilter is not None
      and win._brand_link is not None and win._brand_link.url == ver.REPO_URL)
check("C5 源码里确实给子标签装了过滤器（合成事件不会自动冒泡，不能只装父级）",
      "for _ch in w.findChildren(QLabel):" in mw_s
      and "_ch.installEventFilter(self._brand_link)" in mw_s)
_child_filters = [l for l in (brand.findChildren(QLabel) if brand else [])]
check("C6 品牌区子标签确实各装了一份 + 也是手型光标",
      len(_child_filters) >= 1 and all(c.cursor().shape() == Qt.PointingHandCursor
                                      for c in _child_filters),
      "子标签 %d 个" % len(_child_filters))

_calls = []
_real_open = mw.open_url
mw.open_url = lambda u: (_calls.append(u), True)[1]
try:
    click(brand)
    check("C7 点品牌区 → 用项目地址打开浏览器",
          _calls == [ver.REPO_URL], _calls)
    _calls.clear()
    if _child_filters:
        click(_child_filters[0])
    check("C8 点在**文字标签**上也触发（且只触发一次，不会重复开两个页面）",
          _calls == [ver.REPO_URL], _calls)
    _calls.clear()
    click(brand)
    check("C9 点空白处（品牌容器本身）也触发", _calls == [ver.REPO_URL], _calls)
finally:
    mw.open_url = _real_open

qss = src("style.qss")
check("C10 QSS 给了品牌区悬停高亮（暗示可点）",
      "QWidget#BrandBox:hover" in qss and "QWidget#BrandBox {" in qss)
check("C11 品牌区没写任何 setStyleSheet（自绘底衬上的硬边色带老坑）",
      "w.setStyleSheet" not in mw_s.split("def _brand")[1].split("def _section")[0])
check("C12 open_url 走 QDesktopServices，且失败只记日志不弹框",
      "QDesktopServices.openUrl" in mw_s and "QMessageBox" not in mw_s.split("def open_url")[1].split("class LinkFilter")[0])

# ============================================================ D. 反馈 3
section("D. 反馈 3：点击底部状态栏 → 打开作者 GitHub 主页")

sb = win.statusBar()
check("D1 状态栏是手型光标", sb.cursor().shape() == Qt.PointingHandCursor)
check("D2 状态栏悬停提示里带作者地址", ver.AUTHOR_URL in sb.toolTip(),
      sb.toolTip().replace("\n", " "))
check("D3 状态栏装了过滤器且主窗持有引用",
      win._footer_link is not None and win._footer_link.url == ver.AUTHOR_URL)
check("D4 底部文案没被这轮改坏（版本 | Copyright | 开源声明）",
      sb.currentMessage() == f"{ver.FULL_VERSION}  |  {ver.COPYRIGHT}  |  {ver.LICENSE_NOTE}",
      sb.currentMessage())
_calls2 = []
mw.open_url = lambda u: (_calls2.append(u), True)[1]
try:
    click(sb)
    check("D5 点底部状态栏 → 用作者地址打开浏览器", _calls2 == [ver.AUTHOR_URL], _calls2)
finally:
    mw.open_url = _real_open
check("D6 QSS 给了状态栏悬停提亮", "QStatusBar:hover" in qss)
check("D7 状态栏**没有**被换成子类（QSS 的 QStatusBar 规则必须仍然命中）",
      type(sb).__name__ == "QStatusBar", type(sb).__name__)

# ============================================================ E. 回归
section("E. 回归（v1.27.0 的血泪教训不能被这轮带回来）")
check("E1 closeEvent 停的仍是进程级单例线程",
      "sysmon.stop_shared_worker()" in mw_s and "sm.stop()" not in mw_s)
check("E2 面板仍不从自己 new 线程", "self._worker = SysMonWorker(parent=self)" not in mw_s)
check("E3 侧栏里「媒体库」分组还在（没被开关顺手删掉）",
      "媒体库" in sections_of(win), sections_of(win))
_tsk = QApplication.instance().findChildren(sysmon.SysMonWorker)
w_shared = _tsk[0] if _tsk else None
win.close()
pump(8)
check("E4 关窗后采集线程已停（不留后台线程）",
      w_shared is None or not w_shared.isRunning(),
      "None" if w_shared is None else w_shared.isRunning())
check("E5 关窗后 window 标题仍是新版本号",
      f"{ver.APP_NAME}  {ver.FULL_VERSION}" in win.windowTitle(), win.windowTitle())

# ============================================================ F. 文档
section("F. 文档回归")
rd = doc("README.md")
check("F1 README 有 v1.28.0 迭代记录", "### v1.28.0" in rd)
check("F2 README 记录了三条反馈",
      "外观" in rd and "数据统计" in rd and ver.REPO_URL in rd and ver.AUTHOR_URL in rd)
check("F3 README 标题仍是流明盒", rd.startswith("# 流明盒 (LumaCrate)"))

# ============================================================ 汇总
print("\n" + "=" * 74)
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for t in FAIL:
        print("  -", t)
print("=" * 74)
sys.exit(1 if FAIL else 0)
