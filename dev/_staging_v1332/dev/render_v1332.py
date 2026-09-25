# -*- coding: utf-8 -*-
"""v1.33.2 智能推荐 A+B 效果图（离屏，用真数据库跑对比）。

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1332.py', run_name='__main__')"

产物 → dev/screenshots_v1332/
    01_recommend_wall.png  「智能推荐」页面（真实库跑 24 部，看四位是否还霸屏）
    02_profile_top.png     个人画像前 24 项（看是标签主导还是演员主导）

安全：db / config / 日志全指向临时目录，绝不碰真实索引。
      若要跑真库，另用 `--real` 环境变量 LMC_REAL_DB 指定只读副本。
"""
import os
import sys
import time
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(ROOT, "dev"))

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1332")
INDEX = os.path.join(TMP, "index_data")
AVATARS = os.path.join(TMP, "people_photos")
OUT = os.path.join(ROOT, "dev", "screenshots_v1332")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(AVATARS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def _wipe(p):
    if not os.path.exists(p):
        return
    import ctypes
    ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
    ctypes.windll.kernel32.DeleteFileW(p)


for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    _wipe(_f)

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

# 真实库副本（只读）：由 LMC_REAL_DB 指定；没有就建临时空库
_REAL = os.environ.get("LMC_REAL_DB", "")
if _REAL and os.path.isfile(_REAL):
    db.db_path = lambda: _REAL
    print("真库：", _REAL)
else:
    db.db_path = lambda: os.path.join(INDEX, "media_center.db")

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import version as ver

db.init_db()
_s0 = cfg.get_settings()
_s0.scraper["photo_dir"] = AVATARS
_s0.save()

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw

mw.load_style(app)

import shots_lib_stub as SL

MADE = []


def pump(n=8):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


def save(pm, name, bg=None, corner="br"):
    p = os.path.join(OUT, name)
    pm.save(p)
    im = Image.open(p).convert("RGBA")
    if bg is not None:
        base = Image.new("RGBA", im.size, tuple(bg) + (255,))
        im = Image.alpha_composite(base, im)
    im = im.convert("RGB")
    im = SL.watermark(im, corner=corner)
    im.save(p)
    MADE.append(name)
    print("  %-30s %dx%d" % (name, im.width, im.height))


# ============================================================ 推荐页
print("== 智能推荐页 ==")
try:
    win = mw.MainWindow()
    win.resize(1920, 1080)
    win.show()
    pump(30)
    try:
        win._nav_builders()["smart"]()
    except Exception as e:
        print("     导航失败：%s" % e)
    pump(90)
    save(win.grab(), "01_recommend_wall.png", bg=(27, 26, 24))
    try:
        win.close()
    except Exception:
        pass
except Exception as e:
    import traceback
    print("     推荐页抓图失败：%s" % e)
    traceback.print_exc()

pump(8)
print("\n共 %d 张 → %s" % (len(MADE), OUT))
print("版本：%s (Build %s)" % (ver.VERSION, ver.BUILD))
