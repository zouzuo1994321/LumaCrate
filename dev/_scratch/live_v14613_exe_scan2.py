# -*- coding: utf-8 -*-
"""v1.46.13 打包后 exe 扫描验收 v2。

v1 的两个坑：
  ① 只造 360 个文件 → <1s 扫完，抓到全是「已结束」的帧；
  ② `_on_cat_scan_done` 会弹「扫描完成」模态框 → 主窗口冻结在最后一帧。
所以这里：3×700 个文件 + 建库前先删索引（逼出全量新增）+ **早期密集抓帧**，
并且逐 0.5s 记账「模态框出现 / 进程退出」的时间线，顺带查一次 v1 里
「进程自己退出」是否复现。
"""
import os
import sys
import json
import time
import ctypes
import subprocess
from ctypes import wintypes

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v14613")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication

uu = ctypes.windll.user32

paths = [os.path.join(TEMP, "lib", "path-%d" % (i + 1)) for i in range(3)]
with open(os.path.join(TEMP, "settings.json"), "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "演示库", "kind": "电影", "paths": paths,
                              "filter": {}}]}, f, ensure_ascii=False)


def _del(p):
    if os.path.exists(p):
        ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
        ctypes.windll.kernel32.DeleteFileW(p)


idx = os.path.join(TEMP, "index_data")
n_files = 0
if os.path.isdir(idx):
    for fn in os.listdir(idx):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(idx, fn))
for p in paths:
    n_files += len([d for d in os.listdir(p)]) if os.path.isdir(p) else 0
print("磁盘文件数:", n_files)

exe = None
for fn in os.listdir(TEMP):
    if fn.lower().endswith(".exe"):
        exe = os.path.join(TEMP, fn)
exe_name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
env = dict(os.environ)
if os.environ.get("DRV_MIN") == "1":
    env.update({"LMC_NO_SYSPLASH": "1", "LMC_NO_SYSMON": "1", "LMC_NO_BACKDROP": "1"})
print("DRV_MIN:", os.environ.get("DRV_MIN"))
proc = subprocess.Popen([exe], cwd=TEMP, env=env)
print("启动 pid=", proc.pid)

app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
print("hwnd:", hwnd, lv.wtitle(hwnd))
time.sleep(9)


def to_screen(cx, cy):
    pt = wintypes.POINT(cx, cy)
    uu.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def click(cx, cy, right=False, screen=False):
    sx, sy = (cx, cy) if screen else to_screen(cx, cy)
    uu.SetForegroundWindow(hwnd)
    uu.SetCursorPos(sx, sy)
    time.sleep(0.22)
    uu.mouse_event(0x0008 if right else 0x0002, 0, 0, 0, 0)
    time.sleep(0.09)
    uu.mouse_event(0x0010 if right else 0x0004, 0, 0, 0, 0)


def find_modal(sub=""):
    pids = lv.pids_of_exe(exe_name) | {proc.pid}
    hits = []

    def cb(h, _):
        if uu.IsWindowVisible(h) and lv.wpid(h) in pids and sub in lv.wtitle(h):
            hits.append(h)
        return True

    uu.EnumWindows(lv.EnumWindowsProc(cb), 0)
    return hits[0] if hits else None


ROW = (100, 506)
click(*ROW)
time.sleep(2.0)
click(*ROW, right=True)
time.sleep(1.2)
sx, sy = to_screen(*ROW)
uu.SetCursorPos(sx + 60, sy + 84)
time.sleep(1.5)
click(sx + 140, sy + 78, screen=True)
print("已点「扫描新添加和修改的」")

t0 = time.time()
plan = [0.8, 1.8, 2.8, 4.0, 5.2, 6.6, 8.0, 9.5, 11.0, 13.0]
shots = []
modal_at = None
exit_at = None
i = 0
while i < len(plan):
    wait = plan[i] - (time.time() - t0)
    if wait > 0:
        time.sleep(wait)
    if proc.poll() is not None:
        exit_at = exit_at or (time.time() - t0)
        break
    if modal_at is None:
        m = find_modal("扫描完成")
        if m:
            modal_at = time.time() - t0
            print("  模态框出现 +%.1fs" % modal_at)
    if modal_at is None:
        pm = lv.grab(app, hwnd, tries=6, gap=0.2, settle=3)
        name = "_exe2_scan_%d" % i
        pm.save(os.path.join(SHOTS, name + ".png"), "PNG")
        shots.append((name, round(time.time() - t0, 1), pm.width()))
    i += 1

print("抓到的帧:", shots)
print("modal_at:", modal_at, "exit_at:", exit_at)

m = find_modal("扫描完成")
if m:
    print("模态框标题:", lv.wtitle(m))
    uu.PostMessageW(m, 0x0010, 0, 0)
    time.sleep(1.5)
if proc.poll() is None:
    uu.PostMessageW(hwnd, 0x0010, 0, 0)
    t1 = time.time()
    while time.time() - t1 < 20 and proc.poll() is None:
        time.sleep(0.3)
print("退出码:", proc.poll())
if proc.poll() is None:
    proc.kill()

log = os.path.join(TEMP, "index_data", "logs", "app.log")
if os.path.exists(log):
    txt = open(log, encoding="utf-8", errors="replace").read()
    print("app.log 异常关键字:", [k for k in ("未捕获异常", "Traceback", "QThread: Destroyed")
                                  if k in txt] or "无")
print("DONE")
