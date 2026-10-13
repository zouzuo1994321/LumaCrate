# -*- coding: utf-8 -*-
"""v1.40.8 冒烟（离屏）：页面内容完整显示回归
==============================================
背景：v1.40.7 把用户要的「**宽度**冻结」误做成了「宽 + 高都钉死」——
`page.setFixedHeight(page.sizeHint().height())`。`sizeHint()` 是构造途中的估算值
（实测手动修改 356 / 画像概览 792，真值 1400+ / 1242），且「整页自带滚动区」的页面
被钉在比视口还矮的高度后，外层给不了高度、内层滚动区也拿不到高度 → 内容被**硬切**。

本脚本断言 v1.40.8 的修法：
  ① 源码层：`_freeze()` 不再 `setFixedHeight`、只 `setFixedWidth(CONTENT_W)`；
     新增 `_content_need_height()` / `_defer_canvas_height()` / `_refresh_frozen_height()`
     / `_show_refresh_frozen()`；画布 `objectName=="LmcFreezeCanvas"`；
     `ui_manualedit.ManualEditPage` 有 `contentChanged` 信号。
  ② 真建控件（**假屏幕复刻真机 2560×1392**）：
       · 12 页切遍窗口恒为 1320×960；
       · 每页内容宽恒为 1170；
       · **每页「画布最小高 >= 内容需求」**（= 内容不被切，本版核心断言）；
       · 拉宽到 1900 内容宽仍 1170；
       · 拉高到 1200：矮内容页铺满视口、高内容页画布变高（可滚）。
  ③ 动态：手动修改选片后画布最小高自动变大；画像概览分析完成后自动变大。

跑法（务必用 E 盘绝对路径）：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/smoke_v1408.py"
"""
import os
import re
import sys

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication, QScrollArea
from PySide6.QtCore import QRect
from PySide6.QtGui import QFontDatabase

# ---------- 断言框架 ----------
OK = []
BAD = []


def chk(cond, msg):
    (OK if cond else BAD).append(msg)
    print(("[OK ] " if cond else "[FAIL] ") + msg)


# ---------- ① 源码层 ----------
print("=" * 72)
print("① 源码层断言")
print("=" * 72)

USRC = open(os.path.join(ROOT, "src", "ui_settings.py"), encoding="utf-8").read()
MSRC = open(os.path.join(ROOT, "src", "ui_manualedit.py"), encoding="utf-8").read()

# 从 class SettingsDialog 起截（避开文件开头可能的同名子串）
CLS = USRC[USRC.find("class SettingsDialog"):]


def body_of(src, name):
    """取一个方法的函数体源码（从 `def` 那行起，到下一个同缩进 `def` 前）。

    ⚠ 两处必须处理，否则会把「下一个方法」的碎片带进来：
      · `\\n    def ` 只截到下一个 `def` 那行，**装饰器**（`@staticmethod` 等）
        在它**前面**，会被一起带进来 → 结尾要把尾部的装饰器行剪掉；
      · 本函数从 `def <name>(` **之后**开始，第一行是签名残余（`self, sc):`），
        由 `is_stub()` 负责丢掉。

    ⚠ 返回的是**原始源码**（含注释与文档字符串）。
      判「有没有真的调用某 API」时必须先过一遍 `code_only()` ——
      本文件的注释里大量引用了 v1.40.7 的错法（`setFixedHeight` / `Qt.AlignLeft`），
      不剥注释就会把「注释里提到的」误判成「代码里在用的」。
    """
    m = re.search(r"\n    def %s\(" % re.escape(name), src)
    if not m:
        return ""
    start = m.end()
    m2 = re.search(r"\n    def ", src[start:])
    body = src[start:start + m2.start()] if m2 else src[start:]
    # 剪掉尾部可能被带进来的装饰器行（如 `@staticmethod`）
    lines = body.splitlines()
    while lines and lines[-1].strip().startswith("@"):
        lines.pop()
    return "\n".join(lines)


