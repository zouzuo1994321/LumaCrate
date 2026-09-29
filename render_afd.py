# -*- coding: utf-8 -*-
"""v1.34.2 视觉验收：离屏渲染 AutoFillDialog，抓图 + 量化留白 + 证明填 999。"""
import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QImage
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

# 先注册中文字体（否则 sizeHint 虚高、文字成豆腐块）
for fp in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyh.ttf",
           r"C:/Windows/Fonts/simhei.ttf"):
    if os.path.exists(fp):
        QFontDatabase.addApplicationFont(fp)
        print("font:", fp)

# 载入 style（accent 令牌替换，使 QSS 合法；padding 决定 spinner 宽度）
qss = open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()
qss = (qss.replace("__ACCENT__", "#e05243").replace("__ACCENT_DARK__", "#b23a2e")
          .replace("__ACCENT_DEEP__", "#7d261d").replace("__ACCENT_LIGHT__", "#f0a89c"))
qss = re.sub(r"rgba\([^)]*\)", "#e05243", qss)
qss = qss.replace("__ACCENT_RGB__", "224, 82, 67")
app.setStyleSheet(qss)

from ui_settings import AutoFillDialog

dlg = AutoFillDialog(None)
dlg.show()
dlg._fit_height()
app.processEvents()

# 把所有维度勾上并填到上限 999，证明三位数字能完整显示、值确实落到 999
first_key = None
for key in dlg.dim_rows:
    ck, sp_top, sp_w = dlg.dim_rows[key]
    ck.setChecked(True)
    sp_top.setValue(999)
    if first_key is None:
        first_key = key
app.processEvents()
dlg.repaint()

spin = dlg.dim_rows[first_key][1]
print("spin first_key=%s max=%d text=%r value=%d"
      % (first_key, spin.maximum(), spin.text(), spin.value()))

# 量化留白：统计范围组框(g1)底边 → 其下方第一个可见兄弟控件顶边 的竖向间隙
g1 = dlg.findChild(type(dlg).__mro__[0], "")  # placeholder, replaced below
from PySide6.QtWidgets import QGroupBox
groups = dlg.findChildren(QGroupBox)
print("groupboxes:", [(g.objectName(), g.title(), g.geometry().getRect()) for g in groups])
if len(groups) >= 1:
    g1 = groups[0]
    g1_bottom = g1.geometry().bottom()  # 相对 dlg
    # 找 g1 之后、位于其下方的第一个控件
    nxt_y = None
    for ch in dlg.findChildren(object):
        pass
    # 用布局里的顺序：g1 的下一个 widget
    lay = dlg.layout() if dlg.layout() else None
    # 直接遍历所有可见子控件几何
    cands = []
    for ch in dlg.children():
        from PySide6.QtWidgets import QWidget as _W
        if isinstance(ch, _W) and ch.isVisible():
            geo = ch.geometry()
            if geo.top() > g1_bottom:
                cands.append((geo.top(), type(ch).__name__, geo.getRect()))
    cands.sort()
    if cands:
        print("below g1 first widget: %s top=%d  ->  gap=%d px"
              % (cands[0][1], cands[0][0], cands[0][0] - g1_bottom))

print("dialog h=%d w=%d" % (dlg.height(), dlg.width()))

# 抓图（合成到深底）
px = dlg.grab()
img = px.toImage().convertToFormat(QImage.Format_ARGB32)
bg = QImage(img.size(), QImage.Format_ARGB32)
bg.fill(QColor(20, 18, 16))
p = QPainter(bg)
p.drawImage(0, 0, img)
p.end()
out = os.path.join(HERE, "afd_v1342.png")
bg.save(out)
print("RENDER ok -> %s" % out)
