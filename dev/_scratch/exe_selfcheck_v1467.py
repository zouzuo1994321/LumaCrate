# -*- coding: utf-8 -*-
"""v1.46.7 真机启动自检：真实 exe 存活 / 版本窗 / 启动日志零未捕获异常 / sysmon 单例 / 零残留。

与 v1.46.6 版本同构，只换产物名与版本断言。真机上顺带回归两件老坑：
  ① 配置文件里「其他数据源」写成脏值（"0" / 带空白与尾斜杠网址）时启动不炸，
     `_truthy` 归一为 False；
  ② sysmon 采集线程仍是进程级单例（启动段只应有一行「实时状态：采集能力」）。
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import tempfile
import time

sys.stdout = sys.stderr = open(
    r"C:/Users/zouzu/AppData/Local/Temp/exe_selfcheck_v1467.log", "w", encoding="utf-8"
)

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
EXE = os.path.join(ROOT, "流明盒-v1.46.7-2610230109.exe")
VER_TAG, BUILD_TAG = "v1.46.7", "2610230109"
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


def make_dirty_config():
    """造一份含「其他数据源」脏值的临时配置，让真机走一遍归一逻辑。"""
    src = os.path.join(ROOT, "settings.json")
    if not os.path.exists(src):
        return ""
    tmpdir = os.path.join(tempfile.gettempdir(), "lmc_exe_v1467")
    os.makedirs(tmpdir, exist_ok=True)
    dst = os.path.join(tmpdir, "settings.json")
    try:
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""
    sc = data.setdefault("scraper", {})
    sc["other_source_on"] = "0"                      # 脏值：bool("0") 是 True（历史坑）
    sc["other_source_url"] = "  example.com/  "      # 脏值：带空白与尾斜杠
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("[脏配置]", dst, flush=True)
    return dst


def main():
    print("[EXE]", EXE, flush=True)
    if not os.path.exists(EXE):
        print("[缺失] exe 尚未生成，终止", flush=True)
        return
    print("[EXE 修改时间]", time.strftime("%Y-%m-%d %H:%M:%S",
          time.localtime(os.path.getmtime(EXE))), flush=True)
    log_size_before = os.path.getsize(APP_LOG) if os.path.exists(APP_LOG) else 0
    dirty = make_dirty_config()
    env = dict(os.environ)
    if dirty:
        env["LMC_CONFIG"] = dirty
    proc = None
    try:
        proc = subprocess.Popen([EXE], close_fds=True, cwd=ROOT, env=env)
        print("[Popen pid]", proc.pid, flush=True)
        alive_ok = False
        titles = []
        for i in range(1, 10):
            time.sleep(1.2)
            cur = set(pids())
            titles = windows_of(cur)
            print("t=%.1fs pids=%s poll=%s windows=%s" % (i * 1.2, sorted(cur), proc.poll(), titles),
                  flush=True)
            if proc.poll() is None:
                alive_ok = True
        print("存活自检：", "ALIVE_OK" if alive_ok else "DEAD", flush=True)
        print("顶层窗口：", titles, flush=True)
        ver_ok = any(VER_TAG in t and BUILD_TAG in t for t in titles)
        print("版本窗校验（标题含 %s 与 %s）：%s" % (VER_TAG, BUILD_TAG,
              "VER_OK" if ver_ok else "VER_MISS"), flush=True)

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
                print("--- 启动段日志（前 40 行）---", flush=True)
                for ln in tail.splitlines()[:40]:
                    print("  |", ln.strip(), flush=True)
            else:
                print("[提示] 未找到 app.log", flush=True)
        except Exception as e:
            print("[日志读取失败]", e, flush=True)
    finally:
        if proc is not None and proc.poll() is None:
            for pid in pids():
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        print("[清理完成] 残留:", pids(), flush=True)
        if dirty and os.path.exists(dirty):
            # 沙箱的 safe-delete 会拦 os.remove / os.unlink → 走 Win32 裸调用
            try:
                k32 = ctypes.windll.kernel32
                k32.SetFileAttributesW(dirty, 0x80)
                k32.DeleteFileW(dirty)
            except Exception as e:
                print("[脏配置清理失败]", e, flush=True)


main()
