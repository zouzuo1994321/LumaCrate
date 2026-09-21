# -*- coding: utf-8 -*-
"""测出侧边栏导航条目的客户区坐标，供 dev/live_verify.py 的 SIDEBAR 使用。

v1.23.0：品牌区由「logo 竖排在上」改为「logo 与标题横向平齐」，整列 y 又变了，
所以每次动 _brand() 都要重测一次 —— 别再靠肉眼看截图量像素。
v1.24.0：分类组多了「导演库」、导航多了「智能推荐」，整列整体下移；这里**顺便建一个
临时媒体库**，让「媒体库」分组头也参与布局，第一个库行的 y 就能直接量到（不再靠推算）。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_BACKDROP"] = "1"

import tempfile  # noqa: E402
TMP = tempfile.mkdtemp(prefix="lmc_probe_sidebar_")
os.makedirs(os.path.join(TMP, "index_data"), exist_ok=True)

import database as db  # noqa: E402
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
import applog  # noqa: E402
applog.log_dir = lambda: os.path.join(TMP, "logs")
import config as cfg  # noqa: E402
cfg.config_path = lambda: os.path.join(TMP, "settings.json")   # 别碰用户真实配置
cfg._SETTINGS = None
db.init_db()

from PySide6.QtWidgets import QApplication, QAbstractButton  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtCore import QPoint  # noqa: E402

app = QApplication.instance() or QApplication([])
for f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import main_window as mw  # noqa: E402
mw.load_style(app)

TARGETS = ["首页", "最近播放", "我的收藏", "智能推荐", "文件夹", "合集",
           "全部", "演员库", "导演库", "电影"]

# 建一个叫「电影」的临时库 —— 只为让「媒体库」分组头出现，第一个库行才量得到
_cs = cfg.get_settings()
if not _cs.library_names():
    _cs.add_library("电影", "电影", [os.path.join(TMP, "lib")])

win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
win.resize(1920, 1080)
win.show()
app.processEvents()

found = {}
for w in win.findChildren(QAbstractButton):
    t = (w.text() or "").strip()
    if t in TARGETS and t not in found:
        # 相对窗口客户区（live_verify 用的是客户区坐标）
        p = w.mapTo(win, QPoint(w.width() // 2, w.height() // 2))
        found[t] = (p.x(), p.y())

print("SIDEBAR = {")
for t in TARGETS:
    if t in found:
        print('    "%s": (%d, %d),' % (t, found[t][0], found[t][1]))
    else:
        print('    # 未找到: %s' % t)
print("}")
missing = [t for t in TARGETS if t not in found]
print("MISSING:", missing)
