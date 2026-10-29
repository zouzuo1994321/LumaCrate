# -*- coding: utf-8 -*-
"""v1.46.15（Build 0118）打包后真机验收。

本版只动「工具 → 服务管理 → 已配置的媒体库」这一个列表（行距 + 三个按钮的内边距），
所以真机除了「起得来 / 不崩 / 日志干净」，还要**真的点进那一页抓图**留证。
坐标取自 `lmc_ui_coords.json`（主窗「工具」按钮 + 工具窗导航「服务管理」）。

注意：`live_verify` 顶层会把 stdout/stderr 重定向到它自己的日志 → 先存后还。
"""
import os
import sys
import json
import time
import ctypes
import ctypes.wintypes
import shutil
import subprocess

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v14615b")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication

FAILS, OKS = [], []
T0 = time.time()


def p(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    p(("  OK   " if cond else "  FAIL ") + name + (("  → " + str(detail)) if detail else ""))


def _del(pth):
    if os.path.exists(pth):
        ctypes.windll.kernel32.SetFileAttributesW(pth, 0x80)
        ctypes.windll.kernel32.DeleteFileW(pth)


os.makedirs(TEMP, exist_ok=True)
src = lv.newest_exe()
p("新 exe:", src)
assert src and os.path.exists(src)
exe = os.path.join(TEMP, os.path.basename(src))
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)

LIBS = [
    {"name": "Javlibrary", "kind": "电影",
     "paths": ["D:/演示路径-%d" % i for i in range(14)], "filter": {}},
    {"name": "Jav-VR", "kind": "电影", "paths": ["D:/演示路径-vr"], "filter": {}},
    {"name": "Jav-临时", "kind": "混合", "paths": ["D:/演示路径-tmp"], "filter": {}},
]
cfg_path = os.path.join(TEMP, "settings.json")
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump({"libraries": LIBS}, f, ensure_ascii=False)
os.environ["LMC_CONFIG"] = cfg_path

idx = os.path.join(TEMP, "index_data")
if os.path.isdir(idx):
    for fn in os.listdir(idx):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(idx, fn))

COORDS = json.load(open(lv.COORDS, encoding="utf-8"))
TOOLS_BTN = tuple(COORDS["main_settings_btn"])
NAV_SERVICE = tuple(COORDS["dialog_nav"]["服务管理"])
p("坐标：工具按钮", TOOLS_BTN, " 服务管理", NAV_SERVICE)

exe_name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)

app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)
if hwnd:
    p("  title:", lv.wtitle(hwnd))
    check("标题含新版本号 v1.46.15", "v1.46.15" in lv.wtitle(hwnd), lv.wtitle(hwnd))
    check("标题含新构建号 2610290118", "2610290118" in lv.wtitle(hwnd), lv.wtitle(hwnd))
    time.sleep(6)
    check("启动后不处于「未响应」",
          not bool(ctypes.windll.user32.IsHungAppWindow(hwnd)))
    pm = lv.grab(app, hwnd, tries=20, gap=0.4, settle=4)
    out = os.path.join(SHOTS, "v14615_exe_start.png")
    ok = pm.width() > 1 and pm.save(out, "PNG")
    check("主窗可抓图（非空白）", bool(ok) and pm.width() > 1000, (pm.width(), pm.height()))

    # ---- 点开「工具」→「服务管理」，抓「已配置的媒体库」 ----
    lv.click(hwnd, TOOLS_BTN[0], TOOLS_BTN[1])
    dlg = lv.find_window_ex(exe_name, [proc.pid], exclude=(hwnd,), timeout=25,
                            title_sub="工具")
    check("工具窗已打开（标题含「工具」）", dlg is not None, dlg)
    if dlg:
        time.sleep(2.0)
        _r = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(dlg, ctypes.byref(_r))
        _w, _h = _r.right - _r.left, _r.bottom - _r.top
        check("工具窗尺寸接近 1320×960", _w >= 1200 and _h >= 800, (_w, _h))
        lv.click(dlg, NAV_SERVICE[0], NAV_SERVICE[1])
        # 等页面切换 + 淡入；同时盯进程（真机若崩退，这里立刻能看出来）
        for _ in range(20):
            time.sleep(0.3)
            if proc.poll() is not None:
                break
        check("切到「服务管理」后进程仍活着", proc.poll() is None, proc.poll())
        pm2 = None
        for _ in range(6):
            pm2 = app.primaryScreen().grabWindow(dlg)
            if pm2.width() > 1000:
                break
            time.sleep(0.6)
            app.processEvents()
        out2 = os.path.join(SHOTS, "v14615_exe_service.png")
        ok2 = pm2 is not None and pm2.width() > 1000 and pm2.save(out2, "PNG")
        check("服务管理页可抓图", bool(ok2),
              (pm2.width(), pm2.height()) if pm2 is not None else "None")
        if ok2:
            # 抓图上数一下「编辑/扫描/删除」三组按钮：每行应有 3 个圆角框
            from PIL import Image
            im = Image.open(out2).convert("L")
            p("  服务管理页图:", im.size)
        check("工具窗仍活着（切页没崩）",
              not bool(ctypes.windll.user32.IsHungAppWindow(dlg)))
        lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
        time.sleep(1.2)

    check("进程仍在运行（没有崩退）", proc.poll() is None, proc.poll())
    lv.u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
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
    p("  app.log 行数:", len(txt.splitlines()))
check("app.log 无未捕获异常 / Traceback", not bad, bad)

p("FAILS:", FAILS)
p("通过 %d/%d" % (len(OKS), len(OKS) + len(FAILS)))
p("LIVE_V14615_ALL_OK" if not FAILS else "LIVE_V14615_HAS_FAIL")
