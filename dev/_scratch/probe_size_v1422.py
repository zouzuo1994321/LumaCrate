# -*- coding: utf-8 -*-
"""v1.42.2 定位实验：不同对话框尺寸下，IMDB 行底→按钮行顶的空档是多少。
用户真机截图显示 ~44px，离屏 1320x960 只有 6px → 逐一试小屏/矮屏收敛尺寸。"""
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

TMP = tempfile.mkdtemp(prefix="lmc_size_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow, load_style
from ui_settings import SettingsDialog

load_style(app)


class _FakeScr:
    def __init__(self, w, h):
        self._w, self._h = w, h

    def availableGeometry(self):
        return QRect(0, 0, self._w, self._h)

    def geometry(self):
        return QRect(0, 0, self._w, self._h + 80)


def measure(dw, dh, scr_w, scr_h):
    SettingsDialog.screen = lambda self: _FakeScr(scr_w, scr_h)
    win = MainWindow()
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    win.resize(1920, 1080)
    win.show()
    app.processEvents()
    dlg = SettingsDialog(win)
    dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
    dlg.resize(dw, dh)
    dlg.show()
    app.processEvents()
    for k, b in dlg.sub_btns.items():
        if "刮削" in k:
            b.click()
            break
    app.processEvents()
    app.processEvents()

    sl = dlg.src_list
    g0 = [g for g in dlg.findChildren(QGroupBox) if "数据源" in g.title()][0]
    # 末行底（列表内坐标）
    n = sl.count()
    last = sl.itemWidget(sl.item(n - 1))
    last_bottom_in_list = last.y() + last.height()
    # 按钮行
    btns = None
    for c in g0.children():
        if type(c).__name__ == "QWidget" and c.layout() is not None:
            names = []
            for i in range(c.layout().count()):
                w = c.layout().itemAt(i).widget()
                if w is not None and hasattr(w, "text"):
                    names.append(w.text())
            if any("测试全部数据源" in t for t in names):
                btns = c
                break
    btns_top_in_g0 = btns.mapTo(g0, QPoint(0, 0)).y() if btns else -1
    list_bottom_in_g0 = sl.mapTo(g0, QPoint(0, 0)).y() + sl.height()
    rows_h = [sl.itemWidget(sl.item(i)).height() for i in range(n)]
    # 每行的实际槽位（pitch）
    ys = [sl.itemWidget(sl.item(i)).y() for i in range(n)]
    pitch = (ys[1] - ys[0]) if n > 1 else 0
    print(f"dlg={dw}x{dh} screen={scr_w}x{scr_h} -> 实际窗={dlg.width()}x{dlg.height()} "
          f"list_h={sl.height()} rows={rows_h} pitch={pitch} "
          f"list底( g0坐标)={list_bottom_in_g0} 按钮顶={btns_top_in_g0} "
          f"空档={btns_top_in_g0 - list_bottom_in_g0 if btns else '?'}")
    dlg.close()
    win.close()
    return btns_top_in_g0 - list_bottom_in_g0 if btns else None


# 基线：大屏
measure(1320, 960, 2560, 1392)
# 小屏收敛（1366x768 笔记本）：w=1326->1320, h=728
measure(1320, 728, 1366, 768)
# 更小屏（1280x720）：w=1240, h=680
measure(1240, 680, 1280, 720)
# 窄屏（1152x864）：w=1112
measure(1112, 728, 1152, 864)
print("SIZE_PROBE_DONE")
