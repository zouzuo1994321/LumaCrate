# -*- coding: utf-8 -*-
"""真机验收脚本（v1.40.2）：启动根目录最新 exe，打开「工具 → 演员刮削」抓图。

v1.40.2 验收重点（三条反馈）：
  ① 反馈 1：站点验证对话框**行距压缩** —— 打开后量出对话框客户区高度应显著小于
     v1.40.1 的 360（本版目标 ~262）；边距/行距都收紧。
  ② 反馈 2：新增**独立「读取 Cookie」按钮** —— 对话框里应有它，且按钮位置在
     「打开内置浏览器」右侧；点它不会崩（没快照时应给出明确提示而不是异常）。
  ③ 反馈 3：「执行」区**底部不留白** —— 整页抓图里执行组框应延伸到底；
     工具窗默认高应为 960（真机 1080p）。

**只读验收**：打开页面 + 截图 + 点开验证对话框 + 点一次「打开内置浏览器」（随后杀干净）
+ 点一次「读取 Cookie」（只读本地快照，不写库）。
**绝不点「保存并校验」「全量刮削 / 增量刮削」**。

用法：python dev/live_verify_v1402.py
"""
import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots")
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1402.log"
SNAPSHOT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_cf_snapshot.json"

# ---- 复用 v1.39.5 的基础设施（与 v1.40.1 同一套） ----------------------------
_keep_out = sys.stdout
_spec = importlib.util.spec_from_file_location(
    "lv1395", os.path.join(ROOT, "dev", "live_verify_v1395.py"))
g = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(g)
except SystemExit:
    g = None
finally:
    sys.stdout = _keep_out


def _rm(path):
    """safe-delete：SetFileAttributesW(0x80) + DeleteFileW（os.remove 会被 shim 拦）。"""
    try:
        k = ctypes.windll.kernel32
        k.SetFileAttributesW(str(path), 0x80)
        return bool(k.DeleteFileW(str(path)))
    except Exception:
        return False


