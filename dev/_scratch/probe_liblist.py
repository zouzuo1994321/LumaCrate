# -*- coding: utf-8 -*-
"""「服务管理 → 媒体库」列表的用量探针：量行高 / 列表高 / 行内控件的实际几何，并出图。

用法：python … probe_liblist.py [tag]
"""
import os
import sys
import json

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
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
for fn in ("msyh.ttc", "msyhbd.ttc"):
    p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", fn)
    if os.path.exists(p):
        QFontDatabase.addApplicationFont(p)

import main_window as mw
mw.load_style(app)
import ui_settings

TAG = sys.argv[1] if len(sys.argv) > 1 else "now"
dlg = ui_settings.SettingsDialog(None)
dlg.resize(ui_settings.SettingsDialog.DEF_W, ui_settings.SettingsDialog.DEF_H)
dlg.show()
dlg._show("服务管理")
for _ in range(12):
    app.processEvents()

lst = dlg.lib_list
print("LIB_ROW_H      :", ui_settings.LIB_ROW_H, " LIST_CHROME:", ui_settings.LIST_CHROME)
print("lib_list height:", lst.height(), " viewport h:", lst.viewport().height(),
      " count:", lst.count(),
      " vscroll max:", lst.verticalScrollBar().maximum())
for i in range(lst.count()):
    it = lst.item(i)
    w = lst.itemWidget(it)
    r = lst.visualItemRect(it)
    print("  item%d sizeHint=%s  visualRect=(%d,%d,%d,%d)  rowWidget h=%d  (h 差=%d)" % (
        i, (it.sizeHint().width(), it.sizeHint().height()),
        r.x(), r.y(), r.width(), r.height(),
        w.height() if w else -1,
        (r.height() - w.height()) if w else -1))
    if w is not None:
        for b in w.findChildren(QPushButton):
            g = b.geometry()
            print("      btn %-4s geo=(%d,%d,%d,%d)" % (b.text(), g.x(), g.y(), g.width(), g.height()))

# 出图：整个「媒体库」组框（含标题「已配置的媒体库：」与「扫描全部媒体库」）
grp = lst.parentWidget()
while grp is not None and grp.__class__.__name__ != "QGroupBox":
    grp = grp.parentWidget()
target = grp or lst
pm = target.grab()
out = os.path.join(ROOT, "dev", "screenshots", "_liblist_%s.png" % TAG)
pm.save(out, "PNG")
print("出图:", out, pm.width(), "x", pm.height())
print("PROBE_OK")
