# -*- coding: utf-8 -*-
"""v2.0.11 取证 2：滚动条滑块四种 QSS 变体的**真实几何**对比。

为什么必须实测：Qt 里给 `::handle` 写 `margin` 后，圆角是按**缩窄后的矩形**算、
还是按原始矩形算再裁，直接决定滑块看起来是胶囊还是方头。
用户截图（53×117）里滑块是 4px 宽、两端齐平 —— 4px 宽 + radius 4 本来该是正圆头，
结果量出来顶行就是满宽，说明 radius 在带 margin 的情形下**没生效**。
这里把 4 种写法各渲一次，量「顶端逐行填充宽度」和「左上角亮度矩阵」，用数据挑。

用法：
  python -u -c "import runpy; runpy.run_path('<本文件>', run_name='__main__')"
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("LMC_NO_SYSMON", "1")

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget  # noqa: E402

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw  # noqa: E402

mw.load_style(app)

VARIANTS = [
    ("V0 现状 width8 margin2 r4",
     "QScrollBar:vertical{background:transparent;width:8px;margin:2px;}"
     "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);"
     "border-radius:4px;min-height:32px;}"
     "QScrollBar::add-line,QScrollBar::sub-line{height:0;width:0;}"
     "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}"),
    ("V1 width12 handle margin 2px/3px r3",
     "QScrollBar:vertical{background:transparent;width:12px;margin:0;}"
     "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);"
     "border-radius:3px;min-height:36px;margin:2px 3px;}"
     "QScrollBar::add-line,QScrollBar::sub-line{height:0;width:0;}"
     "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}"),
    ("V2 width12 无 margin r6",
     "QScrollBar:vertical{background:transparent;width:12px;margin:0;}"
     "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);"
     "border-radius:6px;min-height:36px;}"
     "QScrollBar::add-line,QScrollBar::sub-line{height:0;width:0;}"
     "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}"),
    ("V3 width14 handle margin 0 4px r3",
     "QScrollBar:vertical{background:transparent;width:14px;margin:0;}"
     "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);"
     "border-radius:3px;min-height:36px;margin:0 4px;}"
     "QScrollBar::add-line,QScrollBar::sub-line{height:0;width:0;}"
     "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}"),
    # ↓ 关键对照：**槽**带 margin、滑块不带 —— 看槽的 margin 会不会也把圆角切掉
    ("V4 槽 width12 margin2 r4(滑块无margin)",
     "QScrollBar:vertical{background:transparent;width:12px;margin:2px;}"
     "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);"
     "border-radius:4px;min-height:32px;}"
     "QScrollBar::add-line,QScrollBar::sub-line{height:0;width:0;}"
     "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}"),
    ("V5 槽 width8 margin0 r4(滑块无margin)",
     "QScrollBar:vertical{background:transparent;width:8px;margin:0;}"
     "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);"
     "border-radius:4px;min-height:32px;}"
     "QScrollBar::add-line,QScrollBar::sub-line{height:0;width:0;}"
     "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}"),
    ("V6 槽 width12 margin2 滑块r4+悬浮槽底",
     "QScrollBar:vertical{background:transparent;width:12px;margin:2px;}"
     "QScrollBar:vertical:hover{background:rgba(255,255,255,0.05);"
     "border-radius:5px;}"
     "QScrollBar::handle:vertical{background:rgba(255,255,255,0.22);"
     "border-radius:4px;min-height:32px;}"
     "QScrollBar::handle:vertical:hover{background:rgba(255,255,255,0.40);}"
     "QScrollBar::add-line,QScrollBar::sub-line{height:0;width:0;}"
     "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}"),
]


def lum(img, x, y):
    c = img.pixelColor(x, y)
    return (c.red() + c.green() + c.blue()) / 3.0


def run(tag, qss):
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    body = QWidget()
    body.setMinimumHeight(1400)
    sa.setWidget(body)
    sa.setStyleSheet(qss)
    sa.resize(320, 240)
    sa.show()
    app.processEvents()
    sb = sa.verticalScrollBar()
    img = sb.grab().toImage().convertToFormat(QImage.Format_RGB32)
    W, H = img.width(), img.height()
    # 找滑块：取中间一列里「比槽底亮」的连续区间
    col_x = W // 2
    vals = [lum(img, col_x, y) for y in range(H)]
    lit = [y for y, v in enumerate(vals) if v > 12]
    if not lit:
        print("%-34s 槽 %dx%d  ⚠ 中间列没有滑块" % (tag, W, H))
        return None
    y0, y1 = lit[0], lit[-1]
    base = min(vals)
    thr = (max(vals[y0:y1 + 1]) + base) / 2.0
    widths = []
    for y in range(y0, y0 + 6):
        xs = [x for x in range(W) if lum(img, x, y) > thr]
        widths.append(len(xs))
    mid = [x for x in range(W) if lum(img, x, (y0 + y1) // 2) > thr]
    print("%-34s 槽 %2dx%d  滑块 y=%d..%d(h=%d) 宽=%d  x=%s"
          % (tag, W, H, y0, y1, y1 - y0 + 1, len(mid), (mid[0], mid[-1]) if mid else None))
    print("    顶端逐行宽度 %s  → %s"
          % (widths, "圆头 ✓" if widths[0] < widths[-1] else "方头 ✗"))
    return sa, img, W, H, y0, y1


print("=" * 78)
print("滚动条变体实测（槽宽 / 滑块宽 / 顶端逐行宽度）")
print("=" * 78)
for tag, qss in VARIANTS:
    run(tag, qss)
    print()

print("PROBE_V2011_SB_DONE")
