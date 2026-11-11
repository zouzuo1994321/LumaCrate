# -*- coding: utf-8 -*-
"""v2.0.14 诊断五：顶栏那个 `self.search` 到 enable 了没？

真机上「打字 3 秒内右端始终没有叉，按回车才出现」。先排除最简单的一种可能：
`editfix` 压根没给这个控件开清空按钮（`isClearButtonEnabled()` 是 Qt 自己的 getter，
一问便知）。顺带量：按钮是否存在、文本非空时是否可见。
"""
import os
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = tempfile.mkdtemp(prefix="lmc_p2014s_")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtCore import Qt                          # noqa: E402
from PySide6.QtGui import QFontDatabase                # noqa: E402
from PySide6.QtWidgets import (QApplication, QLineEdit,  # noqa: E402
                               QSpinBox, QToolButton)

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc",):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db          # noqa: E402
import config as cfg           # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP
db.init_db()

import main_window as mw       # noqa: E402
import editfix                 # noqa: E402

mw.load_style(app)


def pump(n=12, d=0.03):
    for _ in range(n):
        app.processEvents()
        time.sleep(d)


win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
pump()

le = win.search
print("self.search 类型 =", type(le).__name__)
print("isClearButtonEnabled() =", le.isClearButtonEnabled())
print("editfix 标记 =", getattr(le, "_lmc_clear_armed", False))
kids = le.findChildren(QToolButton)
print("子 QToolButton =", [(k.objectName(), k.isVisible(), k.isHidden()) for k in kids])

print("\n--- setText('机器') 之后 ---")
le.setText("机器")
pump(20)
print("text =", repr(le.text()))
print("子 QToolButton =", [(k.objectName(), k.isVisible(), k.isHidden()) for k in kids])
pm = le.grab()
img = pm.toImage()
n = 0
for y in range(img.height()):
    for x in range(max(0, img.width() - 46), img.width()):
        if img.pixelColor(x, y).lightness() > 130:
            n += 1
print("右端 46px 亮像素(>130) =", n)

print("\n--- 回车之后 ---")
le.returnPressed.emit()
pump(20)
print("子 QToolButton =", [(k.objectName(), k.isVisible(), k.isHidden()) for k in kids])

print("\n--- 普通 QLineEdit 对照 ---")
le2 = QLineEdit(win)
le2.setGeometry(10, 10, 300, 32)
le2.show()
pump()
print("新建后 isClearButtonEnabled() =", le2.isClearButtonEnabled(),
      " 子按钮 =", len(le2.findChildren(QToolButton)))
le2.setText("abc")
pump(20)
print("setText 后 子按钮 =", [(k.isVisible(), k.isHidden()) for k in le2.findChildren(QToolButton)])

print("\n--- QSpinBox 内部（不该有）---")
sp = QSpinBox(win)
sp.setGeometry(10, 60, 120, 30)
sp.show()
pump()
print("spin lineedit 子按钮 =", len(sp.findChildren(QLineEdit)[0].findChildren(QToolButton)))

print("\nDONE")
