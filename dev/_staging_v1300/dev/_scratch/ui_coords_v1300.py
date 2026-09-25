# -*- coding: utf-8 -*-
"""v1.30.0 新增控件坐标探针（离屏，1000x900 同真机）。

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/_scratch/ui_coords_v1300.py', run_name='__main__')"

产出：追加到 `C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json` 的 `v1300` 段，
供 `dev/live_verify_v1300.py` 真机点击用（真机点不到坐标就会静默落在空处）。
"""
import json
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="lmc_coords1300_")
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

# 给「手动修改」造一条可检索的记录，否则列表是空的、首行坐标无从谈起
_c = db.get_conn()
try:
    _c.execute("INSERT INTO media(kind,title,sort_title,year,file_path,library) "
               "VALUES(?,?,?,?,?,?)",
               ("movie", "验收用影片", "验收用影片", 2024,
                "X:/__probe__/VERIFY-001.mp4", "验收库"))
    _c.commit()
finally:
    _c.close()

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import backdrop

backdrop.auto_apply = lambda w, *a, **k: None

from ui_settings import SettingsDialog


def center(widget, ref):
    p = widget.mapTo(ref, QPoint(widget.width() // 2, widget.height() // 2))
    return [int(p.x()), int(p.y())]


dlg = SettingsDialog()
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1000, 900)
dlg.show()
app.processEvents()

res = {}

dlg._show("手动修改")
app.processEvents()
man = dlg.stack.currentWidget().widget()
res["manual_search_btn"] = None
for b in man.findChildren(QPushButton):
    if b.text() == "搜索":
        res["manual_search_btn"] = center(b, dlg)
    if b.text().startswith("保存"):
        res["manual_save_btn"] = center(b, dlg)
res["manual_list"] = center(man.list, dlg)
res["manual_list_count"] = man.list.count()
if man.list.count():
    it = man.list.item(0)
    r = man.list.visualItemRect(it)
    p = man.list.mapTo(dlg, QPoint(r.center().x(), r.center().y()))
    res["manual_first_row"] = [int(p.x()), int(p.y())]

dlg._show("图像检测")
app.processEvents()
img = dlg.stack.currentWidget().widget()
res["image_run_btn"] = center(img.run_btn, dlg)
res["image_tree"] = center(img.tree, dlg)
res["image_lib_combo"] = center(img.lib_box, dlg)

# 主窗「工具」按钮（真机上要用它开工具窗）
import main_window as mw

win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
for b in win.findChildren(QPushButton):
    if b.text() in ("工具", "设置"):
        res["main_settings_btn"] = center(b, win)
        break
res["main_size"] = [win.width(), win.height()]
res["dialog_size"] = [dlg.width(), dlg.height()]

print(json.dumps(res, ensure_ascii=False, indent=1))

# 合并进 live_verify 用的坐标文件（保留原有 dialog_nav 等）
dst = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"
try:
    with open(dst, encoding="utf-8") as f:
        old = json.load(f)
except Exception:
    old = {}
old.setdefault("v1300", {}).update(res)
with open(dst, "w", encoding="utf-8") as f:
    json.dump(old, f, ensure_ascii=False, indent=1)
print("\n已合并到 %s" % dst)
