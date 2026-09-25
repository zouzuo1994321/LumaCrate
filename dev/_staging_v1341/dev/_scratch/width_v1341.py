# -*- coding: utf-8 -*-
"""v1.34.1 根因③b：工具行各控件的**最小所需宽度** vs 代码给定的固定宽度。

真机截图里 `[2.0▾]` 数字贴边、右边被「加强」压住 → 怀疑 setFixedWidth 不够。
这里在**真机（非 offscreen）**与离屏两种 DPR 下分别量：
  - QDoubleSpinBox(min 0.5 / max 10 / 1 位小数) 的 sizeHint / minimumSizeHint
  - QLineEdit(placeholder 长文) 的 sizeHint
  - 每个控件的 x + w，看相邻控件是否相交
"""
import io
import os
import sys

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_width_v1341.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1310"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"
# 注意：这里**不加** QT_QPA_PLATFORM=offscreen，走真机平台插件

from PySide6.QtCore import Qt                                    # noqa: E402
from PySide6.QtGui import QFontDatabase, QFont                   # noqa: E402
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout,  # noqa: E402
                               QDoubleSpinBox, QLabel, QPushButton, QLineEdit)

app = QApplication(sys.argv)
print("屏幕 =", app.primaryScreen().size() if app.primaryScreen() else None)
print("DPR  =", app.devicePixelRatio())
print("逻辑 DPI =", app.primaryScreen().logicalDotsPerInch()
      if app.primaryScreen() else "?")
for f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.isfile(f):
        QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei UI", 9))

import main_window as mw                                         # noqa: E402
mw.load_style(app)
print("字体行高 =", app.fontMetrics().height(),
      " 字体 =", app.font().family(), app.font().pointSize())
print("=" * 78)

# ---- 单独量 guide_w：0.5~10.0，1 位小数 ----
HOST = QWidget()
lay = QHBoxLayout(HOST)
sp = QDoubleSpinBox()
sp.setRange(0.5, 10.0)
sp.setSingleStep(0.5)
sp.setDecimals(1)
sp.setValue(2.0)
lay.addWidget(sp)
sp_bare = QDoubleSpinBox()
sp_bare.setRange(0.5, 10.0); sp_bare.setDecimals(1); sp_bare.setValue(2.0)
lay.addWidget(sp_bare)
HOST.show()
for _ in range(4):
    app.processEvents()
print("guide_w 同参数（无 setFixedWidth）：")
print("   sizeHint        = %4d x %d" % (sp.sizeHint().width(), sp.sizeHint().height()))
print("   minimumSizeHint = %4d x %d"
      % (sp.minimumSizeHint().width(), sp.minimumSizeHint().height()))
print("   实际宽（被布局给） =", sp.width())
print("   → 代码 setFixedWidth(72)  是否够 =",
      72 >= sp.minimumSizeHint().width())
HOST.close()

# ---- 标题 label 宽度需求 ----
lb = QLabel("引导向量")
lb.setStyleSheet("color:#c9bda7;font-size:12px;")
print()
print("「引导向量」label sizeHint =", lb.sizeHint().width(), "x", lb.sizeHint().height())

# ---- 真正的工具行 ----
print()
print("=" * 78)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
for _ in range(6):
    app.processEvents()

from PySide6.QtWidgets import QVBoxLayout                        # noqa: E402
w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
ph = QLabel("占位"); ph.setFixedHeight(300); v.addWidget(ph)
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
page.show()
for _ in range(6):
    app.processEvents()

print("tb geo=%s h=%d" % ((tb.x(), tb.y(), tb.width(), tb.height()), tb.height()))
print()
print("控件                 x    w    右边界  hintW minHintW")
rows = []
for c in tb.findChildren(QWidget):
    if c.parent() is not tb or not c.isVisible():
        continue
    t = c.text()[:14] if isinstance(c, (QLabel, QPushButton)) else ""
    rows.append((c.x(), c, t))
rows.sort(key=lambda r: r[0])
prev_right = None
for x, c, t in rows:
    right = x + c.width()
    flag = ""
    if prev_right is not None and x < prev_right:
        flag = "  ❌ 与左邻重叠 %dpx" % (prev_right - x)
    print("  %-16s %4d %4d %6d  %5d %8d%s"
          % (type(c).__name__ + ("/" + t if t else ""), x, c.width(), right,
             c.sizeHint().width(), c.minimumSizeHint().width(), flag))
    prev_right = max(prev_right or 0, right)

print()
print("---- 高度明细 ----")
for x, c, t in rows:
    print("  %-16s y=%3d h=%3d 底边=%3d  (hint_h=%d)"
          % (type(c).__name__ + ("/" + t if t else ""), c.y(), c.height(),
             c.y() + c.height(), c.sizeHint().height()))
page.close(); win.close()
