# -*- coding: utf-8 -*-
"""v1.39.2 离屏冒烟（构建期）。

① 继承 v1.39.0 全部断言（演员检测复选框列 / minnano Cloudflare 降级链 / 导航转圈）；
② 新增画像概览「高频榜 / 分布」排版回归（反馈 4：长 CJK 名把整行撑爆、计数与条形
   被折到下一行与相邻条目重叠）。

v1.39.0 三条反馈的回归与单元断言：
① bug 修复：演员检测「选择」列复选框看不见 + 不能 Shift/Ctrl 多选 ——
   根因是 QTreeView 布局不给 indicator 占位、复选框绝对定位超出 46px 列宽被裁；
   修法：列宽 62 + ExtendedSelection + 勾选∪选中并集驱动批量合并。
② bug 修复：minnano-av.com 的 Cloudflare 指纹墙（按 TLS 指纹拦 urllib，与代理无关）——
   cookie 罐 + opener 会话复用 + 首页预热（600s）+ 连续 403 达 3 次自动降级
   curl_cffi（chrome124 指纹，可选依赖）+ test_source 403 人话提示。
③ 功能新增：工具窗左侧导航「进行中」任务旁加转圈 —— ScanRing 抽到独立模块
   src/scan_ring.py；导航按钮包 row 容器（ring 隐藏不占布局空间）；400ms 轮询
   _running_tasks() 覆盖 11 类 worker + 两个检测页的 is_busy()。

使用临时数据库与临时配置，绝不读写真实索引 / 真实 settings.json。
"""
import os
import io
import sys
import time
import shutil
import inspect
import tempfile
import importlib
import urllib.error
import faulthandler

faulthandler.enable()

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1391_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import (QApplication, QAbstractItemView,
                               QSizePolicy)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

# v1.39.4：必须与 main.py 一样显式设 Fusion，否则本冒烟的「复选框可见面积」等
# 像素断言会随**外部有没有传** QT_QPA_PLATFORM 而飘。
# 背景（v1.39.3 实锤）：Qt 6 在 Windows 上默认 QStyle 是 `windows11`，
# 它是唯一画不出 `QTreeView::indicator` 的风格 —— 像素恒为 0；
# 而 `QT_QPA_PLATFORM=offscreen` 同样用 windows11，所以光换后端救不了，
# **必须换 QStyle**。这里固定下来 → 冒烟结论不再依赖调用环境。
try:
    from PySide6.QtWidgets import QStyleFactory
    _st = QStyleFactory.create("Fusion")
    if _st is not None:
        app.setStyle(_st)
except Exception:
    pass

import database as db
import config as cfg
import version as ver
import applog
import scraper
import scan_ring
import ui_actorcheck as ack_page
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


# ================================================================ ① 演员检测复选框列

# ============================================================ v1.39.4 追加段
# 反馈 1：minnano SSL 错误 + IMDB「可访问但检索无结果」的根因回归。
# 三个代码 bug（A 异常包装 / B WAF 挑战页 200·202 / C 降级太晚）+ 一个提示误导（D）。


