# -*- coding: utf-8 -*-
"""「我的评分」对话框：离屏渲染 + 量尺寸，验证宽度是否被提示文字撑开、左右留空多少。

输出：
  · 对话框 size / minimumSizeHint / sizeHint
  · 每个布局子项的 geometry（spin / hint / 按钮行）
  · 出图 dev/screenshots/_rate_<tag>.png（已垫底色，避免 grab 透明底骗人）
用法：python … probe_rate_dialog.py [tag]
"""
import os
import sys

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSPLASH"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"

TAG = sys.argv[1] if len(sys.argv) > 1 else "now"

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import Qt

app = QApplication([])
for fn in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf"):
    p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", fn)
    if os.path.exists(p):
        QFontDatabase.addApplicationFont(p)

import main_window as mw
mw.load_style(app)

from ui_hero import RateDialog

dlg = RateDialog(None, 7.5)
dlg.show()
for _ in range(6):
    app.processEvents()

print("sizeHint      :", dlg.sizeHint().width(), "x", dlg.sizeHint().height())
print("minimumSizeHint:", dlg.minimumSizeHint().width(), "x", dlg.minimumSizeHint().height())
print("actual        :", dlg.width(), "x", dlg.height())
print("spin sizeHint :", dlg.spin.sizeHint().width(), "actual", dlg.spin.width())
lay = dlg.layout()
for i in range(lay.count()):
    it = lay.itemAt(i)
    w = it.widget()
    if w is not None:
        g = w.geometry()
        print("  item%d %-14s geo=(%d,%d,%d,%d)" % (
            i, type(w).__name__, g.x(), g.y(), g.width(), g.height()))
    else:
        print("  item%d layout                          geo=%s" % (i, it.geometry()))
btns = [b for b in dlg.findChildren(QPushButton)]
for b in btns:
    g = b.geometry()
    print("  btn %-6s geo=(%d,%d,%d,%d)  text_w=%d" % (
        b.text(), g.x(), g.y(), g.width(), g.height(), b.sizeHint().width()))

pm = dlg.grab()
from PySide6.QtGui import QImage, QPainter, QColor
img = QImage(pm.size(), QImage.Format_RGB32)
img.fill(QColor("#14110e"))
p = QPainter(img)
p.drawPixmap(0, 0, pm)
p.end()
out = os.path.join(ROOT, "dev", "screenshots", "_rate_%s.png" % TAG)
img.save(out)
print("出图:", out, pm.width(), "x", pm.height())
print("PROBE_OK")
