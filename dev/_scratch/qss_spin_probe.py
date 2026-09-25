# -*- coding: utf-8 -*-
"""v1.34.1 根因验证：QSS 的 padding 是否把 SpinBox 的数字挤到裁切。

对照实验（同一字体、同一 QSS）：
  A) 现状 QSS：QSpinBox/QDoubleSpinBox { padding: 5px 10px; }            → 量高度
  B) 加 min-height 兜底：{ padding: 5px 10px; min-height: 24px; }        → 量高度
  C) 只写 min-height + padding 收窄：{ padding: 2px 8px; min-height: 24px; }
判据：内容可用高（rect.h - 2*frame - 上下 padding）是否 >= 字体行高。
"""
import io
import os
import sys

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_spin_qss.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtGui import QFont, QFontDatabase                    # noqa: E402
from PySide6.QtWidgets import (QApplication, QSpinBox, QDoubleSpinBox,  # noqa: E402
                               QWidget, QVBoxLayout)

app = QApplication(sys.argv)
for f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.isfile(f):
        QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei UI", 9))

BASE = """
QSpinBox, QDoubleSpinBox {
    background: rgba(255,255,255,0.06); color: #ece5d8;
    border: 1px solid rgba(255,255,255,0.10); border-radius: 8px;
    %s
}
"""

CASES = [
    ("A 现状 padding:5/10", "padding: 5px 10px;"),
    ("B +min-height:24", "padding: 5px 10px; min-height: 24px;"),
    ("C padding:2/8 +min-height:24", "padding: 2px 8px; min-height: 24px;"),
    ("D padding:5/10 +min-height:28", "padding: 5px 10px; min-height: 28px;"),
    ("E padding:0 +min-height:22", "padding: 0px 8px; min-height: 22px;"),
]

print("字体像素高 =", app.fontMetrics().height())
print("=" * 78)

for label, decl in CASES:
    host = QWidget()
    host.setStyleSheet(BASE % decl)
    lay = QVBoxLayout(host)
    sp = QSpinBox(); sp.setFixedWidth(96); sp.setRange(0, 200); sp.setValue(30)
    sp.setSuffix(" 个")
    dp = QDoubleSpinBox(); dp.setFixedWidth(88); dp.setRange(0, 5)
    dp.setDecimals(2); dp.setValue(1.50)
    lay.addWidget(sp); lay.addWidget(dp)
    host.show()
    app.processEvents()
    print("[%s]" % label)
    print("   QSpinBox       h=%3d sizeHint=%3d minHint=%3d"
          % (sp.height(), sp.sizeHint().height(), sp.minimumSizeHint().height()))
    print("   QDoubleSpinBox h=%3d sizeHint=%3d minHint=%3d"
          % (dp.height(), dp.sizeHint().height(), dp.minimumSizeHint().height()))
    host.close()

print("=" * 78)
print("对照：无任何 QSS 的原生 SpinBox")
host = QWidget(); lay = QVBoxLayout(host)
sp = QSpinBox(); sp.setFixedWidth(96); sp.setValue(30)
lay.addWidget(sp); host.show(); app.processEvents()
print("   原生 QSpinBox h=%d sizeHint=%d minHint=%d"
      % (sp.height(), sp.sizeHint().height(), sp.minimumSizeHint().height()))
host.close()
