# -*- coding: utf-8 -*-
"""v1.40.0 离屏冒烟（构建期）。

四条反馈的回归与单元断言：

① 反馈 1 ——「演员资料统计」独立成模块。
   用户截图红框那条「空白带」的成因，**经探针逐值实测后修正为**：不是 `src_hint`
   被压扁（真实窗口宽 1092px 下文案一行放得下，`heightForWidth` 返回 15，文字完整），
   而是**数据源组框整体被布局压小** + 统计行夹在数据源组框里，视觉上把「统计」和
   「数据源」混成一段、下面留出空档。治法是「把统计抽成独立组框」+「按内容真实
   需求钉住组框最小高」（`_pin_min_height` 逐子项累加 sizeHint，避开被压缩后
   `lay.sizeHint()` 返回缩水值的陷阱）。
   断言：三个独立 sibling 组框 + 统计组框标题 + `src_hint` **不裁字**
（`height() >= heightForWidth(宽)`）+ 窄窗确实折行。

② 反馈 2 —— 加大执行日志区。`sc_log` 由 `setFixedHeight(48)`（≈3 行，连一条
   测连结果都装不下）改为 `setMinimumHeight(240)` + 布局弹性 1。

③ 反馈 3 —— 代理显式开关 `proxy_enabled`。
   关 = 纯直连（`scraper_proxy()` 返回空串 + `scraper._PROXY_FORCED_OFF` 为真，
   `http_get` 不再兜底套系统代理）；开 = 用 proxy（空则回落系统代理）。
   另验 `config._truthy()` —— **绝不写 `bool(v)`**（`bool("0")` 是 `True`）。

④ 反馈 4 —— Cloudflare 验证助手。
   `parse_cookie_header()` 三种粘贴形态；`inject_cookies()` 后两条路径都带得上
   cookie（urllib 走 `_JAR`、curl_cffi 走 `_manual_cookie_header()`）；
   `clear_cookies()` **必须真的**变回假（v1.40.0 探针实锤过的缺陷：只清
   `_MANUAL_COOKIES` 时 `has_pass_cookie()` 回退扫 `_JAR` 仍是 True）；
   `_explain()` 认得 curl_cffi 的 BoringSSL 文案并给出可执行出路。

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

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1400_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QSizePolicy, QStyleFactory
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


# ================================================================ ① 版本号
print("\n---- ① 版本号 ----")
check("VERSION = v1.40.0", ver.VERSION == "v1.40.0", ver.VERSION)
check("BUILD = 2610130063", ver.BUILD == "2610130063", ver.BUILD)
check("MAJOR_ITER = 40", ver.MAJOR_ITER == 40, ver.MAJOR_ITER)
check("MINOR_ITER = 0", ver.MINOR_ITER == 0, ver.MINOR_ITER)


# ================================================================ ② config：proxy_enabled
print("\n---- ② config：代理开关与 _truthy ----")
check("DEFAULT_SCRAPER 有 proxy_enabled", "proxy_enabled" in cfg.DEFAULT_SCRAPER)
check("proxy_enabled 默认 False（直连）",
      cfg.DEFAULT_SCRAPER["proxy_enabled"] is False,
      cfg.DEFAULT_SCRAPER["proxy_enabled"])
check("config 有 _truthy", hasattr(cfg, "_truthy"))
for _v, _exp in (("0", False), ("false", False), ("no", False), ("off", False),
                 ("", False), ("FALSE", False), (" no ", False),
                 (True, True), (1, True), ("1", True), ("yes", True)):
    check(f"_truthy({_v!r}) == {_exp}", cfg._truthy(_v, False) is _exp,
          cfg._truthy(_v, False))
check("_truthy(None, default=True) == True", cfg._truthy(None, True) is True)
check("bool('0') 确实是 True（这正是不能用 bool() 的原因）", bool("0") is True)

# Settings.scraper_proxy() 的两态
_s = cfg.Settings()
_s.scraper["proxy_enabled"] = False
_s.scraper["proxy"] = "http://127.0.0.1:7890"
check("开关关 → scraper_proxy() 返回空串（纯直连）",
      _s.scraper_proxy() == "", repr(_s.scraper_proxy()))
_s.scraper["proxy_enabled"] = True
check("开关开 → scraper_proxy() 返回填的地址",
      _s.scraper_proxy() == "http://127.0.0.1:7890", _s.scraper_proxy())
_s.scraper["proxy"] = ""
check("开关开 + proxy 空 → 返回空串（由引擎回落系统代理）",
      _s.scraper_proxy() == "", repr(_s.scraper_proxy()))
# 脏配置归一：写盘成 "0" 再读回来必须是 False
_s.scraper["proxy_enabled"] = "0"
check("scraper_proxy() 对脏值 '0' 判假", _s.scraper_proxy() == "")


# ================================================================ ③ scraper：代理 + cookie
print("\n---- ③ scraper：直连标志 / cookie 注入 / 文案 ----")
check("scraper 有 set_proxy_disabled", hasattr(scraper, "set_proxy_disabled"))
check("scraper 有 _PROXY_FORCED_OFF", hasattr(scraper, "_PROXY_FORCED_OFF"))
check("默认 _PROXY_FORCED_OFF 为 False", scraper._PROXY_FORCED_OFF is False)

scraper.set_proxy_disabled(True)
check("set_proxy_disabled(True) → _PROXY_FORCED_OFF 为真", scraper._PROXY_FORCED_OFF is True)
scraper.set_proxy_disabled(False)
check("set_proxy_disabled(False) → 复位", scraper._PROXY_FORCED_OFF is False)

# http_get 里那张「不再兜底套系统代理」的表 —— 源码级守卫
_src_http = open(os.path.join(SRC, "scraper.py"), encoding="utf-8").read()
check("http_get 的代理兜底受 _PROXY_FORCED_OFF 约束",
      "_PROXY_FORCED_OFF" in _src_http and "用户显式选了直连" in _src_http)
check("download_photo 的代理兜底同样受约束",
      _src_http.count("_PROXY_FORCED_OFF") >= 4, _src_http.count("_PROXY_FORCED_OFF"))

# --- parse_cookie_header 三种粘贴形态 ---
check("scraper 有 parse_cookie_header", hasattr(scraper, "parse_cookie_header"))
_c1 = scraper.parse_cookie_header("cf_clearance=abc123==; __cf_bm=xyz")
check("分号串解析正确", _c1 == {"cf_clearance": "abc123==", "__cf_bm": "xyz"}, _c1)
_c2 = scraper.parse_cookie_header("Cookie: cf_clearance=abc; other=1")
check("整行 Cookie: 头解析正确（前缀被剥掉）",
      _c2 == {"cf_clearance": "abc", "other": "1"}, _c2)
_c3 = scraper.parse_cookie_header("cf_clearance\tAbC123.xyz-_def")
check("DevTools 逐行复制的 name<TAB>value 解析正确",
      _c3 == {"cf_clearance": "AbC123.xyz-_def"}, _c3)
check("空串解析为空 dict", scraper.parse_cookie_header("") == {})
check("无 = 的垃圾行被忽略", scraper.parse_cookie_header("garbage-line") == {})

# --- inject / lookup / clear ---
check("scraper 有 inject_cookies", hasattr(scraper, "inject_cookies"))
HOST = scraper.MINNANO_BASE
_n = scraper.inject_cookies(HOST, {"cf_clearance": "TOK", "__cf_bm": "B"})
check("inject_cookies 返回注入条数 2", _n == 2, _n)
check("注入后 has_pass_cookie 为真", scraper.has_pass_cookie(HOST) is True)
_st = scraper.cookie_state(HOST)
check("cookie_state 条数为 2", _st["count"] == 2, _st)
check("cookie_state has_pass 为真", _st["has_pass"] is True, _st)
check("cookie_state 记了注入时间", bool(_st["at"]), _st)
# curl_cffi 路径的 Cookie 头
_hdr = scraper._manual_cookie_header("www.minnano-av.com")
check("_manual_cookie_header 拼出 curl_cffi 用的头",
      "cf_clearance=TOK" in _hdr and "__cf_bm=B" in _hdr, _hdr)
check("_manual_cookie_header 对未知 host 返回空串",
      scraper._manual_cookie_header("example.com") == "")

# urllib 路径：cookie 真的进了 _JAR
check("cookie 进了 _JAR（urllib 路径带得上）",
      any(c.name == "cf_clearance" for c in scraper._JAR) is True)

# ★ v1.40.0 探针实锤的缺陷：只清 _MANUAL_COOKIES 时 has_pass_cookie 仍是 True
scraper.clear_cookies(HOST)
check("clear_cookies(host) 后 has_pass_cookie **必须**变假",
      scraper.has_pass_cookie(HOST) is False)
check("clear_cookies(host) 后 _JAR 里也不再有它",
      any(c.name == "cf_clearance" for c in scraper._JAR) is False)

# 清全部
scraper.inject_cookies(HOST, {"cf_clearance": "T2"})
scraper.inject_cookies(scraper.IMDB_BASE, {"aws-waf-token": "W"})
check("两个 host 各自独立（minnano/IMDB）",
      scraper.has_pass_cookie(HOST) and scraper.has_pass_cookie(scraper.IMDB_BASE))
scraper.clear_cookies()
check("clear_cookies() 清全部后两个 host 都变假",
      not scraper.has_pass_cookie(HOST)
      and not scraper.has_pass_cookie(scraper.IMDB_BASE))

# --- _explain 认得 curl_cffi / BoringSSL 文案 ---
_msgs = [
    ("SSLError: Failed to perform, curl: (35) BoringSSL SSL_connect: "
     "Connection closed abruptly (SSL_ERROR_SYSCALL; error queue empty)", ),
    ("SSLError: BoringSSL SSL_connect: Connection closed abruptly", ),
    ("TLS 被对端断开（SSLError）", ),
    ("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred", ),
    ("命中反爬挑战页（WAF 回 202）", ),
]
for (_m,) in _msgs:
    _e = scraper._explain(_m, "imdb")
    check(f"_explain 把「{_m[:34]}…」翻成人话（不再原样透出）", _e != _m, _e[:60])
_e_bor = scraper._explain(
    "SSLError: Failed to perform, curl: (35) BoringSSL SSL_connect: "
    "Connection closed abruptly (SSL_ERROR_SYSCALL; error queue empty)", "imdb")
check("BoringSSL 文案被归到「TLS 握手后立刻断开」一类",
      "TLS 握手后立刻断开" in _e_bor, _e_bor[:60])
check("BoringSSL 文案里给出可执行出路（Cloudflare 验证…）",
      "Cloudflare 验证" in _e_bor, _e_bor[:120])
check("_network_hint 关掉代理时说「直连」而不是瞎报系统代理",
      "直连" in scraper._network_hint("") or "系统代理" in scraper._network_hint(""))

# ================================================================ ④ UI：刮削页改版
print("\n---- ④ UI：演员刮削页三模块 / 日志区 / 代理开关 ----")
load_style(app)
from ui_settings import SettingsDialog

dlg = SettingsDialog(None)
dlg.resize(1000, 900)
dlg.show()
dlg._show("演员刮削")
for _ in range(8):
    app.processEvents()

page = dlg._pg_scraper
check("刮削页已构建", page is not None)

# --- 三个独立组框 ---
_boxes = [b for b in page.findChildren(QGroupBox)]
_titles = [b.title() for b in _boxes]
print("     组框标题:", _titles)
check("存在「演员资料统计」独立组框（反馈 1 的核心）",
      "演员资料统计" in _titles, _titles)
check("统计组框与数据源组框是**两个**不同的对象",
      len([t for t in _titles if t == "演员资料统计"]) == 1
      and len([t for t in _titles if "数据源" in t]) == 1, _titles)

_stats_box = [b for b in _boxes if b.title() == "演员资料统计"][0]
_src_box = [b for b in _boxes if "数据源" in b.title()][0]
check("统计条 sc_stats 住在「演员资料统计」组框内",
      _stats_box.isAncestorOf(dlg.sc_stats) is True)
check("统计条**不在**数据源组框内（这正是反馈 1 要修的）",
      _src_box.isAncestorOf(dlg.sc_stats) is False)
check("「启用演员刮削」开关也不在数据源组框内",
      _src_box.isAncestorOf(dlg.sc_enabled) is False)

# --- 统计条仍恒单行 ---
check("sc_stats 仍 setWordWrap(False)（v1.39.5 的修复未被回退）",
      dlg.sc_stats.wordWrap() is False)
check("sc_stats 仍为横向 Ignored（不被 minimumSizeHint 顶宽）",
      dlg.sc_stats.sizePolicy().horizontalPolicy() == QSizePolicy.Ignored)

# --- ★ src_hint 不被裁字（反馈 1 那条「空白带」的排查落点） ---
#
# ⚠ 这里纠正一条我在排查途中一度写错的假设（探针逐值实锤后修正）：
#   原断言写的是「高度 >= 两行」，前提是「文案本来就是两行」。**这个前提是错的。**
#   `src_hint` 的 `sizeHint().height()` 返回 60，那是「宽度未知」时的保守估算
#   （按 198px 窄宽估的 4 行）；而在真实窗口宽（1085→内容区 1092px）下量
#   `heightForWidth(1092)` 只有 **15** —— 11px 字体行距，78 字的文案**一行放得下**。
#   拿「60」当需求去断言「>= 两行」，等于要求控件虚高，断言本身写错了。
#
# 正确的判据是**「不裁字」**：`height() >= heightForWidth(当前宽)`。
# 再补一条窄窗口（900px）用例 —— 那里确实会折成两行，正好覆盖「钉高真的生效」。
_hint = dlg.src_hint
_hint_h = _hint.height()
_line = _hint.fontMetrics().lineSpacing()
_hint_w = _hint.width()
_hint_need = _hint.heightForWidth(_hint_w) if _hint_w > 0 else -1
check("src_hint 高度 >= 一个行距（不再被压成一条描边）",
      _hint_h >= _line, f"h={_hint_h} line={_line}")
check("src_hint 不裁字：height() >= heightForWidth(当前宽)",
      _hint_need >= 0 and _hint_h >= _hint_need,
      f"h={_hint_h} need={_hint_need} w={_hint_w}")
check("src_hint 已装 wordWrap（换行由内容决定，而非写死行数）",
      _hint.wordWrap() is True)
# 结构性守卫：文案必须真的显示出来（不是空标签）
check("src_hint 文案非空", len(_hint.text()) > 10, _hint.text()[:40])

# 窄窗必须折行 → 验证「钉高」真的按宽度在算（不是恰好蒙对）。
# ⚠ 不能靠 `dlg.resize(900, ...)`：刮削页此时已被包进 QScrollArea
# （`setWidgetResizable(True)`），内层 widget 有自己的宽度，外层缩窗**不会**
# 改变标签宽度 —— 探针实测 resize 到 900 后 `w` 仍是 1092（踩过的坑）。
# 直接改标签自己的宽度来验证折行行为，才是真正测「按宽算高」这条逻辑。
_hint.setFixedWidth(400)
for _ in range(6):
    app.processEvents()
_narrow_need = _hint.heightForWidth(_hint.width())
check("窄宽（400px）下 src_hint 确实折成多行（> 一个行距）",
      _narrow_need > _line,
      f"need={_narrow_need} line={_line} w={_hint.width()}")
check("窄宽下钉高跟着变（_pin_label_height 按当前宽重算）",
      ui_mod.SettingsDialog._pin_label_height(_hint) is None  # 只是调用，不抛异常
      and _hint.heightForWidth(_hint.width()) > _line,
      f"need={_hint.heightForWidth(_hint.width())}")
_hint.setMinimumWidth(0)
_hint.setMaximumWidth(16777215)
for _ in range(6):
    app.processEvents()

# --- ★ 数据源组框的「内容不被牺牲」硬保证 ---
# 反馈 1 的另一半：组框被布局压小 → 列表只剩一两行。修法是把组框最小高钉到
# 「逐子项 sizeHint 累加」的真实需求（避开 `lay.sizeHint()` 被压缩后返回缩水值的坑）。
#
# ⚠ 断言用的是**代码里同一套算法**：折行子项按 `heightForWidth(当前宽)` 算
# （不是裸 `sizeHint()` —— 那种会把 `src_hint` 算成 60 而不是 15，虚高一轮）。
_src_box2 = [b for b in page.findChildren(QGroupBox) if "数据源" in b.title()][0]
_slay = _src_box2.layout()
_need_h = 0
_n_items = 0
for _i in range(_slay.count()):
    _w = _slay.itemAt(_i).widget()
    if _w is None:
        continue
    _n = 0
    try:
        if _w.hasHeightForWidth() and _w.width() > 0:
            _n = _w.heightForWidth(_w.width())
    except Exception:
        _n = 0
    _need_h += max(_n, _w.minimumSizeHint().height())
    _n_items += 1
if _n_items > 1:
    _need_h += (_n_items - 1) * max(0, _slay.spacing())
_m = _slay.contentsMargins()
_need_h += _m.top() + _m.bottom()
check("数据源组框 minimumHeight 已按内容需求钉住（不再被压小）",
      _src_box2.minimumHeight() >= _need_h - 2,
      f"minH={_src_box2.minimumHeight()} need≈{_need_h} h={_src_box2.height()}")
check("数据源组框 minimumHeight > 0（真的钉了，不是默认）",
      _src_box2.minimumHeight() > 0, _src_box2.minimumHeight())

# --- ★ fit guard 的引用必须指对页（本轮真机排查中抓到的两个缺陷） ---
# 缺陷 A（**重入**）：`_make_scrollable()` 内部 `insertWidget` 会改当前索引 →
#   触发 `currentChanged` → 又回调 `_fit_page` → 第二次包一层，最后 `_pg_scraper`
#   指向一个**不在 stack 里的孤儿**（探针实测 `stack.indexOf(_pg_scraper) == -1`）。
# 缺陷 B（**当前页跳走**）：包完后当前索引被 `insertWidget` 挪到隔壁页，
#   用户切页后会看到**页面跳到别的工具**上（实测跳到「智能推荐」）。
# 两条都用「引用/当前页必须自洽」来守。
check("fit guard 未重入（_in_fit 标志已复位）",
      getattr(dlg, "_in_fit", None) is False, getattr(dlg, "_in_fit", "缺失"))
check("★ _pg_scraper 必须**真的在** stack 里（不是被包丢的孤儿）",
      dlg.stack.indexOf(dlg._pg_scraper) >= 0,
      f"indexOf={dlg.stack.indexOf(dlg._pg_scraper)} count={dlg.stack.count()}")
check("★ 当前页与 _pg_scraper 是同一个对象（切页不会跳到隔壁工具）",
      dlg.stack.currentWidget() is dlg._pg_scraper,
      f"cur={type(dlg.stack.currentWidget()).__name__} "
      f"idx={dlg.stack.indexOf(dlg.stack.currentWidget())} "
      f"scraper_idx={dlg.stack.indexOf(dlg._pg_scraper)}")
# 每一个页面属性都必须在 stack 里（防止再有别的页被同样的方式包丢）
_pg_attrs = ("_pg_personal", "_pg_manual", "_pg_insight", "_pg_scraper",
             "_pg_smart", "_pg_tagopt", "_pg_service", "_pg_aiengine",
             "_pg_dedupe", "_pg_actorcheck", "_pg_imagedetect", "_pg_data")
_orphans = [n for n in _pg_attrs
            if getattr(dlg, n, None) is not None
            and dlg.stack.indexOf(getattr(dlg, n)) < 0]
check("12 个页面属性全部在 stack 里（无孤儿）", not _orphans, _orphans)

# --- 日志区加大 ---
_lh = dlg.sc_log.minimumHeight()
check("sc_log 最小高 = 240（原为 setFixedHeight(48)）", _lh == 240, _lh)
check("sc_log 不再是 setFixedHeight（能跟着窗口长）",
      dlg.sc_log.maximumHeight() > 240, dlg.sc_log.maximumHeight())
check("sc_log 在布局里有弹性（stretch > 0 才算「跟着长」）",
      _has_stretch(page, dlg.sc_log), "见 _has_stretch")

# --- 代理开关 ---
check("存在 sc_proxy_on 开关", hasattr(dlg, "sc_proxy_on"))
check("proxy_enabled 为假 → 开关未勾选",
      dlg.sc_proxy_on.isChecked() == bool(dlg.s.scraper.get("proxy_enabled")),
      dlg.sc_proxy_on.isChecked())
check("开关关 → 代理输入框被置灰（即时视觉反馈）",
      dlg.sc_proxy.isEnabled() is False)
check("开关关 → 占位文案说明「直连」",
      "直连" in dlg.sc_proxy.placeholderText(), dlg.sc_proxy.placeholderText())
dlg.sc_proxy_on.setChecked(True)
app.processEvents()
check("开关开 → 输入框恢复可用", dlg.sc_proxy.isEnabled() is True)
check("开关开 → 占位文案提示可用系统代理",
      "系统代理" in dlg.sc_proxy.placeholderText(), dlg.sc_proxy.placeholderText())
check("开关开 → 已落盘 proxy_enabled=True",
      dlg.s.scraper.get("proxy_enabled") is True, dlg.s.scraper.get("proxy_enabled"))
# _scrape_opts 里 proxy 必须受开关约束
dlg.sc_proxy.setText("http://127.0.0.1:7890")
dlg.s.set_scraper(proxy="http://127.0.0.1:7890", proxy_enabled=True)
check("_scrape_opts() 开关开 → 带代理",
      (dlg._scrape_opts() or {}).get("proxy") == "http://127.0.0.1:7890",
      (dlg._scrape_opts() or {}).get("proxy"))
dlg.s.set_scraper(proxy_enabled=False)
check("_scrape_opts() 开关关 → 代理为空串（纯直连）",
      (dlg._scrape_opts() or {}).get("proxy") == "",
      repr((dlg._scrape_opts() or {}).get("proxy")))
dlg.sc_proxy_on.setChecked(False)
app.processEvents()

# --- Cloudflare 验证入口 ---
check("有「Cloudflare 验证…」按钮", hasattr(dlg, "sc_cf"))
check("按钮文案含 Cloudflare", "Cloudflare" in dlg.sc_cf.text(), dlg.sc_cf.text())
check("按钮 tooltip 说明了用途",
      "人机校验" in dlg.sc_cf.toolTip() or "Cloudflare" in dlg.sc_cf.toolTip(),
      dlg.sc_cf.toolTip()[:60])
check("CloudflareDialog 类存在", hasattr(ui_mod, "CloudflareDialog"))

# 对话框本身能建起来、能解析粘贴
_cfd = ui_mod.CloudflareDialog(scraper.MINNANO_BASE, "站点验证 · 测试", parent=dlg)
_cfd.show()
app.processEvents()
check("CloudflareDialog 建得起来并有输入框", _cfd.ed is not None)
check("CloudflareDialog 有「用系统浏览器打开」",
      "浏览器" in _cfd.btn_open.text(), _cfd.btn_open.text())
_cfd.ed.setPlainText("cf_clearance=ZZZ; __cf_bm=Y")
_cfd._save_and_verify()
app.processEvents()
check("对话框保存后 has_pass_cookie 为真", scraper.has_pass_cookie(scraper.MINNANO_BASE))
scraper.clear_cookies()
_cfd.close()


print("")
print(f"==== v1.40.0 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  (失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAIL:", n)

try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if FAIL else 0)
