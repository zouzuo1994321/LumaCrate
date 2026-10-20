# -*- coding: utf-8 -*-
"""v1.42.2 探针 6：精确测量 src_list 行几何，推导「不裁切」的高度公式。

量：sizeHintForRow / spacing() / 首个 item 的 inset / 各行 visualRect /
    最后一个 row widget 完整可见所需的最小列表高（n=1..4，含幻影项场景）。
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QWidget, QHBoxLayout, QLabel
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QSize

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_geo_")
db.db_path = lambda: os.path.join(TMP, "x.db")
cfg.config_path = lambda: os.path.join(TMP, "s.json")
cfg._SETTINGS = None
st = cfg.Settings()
cfg._SETTINGS = st
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow, load_style
from ui_settings import SettingsDialog

load_style(app, st.appearance)


class _FakeScr:
    def availableGeometry(self):
        from PySide6.QtCore import QRect
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        from PySide6.QtCore import QRect
        return QRect(0, 0, 2560, 1440)


SettingsDialog.screen = lambda self: _FakeScr()
win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
app.processEvents()
for k, b in dlg.sub_btns.items():
    if "刮削" in k:
        b.click()
        break
app.processEvents()

sl = dlg.src_list
print("frameWidth =", sl.frameWidth(), " spacing =", sl.spacing())
for i in range(sl.count()):
    print("sizeHintForRow(%d) = %d" % (i, sl.sizeHintForRow(i)))

# 二分找「最后一行 widget 完整可见」的最小列表高
n = sl.count()
last = sl.item(n - 1)
w = sl.itemWidget(last)


def fully_visible(h):
    sl.setFixedHeight(h)
    app.processEvents()
    wg = w.geometry()
    vh = sl.viewport().height()
    return wg.bottom() <= vh, wg.bottom(), vh


lo, hi = 40, 400
while lo < hi:
    mid = (lo + hi) // 2
    ok, _, _ = fully_visible(mid)
    if ok:
        hi = mid
    else:
        lo = mid + 1
ok, wb, vh = fully_visible(lo)
print("n=%d 不裁切最小列表高 = %d（widget bottom=%d, viewport h=%d）" % (n, lo, wb, vh))
print("旧公式 44n+8 =", 44 * n + 8)
print("候选公式 48n =", 48 * n, " 48n+2 =", 48 * n + 2)

# 幻影项场景（n=4，第 4 项无 widget）：同样量不裁切高度（前 3 行完整即可）
li = QListWidgetItem(sl)
li.setData(Qt.UserRole, "phantom")
sl.addItem(li)
n4 = sl.count()
last3 = sl.item(2)
w3 = sl.itemWidget(last3)


def fully_visible3(h):
    sl.setFixedHeight(h)
    app.processEvents()
    wg = w3.geometry()
    return wg.bottom() <= sl.viewport().height(), wg.bottom(), sl.viewport().height()


lo2, hi2 = 40, 400
while lo2 < hi2:
    mid = (lo2 + hi2) // 2
    ok, _, _ = fully_visible3(mid)
    if ok:
        hi2 = mid
    else:
        lo2 = mid + 1
ok, wb, vh = fully_visible3(lo2)
print("含幻影 n=%d 前三行不裁切最小高 = %d（widget bottom=%d, viewport h=%d）" % (n4, lo2, wb, vh))
print("GEO_PROBE_DONE")
