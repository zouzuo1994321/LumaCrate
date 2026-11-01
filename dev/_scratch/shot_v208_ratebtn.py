# -*- coding: utf-8 -*-
"""补一张「未评分影片」的详情页按钮行 —— 证明「评分」按钮是白字。

复用上一轮真机验收留下的临时库与配置（lmc_exe_v208），只把 home_sort 改回名称升序，
双击第 3 行 CCC-003（favorite=0、user_rating=None）→ 按钮应显示「评分」且为白字。
所有进度写进自己的日志文件（不依赖 shell 重定向）。
"""
import ctypes
import ctypes.wintypes
import json
import os
import subprocess
import sys
import time
import traceback
from ctypes import wintypes

TEMP = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "lmc_exe_v208")
CFG = os.path.join(TEMP, "settings.json")
EXE = os.path.join(TEMP, "LMC-probe-2611010129.exe")
EXE_NAME = os.path.basename(EXE).lower()
OUT = os.path.join(TEMP, "ratebtn.png")
LOGP = os.path.join(TEMP, "ratebtn_self.log")


def L(*a):
    with open(LOGP, "a", encoding="utf-8") as f:
        f.write("[%6.1f] %s\n" % (time.time() - T0, " ".join(str(x) for x in a)))
        f.flush()


T0 = time.time()
open(LOGP, "w", encoding="utf-8").close()

try:
    sys.path.insert(0, r"E:\【01】自研软件\【26-19】本地影视中心\dev")
    import live_verify as lv
    from PySide6.QtWidgets import QApplication
    L("imports ok")

    u32 = ctypes.WinDLL("user32", use_last_error=True)

    cfg = json.load(open(CFG, encoding="utf-8"))
    cfg["home_sort"] = {"key": "title", "asc": True}
    json.dump(cfg, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.environ["LMC_CONFIG"] = CFG
    L("cfg home_sort -> title/asc")

    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    time.sleep(1.5)
    app = QApplication.instance() or QApplication(sys.argv)
    proc = subprocess.Popen([EXE], cwd=TEMP, env=dict(os.environ))
    L("started pid", proc.pid)
    hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=120, title_sub="Build")
    L("hwnd", hwnd)
    if not hwnd:
        raise SystemExit(1)
    time.sleep(3.5)

    def screen_of(x, y):
        p = wintypes.POINT(0, 0)
        u32.ClientToScreen(hwnd, ctypes.byref(p))
        return p.x + x, p.y + y

    def dbl(x, y):
        u32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        sx, sy = screen_of(x, y)
        u32.SetCursorPos(int(sx), int(sy))
        time.sleep(0.22)
        for _ in range(2):
            u32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.03)
            u32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.07)
        time.sleep(0.4)

    # 表头 y=145..185、行高 30 → 第 3 行（下标 2）中心 ≈ 260
    dbl(340, 260)
    time.sleep(3.0)
    u32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0100 | 0x0080)
    u32.UpdateWindow(hwnd)
    pm = lv.grab(app, hwnd, tries=24, gap=0.4, settle=6)
    L("grab", pm.width(), pm.height())
    pm.save(OUT)
    L("saved", OUT, os.path.getsize(OUT))
except SystemExit:
    L("no window")
except Exception:
    L("EXC\n" + traceback.format_exc())
finally:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
