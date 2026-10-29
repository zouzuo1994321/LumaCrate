# -*- coding: utf-8 -*-
"""点击坐标校准：点一下 → 抓图 → 在左侧导航列里找「高亮行」的 y 范围。

目的：搞清 `lv.click(dlg, x, y)` 的 y 与「离屏算出的客户区 y」之间到底差多少。
输出每一步的：点击坐标、导航高亮行 y 区间、当前 accent（从 settings.json 读）。
"""
import os
import sys
import json
import time
import ctypes
import ctypes.wintypes
import subprocess

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(DEV, "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v200")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"
_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication
from PIL import Image

app = QApplication.instance() or QApplication([])
exe = os.path.join(TEMP, "流明盒-v2.0.0-2610290119.exe")
exe_name = os.path.basename(exe)
cfg_path = os.path.join(TEMP, "settings.json")
os.environ["LMC_CONFIG"] = cfg_path

subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
print("main hwnd", hwnd)
time.sleep(5)
COORDS = json.load(open(lv.COORDS, encoding="utf-8"))
lv.click(hwnd, *tuple(COORDS["main_settings_btn"]))
dlg = lv.find_window_ex(exe_name, [proc.pid], exclude=(hwnd,), timeout=25, title_sub="工具")
print("dlg hwnd", dlg)
time.sleep(3.0)

TMPPNG = os.path.join(TEMP, "cal.png")


def shot():
    for _ in range(8):
        pm = app.primaryScreen().grabWindow(dlg)
        if pm.width() > 100:
            pm.save(TMPPNG, "PNG")
            return Image.open(TMPPNG).convert("RGB")
        time.sleep(0.4)
    return None


def nav_rows(im):
    """在导航列 x∈[12,130] 找高亮（比相邻行更亮）的连续行。"""
    px = im.load()
    means = []
    for y in range(im.height):
        s = 0
        for x in range(12, 130, 2):
            r, g, b = px[x, y]
            s += (r + g + b) / 3.0
        means.append(s / 59.0)
    base = sorted(means)[len(means) // 2]
    hot = [y for y, v in enumerate(means) if v > base + 4.0]
    runs = []
    for y in hot:
        if runs and y - runs[-1][1] <= 2:
            runs[-1][1] = y
        else:
            runs.append([y, y])
    return [(a, b) for a, b in runs if b - a >= 12], round(base, 1)


def accent():
    try:
        with open(cfg_path, encoding="utf-8") as f:
            return (json.load(f).get("appearance") or {}).get("accent")
    except Exception as e:
        return "err:%s" % e


STEPS = [(71, 63), (71, 102), (458, 247), (71, 404)]
for (x, y) in STEPS:
    lv.click(dlg, x, y)
    time.sleep(1.6)
    im = shot()
    rows, base = nav_rows(im) if im else ([], -1)
    print("click(%d,%d) -> nav 高亮行 %s  base亮度=%s  accent=%s"
          % (x, y, rows, base, accent()), flush=True)

# 收尾
lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
time.sleep(1.0)
lv.u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
for _ in range(30):
    if proc.poll() is not None:
        break
    time.sleep(0.3)
if proc.poll() is None:
    proc.kill()
print("rc", proc.poll())
print("CAL_DONE")
