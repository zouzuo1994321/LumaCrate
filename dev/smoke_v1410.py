# -*- coding: utf-8 -*-
"""v1.40.10 冒烟（离屏，不截图）：六条 UI 反馈 + v1.40.9 回归
====================================================================
六条反馈（来自用户整页截图；红框区域由用户口头确认为「演员刮削页顶部开关区」）：
  ① 演员刮削顶部开关区压矮；
  ② 演员检测选中色跟软件风格（QTreeView::item:selected）；
  ③ 高频榜美化（RichText + 当前高亮色条形）；
  ④ 重复检测 / 演员检测 / 图像检测 / 标签优化 运行时加「进行中」转圈；
  ⑤ 个性化设置无底部横向滚轴（冻结页 ScrollBarAlwaysOff）；
  ⑥ 演员检测高度条强调色 + 上下 2px 留白（ActorSplitV/H + objectName 限定）。

本脚本以**数据断言**取代肉眼截图（用户要求：交付不再附截图）。
  ① 源码层：style.qss / ui_actorcheck.py / ui_settings.py / version.py 关键改动到位；
  ② 真建控件（假屏幕复刻真机 2560×1392）：
       · v1.40.9 回归：12 页切遍窗口恒 1320×960 / 内容宽恒 1170 / 画布最小高 >= 内容；
         演员刮削子模块高度锁定（960 vs 1300 恒定）；画像概览无下滚轴；
       · 反馈①：顶部开关区组框高度 <= 旧基线 108（压缩生效、无回归）；
       · 反馈③：_bar_lines 输出含 accent 色 span + <br> + █（RichText 条形）；
       · 反馈④：_running_tasks 四条映射齐全；
       · 反馈⑤：冻结页 horizontalScrollBarPolicy == AlwaysOff；
       · 反馈⑥：演员检测两个 splitter objectName 到位。
  ③ 版本号 MINOR_ITER = 10 / BUILD_SEQ = "0073"。

跑法（务必用 E 盘绝对路径）：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/smoke_v1410.py"
"""
import os
import re
import sys

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication, QScrollArea, QGroupBox, QLabel, QVBoxLayout
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFontDatabase

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
QSS = open(os.path.join(ROOT, "src", "style.qss"), encoding="utf-8").read()
ASRC = open(os.path.join(ROOT, "src", "ui_actorcheck.py"), encoding="utf-8").read()
VSRC = open(os.path.join(ROOT, "src", "version.py"), encoding="utf-8").read()


def body_of(src, name):
    m = re.search(r"\n    def %s\(" % re.escape(name), src)
    if not m:
        return ""
    start = m.end()
    m2 = re.search(r"\n    def ", src[start:])
    body = src[start:start + m2.start()] if m2 else src[start:]
    lines = body.splitlines()
    while lines and lines[-1].strip().startswith("@"):
        lines.pop()
    return "\n".join(lines)


def code_only(body):
    b = re.sub(r'"""(?:.|\n)*?"""', "", body)
    b = re.sub(r"'''(?:.|\n)*?'''", "", b)
    out = []
    for ln in b.splitlines():
        i = ln.find("#")
        if i >= 0:
            ln = ln[:i]
        out.append(ln)
    return "\n".join(out)


# ---- v1.40.9 回归（防回退）----
FB_CODE = code_only(body_of(USRC, "_freeze"))
chk("def _freeze(self, widget, scroll=True, lock_height=False)" in USRC,
    "[回归] _freeze() 仍有 lock_height 形参")
chk("setWidgetResizable(not lock_height)" in FB_CODE,
    "[回归] _freeze() 仍用 setWidgetResizable(not lock_height)")
chk("self._freeze(self._build_scraper(), lock_height=True)" in USRC,
    "[回归] 演员刮削页仍走 lock_height=True")
chk("self._page_scroll(self._build_insight())" in USRC,
    "[回归] 画像概览页仍走 _page_scroll（不锁高）")
DCH = body_of(USRC, "_defer_canvas_height")
chk("elif lock:" in DCH and "real = max(real, page.minimumSizeHint().height()," in DCH,
    "[回归] 锁高分支仍在（钉死真实自然高）")