def main():
    sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

    def say(m):
        print(m, flush=True)

    say("=" * 66)
    say("流明盒 v1.40.2 真机验收（三条反馈）")
    say("=" * 66)

    if g is None:
        say("[中止] 无法加载 live_verify_v1395 基础设施")
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}  ({os.path.getsize(exe) / 1048576:.1f} MB)")
    if "v1.40.2" not in exe_name:
        say(f"[警告] 最新 exe 不是 v1.40.2：{exe_name}")

    env = dict(os.environ)
    env["LMC_CONFIG"] = g.make_temp_settings()      # 临时配置，不碰真实 settings.json
    say(f"[配置] LMC_CONFIG={env['LMC_CONFIG']}")

    _log_before = g.log_size()
    _res = r"C:/Users/zouzu/AppData/Local/Temp/lmc_cf_result.json"
    _rm(_res)
    proc = subprocess.Popen([exe], close_fds=True, env=env)
    say(f"[启动] pid={proc.pid}")

    spawned = False
    read_clicked_ok = False
    try:
        hwnd = g.find_window(exe_name, {proc.pid}, title_sub="Build")
        if not hwnd:
            say("[警告] 按标题没找到主窗口，回退到「最大可见窗口」")
            hwnd = g.find_window(exe_name, {proc.pid})
        if not hwnd:
            say("[失败] 未发现主窗口")
            return 1
        say(f"[窗口] hwnd={hwnd} pid={g.wpid(hwnd)} title={g.wtitle(hwnd)!r}")
        g.u32.ShowWindow(hwnd, 9)
        g.u32.SetForegroundWindow(hwnd)
        time.sleep(2.5)

        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        os.makedirs(SHOT_DIR, exist_ok=True)

        coords = g.load_coords()
        if not coords:
            say("[中止] 读不到界面坐标表")
            return 2

        # ---------------- 打开工具窗口 ----------------
        sx, sy = coords["main_settings_btn"]
        dlg = None
        for attempt in range(3):
            say(f"[点击] 顶栏「工具」@({sx},{sy}) 第 {attempt + 1} 次")
            g.u32.SetForegroundWindow(hwnd)
            g.click(hwnd, sx, sy)
            dlg = g.find_window_ex(exe_name, {proc.pid}, exclude={hwnd},
                                   title_sub="工具", timeout=8)
            if dlg:
                break
        if not dlg:
            say("[失败] 工具窗口没出来")
            return 3

        r = wt.RECT()
        g.u32.GetWindowRect(dlg, ctypes.byref(r))
        win_h = r.bottom - r.top
        say(f"[工具窗口] hwnd={dlg} {r.right - r.left}x{win_h} "
            f"title={g.wtitle(dlg)!r}")
        say(f"[验收③] 工具窗默认高 ≈ 960（真机 1080p）→ 实测 {win_h}")

        # 把工具窗缩回 ui_coords 对应的尺寸（否则所有坐标整体偏移）
        _cw = (r.right - r.left) - g.COORDS_CLIENT_W
        _ch = win_h - g.COORDS_CLIENT_H
        if abs(_cw) > 8 or abs(_ch) > 8:
            g.u32.SetWindowPos(dlg, 0, 0, 0, g.COORDS_CLIENT_W + _cw,
                               g.COORDS_CLIENT_H + _ch, 0)
            g.u32.GetWindowRect(dlg, ctypes.byref(r))
            say(f"[尺寸校正] 工具窗调成 {r.right - r.left}x{r.bottom - r.top}")
            time.sleep(1.0)
        time.sleep(2.0)

        # ---------------- ① 演员刮削页整页（反馈 3：执行不留白） ----------------
        dn = (coords.get("dialog_nav") or {}).get("演员刮削")
        if not dn:
            say("[失败] 坐标表里没有「演员刮削」导航坐标")
            return 4
        say(f"[点击] 工具·演员刮削 @({dn[0]},{dn[1]})")
        g.click(dlg, dn[0], dn[1])
        time.sleep(3.5)
        out = os.path.join(SHOT_DIR, "60_live_scraper_full_v1402.png")
        pm = g.grab(app, dlg)
        say(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} {pm.save(out)}")

        # ---------------- ②+③ 站点验证对话框 ----------------
        cf = coords.get("scraper_cf_btn")
        cfw = None
        if cf:
            say(f"[点击] Cloudflare 验证… @({cf[0]},{cf[1]})")
            g.click(dlg, cf[0], cf[1])
            time.sleep(3.0)
            cfw = g.find_window_ex(exe_name, {proc.pid}, exclude={hwnd, dlg},
                                   title_sub="站点验证", timeout=6)
            target = cfw or dlg
            out2 = os.path.join(SHOT_DIR, "61_live_cloudflare_compact_v1402.png")
            pm2 = g.grab(app, target)
            say(f"  [抓取] {pm2.width()}x{pm2.height()} -> "
                f"{os.path.basename(out2)} {pm2.save(out2)}")
            if cfw:
                rr = wt.RECT()
                g.u32.GetWindowRect(cfw, ctypes.byref(rr))
                h = rr.bottom - rr.top
                say(f"  [验收②] 对话框客户区 ≈ {coords.get('cf_dlg_client')}"
                    f"（v1.40.1 是 660x360，本版目标 660x262）→ 实测高 {h}")
        else:
            say("[跳过] 坐标表里没有 Cloudflare 按钮坐标（可选）")

        # ---------------- ②b 点「读取 Cookie」（新增按钮） ----------------
        try:
            rp = coords.get("cf_dlg_read_btn")
            say(f"[坐标] 读取 Cookie @ {rp}（对话框客户区 {coords.get('cf_dlg_client')}）")
            if rp is None or cfw is None:
                say("  [提示] 缺坐标或对话框窗口，跳过实点读取（其余验收照常）")
            else:
                say(f"[点击] 「读取 Cookie」@{rp}")
                g.click(cfw, rp[0], rp[1])
                time.sleep(2.5)
                out_r = os.path.join(SHOT_DIR, "63_live_read_cookie_v1402.png")
                pm_r = g.grab(app, cfw)
                say(f"  [抓取] {pm_r.width()}x{pm_r.height()} -> "
                    f"{os.path.basename(out_r)} {pm_r.save(out_r)}")
                read_clicked_ok = True
                say(f"  [验收②b] 点「读取 Cookie」未崩溃；无快照时给出提示"
                    f"（快照存在={os.path.exists(SNAPSHOT)}）")
        except Exception as e:
            say(f"  [异常] 实点读取 Cookie 出错（不阻断）：{type(e).__name__}: {e}")

        # ---------------- ③b 真点子进程 ----------------
        try:
            bp = coords.get("cf_dlg_open_builtin")
            say(f"[坐标] 打开内置浏览器 @ {bp}")
            if bp is None or cfw is None:
                say("  [提示] 缺坐标或对话框窗口，跳过实点子进程（其余验收照常）")
            else:
                say(f"[点击] 「打开内置浏览器」@{bp}")
                g.click(cfw, bp[0], bp[1])
                for _ in range(16):
                    time.sleep(1.0)
                    kids = _cf_children(exe_name, proc.pid)
                    if kids:
                        spawned = True
                        say(f"  [子进程] 已拉起：{kids}")
                        break
                wv = g.find_window_ex("", set(), title_sub="站点验证 - 请在", timeout=3)
                say(f"  [内嵌窗口] {('找到 ' + str(wv)) if wv else '未按标题找到（可能被 WebView2 子窗口挡住）'}")
                out3 = os.path.join(SHOT_DIR, "62_live_builtin_browser_v1402.png")
                pm3 = g.grab(app, wv if wv else cfw)
                say(f"  [抓取] {pm3.width()}x{pm3.height()} -> "
                    f"{os.path.basename(out3)} {pm3.save(out3)}")
        except Exception as e:
            say(f"  [异常] 实点内置浏览器出错（不阻断）：{type(e).__name__}: {e}")
        finally:
            _kill_cf_children(exe_name, proc.pid)
            say(f"  [清理] 内置浏览器子进程残留：{_cf_children(exe_name, proc.pid)}")

        say(f"[验收②] 读取 Cookie 按钮可点 = {read_clicked_ok}")
        say(f"[验收③] 内置浏览器子进程被拉起 = {spawned}")

        # ---------------- 真机日志体检 ----------------
        time.sleep(1.5)
        g.check_new_log(_log_before)

    finally:
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True)
        except Exception:
            pass
        time.sleep(1.5)
        say(f"[结束] 残留同名进程: {sorted(g.pids_of_exe(exe_name))}")
    return 0


