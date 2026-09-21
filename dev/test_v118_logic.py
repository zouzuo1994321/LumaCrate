# -*- coding: utf-8 -*-
"""v1.18.0 逻辑验证（临时库，不污染真实索引）。
覆盖：#96 选集代表取名称排序最靠前；#95 选集横版缩略图路径；#98 实时运行状态汇总。
运行：python -u dev/test_v118_logic.py
"""
import os
import sys
import tempfile
import shutil

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, SRC)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import applog
import scanner

# ---------- 临时环境 ----------
TMP = tempfile.mkdtemp(prefix="lmc_v118_")
TMPDB = os.path.join(TMP, "index_data", "media_center.db")
TMPLOG = os.path.join(TMP, "index_data", "logs")
os.makedirs(os.path.dirname(TMPDB), exist_ok=True)
os.makedirs(TMPLOG, exist_ok=True)
db.db_path = lambda: TMPDB
applog.log_dir = lambda: TMPLOG

db.init_db()

ok = True
def check(name, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))
    if not cond:
        ok = False

# ---------- #96 选集代表口径：名称最靠前，而非 cd 号最小 ----------
D = os.path.join(TMP, "movie_a")
os.makedirs(D, exist_ok=True)
f1 = os.path.join(D, "M CD1.mp4")   # cd 最小，但名称靠后
f2 = os.path.join(D, "A CD2.mp4")   # cd 较大，但名称最靠前
open(f1, "w").close()
open(f2, "w").close()
db.insert_media(file_path=f1, title="M CD1", kind="movie", library="测试库",
                nfo_path=f1 + ".nfo", poster=None)
db.insert_media(file_path=f2, title="A CD2", kind="movie", library="测试库",
                nfo_path=f2 + ".nfo", poster=None)

scanner.group_cd_sets(D)

reps = db.search_media(library="测试库")  # 顶层条目（parent_id IS NULL）
top = [m for m in reps if m.get("parent_id") is None]
check("#96 选集代表唯一(顶层1条)", len(top) == 1, f"top={len(top)}")
if top:
    rep = top[0]
    check("#96 代表=名称最靠前(A CD2)", os.path.basename(rep["file_path"]) == "A CD2.mp4",
          f"rep={os.path.basename(rep['file_path'])}")
    check("#96 代表标题已去 CD 标记", rep.get("title") == "A", f"title={rep.get('title')!r}")
    # 子片应指向代表
    kids = db.children_of(rep["id"])
    check("#96 子片归属正确", len(kids) == 1 and kids[0]["episode"] == 1,
          f"kids={[(k['file_path'], k['episode']) for k in kids]}")

# ---------- #95 选集横版缩略图路径 ----------
from ui_hero import _part_thumb_path
vf = os.path.join(D, "X CD1.mp4")
open(vf, "w").close()
thumb = os.path.join(D, "X CD1-thumb.jpg")
open(thumb, "w").close()
check("#95 存在 thumb 时返回路径", _part_thumb_path({"file_path": vf}) == thumb)
os.remove(thumb)
check("#95 无 thumb 时返回 None", _part_thumb_path({"file_path": vf}) is None)
check("#95 无 file_path 时返回 None", _part_thumb_path({}) is None)

# ---------- #98 实时运行状态汇总 ----------
st = db.runtime_status()
need = ("stats", "library_counts", "top_total", "pragmas", "db_path")
check("#98 runtime_status 字段齐全", all(k in st for k in need), str(list(st.keys())))
check("#98 顶层总数=1", st.get("top_total") == 1, f"top={st.get('top_total')}")
check("#98 数据库模式含 WAL", str(st["pragmas"].get("journal_mode")).upper() == "WAL",
      f"jm={st['pragmas'].get('journal_mode')}")
check("#98 统计含电影数", st["stats"].get("movies") == 1, f"movies={st['stats'].get('movies')}")

db.close_all()
shutil.rmtree(TMP, ignore_errors=True)
print("\nRESULT:", "ALL PASS" if ok else "HAS FAILURE")
sys.exit(0 if ok else 1)
