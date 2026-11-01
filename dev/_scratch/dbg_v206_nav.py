# -*- coding: utf-8 -*-
"""调参用：真机 exe 里「最近播放」到底是海报墙还是列表 / 海报有没有画出来。

复用 live_v206b_exe.py 留下的 TEMP 环境（同一个 settings.json 与索引），
只做「点侧栏 → 抓图」，不改任何数据。
"""
import json
import os
import subprocess
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v206b")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"
_out, _err = sys.stdout, sys.stderr
import live_verify as lv          # noqa: E402
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication      # noqa: E402
from PIL import Image                          # noqa: E402

os.environ["LMC_CONFIG"] = os.path.join(TEMP, "settings.json")
exe = os.path.join(TEMP, "LMC-probe-2611010127.exe")
EXE_NAME = os.path.basename(exe).lower()
app = QApplication.instance() or QApplication([])
TMPPNG = os.path.join(TEMP, "_dbg.png")


def shot(h, min_w=1000, tries=10, gap=0.4):
    pm = None
    for _ in range(tries):
        pm = app.primaryScreen().grabWindow(h)
        if pm is not None and pm.width() >= min_w:
            break
        time.sleep(gap)
        app.processEvents()
    if pm is None or pm.width() < min_w:
        return None
    pm.save(TMPPNG, "PNG")
    return Image.open(TMPPNG).convert("RGB")


subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
print("pid", proc.pid, flush=True)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=120, title_sub="Build")
print("hwnd", hwnd, flush=True)
time.sleep(6)

# 侧栏行：从上往下扫一遍，逐个点 + 抓图（不看标题，只留图）
for i, y in enumerate((120, 160, 200, 240, 280, 320, 360, 400)):
    lv.click(hwnd, 90, y)
    time.sleep(1.6)
    im = shot(hwnd, min_w=1500, tries=6)
    if im is None:
        print("y=%s 抓图失败" % y, flush=True)
        continue
    pth = os.path.join(SHOTS, "dbg_nav_%03d.png" % y)
    im.save(pth)
    # 统计内容区（右侧）的非背景像素，粗略判断「有墙」
    px = im.load()
    n = 0
    for yy in range(120, min(900, im.height), 3):
        for xx in range(220, min(1500, im.width), 3):
            r, g, b = px[xx, yy]
            if r + g + b > 150:
                n += 1
    print("y=%s -> %s 亮像素 %s" % (y, os.path.basename(pth), n), flush=True)

try:
    lv.u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
except Exception:
    pass
t0 = time.time()
while time.time() - t0 < 20 and proc.poll() is None:
    time.sleep(0.3)
if proc.poll() is None:
    proc.kill()
print("rc", proc.poll())
