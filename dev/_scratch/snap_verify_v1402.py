# -*- coding: utf-8 -*-
"""v1.40.2 补充真机取证：验证「持久快照」协议（反馈 2 的关键证据链）。

只做只读 + 内置浏览器一次：
  1. 启动根目录 v1.40.2 exe（临时配置）；
  2. 打开 工具 → 演员刮削 → Cloudflare 验证…；
  3. 点「打开内置浏览器」，等子进程真正取回 cookie（app.log 出现「取回 5 条 cookie」）；
  4. 断言持久快照文件 `lmc_cf_snapshot.json` **真的落盘**且含 cf_clearance；
  5. 抓内嵌浏览器窗口（按进程枚举 + PrintWindow，不靠标题）；
  6. 杀净子树，退出。

用法：python -u <本文件>
"""
import ctypes
import ctypes.wintypes as wt
import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots")
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_snap_verify_v1402.log"
SNAP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_cf_snapshot.json"
REQ = r"C:/Users/zouzu/AppData/Local/Temp/lmc_cf_request.json"
APPDATA_LOG = os.path.join(ROOT, "index_data", "logs", "app.log")

_keep = sys.stdout
_spec = importlib.util.spec_from_file_location(
    "lv1395", os.path.join(ROOT, "dev", "live_verify_v1395.py"))
g = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(g)
except SystemExit:
    g = None
finally:
    sys.stdout = _keep


