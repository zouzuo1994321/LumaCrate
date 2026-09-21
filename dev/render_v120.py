# -*- coding: utf-8 -*-
"""v1.12.0 定向渲染：合并后的「媒体库」侧边栏分组、服务管理页（无内置库痕迹）、新建媒体库对话框。

全部用临时库 + 临时 settings.json，不污染真实索引与配置。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

import database as db
import config as cfg
from main_window import MainWindow, load_style

TMP = tempfile.mkdtemp(prefix="lmc_render_v120_")
# 把数据库与配置都指向临时文件，避免污染真实索引 / settings.json
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")

db.init_db()
# 注入两个用户自命名媒体库，验证侧边栏合并后的「媒体库」分组 + 设置页列表
cfg.get_settings().add_library("Jav-VR", "混合", ["D:/vr"])
cfg.get_settings().add_library("我的电影", "电影", ["D:/movies"])
cfg.get_settings().save()

load_style(app)
win = MainWindow()
win.resize(1600, 900)
win.show()
app.processEvents()

OUT = os.path.join(ROOT, "dev", "screenshots_v120")
os.makedirs(OUT, exist_ok=True)


def shot(widget, name):
    for _ in range(3):
        app.processEvents()
    widget.grab().save(os.path.join(OUT, name))
    print("saved", name)


# 1) 主界面：侧边栏合并后的「媒体库」分组（含「＋ 新建媒体库」入口）
shot(win, "01_sidebar_merged.png")

# 2) 设置 -> 服务管理（媒体库）：无内置库痕迹、无恢复按钮
from ui_settings import SettingsDialog, LibraryEditDialog
sd = SettingsDialog(win)
sd.resize(1080, 780)
sd.show()
sd._show("服务管理")
app.processEvents()
shot(sd, "02_settings_service_libraries.png")

# 3) 新建媒体库对话框
dlg = LibraryEditDialog(win, {"name": "", "kind": "混合", "paths": []}, title="新建媒体库")
dlg.resize(440, 300)
dlg.show()
app.processEvents()
shot(dlg, "03_new_library_dialog.png")

print("OUT:", OUT)