INS = body_of(USRC, "_build_insight")
chk("self.ins_radar.setFixedHeight(220)" in INS,
    "[回归] 画像概览雷达仍钉高 220")
chk("low = QHBoxLayout()" in INS and "low.addWidget(g3)" in INS and "low.addWidget(g4)" in INS,
    "[回归] 高频榜 + 分布 仍并排成一行")

# ---- 反馈①：演员刮削顶部开关区压矮 ----
chk('_en_lab = QLabel("启用演员刮削（补齐演员头像 / 别名 / 生日 / 简介）")' in USRC
    and "_en_lab.setWordWrap(False)" in USRC,
    "反馈① 启用说明标签 setWordWrap(False) 锁单行（窄窗不再折两行顶高）")
chk("geh.setContentsMargins(9, 2, 9, 2)" in USRC,
    "反馈① 顶部开关区组内上下留白 4→2")
chk("geh.setSpacing(8)" in USRC,
    "反馈① 顶部开关区列间距 12→8")

# ---- 反馈②：演员检测选中色 ----
chk("QTreeView::item:selected { background: rgba(__ACCENT_DARK__, 0.72); color: #ffffff; }" in QSS,
    "反馈② style.qss 补 QTreeView::item:selected（强调色选中）")
chk("QTreeView::item:selected:!active" in QSS,
    "反馈② style.qss 补 QTreeView::item:selected:!active（失焦态）")

# ---- 反馈③：高频榜美化（RichText + accent）----
chk("def _bar_lines(self, items, body, show_bar=True, limit=16, accent=" in USRC,
    "反馈③ _bar_lines 改为实例方法并接收 accent 参数")
chk("lb.setTextFormat(Qt.RichText)" in USRC,
    "反馈③ _bar_label 改用 RichText")
chk("accent=self.s.accent()" in USRC,
    "反馈③ _render_insight 传 accent=self.s.accent()（跟随高亮色）")
chk("replace(\" \", \"&nbsp;\")" in USRC,
    "反馈③ 空格替换 &nbsp; 保等宽对齐")

# ---- 反馈④：四页「进行中」转圈映射 ----
chk('("_to_scan_worker", "标签优化")' in USRC
    and '("_to_run_worker", "标签优化")' in USRC
    and '("_to_ai_worker", "标签优化")' in USRC,
    "反馈④ 标签优化 三 worker 接进 _running_tasks")
chk('("_dd_worker", "重复检测")' in USRC,
    "反馈④ 重复检测 worker 接进 _running_tasks")
chk('("_pg_actorcheck", "演员检测")' in USRC
    and '("_pg_imagedetect", "图像检测")' in USRC,
    "反馈④ 演员检测 / 图像检测 走 _page_busy(is_busy) 接进 _running_tasks")
chk("nav_rings = {}" in USRC and "self.nav_rings[key] = ring" in USRC,
    "反馈④ nav_rings 按 NAV_GROUPS 建全（四页都有 ring）")

# ---- 反馈⑤：个性化无底部横向滚轴 ----
chk("sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)" in FB_CODE,
    "反馈⑤ 冻结页 setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)")

# ---- 反馈⑥：演员检测高度条强调色 ----
chk('split.setObjectName("ActorSplitV")' in ASRC,
    "反馈⑥ 演员检测竖向高度条 objectName = ActorSplitV")
chk('split.setObjectName("ActorSplitH")' in ASRC,
    "反馈⑥ 演员检测横向树/详情分隔条 objectName = ActorSplitH")
chk("QSplitter#ActorSplitV::handle:vertical" in QSS
    and "QSplitter#ActorSplitH::handle:horizontal" in QSS,
    "反馈⑥ style.qss 用 objectName 限定给两 splitter 上强调色 + 留白")

# ---- 版本号 ----
chk("MINOR_ITER = 10" in VSRC, "version.py MINOR_ITER = 10")
chk('BUILD_SEQ = "0073"' in VSRC, 'version.py BUILD_SEQ = "0073"')

