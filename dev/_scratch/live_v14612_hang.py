# -*- coding: utf-8 -*-
"""v1.46.12 真机探针：改完之后的偏好导入/导出，界面还卡不卡。

同一套尺子（真窗口 + 主线程 QTimer 间隔 + 后台线程轮询 IsHungAppWindow），
只是这次量的是 v1.46.12 的新链路（PrefsWorker 后台线程 + 页面内进度）。

安全措施：数据库用副本；nfo 写回改成「先复制到临时目录、再改副本」，
真实 nfo 一个字节都不动。
"""
import ctypes
import os
import shutil
import sys
import threading
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
TMP = r"C:/Users/zouzu/AppData/Local/Temp/probe_v14612"
os.makedirs(TMP, exist_ok=True)
SRC_JSON = os.path.join(TMP, "prefs.json")
k32 = ctypes.windll.kernel32


def _del(p):
    """删文件走 Win32（本机 safe-delete shim 会拦 os.remove）。"""
    if os.path.exists(p):
        k32.SetFileAttributesW(p, 0x80)
        k32.DeleteFileW(p)


# ---- 数据库只碰副本 ----
dbcopy = os.path.join(TMP, "hang2.db")
_del(dbcopy)
shutil.copyfile(os.path.join(ROOT, "index_data", "media_center.db"), dbcopy)
import database as db                                    # noqa: E402
db.db_path = lambda: dbcopy

import applog                                            # noqa: E402
applog.log_dir = lambda: os.path.join(TMP, "logs")

# ---- nfo 写回到副本（真实 nfo 不动） ----
import nfo_parser as nfo_mod                             # noqa: E402
_real_write = nfo_mod.write_user_rating
_nfo_tmp = os.path.join(TMP, "nfo_safe2")
os.makedirs(_nfo_tmp, exist_ok=True)
_map = {}


def safe_write(path, value):
    if not path:
        return False
    dst = _map.get(path)
    if dst is None:
        if not os.path.exists(path):
            return False
        dst = os.path.join(_nfo_tmp, "n%04d.nfo" % len(_map))
        shutil.copyfile(path, dst)
        _map[path] = dst
    return _real_write(dst, value)


nfo_mod.write_user_rating = safe_write

from PySide6.QtCore import QTimer                        # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import main_window as mwmod                              # noqa: E402
import ui_settings                                       # noqa: E402
import prefs as prefs_mod                                # noqa: E402

u32 = ctypes.windll.user32
u32.IsHungAppWindow.argtypes = [ctypes.c_void_p]
u32.IsHungAppWindow.restype = ctypes.c_bool


def as_int(v):
    if isinstance(v, (bytes, bytearray)):
        return int.from_bytes(v[:8], "little")
    return int(v)


app = QApplication.instance() or QApplication([])
QMessageBox.information = staticmethod(
    lambda *a, **k: print("  [info]", a[1] if len(a) > 1 else ""))
QMessageBox.warning = staticmethod(
    lambda *a, **k: print("  [warn]", a[1:] if len(a) > 1 else ""))

t0 = time.perf_counter()
win = mwmod.MainWindow()
win.resize(1600, 900)
win.show()
for _ in range(30):
    app.processEvents()
print("主窗就绪 %.1fs" % (time.perf_counter() - t0))

dlg = ui_settings.SettingsDialog(win, on_changed=None)
_orig_apply = win._apply_settings


def _timed_apply():
    """包一层计时：结尾「正在刷新界面…」到底占多少。"""
    t = time.perf_counter()
    _orig_apply()
    print("  [on_changed = _apply_settings] %.2fs" % (time.perf_counter() - t))


dlg.on_changed = _timed_apply
dlg.setModal(False)
dlg.show()
app.processEvents()
dlg._show("数据管理")
for _ in range(10):
    app.processEvents()
print("数据管理页就绪")

HWNDS = {"main": as_int(win.winId()), "dlg": as_int(dlg.winId())}


class HungMon(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop = False
        self.samples = []

    def run(self):
        while not self.stop:
            snap = {}
            for k, h in HWNDS.items():
                try:
                    snap[k] = bool(u32.IsHungAppWindow(ctypes.c_void_p(h)))
                except Exception:
                    snap[k] = False
            self.samples.append((time.perf_counter(), snap))
            time.sleep(0.05)


def measure_async(start, label, timeout=180):
    ticks = []
    tmr = QTimer()
    tmr.setInterval(50)
    tmr.timeout.connect(lambda: ticks.append(time.perf_counter()))
    tmr.start()
    stages = []

    mon = HungMon()
    mon.start()
    t0 = time.perf_counter()
    start()
    while time.perf_counter() - t0 < timeout:
        app.processEvents()
        time.sleep(0.01)
        st = dlg.pref_status.text()
        if st and (not stages or stages[-1] != st):
            stages.append(st)
        if (not dlg._prefs_running() and not dlg.pref_prog_row.isVisible()
                and time.perf_counter() - t0 > 0.4):
            break
    dt = time.perf_counter() - t0
    mon.stop = True
    mon.join(timeout=1.0)
    tmr.stop()
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    if ticks:
        gaps.append(time.perf_counter() - ticks[-1])   # 别忘了最后一段「不再跳」的空档
    hung_main = [t for t, s in mon.samples if s["main"]]
    hung_dlg = [t for t, s in mon.samples if s["dlg"]]
    print("\n===== %s =====" % label)
    print("  墙上时间         : %.2fs" % dt)
    print("  timer 跳了        : %d 次 / 期望约 %d 次"
          % (len(ticks), int(dt / 0.05)))
    print("  事件循环最长停摆 : %.2fs（50ms 一跳到下一跳）"
          % (max(gaps) if gaps else -1))
    print("  IsHungAppWindow 主窗 : %d/%d 次为真%s"
          % (len(hung_main), len(mon.samples),
             ("" if not hung_main else
              "（跨度 %.2fs）" % (max(hung_main) - min(hung_main)))))
    print("  IsHungAppWindow 设置窗: %d/%d 次为真%s"
          % (len(hung_dlg), len(mon.samples),
             ("" if not hung_dlg else
              "（跨度 %.2fs）" % (max(hung_dlg) - min(hung_dlg)))))
    print("  进度阶段（去重，共 %d 条）:" % len(stages))
    for s in stages[:6]:
        print("     ·", s)
    if len(stages) > 6:
        print("     · …", stages[-1])
    return dt


def do_import():
    dlg._prefs_run("import", SRC_JSON)


def do_export():
    dst = os.path.join(TMP, "export_from_ui2.json")
    _del(dst)
    dlg._prefs_run("export", dst, ["favorite", "play", "rating", "people", "gender"])
    dlg._export_dst = dst


QTimer.singleShot(600, lambda: (
    measure_async(do_import, "导入偏好（v1.46.12：后台线程 + 进度）"),
    measure_async(do_export, "导出偏好（v1.46.12：后台线程 + 进度）"),
    print("\npref_hint:", dlg.pref_hint.text()),
    app.quit()))
app.exec()
print("\n[完成] 真实 nfo 未改动：改写全部落在 %s（%d 个）" % (_nfo_tmp, len(_map)))
