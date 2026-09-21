# -*- coding: utf-8 -*-
"""诊断：首页列宽/布局在页面切换后是否真的持久化（真实 MainWindow 上下文）。

使用**临时数据库 + 临时 settings.json**，绝不触碰真实配置与索引。
"""
import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))

TMP = tempfile.mkdtemp(prefix="lmc_diag_")

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import config as cfg
cfg.config_path = lambda: os.path.join(TMP, "settings.json")   # 隔离真实配置
cfg._SETTINGS = None

import database as db
import scanner as scanner_mod
from main_window import MainWindow

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")

# 造几条媒体
for k, t in (("A-1", "片名一"), ("B-2", "片名二"), ("C-3", "片名三")):
    d = os.path.join(TMP, k)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, k + ".nfo"), "w", encoding="utf-8").write(
        f'<?xml version="1.0"?><movie><title>{t}</title><year>2020</year></movie>')
    open(os.path.join(d, k + ".mkv"), "wb").write(b"\x00" * 4096)
db.init_db()
scanner_mod.scan_library(TMP)

s = cfg.get_settings()
print("== 初始 home_column_widths =", s.home_column_widths)
print("== 初始 home_columns =", s.home_columns)

win = MainWindow()
win.resize(1600, 900)
win.show()
for _ in range(30):
    app.processEvents()


def widths_of(view):
    return [view.table.columnWidth(c) for c in range(view.table.columnCount())]


hv = win.stack.currentWidget()
print("== 视图类型 =", type(hv).__name__, " 列 key =", hv._cols)
print("== 初始实际列宽 =", widths_of(hv))

# 模拟用户拖动第 0 列分隔线到 111px，并触发去抖提交
hdr = hv.table.horizontalHeader()
hdr.resizeSection(0, 111)
for _ in range(20):
    app.processEvents()
hv._commit_width()
print("== 拖动后 settings.home_column_widths =", s.home_column_widths)
print("== 拖动后实际列宽 =", widths_of(hv))

# 记录分栏位置
try:
    hv.split.setSizes([700, 300])
    app.processEvents()
    print("== 设定后 splitter sizes =", hv.split.sizes())
except Exception as e:
    print("== splitter 操作失败:", e)

# 模拟页面切换：去别的页面再回首页
win.go(win._view_recent)
for _ in range(20):
    app.processEvents()
win.go(win._view_home)
for _ in range(60):
    app.processEvents()
hv2 = win.stack.currentWidget()
print("== 返回后视图类型 =", type(hv2).__name__)
print("== 返回后实际列宽 =", widths_of(hv2))
print("== 返回后 settings.home_column_widths =", s.home_column_widths)
try:
    print("== 返回后 splitter sizes =", hv2.split.sizes())
except Exception as e:
    print("== 返回后 splitter 读取失败:", e)

shutil.rmtree(TMP, ignore_errors=True)
print("== DONE")
