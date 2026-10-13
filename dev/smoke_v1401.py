# -*- coding: utf-8 -*-
"""v1.40.1 离屏冒烟（构建期）。

三条反馈的回归断言（全部是对 v1.40.0 的回修）：

① 反馈 1 ——「数据源组框底部留空太多」。
   真根因是 v1.40.0 的 `_pin_min_height()` 对**固定高控件也用了 `sizeHint()`**：
   `src_list` 是 `setFixedHeight(120)`，但 QListWidget 的 `sizeHint()` 恒返回通用
   默认 **192**；`src_hint` 折行标签按当前宽只需 15~30，也被算成 60。逐子项累加
   = 280，而真实内容只需 ~208 → 72px 空白。
   断言：组框 `minimumHeight()` 必须贴近「逐子项真实需求」（含 maximumHeight 夹取），
   且**远小于**旧的虚高值 280；`src_list` 的贡献必须是它自己的 120 而非 192。

② 反馈 2 ——「执行日志缩小一半」。`sc_log` 由 `setMinimumHeight(240)` 改为 **120**，
   仍是弹性高度（不 `setFixedHeight`、布局 stretch=1）。

③ 反馈 3 —— 站点验证改用**内置浏览器**（pywebview + 系统 WebView2，子进程）。
   断言：`CloudflareDialog` 有 `_open_builtin` / `_check_webview` / `_poll_result` /
   `_toggle_adv`，「打开内置浏览器」入口在；「高级 ▾」手动兜底仍在且默认收起、
   勾选后展开；`_webview_ready()` 能探测 pywebview；helper 命令行指向 `cf_browser.py`
   （源码）或带 `--cf-browser`（打包）；`cf_browser._extract_pairs()` 对
   SimpleCookie（含**多条**）/ dict / 对象三种形态都能解析；`main.py` 有 `--cf-browser`
   分流且只定义一次 `main()`。

使用临时数据库与临时配置，绝不读写真实索引 / 真实 settings.json。
"""
import os
import sys
import shutil
import tempfile
import faulthandler

faulthandler.enable()

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1401_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import (QApplication, QGroupBox, QLabel, QSizePolicy,
                               QStyleFactory, QListWidget, QPlainTextEdit, QWidget)
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
    """该控件在父布局里的 stretch 是否 > 0（决定窗口拉高时它长不长）。"""
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


def _need_of(w):
    """复刻 `_pin_min_height()` 的单子项需求算法，用于独立核算。"""
    need = 0
    try:
        if w.hasHeightForWidth() and w.width() > 0:
            need = w.heightForWidth(w.width())
    except Exception:
        need = 0
    if need <= 0:
        need = w.sizeHint().height()
    need = max(need, w.minimumSizeHint().height())
    cap = w.maximumHeight()
    if 0 < cap < need:
        need = cap
    return need


# ================================================================ ① 版本号
print("\n---- ① 版本号 ----")
check("VERSION = v1.40.1", ver.VERSION == "v1.40.1", ver.VERSION)
check("BUILD = 2610130064", ver.BUILD == "2610130064", ver.BUILD)
check("MAJOR_ITER = 40", ver.MAJOR_ITER == 40, ver.MAJOR_ITER)
check("MINOR_ITER = 1", ver.MINOR_ITER == 1, ver.MINOR_ITER)


# ================================================================ ② 反馈 1：组框不虚高
print("\n---- ② 反馈 1：数据源组框不再虚高 ----")
load_style(app)
dlg = ui_mod.SettingsDialog(None)
dlg.resize(1920, 1080)
dlg.show()
app.processEvents()
import time as _t
_t.sleep(0.35)
app.processEvents()

# 切到「演员刮削」页
try:
    dlg._show("演员刮削")
except Exception as e:
    print("  (提示) _show 失败：", e)
app.processEvents()
_t.sleep(0.25)
app.processEvents()

grp = None
for g in dlg.findChildren(QGroupBox):
    if "数据源" in (g.title() or ""):
        grp = g
        break
check("找到「数据源」组框", grp is not None)

