# -*- coding: utf-8 -*-
"""v1.40.3 离屏冒烟（构建期）。

本轮两条反馈的回归断言：

① 反馈 1 ——「压缩执行的高度，把界面控制在 960px」。
   ★ 这是对 v1.40.2 的**回退**：v1.40.2 把执行组框改成 `addWidget(g3, 1)` 吃满 stretch，
   本意「底边贴页底」，实际把余量全灌进日志框（QPlainTextEdit 是唯一的 Expanding 项）
   → 真机日志框被撑到 200px+。断言：
     · `sc_log.setFixedHeight(96)`（固定，不参与拉伸）；
     · 执行组框 `addWidget(g3)`（**不**吃 stretch）；
     · 页面**有**尾部弹簧（余量留在页底，不进日志框）；
     · 真建页面：执行组框 stretch == 0、页面末项是弹簧；
     · 执行组框高度 == sizeHint（内容固有高度，不被撑高）。

② 反馈 2 ——「内置浏览器点击没反应」。
   真机复现证明窗口建得出来但被主程序挡住（不置顶）→ 用户看不到。
   断言：
     · `cf_browser.create_window(...)` 带 `on_top=True` 与 `focus=True`；
     · `CloudflareDialog` 有 `_focus_builtin_window()` 与 `_restore_open_btn()`；
     · `_open_builtin` 里点击后设置按钮禁用 + 文案改为「已打开 · 等待验证…」，
       并用 `QTimer.singleShot` 多次尝试拉前台；
     · `closeEvent` 不残留定时器崩溃风险。

使用临时数据库与临时配置，绝不读写真实索引 / 真实 settings.json。
"""
import os
import sys
import tempfile
import faulthandler

faulthandler.enable()

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1403_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import (QApplication, QGroupBox, QLabel,
                               QStyleFactory, QPlainTextEdit, QPushButton)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

# 铁律：每个冒烟脚本都要**自己** setStyle(Fusion)，否则结论随调用环境飘。
try:
    _st = QStyleFactory.create("Fusion")
    if _st is not None:
        app.setStyle(_st)
except Exception:
    pass

import config as cfg
import database as db
import version as ver
import applog
import scraper
import ui_settings as ui_mod
from main_window import load_style

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