# ---------- ② 真建控件 ----------
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


def settle(n=8):
    for _ in range(n):
        app.processEvents()


def page_of(sc):
    if not isinstance(sc, QScrollArea):
        return sc
    cv = sc.widget()
    if cv is None or cv.layout() is None or cv.layout().count() == 0:
        return cv
    return cv.layout().itemAt(0).widget()


def child_groups(page):
    out = {}
    for w in page.findChildren(QGroupBox):
        t = w.title().strip()
        if t:
            out.setdefault(t, w)
    return out


ORDER = ["个性化设置", "手动修改", "画像概览", "演员刮削", "智能推荐", "标签优化",
         "服务管理", "AI引擎设置", "重复检测", "演员检测", "图像检测", "数据与日志"]
PAGES = {
    "个性化设置": d._pg_personal, "手动修改": d._pg_manual, "画像概览": d._pg_insight,
    "演员刮削": d._pg_scraper, "智能推荐": d._pg_smart, "标签优化": d._pg_tagopt,
    "服务管理": d._pg_service, "AI引擎设置": d._pg_aiengine, "重复检测": d._pg_dedupe,
    "演员检测": d._pg_actorcheck, "图像检测": d._pg_imagedetect, "数据与日志": d._pg_data,
}

settle(12)
chk(d.width() == 1320 and d.height() == 960,
    "打开默认宽 1320 / 高 960（实际 %dx%d）" % (d.width(), d.height()))

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

# ===== 反馈① + ③ 运行时 =====
print()
print("=" * 72)
print("③ 反馈① 顶部开关区压矮 + 反馈③ 高频榜 RichText")
print("=" * 72)

d._show("演员刮削")
settle(12)
sc = PAGES["演员刮削"]
pg = page_of(sc)
gs = child_groups(pg)
ge_h = gs.get("演员刮削")
if ge_h is not None:
    print("[顶部开关区] 组框高度 = %d（v1.40.9 基线 108）" % ge_h.height())
    # 压缩生效（<= 旧基线）；若改动无效果会卡在 108 附近，这里给 104 余量防误判
    chk(ge_h.height() <= 104,
        "反馈① 顶部开关区组框高度 %d <= 104（较 108 基线已压缩、无回归）" % ge_h.height())
else:
    chk(False, "反馈① 未找到「演员刮削」顶部开关区组框")

# 反馈③：直接调用 _bar_lines，断言输出为含 accent 的 RichText
# （_bar_lines 内部会取 body.parentWidget().width() 估算列宽，需给一个带父容器的 QLabel）
bar_host = QGroupBox()
bar_hl = QVBoxLayout(bar_host)
bar_lbl = QLabel("—")
bar_hl.addWidget(bar_lbl)
bar_host.show()
bar_host.resize(360, 120)
settle(4)
html = d._bar_lines([("测试演员", 1000), ("另一个名字", 500), ("第三", 200)],
                    bar_lbl, show_bar=True, accent="#C63975")
print("[高频榜] 输出片段：", html[:160].replace("\n", " "))
chk("color:#C63975" in html, "反馈③ 条形段使用 accent 高亮色（#C63975）")
chk("<br>" in html, "反馈③ 多行用 <br> 分隔（RichText）")
chk("█" in html, "反馈③ 条形仍用 █ 字符")
chk("&nbsp;" in html, "反馈③ 空格转 &nbsp; 保等宽对齐")

# ===== 反馈④ 映射（运行时核对 _running_tasks）=====
print()
print("=" * 72)
print("④ 反馈④ 四页 _running_tasks 映射")
print("=" * 72)
# 静态核对：_running_tasks 体含四页 key 的映射（已在源码层断言）；
# 运行时核对 nav_rings 字典确实含四页 key
for k in ("重复检测", "演员检测", "图像检测", "标签优化"):
    chk(k in d.nav_rings,
        "反馈④ nav_rings 含「%s」ring 实例" % k)
    ring = d.nav_rings.get(k)
    chk(ring is not None and hasattr(ring, "set_state"),
        "反馈④「%s」ring 可被 set_state 驱动（运行时出现转圈）" % k)