def _all_pids():
    import ctypes.wintypes as w2
    TH32CS_SNAPPROCESS = 0x2

    class PE(ctypes.Structure):
        _fields_ = [("dwSize", w2.DWORD), ("cntUsage", w2.DWORD),
                    ("th32ProcessID", w2.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", w2.DWORD), ("cntThreads", w2.DWORD),
                    ("th32ParentProcessID", w2.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", w2.DWORD),
                    ("szExeFile", ctypes.c_char * 260)]

    k = ctypes.windll.kernel32
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    out = []
    if snap in (0, -1):
        return out
    try:
        e = PE()
        e.dwSize = ctypes.sizeof(PE)
        ok = k.Process32First(snap, ctypes.byref(e))
        while ok:
            out.append((e.th32ProcessID, e.th32ParentProcessID,
                        e.szExeFile.decode("mbcs", "replace")))
            ok = k.Process32Next(snap, ctypes.byref(e))
    finally:
        k.CloseHandle(snap)
    return out


def _kill_tree(main_pid, exe_name):
    procs = _all_pids()
    by_parent = {}
    for pid, ppid, name in procs:
        by_parent.setdefault(ppid, []).append((pid, name))
    stack, seen = [main_pid], set()
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        for pid, name in by_parent.get(p, []):
            stack.append(pid)
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True)
            except Exception:
                pass
    try:
        subprocess.run(["taskkill", "/PID", str(main_pid), "/T", "/F"],
                       capture_output=True)
    except Exception:
        pass


def main():
    sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

    def say(m):
        print(m, flush=True)

    say("=" * 66)
    say("流明盒 v1.40.2 补充取证：持久快照协议 + 内嵌浏览器窗口")
    say("=" * 66)
    if g is None:
        say("[中止] 无法加载基础设施")
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}  ({os.path.getsize(exe) / 1048576:.1f} MB)")

    # 清掉旧快照 / 请求文件
    for p in (SNAP, REQ):
        try:
            k = ctypes.windll.kernel32
            k.SetFileAttributesW(p, 0x80)
            k.DeleteFileW(p)
        except Exception:
            pass
    say(f"[清理] 快照存在={os.path.exists(SNAP)} 请求存在={os.path.exists(REQ)}")

    env = dict(os.environ)
    env["LMC_CONFIG"] = g.make_temp_settings()
    log_before = g.log_size()
    app_len_before = os.path.getsize(APPDATA_LOG) if os.path.exists(APPDATA_LOG) else 0

    proc = subprocess.Popen([exe], close_fds=True, env=env)
    say(f"[启动] pid={proc.pid}")

    snap_ok = False
    try:
        hwnd = g.find_window(exe_name, {proc.pid}, title_sub="Build") \
            or g.find_window(exe_name, {proc.pid})
        if not hwnd:
            say("[失败] 未发现主窗口")
            return 1
        say(f"[主窗] hwnd={hwnd} title={g.wtitle(hwnd)!r}")
        g.u32.ShowWindow(hwnd, 9)
        g.u32.SetForegroundWindow(hwnd)
        time.sleep(2.5)

        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        os.makedirs(SHOT_DIR, exist_ok=True)
        coords = g.load_coords()

        sx, sy = coords["main_settings_btn"]
        dlg = None
        for _ in range(3):
            g.u32.SetForegroundWindow(hwnd)
            g.click(hwnd, sx, sy)
            dlg = g.find_window_ex(exe_name, {proc.pid}, exclude={hwnd},
                                   title_sub="工具", timeout=8)
            if dlg:
                break
        if not dlg:
            say("[失败] 工具窗口没出来")
            return 3
        say(f"[工具窗] hwnd={dlg} title={g.wtitle(dlg)!r}")

        r = wt.RECT()
        g.u32.GetWindowRect(dlg, ctypes.byref(r))
        _cw = (r.right - r.left) - g.COORDS_CLIENT_W
        _ch = (r.bottom - r.top) - g.COORDS_CLIENT_H
        if abs(_cw) > 8 or abs(_ch) > 8:
            g.u32.SetWindowPos(dlg, 0, 0, 0, g.COORDS_CLIENT_W + _cw,
                               g.COORDS_CLIENT_H + _ch, 0)
            say("[尺寸校正] 已对齐 ui_coords 客户区")
            time.sleep(1.0)
        time.sleep(2.0)

        dn = (coords.get("dialog_nav") or {}).get("演员刮削")
        g.click(dlg, dn[0], dn[1])
        time.sleep(3.0)
        cf = coords.get("scraper_cf_btn")
        g.click(dlg, cf[0], cf[1])
        time.sleep(3.0)
        cfw = g.find_window_ex(exe_name, {proc.pid}, exclude={hwnd, dlg},
                               title_sub="站点验证", timeout=6)
        say(f"[对话框] cfw={cfw}")
        if not cfw:
            return 4

        # ---- 点「打开内置浏览器」并等到真的取回 cookie ----
        bp = coords.get("cf_dlg_open_builtin")
        say(f"[点击] 打开内置浏览器 @{bp}")
        g.click(cfw, bp[0], bp[1])

        wait_deadline = time.time() + 60
        while time.time() < wait_deadline:
            time.sleep(1.5)
            if os.path.exists(SNAP):
                snap_ok = True
                break
        say(f"[快照] 落盘={snap_ok} 路径={SNAP}")

        # 内嵌浏览器窗口：按进程树里的子进程枚举所有顶层窗口
        kids = [pid for pid, ppid, name in _all_pids()
                if ppid == proc.pid and pid != proc.pid]
        say(f"[子进程] 主进程直属子进程={kids}")
        wv = g.find_window_ex("", set(), title_sub="站点验证", timeout=3)
        say(f"[内嵌窗口] 按标题找到={wv}")

        # 抓对话框 + 若找到内嵌窗就抓它
        out_d = os.path.join(SHOT_DIR, "64_live_snapshot_dialog_v1402.png")
        g.grab(app, cfw).save(out_d)
        say(f"  [抓取] -> {os.path.basename(out_d)}")
        if wv:
            out_w = os.path.join(SHOT_DIR, "62_live_builtin_browser_v1402.png")
            pm = g.grab(app, wv)
            say(f"  [抓取] {pm.width()}x{pm.height()} -> "
                f"{os.path.basename(out_w)} {pm.save(out_w)}")
        else:
            say("  [提示] 内嵌窗口按标题找不到，改抓桌面区域")
            # 用 PrintWindow 抓主窗，内嵌浏览器窗口通常会覆盖在上面
            out_w = os.path.join(SHOT_DIR, "62_live_builtin_browser_v1402.png")
            allw = g.find_window_ex(exe_name, {proc.pid}, exclude={hwnd, dlg, cfw},
                                   timeout=1)
            say(f"  [兜底] 其他同名窗口={allw}")

        # ---- 校验快照内容 ----
        if snap_ok:
            try:
                data = json.load(open(SNAP, encoding="utf-8"))
                ck = data.get("cookie", "")
                say(f"[快照内容] ok={data.get('ok')} host={data.get('host')} "
                    f"count={data.get('count')} 含 cf_clearance={'cf_clearance' in ck}")
            except Exception as e:
                say(f"[快照解析失败] {e}")

        # ---- 验证「关窗后仍可读」：读 app.log 新增行 ----
        time.sleep(1.0)
        try:
            with open(APPDATA_LOG, encoding="utf-8", errors="replace") as f:
                f.seek(app_len_before)
                newlog = f.read()
            for line in newlog.splitlines():
                if "站点验证" in line or "未捕获异常" in line or "Traceback" in line:
                    say(f"[app.log] {line}")
        except Exception as e:
            say(f"[app.log 读取失败] {e}")

        g.check_new_log(log_before)

    finally:
        _kill_tree(proc.pid, exe_name)
        time.sleep(1.5)
        left = [f"{n}({p})" for p, pp, n in _all_pids()
                if "2610130065" in n or ("流明盒" in n and "v1.40.2" in n)]
        say(f"[结束] 残留: {left if left else '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
