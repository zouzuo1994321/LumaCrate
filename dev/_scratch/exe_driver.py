# -*- coding: utf-8 -*-
"""v1.46.13 打包后 exe 的**可编排**真机驱动。

用法：把动作串成参数，逐条执行，每步可抓图。

  L:x,y   左键点客户区坐标      R:x,y   右键点客户区坐标
  S:x,y   左键点屏幕坐标（弹窗 / 菜单用）  M:x,y 只移动光标
  W:1.5   等待秒数              G:名字  抓主窗口
  F:名字  抓整屏（菜单 / 弹窗是独立顶层窗口，抓主窗抓不到）

示例：`L:100,506 R:100,506 W:0.8 F:menu`
"""
import os
import sys
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

exe = None
for fn in os.listdir(TEMP):
    if fn.lower().endswith(".exe"):
        exe = os.path.join(TEMP, fn)
exe_name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
env = dict(os.environ)
if os.environ.get("DRV_MIN") == "1":       # 关掉启动画面 / 实时状态 / 背景
    env.update({"LMC_NO_SYSPLASH": "1", "LMC_NO_SYSMON": "1", "LMC_NO_BACKDROP": "1"})
print("env MIN:", os.environ.get("DRV_MIN"))
proc = subprocess.Popen([exe], cwd=TEMP, env=env)
print("启动:", exe_name, "pid=", proc.pid)

app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
print("hwnd:", hwnd, lv.wtitle(hwnd))
time.sleep(8)

LEFTDOWN, LEFTUP, RIGHTDOWN, RIGHTUP = 0x0002, 0x0004, 0x0008, 0x0010


def to_screen(cx, cy):
    pt = wintypes.POINT(cx, cy)
    uu.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def move_to(sx, sy):
    uu.SetCursorPos(sx, sy)
    time.sleep(0.2)


def click_screen(sx, sy, right=False):
    uu.SetForegroundWindow(hwnd)
    move_to(sx, sy)
    uu.mouse_event(RIGHTDOWN if right else LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.09)
    uu.mouse_event(RIGHTUP if right else LEFTUP, 0, 0, 0, 0)


def grab_win(name):
    pm = lv.grab(app, hwnd, tries=10, gap=0.3, settle=5)
    pm.save(os.path.join(SHOTS, name + ".png"), "PNG")
    print("  抓主窗:", name, pm.width(), pm.height())


def grab_screen(name):
    pm = app.primaryScreen().grabWindow(0)
    pm.save(os.path.join(SHOTS, name + ".png"), "PNG")
    print("  抓整屏:", name, pm.width(), pm.height())


for a in sys.argv[1:]:
    try:
        op, val = a.split(":", 1)
    except ValueError:
        continue
    if op == "L" or op == "R":
        x, y = (int(v) for v in val.split(","))
        sx, sy = to_screen(x, y)
        click_screen(sx, sy, right=(op == "R"))
        print("  %s 客户区 %d,%d → 屏幕 %d,%d" % (op, x, y, sx, sy))
    elif op == "S":
        x, y = (int(v) for v in val.split(","))
        click_screen(x, y)
        print("  S 屏幕 %d,%d" % (x, y))
    elif op == "M":
        x, y = (int(v) for v in val.split(","))
        move_to(x, y)
        print("  M 屏幕 %d,%d" % (x, y))
    elif op == "W":
        time.sleep(float(val))
        print("  等待", val)
    elif op == "G":
        grab_win(val)
    elif op == "F":
        grab_screen(val)

print("DONE")
