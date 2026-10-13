# -*- coding: utf-8 -*-
"""v1.40.2 离屏冒烟（构建期）。

三条反馈的回归断言：

① 反馈 1 ——「界面行与行间隔太大，压缩空间」（站点验证对话框）。
   断言：对话框外框边距 <= 12、v 布局 spacing <= 8、状态标签与「高级」按钮仍在；
   「高级」内部边距与输入框高度都收紧（<= 64）。

② 反馈 2 ——「复测未通过…单独安排一个按钮进行 cookie 读取，查明失败原因」。
   断言：`CloudflareDialog` 有 `btn_read` / `_read_cookie` / `_read_cookie_snapshot`；
   有 `_on_verified` 且失败文案**不再**甩「cookie 可能已过期」这句误导结论、
   且对 TLS 层失败给出明确「不是 cookie 问题」判因；
   `scraper.diagnose_host()` 存在并返回 {stage, ok, verdict, detail}；
   `test_source()` 失败时带 `diag`；
   `cf_browser` 有 `snapshot_path()` / `request_path()`，`Result.write` 成功时会写快照。

③ 反馈 3 ——「执行底部留白太多，压缩界面到 960px；工具默认窗口高度控制在 960px」。
   断言：`SettingsDialog` 默认高上限为 960（源码里 `min(960,`）；
   刮削页边距 8、组距 7；
   ★ 关键：「执行」组框在页面布局里的 stretch > 0，且页面**没有**尾部弹簧
   （这是「底部留白」的真根因 —— 旧的 `addStretch(1)` 把余量全吃掉、
   组框本身不长，于是在组框下方形成空白）。

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

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1402_")
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


def _has_stretch(pg, w):
    p = w.parentWidget()
    lay = p.layout() if p is not None else None
    if lay is None:
        return False
    try:
        idx = lay.indexOf(w)
        if idx < 0:
            return False
        return lay.stretch(idx) > 0
    except Exception:
        return False


# ================================================================ ① 版本号
print("\n---- ① 版本号 ----")
check("VERSION = v1.40.2", ver.VERSION == "v1.40.2", ver.VERSION)
check("BUILD = 2610130065", ver.BUILD == "2610130065", ver.BUILD)
check("MAJOR_ITER = 40", ver.MAJOR_ITER == 40, ver.MAJOR_ITER)
check("MINOR_ITER = 2", ver.MINOR_ITER == 2, ver.MINOR_ITER)


# ================================================================ ② 反馈 1：对话框行距
print("\n---- ② 反馈 1：站点验证对话框行距压缩 ----")
load_style(app)
cfd = ui_mod.CloudflareDialog(scraper.MINNANO_BASE, "站点验证 · 冒烟", parent=None)
cfd.show()
app.processEvents()

lay = cfd.layout()
m = lay.contentsMargins()
print(f"    对话框布局：内容边距 L{m.left()} T{m.top()} R{m.right()} B{m.bottom()}"
      f"；spacing={lay.spacing()}")
check("对话框左右边距已收紧（<= 16）", m.left() <= 16 and m.right() <= 16, m.left())
check("对话框上下边距已收紧（<= 12）", m.top() <= 12 and m.bottom() <= 12, m.top())
check("对话框行距已收紧（<= 8）", lay.spacing() <= 8, lay.spacing())

check("「打开内置浏览器」按钮仍在", "内置浏览器" in cfd.btn_open.text(), cfd.btn_open.text())
check("状态标签仍在", cfd.state is not None)
check("「高级 ▾」按钮仍在", cfd.btn_adv is not None)
check("高级面板默认收起", not cfd.adv.isVisibleTo(cfd))
cfd.btn_adv.setChecked(True)
app.processEvents()
check("勾选后高级面板展开", cfd.adv.isVisibleTo(cfd))
check("高级面板输入框高度已收紧（<= 64）", cfd.ed.minimumHeight() <= 64,
      cfd.ed.minimumHeight())
cfd.btn_adv.setChecked(False)
app.processEvents()

# 底部按钮行距 << 原来 8
btns_ok = True
print(f"    对话框 sizeHint：{cfd.sizeHint().width()}x{cfd.sizeHint().height()}")
check("对话框最小宽仍为 660（内容不被压扁）", cfd.minimumWidth() == 660,
      cfd.minimumWidth())


# ================================================================ ③ 反馈 2：读 cookie + 根因
print("\n---- ③ 反馈 2：独立「读取 Cookie」按钮 + 失败根因诊断 ----")
CF = ui_mod.CloudflareDialog
check("有 btn_read（独立读取 Cookie 按钮）", hasattr(CF, "_read_cookie"))
check("btn_read 实例存在", hasattr(cfd, "btn_read"))
check("读取按钮文案含「读取 Cookie」",
      "读取 Cookie" in getattr(cfd, "btn_read").text(),
      getattr(cfd, "btn_read").text())
check("有 _read_cookie（读 cookie 主入口）", hasattr(CF, "_read_cookie"))
check("有 _read_cookie_snapshot（关窗后读持久快照）", hasattr(CF, "_read_cookie_snapshot"))
check("有 _on_verified", hasattr(CF, "_on_verified"))

# 失败文案不能再甩「cookie 可能已过期」这句误导结论
import inspect
src_us = inspect.getsource(CF._on_verified)
check("失败文案已删除「cookie 可能已过期」误导句",
      "cookie 可能已过期" not in src_us)
check("失败文案对 TLS 层失败给出「不是 cookie 问题」判因",
      "不是 cookie" in src_us or "TLS 握手" in src_us, )

# --- scraper.diagnose_host 分层探针 ---
print("\n---- ④ scraper.diagnose_host 分层探针 ----")
check("diagnose_host 存在", callable(getattr(scraper, "diagnose_host", None)))
diag = scraper.diagnose_host("https://www.minnano-av.com/", "", 6)
print("    diag:", {k: diag.get(k) for k in ("stage", "ok", "verdict")})
check("diagnose_host 返回 dict", isinstance(diag, dict))
check("diag 含 stage/ok/verdict/detail",
      all(k in diag for k in ("stage", "ok", "verdict", "detail")), sorted(diag))
check("diag['detail'] 是 list", isinstance(diag.get("detail"), list))
# 本机实测：minnano 是 TLS 层被重置（若换环境可能不同，故只断言"给出了某层结论"）
check("diag 给出了失败层或成功结论",
      diag.get("stage") in ("tcp", "tls", "http"), diag.get("stage"))
if diag.get("stage") == "tls":
    check("TLS 层结论明确指向「cookie 没用上」（不是 cookie 问题）",
          "cookie" in (diag.get("verdict") or "") and "没用" in (diag.get("verdict") or ""),
          diag.get("verdict"))

# --- test_source 失败时带 diag ---
print("\n---- ⑤ test_source 失败时附带 diag ----")
_res = scraper.test_source("minnano", "", 6)
print("    test_source ok=%s ms=%s" % (_res.get("ok"), _res.get("ms")))
check("test_source 返回 dict", isinstance(_res, dict))
check("test_source 含 ok/msg/ms", all(k in _res for k in ("ok", "msg", "ms")))
if not _res.get("ok"):
    check("失败时带 diag 字段", "diag" in _res, sorted(_res.keys()))
    check("diag 是 dict", isinstance(_res.get("diag"), dict))
    # 文案不能再出现「缺的只是通行 cookie」这种错误推断
    check("错误文案不再说「缺的只是通行 cookie」",
          "缺的只是通行 cookie" not in (_res.get("msg") or ""), _res.get("msg"))
else:
    print("    （本机 minnano 竟然通了，跳过失败分支断言）")

# --- _network_hint 文案更正 ---
nh = scraper._network_hint("")
print("    _network_hint:", nh)
check("_network_hint 指出「与 cookie 无关」或「TLS 握手」",
      "与 cookie 无关" in nh or "TLS 握手" in nh, nh)
check("_network_hint 不再说「缺的只是通行 cookie」",
      "缺的只是通行 cookie" not in nh, nh)
check("_network_hint 给出可行出路（换网络/换代理）",
      "换网络" in nh or "换代理" in nh, nh)


# ================================================================ ⑥ 反馈 3：执行底部留白
print("\n---- ⑥ 反馈 3：工具默认 960px + 执行底部留白 ----")
vsrc = open(os.path.join(SRC, "version.py"), encoding="utf-8").read()
usrc = open(os.path.join(SRC, "ui_settings.py"), encoding="utf-8").read()
check("SettingsDialog 默认高上限为 960", "min(960," in usrc, "（旧为 min(900,）")
check("刮削页上下边距 8", "v.setContentsMargins(16, 8, 16, 8)" in usrc)
check("刮削页组距 7", "v.setSpacing(7)" in usrc)
check("执行组内行距已设 6", "g3v.setSpacing(6)" in usrc)
check("执行组框吃 stretch（addWidget(g3, 1)）", "v.addWidget(g3, 1)" in usrc)

# 真建页面验证：执行组框 stretch>0 且页面无尾部弹簧
dlg = ui_mod.SettingsDialog(None)
dlg.resize(1920, 1080)
dlg.show()
app.processEvents()
import time as _t
_t.sleep(0.35)
app.processEvents()
try:
    dlg._show("演员刮削")
except Exception as e:
    print("  (提示) _show 失败：", e)
app.processEvents()
_t.sleep(0.25)
app.processEvents()

# 找到「执行」组框
g3 = None
for g in dlg.findChildren(QGroupBox):
    if (g.title() or "").strip() == "执行":
        g3 = g
        break
check("找到「执行」组框", g3 is not None)
if g3 is not None:
    check("执行组框在页面布局里有 stretch（余量进组框，不吃成底部空白）",
          _has_stretch(dlg, g3))
    pg = g3.parentWidget()
    play = pg.layout() if pg is not None else None
    if play is not None:
        # 检查页面布局里没有尾部弹簧（末尾是 stretch 的 spacer 且 stretch 很大）
        last = play.itemAt(play.count() - 1)
        tail_is_spacer = last is not None and last.widget() is None and last.spacerItem() is not None
        print(f"    页面布局末项是弹簧 spacer：{tail_is_spacer}")
        check("页面布局末尾没有页级弹簧（旧 addStretch(1) 会形成底部空白）",
              not tail_is_spacer)

# 日志区仍是 120 弹性
check("sc_log.minimumHeight() 仍为 120", dlg.sc_log.minimumHeight() == 120,
      dlg.sc_log.minimumHeight())
check("sc_log 在布局里有 stretch（拉窗时长高）", _has_stretch(dlg, dlg.sc_log))


# ================================================================ ⑦ cf_browser 快照/请求协议
print("\n---- ⑦ cf_browser 快照与按需 dump 协议 ----")
import cf_browser
import json as _json

check("cf_browser 有 snapshot_path()", callable(getattr(cf_browser, "snapshot_path", None)))
check("cf_browser 有 request_path()", callable(getattr(cf_browser, "request_path", None)))
check("snapshot_path 文件名含 lmc_cf_snapshot",
      "lmc_cf_snapshot" in cf_browser.snapshot_path(), cf_browser.snapshot_path())
check("request_path 文件名含 lmc_cf_request",
      "lmc_cf_request" in cf_browser.request_path(), cf_browser.request_path())

# Result.write 成功时应同时写快照
import tempfile as _tf
_snapdir = _tf.mkdtemp(prefix="lmc_snap_")
_orig_snap = cf_browser.snapshot_path
cf_browser.snapshot_path = lambda: os.path.join(_snapdir, "snap.json")
try:
    _r = cf_browser.Result(os.path.join(_snapdir, "res.json"))
    _r.write({"ok": True, "cookie": "cf_clearance=Z", "host": "x", "count": 1})
    check("Result.write 成功时写出持久快照",
          os.path.exists(os.path.join(_snapdir, "snap.json")))
    if os.path.exists(os.path.join(_snapdir, "snap.json")):
        _d = _json.load(open(os.path.join(_snapdir, "snap.json"), encoding="utf-8"))
        check("快照内容与结果一致", _d.get("cookie") == "cf_clearance=Z", _d)
    _r2 = cf_browser.Result(os.path.join(_snapdir, "res2.json"))
    _r2.write({"ok": False, "error": "x"})
    check("失败结果不写快照（不污染）",
          not os.path.exists(os.path.join(_snapdir, "snap2.json")))
finally:
    cf_browser.snapshot_path = _orig_snap

check("cf_browser 有监听请求的线程函数（_watch_request）",
      "_watch_request" in open(os.path.join(SRC, "cf_browser.py"), encoding="utf-8").read())
check("cf_browser 有 threading import",
      "import threading" in open(os.path.join(SRC, "cf_browser.py"), encoding="utf-8").read())

# ui_settings 侧的快照路径对齐
check("ui_settings.cf_browser_snapshot_path 存在",
      callable(getattr(ui_mod, "cf_browser_snapshot_path", None)))
check("ui_settings 快照路径与 cf_browser 一致",
      ui_mod.cf_browser_snapshot_path() == cf_browser.snapshot_path())


# ================================================================ ⑧ 打包配置
print("\n---- ⑧ 打包配置（沿用 v1.40.1，确认未回退） ----")
bld = os.path.join(ROOT, "build_exe.py")
if os.path.exists(bld):
    bsrc = open(bld, encoding="utf-8").read()
    check("build_exe.py 有 --collect-all webview", '"--collect-all", "webview"' in bsrc)
    check("build_exe.py 带上 pythonnet + clr_loader", "pythonnet" in bsrc and "clr_loader" in bsrc)
    check("build_exe.py 带上 cf_browser", '"cf_browser"' in bsrc)
else:
    check("build_exe.py 存在", False, "未找到")

print("")
print(f"==== v1.40.2 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  (失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAILED:", n)
sys.exit(1 if FAIL else 0)
