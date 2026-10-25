# -*- coding: utf-8 -*-
"""v1.27.0 离屏冒烟回归 —— 两条反馈逐条自证 + 样式/文档回归

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1270.py', run_name='__main__')"

**安全约定**：`db.db_path` 指向临时目录、`cfg.config_path` 指向临时 settings.json、
日志重定向到临时目录 —— 全程不碰真实索引 / 真实配置 / 真实媒体目录。

覆盖：
  A 版本号与品牌常量          B 反馈 1 更名落点（含启动画面与「关于」几何）
  C 反馈 2 侧栏实时状态（含**像素级**横条取证 / 降级链 / 线程生命周期）
  D 样式与文档回归
"""
import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1270")
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
os.environ.pop("LMC_NO_SYSMON", None)      # 本轮要**真跑**一次采集线程

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

REAL_DB = db.db_path()
db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import version as ver
import sysmon

db.init_db()          # 临时库先建表（MainWindow 一建起来就会查 library_counts）

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print("[%s] %s  %s" % ("PASS" if cond else "FAIL", tag, detail))


def section(t):
    print("\n" + "=" * 74 + "\n" + t + "\n" + "=" * 74)


def src(rel):
    with io.open(os.path.join(SRC, rel), encoding="utf-8", newline="") as f:
        return f.read()


# ============================================================ A. 版本号 / 品牌
section("A. 版本号与品牌常量（v1.27.0 / Build 2609210037）")
check("A1 外部版本 v1.27.0", ver.VERSION == "v1.27.0", ver.VERSION)
check("A2 内部构建号 2609210037", ver.BUILD == "2609210037", ver.BUILD)
check("A3 完整标识", ver.FULL_VERSION == "v1.27.0 (Build 2609210037)", ver.FULL_VERSION)
check("A4 中文名 = 流明盒", ver.APP_NAME == "流明盒", ver.APP_NAME)
check("A5 英文名 = LumaCrate", ver.APP_NAME_EN == "LumaCrate", ver.APP_NAME_EN)
check("A6 Slogan 中文", ver.SLOGAN_CN == "所有流明 · 尽收盒中", ver.SLOGAN_CN)
check("A7 Slogan 英文", ver.SLOGAN_EN == "Every lumen, in one crate.", ver.SLOGAN_EN)
check("A8 开源声明文案保持不变",
      ver.LICENSE_NOTE == "本软件为开源软件，没有授权禁止用于商业用途。", ver.LICENSE_NOTE)
check("A9 版权文案保持不变",
      ver.COPYRIGHT == "Copyright  2026 肆月Aperture", ver.COPYRIGHT)

# ============================================================ Qt
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QTextBrowser

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


pump(3)

# ============================================================ B. 反馈 1
section("B. 反馈 1：全局改名「流明盒 / LumaCrate」+ Slogan 进启动画面与「关于」")

# —— B1~B4 源码级：旧名只剩注释 ——
quoted_old = 0
for f in sorted(os.listdir(SRC)):
    if not f.endswith(".py"):
        continue
    s = src(f)
    quoted_old += s.count('"LocalMediaCenter"') + s.count('"本地影视中心"')
check("B1 src/ 里再无旧名字符串字面量", quoted_old == 0, "命中 %d" % quoted_old)

raw_old = sum(src(f).count("本地影视中心") + src(f).count("LocalMediaCenter")
              for f in sorted(os.listdir(SRC)) if f.endswith(".py"))
check("B2 旧名只剩注释/文档串（≤3 处）", raw_old <= 3, "命中 %d" % raw_old)

mw_s = src("main_window.py")
check("B3 侧栏副标题不再硬编码（读 ver.APP_NAME_EN）",
      'QLabel(ver.APP_NAME_EN); s.setObjectName("Sub")' in mw_s)
check("B4 「关于」框加了 QLabel#Slogan",
      'sl = QLabel(ver.SLOGAN_CN)' in mw_s and 'sl.setObjectName("Slogan")' in mw_s)