if grp is not None:
    lay = grp.layout()
    total = 0
    n = 0
    list_need = None
    label_need = None
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if w is None:
            continue
        need = _need_of(w)
        total += need
        n += 1
        if isinstance(w, QListWidget):
            list_need = need
        if isinstance(w, QLabel) and "minnano" in (w.text() or ""):
            label_need = need
    if n > 1:
        total += (n - 1) * max(0, lay.spacing())
    m = lay.contentsMargins()
    total += m.top() + m.bottom()
    print(f"    逐子项真实需求 = {total}；组框 minimumHeight={grp.minimumHeight()}"
          f"；sizeHint={grp.sizeHint().height()}")
    # QGroupBox 自己的标题 + 边框还会加一截「外框高」（≈ title 行 + 内边距），
    # 所以 minH 会比纯内容高略大 —— 容差取 30px 覆盖这层 chrome。
    check("组框 minimumHeight 贴近内容需求（容差 30px，覆盖组框标题/边框）",
          0 <= grp.minimumHeight() - total <= 30,
          f"minH={grp.minimumHeight()} vs need={total}")
    check("组框 minimumHeight 远小于旧虚高值 280（< 240）",
          grp.minimumHeight() < 240, grp.minimumHeight())
    check("数据源列表贡献 = 它的实际固定高 120（不是 sizeHint 192）",
          list_need is not None and list_need <= 130, list_need)
    check("折行提示标签贡献 = heightForWidth 值（不是 sizeHint 60）",
          label_need is not None and label_need < 60, label_need)

    # 钉高之后不能裁字：标签实际高必须 >= 它按当前宽所需
    for w in grp.findChildren(QLabel):
        if "minnano" in (w.text() or "") and w.wordWrap():
            hfw = w.heightForWidth(w.width())
            check("提示标签未被裁字（height >= heightForWidth）",
                  w.height() >= hfw, f"h={w.height()} hfw={hfw}")
            break


# ================================================================ ③ 反馈 2：日志区
print("\n---- ③ 反馈 2：执行日志区 120px 弹性 ----")
check("sc_log 存在", hasattr(dlg, "sc_log"))
if hasattr(dlg, "sc_log"):
    check("sc_log.minimumHeight() == 120", dlg.sc_log.minimumHeight() == 120,
          dlg.sc_log.minimumHeight())
    check("sc_log 不是固定高（maximumHeight 未锁）",
          dlg.sc_log.maximumHeight() > 100000, dlg.sc_log.maximumHeight())
    check("sc_log 在布局里有 stretch（拉窗时长高）", _has_stretch(dlg, dlg.sc_log))


# ================================================================ ④ 反馈 3：内置浏览器
print("\n---- ④ 反馈 3：站点验证改内置浏览器 ----")
CF = ui_mod.CloudflareDialog
check("有 _open_builtin", hasattr(CF, "_open_builtin"))
check("有 _check_webview", hasattr(CF, "_check_webview"))
check("有 _poll_result", hasattr(CF, "_poll_result"))
check("有 _on_helper_done", hasattr(CF, "_on_helper_done"))
check("有 _toggle_adv", hasattr(CF, "_toggle_adv"))
check("有 _helper_cmd", hasattr(CF, "_helper_cmd"))
check("旧「_open_browser」已移除", not hasattr(CF, "_open_browser"))

cfd = CF(scraper.MINNANO_BASE, "站点验证 · 冒烟", parent=dlg)
cfd.show()
app.processEvents()
check("「打开内置浏览器」入口在", "内置浏览器" in cfd.btn_open.text(), cfd.btn_open.text())
check("两步走文案写进正文", "读取 Cookie" in cfd.findChildren(QLabel)[1].text())
check("高级面板默认收起", not cfd.adv.isVisibleTo(cfd))
cfd.btn_adv.setChecked(True)
app.processEvents()
check("勾选后高级面板展开", cfd.adv.isVisibleTo(cfd))
check("高级面板里仍有手动粘贴框", cfd.ed is not None)
cfd.btn_adv.setChecked(False)
app.processEvents()

ok_wv, msg_wv = cfd._webview_ready()
print("    _webview_ready:", ok_wv, msg_wv)
check("_webview_ready() 返回 (bool, str)", isinstance(ok_wv, bool) and isinstance(msg_wv, str))
# 源码运行下本机应就绪（pywebview 已装 + WebView2 在）
if not getattr(sys, "frozen", False):
    check("源码运行：pywebview + WebView2 就绪", ok_wv, msg_wv)

cmd, resfile = cfd._helper_cmd()
print("    helper cmd:", cmd)
print("    result file:", resfile)
check("helper 命令行非空且是 list", isinstance(cmd, list) and len(cmd) >= 4)
check("helper 指向 cf_browser.py（源码）或带 --cf-browser（打包）",
      any("cf_browser.py" in str(c) for c in cmd) or "--cf-browser" in cmd)
check("结果文件名在命令行里", resfile in cmd or any(resfile in str(c) for c in cmd))

# 手动通路仍可用（复用 v1.40.0 断言）
cfd.ed.setPlainText("cf_clearance=ZZZ; __cf_bm=Y")
cfd._save_and_verify()
app.processEvents()
check("高级手动粘贴通路仍生效（has_pass_cookie 为真）",
      scraper.has_pass_cookie(scraper.MINNANO_BASE))
