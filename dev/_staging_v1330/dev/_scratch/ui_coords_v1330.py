# -*- coding: utf-8 -*-
"""v1.33.0 界面坐标探针：主窗顶部「关于」按钮 + 四页侧栏入口。

产出（合并进 C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json）：
  - `main_about_btn`：主窗工具栏最右的「关于」按钮中心（对话坐标）
  - `main_sidebar_v1330`：演员库 / 导演库 / 最近播放 / 合集 四项侧栏条目

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/_scratch/ui_coords_v1330.py', run_name='__main__')"
"""
import json
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="lmc_coords1330_")
INDEX = os.path.join(TMP, "index_data")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import backdrop

backdrop.auto_apply = lambda w, *a, **k: None

import main_window as mw

mw.load_style(app)

win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
for _ in range(40):
    app.processEvents()

res = {}
COORDS = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"
try:
    with open(COORDS, encoding="utf-8") as f:
        res = json.load(f)
except Exception:
    res = {}

# ---- 顶部工具栏的四个按钮：扫描 / 刷新 / 工具 / 关于 ----
try:
    btns = [b for b in win.findChildren(QPushButton)
            if b.text() in ("扫描媒体库", "扫描", "刷新", "工具", "关于")]
    for b in btns:
        c = b.mapTo(win, QPoint(b.width() // 2, b.height() // 2))
        key = {"关于": "main_about_btn", "工具": "main_settings_btn",
               "刷新": "main_refresh_btn"}.get(b.text())
        print("  %-8s -> (%d, %d)  size=%dx%d" % (b.text(), c.x(), c.y(),
                                                  b.width(), b.height()))
        if key and b.text() == "关于":
            res[key] = [int(c.x()), int(c.y())]
        elif key and key not in res:
            res[key] = [int(c.x()), int(c.y())]
except Exception as e:
    print("  找按钮失败：%s" % e)

# ---- 侧栏四项 ----
try:
    nav = {}
    for key in ("演员库", "导演库", "最近播放", "合集", "首页"):
        for b in win.findChildren(QPushButton):
            if b.text().startswith(key):
                c = b.mapTo(win, QPoint(b.width() // 2, b.height() // 2))
                nav[key] = [int(c.x()), int(c.y())]
                break
    res["main_sidebar_v1330"] = nav
    print("  侧栏：%s" % nav)
except Exception as e:
    print("  找侧栏失败：%s" % e)

with open(COORDS, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("\n已合并写入 %s" % COORDS)
print("keys: %s" % sorted(res))
try:
    win.close()
except Exception:
    pass