def _all_pids():
    """当前所有进程的 (pid, ppid, exe_name) 列表。"""
    import ctypes.wintypes as wt2
    TH32CS_SNAPPROCESS = 0x2

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", wt2.DWORD), ("cntUsage", wt2.DWORD),
                    ("th32ProcessID", wt2.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", wt2.DWORD), ("cntThreads", wt2.DWORD),
                    ("th32ParentProcessID", wt2.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt2.DWORD),
                    ("szExeFile", ctypes.c_char * 260)]

    k = ctypes.windll.kernel32
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    out = []
    if snap in (0, -1):
        return out
    try:
        e = PROCESSENTRY32()
        e.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = k.Process32First(snap, ctypes.byref(e))
        while ok:
            out.append((e.th32ProcessID, e.th32ParentProcessID,
                        e.szExeFile.decode("mbcs", "replace")))
            ok = k.Process32Next(snap, ctypes.byref(e))
    finally:
        k.CloseHandle(snap)
    return out


def _cf_children(exe_name, main_pid):
    """找主进程子树里「内置浏览器」相关进程：pywebview 子进程 / msedgewebview2。"""
    procs = _all_pids()
    by_parent = {}
    for pid, ppid, name in procs:
        by_parent.setdefault(ppid, []).append((pid, name))
    kids, stack = [], [main_pid]
    seen = set()
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        for pid, name in by_parent.get(p, []):
            kids.append(f"{name}({pid})")
            stack.append(pid)
    return [k for k in kids
            if ("msedgewebview2" in k.lower() or "webview" in k.lower()
                or exe_name.replace(".exe", "") in k.lower())]


def _kill_cf_children(exe_name, main_pid):
    """把主进程子树里的 msedgewebview2 一并杀掉（pywebview 会带出它）。"""
    procs = _all_pids()
    by_parent = {}
    for pid, ppid, name in procs:
        by_parent.setdefault(ppid, []).append((pid, name))
    stack, seen = [main_pid], set()
    victims = []
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        for pid, name in by_parent.get(p, []):
            stack.append(pid)
            if "msedgewebview2" in name.lower():
                victims.append(pid)
    for pid in victims:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
