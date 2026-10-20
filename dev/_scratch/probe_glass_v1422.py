# -*- coding: utf-8 -*-
"""v1.42.2 关键实验：用**用户真实外观**（磨砂玻璃/中/#e2659a）离屏渲染刮削页，
与用户截图逐区比对像素，并量准 列表高/行距/空档。"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QGroupBox
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_glass_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
# 用户真实外观
cfg.DEFAULT_APPEARANCE = dict(cfg.DEFAULT_APPEARANCE)
st = cfg.Settings()
st.appearance.update({"mode": "磨砂玻璃", "level": "中", "accent": "#e2659a"})
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
print("alphas:", cfg.appearance_alphas(st.appearance))


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
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

pg = dlg._pg_scraper
seen = 0
while hasattr(pg, "widget") and seen < 4:
    inner = pg.widget()
    if inner is None:
        break
    pg = inner
    seen += 1

sl = dlg.src_list
print("list h =", sl.height(), "count =", sl.count())
for i in range(sl.count()):
    w = sl.itemWidget(sl.item(i))
    print(f"  row{i}: y={w.y()} h={w.height()} pitch="
          f"{sl.itemWidget(sl.item(i+1)).y() - w.y() if i + 1 < sl.count() else '-'}")
# 悬停第一行，看悬停带高度（对应用户截图里的 44px 带）
sl.item(1).setSelected(True)
app.processEvents()
print("选中 row1 后 list h =", sl.height())

# 出图：页面 + 列表局部
pix = pg.grab()
pix.save(os.path.join(TMP, "glass_page.png"))
lp = sl.mapTo(pg, QPoint(0, 0))
sl.grab().save(os.path.join(TMP, "glass_list.png"))
print("page saved; list pos in page:", lp.x(), lp.y(), "size:", sl.width(), sl.height())
print("TMP:", TMP)
print("GLASS_PROBE_DONE")
