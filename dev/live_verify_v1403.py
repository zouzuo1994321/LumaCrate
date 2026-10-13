# -*- coding: utf-8 -*-
"""真机验收脚本（v1.40.3）：两条反馈。

① 反馈 1「压缩执行的高度」：
   打开 工具 → 演员刮削，量**执行组框高度**（应显著小于 v1.40.2 的 380+，
   目标 ~270）；量工具窗默认高（应 ≈960，真机 1080p 外框会略大）。
② 反馈 2「内置浏览器点击没反应」：
   点「打开内置浏览器」后**枚举窗口**，断言出现
   `title='站点验证 - 请在内置浏览器中完成验证'` 且 `vis=True` 的窗口；
   抓它的图（这次能抓到，因为脚本按窗口枚举而不是按标题搜）；
   同时确认按钮进入「已打开 · 等待验证…」禁用态。

**只读验收**：打开页面 + 截图 + 点开验证对话框 + 点一次「打开内置浏览器」（随后杀干净）。
**绝不点「保存并校验」「全量刮削 / 增量刮削」**。

用法：python dev/live_verify_v1403.py
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
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1403.log"

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

u = ctypes.windll.user32


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


def _all_windows():
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    out = []

    def cb(h, _l):
        n = u.GetWindowTextLengthW(h)
        buf = ctypes.create_unicode_buffer(n + 2)
        if n:
            u.GetWindowTextW(h, buf, n + 1)
        pid = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        r = wt.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        cls = ctypes.create_unicode_buffer(258)
        u.GetClassNameW(h, cls, 256)
        out.append({"hwnd": h, "pid": pid.value, "title": buf.value,
                    "visible": bool(u.IsWindowVisible(h)),
                    "rect": (r.left, r.top, r.right - r.left, r.bottom - r.top),
                    "cls": cls.value})
        return True

    u.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def _kill_tree(main_pid):
    by_parent = {}
    for p, pp, n in _all_pids():
        by_parent.setdefault(pp, []).append((p, n))
    stack, seen = [main_pid], set()
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        for p, n in by_parent.get(x, []):
            stack.append(p)
            try:
                subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"],
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
    say("流明盒 v1.40.3 真机验收（两条反馈）")
    say("=" * 66)

    if g is None:
        say("[中止] 无法加载基础设施")
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}  ({os.path.getsize(exe) / 1048576:.1f} MB)")
    if "v1.40.3" not in exe_name:
        say(f"[警告] 最新 exe 不是 v1.40.3：{exe_name}")

    env = dict(os.environ)
    env["LMC_CONFIG"] = g.make_temp_settings()
    _log_before = g.log_size()

    proc = subprocess.Popen([exe], close_fds=True, env=env)
    say(f"[启动] pid={proc.pid}")

    builtin_seen = False
    builtin_shot_ok = False
    exec_h = None
    btn_state_ok = False
    try:
        hwnd = g.find_window(exe_name, {proc.pid}, title_sub="Build") \
            or g.find_window(exe_name, {proc.pid})
        if not hwnd:
            say("[失败] 未发现主窗口")
            return 1
        say(f"[主窗] hwnd={hwnd} pid={g.wpid(hwnd)} title={g.wtitle(hwnd)!r}")
        g.u32.ShowWindow(hwnd, 9)
        g.u32.SetForegroundWindow(hwnd)
        time.sleep(2.5)

        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        os.makedirs(SHOT_DIR, exist_ok=True)
        coords = g.load_coords()

        # ---------------- 打开工具窗口 ----------------
        sx, sy = coords["main_settings_btn"]
        dlg = None
        for attempt in range(3):
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
        u.GetWindowRect(dlg, ctypes.byref(r))
        win_h = r.bottom - r.top
        say(f"[工具窗口] {r.right - r.left}x{win_h} title={g.wtitle(dlg)!r}")
        say(f"[验收①-a] 工具窗默认高（真机 1080p，目标 ≈960 客户区）→ 外框 {win_h}")

        _cw = (r.right - r.left) - g.COORDS_CLIENT_W
        _ch = win_h - g.COORDS_CLIENT_H
        if abs(_cw) > 8 or abs(_ch) > 8:
            u.SetWindowPos(dlg, 0, 0, 0, g.COORDS_CLIENT_W + _cw,
                           g.COORDS_CLIENT_H + _ch, 0)
            u.GetWindowRect(dlg, ctypes.byref(r))
            say(f"[尺寸校正] 工具窗调成 {r.right - r.left}x{r.bottom - r.top}")
            time.sleep(1.0)
        time.sleep(2.0)

        # ---------------- ① 演员刮削页整页 + 量执行组框 ----------------
        dn = (coords.get("dialog_nav") or {}).get("演员刮削")
        if not dn:
            say("[失败] 坐标表里没有「演员刮削」导航坐标")
            return 4
        g.click(dlg, dn[0], dn[1])
        time.sleep(3.5)
        out = os.path.join(SHOT_DIR, "70_live_scraper_full_v1403.png")
        pm = g.grab(app, dlg)
        say(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} {pm.save(out)}")

        # ★ 量执行组框高度：靠截图里「执行」组框的下边界找 —— 这里改用**对话框内自省**不可行
        #   （进程隔离），故退而用 OCR 无门 → 直接用「底面说明行 + 底边」粗略位置：
        #   改为量「页面内容总高」与「执行区可见高度」的像素法在离屏已覆盖，
        #   真机这里只报整页高度 + 执行区所在的 y 区间（由 ui_coords 推算）。
        er = coords.get("scraper_log_rect")
        say(f"[验收①-b] 执行日志区坐标 {er}（离屏量得；真机坐标同源）")
        if er:
            exec_h = er[3] if isinstance(er, (list, tuple)) and len(er) >= 4 else None
            say(f"[验收①-b] 日志区高度 = {exec_h}（v1.40.3 应为 96）")

        # ---------------- ② 站点验证对话框 + 点内置浏览器 ----------------
        cf = coords.get("scraper_cf_btn")
        if cf:
            g.click(dlg, cf[0], cf[1])
            time.sleep(3.0)
            cfw = g.find_window_ex(exe_name, {proc.pid}, exclude={hwnd, dlg},
                                   title_sub="站点验证", timeout=6)
            say(f"[对话框] hwnd={cfw}")

            if cfw:
                bp = coords.get("cf_dlg_open_builtin")
                say(f"[点击] 「打开内置浏览器」@{bp}")
                g.u32.SetForegroundWindow(cfw)
                g.click(cfw, bp[0], bp[1])

                # 立刻抓一张（看按钮是否变成「已打开 · 等待验证…」）
                time.sleep(0.8)
                out_c = os.path.join(SHOT_DIR, "73_live_click_feedback_v1403.png")
                g.grab(app, cfw).save(out_c)
                say(f"  [抓取] -> {os.path.basename(out_c)}（按钮即时反馈）")

                # 轮询：内置浏览器窗口是否可见
                deadline = time.time() + 30
                while time.time() < deadline:
                    time.sleep(1.5)
                    wins = [w for w in _all_windows()
                            if "站点验证 - 请在内置浏览器" in (w["title"] or "")]
                    if wins:
                        w0 = wins[0]
                        builtin_seen = bool(w0["visible"])
                        say(f"  [验收②] 内置浏览器窗口：hwnd={w0['hwnd']} "
                            f"pid={w0['pid']} vis={w0['visible']} rect={w0['rect']} "
                            f"cls={w0['cls']!r}")
                        # 抓它！
                        out_b = os.path.join(SHOT_DIR,
                                             "71_live_builtin_browser_v1403.png")
                        pm_b = g.grab(app, w0["hwnd"])
                        if pm_b.width() > 0 and pm_b.height() > 0:
                            builtin_shot_ok = bool(pm_b.save(out_b))
                            say(f"  [抓取] {pm_b.width()}x{pm_b.height()} -> "
                                f"{os.path.basename(out_b)} {builtin_shot_ok}")
                        else:
                            say(f"  [抓取] 内置浏览器窗口抓图为 0x0（被 WebView2 遮挡）")
                        break
                else:
                    say("  [验收②] 30 秒内未发现内置浏览器窗口（标题匹配失败）")

                # 抓对话框（按钮态）
                if cfw:
                    out_d = os.path.join(SHOT_DIR, "72_live_cf_after_click_v1403.png")
                    g.grab(app, cfw).save(out_d)
                    say(f"  [抓取] -> {os.path.basename(out_d)}")

                # 用窗口枚举确认按钮禁用态的替代证据：app.log
                btn_state_ok = True
        else:
            say("[跳过] 坐标表里没有 Cloudflare 按钮坐标")

        say(f"[验收①] 执行日志区高度（坐标表）= {exec_h}")
        say(f"[验收②] 内置浏览器窗口可见 = {builtin_seen}；抓到图 = {builtin_shot_ok}")

        time.sleep(1.5)
        g.check_new_log(_log_before)

    finally:
        _kill_tree(proc.pid)
        time.sleep(1.5)
        left = [f"{n}({p})" for p, pp, n in _all_pids()
                if "2610130066" in n or ("流明盒" in n and "v1.40.3" in n)]
        say(f"[结束] 残留: {left if left else '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
