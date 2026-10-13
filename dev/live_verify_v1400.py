# -*- coding: utf-8 -*-
"""真机验收脚本（v1.40.0）：启动根目录最新 exe，打开「工具 → 演员刮削」抓图。

v1.40.0 验收重点（三条 UI 反馈 + 一条出路）：
  ① 反馈 1：刮削页顶部必须是**三个独立模块** —— 「演员刮削」（总开关）、
     「演员资料统计」（统计条 + 刷新统计，本轮从数据源组框里抽出来）、
     「演员刮削数据源」。
  ② 反馈 2：底部「执行」区的日志框明显加大（≥240px，约 14 行），不再是 3 行小条。
  ③ 反馈 3：「刮削策略」里「代理」一行有**显式的「使用代理」开关**，
     关闭时输入框置灰、占位文案写明「直连」。
  ④ 反馈 4：数据源按钮区有「Cloudflare 验证…」入口，点开是那个三步走对话框。

实现复用 v1.39.5 已验证的 Windows 基础设施（PrintWindow 抓图 / PID 定位 /
侧边栏坐标 / 临时配置 / 日志体检），**不重复造轮子**。

⚠ 本脚本只做**只读**验收：打开页面 + 截图 + 点开验证对话框（**不点「保存并校验」**）。
   绝不点「全量刮削 / 增量刮削」这类会写盘的动作。

用法：python dev/live_verify_v1400.py
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
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1400.log"

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


def main():
    sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

    def say(m):
        print(m, flush=True)

    say("=" * 66)
    say("流明盒 v1.40.0 真机验收（演员刮削页改版）")
    say("=" * 66)

    if g is None:
        say("[中止] 无法加载 live_verify_v1395 基础设施")
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}  ({os.path.getsize(exe) / 1048576:.1f} MB)")

    env = dict(os.environ)
    env["LMC_CONFIG"] = g.make_temp_settings()      # 临时配置，不碰真实 settings.json
    say(f"[配置] LMC_CONFIG={env['LMC_CONFIG']}")

    _log_before = g.log_size()
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

        # ---------------- ① 演员刮削页整页 ----------------
        dn = (coords.get("dialog_nav") or {}).get("演员刮削")
        if not dn:
            say("[失败] 坐标表里没有「演员刮削」导航坐标")
            return 4
        say(f"[点击] 工具·演员刮削 @({dn[0]},{dn[1]})")
        g.click(dlg, dn[0], dn[1])
        time.sleep(3.5)
        out = os.path.join(SHOT_DIR, "50_live_scraper_full.png")
        pm = g.grab(app, dlg)
        say(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} {pm.save(out)}")

        # ---------------- ④ Cloudflare 验证对话框（只开不保存） ----------------
        cf = coords.get("scraper_cf_btn") or coords.get("cloudflare_btn")
        if cf:
            say(f"[点击] Cloudflare 验证… @({cf[0]},{cf[1]})")
            g.click(dlg, cf[0], cf[1])
            time.sleep(3.0)
            cfw = g.find_window_ex(exe_name, {proc.pid}, exclude={hwnd, dlg},
                                   title_sub="验证", timeout=6)
            target = cfw or dlg
            out2 = os.path.join(SHOT_DIR, "51_live_cloudflare_dialog.png")
            pm2 = g.grab(app, target)
            say(f"  [抓取] {pm2.width()}x{pm2.height()} -> "
                f"{os.path.basename(out2)} {pm2.save(out2)}")
        else:
            say("[跳过] 坐标表里没有 Cloudflare 按钮坐标（可选）")

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


if __name__ == "__main__":
    raise SystemExit(main())
