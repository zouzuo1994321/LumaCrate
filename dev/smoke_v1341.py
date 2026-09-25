# -*- coding: utf-8 -*-
"""v1.34.1 离屏冒烟：三条 UI 重叠 / 高度缺陷的**硬断言**（加载真实 QSS）。

断言分组：
  P  版本号 / 常量口径
  Q  SpinBox 宽度口径（不许小于 minimumSizeHint —— 就是「重叠」的根因）
  R  AutoFillDialog 高度自适应 + 切范围零跳变
  S  智能推荐工具行几何（引导权重框宽度 / 相邻不重叠 / 不超容器）
  T  文档同步（README 中英文都写了 v1.34.1 / 2609250048 / 修复说明）

跑法：
  python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1341.py', run_name='__main__')"
"""
import io
import json
import os
import sys

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_smoke_v1341.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1310"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QTimer                            # noqa: E402
from PySide6.QtGui import QFontDatabase, QFont                   # noqa: E402
from PySide6.QtWidgets import (QApplication, QAbstractSpinBox,   # noqa: E402
                               QWidget, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

app = QApplication(sys.argv)
for f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.isfile(f):
        QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei UI", 9))

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print(" [%s] %s  %s" % ("PASS" if cond else "FAIL", tag, detail), flush=True)


def sec(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0
    ix = min(ax + aw, bx + bw) - max(ax, bx)
    iy = min(ay + ah, by + bh) - max(ay, by)
    return max(0, ix) * max(0, iy)


import main_window as mw                                        # noqa: E402
mw.load_style(app)
import config as cfg                                            # noqa: E402
import version as ver                                           # noqa: E402
import ui_settings as uis                                       # noqa: E402


# ============================ P 版本 / 常量 ============================
sec("P 版本号与常量口径")
check("P1 外部版本号是 v1.34.1", ver.VERSION == "v1.34.1", ver.VERSION)
check("P2 内部构建号是 2609250048", ver.BUILD == "2609250048", ver.BUILD)
check("P3 MAJOR_ITER=34 / MINOR_ITER=1（小版本迭代 → 第三位 +1）",
      ver.MAJOR_ITER == 34 and ver.MINOR_ITER == 1,
      "%s.%s" % (ver.MAJOR_ITER, ver.MINOR_ITER))
check("P4 config.SPIN_MIN_W 存在且 >= 120", getattr(cfg, "SPIN_MIN_W", 0) >= 120,
      str(getattr(cfg, "SPIN_MIN_W", None)))
check("P5 SPIN_MAX_W > SPIN_MIN_W",
      getattr(cfg, "SPIN_MAX_W", 0) > getattr(cfg, "SPIN_MIN_W", 0),
      "%s > %s" % (getattr(cfg, "SPIN_MAX_W", None), getattr(cfg, "SPIN_MIN_W", None)))

# ============================ Q SpinBox 宽度口径 ============================
sec("Q SpinBox 宽度口径（小于 minimumSizeHint = 数字被挤 = 重叠）")
dlg = uis.AutoFillDialog()
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.show()
for _ in range(3):
    app.processEvents()

bad = []
for sp in dlg.findChildren(QAbstractSpinBox):
    need_w = sp.minimumSizeHint().width()
    need_h = sp.minimumSizeHint().height()
    if sp.width() < need_w or sp.height() < need_h:
        bad.append((type(sp).__name__, sp.width(), need_w, sp.height(), need_h))
check("Q1 自动填充面板 10 个 SpinBox 全部 >= 自身 minimumSizeHint（宽与高）",
      not bad, "越界 %d 个 %s" % (len(bad), bad[:3]))
check("Q2 自动填充面板 SpinBox 数量 = 10（5 维度 × 前N/权重）",
      len(dlg.findChildren(QAbstractSpinBox)) == 10,
      str(len(dlg.findChildren(QAbstractSpinBox))))
wd = [sp.width() for sp in dlg.findChildren(QAbstractSpinBox)]
check("Q3 自动填充面板 SpinBox 宽度都 = cfg.SPIN_MIN_W（未被压窄）",
      all(w == cfg.SPIN_MIN_W for w in wd), str(sorted(set(wd))))

# ============================ R AutoFillDialog 高度 ============================
sec("R AutoFillDialog 高度自适应 + 切统计范围零跳变")
check("R1 对话框高度 >= 自身 minimumSizeHint（不再被写死的 560 压缩）",
      dlg.height() >= dlg.minimumSizeHint().height(),
      "h=%d minH=%d" % (dlg.height(), dlg.minimumSizeHint().height()))

sig = []
for i in range(dlg.cb_scope.count()):
    dlg.cb_scope.setCurrentIndex(i)
    for _ in range(4):
        app.processEvents()
    g1 = dlg.cb_scope.parent()
    g2 = dlg.dim_rows["tag"][1].parent()
    note = None
    for lb in dlg.findChildren(QLabel):
        if lb.text().startswith("权重含义"):
            note = lb
            break
    sig.append({"i": i, "dlg_h": dlg.height(),
                "g1_y": g1.y(), "g1_h": g1.height(),
                "g2_y": g2.y(), "g2_h": g2.height(),
                "note_y": note.y() if note else -1,
                "est_y": dlg.lb_est.y()})
    print("   scope[%d] %s" % (i, sig[-1]), flush=True)

check("R2 切换统计范围时**对话框高度零跳变**",
      len(set(s["dlg_h"] for s in sig)) == 1,
      str([s["dlg_h"] for s in sig]))
check("R3 切换统计范围时**维度框 y 零跳变**",
      len(set(s["g2_y"] for s in sig)) == 1, str([s["g2_y"] for s in sig]))
check("R4 切换统计范围时**说明块 y 零跳变**",
      len(set(s["note_y"] for s in sig)) == 1, str([s["note_y"] for s in sig]))
check("R5 切换统计范围时**统计行 y 零跳变**",
      len(set(s["est_y"] for s in sig)) == 1, str([s["est_y"] for s in sig]))

# 重叠判定：维度框 / 说明块 / 统计行 两两不相交
dlg.cb_scope.setCurrentIndex(1)
for _ in range(4):
    app.processEvents()
g2 = dlg.dim_rows["tag"][1].parent()
note = [lb for lb in dlg.findChildren(QLabel)
        if lb.text().startswith("权重含义")][0]
a = (g2.x(), g2.y(), g2.width(), g2.height())
b = (note.x(), note.y(), note.width(), note.height())
c = (dlg.lb_est.x(), dlg.lb_est.y(), dlg.lb_est.width(), dlg.lb_est.height())
check("R6 「我的收藏」下 维度框 ∩ 说明块 = 0",
      rects_overlap(a, b) == 0, "%d px²" % rects_overlap(a, b))
check("R7 「我的收藏」下 说明块 ∩ 统计行 = 0",
      rects_overlap(b, c) == 0, "%d px²" % rects_overlap(b, c))
check("R8 「我的收藏」下 维度框 ∩ 统计行 = 0",
      rects_overlap(a, c) == 0, "%d px²" % rects_overlap(a, c))
check("R9 lb_scope_tip 锁了恒定两行高（三种范围都不变）",
      dlg.lb_scope_tip.minimumHeight() >=
      dlg.lb_scope_tip.fontMetrics().lineSpacing() * 2,
      "minH=%d lineSpacing=%d" % (dlg.lb_scope_tip.minimumHeight(),
                                  dlg.lb_scope_tip.fontMetrics().lineSpacing()))
dlg.close()

# ============================ S 智能推荐工具行 ============================
sec("S 智能推荐工具行（引导向量）几何")
win = mw.MainWindow()
win.resize(1920, 1080)
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.show()
for _ in range(4):
    app.processEvents()

w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
ph = QLabel("占位"); ph.setFixedHeight(400); v.addWidget(ph)
tb = QWidget(); tbl = QHBoxLayout(tb)
tbl.setContentsMargins(0, 0, 0, 0); tbl.setSpacing(8)
info = QLabel("<b>AI 智能算法（本地 Ollama 扩词）</b> · 依据 381 部收藏影片"
              "（23038 部高分） + 143 位收藏的演员/导演 · 候选 47,571 部")
info.setStyleSheet("color:#c9bda7;font-size:12px;")
info.setMinimumWidth(0)
tbl.addWidget(info, 1)
win._smart_guides = []
win._guide_bar(tbl)
win._refresh_guides()
again = QPushButton("换一批"); again.setObjectName("Ghost")
tbl.addWidget(again)
v.insertWidget(0, tb)

page = win._page("智能推荐（24 部）", w)
page.resize(1734, 1007)
page.setAttribute(Qt.WA_DontShowOnScreen, True)
page.show()
for _ in range(6):
    app.processEvents()

gw = win.guide_w
check("S1 引导权重框宽度 = cfg.SPIN_MIN_W（旧值是 72 → 就是「挤在一起」的根因）",
      gw.width() == cfg.SPIN_MIN_W, "w=%d 期望=%d" % (gw.width(), cfg.SPIN_MIN_W))
check("S2 引导权重框宽度 >= 自身 minimumSizeHint",
      gw.width() >= gw.minimumSizeHint().width(),
      "%d >= %d" % (gw.width(), gw.minimumSizeHint().width()))
check("S3 引导权重框已不再用 setFixedWidth（min/max 分开设）",
      gw.minimumWidth() == cfg.SPIN_MIN_W and gw.maximumWidth() == cfg.SPIN_MAX_W,
      "min=%d max=%d" % (gw.minimumWidth(), gw.maximumWidth()))

rows = sorted([c for c in tb.findChildren(QWidget)
               if c.parent() is tb and c.isVisible()], key=lambda c: c.x())
worst = 0
worst_pair = None
prev = None
for c in rows:
    if prev is not None:
        ov = rects_overlap(
            (prev.x(), prev.y(), prev.width(), prev.height()),
            (c.x(), c.y(), c.width(), c.height()))
        if ov > worst:
            worst, worst_pair = ov, (type(prev).__name__, type(c).__name__)
    prev = c
check("S4 工具行内相邻控件零重叠", worst == 0,
      "worst=%d px² %s" % (worst, worst_pair))

over = [c for c in rows if c.y() + c.height() > tb.height() + 1 or c.y() < -1]
check("S5 工具行内控件不超出工具行（无裁切）", not over,
      "超出 %d 个" % len(over))
check("S6 引导权重框与「加强」按钮间距 > 0（不再挤在一起）",
      min([c for c in rows if isinstance(c, QPushButton) and c.text() == "加强"],
          key=lambda c: c.x()).x() - (gw.x() + gw.width()) > 0,
      "间距 = %d" % (min([c for c in rows if isinstance(c, QPushButton)
                          and c.text() == "加强"], key=lambda c: c.x()).x()
                     - (gw.x() + gw.width())))
page.close(); win.close()

# ============================ T 文档同步 ============================
sec("T 文档同步（中英文 README）")
rp = os.path.join(ROOT, "README.md")
ep = os.path.join(ROOT, "README_EN.md")
rmd = io.open(rp, encoding="utf-8").read()
emd = io.open(ep, encoding="utf-8").read()
check("T1 中文 README 徽章 version = v1.34.1",
      "badge/version-v1.34.1-" in rmd)
check("T2 中文 README 徽章 build = 2609250048",
      "badge/build-2609250048-" in rmd)
check("T3 中文 README 有 v1.34.1 迭代记录标题",
      "### v1.34.1 (Build 2609250048)" in rmd)
check("T4 中文 README 下载名写的是 v1.34.1",
      "流明盒-v1.34.1-<构建号>.exe" in rmd)
check("T5 英文 README 徽章 version = v1.34.1",
      "badge/version-v1.34.1-" in emd)
check("T6 英文 README 徽章 build = 2609250048",
      "badge/build-2609250048-" in emd)
check("T7 英文 README changelog 有 v1.34.1 条目",
      "**v1.34.1** (2026-09-25)" in emd)
check("T8 英文 README 下载名写的是 v1.34.1",
      "流明盒-v1.34.1-<build>.exe" in emd)
check("T9 中文 README 说明了 SPIN_MIN_W 口径（含根因）",
      "SPIN_MIN_W" in rmd and "minimumSizeHint" in rmd)
check("T10 英文 README 说明了同一根因（minimumSizeHint）",
      "minimumSizeHint" in emd)
check("T11 中文 README 记录了回归探针 overlap_v1341.py",
      "overlap_v1341.py" in rmd)
check("T12 英文 README 记录了回归探针 overlap_v1341.py",
      "overlap_v1341.py" in emd)
check("T13 中文 README 旧版 v1.34.0 迭代记录仍在（不删历史）",
      "### v1.34.0 (Build 2609240047)" in rmd)

print("\n" + "=" * 74)
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
for f in FAIL:
    print("  -", f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
