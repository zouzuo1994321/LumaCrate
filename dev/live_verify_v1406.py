# -*- coding: utf-8 -*-
"""真机验收脚本（v1.40.6）：工具窗高度「按页自适应 + 可拉伸」。

① 硬锁已取消：工具窗初始高**不再恒为 960**；最小高受 MIN_H 约束。
② 逐页切换：量真实外框高，断言**矮页比高页矮**（自适应生效）。
   真机 1080p：可用高 ~1040 → 上限 960。
   预期：手动修改 ≈ 560+chrome，AI引擎设置 ≈ 616+chrome，个性化设置/演员刮削 = 上限。
③ 可拖拽：SetWindowPos 改高 → 应**真的变高**（v1.40.4 是拉不动）。
   ⚠ 注意 SetWindowPos(hwnd, 0, cx, cy, w, h, flags) —— **第 3/4 个参数是坐标**，
     v1.40.6 首轮误把高度写进坐标位（窗口被推到 y=1200 → 出屏、外框高 0）。
     这里只动高度、坐标传原值。

**只读验收**：打开工具窗 + 切页 + 截图。**不点任何执行/保存按钮**。

用法：python dev/live_verify_v1406.py
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
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1406.log"

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


def _win_h(hwnd):
    r = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return r.bottom - r.top


def main():
    sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

    def say(m):
        print(m, flush=True)

    say("=" * 66)
    say("流明盒 v1.40.6 真机验收（工具窗高度按页自适应 + 可拉伸）")
    say("=" * 66)

    if g is None:
        say("[中止] 无法加载基础设施")
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}  ({os.path.getsize(exe) / 1048576:.1f} MB)")
    if "v1.40.6" not in exe_name:
        say(f"[警告] 最新 exe 不是 v1.40.6：{exe_name}")

    env = dict(os.environ)
    env["LMC_CONFIG"] = g.make_temp_settings()
    _log_before = g.log_size()

    proc = subprocess.Popen([exe], close_fds=True, env=env)
    say(f"[启动] pid={proc.pid}")

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

        h0 = _win_h(dlg)
        r = wt.RECT()
        u.GetWindowRect(dlg, ctypes.byref(r))
        say(f"[工具窗口] {r.right - r.left}x{h0} title={g.wtitle(dlg)!r}")

        # ---------------- ① 硬锁已取消 ----------------
        say(f"[验收①] 工具窗初始外框高 = {h0}（v1.40.4 恒为 960+chrome）")

        # ---------------- ② 逐页切换，量真实外框高 ----------------
        # ★★★ v1.40.6 最大的验收坑（首轮踩到，务必先做逐页、后做拖动）：
        #   **「手动拖过窗口」这件事本身会置位 `_user_resized_h`，从而永久关掉自适应**
        #   （这正是产品的设计要求 —— 尊重用户手动高度）。所以任何 `SetWindowPos`
        #   都**必须放在逐页测量之后**；否则测出来的每一页都是拖动后的同一个高度，
        #   会误判「自适应没生效」。首轮 ③ 在前 → 六页全是 999/846，就是被这个害的。
        #
        # 坐标方面：导航项 y 是**按内容撑开、与窗口高无关**的（离屏坐标表可复用），
        # 但一旦窗口高度变了、导航区若出现滚动就会整体平移 —— 为稳妥，只做
        # 「同高连续量」：每量一页前**不**动窗口，纯粹点导航 + 等自适应落定。
        nav = coords.get("dialog_nav") or {}
        # ★ v1.40.6：**每条 nav 的 y 与离屏坐标表一致**（实测真机文字行也落在
        #   62 / 100 / 140 / 179 / 251 / 329 / 479 / 551，同一张表可复用）。
        #   ⚠ 但真机「窗口高度会随页变化」，若抓图跨了下一轮点击，会拿到**下一页的残帧**
        #     （首轮「手动修改」的图里显示的是「演员刮削」高亮 —— 就是这个）。
        #   所以本轮**以数字高度为判据**，抓图只作旁证且点完立刻抓。
        seq = ["手动修改", "AI引擎设置", "图像检测", "演员检测",
               "演员刮削", "个性化设置"]
        say("\n[验收②] 逐页切换：页 / 导航坐标 / 真实外框高（未拖动过）")
        heights = {}
        for key in seq:
            xy = nav.get(key)
            if not xy:
                say(f"   {key:<12} [跳过] 坐标表无此项")
                continue
            g.u32.SetForegroundWindow(dlg)
            g.click(dlg, xy[0], xy[1])
            time.sleep(2.5)
            h = _win_h(dlg)
            heights[key] = h
            say(f"   {key:<12} {xy} → 外框高 {h}")

        # ---------------- 判定（自适应） ----------------
        say("\n[验收②] 自适应判定：")
        lo, hi = heights.get("手动修改"), heights.get("个性化设置")
        if lo and hi:
            say(f"   「手动修改」={lo}  「个性化设置」={hi}  → 矮页更矮 = {lo < hi}")
            say(f"   打分：{'自适应生效 ✅' if lo < hi - 40 else '未生效 ❌'}")
        else:
            say("   [跳过] 缺页坐标")
        # ★ 真机上限断言：所有页都不该超过 MAX_H(960) + 外框开销(实测 ~39) + 余量
        cap = 960 + 60
        over = {k: v for k, v in heights.items() if v > cap}
        say(f"   ★ 上限检查（MAX_H=960 + chrome≈39）：所有页 ≤ {cap} ? "
            f"{'是 ✅' if not over else f'否 ❌ {over}'}")
        # 逐页明细打分
        for k, v in heights.items():
            mark = "OK " if v <= cap else "★超"
            say(f"      {mark} {k:<12} {v}")

        # ---------------- 抓两张代表图（点完立刻抓，避免残帧） ----------------
        for key in ("手动修改", "演员刮削"):
            xy = nav.get(key)
            if not xy:
                continue
            g.u32.SetForegroundWindow(dlg)
            g.click(dlg, xy[0], xy[1])
            time.sleep(3.0)
            pm = g.grab(app, dlg, tries=6, gap=0.3, settle=1)
            out = os.path.join(SHOT_DIR, f"90_live_{key}_v1406.png")
            say(f"   [抓取] {key} {pm.width()}x{pm.height()} -> "
                f"{os.path.basename(out)} {pm.save(out)}")

        # ---------------- ③ 可拖拽（**放最后**：会关掉自适应） ----------------
        # ⚠ SetWindowPos 签名： (hwnd, hWndInsertAfter, X, Y, cx, cy, uFlags)
        #   第 3/4 参是窗口左上角坐标、第 5/6 参才是宽高 —— 首轮把高度写到坐标位，
        #   窗口被移到屏幕外 → 外框高量到 0。
        say("\n[验收③] 手动拖拽（做完这一步自适应会被关掉，故必须放最后）")
        try:
            RECT2 = wt.RECT()
            u.GetWindowRect(dlg, ctypes.byref(RECT2))
            _pad = (RECT2.right - RECT2.left) - g.COORDS_CLIENT_W
            u.SetWindowPos(dlg, 0, RECT2.left, RECT2.top,
                           g.COORDS_CLIENT_W + _pad, 1200, 0x0004)  # SWP_NOZORDER
        except Exception as _e:
            say(f"   [警告] 拉高失败：{type(_e).__name__}: {_e}")
        time.sleep(1.2)
        h_pull = _win_h(dlg)
        say(f"   拉高尝试 1200 → 实际外框高 {h_pull}"
            f"（{'可拉伸 ✅' if h_pull > h0 + 20 else '仍拉不动 ❌'}）")

        try:
            RECT3 = wt.RECT()
            u.GetWindowRect(dlg, ctypes.byref(RECT3))
            u.SetWindowPos(dlg, 0, RECT3.left, RECT3.top,
                           RECT3.right - RECT3.left, 700, 0x0004)
        except Exception as _e:
            say(f"   [警告] 压矮失败：{type(_e).__name__}: {_e}")
        time.sleep(1.2)
        h_squash = _win_h(dlg)
        say(f"   压矮尝试 700 → 实际外框高 {h_squash}"
            f"（{'可双向拉伸 ✅' if h_squash < h_pull - 20 else '压不下去 ❌'}）")

        time.sleep(1.5)
        g.check_new_log(_log_before)

    finally:
        _kill_tree(proc.pid)
        time.sleep(1.5)
        left = [f"{n}({p})" for p, pp, n in _all_pids()
                if "2610130069" in n or ("流明盒" in n and "v1.40.6" in n)]
        say(f"[结束] 残留: {left if left else '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