def section_network():
    """v1.39.4：网络层根因回归。"""
    check("版本号 = v1.39.4", ver.VERSION == "v1.39.4", ver.VERSION)
    check("BUILD = 2610130061", ver.BUILD == "2610130061", ver.BUILD)

    # --- bug A：URLError 包装 SSL 错误 -------------------------------
    check("scraper 有 _unwrap_reason（剥 URLError.reason）",
          hasattr(scraper, "_unwrap_reason"))
    import ssl as _ssl
    import urllib.error as _ue

    class _Fake(_ue.URLError):
        pass

    inner = _ssl.SSLError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred")
    wrapped = _ue.URLError(inner)
    check("URLError 包装后 isinstance(ssl.SSLError) 为 False（这正是原 bug 的根因）",
          not isinstance(wrapped, _ssl.SSLError))
    check("_unwrap_reason 能剥到内层 SSLError",
          isinstance(scraper._unwrap_reason(wrapped), _ssl.SSLError))
    check("_unwrap_reason 对无 reason 的异常返回自身",
          scraper._unwrap_reason(ValueError("x")) is not None)
    # 多层包裹也能剥到底
    deep = _ue.URLError(_ue.URLError(inner))
    check("_unwrap_reason 支持多层 reason 嵌套",
          isinstance(scraper._unwrap_reason(deep), _ssl.SSLError))

    # --- bug B：WAF 挑战页识别 ---------------------------------------
    check("scraper 有 is_waf_challenge", hasattr(scraper, "is_waf_challenge"))
    waf_body = ('<html><head><script src="/cdn-cgi/challenge-platform/h/b/orchestrate">'
                '</script></script><body>awsWafCookieDomainList</body></html>')
    check("能识别 AWS WAF 挑战页（awsWafCookieDomainList）",
          scraper.is_waf_challenge(waf_body))
    check("能识别 Cloudflare 挑战页（Just a moment...）",
          scraper.is_waf_challenge("<title>Just a moment...</title>"))
    check("能识别 Checking your browser",
          scraper.is_waf_challenge("<h1>Checking your browser</h1>"))
    check("**正常内容页不被误判**",
          not scraper.is_waf_challenge(
              "<html><body><a href=\"/name/nm0000123/\">Emma Stone</a></body></html>"))
    check("空正文不被判为挑战页", not scraper.is_waf_challenge(""))
    check("None 不被判为挑战页（不抛异常）",
          scraper.is_waf_challenge(None) is False)

    # --- bug B：_curl_get 必须拦 202 ---------------------------------
    src_txt = io.open(os.path.join(SRC, "scraper.py"), encoding="utf-8").read()
    check("_curl_get 状态检查处拦 202（AWS WAF 专用码）",
          "r.status_code in (202, 403)" in src_txt,
          "202 拦截缺失")
    check("_curl_get 在状态检查**之前**识别 WAF 正文",
          src_txt.count("is_waf_challenge") >= 3,
          "is_waf_challenge 出现 %d 次" % src_txt.count("is_waf_challenge"))

    # --- bug A/C：http_get 的降级链 ----------------------------------
    check("http_get 签名带 _escalated 参数（首次拦截立即升级）",
          "_escalated" in src_txt)
    check("http_get 有 urllib.error.URLError 分支",
          "except urllib.error.URLError as e:" in src_txt)
    check("UNEXPECTED_EOF_WHILE_READING 被识别为 TLS 指纹拦截",
          "UNEXPECTED_EOF_WHILE_READING" in src_txt)
    check("有 _network_hint（拦截时提示系统代理与换网络）",
          hasattr(scraper, "_network_hint"))
    check("有 _explain（把拦截错误翻译成人话）", hasattr(scraper, "_explain"))

    # --- bug D：测连文案 ---------------------------------------------
    hint = scraper._network_hint("")
    check("_network_hint 会点出系统代理", "系统代理" in hint or "代理" in hint, hint[:60])
    check("_network_hint 给出「换网络/换代理」出路",
          "换网络" in hint or "换代理" in hint)
    e1 = scraper._explain("TLS 被对端断开（SSLEOFError）", "minnano")
    check("_explain 识别 TLS 断开", "TLS" in e1, e1[:50])
    e2 = scraper._explain("命中反爬挑战页（WAF 回 202）", "imdb")
    check("_explain 识别 WAF 挑战", "WAF" in e2 or "挑战页" in e2, e2[:50])
    e3 = scraper._explain("HTTP 403", "minnano")
    check("_explain 识别 minnano 403 指纹墙", "指纹" in e3, e3[:50])
    check("_explain 对未知消息原样返回",
          scraper._explain("随便什么错", "imdb") == "随便什么错")

    # 源码里不得再出现会误导用户的旧文案。
    # ⚠ 只扫**可执行代码**：注释与 docstring 里为了记录根因会引用这句原话
    #   （scraper.py:776 的 test_source docstring、version.py 的 # 355/# 359），
    #   那是刻意留的证伪记录，不该被当成残留文案。用 ast精确剥掉 docstring。
    import ast as _ast

    def _strip_doc_and_comments(fn):
        src_ = inspect.getsource(fn)
        tree = _ast.parse(_ast.unparse(_ast.parse(src_)))
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                 _ast.ClassDef, _ast.Module)):
                b = getattr(node, "body", None)
                if b and isinstance(b[0], _ast.Expr) and isinstance(
                        getattr(b[0], "value", None), _ast.Constant) and \
                        isinstance(b[0].value.value, str):
                    node.body = b[1:] or [_ast.Pass()]
        return _ast.unparse(tree)

    _code_only = _strip_doc_and_comments(scraper.test_source)
    check("test_source 的可执行代码已无「可访问，但检索无结果」（注释/docstring 保留引用）",
          "可访问，但检索无结果" not in _code_only,
          _code_only[:160])

    # --- 网络实测：两站大概率仍被拦，但**错误信息必须正确** --------
    r_min = scraper.test_source("minnano", timeout=8)
    r_imdb = scraper.test_source("imdb", timeout=8)
    print("    [实测] minnano ok=%s ms=%s msg=%s" % (r_min["ok"], r_min["ms"], r_min["msg"][:110]))
    print("    [实测] imdb    ok=%s ms=%s msg=%s" % (r_imdb["ok"], r_imdb["ms"], r_imdb["msg"][:110]))
    for nm, r in (("minnano", r_min), ("imdb", r_imdb)):
        check("%s 测连返回结构完整" % nm,
              set(("ok", "msg", "ms")).issubset(set(r.keys())))
        check("%s 测连 msg 非空" % nm, bool(r["msg"].strip()), r["msg"][:60])
        check("%s 测连 ms 为非负整数" % nm,
              isinstance(r["ms"], int) and r["ms"] >= 0, r["ms"])
        if not r["ok"]:
            check("%s 失败时给出可行动出路（换网络/代理/IP）" % nm,
                  ("换网络" in r["msg"] or "换代理" in r["msg"]
                   or "出口 IP" in r["msg"] or "未匹配" in r["msg"]),
                  r["msg"][:80])

    # 未知数据源仍要正常返回
    r_bad = scraper.test_source("不存在的源")
    check("未知数据源 ok=False", r_bad["ok"] is False)
    check("未知数据源给出明确提示", "未知数据源" in r_bad["msg"], r_bad["msg"])


section_network()


print("\n---- ① 演员检测：复选框列宽 62 + ExtendedSelection + 勾选∪选中 ----")
page = ack_page.ActorCheckPage()
check("演员检测页可离屏构建", page is not None)
mode = page.tree.selectionMode()
check("选择模式 = ExtendedSelection（Shift 区间 / Ctrl 逐点多选）",
      mode == QAbstractItemView.SelectionMode.ExtendedSelection, mode)
check("列 0 宽 = 62（容纳 17px 复选框：绝对定位 x=43..60 + 2px 余量）",
      page.tree.columnWidth(0) == 62, page.tree.columnWidth(0))
check("列 0 表头为「选择」", page.tree.headerItem().text(0) == "选择",
      page.tree.headerItem().text(0))

# 造两份假簇 → 填入树
page._res = {"merge_people": 2}
page._suspects = []
page._clusters = [
    {"ids": [10, 20], "keep_id": 10, "score": 90, "tier": "铁证",
     "reasons": ["罗马音一致"], "total_works": 6,
     "members": [{"id": 10, "name": "明里つくし", "works": 5, "photo": ""},
                 {"id": 20, "name": "つくし明里", "works": 1, "photo": ""}]},
    {"ids": [11, 21], "keep_id": 11, "score": 85, "tier": "很高",
     "reasons": ["别名互指"], "total_works": 3,
     "members": [{"id": 11, "name": "佐藤さん", "works": 2, "photo": ""},
                 {"id": 21, "name": "サトウ", "works": 1, "photo": ""}]},
]


def _cluster_items():
    out = []
    for i in range(page.tree.topLevelItemCount()):
        top = page.tree.topLevelItem(i)
        for j in range(top.childCount()):
            it = top.child(j)
            if it.data(0, page.ROLE_KIND) == "cluster":
                out.append(it)
    return out


page._fill_tree()
items = _cluster_items()
check("填入 2 个建议合并簇", len(items) == 2, len(items))
check("簇行带复选框(ItemIsUserCheckable)",
      bool(items[0].flags() & Qt.ItemIsUserCheckable))