def code_only(body):
    """剥掉文档字符串与 `#` 注释，只留可执行语句（用于「是否真调用了某 API」的断言）。"""
    b = body
    # 去掉三引号文档字符串（贪婪度控制：非贪婪 + DOTALL）
    b = re.sub(r'"""(?:.|\n)*?"""', "", b)
    b = re.sub(r"'''(?:.|\n)*?'''", "", b)
    out = []
    for ln in b.splitlines():
        # 去掉行内 `#` 注释（简单起见：不处理字符串里的 #，本用例足够）
        i = ln.find("#")
        if i >= 0:
            ln = ln[:i]
        out.append(ln)
    return "\n".join(out)


def is_stub(src, name):
    """方法体是否只剩 return/pass（= 已停用）。剥掉文档字符串与注释后判。

    ⚠ `body_of()` 是从 `def <name>(` **之后**开始截的，所以第一行是签名的残余
      （如 `self, *_):` / `self, sc):`）—— 必须先丢掉，否则永远判不出「空壳」。
    """
    b = code_only(body_of(src, name))
    lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
    if lines and re.match(r"^self\b", lines[0]) and lines[0].endswith("):"):
        lines = lines[1:]        # 丢掉签名残余
    for ln in lines:
        if ln == "pass":
            continue
        if re.fullmatch(r"return\b.*", ln):
            continue
        return False
    return True


FB_CODE = code_only(body_of(USRC, "_freeze"))
chk("setFixedWidth(self.CONTENT_W)" in FB_CODE,
    "_freeze() 仍钉宽度 (setFixedWidth(self.CONTENT_W))")
chk("setFixedHeight" not in FB_CODE,
    "_freeze() **不再**用 setFixedHeight（v1.40.7 的错法已移除，注释不计）")
chk("Qt.AlignLeft" not in FB_CODE,
    "_freeze() **不再**用 Qt.AlignLeft 对齐旗标（与拉伸互斥，会退回 sizeHint 高）")
chk("setMinimumHeight(0)" in FB_CODE,
    "_freeze() 先把页面最小高归零（防构造途中虚高）")
chk("LmcFreezeCanvas" in FB_CODE, "画布 objectName 设为 LmcFreezeCanvas（供反查）")
chk("lmc_frozen" in FB_CODE, "滚动区带 lmc_frozen 属性（供探针识别）")

for name in ("_content_need_height", "_defer_canvas_height",
             "_refresh_frozen_height", "_show_refresh_frozen"):
    chk(("\n    def %s(" % name) in USRC, "存在方法 %s()" % name)

chk("def _show_refresh_frozen" in USRC and "def _refresh_frozen_height_soon" in USRC,
    "_refresh_frozen_height_soon() 保留（画像概览调用点）")
chk("self._show_refresh_frozen(self.stack.currentWidget())" in USRC,
    "_show() 切页后补量画布高")
chk("self._refresh_frozen_height_soon(self._pg_insight)" in USRC,
    "_on_insight_done() 分析完成后补量画布高")

# 旧状态机必须**还在**（v1.40.7 停用的那批，别被本版误删）
for name in ("_fit_page", "_compact_to", "_grow_to", "_unwrap_page", "_make_scrollable"):
    chk(is_stub(USRC, name), "%s() 仍是停用空壳（v1.40.7 状态保持）" % name)

chk("\n    def _page_scroll(" in USRC and "return self._freeze(widget, scroll=True)" in USRC,
    "_page_scroll() 仍是 _freeze() 的薄包装")

# ui_manualedit
chk("contentChanged = Signal()" in MSRC,
    "ui_manualedit.ManualEditPage 有 contentChanged 信号")
chk("self.contentChanged.emit" in MSRC,
    "换右栏根 widget 后广播 contentChanged")

