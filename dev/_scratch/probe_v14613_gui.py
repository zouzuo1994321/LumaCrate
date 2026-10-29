# -*- coding: utf-8 -*-
"""v1.46.13 真机（源码态）走查：站在媒体库页面上跑一次「扫描新添加和修改的」，
中途每 250ms 采样一次，验证三件事：

  ① 扫描按媒体库「路径」列表自上而下（tick 文案里的 路径 i/n 顺序）
  ② 影片墙 / 侧栏计数在**扫描进行中**就变（不是扫完才变）
  ③ 底部状态栏有扫描文字 + 进度条在走

用临时 settings / 临时索引库 / 临时媒体树，不碰真实数据。
截图存到 dev/screenshots/v14613_*.png。
"""
import os
import sys
import json
import time
import tempfile
import traceback

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
SHOTS = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
TMP = os.path.join(tempfile.gettempdir(), "lmc_gui_v14613")
os.makedirs(TMP, exist_ok=True)
os.makedirs(SHOTS, exist_ok=True)

sys.path.insert(0, SRC)
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

import config as cfg
cfg_path = os.path.join(TMP, "settings.json")
os.environ["LMC_CONFIG"] = cfg_path

import database as db
db_path = os.path.join(TMP, "index_data", "media_center.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db.db_path = lambda: db_path

import applog
os.makedirs(os.path.join(TMP, "logs"), exist_ok=True)
applog.log_dir = lambda: os.path.join(TMP, "logs")


def _del(p):
    import ctypes
    if not os.path.exists(p):
        return
    ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
    ctypes.windll.kernel32.DeleteFileW(p)


# ---------- 造 3 个路径 × 400 项（够扫十几秒，能看清「边扫边出」） ----------
NFO = """<?xml version="1.0" encoding="UTF-8"?>
<movie><title>%s</title><year>2020</year><plot>p</plot></movie>
"""
TREE = os.path.join(TMP, "libbig3")
PATHS = []
PER_PATH = 1500
if not os.path.isdir(os.path.join(TREE, "path-3")):
    for pi in range(3):
        base = os.path.join(TREE, "path-%d" % (pi + 1))
        PATHS.append(base)
        for i in range(PER_PATH):
            folder = os.path.join(base, "F%d_%03d" % (pi + 1, i))
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "movie.nfo"), "w", encoding="utf-8") as f:
                f.write(NFO % ("作品%d-%03d" % (pi + 1, i)))
            with open(os.path.join(folder, "F%d_%03d.mp4" % (pi + 1, i)), "wb") as f:
                f.write(b"\0" * 4096)
else:
    PATHS = [os.path.join(TREE, "path-%d" % (i + 1)) for i in range(3)]

# 每次从空库开始（否则没有「新增」，验不到边扫边出）
db.close_conn()
for suffix in ("", "-wal", "-shm"):
    _del(db_path + suffix)
db.init_db()

with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump({}, f)
s = cfg.get_settings()
s.libraries = []
s.add_library("演示库", "电影", PATHS)
s.save()

# ---------- 起界面 ----------
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QImage, QPainter, QColor

import main_window as mw

app = QApplication([])
mw.load_style(app)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()

lib = cfg.get_settings().library("演示库")
print("LIBRARY:", lib)

rec = {"ticks": [], "samples": [], "modals": [], "order": [], "scan_start": 0.0,
       "scan_end": 0.0, "boot": time.monotonic(), "started": False}
orig_tick = win._on_scan_tick


def wrapped_tick(name, d, t, m):
    rec["ticks"].append((time.monotonic(), d, t, m))
    if m and "路径" in m:
        seg = [x for x in m.split(" · ") if x.startswith("路径")]
        if seg and (not rec["order"] or rec["order"][-1] != seg[0]):
            rec["order"].append(seg[0])
    return orig_tick(name, d, t, m)


win._on_scan_tick = wrapped_tick