scraper.clear_cookies()
check("clear_cookies 后 has_pass_cookie 真的变回假",
      not scraper.has_pass_cookie(scraper.MINNANO_BASE))
cfd.close()

# --- cf_browser 模块 ---
print("\n---- ⑤ cf_browser 子进程模块 ----")
import cf_browser
from http.cookies import SimpleCookie

check("cf_browser 有 main()", callable(getattr(cf_browser, "main", None)))
check("cf_browser 有 _extract_pairs", callable(getattr(cf_browser, "_extract_pairs", None)))

sc1 = SimpleCookie(); sc1["cf_clearance"] = "AbC123.xyz-_def"
p1 = cf_browser._extract_pairs([sc1])
check("SimpleCookie 解析出 cf_clearance",
      p1.get("cf_clearance") == "AbC123.xyz-_def", p1)

# 一个 SimpleCookie 里装多条（漏第一条就丢 __cf_bm 的坑）
scn = SimpleCookie(); scn["cf_clearance"] = "V1"; scn["__cf_bm"] = "V2"
pn = cf_browser._extract_pairs([scn])
check("一个 SimpleCookie 内的多条全部取到",
      pn == {"cf_clearance": "V1", "__cf_bm": "V2"}, pn)

# 每条 cookie 一个 SimpleCookie（pywebview 真实形态）
a = SimpleCookie(); a["cf_clearance"] = "A"
b = SimpleCookie(); b["__cf_bm"] = "B"
pm = cf_browser._extract_pairs([a, b])
check("多个 SimpleCookie 全部取到",
      pm == {"cf_clearance": "A", "__cf_bm": "B"}, pm)

check("dict 形态兼容",
      cf_browser._extract_pairs([{"name": "cf_clearance", "value": "D"}]).get("cf_clearance") == "D")


class _Obj:
    name = "cf_clearance"
    value = "O"


check("对象形态兼容",
      cf_browser._extract_pairs([_Obj()]).get("cf_clearance") == "O")
check("空输入返回 {}", cf_browser._extract_pairs([]) == {} and cf_browser._extract_pairs(None) == {})
check("坏输入不抛异常", cf_browser._extract_pairs([None, 123, "x"]) == {})
check("_to_header 拼接正确",
      cf_browser._to_header({"a": "1", "b": "2"}) == "a=1; b=2")
check("cf_browser 设了 OPEN_EXTERNAL_LINKS_IN_BROWSER=False 的开关点",
      "OPEN_EXTERNAL_LINKS_IN_BROWSER" in open(
          os.path.join(SRC, "cf_browser.py"), encoding="utf-8").read())

# --- 结果文件协议（Result 原子写） ---
_r = cf_browser.Result(os.path.join(TMP, "res.json"))
_r.write({"ok": True, "cookie": "x=1"})
import json as _json
check("Result.write 落到盘且可解析",
      _json.load(open(_r.path, encoding="utf-8")).get("cookie") == "x=1")
_r.write({"ok": False})          # 只写一次，第二次应被忽略
check("Result 只写一次（父进程不会读到半截翻转值）",
      _json.load(open(_r.path, encoding="utf-8")).get("ok") is True)

# --- main.py 分流 ---
print("\n---- ⑥ main.py --cf-browser 分流 ----")
main_src = open(os.path.join(SRC, "main.py"), encoding="utf-8").read()
check("main.py 有 --cf-browser 分流", '"--cf-browser"' in main_src)
check("main.py 分流调 cf_browser.main()", "cf_browser.main()" in main_src)
check("main.py 只定义一次 main()", main_src.count("def main(") == 1,
      main_src.count("def main("))
check("main.py 顶层不 import PySide6（子进程不白加载 Qt）",
      "from PySide6.QtWidgets import QApplication" not in main_src.split("def main()")[0])

# --- 打包配置带上 pywebview ---
print("\n---- ⑦ 打包配置 ----")
bld = os.path.join(ROOT, "build_exe.py")
if os.path.exists(bld):
    bsrc = open(bld, encoding="utf-8").read()
    check("build_exe.py 提及 pywebview/webview", "webview" in bsrc)
    check("build_exe.py 有 --collect-all webview",
          '"--collect-all", "webview"' in bsrc, "（PyPI 包名 pywebview，导入名 webview）")
    check("build_exe.py 带上 pythonnet + clr_loader（Windows 后端依赖）",
          "pythonnet" in bsrc and "clr_loader" in bsrc)
    check("build_exe.py 带上 cf_browser 子进程模块",
          '"cf_browser"' in bsrc)
else:
    check("build_exe.py 存在", False, "未找到")

print("")
print(f"==== v1.40.1 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  (失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAIL:", n)

try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if FAIL else 0)