# 版本号
VSRC = open(os.path.join(ROOT, "src", "version.py"), encoding="utf-8").read()
chk("MINOR_ITER = 8" in VSRC, "version.py MINOR_ITER = 8")
chk('BUILD_SEQ = "0071"' in VSRC, 'version.py BUILD_SEQ = "0071"')

# ---------- 真建控件 ----------
print()
print("=" * 72)
print("② 真建控件断言（假屏幕复刻真机 2560×1392）")
print("=" * 72)

app = QApplication([])
try:
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
except Exception:
    pass

import main_window as mw
import ui_settings as uis

print("ui_settings:", uis.__file__)
print("main_window:", mw.__file__)


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


uis.SettingsDialog.screen = lambda self: _FakeScr()
mw.load_style(app)

d = uis.SettingsDialog()
d.show()
for _ in range(10):
    app.processEvents()

ORDER = ["个性化设置", "手动修改", "画像概览", "演员刮削", "智能推荐", "标签优化",
         "服务管理", "AI引擎设置", "重复检测", "演员检测", "图像检测", "数据与日志"]
PAGES = {
    "个性化设置": d._pg_personal, "手动修改": d._pg_manual, "画像概览": d._pg_insight,
    "演员刮削": d._pg_scraper, "智能推荐": d._pg_smart, "标签优化": d._pg_tagopt,
    "服务管理": d._pg_service, "AI引擎设置": d._pg_aiengine, "重复检测": d._pg_dedupe,
    "演员检测": d._pg_actorcheck, "图像检测": d._pg_imagedetect, "数据与日志": d._pg_data,
}


def settle(n=8):
    for _ in range(n):
        app.processEvents()


def page_of(sc):
    """取冻结滚动区里的真页面。"""
    if not isinstance(sc, QScrollArea):
        return sc
    cv = sc.widget()
    if cv is None or cv.layout() is None or cv.layout().count() == 0:
        return cv
    return cv.layout().itemAt(0).widget()


settle(12)
chk(d.width() == 1320 and d.height() == 960,
    "打开默认宽 1320 / 高 960（实际 %dx%d）" % (d.width(), d.height()))

# ★ 画像概览的「分析前」画布最小高必须**在切页之前**记下来 ——
#   步骤 ② 会逐页切一遍（其中就包含「画像概览」，`_show()` 会触发自动分析），
#   等走到步骤 ③ 再取 `before` 就已经是「分析后」的值了（1242 -> 1242 的假失败）。
INSIGHT_MINH_BEFORE = d._pg_insight.widget().minimumHeight() if isinstance(
    d._pg_insight, QScrollArea) else 0
print("[info] 画像概览「分析前」画布最小高 = %d" % INSIGHT_MINH_BEFORE)
chk(d.minimumHeight() == uis.SettingsDialog.MIN_H,
    "最小高 == MIN_H(%d)（实际 %d）" % (uis.SettingsDialog.MIN_H, d.minimumHeight()))
chk(d.minimumHeight() != d.maximumHeight(),
    "**可拖拽**（minH=%d maxH=%d 应不等）" % (d.minimumHeight(), d.maximumHeight()))
chk(uis.SettingsDialog.CONTENT_W == uis.SettingsDialog.DEF_W - uis.SettingsDialog.NAV_W,
    "CONTENT_W == DEF_W - NAV_W (%d)" % uis.SettingsDialog.CONTENT_W)

print()
print("-- 逐页切换：窗口尺寸恒定 + 内容宽恒 1170 + 画布最小高 >= 内容需求 --")
for k in ORDER:
    d._show(k)
    settle(10)
    chk(d.width() == 1320 and d.height() == 960,
        "「%s」切页后窗口仍 1320x960（实际 %dx%d）" % (k, d.width(), d.height()))
    sc = PAGES[k]
    pg = page_of(sc)
    chk(pg.width() == 1170, "「%s」内容宽 1170（实际 %d）" % (k, pg.width()))
    if isinstance(sc, QScrollArea) and sc.property("lmc_frozen"):
        cv = sc.widget()
        need = uis.SettingsDialog._content_need_height(pg)
        chk(cv.minimumHeight() >= need,
            "「%s」画布最小高 %d >= 内容需求 %d（内容不被切）"
            % (k, cv.minimumHeight(), need))