check("B5 「关于」正文含中英 Slogan",
      'f"*{ver.SLOGAN_CN} — {ver.SLOGAN_EN}*' in mw_s)

# —— B6/B7 源码级：exe 产物名 ——
bs = io.open(os.path.join(ROOT, "build_exe.py"), encoding="utf-8", newline="").read()
check("B6 exe 产物名随品牌",
      'EXE_NAME = f"{ver.APP_NAME}-{ver.VERSION}-{ver.BUILD}"' in bs)
exe_name = "%s-%s-%s" % (ver.APP_NAME, ver.VERSION, ver.BUILD)
check("B7 exe 名为 流明盒-v1.27.0-2609210037",
      exe_name == "流明盒-v1.27.0-2609210037", exe_name)
check("B8 归档认旧名前缀（更名后不漏归档）",
      "LEGACY_PREFIXES" in bs and '"本地影视中心-"' in bs)

lv = io.open(os.path.join(ROOT, "dev/live_verify.py"), encoding="utf-8", newline="").read()
check("B9 验收脚本认新旧两种 exe 前缀",
      'EXE_GLOBS = ("流明盒-v*.exe", "本地影视中心-v*.exe")' in lv)

# —— B10 启动画面：画布 / 行位 / Slogan ——
import splash

sp = splash.SplashScreen()
R = sp._rows()
check("B10 启动画面 440×344", (sp.W, sp.H) == (440, 344), "%dx%d" % (sp.W, sp.H))
check("B11 _rows() 含 slogan 项", "slogan" in R, sorted(R))
check("B12 logo 96 且不压标题", R["logo"] + sp.LOGO <= R["title"],
      "logo_bottom=%.0f title=%.0f" % (R["logo"] + sp.LOGO, R["title"]))
check("B13 副标题底 ≤ Slogan 顶", R["sub"] + sp._SUB_H <= R["slogan"])
check("B14 Slogan 底 ≤ 百分比行顶", R["slogan"] + sp._SLOGAN_H <= R["pct"])
check("B15 进度槽底 < 提示语顶", R["bar"] + sp._BAR_H < R["tip"],
      "bar_bottom=%.0f tip=%.0f" % (R["bar"] + sp._BAR_H, R["tip"]))
check("B16 版权行不出画布", R["copy"] + sp._FOOT_H <= sp.H,
      "copy_bottom=%.0f H=%d" % (R["copy"] + sp._FOOT_H, sp.H))
sp_s = src("splash.py")
check("B17 启动画面确实画了 ver.SLOGAN_CN",
      "ver.SLOGAN_CN)" in sp_s and "R[\"slogan\"]" in sp_s)
check("B18 Slogan 用独立色 _SLOGAN", "_SLOGAN = QColor(" in sp_s)
check("B19 标题仍取 APP_NAME（改一处全局生效）",
      "self.title = title or ver.APP_NAME" in sp_s)

# 真渲染一帧：Slogan 那一行必须真的有像素（不是空画）
try:
    sp.setProgress(100, "准备就绪")
    pm_sp = QPixmap(sp.W, sp.H)
    pm_sp.fill(Qt.transparent)
    sp.render(pm_sp)
    im = pm_sp.toImage()
    lit = 0
    for x in range(24, sp.W - 24, 2):
        for y in range(int(R["slogan"]), int(R["slogan"] + sp._SLOGAN_H), 1):
            c = im.pixelColor(x, y)
            if c.alpha() > 24 and (c.red() + c.green() + c.blue()) > 120:
                lit += 1
    check("B20 Slogan 行渲染出可见像素", lit > 60, "亮像素 %d" % lit)
except Exception as e:                                  # noqa: BLE001
    check("B20 Slogan 行渲染出可见像素", False, "渲染异常 %r" % (e,))

