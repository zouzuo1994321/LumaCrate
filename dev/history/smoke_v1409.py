# -*- coding: utf-8 -*-
"""v1.40.9 冒烟（离屏，不截图）：演员刮削子模块锁定高度 + 画像概览无下滚轴
==========================================================================
两条反馈（均针对 v1.40.8 的布局回修）：
  ① 演员刮削 和 其他工具一样，各个子模块锁定高度，不用跟着界面大小进行调整；
  ② 画像概览 控制好宽度，不用 下滚轴。

本脚本以**数据断言**取代肉眼截图（用户要求：本轮起交付不再附截图）：
  ① 源码层：`_freeze()` 支持 `lock_height` 形参；演员刮削页走 `lock_height=True`。
  ② 真建控件（假屏幕复刻真机 2560×1392）：
       · 12 页切遍窗口恒 1320×960 / 内容宽恒 1170 / 画布最小高 >= 内容需求
         （v1.40.8 的核心回归，必须保持）；
       · **演员刮削高度锁定**：窗口 960 与 1300 下，画布固定高恒定
         （minH==maxH）、各子模块（组框）高度一一恒定；
       · **画像概览无下滚轴**：注入合成满量数据后，内容需求 <= 视口高 → 无竖向滚动。
  ③ 版本号 MINOR_ITER = 9 / BUILD_SEQ = "0072"。

跑法（务必用 E 盘绝对路径）：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/smoke_v1409.py"
"""
import os
import re
import sys

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication, QScrollArea, QGroupBox
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


FB_CODE = code_only(body_of(USRC, "_freeze"))
chk("def _freeze(self, widget, scroll=True, lock_height=False)" in USRC,
    "_freeze() 新增 lock_height 形参")
chk("setWidgetResizable(not lock_height)" in FB_CODE,
    "_freeze() 用 setWidgetResizable(not lock_height)（lock 时关掉 resizable）")
# 演员刮削页调用点（在全文件里搜，避开 body_of 截到别的 _build* 方法）
chk("self._freeze(self._build_scraper(), lock_height=True)" in USRC,
    "_build() 演员刮削页走 lock_height=True")
chk("self._page_scroll(self._build_insight())" in USRC,
    "_build() 画像概览页走 _page_scroll（= _freeze 默认，不锁高，靠视口自适应）")
chk("self._freeze(self._build_insight(), lock_height=True)" not in USRC,
    "画像概览页**未**走 lock_height（保持可随视口滚动）")
# 锁高分支
DCH = body_of(USRC, "_defer_canvas_height")
chk("elif lock:" in DCH, "_defer_canvas_height() 有 lock 分支（钉死固定高）")
chk("real = max(real, page.minimumSizeHint().height()," in DCH,
    "锁高用 页面真实自然高 取大（need/minSizeHint/sizeHint）")
CNH = body_of(USRC, "_content_need_height")
chk("mh = w.minimumHeight()" in CNH,
    "_content_need_height() 采纳被显式钉死的 minimumHeight()")
# 画像概览收窄
INS = body_of(USRC, "_build_insight")
chk("self.ins_radar.setFixedHeight(220)" in INS,
    "画像概览雷达钉高 220（不再自然 300）")
# 高频榜 + 分布 并排：用 low 布局同时容纳 g3 / g4
chk("low = QHBoxLayout()" in INS and "low.addWidget(g3)" in INS and "low.addWidget(g4)" in INS,
    "画像概览 高频榜 + 分布 并排成一行（省掉一列竖向高度）")
chk("v.addLayout(low)" in INS, "画像概览 low 布局已加入页面")

# 版本号
VSRC = open(os.path.join(ROOT, "src", "version.py"), encoding="utf-8").read()
chk("MINOR_ITER = 9" in VSRC, "version.py MINOR_ITER = 9")
chk('BUILD_SEQ = "0072"' in VSRC, 'version.py BUILD_SEQ = "0072"')
chk('VERSION = f"v{PRODUCT_GENERATION}.{MAJOR_ITER}.{MINOR_ITER}"' in VSRC,
    "version.py 外部版本号由常量拼出（v1.40.9）")

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

# ===== ③ 演员刮削：高度锁定（窗口 960 vs 1300 子模块不变）=====
print()
print("=" * 72)
print("③ 演员刮削 子模块锁定高度（窗口 960 vs 1300）")
print("=" * 72)

d._show("演员刮削")
settle(12)
sc = PAGES["演员刮削"]
pg = page_of(sc)


def snap_actor_heights():
    d.resize(1320, 960)
    settle(15)
    cv = sc.widget()
    h960 = dict(canvas_min=cv.minimumHeight(), canvas_max=cv.maximumHeight(),
                page_sizehint=pg.sizeHint().height())
    gs = child_groups(pg)
    h960["groups"] = {t: w.height() for t, w in gs.items()}
    d.resize(1320, 1300)
    settle(15)
    cv = sc.widget()
    h1300 = dict(canvas_min=cv.minimumHeight(), canvas_max=cv.maximumHeight(),
                 page_sizehint=pg.sizeHint().height())
    gs = child_groups(pg)
    h1300["groups"] = {t: w.height() for t, w in gs.items()}
    return h960, h1300


h960, h1300 = snap_actor_heights()
print("[h960 ] 画布 min=%d max=%d page.sizeHint=%d 子模块=%s"
      % (h960["canvas_min"], h960["canvas_max"], h960["page_sizehint"],
         {t: h for t, h in h960["groups"].items()}))
print("[h1300] 画布 min=%d max=%d page.sizeHint=%d 子模块=%s"
      % (h1300["canvas_min"], h1300["canvas_max"], h1300["page_sizehint"],
         {t: h for t, h in h1300["groups"].items()}))

chk(h960["canvas_min"] == h1300["canvas_min"],
    "演员刮削画布高不随窗口变（960:%d == 1300:%d，多余高度落视口留白）"
    % (h960["canvas_min"], h1300["canvas_min"]))
# 内容不被切（锁高页面底部不裁）：画布最小高 >= 内容真实需求
need_actor = uis.SettingsDialog._content_need_height(pg)
chk(h960["canvas_min"] >= need_actor - 1,
    "演员刮削画布 %d >= 内容需求 %d（锁高不切底）"
    % (h960["canvas_min"], need_actor))
# 子模块高度一一恒定
chk(set(h960["groups"].keys()) == set(h1300["groups"].keys()),
    "演员刮削子模块集合一致（%s）" % " / ".join(h960["groups"].keys()))
all_same = all(h960["groups"].get(t) == h1300["groups"].get(t)
               for t in h960["groups"])
chk(all_same, "演员刮削各子模块高度在 960 / 1300 下一一恒定（不随窗口拉伸）")
for t in h960["groups"]:
    chk(h960["groups"][t] == h1300["groups"][t],
        "  子模块[%s] h=%d（960==1300）" % (t, h960["groups"][t]))

d.resize(1320, 960)
settle(12)

# ===== ④ 画像概览：无下滚轴（注入满量合成数据）=====
print()
print("=" * 72)
print("④ 画像概览 无下滚轴（注入满量合成数据）")
print("=" * 72)

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
chk(need <= vp,
    "画像概览内容需求 %d <= 视口高 %d → 无下滚轴" % (need, vp))
# 真实竖向滚动条应隐藏（内容放得下时画布 == 视口）
chk(not sc.verticalScrollBar().isVisible(),
    "画像概览竖向滚动条隐藏（内容已塞进一屏）")

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