print()
print("-- 拉宽到 1900：内容宽仍 1170 --")
d.resize(1900, 960)
settle(12)
for k in ORDER:
    d._show(k)
    settle(8)
    pg = page_of(PAGES[k])
    chk(pg.width() == 1170, "「%s」拉宽后内容宽 1170（实际 %d）" % (k, pg.width()))
d.resize(1320, 960)
settle(12)

print()
print("-- 拉高到 1200：矮内容页铺满视口 / 高内容页可滚 --")
d.resize(1320, 1200)
settle(12)
d._show("手动修改")
settle(10)
sc = PAGES["手动修改"]
pg = page_of(sc)
chk(pg.height() >= sc.viewport().height() - 2,
    "手动修改页铺满视口高（page=%d viewport=%d）" % (pg.height(), sc.viewport().height()))
d._show("个性化设置")
settle(10)
cv = PAGES["个性化设置"].widget()
chk(cv.minimumHeight() >= 1300,
    "个性化设置画布最小高 >= 1300（实际 %d）→ 外侧可滚动" % cv.minimumHeight())
d.resize(1320, 960)
settle(12)

print()
print("-- 压窄到 900：内容仍 1170（不被压缩） --")
d.resize(900, 960)
settle(12)
pg = page_of(PAGES["手动修改"])
chk(pg.width() == 1170, "压窄后内容仍 1170（实际 %d）" % pg.width())
d.resize(1320, 960)
settle(12)

print()
print("=" * 72)
print("③ 动态内容变化断言")
print("=" * 72)

# 手动修改：选片后画布最小高必须变大
d._show("手动修改")
settle(10)
sc = PAGES["手动修改"]
pg = page_of(sc)
before = sc.widget().minimumHeight()
mp = d._manual_page
if mp.list.count():
    mp.list.setCurrentRow(0)
    settle(20)
    after = sc.widget().minimumHeight()
    chk(after > before,
        "手动修改选片后画布最小高变大（%d -> %d）" % (before, after))
    chk(after >= uis.SettingsDialog._content_need_height(pg),
        "选片后画布最小高 %d >= 内容需求 %d" % (after, uis.SettingsDialog._content_need_height(pg)))
    # 右栏自带滚动区高度正确（能拿到视口高）
    host = mp.scroll.widget()
    if host is not None:
        chk(mp.scroll.viewport().height() > 100,
            "右栏滚动区视口高 > 100（实际 %d）" % mp.scroll.viewport().height())
else:
    chk(False, "手动修改列表为空（索引库可能没数据，跳过）")

# 画像概览：分析完成后画布最小高必须变大
import time
d._show("画像概览")
settle(10)
sc = PAGES["画像概览"]
before = INSIGHT_MINH_BEFORE      # 见步骤 ② 前的 [info] 记录（切页会触发分析）
t0 = time.time()
while not d._insight_data and time.time() - t0 < 60:
    app.processEvents()
    time.sleep(0.03)
settle(40)
after = sc.widget().minimumHeight()
chk(bool(d._insight_data), "画像概览分析完成（数据非空）")
chk(after > before, "画像概览分析完成后画布最小高变大（%d -> %d）" % (before, after))
pg = page_of(sc)
need = uis.SettingsDialog._content_need_height(pg)
chk(after >= need, "画像概览画布最小高 %d >= 内容需求 %d" % (after, need))

print()
print("=" * 72)
print("结果：%d 项通过 / %d 项失败" % (len(OK), len(BAD)))
if BAD:
    print("失败项：")
    for m in BAD:
        print("  ✗ " + m)
print("全部通过 ✅" if not BAD else "存在失败 ❌")
print("=" * 72)
sys.exit(0 if not BAD else 1)
