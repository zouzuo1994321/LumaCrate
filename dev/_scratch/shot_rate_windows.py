# -*- coding: utf-8 -*-
"""真机 windows 平台渲染「我的评分」对话框（含原生标题栏），出交付图。

离屏 grab 只有控件内容；用户看到的那个窗口带标题栏与圆角，所以这里走 windows 平台 +
`QScreen.grabWindow(winId)`，抓的是屏幕上这个窗口的真实样子。
"""
import os
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["LMC_NO_SYSPLASH"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

app = QApplication([])
for fn in ("msyh.ttc", "msyhbd.ttc"):
    p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", fn)
    if os.path.exists(p):
        QFontDatabase.addApplicationFont(p)

import main_window as mw
mw.load_style(app)
import ui_hero

dlg = ui_hero.RateDialog(None, 7.5)
dlg.move(600, 400)
dlg.show()
dlg.raise_()
dlg.activateWindow()
for _ in range(30):
    app.processEvents()
    time.sleep(0.02)
time.sleep(0.6)
app.processEvents()

print("dialog size:", dlg.width(), "x", dlg.height())
sc = app.primaryScreen()
pm = sc.grabWindow(int(dlg.winId()))
out = os.path.join(ROOT, "dev", "screenshots", "v14614_rate_dialog.png")
pm.save(out, "PNG")
print("出图:", out, pm.width(), "x", pm.height())

# 再抓一张内容特写（控件本体，不含标题栏）
pm2 = dlg.grab()
pm2.save(os.path.join(ROOT, "dev", "screenshots", "v14614_rate_body.png"), "PNG")
print("body:", pm2.width(), "x", pm2.height())
dlg.close()
print("SHOT_OK")
