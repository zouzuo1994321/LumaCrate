# -*- coding: utf-8 -*-
"""v1.44.0 真机启动自检：真实 exe 存活 / 版本窗 / 启动日志零未捕获异常 / sysmon 单例 / 零残留。"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

sys.stdout = sys.stderr = open(
    r"C:/Users/zouzu/AppData/Local/Temp/exe_selfcheck_v1440.log", "w", encoding="utf-8"
)

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
EXE = os.path.join(ROOT, "流明盒-v1.44.0-2610230093.exe")
EXE_NAME = os.path.basename(EXE).lower()
APP_LOG = os.path.join(ROOT, "index_data", "logs", "app.log")
u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def pids():
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=20).stdout or b""
    res = []
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == EXE_NAME and parts[1].isdigit():
            res.append(int(parts[1]))
    return res


def windows_of(pidset):
    rows = []

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            n = u32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                pid = wt.DWORD()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in pidset:
                    rows.append(buf.value)
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return rows


def main():
    print("[EXE]", EXE, flush=True)
    if not os.path.exists(EXE):
        print("[缺失] exe 尚未生成，终止", flush=True)
        return
    log_size_before = os.path.getsize(APP_LOG) if os.path.exists(APP_LOG) else 0
    proc = None
    try:
        proc = subprocess.Popen([EXE], close_fds=True, cwd=ROOT)
        print("[Popen pid]", proc.pid, flush=True)
        alive_ok = False
        titles = []
        for i in range(1, 9):
            time.sleep(1.2)
            cur = set(pids())
            titles = windows_of(cur)
            print("t=%.1fs pids=%s poll=%s windows=%s" % (i * 1.2, sorted(cur), proc.poll(), titles),
                  flush=True)
            if proc.poll() is None:
                alive_ok = True
        print("存活自检：", "ALIVE_OK" if alive_ok else "DEAD", flush=True)
        print("顶层窗口：", titles, flush=True)
        ver_ok = any("v1.44.0" in t and "2610230093" in t for t in titles)
        print("版本窗校验（标题含 v1.44.0 与 2610230093）：", "VER_OK" if ver_ok else "VER_MISS",
              flush=True)

        try:
            if os.path.exists(APP_LOG):
                with open(APP_LOG, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(max(0, log_size_before))
                    tail = fh.read()
                uncaught = [ln for ln in tail.splitlines() if "未捕获异常" in ln]
                sysmon_lines = [ln for ln in tail.splitlines() if "实时状态：采集能力" in ln]
                print("启动段「未捕获异常」行数：", len(uncaught), flush=True)
                for ln in uncaught[:5]:
                    print("  [EXC]", ln.strip(), flush=True)
                print("启动段「实时状态：采集能力」行数（应为1，证明 sysmon 单例未重建）：",
                      len(sysmon_lines), flush=True)
            else:
                print("[提示] 未找到 app.log", flush=True)
        except Exception as e:
            print("[日志读取失败]", e, flush=True)
    finally:
        if proc is not None and proc.poll() is None:
            for pid in pids():
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        print("[清理完成] 残留:", pids(), flush=True)


main()
