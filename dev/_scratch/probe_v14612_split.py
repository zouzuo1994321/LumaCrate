# -*- coding: utf-8 -*-
"""v1.46.12 探针（三）：7 秒里各段各占多少 —— 拆分 import_prefs 与 _apply_settings。"""
import ctypes
import os
import shutil
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
TMP = r"C:/Users/zouzu/AppData/Local/Temp/probe_v14612"
SRC_JSON = os.path.join(TMP, "prefs.json")
k32 = ctypes.windll.kernel32


def _del(p):
    if os.path.exists(p):
        k32.SetFileAttributesW(p, 0x80)
        k32.DeleteFileW(p)


dbcopy = os.path.join(TMP, "split.db")
_del(dbcopy)
shutil.copyfile(os.path.join(ROOT, "index_data", "media_center.db"), dbcopy)
import database as db                                    # noqa: E402
db.db_path = lambda: dbcopy
import applog                                            # noqa: E402
applog.log_dir = lambda: os.path.join(TMP, "logs")

import nfo_parser as nfo_mod                             # noqa: E402
_real = nfo_mod.write_user_rating
_tmpdir = os.path.join(TMP, "nfo_safe2")
os.makedirs(_tmpdir, exist_ok=True)
_map = {}


def safe_write(path, value):
    if not path:
        return False
    dst = _map.get(path)
    if dst is None:
        if not os.path.exists(path):
            return False
        dst = os.path.join(_tmpdir, "n%04d.nfo" % len(_map))
        shutil.copyfile(path, dst)
        _map[path] = dst
    return _real(dst, value)


nfo_mod.write_user_rating = safe_write

import prefs as prefs_mod                                # noqa: E402

t0 = time.perf_counter()
r = prefs_mod.import_prefs(SRC_JSON)
d_db = time.perf_counter() - t0
print("import_prefs（含 415 个 nfo 写回，本地副本盘）: %.2fs  %s"
      % (d_db, {k: r.get(k) for k in ("media_ok", "people_ok", "nfo_written")}))
print("  被写 refl 的 nfo 数:", len(_map))

# 把 nfo 写回打桩掉，再跑一次（换新副本）看 DB 段本身
db.close_conn()                        # 先放掉自己持有的句柄，否则删/拷都失败
_del(dbcopy)
shutil.copyfile(os.path.join(ROOT, "index_data", "media_center.db"), dbcopy)
nfo_mod.write_user_rating = lambda *a, **k: False
t0 = time.perf_counter()
r = prefs_mod.import_prefs(SRC_JSON)
d_dbonly = time.perf_counter() - t0
nfo_mod.write_user_rating = safe_write
print("import_prefs（不写 nfo，纯 DB）: %.2fs" % d_dbonly)
print("→ nfo 写回段 ≈ %.2fs（本地盘；真实 nfo 在 X: 盘，每文件多 2 次盘操作）"
      % (d_db - d_dbonly))

# 尾部 _apply_settings 的耗时
from PySide6.QtWidgets import QApplication                # noqa: E402
import main_window as mwmod                              # noqa: E402

app = QApplication.instance() or QApplication([])
t0 = time.perf_counter()
win = mwmod.MainWindow()
win.resize(1600, 900)
win.show()
for _ in range(30):
    app.processEvents()
print("\nMainWindow 构建 %.2fs" % (time.perf_counter() - t0))

for i in range(2):
    t0 = time.perf_counter()
    win._apply_settings()
    for _ in range(5):
        app.processEvents()
    print("_apply_settings 第 %d 次: %.2fs（导入完成后 on_changed 就是它）"
          % (i + 1, time.perf_counter() - t0))
win.close()
