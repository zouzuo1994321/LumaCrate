# -*- coding: utf-8 -*-
"""v2.0.11 取证：输入框左侧内边距 + 首页滚动条滑块几何。

用户反馈（本轮 2 / 3）：
  2. 「优化首页的滚轮，更符合软件风格，和圆角保持一致」
  3. 「所有输入的好像前面有几px的间隙」

这里不猜，全部用**像素**量：
  A. 输入框：grab() 后从 x=0 往右扫，第一个「亮字列」的列号 = 边框(1) + padding + 字形左余隙。
     同时量控件高、圆角可推断量（左上角非底色像素的行宽）。
  B. 滚动条：grab() 后量滑块的**每行填充宽度**——圆角滑块的顶部几行会窄下去（1,2,4,6…），
     方头滑块则一行就是满宽。这是「圆角到底有没有生效」唯一站得住的判据。

用法（必须用 runpy 走绝对路径）：
  python -u -c "import runpy; runpy.run_path(r'<本文件>', run_name='__main__')"
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
from PySide6.QtWidgets import (QApplication, QDialog, QLineEdit,  # noqa: E402
                               QScrollArea, QVBoxLayout, QWidget)

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw          # noqa: E402
import ui_home                    # noqa: E402

mw.load_style(app)

GLYPH = "汉"
FAIL = []


def _img(widget):
    """grab() 成独立 QImage（不复用 pixmap，避免引用抖动）。"""
    pm = widget.grab()
    return pm.toImage().convertToFormat(QImage.Format_RGB32)


def _lum(img, x, y):
    c = img.pixelColor(x, y)
    return (c.red() + c.green() + c.blue()) / 3.0


def first_ink(img, thr=95):
    """从 x=2 起扫第一列出现「亮字」的列号（x=0/1 是 1px 边框 + 抗锯齿，必须跳过）。

    只数「同一列里有 ≥2 个亮像素」的列 —— 单个孤立亮点是边框圆角的抗锯齿。
    """
    w, h = img.width(), img.height()
    for x in range(2, w):
        ys = [y for y in range(3, h - 3) if _lum(img, x, y) > thr]
        if len(ys) >= 2:
            return x, (min(ys), max(ys))
    return None, None


def field_report(tag, edit):
    edit.setPlaceholderText(GLYPH)
    edit.setText("")
    edit.resize(max(160, edit.sizeHint().width()), edit.sizeHint().height())
    edit.show()
    app.processEvents()
    img = _img(edit)
    x_ink, ys = first_ink(img)
    # 左边框是否被画出来（第 0 列应该有比底色亮的一条）
    lum_border = _lum(img, 0, img.height() // 2)
    lum_bg = _lum(img, 4, img.height() // 2)
    print("%-14s h=%2d  w=%3d  首字列=%s  边框列亮度=%.0f  内部底=%.0f  字形行=%s"
          % (tag, edit.height(), edit.width(), x_ink, lum_border, lum_bg, ys))
    print("               contentsRect=%s  textMargins=%s  font.px=%s"
          % (edit.contentsRect(), edit.textMargins(),
             edit.font().pixelSize()))
    return x_ink


print("=" * 78)
print("A. 输入框左内边距（首字列号 = 边框 1px + padding + 字形余隙）")
print("=" * 78)

# A1 普通页面里的输入框（全局 QLineEdit 规则）
host = QWidget()
lay = QVBoxLayout(host)
e1 = QLineEdit()
lay.addWidget(e1)
host.resize(300, 90)
host.show()
app.processEvents()
a1 = field_report("普通页面", e1)

# A2 首页列筛选弹层（QFrame + Qt.Dialog，不是 QDialog → 走全局规则）
pop = ui_home.ColumnFilterPopup("title", "标题")
pop.show()
app.processEvents()
a2 = field_report("列筛选弹层", pop.edit)

# A3 真 QDialog 里的输入框（`QDialog QLineEdit` 那条规则只对它生效）
dlg = QDialog()
dl = QVBoxLayout(dlg)
e3 = QLineEdit()
dl.addWidget(e3)
dlg.resize(320, 100)
dlg.show()
app.processEvents()
a3 = field_report("QDialog 内", e3)

print()
print("=" * 78)
print("B. 首页滚动条（QScrollArea 竖条，与 _page() 同构）")
print("=" * 78)

sa = QScrollArea()
sa.setWidgetResizable(True)
sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
body = QWidget()
body.setMinimumHeight(1400)
sa.setWidget(body)
sa.resize(320, 240)
sa.show()
app.processEvents()

sb = sa.verticalScrollBar()
sb.show()
app.processEvents()
sb_img = _img(sb)
W, H = sb_img.width(), sb_img.height()
print("竖条控件 %dx%d   handle 几何=%s   range=%d" % (W, H, sb.rect(), sb.maximum()))

vals_mid = [_lum(sb_img, W // 2, y) for y in range(H)]
lit = [y for y, v in enumerate(vals_mid) if v > 12]
if not lit:
    FAIL.append("滚动条：中间列没量到滑块")
    print("  ⚠ 没量到滑块")
else:
    y0, y1 = lit[0], lit[-1]
    thr = (max(vals_mid[y0:y1 + 1]) + min(vals_mid)) / 2.0
    print("  滑块 y=%d..%d（高 %d）" % (y0, y1, y1 - y0 + 1))
    widths, spans = [], []
    for y in range(y0, min(y0 + 5, y1 + 1)):
        xs = [x for x in range(W) if _lum(sb_img, x, y) > thr]
        widths.append(len(xs))
        spans.append((xs[0], xs[-1]) if xs else None)
    mid_y = (y0 + y1) // 2
    mid_xs = [x for x in range(W) if _lum(sb_img, x, mid_y) > thr]
    print("  中间行 x=%s 宽=%d" % ((mid_xs[0], mid_xs[-1]) if mid_xs else None, len(mid_xs)))
    print("  顶端逐行：%s" % list(zip(range(y0, y0 + len(widths)), widths, spans)))
    rounded = widths[0] < len(mid_xs)
    print("  → %s" % ("顶端更窄 = 圆角生效 ✓" if rounded else "顶端与中间同宽 = 方头 ✗"))
    if not rounded:
        FAIL.append("滚动条滑块仍是方头（顶端宽 %d vs 中间 %d）"
                    % (widths[0], len(mid_xs)))
    print("  滑块宽度 = %d px（用户截图里是 4px 方头）" % len(mid_xs))

print()
if a1 is None or a2 is None:
    FAIL.append("输入框首字列没量到")
else:
    print("首字列：普通=%s 弹层=%s 对话框=%s（px）" % (a1, a2, a3))

print()
print("PROBE_V2011_DONE 失败项=%d" % len(FAIL))
for f in FAIL:
    print("  ✗", f)
