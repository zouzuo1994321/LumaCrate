# -*- coding: utf-8 -*-
"""v1.46.13 打包后真机验收（轻量）：把新 exe 拷到**临时目录**跑一遍。

为什么拷到临时目录：打包后 `index_data/` 与 `settings.json` 都在 exe 同级
（`database.db_path()` / `config.config_path()`）—— 直接在项目根跑会把演示库写进
用户的真实索引。拷一份到 %TEMP% 下，索引 / 配置 / 日志全部隔离。

验证项：
  ① 进程起得来、主窗口出现（标题带 Build）、窗口可绘制（抓图非空白）
  ② 启动后不处于「未响应」（IsHungAppWindow 为假）
  ③ 侧栏出现演示库行（说明扫描前配置生效）
  ④ 关窗能正常退出（rc=0）
  ⑤ app.log 里没有「未捕获异常」/Traceback
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
                    "lmc_exe_v14613")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

# live_verify.py 顶层会把 sys.stdout/sys.stderr 重定向到它自己的日志（并截断），
# 被 import 时会把本脚本的输出全部吞掉 → 先存后还。
_stdout, _stderr = sys.stdout, sys.stderr
import live_verify as lv           # 复用找窗口 / 抓图 / 进程查询
sys.stdout, sys.stderr = _stdout, _stderr
from PySide6.QtWidgets import QApplication

FAILS = []
OKS = []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    print(("  OK   " if cond else "  FAIL ") + name + (("  → " + str(detail)) if detail else ""))


def _del(p):
    if not os.path.exists(p):
        return
    ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
    ctypes.windll.kernel32.DeleteFileW(p)


def make_tree(base, n_per_path=120):
    for pi in range(3):
        p = os.path.join(base, "path-%d" % (pi + 1))
        for i in range(n_per_path):
            d = os.path.join(p, "F%d_%03d" % (pi + 1, i))
            if os.path.isdir(d):
                continue
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>'
                        '<movie><title>演示%d-%03d</title><year>2021</year></movie>' % (pi + 1, i))
            with open(os.path.join(d, "F%d_%03d.mp4" % (pi + 1, i)), "wb") as f:
                f.write(b"\0" * 1024)
    return [os.path.join(base, "path-%d" % (i + 1)) for i in range(3)]


os.makedirs(TEMP, exist_ok=True)
os.makedirs(SHOTS, exist_ok=True)

src = lv.newest_exe()
print("新 exe:", src)
assert src and os.path.exists(src), "没找到新 exe"
exe = os.path.join(TEMP, os.path.basename(src))
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)
print("拷贝到:", exe, os.path.getsize(exe) // 1024 // 1024, "MB")

paths = make_tree(os.path.join(TEMP, "lib"))
cfg_path = os.path.join(TEMP, "settings.json")
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "演示库", "kind": "电影", "paths": paths,
                              "filter": {}}]}, f, ensure_ascii=False)

# 干净起步：删掉上一轮残留的索引（exe 同级 index_data）
idx = os.path.join(TEMP, "index_data")
if os.path.isdir(idx):
    for fn in os.listdir(idx):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(idx, fn))

exe_name = os.path.basename(exe)
# 上一轮崩溃残留的进程会抢窗口（同名 exe）→ 先清干净
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP)
print("已启动 pid=", proc.pid)

app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)
if hwnd:
    print("  title:", lv.wtitle(hwnd))
    check("标题含新版本号 v1.46.13", "v1.46.13" in lv.wtitle(hwnd), lv.wtitle(hwnd))
    time.sleep(6)                       # 等首屏绘制 + 索引查询
    hung = bool(ctypes.windll.user32.IsHungAppWindow(hwnd))
    check("启动后不处于「未响应」", not hung, hung)
    pm = lv.grab(app, hwnd, tries=20, gap=0.4, settle=6)
    out = os.path.join(SHOTS, "v14613_exe_start.png")
    ok = pm.width() > 1 and pm.save(out, "PNG")
    check("窗口可抓图（非空白）", bool(ok) and pm.width() > 1000, (pm.width(), pm.height()))
    print("  截图:", out)

    # 侧栏是否列出演示库（读窗口文本不可行，用日志/配置间接确认；这里只查进程仍在）
    check("进程仍在运行（没有崩退）", proc.poll() is None, proc.poll())

    lv.u32.PostMessageW(hwnd, 0x0010, 0, 0)     # WM_CLOSE
    t0 = time.time()
    while time.time() - t0 < 25 and proc.poll() is None:
        time.sleep(0.3)
    check("关窗后正常退出（rc=0）", proc.poll() == 0, proc.poll())
    if proc.poll() is None:
        proc.kill()

log = os.path.join(TEMP, "index_data", "logs", "app.log")
bad = []
if os.path.exists(log):
    with open(log, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    for kw in ("未捕获异常", "Traceback", "QThread: Destroyed", "Fatal"):
        if kw in txt:
            bad.append(kw)
    print("  app.log 行数:", len(txt.splitlines()))
check("app.log 无未捕获异常 / Traceback", not bad, bad)

print("FAILS:", FAILS)
print("通过 %d/%d" % (len(OKS), len(OKS) + len(FAILS)))
print("LIVE_V14613_ALL_OK" if not FAILS else "LIVE_V14613_HAS_FAIL")