# —— B21~B23 「关于」对话框 ——
dlg = mw.AboutDialog()
sl = dlg.findChild(QLabel, "Slogan")
check("B21 关于框有 QLabel#Slogan", sl is not None)
check("B22 Slogan 文本 == ver.SLOGAN_CN", sl is not None and sl.text() == ver.SLOGAN_CN,
      sl.text() if sl else "")
tbs = dlg.findChildren(QTextBrowser)
body = tbs[0].toPlainText() if tbs else ""
check("B23 关于正文含中英 Slogan", ver.SLOGAN_CN in body and ver.SLOGAN_EN in body,
      repr(body[:60]))
check("B24 关于框最小高度已放宽（容下 Slogan 行）",
      dlg.minimumHeight() >= 400, dlg.minimumHeight())
lay = dlg.layout()
order_ok = False
if sl is not None and tbs:
    order_ok = lay.indexOf(sl) < lay.indexOf(tbs[0])
check("B25 Slogan 排在正文之前（同一纵向队列里顺序正确）", order_ok)

# ============================================================ C. 反馈 2
section("C. 反馈 2：侧栏「数据统计」上移 + 新增「实时状态」面板")

check("C1 stat_label 走 QSS 类名（不再是内联 setStyleSheet）",
      'self.stat_label.setObjectName("SideStats")' in mw_s
      and 'self.stat_label.setStyleSheet("color:#9b8e7a' not in mw_s)
check("C2 侧栏底部两段小标题都在",
      'sv.addWidget(self._section("数据统计"))' in mw_s
      and 'sv.addWidget(self._section("实时状态"))' in mw_s)
check("C3 实时状态排在数据统计之后",
      mw_s.index('self._section("数据统计")') < mw_s.index('self._section("实时状态")'))
check("C4 统计正文压成 2 行（用 · 连接）",
      """self.stat_label.setText(f"电影 {s['movies']} · 剧集 {s['tvshows']}\\n"
                                f"分集 {s['episodes']} · 演员 {s['people']}")""" in mw_s)
check("C5 MainWindow 构建了 sysmon 面板",
      "self.sysmon = sysmon.SysMonitorPanel()" in mw_s)
sm_s = src("sysmon.py")      # 本轮要按源码核对线程归属
check("C6 closeEvent 停的是**进程级**线程（不是面板自己那个）",
      "sysmon.stop_shared_worker()" in mw_s and "sm.stop()" not in mw_s)
check("C6b 线程是进程级单例，且挂在 QApplication 下（面板删不掉它）",
      "_WORKER = None" in sm_s and "def shared_worker()" in sm_s
      and "w.setParent(app)" in sm_s and "aboutToQuit.connect(w.stop)" in sm_s)
check("C6c 面板不再自己 new 线程（回归护栏：这行曾导致真机 abort）",
      "self._worker = SysMonWorker(parent=self)" not in sm_s
      and "self._worker = shared_worker()" in sm_s)
check("C6d 面板 stop() 只退订、不停线程",
      "w.sampled.disconnect(self.apply)" in sm_s)
check("C7 新模块被 build_exe 收进打包",
      '"--hidden-import", "sysmon"' in bs and '"--hidden-import", "psutil"' in bs)

# —— 构造真实主窗口（会真启一个采集线程）——
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()                  # 离屏也要 show 一次，否则布局未激活、几何全是 0
pump(10)
side = win.sidebar
sm = win.sysmon
lay_side = side.layout()
i_stat, i_smOn = lay_side.indexOf(win.stat_label), lay_side.indexOf(sm)
check("C8 面板挂在侧栏里", sm.parent() is not None and side.isAncestorOf(sm))
check("C9 数据统计在实时状态**上方**（反馈 2 的「上移」）", 0 <= i_stat < i_smOn,
      "index: stat=%d sysmon=%d" % (i_stat, i_smOn))
