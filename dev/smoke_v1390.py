# -*- coding: utf-8 -*-
"""v1.39.0 离屏冒烟（构建期）。

三条反馈的回归与单元断言：
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

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1390_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QAbstractItemView
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

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


# ================================================================ ④ 版本号
print("\n---- ④ 版本号 ----")
check("外部版本号 = v1.39.0", ver.VERSION == "v1.39.0", ver.VERSION)
check("内部构建号 = 2610130057", ver.BUILD == "2610130057", ver.BUILD)


# ================================================================ ⑤ 全模块 import 链
print("\n---- ⑤ 全模块 import 链（打包隐式依赖不丢）----")
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


print("")
print(f"==== v1.39.0 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  (失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAIL:", n)

try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if FAIL else 0)
