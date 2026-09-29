# -*- coding: utf-8 -*-
"""v1.34.2 真机验收：启动冻结 exe，等其初始化，读 app.log 查未捕获异常，枚举真实窗口。
用法: python live_verify_v1342.py <exe_path> <work_dir>
"""
import os
import sys
import time
import shutil
import ctypes
import ctypes.wintypes as wt
import subprocess

exe = sys.argv[1]
work = sys.argv[2]
os.makedirs(work, exist_ok=True)
dst_exe = os.path.join(work, "LumaCrate.exe")
if not os.path.exists(dst_exe):
    shutil.copy2(exe, dst_exe)

env = dict(os.environ)
env["LMC_NO_SPLASH"] = "1"          # 跳过启动画面，加快就绪
p = subprocess.Popen([dst_exe], cwd=work, env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 等它初始化（含建索引目录、打开样式、统计媒体库）
time.sleep(28)

alive = p.poll() is None
log = os.path.join(work, "index_data", "logs", "app.log")
log_txt = ""
if os.path.exists(log):
    with open(log, encoding="utf-8", errors="replace") as f:
        log_txt = f.read()

# 用 ctypes 枚举该进程的顶层窗口，确认真实 GUI 起来了
user32 = ctypes.windll.user32
pid = p.pid
found = []


def cb(hwnd, lparam):
    wpid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
    if wpid.value == pid:
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        vis = bool(user32.IsWindowVisible(hwnd))
        found.append((buf.value, cls.value, vis, hwnd))
    return True


WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows(WNDENUMPROC(cb), 0)

print("alive_after_28s =", alive)
print("windows(pid=%d) =" % pid, [(t, c, v) for t, c, v, _ in found])

bad = [ln for ln in log_txt.splitlines()
       if ("未捕获异常" in ln or "Traceback" in ln or "CRITICAL" in ln or "ERROR" in ln)]
print("log_lines =", len(log_txt.splitlines()))
print("log_head:")
for ln in log_txt.splitlines()[:12]:
    print("   ", ln)
print("log_tail:")
for ln in log_txt.splitlines()[-8:]:
    print("   ", ln)
print("SUSPECT_LINES =", len(bad))
for ln in bad[-10:]:
    print("   !!", ln)

# 收尾
try:
    p.terminate()
    time.sleep(2)
except Exception:
    pass
try:
    if p.poll() is None:
        p.kill()
except Exception:
    pass
print("done")
