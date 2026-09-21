# -*- coding: utf-8 -*-
"""UI 离屏冒烟测试：构造主窗口与子对话框，捕获导入/构建错误。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PySide6.QtWidgets import QApplication
import database as db
import version as ver
from main_window import MainWindow, load_style, DetailDialog, ActorDialog, AboutDialog

db.init_db()
app = QApplication(sys.argv)
load_style(app)
win = MainWindow()
win.show()
print("MAIN WINDOW OK:", win.windowTitle())

# 若库里有数据则尝试构造详情/演员对话框
movies = db.movies()
if movies:
    d = DetailDialog(movies[0])
    print("DETAIL DIALOG OK")
    people = db.all_people()
    if people:
        a = ActorDialog(people[0]["id"])
        print("ACTOR DIALOG OK")
about = AboutDialog()
print("ABOUT DIALOG OK:", about.windowTitle())
win.close()
print("UI_SMOKE_OK")
