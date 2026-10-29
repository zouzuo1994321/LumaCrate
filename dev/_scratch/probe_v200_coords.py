# -*- coding: utf-8 -*-
"""算出工具窗「个性化设置」页里 11 个色卡（和开关）的**客户区坐标**，供真机点击。

离屏建同样的 SettingsDialog（1320×960），`_show("个性化设置")` 后把每个色卡
`mapTo(dlg, center)` 打出来 —— 真机 `lv.click(dlg, x, y)` 用的是客户区坐标，
所以这里必须 mapTo 到 dialog，不能直接用控件自身 geometry。
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import config as cfg
import database as db

TMP = tempfile.mkdtemp(prefix="lmc_swatch_coords_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

import main_window as mw
import ui_settings as uis


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


uis.SettingsDialog.screen = lambda self: _FakeScr()
mw.load_style(app, {"accent": "#006fee", "style": "glass", "alpha": None})

dlg = uis.SettingsDialog(None)
dlg.resize(uis.SettingsDialog.DEF_W, uis.SettingsDialog.DEF_H)
dlg.show()
app.processEvents()
dlg._show("个性化设置")
for _ in range(8):
    app.processEvents()

print("dialog size:", dlg.width(), "x", dlg.height())
for k in ("个性化设置", "服务管理", "引擎设置", "演员检测", "重复检测"):
    b = dlg.sub_btns.get(k)
    if b is None:
        print("  nav %-8s 缺失" % k)
        continue
    c = b.mapTo(dlg, b.rect().center())
    r = b.mapTo(dlg, b.rect().topLeft())
    print("  nav %-8s rect=(%d,%d) %dx%d center=(%d,%d)"
          % (k, r.x(), r.y(), b.width(), b.height(), c.x(), c.y()))

btns = list(getattr(dlg, "_accent_btns", {}).items())
print("swatch count:", len(btns))
for key, b in btns:
    c = b.mapTo(dlg, b.rect().center())
    r = b.mapTo(dlg, b.rect().topLeft())
    print("  %-8s hex=%-8s rect=(%d,%d) %dx%d  center=(%d,%d)  checked=%s"
          % (key, b.property("hex") or "?", r.x(), r.y(), b.width(), b.height(),
             c.x(), c.y(), b.isChecked()))

try:
    sw = getattr(dlg, "_toggle_stats", None)
    if sw is not None:
        c = sw.mapTo(dlg, sw.rect().center())
        print("toggle(show_stats) center:", c.x(), c.y())
except Exception as e:
    print("toggle probe skipped:", e)

print("PROBE_DONE")
