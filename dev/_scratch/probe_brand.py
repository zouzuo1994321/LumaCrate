# -*- coding: utf-8 -*-
"""量「LocalMediaCenter」副标题到底差多少像素 —— 用数据决定字号，别凭感觉调。

问题（用户反馈 3）：侧栏品牌区副标题 `LocalMediaCenter` 末尾的 r 被裁掉。
侧栏 `setFixedWidth(186)`，内边距 8+8 → 170；品牌区 `_brand()` 再加 6+6 → 158；
减掉 logo 28 + spacing 8 → 留给文字列 **122px**。
`#Sub` 现在是 `font-size:11px; letter-spacing:2px`，15 个字符要 122px 上下 —— 正好卡在边界。

本探针把 11px / 10.5px / 10px / 9.5px 四档都量一遍，输出「文字宽 / 可用宽 / 余量」。
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QFontDatabase

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_brand_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

from main_window import MainWindow, render_style

win = MainWindow()
win.setAttribute(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
app.setStyleSheet(render_style(cfg.get_settings().appearance))
win.show()
app.processEvents()

brand = win._brand()
brand.resize(158, 60)
app.processEvents()
sub = [l for l in brand.findChildren(QLabel) if l.objectName() == "Sub"][0]

# 可用宽度：品牌区 158 − logo(28) − 间距(8) = 122
AVAIL = 158 - 28 - 8
print(f"侧栏宽 {win.sidebar.width()} / 品牌区可用 {AVAIL}px / 文本 {sub.text()!r}")
print(f"QFont family = {sub.font().family()!r}  size = {sub.font().pointSizeF()!r}")

for fsz, ls in ((11, 2), (10.5, 2), (10, 2), (10, 1.5), (10, 1), (9.5, 1)):
    app.setStyleSheet(
        "QLabel#Sub { color:#8c8071; font-size:%spx; letter-spacing:%spx; }" % (fsz, ls))
    app.processEvents()
    fm = sub.fontMetrics()
    w_text = fm.horizontalAdvance(sub.text())
    print(f"font-size {fsz:>4}px / letter-spacing {ls}px → 文字宽 {w_text:>4}px · "
          f"余量 {AVAIL - w_text:>4}px · {'✓ 放得下' if w_text <= AVAIL else '✗ 会被裁'}")

print(f"\n（原始样式下 sub.width()={sub.width()}  sizeHint={sub.sizeHint().width()}）")
