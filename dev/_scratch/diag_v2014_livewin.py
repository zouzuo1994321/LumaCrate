# -*- coding: utf-8 -*-
"""v2.0.14 诊断七：真平台 + 真 MainWindow，打字后清空按钮的 isVisible / 几何。

离屏那条路（诊断六）证明 Qt 打字会显示按钮；真机却要回车才出现。
本脚本在**真 windows 平台**上跑真 MainWindow，把按钮的 isVisible、geometry、
父控件宽度一起打出来，并在抓图里量右端亮像素 —— 一次分清「没显示」还是「显示在错位置」。
"""
import os
import sys
import tempfile
import time

os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = tempfile.mkdtemp(prefix="lmc_p2014t_")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtCore import QEvent, QPoint, Qt            # noqa: E402
from PySide6.QtGui import QFontDatabase, QKeyEvent        # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton   # noqa: E402

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

mw.load_style(app)


def pump(n=10, d=0.02):
    for _ in range(n):
        app.processEvents()
        time.sleep(d)


win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(20, 0.03)

le = win.search
btn = le.findChildren(QToolButton)
btn = btn[0] if btn else None
print("搜索框几何 =", le.geometry().getRect(), " 可见 =", le.isVisible())
print("按钮 =", btn, " visible =", btn.isVisible() if btn else None)


def report(tag):
    if btn is None:
        print("  %-12s 没有按钮" % tag)
        return
    pm = le.grab()
    img = pm.toImage()
    n = 0
    for y in range(img.height()):
        for x in range(max(0, img.width() - 46), img.width()):
            if img.pixelColor(x, y).lightness() > 130:
                n += 1
    print("  %-12s text=%r btn.visible=%s btn.geom=%s  右端亮像素=%d"
          % (tag, le.text(), btn.isVisible(), btn.geometry().getRect(), n), flush=True)


report("初始")
le.setFocus()
pump()
for ch in "ZZZ":
    app.sendEvent(le, QKeyEvent(QEvent.KeyPress, ord(ch), Qt.NoModifier, ch))
    pump(3)
pump(20, 0.03)
report("投键后")

# 再试一次 setText（对照）
le.setText(le.text())
pump(20, 0.03)
report("setText后")

# 强制重排：改一下宽度再改回来（模拟「窗口被重排」）
w0 = le.width()
le.resize(w0 - 1, le.height())
pump(5)
le.resize(w0, le.height())
pump(20, 0.03)
report("重排后")

if btn is not None:
    pm = le.grab()
    pm.save(os.path.join(ROOT, "dev", "screenshots", "v2014g_typed_live.png"))
    print("  图 v2014g_typed_live.png  %dx%d" % (pm.width(), pm.height()))

win.close()
pump()
print("\nDONE")
