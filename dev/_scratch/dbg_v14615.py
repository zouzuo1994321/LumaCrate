# -*- coding: utf-8 -*-
"""诊断：真机点开「工具 → 服务管理」后进程为何 rc=0 退出。"""
import os
import sys
import json
import time
import ctypes
import shutil
import subprocess

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
TEMPB = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                     "lmc_dbgn_v14615")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication

T0 = time.time()


def p(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


os.makedirs(TEMPB, exist_ok=True)
src = lv.newest_exe()
exe = os.path.join(TEMPB, os.path.basename(src))
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)

LIBS = [
    {"name": "Javlibrary", "kind": "电影",
     "paths": ["D:/演示路径-%d" % i for i in range(14)], "filter": {}},
    {"name": "Jav-VR", "kind": "电影", "paths": ["D:/演示路径-vr"], "filter": {}},
    {"name": "Jav-临时", "kind": "混合", "paths": ["D:/演示路径-tmp"], "filter": {}},
]
cfg = os.path.join(TEMPB, "settings.json")
with open(cfg, "w", encoding="utf-8") as f:
    json.dump({"libraries": LIBS}, f, ensure_ascii=False)
os.environ["LMC_CONFIG"] = cfg
idx = os.path.join(TEMPB, "index_data")
if os.path.isdir(idx):
    for fn in os.listdir(idx):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            q = os.path.join(idx, fn)
            ctypes.windll.kernel32.SetFileAttributesW(q, 0x80)
            ctypes.windll.kernel32.DeleteFileW(q)

COORDS = json.load(open(lv.COORDS, encoding="utf-8"))
TOOLS_BTN = tuple(COORDS["main_settings_btn"])
NAV_SERVICE = tuple(COORDS["dialog_nav"]["服务管理"])

name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMPB, env=dict(os.environ))
p("启动 pid=", proc.pid)

app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(name, [proc.pid], timeout=120, title_sub="Build")
p("主窗", hwnd, "poll=", proc.poll())
time.sleep(5)
p("点工具按钮", TOOLS_BTN, "poll=", proc.poll())
lv.click(hwnd, TOOLS_BTN[0], TOOLS_BTN[1])

dlg = None
t1 = time.time()
while time.time() - t1 < 25 and proc.poll() is None:
    rows = lv.dump_windows([proc.pid], "找工具窗")
    cand = [r for r in rows if r[0] != hwnd and r[1] and r[5] > 300 and r[6] > 200
            and "工具" in r[7]]
    if cand:
        dlg = cand[0][0]
        break
    time.sleep(0.8)
p("工具窗", dlg, "poll=", proc.poll())
lv.dump_windows([proc.pid], "工具窗打开后")
time.sleep(1.2)
p("点服务管理", NAV_SERVICE, "poll=", proc.poll())
lv.click(dlg, NAV_SERVICE[0], NAV_SERVICE[1])
for i in range(12):
    time.sleep(0.5)
    p("  等待 %d" % i, "poll=", proc.poll())
    if proc.poll() is not None:
        break
lv.dump_windows([proc.pid], "点完服务管理后")
p("grab 前 poll=", proc.poll())
try:
    pm = app.primaryScreen().grabWindow(dlg)
    p("直接 grab:", pm.width(), pm.height())
except Exception as e:
    p("grab 异常:", e)

log = os.path.join(TEMPB, "index_data", "logs", "app.log")
p("---- app.log ----")
if os.path.exists(log):
    p(open(log, encoding="utf-8", errors="replace").read())
if proc.poll() is None:
    subprocess.run(["taskkill", "/f", "/pid", str(proc.pid)], capture_output=True)
p("最终 poll=", proc.poll())
