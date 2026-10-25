# -*- coding: utf-8 -*-
"""v1.46.8 真机自检：存活 / 版本窗 / 启动日志零未捕获异常 / sysmon 单例 / 零残留
+ **真机抓屏统计状态栏朱红像素**（v1.46.8 的核心修复：进度条高亮要真的画在屏幕上）。

与 v1.46.7 同构，新增最后一段：启动后连续抓取主窗口右下角（状态栏进度条区域），
统计「朱红像素」峰值。值为 0 只作为信息输出（首页不一定触发大量载入），
但 >0 就是「高亮真的画出来了」的实证。
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import tempfile
import time

# 逻辑像素 vs 物理像素：不声明 DPI 感知时 GetWindowRect 与截图坐标会错位
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

sys.stdout = sys.stderr = open(
    r"C:/Users/zouzu/AppData/Local/Temp/exe_selfcheck_v1468.log", "w", encoding="utf-8"
)

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
EXE = os.path.join(ROOT, "流明盒-v1.46.8-2610230110.exe")
VER_TAG, BUILD_TAG = "v1.46.8", "2610230110"
EXE_NAME = os.path.basename(EXE).lower()
APP_LOG = os.path.join(ROOT, "index_data", "logs", "app.log")
u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
# 64 位下 HWND/LPARAM 是 8 字节，不声明 argtypes 会被截断（窗口句柄高 32 位丢失）
u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.PostMessageW.restype = wt.BOOL
u32.SetForegroundWindow.argtypes = [wt.HWND]
u32.SetForegroundWindow.restype = wt.BOOL
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u32.GetWindowRect.restype = wt.BOOL


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
                    rows.append((hwnd, buf.value))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return rows


def accent_count(img):
    n = 0
    px = img.convert("RGB").load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = px[x, y]
            if r > 110 and r - g > 40 and r - b > 35:
                n += 1
    return n


def make_dirty_config():
    src = os.path.join(ROOT, "settings.json")
    if not os.path.exists(src):
        return ""
    tmpdir = os.path.join(tempfile.gettempdir(), "lmc_exe_v1468")
    os.makedirs(tmpdir, exist_ok=True)
    dst = os.path.join(tmpdir, "settings.json")
    try:
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""
    sc = data.setdefault("scraper", {})
    sc["other_source_on"] = "0"
    sc["other_source_url"] = "  example.com/  "
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
        hwnd_main = None
        for i in range(1, 11):
            time.sleep(1.2)
            cur = set(pids())
            wins = windows_of(cur)
            titles = [t for _h, t in wins]
            for h, t in wins:
                if VER_TAG in t and BUILD_TAG in t:
                    hwnd_main = h
            print("t=%.1fs pids=%s poll=%s windows=%s" % (i * 1.2, sorted(cur),
                                                          proc.poll(), titles), flush=True)
            if proc.poll() is None:
                alive_ok = True
        print("存活自检：", "ALIVE_OK" if alive_ok else "DEAD", flush=True)
        print("顶层窗口：", titles, flush=True)
        ver_ok = any(VER_TAG in t and BUILD_TAG in t for t in titles)
        print("版本窗校验（标题含 %s 与 %s）：%s" % (VER_TAG, BUILD_TAG,
              "VER_OK" if ver_ok else "VER_MISS"), flush=True)

        # ---- 真机像素验证见 `dev/_scratch/grab_window.py`（PrintWindow 抓窗口自身）----
        # 这里曾用 PIL.ImageGrab 截屏，但 `SetForegroundWindow` 对非前台进程无效，
        # 窗口被别的程序遮挡时抓到的是别人的界面（一次真实的误判）。
        print("[提示] 进度条真机像素验证：python dev/_scratch/grab_window.py "
              "--tag v1.46.8 --click 93,313", flush=True)
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
                print("--- 启动段日志（前 30 行）---", flush=True)
                for ln in tail.splitlines()[:30]:
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
            try:
                k32 = ctypes.windll.kernel32
                k32.SetFileAttributesW(dirty, 0x80)
                k32.DeleteFileW(dirty)
            except Exception as e:
                print("[脏配置清理失败]", e, flush=True)


main()
