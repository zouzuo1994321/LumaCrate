# -*- coding: utf-8 -*-
"""v1.46.13 打包后 exe：真正抓一次「扫描中」的底部状态栏。

上一版失败原因（重要）：只造了 360 个小文件，扫描 < 1s 就结束了，随后
`_on_cat_scan_done` 弹出「扫描完成」模态框 → 主窗口冻结在最后一帧，
抓到的每一张都是「已结束」。所以这里造 3×700 个文件，扫描要跑十几秒。

要点：
  · 真实鼠标输入（SetCursorPos + mouse_event）：PostMessage 的合成点击无效
  · 扫描入口 = 侧栏库行**右键菜单 → 扫描 → 扫描新添加和修改的**
  · 结束时会有模态「扫描完成」框，用回车关掉，再 WM_CLOSE 退出
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
N_PER = 700

# ---------- 1. 造 3×700 的媒体树 ----------
paths = []
for pi in range(3):
    p = os.path.join(TEMP, "lib", "path-%d" % (pi + 1))
    paths.append(p)
    for i in range(N_PER):
        d = os.path.join(p, "F%d_%03d" % (pi + 1, i))
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>'
                        '<movie><title>演示%d-%03d</title><year>2021</year></movie>'
                        % (pi + 1, i))
            with open(os.path.join(d, "F%d_%03d.mp4" % (pi + 1, i)), "wb") as f:
                f.write(b"\0" * 1024)
print("媒体树就绪：3 ×", N_PER)

cfg_path = os.path.join(TEMP, "settings.json")
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "演示库", "kind": "电影", "paths": paths,
                              "filter": {}}]}, f, ensure_ascii=False)


def _del(p):
    if os.path.exists(p):
        ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
        ctypes.windll.kernel32.DeleteFileW(p)


idx = os.path.join(TEMP, "index_data")
if os.path.isdir(idx):
    for fn in os.listdir(idx):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(idx, fn))

exe = None
for fn in os.listdir(TEMP):
    if fn.lower().endswith(".exe"):
        exe = os.path.join(TEMP, fn)
exe_name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
env = dict(os.environ)
if os.environ.get("DRV_MIN") == "1":       # 关掉启动画面 / 实时状态 / 背景，做差异对照
    env.update({"LMC_NO_SYSPLASH": "1", "LMC_NO_SYSMON": "1", "LMC_NO_BACKDROP": "1"})
print("DRV_MIN:", os.environ.get("DRV_MIN"))
proc = subprocess.Popen([exe], cwd=TEMP, env=env)
print("启动:", exe_name, "pid=", proc.pid)

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
    time.sleep(0.25)
    uu.mouse_event(0x0008 if right else 0x0002, 0, 0, 0, 0)
    time.sleep(0.09)
    uu.mouse_event(0x0010 if right else 0x0004, 0, 0, 0, 0)


def grab(name):
    pm = lv.grab(app, hwnd, tries=8, gap=0.25, settle=4)
    pm.save(os.path.join(SHOTS, name + ".png"), "PNG")
    return pm


def grab_screen(name):
    pm = app.primaryScreen().grabWindow(0)
    pm.save(os.path.join(SHOTS, name + ".png"), "PNG")


# ---------- 2. 右键库行 → 悬停「扫描」→ 点「扫描新添加和修改的」 ----------
ROW = (100, 506)
click(*ROW)                      # 先左键选中（同时进入库页面）
time.sleep(2.0)
click(*ROW, right=True)          # 右键菜单
time.sleep(1.2)
sx, sy = to_screen(*ROW)
print("库行屏幕坐标:", sx, sy)
uu.SetCursorPos(sx + 60, sy + 84)     # 「扫描」项（相对右键点 +84px）
time.sleep(1.6)
grab_screen("_exe_menu_sub")
click(sx + 140, sy + 78, screen=True)   # 「扫描新添加和修改的」
print("已点扫描")

t0 = time.time()
for i, at in enumerate((1.2, 2.5, 4.5, 7.0, 10.0, 14.0, 19.0)):
    wait = at - (time.time() - t0)
    if wait > 0:
        time.sleep(wait)
    pm = grab("_exe_scan_%d" % i)
    print("  抓图 +%.1fs" % (time.time() - t0), pm.width(), pm.height())
grab_screen("_exe_scan_full")

# ---------- 3. 收尾：关掉「扫描完成」模态 → 关窗 ----------
def find_modal(sub=""):
    """在同一个 PID 下找标题含 sub 的可见顶层窗口（模态框）。"""
    pids = lv.pids_of_exe(exe_name) | {proc.pid}
    hits = []

    def cb(h, _):
        if uu.IsWindowVisible(h) and lv.wpid(h) in pids:
            t = lv.wtitle(h)
            if sub in t:
                hits.append((h, t))
        return True

    uu.EnumWindows(lv.EnumWindowsProc(cb), 0)
    return hits[0] if hits else (None, "")


mh, mt = find_modal("扫描完成")
print("模态框:", mh, mt)
if mh:
    uu.PostMessageW(mh, 0x0010, 0, 0)      # WM_CLOSE
    time.sleep(1.5)
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
    bad = [k for k in ("未捕获异常", "Traceback", "QThread: Destroyed") if k in txt]
    print("app.log 异常关键字:", bad or "无")
print("DONE")
