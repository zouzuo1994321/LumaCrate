# -*- coding: utf-8 -*-
"""v1.34.1 修复前/后 通用诊断：**加载真实 QSS** 后逐控件量「内容溢出」。

判据（硬）：
  A. SpinBox：控件实际高 vs QSS 声明的 height（或 sizeHint）—— 实际 < 期望 = 被压缩裁切。
  B. 同一布局里任意两个控件的矩形**相交** = 重叠。
  C. 子控件 y + h 超出父容器高度 = 被容器裁掉。

用法（改代码前后各跑一次，对比输出）：
  python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/_scratch/overlap_v1341.py', run_name='__main__')"
"""
import io
import os
import sys

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_overlap_v1341.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1310"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt                                    # noqa: E402
from PySide6.QtGui import QFontDatabase, QFont                   # noqa: E402
from PySide6.QtWidgets import (QApplication, QAbstractSpinBox, QLabel,  # noqa: E402
                               QPushButton, QWidget, QHBoxLayout)

app = QApplication(sys.argv)
for f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.isfile(f):
        QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei UI", 9))

import main_window as mw                                        # noqa: E402
mw.load_style(app)             # ★ 关键：加载真实 QSS（含 padding）

FONT_H = app.fontMetrics().height()
print("字体行高 =", FONT_H)
print("=" * 80)

ISSUES = []


def rect_of(wdg):
    return (wdg.x(), wdg.y(), wdg.width(), wdg.height())


def rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return False
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def check_spins(root, tag):
    """★ 核心判据（v1.34.1）：SpinBox 实际宽**必须 >= Qt 自己算的 minimumSizeHint**。
    小于它 = 数字与箭头被挤进一格 → 数字贴边/右侧裁切，就是用户反馈的「重叠」。"""
    print("---- [%s] SpinBox 宽度 vs minimumSizeHint（<它就会挤出重叠）----" % tag)
    bad = 0
    for sp in root.findChildren(QAbstractSpinBox):
        need = sp.minimumSizeHint().width()
        got = sp.width()
        h_need = sp.minimumSizeHint().height()
        h_got = sp.height()
        ok = got >= need and h_got >= h_need
        if not ok:
            bad += 1
        print("   %-14s 宽 %3d / 需 %3d %s   高 %3d / 需 %3d %s"
              % (type(sp).__name__, got, need, "OK" if got >= need else "❌压窄",
                 h_got, h_need, "OK" if h_got >= h_need else "❌压矮"))
    if bad:
        ISSUES.append("[%s] %d 个 SpinBox 被压得小于 minimumSizeHint" % (tag, bad))
    return bad


def check_overlap_in(widget, tag, min_area=4):
    """同父下可见子控件两两相交检测（只比同层，避免误报）。"""
    print("---- [%s] 同层控件相交检测 ----" % tag)
    kids = [c for c in widget.findChildren(QWidget)
            if c.parent() is widget and c.isVisible()
            and c.width() > 0 and c.height() > 0]
    bad = []
    for i in range(len(kids)):
        for j in range(i + 1, len(kids)):
            a, b = rect_of(kids[i]), rect_of(kids[j])
            if rects_overlap(a, b):
                ix = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
                iy = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
                if ix * iy >= min_area:
                    bad.append((kids[i], a, kids[j], b, ix * iy))
    for w1, a, w2, b, area in bad[:12]:
        print("   ❌ %s%s %s 与 %s%s %s 重叠 %dpx²"
              % (type(w1).__name__, "", a, type(w2).__name__, "", b, area))
    if not bad:
        print("   （无相交）")
    else:
        ISSUES.append("[%s] %d 对同层控件相交" % (tag, len(bad)))
    return len(bad)


def check_clip(container, tag):
    """子控件是否超出容器高度。"""
    print("---- [%s] 子控件是否被容器裁切 ----" % tag)
    H = container.height()
    over = []
    for c in container.findChildren(QWidget):
        if not c.isVisible() or c.height() <= 0:
            continue
        bot = c.y() + c.height()
        if bot > H + 1:
            over.append((type(c).__name__, rect_of(c), bot - H))
    for t, r, d in over[:12]:
        print("   ❌ %s %s 底边超出容器 %dpx（容器高 %d）" % (t, r, d, H))
    if not over:
        print("   （无裁切，容器高 %d）" % H)
    else:
        ISSUES.append("[%s] %d 个子控件被裁" % (tag, len(over)))
    return len(over)


# ============================ ① ② AutoFillDialog ============================
import ui_settings as uis                                       # noqa: E402

print()
print("#" * 80)
print("# ①② AutoFillDialog（从画像自动填充 · 参数）")
print("#" * 80)
dlg = uis.AutoFillDialog()
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.show()
app.processEvents()

print("dialog %dx%d  sizeHint %dx%d  minimumSizeHint %dx%d"
      % (dlg.width(), dlg.height(), dlg.sizeHint().width(), dlg.sizeHint().height(),
         dlg.minimumSizeHint().width(), dlg.minimumSizeHint().height()))
check_spins(dlg, "AutoFillDialog")

