# -*- coding: utf-8 -*-
"""定位「打开详情页后 media.tags 被写成 genres」的真凶：
用真实库的**副本**跑源码，给两个可能的写入函数套上 traceback 记录，再打开一部片的详情页。
"""
import os
import shutil
import sys
import tempfile
import traceback

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_trace_v1469"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

SRC_DB = os.path.join(ROOT, "index_data", "media_center.db")
DST_DB = os.path.join(TMP, "copy.db")
if not os.path.exists(DST_DB) or os.path.getmtime(DST_DB) < os.path.getmtime(SRC_DB):
    print("复制真实库 →", DST_DB, flush=True)
    shutil.copy(SRC_DB, DST_DB)

import config as cfg
import applog

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import database as db

db.db_path = lambda: DST_DB
db._MEDIA_COLS = None

HITS = []

_orig_up = db.upsert_media_by_path
_orig_set = db.set_media_tags


def up(*a, **kw):
    if "tags" in kw:
        HITS.append(("upsert tags=%r" % kw.get("tags"), traceback.format_stack()[-4:]))
    return _orig_up(*a, **kw)


def st(*a, **kw):
    HITS.append(("set_media_tags %r" % (a,), traceback.format_stack()[-4:]))
    return _orig_set(*a, **kw)


db.upsert_media_by_path = up
db.set_media_tags = st

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

import main_window as mw

mw.load_style(app)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
for _ in range(30):
    app.processEvents()

# 找一部 tags 为空的片
con = db.get_conn()
row = con.execute("SELECT id,title,tags,genres FROM media WHERE IFNULL(tags,'')='' "
                  "AND parent_id IS NULL AND file_path IS NOT NULL LIMIT 1").fetchone()
con.close()
print("目标:", row["id"], row["title"][:30], "tags=", repr(row["tags"]), flush=True)
mid = row["id"]

before = db.get_media(mid).get("tags")
HITS.clear()
win._open_media(db.get_media(mid))
for _ in range(60):
    app.processEvents()

after = db.get_media(mid).get("tags")
print("打开详情前后：before=%r after=%r" % (before, after), flush=True)
print("检测到的写入:", len(HITS), flush=True)
for tag, stk in HITS:
    print("---", tag, flush=True)
    print("".join(stk), flush=True)

print("TRACE_DONE", flush=True)