check("批量按钮文案含「Shift / Ctrl 多选」提示",
      "Shift / Ctrl 多选" in page.batch_merge_btn.toolTip()
      or "Shift / Ctrl 多选" in page.batch_hint.text(),
      page.batch_hint.text())

# ---- 复选框真实可见面积（Checked 态差分法：与未勾选的 grab 图逐像素差分）----
from PySide6.QtWidgets import QDialog, QVBoxLayout

load_style(app)
dlg = QDialog()
lv = QVBoxLayout(dlg)
lv.setContentsMargins(0, 0, 0, 0)
lv.addWidget(page)
dlg.resize(1100, 860)
dlg.show()
app.processEvents()
app.processEvents()


def _grab():
    app.processEvents()
    app.processEvents()
    return page.tree.grab().toImage()


def _diff_n(img1, img2):
    n = 0
    for y in range(min(img1.height(), img2.height())):
        for x in range(min(img1.width(), img2.width())):
            p1, p2 = img1.pixel(x, y), img2.pixel(x, y)
            d = max(abs((p1 >> 16 & 0xFF) - (p2 >> 16 & 0xFF)),
                    abs((p1 >> 8 & 0xFF) - (p2 >> 8 & 0xFF)),
                    abs((p1 & 0xFF) - (p2 & 0xFF)))
            if d > 10:
                n += 1
    return n


imgA = _grab()
page.tree.blockSignals(True)
items[0].setCheckState(0, Qt.Checked)
imgB = _grab()
items[0].setCheckState(0, Qt.Unchecked)
page.tree.blockSignals(False)
vis = _diff_n(imgA, imgB)
check("Checked 态复选框可见面积 ≈ 279px（17×17 完整现形；修复前仅 46px）",
      vis > 200, vis)

# ---- 勾选 ∪ 选中 并集驱动批量按钮与 picked 集合 ----
page.tree.blockSignals(True)
items[0].setCheckState(0, Qt.Checked)
page.tree.blockSignals(False)
page._refresh_batch_btn()
check("勾选 1 簇 → 「合并 1 簇」且启用",
      page.batch_merge_btn.isEnabled()
      and "合并 1 簇" in page.batch_merge_btn.text(), page.batch_merge_btn.text())

page.tree.blockSignals(True)
items[1].setSelected(True)          # 不勾选，只选中（模拟 Ctrl 点选）
page.tree.blockSignals(False)
page._refresh_batch_btn()
check("再选中 1 簇（不勾选）→ 「合并 2 簇」（选中计入）",
      "合并 2 簇" in page.batch_merge_btn.text(), page.batch_merge_btn.text())

picked = []
for i in range(page.tree.topLevelItemCount()):
    top = page.tree.topLevelItem(i)
    for j in range(top.childCount()):
        it = top.child(j)
        if it.data(0, page.ROLE_KIND) == "cluster" \
                and (it.checkState(0) == Qt.Checked or it.isSelected()) \
                and it.text(3) not in ("已合并", "已忽略"):
            picked.append(int(it.data(0, page.ROLE_INDEX)))
check("picked 集合 = [0, 1]（勾选 ∪ 选中）", picked == [0, 1], picked)

page._uncheck_all()
check("全不选后计数 = 0（勾选与选中都清）",
      page._count_checked_clusters() == 0, page._count_checked_clusters())

check("is_busy() 存在且当前空闲（供工具窗导航转圈查询）",
      hasattr(page, "is_busy") and page.is_busy() is False)


# ================================================================ ② minnano Cloudflare 指纹墙
print("\n---- ② scraper：cookie 会话复用 + 首页预热 + 403 计数降级 ----")
check("_JAR 为全局 CookieJar", isinstance(scraper._JAR, __import__("http").cookiejar.CookieJar))
check("_CF_403_LIMIT = 3（连续 403 达阈值才降级）", scraper._CF_403_LIMIT == 3, scraper._CF_403_LIMIT)
check("_WARM_EVERY = 600（秒）", scraper._WARM_EVERY == 600, scraper._WARM_EVERY)
check("_OPENERS / _WARMED / _CF_403_COUNT 三个模块级状态就位",
      isinstance(scraper._OPENERS, dict) and isinstance(scraper._WARMED, dict)
      and isinstance(scraper._CF_403_COUNT, dict))
check("http_get 源码含 opener 复用（会话保持）",
      "opener = _opener(" in inspect.getsource(scraper.http_get))
check("http_get 源码含 403 计数", "_CF_403_COUNT[host] = _CF_403_COUNT.get(host, 0) + 1"
      in inspect.getsource(scraper.http_get))
check("http_get 源码含 curl_cffi 降级分支（连续 403 达阈值）",
      "_CF_403_COUNT.get(host, 0) >= _CF_403_LIMIT" in inspect.getsource(scraper.http_get))
check("_curl_get 用 chrome124 完整 Chrome 指纹",
      'impersonate="chrome124"' in inspect.getsource(scraper._curl_get))

# ---- opener 缓存：同 (proxy, verify_ssl) 复用同一对象（cookie 才带得上）----
scraper._OPENERS.clear()
op1 = scraper._opener("", True)
op2 = scraper._opener("", True)
op3 = scraper._opener("http://127.0.0.1:7890", True)
check("同 key 的 opener 复用同一实例", op1 is op2)
check("不同代理的 opener 分开缓存", op1 is not op3)

# ---- 首页预热：600s 内只预热一次 ----
scraper._WARMED.clear()
warm_calls = []
orig_http_get = scraper.http_get
scraper.http_get = lambda url, **kw: warm_calls.append(url) or ""
try:
    scraper._warmup("https://www.minnano-av.com/", 5, "")
    scraper._warmup("https://www.minnano-av.com/", 5, "")
    check("首页预热：600s 窗口内只发一次", len(warm_calls) == 1, warm_calls)
    host = "www.minnano-av.com"
    scraper._WARMED[host] = time.time() - scraper._WARM_EVERY - 1
    scraper._warmup("https://www.minnano-av.com/", 5, "")
    check("首页预热：窗口过期后重新预热", len(warm_calls) == 2, warm_calls)