# ===== 反馈⑤ 冻结页无横滚轴 =====
print()
print("=" * 72)
print("⑤ 反馈⑤ 冻结页 ScrollBarAlwaysOff")
print("=" * 72)
for k in ORDER:
    sc = PAGES[k]
    if isinstance(sc, QScrollArea) and sc.property("lmc_frozen"):
        chk(sc.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff,
            "反馈⑤「%s」冻结页横向滚轴策略 = AlwaysOff" % k)

# ===== 反馈⑥ 演员检测 splitter objectName =====
print()
print("=" * 72)
print("⑥ 反馈⑥ 演员检测 splitter objectName")
print("=" * 72)
ac = d._pg_actorcheck
found_v = found_h = False
from PySide6.QtWidgets import QSplitter as _QSplitter
for sp in ac.findChildren(_QSplitter):
    if sp.objectName() == "ActorSplitV":
        found_v = True
    if sp.objectName() == "ActorSplitH":
        found_h = True
chk(found_v, "反馈⑥ 演员检测竖向高度条 objectName == ActorSplitV（运行时）")
chk(found_h, "反馈⑥ 演员检测横向分隔条 objectName == ActorSplitH（运行时）")

# ===== v1.40.9 回归：演员刮削锁高 + 画像概览无下滚轴 =====
print()
print("=" * 72)
print("⑦ v1.40.9 回归：锁高 + 无下滚轴")
print("=" * 72)
d._show("演员刮削")
settle(12)
sc = PAGES["演员刮削"]
pg = page_of(sc)


def snap_actor_heights():
    d.resize(1320, 960)
    settle(15)
    cv = sc.widget()
    h960 = dict(canvas_min=cv.minimumHeight(), canvas_max=cv.maximumHeight())
    gs_ = child_groups(pg)
    h960["groups"] = {t: w.height() for t, w in gs_.items()}
    d.resize(1320, 1300)
    settle(15)
    cv = sc.widget()
    h1300 = dict(canvas_min=cv.minimumHeight(), canvas_max=cv.maximumHeight())
    gs_ = child_groups(pg)
    h1300["groups"] = {t: w.height() for t, w in gs_.items()}
    return h960, h1300


h960, h1300 = snap_actor_heights()
print("[h960 ] 画布 min=%d max=%d 子模块=%s"
      % (h960["canvas_min"], h960["canvas_max"], {t: h for t, h in h960["groups"].items()}))
print("[h1300] 画布 min=%d max=%d 子模块=%s"
      % (h1300["canvas_min"], h1300["canvas_max"], {t: h for t, h in h1300["groups"].items()}))
chk(h960["canvas_min"] == h1300["canvas_min"],
    "回归 演员刮削画布高不随窗口变（960:%d == 1300:%d）"
    % (h960["canvas_min"], h1300["canvas_min"]))
need_actor = uis.SettingsDialog._content_need_height(pg)
chk(h960["canvas_min"] >= need_actor - 1,
    "回归 演员刮削画布 %d >= 内容需求 %d（锁高不切底）" % (h960["canvas_min"], need_actor))
all_same = all(h960["groups"].get(t) == h1300["groups"].get(t) for t in h960["groups"])
chk(all_same, "回归 演员刮削各子模块高度在 960 / 1300 下一一恒定")
d.resize(1320, 960)
settle(12)

d._show("画像概览")
settle(12)
ov = dict(scope="全部媒体库", media=48000, favorite=10000, actors=5000,
          actor_links=90000, directors=3000, director_links=40000, series=2000,
          studios=500, tags=3000, avg_rating=7.52, total_hours=90000,
          total_size=50_000_000_000)
