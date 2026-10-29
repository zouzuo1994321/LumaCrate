# -*- coding: utf-8 -*-
"""真机（windows 平台）量「已配置的媒体库」列表：行高 / 行内控件 / 按钮是否被裁。

离屏探针（probe_liblist.py）跑出来一切正常，但用户真机截图里按钮底部被切 ——
本脚本用 QT_QPA_PLATFORM=windows 复现真机 DPI / 样式路径，并单独抓「行控件」的图。
用法：python probe_liblist_win.py [tag]
"""
import os
import sys
import json

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["LMC_NO_SYSPLASH"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"

TMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp", "lmc_liblist")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)
CFG = os.path.join(TMP, "settings.json")
with open(CFG, "w", encoding="utf-8") as f:
    json.dump({"libraries": [
        {"name": "Javlibrary", "kind": "电影", "paths": ["D:/a%d" % i for i in range(14)],
         "filter": {}},
        {"name": "Jav-VR", "kind": "电影", "paths": ["D:/vr"], "filter": {}},
        {"name": "Jav-临时", "kind": "混合", "paths": ["D:/tmp"], "filter": {}},
    ]}, f, ensure_ascii=False)
os.environ["LMC_CONFIG"] = CFG

import database as db
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
import applog
applog.log_dir = lambda: os.path.join(TMP, "index_data", "logs")

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import Qt

app = QApplication([])
print("devicePixelRatio:", app.primaryScreen().devicePixelRatio(),
      " logicalDpi:", app.primaryScreen().logicalDotsPerInch())
for fn in ("msyh.ttc", "msyhbd.ttc"):
    p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", fn)
    if os.path.exists(p):
        QFontDatabase.addApplicationFont(p)

import main_window as mw
from PySide6.QtWidgets import QStyleFactory
_st = QStyleFactory.create("Fusion")     # 与真机入口一致（main.py 强制 Fusion）
if _st is not None:
    app.setStyle(_st)
mw.load_style(app)
import ui_settings

TAG = sys.argv[1] if len(sys.argv) > 1 else "win"
dlg = ui_settings.SettingsDialog(None)
dlg.resize(ui_settings.SettingsDialog.DEF_W, ui_settings.SettingsDialog.DEF_H)
dlg.show()
dlg._show("服务管理")
for _ in range(16):
    app.processEvents()

lst = dlg.lib_list
print("LIB_ROW_H      :", ui_settings.LIB_ROW_H, " LIST_CHROME:", ui_settings.LIST_CHROME)
print("lib_list height:", lst.height(), " viewport h:", lst.viewport().height(),
      " count:", lst.count(), " vscroll max:", lst.verticalScrollBar().maximum())
for i in range(lst.count()):
    it = lst.item(i)
    w = lst.itemWidget(it)
    r = lst.visualItemRect(it)
    print("  item%d sizeHint=%s visualRect=(%d,%d,%d,%d) rowWidget=(%d,%d,%d,%d) h 差=%d" % (
        i, (it.sizeHint().width(), it.sizeHint().height()),
        r.x(), r.y(), r.width(), r.height(),
        w.x(), w.y(), w.width(), w.height() if w else -1,
        (r.height() - w.height()) if w else -1))
    if w is not None:
        for b in w.findChildren(QPushButton):
            g = b.geometry()
            print("      btn %-4s geo=(%d,%d,%d,%d) bottom=%d  row_h=%d 越界=%s" % (
                b.text(), g.x(), g.y(), g.width(), g.height(),
                g.y() + g.height(), w.height(), g.y() + g.height() > w.height()))

# 单抓第一行控件（160% 缩放无关，直接看按钮底部有没有被裁）
w0 = lst.itemWidget(lst.item(0))
if w0 is not None:
    pmr = w0.grab()
    outr = os.path.join(ROOT, "dev", "screenshots", "_librow_%s.png" % TAG)
    pmr.save(outr, "PNG")
    print("行控件出图:", outr, pmr.width(), "x", pmr.height())

# 等淡入动画跑完再抓整块 —— 抓早了拿到的是半透明帧（整体发白，没法量文字）
import time as _t
for _ in range(24):
    app.processEvents()
    _t.sleep(0.08)

grp = lst.parentWidget()
while grp is not None and grp.__class__.__name__ != "QGroupBox":
    grp = grp.parentWidget()
target = grp or lst
pm = target.grab()
out = os.path.join(ROOT, "dev", "screenshots", "_liblist_win_%s.png" % TAG)
pm.save(out, "PNG")
print("组框图:", out, pm.width(), "x", pm.height())
print("PROBE_WIN_OK")
