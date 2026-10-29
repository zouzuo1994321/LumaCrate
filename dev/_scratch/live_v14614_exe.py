# -*- coding: utf-8 -*-
"""v1.46.14 打包后真机验收：新 exe 拷到临时目录跑一遍（索引/配置/日志全隔离）。

复用 `dev/live_verify.py` 的找窗口 / 抓图 / 进程查询。
注意：`live_verify` 顶层会把 stdout/stderr 重定向到它自己的日志 → 先存后还。
"""
import os
import sys
import json
import time
import ctypes
import shutil
import subprocess

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v14614")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication

FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    print(("  OK   " if cond else "  FAIL ") + name + (("  → " + str(detail)) if detail else ""))


def _del(p):
    if os.path.exists(p):
        ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
        ctypes.windll.kernel32.DeleteFileW(p)


def make_tree(base, n=40):
    out = []
    for pi in range(3):
        p = os.path.join(base, "path-%d" % (pi + 1))
        out.append(p)
        for i in range(n):
            d = os.path.join(p, "F%d_%02d" % (pi + 1, i))
            if os.path.isdir(d):
                continue
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0"?><movie><title>演示%d-%02d</title><year>2021</year>'
                        '</movie>' % (pi + 1, i))
            with open(os.path.join(d, "x%d_%02d.mp4" % (pi + 1, i)), "wb") as f:
                f.write(b"\0" * 512)
    return out


os.makedirs(TEMP, exist_ok=True)
src = lv.newest_exe()
print("新 exe:", src)
assert src and os.path.exists(src)
exe = os.path.join(TEMP, os.path.basename(src))
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)
print("拷贝到:", exe)

paths = make_tree(os.path.join(TEMP, "lib"))
with open(os.path.join(TEMP, "settings.json"), "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "演示库", "kind": "电影", "paths": paths,
                              "filter": {}}]}, f, ensure_ascii=False)
idx = os.path.join(TEMP, "index_data")
if os.path.isdir(idx):
    for fn in os.listdir(idx):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(idx, fn))

exe_name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP)
print("已启动 pid=", proc.pid)

app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)
if hwnd:
    print("  title:", lv.wtitle(hwnd))
    check("标题含新版本号 v1.46.14", "v1.46.14" in lv.wtitle(hwnd), lv.wtitle(hwnd))
    time.sleep(6)
    check("启动后不处于「未响应」",
          not bool(ctypes.windll.user32.IsHungAppWindow(hwnd)))
    pm = lv.grab(app, hwnd, tries=20, gap=0.4, settle=6)
    out = os.path.join(SHOTS, "v14614_exe_start.png")
    ok = pm.width() > 1 and pm.save(out, "PNG")
    check("窗口可抓图（非空白）", bool(ok) and pm.width() > 1000, (pm.width(), pm.height()))
    check("进程仍在运行（没有崩退）", proc.poll() is None, proc.poll())
    lv.u32.PostMessageW(hwnd, 0x0010, 0, 0)
    t0 = time.time()
    while time.time() - t0 < 25 and proc.poll() is None:
        time.sleep(0.3)
    check("关窗后正常退出（rc=0）", proc.poll() == 0, proc.poll())
    if proc.poll() is None:
        proc.kill()

log = os.path.join(TEMP, "index_data", "logs", "app.log")
bad = []
if os.path.exists(log):
    txt = open(log, encoding="utf-8", errors="replace").read()
    bad = [k for k in ("未捕获异常", "Traceback", "QThread: Destroyed", "Fatal") if k in txt]
    print("  app.log 行数:", len(txt.splitlines()))
check("app.log 无未捕获异常 / Traceback", not bad, bad)

print("FAILS:", FAILS)
print("通过 %d/%d" % (len(OKS), len(OKS) + len(FAILS)))
print("LIVE_V14614_ALL_OK" if not FAILS else "LIVE_V14614_HAS_FAIL")
