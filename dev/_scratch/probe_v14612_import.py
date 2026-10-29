# -*- coding: utf-8 -*-
"""v1.46.12 探针（二）：真导入的耗时拆分 —— DB 段 vs nfo 写回段。

仍然只在库副本上跑；nfo 写回用**临时副本**计时，绝不碰真实 nfo。
"""
import json
import os
import shutil
import sqlite3
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
TMP = r"C:/Users/zouzu/AppData/Local/Temp/probe_v14612"
DBP = os.path.join(TMP, "media_center.db")
SRC_JSON = os.path.join(TMP, "prefs.json")

import database as db                                    # noqa: E402
db.db_path = lambda: DBP
import applog                                            # noqa: E402
applog.log_dir = lambda: os.path.join(TMP, "logs")
import nfo_parser as nfo_mod                             # noqa: E402
import prefs as prefs_mod                                # noqa: E402

# 每次跑都用一份全新的库副本（上一次 dry_run 没写，但保险）
shutil.copyfile(os.path.join(ROOT, "index_data", "media_center.db"),
                os.path.join(TMP, "run.db"))
c0 = sqlite3.connect(os.path.join(TMP, "run.db"))
print("原始抽样 favorite 和:",
      c0.execute("SELECT SUM(COALESCE(favorite,0)) FROM media").fetchone()[0])
c0.close()
db.db_path = lambda: os.path.join(TMP, "run.db")

print("\n[1] nfo 写回的单文件成本（在临时副本上做，真实 nfo 不动）")
nfo_dir = os.path.join(TMP, "nfo")
os.makedirs(nfo_dir, exist_ok=True)
conn = db.get_conn()
srcs = [r["nfo_path"] for r in conn.execute(
    "SELECT nfo_path FROM media WHERE user_rating IS NOT NULL AND nfo_path IS NOT NULL "
    "LIMIT 40")]
srcs = [p for p in srcs if os.path.exists(p)]
copies = []
for i, p in enumerate(srcs):
    dst = os.path.join(nfo_dir, "n%02d.nfo" % i)
    if not os.path.exists(dst):
        shutil.copyfile(p, dst)
    copies.append(dst)
t0 = time.perf_counter()
for p in copies:
    nfo_mod.write_user_rating(p, 4.5)
per = (time.perf_counter() - t0) / max(1, len(copies))
print("  样本 %d 个，单文件 %.2f ms（含 ET.parse+indent+write，本地盘）"
      % (len(copies), per * 1000))
print("  真实 nfo 在 X: 盘，抽样 os.path.exists 平均 ~2ms/次，"
      "write_user_rating 有 3 次盘操作 → 单文件约 %.1f ms" % (per * 1000 + 6))

print("\n[2] 真导入（不 dry_run）的 DB 段耗时 —— 把 nfo 写回打桩成 no-op")
_real_write = nfo_mod.write_user_rating
nfo_mod.write_user_rating = lambda *a, **k: False
try:
    t0 = time.perf_counter()
    r = prefs_mod.import_prefs(SRC_JSON)
    dt_db = time.perf_counter() - t0
finally:
    nfo_mod.write_user_rating = _real_write
print("  端到端 %.3fs  %s" % (dt_db, {k: r.get(k) for k in
                                    ("media_ok", "people_ok", "nfo_written")}))

print("\n[3] 估算真实导入总时长")
data = json.load(open(SRC_JSON, encoding="utf-8"))
n_rate = sum(1 for x in data["media"] if x.get("user_rating") is not None)
n_rate_dup = 0
print("  带评分的条目 %d，每条要写一个 nfo" % n_rate)
est = dt_db + n_rate * (per + 0.006)
print("  估算 ≈ %.1fs（DB %.2fs + nfo %.2fs）" % (est, dt_db, n_rate * (per + 0.006)))
print("  → 这个时长全部发生在 GUI 线程里，期间不处理任何消息")
print("    Windows 对 5 秒不泵消息的窗口直接打「未响应」")
