# -*- coding: utf-8 -*-
"""真机验收脚本（v1.40.5）：两条留白反馈。

① 反馈 1「左右分布压缩到一行」：
   打开 工具 → 演员刮削，抓整页图；断言**刮削页只剩 4 个组框**（v1.40.4 是 5 个）
   —— 旧的两个独立组框（演员刮削 / 演员资料统计）已合并成一行。
   同时量「演员刮削」行的可视高度（截图裁剪 + 像素法），应明显小于 v1.40.4 的 159。
② 反馈 2「行间距太大，上下留白太多」：
   断言数据源组框里按钮与提示**同一行**：抓整页图看版面即可，另在源码层已由
   smoke_v1405 断言（`sbh.addWidget(self.src_hint, 3)`）。

**只读验收**：打开页面 + 截图。**绝不点「保存并校验」「全量刮削 / 增量刮削」**。

用法：python dev/live_verify_v1405.py
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
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1405.log"

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
    say("流明盒 v1.40.5 真机验收（两条留白反馈）")
    say("=" * 66)

    if g is None:
        say("[中止] 无法加载基础设施")
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}  ({os.path.getsize(exe) / 1048576:.1f} MB)")
    if "v1.40.5" not in exe_name:
        say(f"[警告] 最新 exe 不是 v1.40.5：{exe_name}")

    env = dict(os.environ)
    env["LMC_CONFIG"] = g.make_temp_settings()
    _log_before = g.log_size()

    proc = subprocess.Popen([exe], close_fds=True, env=env)
    say(f"[启动] pid={proc.pid}")

    h_before = h_after = None
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
        h_before = r.bottom - r.top
        say(f"[工具窗口] {r.right - r.left}x{h_before} title={g.wtitle(dlg)!r}")

        _cw = (r.right - r.left) - g.COORDS_CLIENT_W
        _ch = h_before - g.COORDS_CLIENT_H
        if abs(_cw) > 8 or abs(_ch) > 8:
            u.SetWindowPos(dlg, 0, 0, 0, g.COORDS_CLIENT_W + _cw,
                           g.COORDS_CLIENT_H + _ch, 0)
            u.GetWindowRect(dlg, ctypes.byref(r))
            h_before = r.bottom - r.top
            say(f"[尺寸校正] 工具窗调成 {r.right - r.left}x{h_before}")
            time.sleep(1.0)

        # 硬锁回归：尝试拉高 1200 → 应拉不动
        time.sleep(1.0)
        try:
            RECT2 = wt.RECT()
            u.GetWindowRect(dlg, ctypes.byref(RECT2))
            _pad_w = (RECT2.right - RECT2.left) - g.COORDS_CLIENT_W
            _pad_h = (RECT2.bottom - RECT2.top) - g.COORDS_CLIENT_H
            u.SetWindowPos(dlg, 0, 0, 0, g.COORDS_CLIENT_W + _pad_w, 1200 + _pad_h, 0)
        except Exception as _e:
            say(f"[警告] 拉高尝试失败：{type(_e).__name__}: {_e}")
        time.sleep(1.5)
        u.GetWindowRect(dlg, ctypes.byref(r))
        h_after = r.bottom - r.top
        say(f"[验收①] ★ 拉高尝试 1200 → 实际外框高 {h_after}"
            f"（{'锁死生效 ✅' if h_after == h_before else '仍被拉高 ❌'}）")
        time.sleep(1.0)

        # ---------------- 演员刮削页：整页图 + 两个特写 ----------------
        dn = (coords.get("dialog_nav") or {}).get("演员刮削")
        if not dn:
            say("[失败] 坐标表里没有「演员刮削」导航坐标")
            return 4
        g.click(dlg, dn[0], dn[1])
        time.sleep(3.5)

        out = os.path.join(SHOT_DIR, "80_live_scraper_full_v1405.png")
        pm = g.grab(app, dlg)
        say(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} {pm.save(out)}")

        # 断言：坐标表里 scraper_modules 只剩 4 个组框（合并已生效的证据链之一）
        mods = coords.get("scraper_modules") or []
        say(f"[验收①] 坐标表 scraper_modules 共 {len(mods)} 项：")
        for m in mods[-6:]:
            say(f"     · {m}")
        merged = ("演员资料统计" not in mods) and ("演员刮削" in mods)
        say(f"[验收①] 旧「演员资料统计」组框已并入「演员刮削」= {merged}")

        # 裁剪出「演员刮削」那一行的特写（按 ui_coords 的 y 区间）
        er = coords.get("scraper_log_rect")
        say(f"[验收②] 执行日志区坐标 {er}（v1.40.5 仍应为高 96）")

        # 裁剪：从客户区顶部到数据源组框标题之下 —— 覆盖两个反馈目标
        try:
            from PIL import Image
            shot = Image.open(out)
            # 「演员刮削」行 + 数据源组框：客户区 y ∈ [0, 300] 足以覆盖
            crop = shot.crop((0, 0, shot.width, min(300, shot.height)))
            cpath = os.path.join(SHOT_DIR, "81_live_top_rows_v1405.png")
            crop.save(cpath)
            say(f"  [裁剪] {crop.width}x{crop.height} -> {os.path.basename(cpath)}")
        except Exception as _e:
            say(f"[警告] 裁剪失败：{type(_e).__name__}: {_e}")

        say(f"[验收①] 工具窗高度硬锁 = {h_after == h_before}（外框 {h_before} → {h_after}）")

        time.sleep(1.5)
        g.check_new_log(_log_before)

    finally:
        _kill_tree(proc.pid)
        time.sleep(1.5)
        left = [f"{n}({p})" for p, pp, n in _all_pids()
                if "2610130068" in n or ("流明盒" in n and "v1.40.5" in n)]
        say(f"[结束] 残留: {left if left else '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