# 每个范围都量一遍：高度是否跳变 + 是否重叠
print()
print("---- [AutoFillDialog] 逐统计范围：对话框高 / 说明块 y / 是否重叠 ----")
heights = []
for i in range(dlg.cb_scope.count()):
    dlg.cb_scope.setCurrentIndex(i)
    for _ in range(3):
        app.processEvents()
    h = dlg.height()
    heights.append(h)
    g1 = dlg.cb_scope.parent()
    g2 = dlg.dim_rows["tag"][1].parent()
    note = None
    for lb in dlg.findChildren(QLabel):
        if lb.text().startswith("权重含义"): 
            note = lb
            break
    print(" scope[%d] %-24r dialogH=%3d  范围框:y=%3d h=%3d  维度框:y=%3d h=%3d  "
          "说明块:y=%3d h=%3d  估计行:y=%3d h=%3d"
          % (i, dlg.cb_scope.currentText()[:22], h,
             g1.y(), g1.height(), g2.y(), g2.height(),
             note.y() if note else -1, note.height() if note else -1,
             dlg.lb_est.y(), dlg.lb_est.height()))
    # 维度框 与 说明块 是否相交
    if note is not None:
        a = (g2.x(), g2.y(), g2.width(), g2.height())
        b = (note.x(), note.y(), note.width(), note.height())
        if rects_overlap(a, b):
            print("      ❌ 维度框与说明块相交！")
            ISSUES.append("[AutoFillDialog scope=%d] 维度框∩说明块" % i)
    # 说明块 与 估计行 是否相交
    a = (note.x(), note.y(), note.width(), note.height()) if note else None
    b = (dlg.lb_est.x(), dlg.lb_est.y(), dlg.lb_est.width(), dlg.lb_est.height())
    if a and rects_overlap(a, b):
        print("      ❌ 说明块与估计行相交！")
        ISSUES.append("[AutoFillDialog scope=%d] 说明块∩估计行" % i)

print()
print(" 对话框高度序列 =", heights, " 极差 =", max(heights) - min(heights))
if max(heights) - min(heights) > 12:
    ISSUES.append("[AutoFillDialog] 切范围时对话框高度跳变 %dpx"
                  % (max(heights) - min(heights)))
# v1.34.1 新判据：说明块 / 估计行 / 维度框 的 y 在**所有范围下都不得移动**
pos_sig = []
for i in range(dlg.cb_scope.count()):
    dlg.cb_scope.setCurrentIndex(i)
    for _ in range(3):
        app.processEvents()
    g2 = dlg.dim_rows["tag"][1].parent()
    note = None
    for lb in dlg.findChildren(QLabel):
        if lb.text().startswith("权重含义"):
            note = lb
            break
    pos_sig.append((g2.y(), g2.height(),
                    note.y() if note else -1,
                    dlg.lb_est.y(), dlg.lb_est.height()))
print(" 各范围下 (维度框y, 维度框h, 说明块y, 估计行y, 估计行h) =")
for i, s in enumerate(pos_sig):
    print("   scope[%d] %s" % (i, s))
jumps = [abs(pos_sig[i][k] - pos_sig[0][k])
         for i in range(len(pos_sig)) for k in range(len(pos_sig[0]))]
print(" → 最大位置跳变量 =", max(jumps) if jumps else 0, "px")
if max(jumps) > 2:
    ISSUES.append("[AutoFillDialog] 切范围时下半部分区块位置跳动 %dpx" % max(jumps))
check_spins(dlg, "AutoFillDialog")
check_clip(dlg, "AutoFillDialog")

# ============================ ③ 智能推荐工具行 ==============================
print()
print("#" * 80)
print("# ③ 智能推荐工具行（引导向量行）")
print("#" * 80)
win = mw.MainWindow()
win.resize(1920, 1080)
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.show()
app.processEvents()

tb = QWidget()
tbl = QHBoxLayout(tb)
tbl.setContentsMargins(0, 0, 0, 0)
tbl.setSpacing(8)
info = QLabel("<b>普通智能算法</b> · 依据 75 部收藏影片（12 部高分）"
              " + 143 位收藏的演员/导演 · 候选 27,571 部")
info.setStyleSheet("color:#c9bda7;font-size:12px;")
info.setMinimumWidth(0)
tbl.addWidget(info, 1)
win._smart_guides = []
win._guide_bar(tbl)
win._refresh_guides()
again = QPushButton("换一批")
again.setObjectName("Ghost")
tbl.addWidget(again)

tb.resize(1734, 40)            # 故意给个「猜错的高度」，看它会不会自己撑开
tb.setAttribute(Qt.WA_DontShowOnScreen, True)
tb.show()
app.processEvents()
print("工具行 tb 高=%d  sizeHint=%d  minimumSizeHint=%d"
      % (tb.height(), tb.sizeHint().height(), tb.minimumSizeHint().height()))
print("注意：QWidget 不会自己撑开 —— 高度由**布局的父容器**决定，"
      "所以真正要查的是 _page() 里怎么放这个 tb。")
for name in ("guide_edit", "guide_w", "guide_chips", "guide_state"):
    wdg = getattr(win, name, None)
    if wdg is not None:
        print("   %-12s %s  h=%d hint_h=%d"
              % (name, rect_of(wdg), wdg.height(), wdg.sizeHint().height()))
print("   btn '换一批'  %s h=%d" % (rect_of(again), again.height()))

# v1.34.1 新判据：工具行内所有控件的右边界不得越过工具行，且相邻控件不得相交
rows = []
for c in tb.findChildren(QWidget):
    if c.parent() is tb and c.isVisible():
        rows.append((c.x(), c))
rows.sort(key=lambda r: r[0])
prev = None
for x, c in rows:
    right = x + c.width()
    if prev is not None and x < prev:
        print("   ❌ %s 与左邻重叠 %dpx" % (type(c).__name__, prev - x))
        ISSUES.append("[工具行] %s 与左邻重叠 %dpx" % (type(c).__name__, prev - x))
    prev = max(prev or 0, right)
print("   相邻控件最小间距检查完毕（工具行宽 %d，最右 %d）" % (tb.width(), prev or 0))
check_clip(tb, "工具行")
win.close()

print()
print("=" * 80)
if ISSUES:
    print("发现 %d 类问题：" % len(ISSUES))
    for s in ISSUES:
        print("  -", s)
else:
    print("未发现问题 ✅")
print("=" * 80)