finally:
    scraper.http_get = orig_http_get
scraper._WARMED.clear()

# ---- 403 计数：失败 +1、成功清零（mock opener，绝不发真实请求）----
class _FakeResp:
    def read(self):
        return b"<html>ok</html>"
    headers = {"Content-Encoding": "", "Content-Type": "text/html; charset=utf-8"}
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


class _FakeOpener:
    def __init__(self, code):
        self.code = code
        self.calls = 0
    def open(self, req, timeout=None):
        self.calls += 1
        if self.code == 403:
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
        return _FakeResp()


scraper._system_proxy = lambda: ""
scraper._CF_403_COUNT.clear()
scraper._OPENERS.clear()
fake403 = _FakeOpener(403)
scraper._OPENERS[("", True)] = fake403
host = "www.minnano-av.com"
for _ in range(2):
    try:
        scraper.http_get("https://www.minnano-av.com/search?x=1", timeout=3)
    except scraper.ScrapeError:
        pass
check("连续 2 次 403 → 计数 = 2（未达阈值仍走标准库）",
      scraper._CF_403_COUNT.get(host) == 2, scraper._CF_403_COUNT.get(host))
try:
    scraper.http_get("https://www.minnano-av.com/search?x=1", timeout=3)
except scraper.ScrapeError:
    pass
check("第 3 次 403 → 计数 = 3（达到降级阈值）",
      scraper._CF_403_COUNT.get(host) == 3, scraper._CF_403_COUNT.get(host))

# 达到阈值 + curl_cffi 可用 → 走 Chrome 指纹（mock _cffi_requests，验证真实 _curl_get）
class _FakeCffiResp:
    status_code = 200
    content = "<html>fingerprint-ok</html>".encode("utf-8")
    headers = {"Content-Type": "text/html; charset=utf-8"}


class _FakeCffiRequests:
    def __init__(self):
        self.kw = None
    def get(self, url, **kw):
        self.kw = kw
        return _FakeCffiResp()


fake_cffi = _FakeCffiRequests()
scraper._cffi_requests = fake_cffi
try:
    text = scraper.http_get("https://www.minnano-av.com/search?x=1", timeout=3)
    check("连续 403 达阈值后自动走 curl_cffi 且返回内容",
          text == "<html>fingerprint-ok</html>", text[:40])
    check("curl_cffi 带 chrome124 指纹 + verify=False",
          fake_cffi.kw.get("impersonate") == "chrome124" and fake_cffi.kw.get("verify") is False,
          {k: fake_cffi.kw.get(k) for k in ("impersonate", "verify")})
    check("curl 路径成功后 403 计数清零（恢复标准库优先）",
          scraper._CF_403_COUNT.get(host) == 0, scraper._CF_403_COUNT.get(host))
finally:
    scraper._cffi_requests = None

# curl 路径也失败 → 保持降级态、异常上抛
scraper._CF_403_COUNT[host] = scraper._CF_403_LIMIT
scraper._cffi_requests = _FakeCffiRequests()
try:
    scraper._curl_get = lambda *a, **kw: (_ for _ in ()).throw(scraper.ScrapeError("HTTP 403"))
    try:
        scraper.http_get("https://www.minnano-av.com/search?x=1", timeout=3)
        raised = False
    except scraper.ScrapeError:
        raised = True
    check("curl 路径失败 → ScrapeError 上抛且保持降级态",
          raised and scraper._CF_403_COUNT.get(host) == scraper._CF_403_LIMIT,
          scraper._CF_403_COUNT.get(host))
finally:
    scraper._cffi_requests = None
    scraper._CF_403_COUNT.clear()
    scraper._OPENERS.clear()

# 成功一次 → 计数清零（标准库路径恢复）
scraper._CF_403_COUNT[host] = 2
scraper._OPENERS[("", True)] = _FakeOpener(200)
try:
    scraper.http_get("https://www.minnano-av.com/search?x=1", timeout=3)
except scraper.ScrapeError as e:
    check("标准库成功路径取回页面", False, e)
check("成功后 403 计数清零", scraper._CF_403_COUNT.get(host) == 0, scraper._CF_403_COUNT.get(host))

# curl_cffi 不可用（未安装/打包未含）→ 纯标准库模式不受影响
scraper._CF_403_COUNT[host] = 99
scraper._OPENERS.clear()
scraper._OPENERS[("", True)] = _FakeOpener(200)
try:
    text = scraper.http_get("https://www.minnano-av.com/search?x=1", timeout=3)
    check("curl_cffi 不可用时仍走标准库（可选依赖，import 失败自动退回）",
          text == "<html>ok</html>", text[:40])
except scraper.ScrapeError as e:
    check("curl_cffi 不可用时仍走标准库（可选依赖，import 失败自动退回）", False, e)

# test_source 的 403 人话提示
scraper.minnano_search = lambda *a, **kw: (_ for _ in ()).throw(scraper.ScrapeError("HTTP 403"))
try:
    r = scraper.test_source("minnano")
    check("test_source 403 → 提示含「Cloudflare 指纹校验」",
          (not r["ok"]) and "Cloudflare 指纹校验" in r["msg"], r["msg"])
    check("test_source 403 → 提示含「安装 curl_cffi 可启用浏览器指纹模式」（未装时）",
          "安装 curl_cffi 可启用浏览器指纹模式" in r["msg"], r["msg"])
finally:
    pass

# build_exe.py 收集 curl_cffi 二进制（单文件 exe 需要）
build_src = open(os.path.join(ROOT, "build_exe.py"), encoding="utf-8").read()
check("build_exe.py 含 --collect-all curl_cffi（原生二进制进 exe）",
      '"--collect-all", "curl_cffi"' in build_src or "'--collect-all', 'curl_cffi'" in build_src)


# ================================================================ ③ 工具窗导航转圈
print("\n---- ③ 工具窗导航「进行中」转圈 ----")
check("scan_ring 为独立模块（main_window / ui_settings 共用）",
      hasattr(scan_ring, "ScanRing"))
ring = scan_ring.ScanRing(size=14)
check("ScanRing(size=14) 尺寸生效", ring.width() == 14 and ring.height() == 14,
      (ring.width(), ring.height()))
