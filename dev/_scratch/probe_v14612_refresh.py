# -*- coding: utf-8 -*-
"""v1.46.12 探针（四）：导入完成后 on_changed 那 1.4s 花在哪。"""
import ctypes
import os
import shutil
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
TMP = r"C:/Users/zouzu/AppData/Local/Temp/probe_v14612"
k32 = ctypes.windll.kernel32
dst = os.path.join(TMP, "ui.db")
if os.path.exists(dst):
    k32.SetFileAttributesW(dst, 0x80)
    k32.DeleteFileW(dst)
shutil.copyfile(os.path.join(ROOT, "index_data", "media_center.db"), dst)
import database as db                                    # noqa: E402
db.db_path = lambda: dst
import applog                                            # noqa: E402
applog.log_dir = lambda: os.path.join(TMP, "logs")
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication                # noqa: E402
import main_window as mwmod                              # noqa: E402

app = QApplication.instance() or QApplication([])
t0 = time.perf_counter()
win = mwmod.MainWindow()
win.resize(1920, 1080)
win.show()
for _ in range(20):
    app.processEvents()
print("MainWindow 构建 %.2fs" % (time.perf_counter() - t0))


def t(label, fn, pump=6):
    t0 = time.perf_counter()
    fn()
    for _ in range(pump):
        app.processEvents()
    print("  %-26s %.3fs" % (label, time.perf_counter() - t0))
    return time.perf_counter() - t0


print("\n_apply_settings 拆解：")
t("_refresh_stats()", win._refresh_stats)
t("_apply_appearance()", win._apply_appearance)
t("_build_sidebar()", lambda: win._build_sidebar())
t("go(_view_home)  # 重建首页", lambda: win.go(win._view_home))
print("\n完整 _apply_settings():")
t("_apply_settings()", win._apply_settings)
print("\n只刷新统计 + 首页就地刷新：")
home = win.stack.currentWidget()
t("_refresh_stats()", win._refresh_stats)
t("home.live_refresh()", lambda: home.live_refresh() if hasattr(home, "live_refresh") else None)
win.close()