def snap(tag):
    """底部状态栏那一条的截图（垫底色合成，别让 grab 的透明底骗人）。"""
    try:
        pm = win.grab()
        img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
        h = img.height()
        strip = img.copy(0, h - 34, img.width(), 34)
        out = QImage(strip.size(), QImage.Format_RGB32)
        out.fill(QColor(28, 24, 21))
        p = QPainter(out)
        p.drawImage(0, 0, strip)
        p.end()
        path = os.path.join(SHOTS, "v14613_%s.png" % tag)
        out.save(path)
        return path
    except Exception as e:
        print("snap fail:", e)
        return ""


def grid_of_page():
    cur = win.stack.currentWidget()
    try:
        inner = cur.widget() if hasattr(cur, "widget") else cur
        g = getattr(inner, "lazy_grid", None)
        if g is None and inner is not None:
            found = inner.findChildren(mw.LazyGrid)
            g = found[0] if found else None
        return g
    except Exception:
        return None


def sample():
    lbl = getattr(win, "_scan_lbl", None)
    bar = getattr(win, "_busy_bar", None)
    grid = grid_of_page()
    cnt = ""
    try:
        cnt = win._lib_btns["演示库"].text()
    except Exception:
        pass
    rec["samples"].append({
        "t": round(time.monotonic() - rec["scan_start"], 2),
        "lbl_vis": bool(lbl and lbl.isVisible()),
        "lbl": (lbl.text() if lbl else ""),
        "bar_vis": bool(bar and bar.property("busy")),
        "bar_max": (bar.maximum() if bar else -1),
        "bar_val": (bar.value() if bar else -1),
        "grid_total": (grid.total if grid is not None else -1),
        "side": cnt,
    })
    # 扫描完成会弹「扫描完成」模态框 —— 记下文案后关掉，否则脚本挂住
    modal = QApplication.activeModalWidget()
    if isinstance(modal, QMessageBox):
        rec["modals"].append(modal.text())
        modal.close()


def start():
    rec["scan_start"] = time.monotonic()
    rec["started"] = True
    print("SCAN_START")
    win._scan_library_cat(lib, "new")


def watch():
    """扫描结束后：等 done 落地、抓最终截图、收工。"""
    if not rec["started"]:
        if time.monotonic() - rec["boot"] > 60:
            print("TIMEOUT_NOT_STARTED")
            finish()
        return
    modal_seen = bool(rec["modals"])
    if modal_seen and rec["scan_end"] == 0.0:
        rec["scan_end"] = time.monotonic()
        snap("after")
        QTimer.singleShot(700, finish)
        return
    if time.monotonic() - rec["scan_start"] > 240:
        print("TIMEOUT")
        finish()


def finish():
    lbl = getattr(win, "_scan_lbl", None)
    bar = getattr(win, "_scan_bar", None)
    grid = grid_of_page()
    print("=" * 66)
    print("DONE_REPORT")
    print("  order:", rec["order"])
    print("  ticks:", len(rec["ticks"]))
    print("  modals:", rec["modals"])
    print("  end_lbl_visible:", bool(lbl and lbl.isVisible()),
          "end_bar_visible:", bool(bar and bar.isVisible()))
    print("  end_grid_total:", (grid.total if grid is not None else None))
    print("  samples:")
    mid = [x for x in rec["samples"] if x["lbl_vis"] and x["t"] > 0.5]
    for x in rec["samples"][::max(1, len(rec["samples"]) // 14)]:
        print("   ", x)
    print("  mid_scan_with_label:", len(mid))
    print("  mid_scan_grid_totals:", sorted({x["grid_total"] for x in mid}))
    print("  mid_scan_side_counts:", sorted({x["side"] for x in mid}))
    print("  bar_values_mid:", sorted({x["bar_val"] for x in mid if x["bar_max"] == 100})[:20])
    json.dump(rec, open(os.path.join(TMP, "rec.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    app.quit()


t_sample = QTimer()
t_sample.setInterval(250)
t_sample.timeout.connect(sample)
t_sample.start()

t_watch = QTimer()
t_watch.setInterval(200)
t_watch.timeout.connect(watch)
t_watch.start()

QTimer.singleShot(600, lambda: win.go(lambda: win._lib_view(lib)))
QTimer.singleShot(1400, lambda: snap("before"))
QTimer.singleShot(1600, start)
QTimer.singleShot(4200, lambda: snap("during"))

try:
    app.exec()
except Exception:
    traceback.print_exc()
print("EXIT_OK")