check("ScanRing 初始隐藏（空闲不占布局空间）", not ring.isVisible())
ring.set_state(True, 0, "测试")
check("set_state(True) → 忙碌可见", ring.is_busy() and ring.isVisible())
ring.set_state(False)
check("set_state(False) → 隐藏", (not ring.is_busy()) and (not ring.isVisible()))

mw_src = open(os.path.join(SRC, "main_window.py"), encoding="utf-8").read()
check("main_window 不再本地定义 ScanRing（已抽到 scan_ring.py）",
      "class ScanRing" not in mw_src)
check("main_window import scan_ring.ScanRing", "from scan_ring import ScanRing" in mw_src)
us_src = open(os.path.join(SRC, "ui_settings.py"), encoding="utf-8").read()
check("ui_settings import scan_ring.ScanRing", "from scan_ring import ScanRing" in us_src)
check("ui_settings 有 _running_tasks()（集中轮询，不去各 worker 启动点插桩）",
      "def _running_tasks" in us_src)
check("ui_settings 有 _refresh_nav_rings()", "def _refresh_nav_rings" in us_src)

import ui_settings

dlg2 = ui_settings.SettingsDialog()
check("工具窗可离屏构建", dlg2 is not None)
check("导航按钮与转圈一一对应", len(dlg2.nav_rings) == len(dlg2.sub_btns) > 0,
      (len(dlg2.sub_btns), len(dlg2.nav_rings)))
check("_busy_timer 轮询间隔 = 400ms",
      getattr(dlg2, "_busy_timer", None) is not None and dlg2._busy_timer.interval() == 400,
      getattr(getattr(dlg2, "_busy_timer", None), "interval", lambda: None)())


class _FakeWorker:
    def __init__(self, running):
        self._running = running
    def isRunning(self):
        return self._running


check("空闲时 _running_tasks() 为空且所有 ring 隐藏",
      dlg2._running_tasks() == set()
      and all(not r.is_busy() for r in dlg2.nav_rings.values()),
      dlg2._running_tasks())

# 11 类 worker 属性各试一次（服务管理 / 演员刮削 / 标签优化×3 / 重复检测 / 画像概览 / AI引擎×4 / 数据源测试）
_attr_key = [("_worker", "服务管理"), ("_scrape_worker", "演员刮削"),
             ("_to_scan_worker", "标签优化"), ("_to_run_worker", "标签优化"),
             ("_to_ai_worker", "标签优化"), ("_dd_worker", "重复检测"),
             ("_insight_worker", "画像概览"), ("_ai_worker", "AI引擎设置"),
             ("_ae_probe_worker", "AI引擎设置"), ("_ae_models_worker", "AI引擎设置"),
             ("_ae_launch_worker", "AI引擎设置")]
for attr, key in _attr_key:
    old = getattr(dlg2, attr, None)
    setattr(dlg2, attr, _FakeWorker(True))
    try:
        dlg2._refresh_nav_rings()
        ok = (key in dlg2._running_tasks()) and dlg2.nav_rings[key].is_busy()
        others_ok = all((not r.is_busy()) for k, r in dlg2.nav_rings.items() if k != key)
        check("worker %s 运行中 → 导航「%s」转圈且仅它转" % (attr, key), ok and others_ok)
    finally:
        setattr(dlg2, attr, old)

old_tw = getattr(dlg2, "_test_workers", None)
dlg2._test_workers = [_FakeWorker(True)]
try:
    dlg2._refresh_nav_rings()
    check("数据源测试(_test_workers) 运行中 → 导航「演员刮削」转圈",
          dlg2.nav_rings["演员刮削"].is_busy())
finally:
    if old_tw is None:
        if hasattr(dlg2, "_test_workers"):
            del dlg2._test_workers      # 恢复「属性不存在」的出厂状态
    else:
        dlg2._test_workers = old_tw

# _test_workers 为 None 时也要能兜住（轮询槽里任何异常都会让所有转圈静默失效）
dlg2._test_workers = None
try:
    dlg2._refresh_nav_rings()
    check("_test_workers = None 时 _running_tasks() 不炸（None 兜底）", True)
except Exception as e:
    check("_test_workers = None 时 _running_tasks() 不炸（None 兜底）", False,
          "%s: %s" % (type(e).__name__, e))
finally:
    if hasattr(dlg2, "_test_workers"):
        del dlg2._test_workers

# 跨页任务：两个检测页问 is_busy()（图像检测页被 _page_scroll 包成 QScrollArea，
# 必须打到内部真实页面 —— _running_tasks 的 _page_busy 会先 unwrap）
_img_page = dlg2._pg_imagedetect.widget()
check("图像检测页确实被 QScrollArea 包装（_page_busy 必须先 unwrap）",
      dlg2._pg_imagedetect is not _img_page
      and hasattr(_img_page, "is_busy"))
old_ack = dlg2._pg_actorcheck.is_busy
old_img = _img_page.is_busy
dlg2._pg_actorcheck.is_busy = lambda: True
try:
    dlg2._refresh_nav_rings()
    check("演员检测页 is_busy() → 导航「演员检测」转圈",
          dlg2.nav_rings["演员检测"].is_busy())
finally:
    dlg2._pg_actorcheck.is_busy = old_ack
_img_page.is_busy = lambda: True
try:
    dlg2._refresh_nav_rings()
    check("图像检测页 is_busy()（QScrollArea 内部）→ 导航「图像检测」转圈",
          dlg2.nav_rings["图像检测"].is_busy())
finally:
    _img_page.is_busy = old_img

dlg2._refresh_nav_rings()
check("全部任务结束后 ring 全部隐藏",
      dlg2._running_tasks() == set()
      and all(not r.is_busy() for r in dlg2.nav_rings.values()))


# ================================================================ ④ 画像概览高频榜 / 分布排版（反馈 4）
print("\n---- ④ 画像概览「高频榜 / 分布」长 CJK 名排版 ----")
import re as _re
from ui_settings import SettingsDialog

_ui = SettingsDialog(None)
_ui.resize(1000, 900)
_ui.show()
_ui._show("画像概览")
for _ in range(6):
    app.processEvents()