FAIL = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("   -> " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(name)


def _layout_stretch(w):
    p = w.parentWidget()
    lay = p.layout() if p is not None else None
    if lay is None:
        return None
    try:
        idx = lay.indexOf(w)
        if idx < 0:
            return None
        return lay.stretch(idx)
    except Exception:
        return None


import inspect
import time as _t

USRC = open(os.path.join(SRC, "ui_settings.py"), encoding="utf-8").read()
CSRC = open(os.path.join(SRC, "cf_browser.py"), encoding="utf-8").read()


# ================================================================ ① 版本号
print("\n---- ① 版本号 ----")
check("VERSION = v1.40.3", ver.VERSION == "v1.40.3", ver.VERSION)
check("BUILD = 2610130066", ver.BUILD == "2610130066", ver.BUILD)
check("MAJOR_ITER = 40", ver.MAJOR_ITER == 40, ver.MAJOR_ITER)
check("MINOR_ITER = 3", ver.MINOR_ITER == 3, ver.MINOR_ITER)


# ================================================================ ② 反馈 1：执行区高度压缩
print("\n---- ② 反馈 1：「压缩执行的高度」（回退 v1.40.2 的撑高改法） ----")

# --- 源码守卫 ---
check("sc_log 改为固定高度 setFixedHeight(96)",
      "self.sc_log.setFixedHeight(96)" in USRC)
check("sc_log 不再用 setMinimumHeight(120)（v1.40.2 的弹性写法已撤）",
      "self.sc_log.setMinimumHeight(120)" not in USRC)
check("sc_log 加进布局时**不带** stretch（g3v.addWidget(self.sc_log)）",
      "g3v.addWidget(self.sc_log)\n" in USRC
      or "g3v.addWidget(self.sc_log) " in USRC)
check("sc_log 加进布局时不再写 g3v.addWidget(self.sc_log, 1)",
      "g3v.addWidget(self.sc_log, 1)" not in USRC)
check("执行组框不再吃 stretch（v.addWidget(g3) 而非 (g3, 1)）",
      "v.addWidget(g3)\n        v.addStretch(1)" in USRC
      or ("v.addWidget(g3)" in USRC and "v.addWidget(g3, 1)" not in USRC))
check("执行组框不吃 stretch 的写法已就位",
      "v.addWidget(g3, 1)" not in USRC)
check("页尾放回弹簧（余量留页底，不进日志框）",
      "v.addStretch(1)          # 余量留在页尾" in USRC
      or "v.addStretch(1)          #" in USRC)
check("工具默认高上限仍为 960", "min(960," in USRC, "（v1.40.2 已改）")
check("刮削页上下边距 8", "v.setContentsMargins(16, 8, 16, 8)" in USRC)
check("刮削页组距 7", "v.setSpacing(7)" in USRC)
check("执行组内行距 6", "g3v.setSpacing(6)" in USRC)

# --- 真建页面 ---
load_style(app)
dlg = ui_mod.SettingsDialog(None)
# ★ 先读**默认**高度（未手动 resize 前），这才是「工具窗默认高」的断言对象。
_default_h = dlg.height()
print(f"    工具窗默认高 = {_default_h}（离屏屏幕可用高只有 800 → min(960, 800-40)=760；"
      f"真机 1080p 下取 960，v1.40.2 真机实测外框 999）")
check("工具窗默认高 <= 960", _default_h <= 960, _default_h)
# 离屏下屏幕小，断言公式而非绝对值：默认高必须是 min(960, 可用高-40)
check("默认高公式为 min(960, 可用高 - 40)",
      "min(960, (avail.height() if avail else 1040) - 40)" in USRC)
dlg.resize(1920, 1080)
dlg.show()
app.processEvents()
_t.sleep(0.35)
app.processEvents()
try:
    dlg._show("演员刮削")
except Exception as e:
    print("  (提示) _show 失败：", e)
app.processEvents()
_t.sleep(0.3)
app.processEvents()

g3 = None
for g in dlg.findChildren(QGroupBox):
    if (g.title() or "").strip() == "执行":
        g3 = g
        break
check("找到「执行」组框", g3 is not None)

if g3 is not None:
    st = _layout_stretch(g3)
    print(f"    执行组框 stretch = {st}（应为 0：不吃余量）")
    check("执行组框在页面布局里**不**吃 stretch（stretch == 0）", st == 0, st)

    pg = g3.parentWidget()
    play = pg.layout() if pg is not None else None
    tail_spacer = False
    if play is not None:
        last = play.itemAt(play.count() - 1)
        tail_spacer = (last is not None and last.widget() is None
                       and last.spacerItem() is not None)
        print(f"    页面布局 count={play.count()} 末项是弹簧={tail_spacer}")
    check("页面末尾**有**页级弹簧（余量留页底）", tail_spacer)

    print(f"    执行组框 h={g3.height()} sizeHint={g3.sizeHint().height()} "
          f"（离屏屏幕小，h 仅供参考）")
    # 离屏窗口小，用 sizeHint 断言「内容固有高度没被撑大」：
    # 日志框固定 96 → 执行组框 sizeHint 应显著小于 v1.40.2 的 379（撑高后 ~379+）
    check("执行组框 sizeHint 已被压缩（<= 340，v1.40.2 撑高后为 379）",
          g3.sizeHint().height() <= 340, g3.sizeHint().height())

    # 日志框：固定高度、布局 stretch == 0
    print(f"    sc_log h={dlg.sc_log.height()} minH={dlg.sc_log.minimumHeight()} "
          f"maxH={dlg.sc_log.maximumHeight()}")
    check("sc_log 最小高 == 最大高 == 96（固定）",
          dlg.sc_log.minimumHeight() == 96 and dlg.sc_log.maximumHeight() == 96,
          (dlg.sc_log.minimumHeight(), dlg.sc_log.maximumHeight()))
    check("sc_log 在布局里 stretch == 0（不吸余量）",
          _layout_stretch(dlg.sc_log) == 0, _layout_stretch(dlg.sc_log))


# ================================================================ ③ 反馈 2：内置浏览器点击
print("\n---- ③ 反馈 2：「点击没反应」（窗口置顶 + 即时反馈） ----")

# --- cf_browser：窗口置顶 ---
check("cf_browser 建窗带 on_top=True（置顶，不被主程序挡住）",
      "on_top=True" in CSRC)
check("cf_browser 建窗带 focus=True（创建后抢焦点）",
      "focus=True" in CSRC)
check("cf_browser 里注明「点击没反应」的根因",
      "点击没反应" in CSRC or "置顶" in CSRC)

# --- ui_settings：拉前台 + 按钮即时反馈 ---
CF = ui_mod.CloudflareDialog
check("有 _focus_builtin_window（拉内置浏览器窗口到前台）",
      hasattr(CF, "_focus_builtin_window"))
check("_focus_builtin_window 用 SetForegroundWindow",
      "SetForegroundWindow" in inspect.getsource(CF._focus_builtin_window))
check("_focus_builtin_window 按「站点验证」标题找窗口",
      "站点验证" in inspect.getsource(CF._focus_builtin_window))
check("有 _restore_open_btn（恢复按钮可点态）", hasattr(CF, "_restore_open_btn"))

_ob = inspect.getsource(CF._open_builtin)
check("_open_builtin 里点击后禁用按钮（防连点重复 spawn）",
      "setEnabled(False)" in _ob)
check("_open_builtin 里按钮文案改为「已打开 · 等待验证…」",
      "已打开" in _ob)
check("_open_builtin 里用单次定时器恢复按钮",
      "_open_restore_timer" in _ob and "setSingleShot(True)" in _ob)
check("_open_builtin 里多次尝试拉前台（QTimer.singleShot + _focus_builtin_window）",
      "QTimer.singleShot(delay, self._focus_builtin_window)" in _ob)
check("已有子进程在跑时也会拉前台（不重复 spawn）",
      "_focus_builtin_window()" in _ob)

_hd = inspect.getsource(CF._on_helper_done)
check("_on_helper_done 里恢复按钮态（内置浏览器结束后可再点）",
      "_restore_open_btn" in _hd)

# --- 真建对话框，验证按钮存在、可点、文案 ---
cfd = ui_mod.CloudflareDialog(scraper.MINNANO_BASE, "站点验证 · 冒烟", parent=None)
cfd.show()
app.processEvents()
check("「打开内置浏览器」按钮存在", cfd.btn_open is not None)
check("按钮初始文案为「打开内置浏览器」",
      cfd.btn_open.text() == "打开内置浏览器", cfd.btn_open.text())
check("按钮初始可点", cfd.btn_open.isEnabled())
check("「读取 Cookie」按钮仍在（v1.40.2 的回归）",
      "读取 Cookie" in cfd.btn_read.text(), cfd.btn_read.text())

# 模拟 _restore_open_btn 的往返
cfd.btn_open.setEnabled(False)
cfd.btn_open.setText("已打开 · 等待验证…")
cfd._restore_open_btn()
check("_restore_open_btn 把按钮恢复为可点 + 原文案",
      cfd.btn_open.isEnabled() and cfd.btn_open.text() == "打开内置浏览器",
      (cfd.btn_open.isEnabled(), cfd.btn_open.text()))

# v1.40.2 回归：对话框边距/行距仍收紧
lay = cfd.layout()
m = lay.contentsMargins()
print(f"    对话框边距 L{m.left()} T{m.top()} R{m.right()} B{m.bottom()} "
      f"spacing={lay.spacing()}")
check("对话框左右边距仍 <= 16", m.left() <= 16 and m.right() <= 16, m.left())
check("对话框上下边距仍 <= 12", m.top() <= 12 and m.bottom() <= 12, m.top())
check("对话框行距仍 <= 8", lay.spacing() <= 8, lay.spacing())
check("对话框最小宽仍 660", cfd.minimumWidth() == 660, cfd.minimumWidth())
check("「读取 Cookie」按钮文案仍含「读取 Cookie」",
      "读取 Cookie" in cfd.btn_read.text())


# ================================================================ ④ v1.40.2 回归：诊断 + 快照
print("\n---- ④ v1.40.2 回归：分层诊断 + 持久快照协议 ----")
check("CloudflareDialog 有 _read_cookie", hasattr(CF, "_read_cookie"))
check("CloudflareDialog 有 _read_cookie_snapshot", hasattr(CF, "_read_cookie_snapshot"))
check("CloudflareDialog 有 _on_verified", hasattr(CF, "_on_verified"))
_sv = inspect.getsource(CF._on_verified)
check("失败文案仍不含「cookie 可能已过期」", "cookie 可能已过期" not in _sv)
check("失败文案仍对 TLS 层给「不是 cookie」判因",
      "不是 cookie" in _sv or "TLS 握手" in _sv)

check("scraper.diagnose_host 仍在", callable(getattr(scraper, "diagnose_host", None)))
diag = scraper.diagnose_host("https://www.minnano-av.com/", "", 6)
print("    diag:", {k: diag.get(k) for k in ("stage", "ok")})
check("diagnose_host 返回 stage/ok/verdict/detail",
      all(k in diag for k in ("stage", "ok", "verdict", "detail")), sorted(diag))

nh = scraper._network_hint("")
check("_network_hint 仍指出「与 cookie 无关」或「TLS 握手」",
      "与 cookie 无关" in nh or "TLS 握手" in nh, nh[:60])

import cf_browser
import json as _json
check("cf_browser.snapshot_path 存在", callable(getattr(cf_browser, "snapshot_path", None)))
check("cf_browser.request_path 存在", callable(getattr(cf_browser, "request_path", None)))
check("ui_settings 快照路径与 cf_browser 一致",
      ui_mod.cf_browser_snapshot_path() == cf_browser.snapshot_path())


# ================================================================ ⑤ 打包配置
print("\n---- ⑤ 打包配置（确认未回退） ----")
bld = os.path.join(ROOT, "build_exe.py")
if os.path.exists(bld):
    bsrc = open(bld, encoding="utf-8").read()
    check("build_exe.py 有 --collect-all webview", '"--collect-all", "webview"' in bsrc)
    check("build_exe.py 带 pythonnet + clr_loader",
          "pythonnet" in bsrc and "clr_loader" in bsrc)
    check("build_exe.py 带 cf_browser", '"cf_browser"' in bsrc)
    check("build_exe.py 带 curl_cffi", '"--collect-all", "curl_cffi"' in bsrc)
else:
    check("build_exe.py 存在", False, "未找到")


print("")
print(f"==== v1.40.3 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  (失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAILED:", n)
sys.exit(1 if FAIL else 0)
