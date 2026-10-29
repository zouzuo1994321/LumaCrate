# -*- coding: utf-8 -*-
"""v1.46.12 探针：偏好导入/导出为什么让界面「未响应」——按阶段计时。

只读真实库的**副本**，不改任何真实数据（import 一律 dry_run=True）。
"""
import os
import shutil
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = r"C:/Users/zouzu/AppData/Local/Temp/probe_v14612"
os.makedirs(TMP, exist_ok=True)
copied = os.path.join(TMP, "media_center.db")
if not os.path.exists(copied):
    t0 = time.perf_counter()
    shutil.copyfile(os.path.join(ROOT, "index_data", "media_center.db"), copied)
    print("复制库 %.1f MB 用 %.2fs" % (os.path.getsize(copied) / 1048576,
                                       time.perf_counter() - t0))

import database as db                                    # noqa: E402
db.db_path = lambda: copied                              # 全程只在副本上操作

import applog                                            # noqa: E402
applog.log_dir = lambda: os.path.join(TMP, "logs")       # 别写真实日志

import duplicates                                        # noqa: E402
import prefs as prefs_mod                                # noqa: E402
import nfo_parser as nfo_mod                             # noqa: E402


def t(label, fn):
    t0 = time.perf_counter()
    r = fn()
    dt = time.perf_counter() - t0
    print("  %-34s %7.3f s   %s" % (label, dt, r if not isinstance(r, list) else
                                    "list[%d]" % len(r)))
    return dt, r


conn = db.get_conn()
print("\n[A] 导出链路的各阶段")
d_rows, rows = t("_media_rows('all')", lambda: prefs_mod._media_rows("all"))
d_num, _ = t("extract_num × %d 行" % len(rows),
             lambda: [duplicates.extract_num(r.get("file_path"), r.get("title"))
                      for r in rows])
d_json, out = t("export_prefs() 端到端", lambda: prefs_mod.export_prefs(
    os.path.join(TMP, "prefs.json")))
print("     导出结果:", {k: out.get(k) for k in ("ok", "media", "people", "no_code")},
      "文件 %.1f KB" % (os.path.getsize(os.path.join(TMP, "prefs.json")) / 1024))

print("\n[B] 导入链路的各阶段（dry_run，不写库不写 nfo）")
d_idx, _ = t("_num_index(全库 %d 行)" % conn.execute(
    "SELECT COUNT(*) FROM media").fetchone()[0], lambda: prefs_mod._num_index(conn))
d_imp, r = t("import_prefs(dry_run=True)", lambda: prefs_mod.import_prefs(
    os.path.join(TMP, "prefs.json"), dry_run=True))
print("     导入统计:", r)

print("\n[C] 真实导入时 nfo 写回的成本（单个文件）")
sample = conn.execute("SELECT nfo_path FROM media WHERE nfo_path IS NOT NULL "
                      "AND user_rating IS NOT NULL LIMIT 3").fetchall()
for s in sample:
    p = s["nfo_path"]
    if os.path.exists(p):
        d, _ = t("read_user_rating  %s" % os.path.basename(p)[:24],
                 lambda p=p: nfo_mod.read_user_rating(p))

print("\n[D] 结论")
tot_ex = d_json
tot_im = d_idx + d_imp
print("  导出总耗时 ≈ %.2fs（其中 extract_num %.2fs）" % (tot_ex, d_num))
print("  导入总耗时 ≈ %.2fs（其中 _num_index %.2fs）" % (tot_im, d_idx))
print("  真导入还要逐条 UPDATE + 每条命中都读写一个 nfo 文件 → 实际更长")
print("  两者都在 GUI 线程同步执行，Qt 事件循环被堵 → Windows 5s 判「未响应」")