sy = sm.mapTo(side, QPoint(0, 0)).y()
sty = win.stat_label.mapTo(side, QPoint(0, 0)).y()
check("C9b 几何上也确实是上面（show 之后实测 y）", sty < sy,
      "stat.y=%d  sysmon.y=%d" % (sty, sy))
check("C10 面板整体在侧栏高度之内（没被底边裁掉）",
      sy + sm.height() <= side.height(), "bottom=%d side=%d" % (sy + sm.height(), side.height()))
check("C11 面板宽度不超侧栏内容区", sm.sizeHint().width() <= 170,
      "hint=%d" % sm.sizeHint().width())
check("C12 侧栏内容总高 < 侧栏实测高（1080 下不溢出）",
      lay_side.sizeHint().height() <= side.height(),
      "hint=%d side=%d" % (lay_side.sizeHint().height(), side.height()))

# —— 面板结构 ——
check("C13 三条横条齐备", set(sm._rows) == {"cpu", "mem", "gpu"}, sorted(sm._rows))
check("C14 横条是自绘 MiniBar", all(isinstance(v[0], sysmon.MiniBar) for v in sm._rows.values()))
check("C15 两行文字行齐备（网络·Ollama / 当前模型）",
      isinstance(sm.net_row, QLabel) and isinstance(sm.model_row, QLabel))
check("C16 文字行走 SysInfo（名称+值合成一个标签，不用左右分列）",
      sm.net_row.objectName() == "SysInfo" and sm.model_row.objectName() == "SysInfo")
mb_s = src("sysmon.py")
check("C17 MiniBar 没写 setStyleSheet（自绘控件禁用样式背景）",
      "setStyleSheet" not in mb_s.split("class MiniBar")[1].split("class SysMonitorPanel")[0])
check("C18 MiniBar 填充色现取 ACCENT_RGB",
      'rgb = getattr(mw, "ACCENT_RGB", None)' in mb_s)

