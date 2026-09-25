# -*- coding: utf-8 -*-
"""v1.34.1 根因①确认：AutoFillDialog 到底需要多高，以及 DPR 的影响。

把对话框高度从 520 → 700 逐步试，打印：
  - `dlg.sizeHint().height()`（Qt 认为需要的高度）
  - 最后一行控件（foot 里的按钮）底边 y 是否 > 对话框高
  - 每个可见子控件的 y+h 与对话框高度的关系
找出「不裁切」所需的最小高度。
"""
import io
import os
import sys

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_dlgfit.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1310"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt                                    # noqa: E402
from PySide6.QtGui import QFontDatabase, QFont                   # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget              # noqa: E402

app = QApplication(sys.argv)
for f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.isfile(f):
        QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei UI", 9))

import main_window as mw                                         # noqa: E402
mw.load_style(app)
import ui_settings as uis                                        # noqa: E402

print("devicePixelRatio =", app.devicePixelRatio())
print("字体行高 =", app.fontMetrics().height())
print("=" * 78)

dlg = uis.AutoFillDialog()
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)


def report(tag):
    """返回 (对话框高, 最底边, 溢出量)。"""
    dlg.show()
    for _ in range(4):
        app.processEvents()
    H = dlg.height()
    worst = 0
    worst_w = ""
    for c in dlg.findChildren(QWidget):
        if not c.isVisible() or c.height() <= 0:
            continue
        # 只算顶层的直接子控件（排除 QGroupBox 内部，那些不裁）
        p = c.parent()
        if p is not dlg:
            continue
        bot = c.y() + c.height()
        if bot > worst:
            worst = bot
            worst_w = type(c).__name__
    print("  %-22s dlgH=%3d  sizeHintH=%3d minH=%3d  顶层最底边=%3d(from %s)  溢出=%d"
          % (tag, H, dlg.sizeHint().height(), dlg.minimumSizeHint().height(),
             worst, worst_w, max(0, worst - H)))
    return H, worst, max(0, worst - H)


print("---- 现状（代码里 resize(660, 560)）----")
report("as-is(resize 660x560)")

print()
print("---- 手动改高度，找不裁切的最小值 ----")
lo_fit = None
for h in (520, 560, 580, 600, 620, 640, 660, 680, 700, 720):
    dlg.resize(660, h)
    H, bot, over = report("resize(660,%d)" % h)
    if over == 0 and lo_fit is None:
        lo_fit = h

print()
print("→ 不裁切的最小高度 =", lo_fit)
print("→ 代码里的 560 比它少 =", (lo_fit - 560) if lo_fit else "?")

print()
print("---- 切「我的收藏」后是否又不够 ----")
dlg.resize(660, lo_fit or 700)
for i in range(dlg.cb_scope.count()):
    dlg.cb_scope.setCurrentIndex(i)
    report("scope=%d" % i)
dlg.close()
