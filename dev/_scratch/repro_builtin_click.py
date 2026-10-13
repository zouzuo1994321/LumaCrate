# -*- coding: utf-8 -*-
"""复现「点内置浏览器没反应」：真机跑 exe → 点按钮 → 枚举所有顶层窗口 + 子进程树。

重点观察：
  1. 子进程是否起来（已知会起）；
  2. pywebview 窗口是否**真的可见**（IsWindowVisible + 尺寸 + 位置）；
  3. 窗口是否跑到屏幕外 / 尺寸为 0。
"""
import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import subprocess
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_repro_builtin.log"

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

u = ctypes.windll.user32


def all_windows():
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    out = []

    def cb(h, l):
        n = u.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 2) if n else ctypes.create_unicode_buffer(2)
        if n:
            u.GetWindowTextW(h, b, n + 1)
        pid = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        r = wt.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        out.append({
            "hwnd": h, "pid": pid.value, "title": b.value,
            "visible": bool(u.IsWindowVisible(h)),
            "rect": (r.left, r.top, r.right - r.left, r.bottom - r.top),
            "cls": (lambda cb2: (u.GetClassNameW(h, cb2, 256), cb2.value)[1])(ctypes.create_unicode_buffer(258)),
        })
        return True

    u.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def procs():
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
    res = []
    if snap in (0, -1):
        return res
    try:
        e = PE()
        e.dwSize = ctypes.sizeof(PE)
        ok = k.Process32First(snap, ctypes.byref(e))
        while ok:
            res.append((e.th32ProcessID, e.th32ParentProcessID,
                        e.szExeFile.decode("mbcs", "replace")))
            ok = k.Process32Next(snap, ctypes.byref(e))
    finally:
        k.CloseHandle(snap)
    return res


def main():
    sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

    def say(m):
        print(m, flush=True)

    say("=" * 60)
    say("复现「点内置浏览器没反应」")
    say("=" * 60)
    if g is None:
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}")

    env = dict(os.environ)
    env["LMC_CONFIG"] = g.make_temp_settings()
    proc = subprocess.Popen([exe], close_fds=True, env=env)
    say(f"[启动] 主进程 pid={proc.pid}")

    try:
        hwnd = g.find_window(exe_name, {proc.pid}, title_sub="Build") \
            or g.find_window(exe_name, {proc.pid})
        if not hwnd:
            say("[失败] 没找到主窗")
            return 1
        g.u32.ShowWindow(hwnd, 9)
        g.u32.SetForegroundWindow(hwnd)
        time.sleep(3.0)

        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
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
            say("[失败] 工具窗没出来")
            return 3
        say(f"[工具窗] {g.wtitle(dlg)!r}")

        r = wt.RECT()
        u.GetWindowRect(dlg, ctypes.byref(r))
        _cw = (r.right - r.left) - g.COORDS_CLIENT_W
        _ch = (r.bottom - r.top) - g.COORDS_CLIENT_H
        if abs(_cw) > 8 or abs(_ch) > 8:
            g.u32.SetWindowPos(dlg, 0, 0, 0, g.COORDS_CLIENT_W + _cw,
                               g.COORDS_CLIENT_H + _ch, 0)
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
        say(f"[对话框] hwnd={cfw}")
        if not cfw:
            say("[失败] 站点验证对话框没出来")
            return 4

        # ---- 记录点击前的窗口快照 ----
        base_pids = {p for p, _, _ in procs()}
        base_wins = {w["hwnd"] for w in all_windows()}
        say(f"[点击前] 进程数={len(base_pids)} 窗口数={len(base_wins)}")

        bp = coords.get("cf_dlg_open_builtin")
        say(f"[点击] 「打开内置浏览器」@{bp}")
        g.u32.SetForegroundWindow(cfw)
        g.click(cfw, bp[0], bp[1])

        # 之后每 2 秒扫一次，共 10 次，找新窗口 / 新进程
        for tick in range(10):
            time.sleep(2.0)
            cur_procs = procs()
            new_pids = [(p, pp, n) for p, pp, n in cur_procs if p not in base_pids]
            new_wins = [w for w in all_windows() if w["hwnd"] not in base_wins]
            say(f"  [T+{(tick + 1) * 2}s] 新进程={[(n, p) for p, _, n in new_pids]} "
                f"新窗口={len(new_wins)}")
            for w in new_wins:
                say(f"      win hwnd={w['hwnd']} pid={w['pid']} "
                    f"vis={w['visible']} rect={w['rect']} cls={w['cls']!r} "
                    f"title={w['title']!r}")
            if new_wins:
                break

        # 最终全量列出 pywebview / msedgewebview2 相关窗口
        say("  --- 所有含 webview / 站点 字样的窗口 ---")
        for w in all_windows():
            t = (w["title"] or "").lower()
            c = (w["cls"] or "").lower()
            if "站点" in t or "webview" in c or "minnano" in t:
                say(f"      hwnd={w['hwnd']} pid={w['pid']} vis={w['visible']} "
                    f"rect={w['rect']} cls={w['cls']!r} title={w['title']!r}")

        say("  --- 进程树（主进程子树）---")
        by_parent = {}
        for p, pp, n in procs():
            by_parent.setdefault(pp, []).append((p, n))
        stack, seen = [proc.pid], set()
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            for p, n in by_parent.get(x, []):
                say(f"      {n}({p}) <- {x}")
                stack.append(p)

        app_pm = g.grab(app, cfw)
        out = os.path.join(ROOT, "dev", "screenshots", "65_repro_builtin_click.png")
        app_pm.save(out)
        say(f"[抓图] {os.path.basename(out)}")

    finally:
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True)
        except Exception:
            pass
        time.sleep(1.5)
        # 杀净所有同名 exe
        for p, pp, n in procs():
            if "2610130065" in n:
                try:
                    subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"],
                                   capture_output=True)
                except Exception:
                    pass
        say("[结束]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