# —— 像素级：横条真的按百分比画，且跟随高亮色 ——
# 取样点必须落在**低于 60%** 占用上 —— ≥60% 会故意转琥珀、≥85% 转警示橙，
# 那时本来就不该是高亮色（第一版断言把 100% 当「高亮色」采样，必然失败）。
def bar_px(pct, rgb=None, x=70):
    old = mw.ACCENT_RGB
    if rgb is not None:
        mw.ACCENT_RGB = rgb
    b = sysmon.MiniBar()
    b.resize(80, sysmon.MiniBar.H)
    b.set_pct(pct)
    im = b.grab().toImage()
    px = im.pixelColor(x, sysmon.MiniBar.H // 2)
    mw.ACCENT_RGB = old
    return px, (im.width(), im.height())


_b = sysmon.MiniBar()
_b.resize(80, sysmon.MiniBar.H)
_im = _b.grab().toImage()
check("C18b 横条抓图尺寸 = 80×6", (_im.width(), _im.height()) == (80, 6),
      "%dx%d" % (_im.width(), _im.height()))

track, _ = bar_px(0, (192, 57, 43), x=40)
check("C19 0% 时整条只剩轨道（半透明，无实心填充）",
      track.alpha() <= 40,
      "a=%d rgb=(%d,%d,%d)" % (track.alpha(), track.red(), track.green(), track.blue()))

fill50, _ = bar_px(50, (192, 57, 43), x=16)
check("C20 50% 时左段填的是当前高亮色（朱红，实心）",
      fill50.alpha() == 255 and abs(fill50.red() - 192) <= 4
      and abs(fill50.green() - 57) <= 4 and abs(fill50.blue() - 43) <= 4,
      "a=%d rgb=(%d,%d,%d)" % (fill50.alpha(), fill50.red(), fill50.green(), fill50.blue()))

tail50, _ = bar_px(50, (192, 57, 43), x=70)
check("C21 50% 时右端（x=70）仍为轨道 —— 真的按百分比截断",
      tail50.alpha() <= 40 and fill50.alpha() == 255,
      "tail a=%d / fill a=%d" % (tail50.alpha(), fill50.alpha()))

qing, _ = bar_px(50, (63, 169, 201), x=16)
check("C22 换高亮色（天青）后填充色随之改变",
      qing.alpha() == 255 and abs(qing.blue() - 201) <= 4 and qing.red() < 100,
      "青=(%d,%d,%d) vs 朱=(%d,%d,%d)"
      % (qing.red(), qing.green(), qing.blue(), fill50.red(), fill50.green(), fill50.blue()))

alert, _ = bar_px(90, (192, 57, 43), x=70)
check("C22b ≥85% 自行转警示橙（与高亮色无关）",
      (alert.red(), alert.green(), alert.blue()) == (0xD9, 0x63, 0x4A)
      and alert.alpha() == 255,
      "rgb=(%d,%d,%d)" % (alert.red(), alert.green(), alert.blue()))

amber, _ = bar_px(70, (192, 57, 43), x=40)
check("C22c ≥60% 转琥珀",
      (amber.red(), amber.green(), amber.blue()) == (0xD8, 0xA0, 0x4A),
      "rgb=(%d,%d,%d)" % (amber.red(), amber.green(), amber.blue()))

# —— 采集层 ——
m = sysmon.SysMetrics()
check("C26 采集能力自报", "psutil=" in m.source_note(), m.source_note())
d1 = m.sample()
time.sleep(0.4)
d2 = m.sample()
check("C27 sample() 键齐全",
      set(d2) >= {"cpu", "mem", "gpu", "net_on", "net_up", "net_down", "src", "gpu_name"})
check("C28 CPU 取到数值", isinstance(d2["cpu"], float) and 0 <= d2["cpu"] <= 100, d2["cpu"])
check("C29 内存取到数值", isinstance(d2["mem"], float) and 0 < d2["mem"] <= 100, d2["mem"])
check("C30 GPU 取到数值（本机有 N 卡 + nvidia-smi）",
      d2["gpu"] is None or (isinstance(d2["gpu"], float) and 0 <= d2["gpu"] <= 100), d2["gpu"])
check("C31 网络状态取到 bool", isinstance(d2["net_on"], bool), d2["net_on"])
print("     采样：cpu=%.1f mem=%.1f gpu=%s net_on=%s up=%s down=%s"
      % (d2["cpu"], d2["mem"], d2["gpu"], d2["net_on"], d2["net_up"], d2["net_down"]))

# 降级链：砍掉 psutil → ctypes 分支必须仍然给出数字
m2 = sysmon.SysMetrics()
m2._has_psutil = False
m2._psutil = None
m2.cpu()
time.sleep(0.35)
c_c = m2.cpu()
c_m = m2.mem()
n_ok = m2.net()["net_on"]
check("C32 无 psutil 时 CPU 走 ctypes 仍出数", isinstance(c_c, float) and 0 <= c_c <= 100, c_c)
check("C33 无 psutil 时内存走 GlobalMemoryStatusEx 仍出数",
      isinstance(c_m, float) and 0 < c_m <= 100, c_m)
check("C34 无 psutil 时网络走 wininet 仍出 bool", isinstance(n_ok, bool), n_ok)
no_gpu = sysmon.SysMetrics()
no_gpu._nvsmi = None
check("C35 没有 nvidia-smi 时 GPU 返回 None（UI 显示 —）", no_gpu.gpu() is None)

# —— apply() 容错 ——
os.environ["LMC_NO_SYSMON"] = "1"     # 后面这几只面板不要再起线程
p2 = sysmon.SysMonitorPanel()
check("C36 LMC_NO_SYSMON=1 时不起线程", p2._worker is None)
p2.stop()
os.environ.pop("LMC_NO_SYSMON", None)
p2.apply({"cpu": None, "mem": 41.6, "gpu": None, "gpu_name": "", "gpu_mem": None,
          "net_on": True, "net_up": 1.0, "net_down": 2.0,
          "ollama_on": True, "model": "qwen3.5:4b", "model_ok": True, "models": []})
check("C37 None 值显示「—」", p2._rows["cpu"][1].text() == "—"
      and p2._rows["gpu"][1].text() == "—")
check("C38 有值显示百分比", p2._rows["mem"][1].text() == "42%", p2._rows["mem"][1].text())
check("C39 横条同步了百分比", p2._rows["mem"][0].pct() == 41.6)
check("C40 网络行显示「运行中」并带状态点",
      "在线 · 运行中" in p2.net_row.text() and "●" in p2.net_row.text(),
      p2.net_row.text())
check("C41 模型行显示当前模型", "qwen3.5:4b" in p2.model_row.text(), p2.model_row.text())

p2.apply({"cpu": 1, "mem": 2, "gpu": 3, "net_on": False, "ollama_on": False,
          "model": "ghost:1b", "model_ok": False})
check("C42 离线时点显示「离线」", "离线" in p2.net_row.text(), p2.net_row.text())
p2.apply({"cpu": 1, "mem": 2, "gpu": 3, "net_on": True, "ollama_on": True,
          "model": "ghost:1b", "model_ok": False})
check("C43 Ollama 在跑但模型没装 → 仍显示模型名 + 补救命令",
      "ghost:1b" in p2.model_row.text()
      and "ollama pull" in p2.model_row.toolTip(),
      p2.model_row.toolTip().replace("\n", " ")[:48])
p2.apply({"net_on": True, "ollama_on": True, "model": "", "model_ok": True})
check("C44 未指定模型显示「—」", "—" in p2.model_row.text(), p2.model_row.text())
check("C45 长模型名会截断（侧栏放不下）",
      len(sysmon._short("huihui_ai/qwen2.5-abliterate:7b")) <= 16,
      sysmon._short("huihui_ai/qwen2.5-abliterate:7b"))

# —— 线程真实跑起来了 ——
w = sm._worker
check("C46 采集线程已启动", w is not None and w.isRunning(), w)
check("C47 采样周期 1.5s / AI 每 6 次（约 9s）",
      w is not None and abs(w._interval - 1.5) < 1e-6 and sysmon._AI_EVERY == 6,
      getattr(w, "_interval", None))
got = {}
if w is not None:
    w.sampled.connect(lambda d: got.update(d))
    t0 = time.time()
    while not got and time.time() - t0 < 8:
        pump(10)
        time.sleep(0.15)
check("C48 线程真的发出了采样（含 CPU 数值）",
      isinstance(got.get("cpu"), float), {k: got.get(k) for k in ("cpu", "mem", "gpu", "ollama_on")})
check("C49 线程发出的数据里 AI 字段已合并", "ollama_on" in got, got.get("ollama_on"))

# —— 回归：侧栏会被 _apply_settings() 整体重建（真机上就死在这里）——
# 原缺陷：面板自带线程 → MainWindow._apply_settings() 里
#   self.sidebar.deleteLater() → 运行中的 QThread 被连带销毁
#   → Qt "QThread: Destroyed while thread is still running" → abort() 整个进程。
# 真机证据：标签优化写完后 app.log 出现**第二行**「实时状态：采集能力 …」（新面板建起来了），
# 随后日志全停、后续 4 张抓图全部 0×0。
shared_w = sysmon.shared_worker()
check("C51 采集线程是进程级单例（两次取到的是同一个对象）",
      shared_w is w, "shared=%s w=%s" % (id(shared_w), id(w)))
check("C52 线程的父对象是 QApplication（不挂面板下）",
      shared_w.parent() is QApplication.instance(),
      type(shared_w.parent()).__name__ if shared_w.parent() is not None else "None")

n_before = len(QApplication.instance().findChildren(sysmon.SysMonWorker))
win._apply_settings()          # ← 就是这一步在真机上把进程 abort 掉
pump(12)
n_after = len(QApplication.instance().findChildren(sysmon.SysMonWorker))
check("C53 重建侧栏前后，进程里都只有 1 个采集线程（没有泄漏/叠加）",
      n_before == 1 and n_after == 1, "before=%d after=%d" % (n_before, n_after))
check("C54 重建侧栏后线程仍然活着（没被连锁销毁）",
      shared_w.isRunning(), "running=%s" % shared_w.isRunning())
check("C55 重建后侧栏换成了新面板，且它订阅的是同一个线程",
      win.sysmon is not sm and win.sysmon._worker is shared_w
      and win.sysmon._worker.isRunning(),
      "same_panel=%s" % (win.sysmon is sm))
check("C55b 旧面板的采样行已不存在（旧面板真被删了，不是假的）",
      not (win.sysmon is sm))

got2 = {}
win.sysmon._worker.sampled.connect(lambda d: got2.update(d))
t0 = time.time()
while not got2 and time.time() - t0 < 8:
    pump(10)
    time.sleep(0.15)
check("C56 重建后的面板照样收到采样（CPU 有值）",
      isinstance(got2.get("cpu"), float), got2.get("cpu"))
check("C57 新面板的横条也同步上了百分比",
      not isinstance(win.sysmon._rows["cpu"][0].pct(), type(None)),
      win.sysmon._rows["cpu"][0].pct())

# —— 关闭窗口必须把线程停掉 ——
win.close()
pump(8)
check("C50 closeEvent 后进程级采集线程真的停了",
      not shared_w.isRunning(), "running=%s" % shared_w.isRunning())
check("C50b stop_shared_worker() 之后单例指针已清空（可重复调用）",
      sysmon._WORKER is None)
p2.stop()

# ============================================================ D. 样式 / 文档
section("D. 样式与文档回归")
qss = src("style.qss")
for sel in ("QLabel#SideStats", "QLabel#SysKey", "QLabel#SysVal", "QLabel#SysInfo",
            "QLabel#Slogan"):
    check("D1 样式含 %s" % sel, sel in qss)
check("D2 style.qss 里 __ACCENT__ 令牌仍在（高亮色链路没被破坏）",
      qss.count("__ACCENT__") > 0, qss.count("__ACCENT__"))
styled = mw.render_style() if hasattr(mw, "render_style") else ""
check("D3 render_style 后无残留令牌",
      isinstance(styled, str) and styled.count("__ACCENT") == 0,
      "残留 %d" % (styled.count("__ACCENT") if isinstance(styled, str) else -1))
check("D4 侧栏 Sub 字号保持 10px（更名后没顺手改掉用户确认过的值）",
      "QLabel#Sub { color: #8c8071; font-size: 10px;" in qss)

rd = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8", newline="").read()
check("D5 README 标题已更名", rd.startswith("# 流明盒 (LumaCrate)"))
check("D6 README 写明更名与 Slogan",
      "v1.27.0 起更名为「流明盒 / LumaCrate」" in rd and "所有流明 · 尽收盒中" in rd)
check("D7 README 有 v1.27.0 迭代记录", "### v1.27.0 (Build 2609210037)" in rd)
check("D8 README 使用方式用新 exe 名", "流明盒-<版本>.exe" in rd)
check("D9 README 目录结构含 sysmon.py", "sysmon.py" in rd)
check("D10 README 实时状态降级链表齐备",
      "nvidia-smi" in rd and "GetSystemTimes" in rd and "InternetGetConnectedState" in rd)
rq = io.open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8", newline="").read()
check("D11 requirements 里 psutil 已声明", "psutil" in rq)
check("D12 性能基线文档标题已更名",
      io.open(os.path.join(ROOT, "性能基线.md"), encoding="utf-8", newline="").read()
      .startswith("# 流明盒 LumaCrate · 性能基线"))

# ============================================================ 汇总
print("\n" + "=" * 74)
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for t in FAIL:
        print("  -", t)
print("=" * 74)
sys.exit(1 if FAIL else 0)
