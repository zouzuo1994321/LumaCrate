# -*- coding: utf-8 -*-
"""v1.34.0 界面预览出图 —— 智能推荐「引导向量」输入行 + 「从画像自动填充」小面板

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1340.py', run_name='__main__')"

**安全约定**：临时库 + 临时 settings，不碰真实索引 / 真实配置。
出图前把半透明层 alpha_composite 到容器底色（否则 convert("RGB") 会把透明层显示成纯白，图会骗人）。
"""
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1340")
INDEX = os.path.join(TMP, "index_data")
OUT = os.path.join(ROOT, "dev", "shots_v1340")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(OUT, exist_ok=True)


import ctypes


def _wipe(p):
    try:
        if os.path.exists(p):
            ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
            ctypes.windll.kernel32.DeleteFileW(str(p))
    except Exception:
        pass


for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    _wipe(_f)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

db.init_db()

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei UI", 9))

import main_window as mw
import ui_settings as uis

mw.load_style(app)


def _alpha_to_base(widget, base=(18, 20, 26)):
    """grab() 出来是透明底图 —— 先 alpha_composite 到容器底色再存，否则图骗人。"""
    img = widget.grab().toImage()
    from PySide6.QtGui import QImage, QPainter, QColor
    out = QImage(img.size(), QImage.Format_ARGB32_Premultiplied)
    out.fill(QColor(*base))
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    return out


def _save(img, name):
    path = os.path.join(OUT, name)
    ok = img.save(path, "PNG")
    print("[SHOT] %s  %s" % ("OK " if ok else "ERR", path))
    return path


# ---------------------------------------------------------------- 造数据
_FAV_TAGS = ["巨乳", "单体作品", "苗条", "长腿", "美乳", "熟女", "痴女"]
_STUDIOS = ["MOODYZ", "S1 NO.1 STYLE", "Premium", "IdeaPocket"]
_ACTORS = ["さつき芽衣", "新井リマ", "森日向子", "君岛みお", "橋本ありな",
           "三上悠亜", "葵つかさ", "Julia"]
_DIRECTORS = ["山田太郎", "鈴木一郎", "佐藤健二"]

_pids = {}
for _i, _a in enumerate(_ACTORS):
    _pids[("act", _a)] = db.upsert_person(_a, "Actor")
for _d in _DIRECTORS:
    _pids[("dir", _d)] = db.upsert_person(_d, "Director")

for _i in range(48):
    _t = _FAV_TAGS[_i % len(_FAV_TAGS)]
    _s = _STUDIOS[_i % len(_STUDIOS)]
    _a = _ACTORS[_i % len(_ACTORS)]
    _d = _DIRECTORS[_i % len(_DIRECTORS)]
    _mid = db.insert_media(
        title="作品样本 %03d" % _i, kind="movie", library="影片库",
        genres="%s, 片商:%s, 系列:样本系列%d" % (_t, _s, _i % 5))
    db.link_media_person(_mid, _pids[("act", _a)], "actor", 0)
    db.link_media_person(_mid, _pids[("dir", _d)], "director", 0)

print("[数据] 媒体 %d 部 / 演员 %d 位 / 导演 %d 位"
      % (db.count_media(), len(_ACTORS), len(_DIRECTORS)))

_c = db.get_conn()
_c.execute("UPDATE media SET favorite=1 WHERE id IN (SELECT id FROM media LIMIT 20)")
_c.commit()

# ---------------------------------------------------------------- 主窗 + 推荐墙
win = mw.MainWindow()
win.resize(1920, 1040)
win.show()
import time
_t0 = time.time()
while time.time() - _t0 < 2.2:
    app.processEvents()
    time.sleep(0.012)

# 真跑一次推荐（拿到真实 picks）
_res = mw.rec_mod.recommend(page=1, limit=24, algo="normal")
win._smart_picks = mw.MainWindow._hydrate_picks(
    [{"id": r["id"]} for r in (_res.get("picks") or [])][:24])
win._smart_algo = "normal"
win._smart_res = _res
win._smart_guides = []
_pg = win._smart_wall()
win.stack.addWidget(_pg)
win.stack.setCurrentWidget(_pg)
for _ in range(8):
    app.processEvents()
print("[推荐] 候选池 %s / 命中 %d 部"
      % (_res.get("pool"), len(win._smart_picks)))

_save(_alpha_to_base(_pg), "01_guide_bar_empty.png")

# 加两条引导（演员 + 标签），看 chips 与状态文案
win._smart_guides = [
    {"token": "a:%s" % _ACTORS[0], "dim": "actor", "key": _ACTORS[0], "weight": 2.0},
    {"token": "t:巨乳", "dim": "tag", "key": "巨乳", "weight": 4.0},
]
win._refresh_guides()
for _ in range(8):
    app.processEvents()
_save(_alpha_to_base(_pg), "02_guide_bar_with_chips.png")

# 只抓引导行本身（放大看细节）
_bar = None
for w in _pg.findChildren(QWidget):
    if w.objectName() == "guide_chips":
        _bar = w.parentWidget()
        break
if _bar is not None:
    _save(_alpha_to_base(_bar), "03_guide_bar_zoom.png")

# ---------------------------------------------------------------- 自动填充面板
dlg = uis.AutoFillDialog()
for _ in range(6):
    app.processEvents()
_save(_alpha_to_base(dlg), "04_autofill_default.png")

# 改一改：关掉系列、标签取前 50 权重 2.0、范围切「我的收藏」
dlg.dim_rows["series"][0].setChecked(False)
dlg.dim_rows["tag"][1].setValue(50)
dlg.dim_rows["tag"][2].setValue(2.0)
dlg.cb_scope.setCurrentIndex(dlg.cb_scope.findData("__FAV__"))
for _ in range(6):
    app.processEvents()
_save(_alpha_to_base(dlg), "05_autofill_favorites.png")

# 预览写库内容
dlg._show_preview("我的收藏", dlg._plan())
for _ in range(6):
    app.processEvents()

print("\n[完成] 出图目录：%s" % OUT)
