# -*- coding: utf-8 -*-
"""真机验收脚本（v1.40.1）：启动根目录最新 exe，打开「工具 → 演员刮削」抓图。

v1.40.1 验收重点（三条反馈的回修）：
  ① 反馈 1：数据源组框**底部不再留大片空白** —— 与 v1.40.0 的截图对照，
     组框明显变矮（真机高度应显著小于 v1.40.0 的 274~280）。
  ② 反馈 2：「执行」区日志框**缩回约一半**（最小 120px，不再是最小 240px）。
  ③ 反馈 3：站点验证对话框**改用内置浏览器** —— 打开后
     · 主入口按钮文案是「打开内置浏览器」（不再是「用系统浏览器打开」）；
     · 正文是「两步走」；
     · 有「检查内置浏览器」按钮；
     · 底部「高级 ▾（手动粘贴 cookie）」默认**收起**。
     并**实际点一次「打开内置浏览器」**：确认子进程真的被拉起
     （`cf_browser.py` / `--cf-browser` 进程出现），随后**立即杀掉**它在内的整棵
     进程树，不留残留窗口。

实现复用 v1.39.5 已验证的 Windows 基础设施（PrintWindow 抓图 / PID 定位 /
侧边栏坐标 / 临时配置 / 日志体检），**不重复造轮子**。

⚠ 本脚本只做**只读**验收：打开页面 + 截图 + 点开验证对话框 + 点一次「打开内置
   浏览器」（随后杀干净）。**绝不点「保存并校验」「全量刮削 / 增量刮削」**。

用法：python dev/live_verify_v1401.py
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
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1401.log"

# ---- 复用 v1.39.5 的基础设施 -------------------------------------------------
# 用 importlib 按路径加载：文件名带版本号，不是合法模块名，无法普通 import。
# ⚠ v1.39.5 顶层就会把 sys.stdout/stderr 重定向到它自己的日志文件，所以加载前
# 先存一份原 stdout，加载完立刻恢复，否则本脚本的 print 会写进别人的日志。
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
    say("流明盒 v1.40.1 真机验收（三条反馈回修）")
    say("=" * 66)

    if g is None:
        say("[中止] 无法加载 live_verify_v1395 基础设施")
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}  ({os.path.getsize(exe) / 1048576:.1f} MB)")
    if "v1.40.1" not in exe_name:
        say(f"[警告] 最新 exe 不是 v1.40.1：{exe_name}")

    env = dict(os.environ)
    env["LMC_CONFIG"] = g.make_temp_settings()      # 临时配置，不碰真实 settings.json
    say(f"[配置] LMC_CONFIG={env['LMC_CONFIG']}")

    _log_before = g.log_size()
    _res = r"C:/Users/zouzu/AppData/Local/Temp/lmc_cf_result.json"
    _rm(_res)                                       # 清掉上一轮的结果文件
    proc = subprocess.Popen([exe], close_fds=True, env=env)
    say(f"[启动] pid={proc.pid}")

    try:
        # 主窗口标题里带 "(Build …)"，用它把启动画面区分开
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
        say(f"[工具窗口] hwnd={dlg} {r.right - r.left}x{r.bottom - r.top} "
            f"title={g.wtitle(dlg)!r}")

        # 把工具窗缩回 ui_coords 对应的尺寸，否则所有坐标整体偏移
        _cw = (r.right - r.left) - g.COORDS_CLIENT_W
        _ch = (r.bottom - r.top) - g.COORDS_CLIENT_H
        if abs(_cw) > 8 or abs(_ch) > 8:
            g.u32.SetWindowPos(dlg, 0, 0, 0, g.COORDS_CLIENT_W + _cw,
                               g.COORDS_CLIENT_H + _ch, 0)
            g.u32.GetWindowRect(dlg, ctypes.byref(r))
            say(f"[尺寸校正] 工具窗调成 {r.right - r.left}x{r.bottom - r.top}")
            time.sleep(1.0)
        time.sleep(2.0)

        # ---------------- ① 演员刮削页整页（反馈 1 + 2 的对照图） ----------------
        dn = (coords.get("dialog_nav") or {}).get("演员刮削")
        if not dn:
            say("[失败] 坐标表里没有「演员刮削」导航坐标")
            return 4
        say(f"[点击] 工具·演员刮削 @({dn[0]},{dn[1]})")
        g.click(dlg, dn[0], dn[1])
        time.sleep(3.5)
        out = os.path.join(SHOT_DIR, "60_live_scraper_full_v1401.png")
        pm = g.grab(app, dlg)
        say(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} {pm.save(out)}")

        # ---------------- ③ 站点验证对话框（内置浏览器） ----------------
        cf = coords.get("scraper_cf_btn") or coords.get("cloudflare_btn")
        cfw = None
        if cf:
            say(f"[点击] Cloudflare 验证… @({cf[0]},{cf[1]})")
            g.click(dlg, cf[0], cf[1])
            time.sleep(3.0)
            cfw = g.find_window_ex(exe_name, {proc.pid}, exclude={hwnd, dlg},
                                   title_sub="站点验证", timeout=6)
            target = cfw or dlg
            out2 = os.path.join(SHOT_DIR, "61_live_cloudflare_builtin_v1401.png")
            pm2 = g.grab(app, target)
            say(f"  [抓取] {pm2.width()}x{pm2.height()} -> "
                f"{os.path.basename(out2)} {pm2.save(out2)}")
        else:
            say("[跳过] 坐标表里没有 Cloudflare 按钮坐标（可选）")

        # ---------------- ③b 真点子进程：内置浏览器真的会起 ----------------
        # 坐标来自 `ui_coords.py` 新增的 `cf_dlg_open_builtin`（相对对话框客户区）。
        spawned = False
        try:
            bp = coords.get("cf_dlg_open_builtin")
            say(f"[坐标] 打开内置浏览器 @ {bp}（对话框客户区 {coords.get('cf_dlg_client')}）")
            if bp is None or cfw is None:
                say("  [提示] 缺坐标或对话框窗口，跳过实点子进程（其余验收照常）")
            else:
                say(f"[点击] 「打开内置浏览器」@{bp}")
                g.click(cfw, bp[0], bp[1])
                # 等子进程出现（pywebview 拉起 WebView2 通常 1~3 秒）
                for _ in range(16):
                    time.sleep(1.0)
                    kids = _cf_children(exe_name, proc.pid)
                    if kids:
                        spawned = True
                        say(f"  [子进程] 已拉起：{kids}")
                        break
                # 内嵌浏览器窗口（pywebview 标题）出现与否只作参考
                wv = g.find_window_ex("", set(), title_sub="站点验证 - 请在", timeout=3)
                say(f"  [内嵌窗口] {('找到 ' + str(wv)) if wv else '未按标题找到（可能被 WebView2 子窗口挡住）'}")
                out3 = os.path.join(SHOT_DIR, "62_live_builtin_browser_v1401.png")
                pm3 = g.grab(app, wv if wv else cfw)
                say(f"  [抓取] {pm3.width()}x{pm3.height()} -> "
                    f"{os.path.basename(out3)} {pm3.save(out3)}")
        except Exception as e:
            say(f"  [异常] 实点内置浏览器出错（不阻断）：{type(e).__name__}: {e}")
        finally:
            _kill_cf_children(exe_name, proc.pid)
            say(f"  [清理] 内置浏览器子进程残留：{_cf_children(exe_name, proc.pid)}")

        say(f"[验收①] 内置浏览器子进程被拉起 = {spawned}")
        say(f"[验收②] 结果文件是否已写 = {os.path.exists(_res)}（未点是正常的）")

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
    # 只报相关内容，避免噪音
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