fake = {
    "overview": ov,
    "line": "这是一句合成的画像总评，用来把一句话画像组框撑到接近真实的行数。",
    "radar": [("剧情", 0.8, "强"), ("演员", 0.6, "中"), ("画质", 0.7, "中"),
              ("评分", 0.9, "强"), ("时长", 0.5, "中"), ("年份", 0.4, "弱"),
              ("系列", 0.6, "中"), ("片商", 0.5, "中")],
    "tags": [(t, n) for t, n in [("剧情", 3000), ("爱情", 2800), ("喜剧", 2500),
             ("动作", 2200), ("科幻", 2000), ("悬疑", 1800), ("治愈", 1600),
             ("运动", 1400), ("音乐", 1200), ("恐怖", 1000), ("纪录", 900),
             ("奇幻", 800), ("冒险", 700), ("战争", 600), ("历史", 500), ("犯罪", 400)]],
    "actors": [("某演员%c" % chr(65 + i), 900 - i * 50) for i in range(16)],
    "directors": [("导演%c" % chr(65 + i), 400 - i * 25) for i in range(16)],
    "studios": [("片商%c" % chr(65 + i), 500 - i * 30) for i in range(16)],
    "series": [("系列%c" % chr(65 + i), 300 - i * 15) for i in range(16)],
    "dist": {
        "画质": [("1080P", 30000), ("4K", 12000), ("720P", 4000), ("2160P", 2000),
                 ("1080P60", 1000), ("原盘", 800), ("HDR", 600), ("SDR", 500),
                 ("480P", 300), ("2K", 200), ("360P", 100), ("8K", 80),
                 ("1080I", 60), ("准4K", 50), ("480I", 40), ("其他", 30)],
        "评分": [("9+", 5000), ("8+", 9000), ("7+", 12000), ("6+", 8000),
                 ("5+", 4000), ("4+", 2000), ("3+", 1000), ("2+", 500),
                 ("1+", 300), ("0+", 200), ("8.5+", 400), ("9.5+", 300),
                 ("7.5+", 350), ("6.5+", 250), ("5.5+", 150), ("其他", 100)],
        "时长": [("90-120", 15000), ("60-90", 12000), ("120-150", 9000),
                 ("150-180", 6000), ("30-60", 5000), ("180+", 4000),
                 ("<30", 2000), ("120-", 1500), ("90-", 1200), ("60-", 1000),
                 ("45-", 800), ("75-", 700), ("105-", 600), ("135-", 500),
                 ("165-", 400), ("其他", 300)],
        "年份": [("2020", 8000), ("2021", 7500), ("2022", 7000), ("2023", 6500),
                 ("2024", 6000), ("2019", 5500), ("2018", 5000), ("2017", 4500),
                 ("2016", 4000), ("2015", 3500), ("2014", 3000), ("2013", 2500),
                 ("2012", 2000), ("2011", 1500), ("2010", 1000), ("更久", 800)],
        "入库月": [("1月", 4000), ("2月", 3500), ("3月", 4500), ("4月", 5000),
                   ("5月", 5500), ("6月", 6000), ("7月", 6500), ("8月", 6000),
                   ("9月", 5500), ("10月", 5000), ("11月", 4500), ("12月", 7000),
                   ("旺季", 3000), ("淡季", 2500), ("促销月", 2000), ("其他", 1500)],
    },
    "cooc": [(("剧情", "爱情"), 1200), (("喜剧", "治愈"), 900), (("动作", "科幻"), 800),
            (("悬疑", "犯罪"), 700), (("运动", "青春"), 600), (("音乐", "治愈"), 500),
            (("奇幻", "冒险"), 400), (("战争", "历史"), 300), (("恐怖", "惊悚"), 200),
            (("纪录", "真实"), 100)],
}
d._insight_data = fake
d._on_insight_done(fake)
settle(40)
sc = PAGES["画像概览"]
pg = page_of(sc)
need = uis.SettingsDialog._content_need_height(pg)
vp = sc.viewport().height()
print("画像概览：内容需求 need=%d  视口高=%d  画布最小高=%d"
      % (need, vp, sc.widget().minimumHeight()))
chk(need <= vp, "回归 画像概览内容需求 %d <= 视口高 %d → 无下滚轴" % (need, vp))
chk(not sc.verticalScrollBar().isVisible(), "回归 画像概览竖向滚动条隐藏（塞进一屏）")

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