# 用户截图里的真实数据形态：系列 / 片商 / 导演列全是长 CJK，正是把行撑爆的元凶。
_INSERTS = {
    "tags": [("有码", 314), ("单纯作品", 308), ("中出", 222), ("巨乳", 183),
             ("连环裸", 145), ("DMM独家", 132), ("女教师", 100), ("教师", 92),
             ("西装", 76), ("乱伦", 74), ("有码", 72), ("多P", 59)],
    "actors": [("柳ゆか", 18), ("花沢ゆき", 16), ("あいり菜", 12), ("白峰きろ", 12),
               ("飛山莉緒", 6), ("星田一花", 6), ("深川い suba", 6)],
    "directors": [("肉Translator", 74), ("ムKelly坂川", 21), ("三輪な志郎", 21),
                  ("星藤", 18), ("イノ purchasers", 15), ("Takuo Ohtani", 15),
                  ("aranata園", 14)],
    "studios": [("S1 NO.1 STYLE", 101), ("肉手列", 84), ("AV Boise", 76),
                (" Merit", 75), ("ムatrix", 61), ("SEX丽人", 60),
                ("Attackers", 59), ("Mature", 53)],
    "series": [("SEX依存症の女", 48), ("00の湿ったパirst", 37),
               ("女教師NTR 不良生徒に最愛の雲を奪う", 26),
               ("人妻秘書、汗と接吻に満ちた社長室中出", 24),
               ("上司のゴADOYENに何度もイカされるemas", 21),
               ("女体社員と絶対上司が出張先の相部屋", 16),
               ("脅迫スイートルーム", 14),
               ("取引先の激使社長に中出しされ続けた女", 14)],
}
_DIST = {
    "画质": [("1080P", 211), ("720P", 205), ("未标注", 134)],
    "评分": [("4~6", 123), ("6~7", 21), ("7~7.5", 14), ("7.5~8", 11),
             ("8~9", 46), ("9~10", 19), ("无评分", 299)],
    "时长": [("30~60 分", 6), ("60~90 分", 10), ("90~120 分", 70),
             ("120~180 分", 441), ("≥180 分", 23)],
    "年份": [("2012~2016", 27), ("2017~2021", 102), ("2022~2026", 421)],
    "入库月": [("2025-05", 7), ("2025-06", 20), ("2025-07", 49),
              ("2025-08", 14), ("2025-09", 24), ("2025-10", 10),
              ("2025-11", 14), ("2025-12", 4), ("2026-01", 12),
              ("2026-02", 14), ("2026-03", 7), ("2026-04", 9),
              ("2026-05", 12), ("2026-06", 7), ("2026-07", 9),
              ("2026-08", 18)],
}


def _probe_bar(body, items, tag):
    """三项断言：不折行 / 不溢出 / 计数右对齐。

    ⚠ 不能用 `body.height()` 判断折行：网格里的 QLabel 高度由布局统一拉伸，跟文本
    行数无关（7 行文本的标签也是 180px）。「不折行」是**构造性**保证的 ——
    `_bar_label()` 设了 `setWordWrap(False)`，于是只要每行像素宽 ≤ 列宽就成立，
    这也正是 v1.39.2 的修法本身。QTextLayout 的 `createLine()` 在裸 layout 上会
    段错误（exit 139），不要用。
    """
    body.setText(_ui._bar_lines(items, body, show_bar=True))
    for _ in range(3):
        app.processEvents()
    txt = body.text()
    fm = body.fontMetrics()
    widest = max(fm.horizontalAdvance(l) for l in txt.split("\n"))
    fits_w = widest <= body.width() + 1
    no_wrap = (body.wordWrap() is False) and fits_w
    rights = set()
    for line in txt.split("\n"):
        # 计数后面要么行尾、要么 "  █…" 条形；前面必有一个空格（右对齐补出来的），
        # 据此排除**名字里**的数字（如 "1080P" / "2025-05"）。
        for m in _re.finditer(r"(?<=\s)\d[\d,]*(?=\s*(?:█|$))", line):
            rights.add(fm.horizontalAdvance(line[:m.end()]))
    aligned = bool(rights) and (max(rights) - min(rights)) <= 4
    check("%s 不折行" % tag, no_wrap,
          "wordWrap=%s 最宽行 %dpx / 列宽 %dpx" % (body.wordWrap(), widest,
                                            body.width()))
    check("%s 不溢出" % tag, fits_w, "%d<= %d" % (widest, body.width()))
    check("%s 计数右对齐" % tag, aligned, "右端集合 %s" % sorted(rights))
    # tooltip 里必须仍是完整名字（正文已裁过）
    tt = body.toolTip()
    check("%s tooltip 保全名" % tag,
          bool(tt) and all(str(n) in tt for n, _c in items[:3]), tt.split("\n")[0])


check("高频榜 5 个 body 都是不换行 + 横向 Ignored",
      all(b.wordWrap() is False
          and b.sizePolicy().horizontalPolicy() == QSizePolicy.Ignored
          for b in _ui.ins_lists.values()),
      {k: (b.wordWrap(), b.sizePolicy().horizontalPolicy())
       for k, b in _ui.ins_lists.items()})
check("分布 5 个 body 都是不换行 + 横向 Ignored",
      all(b.wordWrap() is False
          and b.sizePolicy().horizontalPolicy() == QSizePolicy.Ignored
          for b in _ui.ins_dist.values()),
      {k: (b.wordWrap(), b.sizePolicy().horizontalPolicy())
       for k, b in _ui.ins_dist.items()})

for _k, _b in _ui.ins_lists.items():
    _probe_bar(_b, _INSERTS[_k], "高频榜.%s" % _k)
for _k, _b in _ui.ins_dist.items():
    _probe_bar(_b, _DIST[_k], "分布.%s" % _k)

# 空数据不炸，且回落到 "—"
_ui.ins_lists["series"].setText(_ui._bar_lines([], _ui.ins_lists["series"]))
check("空数据回落为 —", _ui.ins_lists["series"].text() == "—")

