# -*- coding: utf-8 -*-
"""v1.40.15 真机取像：抓真实窗口像素，看弹层到底有没有被画出「顶部关闭栏」
============================================================================
前两个探针证明：Qt.Popup（旧）/ Qt.Popup|FramelessWindowHint（新）在 Win32 层
都 **没有** 非客户区（无 WS_CAPTION，非客户区高 = 0px）。那用户截图里那条
「替换「XX」 … ×」就不是原生标题栏。本脚本直接把**桌面像素**抓下来，实锤用户看到的是什么。

跑法（务必用 E 盘绝对路径；不要设 QT_QPA_PLATFORM=offscreen）：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/probe_popup_shot.py"
"""
import os
import sys
import tempfile

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ.pop("QT_QPA_PLATFORM", None)
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer, QPoint

# 临时索引库（沿用冒烟那份；缺则补一条「未知演员」）
_tmp = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1415", "index_data")
os.makedirs(_tmp, exist_ok=True)
import database as db
import applog as applog_mod
db.db_path = lambda: os.path.join(_tmp, "media_center.db")
applog_mod.log_dir = lambda: _tmp
db.init_db()
_c = db.get_conn()
if not _c.execute("SELECT 1 FROM people WHERE name='未知演员'").fetchone():
    _c.execute("INSERT INTO people (name, role_type) VALUES ('未知演员','Actor')")
    _c.commit()

app = QApplication([])
try:
    from PySide6.QtGui import QFontDatabase
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
except Exception:
    pass
try:
    import config as cfg
    import main_window as mw
    mw.load_style(app, cfg.DEFAULT_APPEARANCE)
except Exception as e:
    print("[warn] QSS:", e)

import ui_hero as uh

dlg = uh.PersonSearchDialog(initial="未知演员", old_name="未知演员", on_pick=lambda p: None)
dlg.move_to(QPoint(360, 320))
dlg.show()


def shot():
    scr = app.primaryScreen()
    vis = dlg.isVisible()
    geo = dlg.frameGeometry()
    print("弹层是否可见：", vis, " frameGeometry：", geo.x(), geo.y(), geo.width(), geo.height())
    x = max(0, geo.x() - 50)
    y = max(0, geo.y() - 70)
    w = geo.width() + 100
    h = geo.height() + 140
    pm = scr.grabWindow(0, x, y, w, h)     # 抓桌面区域（含任何非客户区/外壳绘制的条）
    out = os.path.join(ROOT, "dev", "probe_popup_shot.png")
    pm.save(out)
    print("已保存：", out, pm.width(), "x", pm.height())
    dlg.reject()
    app.quit()


QTimer.singleShot(700, shot)
app.exec()
print("DONE")
