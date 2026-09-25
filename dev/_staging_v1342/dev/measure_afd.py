# -*- coding: utf-8 -*-
"""通用 AutoFillDialog 度量：argv = srcdir outpng tag。量化统计范围组框高度与下方留白。"""
import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = sys.argv[1]
OUT = sys.argv[2]
TAG = sys.argv[3]
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QGroupBox, QWidget
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QImage

app = QApplication(sys.argv[:1])

for fp in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/simhei.ttf"):
    if os.path.exists(fp):
        QFontDatabase.addApplicationFont(fp)

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
app.processEvents()

groups = dlg.findChildren(QGroupBox)
g1 = None
for g in groups:
    if g.title() == "统计范围":
        g1 = g
        break
info = {}
if g1 is not None:
    geo = g1.geometry()
    info["g1_rect"] = geo.getRect()
    # 组框内最后一个可见子控件的底边
    inner_bottom = None
    for ch in g1.findChildren(QWidget):
        if ch.isVisible() and ch.height() > 0:
            b = ch.y() + ch.height()
            inner_bottom = b if inner_bottom is None else max(inner_bottom, b)
    info["g1_h"] = geo.height()
    info["inner_bottom"] = inner_bottom
    if inner_bottom is not None:
        info["inner_whitespace"] = geo.height() - inner_bottom
    # 组框底 → 下一个可见控件顶
    cands = [ch.geometry().top() for ch in dlg.children()
             if isinstance(ch, QWidget) and ch.isVisible()
             and ch.geometry().top() > geo.bottom()]
    if cands:
        info["gap_below"] = min(cands) - geo.bottom()
# cb_scope / lb_scope_tip 几何（量化组框内部「中间留白」与「下方留白」）
try:
    cb = dlg.cb_scope
    tp = dlg.lb_scope_tip
    cb_b = cb.y() + cb.height()
    tp_t = tp.y()
    tp_b = tp.y() + tp.height()
    g1_b = g1.y() + g1.height() if g1 is not None else -1
    info["cb_rect"] = cb.geometry().getRect()
    info["tip_rect"] = tp.geometry().getRect()
    info["gap_cb_to_tip"] = tp_t - cb_b
    info["ws_below_tip"] = g1_b - tp_b
except Exception as e:
    info["scope_err"] = str(e)

# first spin text
sp = None
try:
    key = next(iter(dlg.dim_rows))
    sp = dlg.dim_rows[key][1]
    info["spin_text"] = sp.text()
    info["spin_max"] = sp.maximum()
except Exception as e:
    info["spin_err"] = str(e)

info["dlg_h"] = dlg.height()
info["dlg_w"] = dlg.width()
print(TAG, "RESULT", info)

px = dlg.grab()
img = px.toImage().convertToFormat(QImage.Format_ARGB32)
bg = QImage(img.size(), QImage.Format_ARGB32)
bg.fill(QColor(20, 18, 16))
p = QPainter(bg)
p.drawImage(0, 0, img)
p.end()
bg.save(OUT)
print(TAG, "saved", OUT)