# 页面横向没被撑爆（Ignored 的意义就在这）。
# ⚠ 判据只能看**标签自身宽度**：`_ui.width()` 是 window 的**外框**宽（含边框），
# resize(1000,900) 之后它是 1016 而不是 1000，拿它当阈值会误报。
# 真正要证明的是「列宽仍是均分的小份」，而不是「某个绝对数字」。
_cols = list(_ui.ins_lists.values()) + list(_ui.ins_dist.values())
_w = [b.width() for b in _cols]
check("5 列均分且未被 minSizeHint 顶宽",
      len(_w) == 10 and max(_w) - min(_w) <= 4 and max(_w) <= 0.35 * _ui.width(),
      "列宽 %s / 窗口外框 %d" % (_w, _ui.width()))

_ui.close()
del _ui


# ============================================== ⑤ 复选框真机可见性（v1.39.2 真根因）
print("\n---- ⑤ 复选框未勾选态真机可见性 ----")
# ⚠⚠ 方法学铁律：**必须与「空树」逐像素差分**，且**未勾选态也要 > 0**。
# v1.39.0 的探针量的是「Checked vs Unchecked 的差分面积」（46→279px）——
# 差分对得上只证明两个状态有差别，**完全证明不了有复选框**，于是漏掉了真机上
# 「未勾选态一格都不画」这个真缺陷（真机截图实锤）。同样的像素差分，
# 基准换成空树，未勾选态才量出 304→1015 的真实面积。
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem


def _cb_tree(width, rows=3):
    t = QTreeWidget()
    t.setColumnCount(5)
    t.setHeaderLabels(["选择", "候选", "人数", "匹配度", "判定依据"])
    t.setColumnWidth(0, width)
    t.setColumnWidth(1, 240)
    root = QTreeWidgetItem(["", "", "", "", ""])
    t.addTopLevelItem(root)
    for i in range(rows):
        it = QTreeWidgetItem(["", "よしい美希 / よし美希", "2 人", "94 标注", "完全一致"])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(0, Qt.Unchecked)
        root.addChild(it)
    root.setExpanded(True)
    t.resize(700, 240)
    t.show()
    for _ in range(6):
        app.processEvents()
    return t, root


def _sel_col_pixels(t, root, state, rows=3):
    """返回「选择」列的像素颜色列表；state=None → 移除全部子行当空基准。"""
    if state is None:
        for i in range(root.childCount() - 1, -1, -1):
            root.removeChild(root.child(i))
    else:
        for i in range(min(rows, root.childCount())):
            root.child(i).setCheckState(0, state)
    for _ in range(6):
        app.processEvents()
    img = t.grab().toImage()
    x0, x1 = 20, 20 + t.columnWidth(0)
    y0, y1 = t.header().height() + 4, t.header().height() + 4 + 22 * rows
    return [img.pixelColor(x, y).rgba()
            for y in range(y0, y1) for x in range(x0, x1)]


def _cb_area(width, state):
    b_t, b_r = _cb_tree(width)
    base = _sel_col_pixels(b_t, b_r, None)
    b_t.close()
    t, r = _cb_tree(width)
    pix = _sel_col_pixels(t, r, state)
    t.close()
    return sum(1 for a, b in zip(pix, base) if a != b)


for _w in (46, 62, 80):
    _u = _cb_area(_w, Qt.Unchecked)
    _c = _cb_area(_w, Qt.Checked)
    check("列宽 %d 未勾选态有复选框（>0）" % _w, _u > 0, "差异像素 %d" % _u)
    check("列宽 %d 已勾选态有复选框（>0）" % _w, _c > 0, "差异像素 %d" % _c)

# QSS 根因守卫：未勾选态**不能是半透明背景**。设了 width/height 后 Qt 走 QSS
# 分支会重铺背景，半透明 = 判成「无背景」→ 整块跳过绘制（一格都不画）。
_qss = open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()


def _qss_block(sel):
    """取某个选择器的完整声明块（含其后所有行，直到花括号闭合）。

    ⚠ 四个坑（都真踩过）：
      ① **选择器后面不一定紧跟 " {"** —— 真实 qss 里有合并写法
         `QCheckBox::indicator, QRadioButton::indicator {`，按 `sel + " {"`
         查找直接落空。所以先定位选择器名，再往后找第一个 `{`。
      ② 不能只切到第一个 `}` —— `width/height/border/background` 常写在同一行，
         且块内还有 `:hover` / `:checked` 变体，要**按花括号深度**配平。
      ③ **必须剔除块内注释** —— qss 里那段解释「为什么不能用半透明」的说明文字
         恰好写着 `rgba(255,255,255,0.05)`，不剔除就会把注释当成声明。
      ④ 判定只看 `background:` **冒号之后**的值 —— 同一行的 border 也含 rgba()。
    """
    i = _qss.find(sel)
    if i < 0:
        return ""
    j = _qss.find("{", i)
    if j < 0:
        return ""
    depth, out = 0, []
    k = j
    while k < len(_qss):
        c = _qss[k]
        out.append(c)
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    blk = "".join(out)
    while "/*" in blk and "*/" in blk:
        a, b = blk.find("/*"), blk.find("*/")
        blk = blk[:a] + blk[b + 2:]
    return blk


for _sel in ("QTreeView::indicator", "QListWidget::indicator",
             "QCheckBox::indicator"):
    # 只看**未勾选**声明：取到 `::checked` / `:checked` 之前那截
    _blk = _qss_block(_sel)
    _cut = _blk.find(":checked")
    _un = _blk[:_cut] if _cut > 0 else _blk
    # ⚠ 只取 `background:` **冒号之后**的值判断 —— 同一行里的 border 也含 rgba()，
    # 直接对整行判 "rgba( not in" 会永远失败。
    _vals = [l.split("background:", 1)[1].strip().rstrip(";")
             for l in _un.splitlines() if "background:" in l]
    check("%s 未勾选态用实色背景" % _sel,
          bool(_vals) and not _vals[0].startswith("rgba("),
          _vals[0] if _vals else "（未勾选块里没有 background 行）")


# ================================================================ ⑥ 版本号
print("\n---- ⑥ 版本号 ----")
check("外部版本号 = v1.39.4", ver.VERSION == "v1.39.4", ver.VERSION)
check("内部构建号 = 2610130061", ver.BUILD == "2610130061", ver.BUILD)


