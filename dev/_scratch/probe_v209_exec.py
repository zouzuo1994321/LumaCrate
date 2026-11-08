# -*- coding: utf-8 -*-
"""量「执行」区里 按钮行 → 进度条 之间的竖向空隙（v2.0.9 反馈 4）。

用来确认那行空白到底是谁占的：`sc_mode_hint`（空 QLabel）？
还是进度条自身留的高度？量完再改，改完再用它复核。
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
TEMP = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "lmc_probe_v209")
os.makedirs(TEMP, exist_ok=True)
os.environ["LMC_CONFIG"] = os.path.join(TEMP, "settings.json")
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import QPoint                                   # noqa: E402
from PySide6.QtGui import QFontDatabase, QFont                       # noqa: E402
from PySide6.QtWidgets import QApplication                           # noqa: E402

app = QApplication(sys.argv)
for f in (r"C:\Windows\Fonts\msyh.ttc",):
    QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei", 9))

import main_window as mw            # noqa: E402
import ui_settings as us            # noqa: E402

mw.load_style(app)

dlg = us.SettingsDialog()
dlg.resize(us.SettingsDialog.DEF_W, us.SettingsDialog.DEF_H)
dlg.show()
app.processEvents()
try:
    dlg._show("演员刮削")
except Exception as e:
    print("切页失败:", e)
app.processEvents()
for _ in range(6):
    app.processEvents()
import time as _t
_t.sleep(0.4)
app.processEvents()

pg = dlg._pg_scraper
ref = dlg.mode_btns["full"]
host = pg


def geo(w):
    """控件在页面坐标系里的 (top, bottom)；未显示/无父返回 None。"""
    if w is None:
        return None
    try:
        if not w.isVisible():
            return "hidden"
        tl = w.mapTo(host, QPoint(0, 0))
        return (tl.y(), tl.y() + w.height())
    except RuntimeError:
        return "gone"


btn_b = geo(ref)
print("按钮行        ", btn_b, "高", ref.height())
print("sc_mode_hint  ", geo(dlg.sc_mode_hint),
      "h=", dlg.sc_mode_hint.height(), "sizeHint=", dlg.sc_mode_hint.sizeHint().height(),
      repr(dlg.sc_mode_hint.text()))
print("sc_prog       ", geo(dlg.sc_prog), "h=", dlg.sc_prog.height(),
      "sizeHint=", dlg.sc_prog.sizeHint().height())
print("sc_log        ", geo(dlg.sc_log), "h=", dlg.sc_log.height())
if isinstance(btn_b, tuple):
    pg_b = geo(dlg.sc_prog)
    if isinstance(pg_b, tuple):
        print(">>> 按钮底 → 进度条顶 的空隙 = %d px" % (pg_b[0] - btn_b[1]))
print("--- 执行组框内各子项（按 y 排序）---")
g3 = dlg.sc_prog.parentWidget()
while g3 is not None and g3.__class__.__name__ != "QGroupBox":
    g3 = g3.parentWidget()
print("组框:", g3, "h=", g3.height() if g3 else "-")
if g3 is not None:
    items = []
    for c in g3.children():
        if hasattr(c, "geometry") and hasattr(c, "isVisible"):
            try:
                if c.isVisible() and c.parentWidget() is g3:
                    tl = c.mapTo(host, QPoint(0, 0))
                    items.append((tl.y(), c.height(), c.__class__.__name__,
                                  getattr(c, "text", lambda: "")() if hasattr(c, "text") else ""))
            except Exception:
                pass
    for y, h, cls, txt in sorted(items):
        print("  y=%4d h=%2d  %-12s %s" % (y, h, cls, str(txt)[:24]))
dlg.close()
print("PROBE_DONE")
