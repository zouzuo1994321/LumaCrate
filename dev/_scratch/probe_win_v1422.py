# -*- coding: utf-8 -*-
"""v1.42.2 探针 5：Windows 平台复测 + clear() 泄漏 + 移动重建循环。

离屏与用户真机的唯一剩余差异是平台。Windows 平台下：
  1. 真实对话框 src_list 的 count/height/逐项 widget
  2. clear() 之后旧 item widget 是否还挂在 viewport 上（幽灵行根源）
  3. 模拟用户点「↑/↓」触发 _move_source → _rebuild_source_list 后的 count/height
"""
import os
import sys
import tempfile

os.environ.pop("QT_QPA_PLATFORM", None)      # 用 Windows 平台
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_win_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
st = cfg.Settings()
st.appearance.update({"mode": "磨砂玻璃", "level": "中", "accent": "#e2659a"})
# 灌入用户真实 3 源
st.scraper["sources"] = ["avbase", "minnano", "imdb"]
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


def report(tag):
    sl = dlg.src_list
    kids = sl.viewport().findChildren(object)
    print("[%s] count=%d h=%d  viewport子对象=%d"
          % (tag, sl.count(), sl.height(), len(kids)))
    for i in range(sl.count()):
        it = sl.item(i)
        w = sl.itemWidget(it)
        print("     item%d key=%r widget=%s" % (i, it.data(Qt.UserRole), w is not None))
    return sl


report("初始")

# 模拟用户点「↑」（把 minnano 上移）→ 触发 _rebuild_source_list
dlg._move_source("minnano", -1)
app.processEvents()
report("上移minnano后")
print("     settings.sources =", st.scraper.get("sources"))

# 再点一次「↓」移回去
dlg._move_source("minnano", 1)
app.processEvents()
report("下移minnano后")

# 直接手动 clear + 重建循环 3 次
for i in range(3):
    dlg._rebuild_source_list()
    app.processEvents()
report("手动重建x3后")

print("WIN_PROBE_DONE")