# ================================================================ ⑦ 全模块 import 链
print("\n---- ⑦ 全模块 import 链（打包隐式依赖不丢）----")
_mods = ["applog", "backdrop", "config", "database", "guide_translate", "i18n",
         "insight", "main_window", "recommend", "scan_ring", "scraper", "splash",
         "sysmon", "ui_actorcheck", "ui_imagedetect", "ui_manualedit",
         "ui_settings", "version"]
for m in _mods:
    try:
        importlib.import_module(m)
        check("import %s" % m, True)
    except Exception as e:
        check("import %s" % m, False, "%s: %s" % (type(e).__name__, e))


# ================================== ⑧ QStyle 守卫（v1.39.4：windows11 画不出复选框）
print("\n---- ⑧ QStyle：必须是 Fusion（windows11 画不出 QTreeView::indicator）----")
# v1.39.4 真根因：Qt 6 在 Windows 11 上默认 QStyle = `windows11`，
# 它是四个可用风格里**唯一**画不出 `QTreeView::indicator` 的（实测色像素 0，
# 而 windowsvista=770 / Windows=820 / Fusion=820）。`QStyleSheetStyle` 画的
# indicator 与 windows11 原生 checkbox 路径冲突 → 直接跳过绘制 →
# 「演员检测」结果树「选择」列一格不画。修法是 main.py 显式 setStyle("Fusion")。
_mainsrc = open(os.path.join(SRC, "main.py"), encoding="utf-8").read()
check("main.py 里显式 setStyle(QStyleFactory.create('Fusion'))",
      ("QStyleFactory.create(\"Fusion\")" in _mainsrc
       and "app.setStyle" in _mainsrc),
      "")

# 实跑：在 windows 平台后端下量复选框颜色像素。
# ⚠ offscreen 后端用不到 windows11，**测不出这个缺陷** —— 所以这里必须显式
# 拉起一个 windows 后端的 QApplication（同进程不能换 platform，故用子进程）。
_probe = os.path.join(TMP, "_qstyle_probe.py")
os.makedirs(TMP, exist_ok=True)
open(_probe, "w", encoding="utf-8").write(
    "import os, sys\n"
    "os.environ['QT_QPA_PLATFORM'] = 'windows'\n"
    "os.environ['LMC_NO_SYSMON'] = '1'\n"
    "from PySide6.QtWidgets import (QApplication, QTreeWidget, QTreeWidgetItem,\n"
    "    QStyleFactory, QAbstractItemView, QStyle, QStyleOptionViewItem)\n"
    "from PySide6.QtCore import Qt\n"
    "app = QApplication(sys.argv)\n"
    "out = {'default': app.style().objectName()}\n"
    "st = QStyleFactory.create('Fusion')\n"
    "app.setStyle(st)\n"
    "out['after'] = app.style().objectName()\n"
    "from main_window import load_style\n"
    "load_style(app)\n"
    "t = QTreeWidget()\n"
    "t.setHeaderLabels(['选择','候选'])\n"
    "r = QTreeWidgetItem(['r','','','',''])\n"
    "t.addTopLevelItem(r)\n"
    "for i in range(3):\n"
    "    it = QTreeWidgetItem(['','n%d'%i,'','',''])\n"
    "    it.setFlags(it.flags() | Qt.ItemIsUserCheckable)\n"
    "    it.setCheckState(0, Qt.Unchecked)\n"
    "    r.addChild(it)\n"
    "r.setExpanded(True)\n"
    "t.setColumnWidth(0, 62)\n"
    "t.resize(700, 200)\n"
    "t.show(); app.processEvents()\n"
    "img = t.grab().toImage()\n"
    "y0 = t.header().height()\n"
    "n = 0\n"
    "for y in range(y0, min(img.height(), y0 + 80)):\n"
    "    for x in range(0, 66):\n"
    "        c = img.pixelColor(x, y)\n"
    "        if (c.red(), c.green(), c.blue()) in ((42,36,28), (89,82,73)):\n"
    "            n += 1\n"
    "out['px'] = n\n"
    "idx = t.model().index(0, 0, t.rootIndex())\n"
    "opt = QStyleOptionViewItem(); opt.rect = t.visualRect(idx)\n"
    "opt.state = QStyle.State_Enabled\n"
    "opt.features = (QStyleOptionViewItem.HasCheckIndicator\n"
    "                | QStyleOptionViewItem.HasDisplay)\n"
    "out['rect'] = t.style().subElementRect(\n"
    "    QStyle.SE_ItemViewItemCheckIndicator, opt, None).width()\n"
    "print('RESULT', out)\n"
)
import subprocess
_env = dict(os.environ)
_env["PYTHONPATH"] = SRC
_r = subprocess.run([sys.executable, "-u", _probe], capture_output=True,
                    text=True, env=_env, timeout=180)
_res = {}
for _ln in _r.stdout.splitlines():
    if _ln.startswith("RESULT"):
        import ast
        _res = ast.literal_eval(_ln[7:].strip())
if not _res:
    check("windows 后端下复选框色像素 > 0（真机可见）", False,
          "子进程未产出结果 rc=%s stderr=%s"
          % (_r.returncode, (_r.stderr or "")[-300:]))
else:
    check("windows 后端可跑（拿到 QStyle 报告）", True,
          "default=%s after=%s" % (_res.get("default"), _res.get("after")))
    # 注：这里报的default 是 Qt 的**原始**默认值，Win11 上就是 windows11 ——
    # 它恰恰是要被 main.py 改掉的对象，所以不能断言 default != windows11
    #（那等于要求 Qt 自己改）。真正的守卫是「main.py 里有 setStyle(Fusion)」
    # ＋「设定后复选框色像素 > 0」，下面两条才是。
    check("Qt 原始默认确为 windows11（说明 main.py 的 setStyle 是必需的）",
          _res.get("default") == "windows11", _res.get("default"))
    check("设定后 QStyle = fusion", _res.get("after") == "fusion",
          _res.get("after"))
    check("windows 后端下复选框色像素 > 0（真机可见）",
          int(_res.get("px") or 0) > 0, "色像素 %s" % _res.get("px"))


print("")
print(f"==== v1.39.4 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  (失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAIL:", n)

try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if FAIL else 0)
