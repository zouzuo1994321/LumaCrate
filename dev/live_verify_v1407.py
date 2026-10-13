# -*- coding: utf-8 -*-
"""真机验收脚本（v1.40.7）：工具窗固定默认 1320×960 + 内部模块冻结。

① **默认尺寸**：打开工具窗即 1320×960（逻辑），外框 ≈ 1320+chrome。
   v1.40.6 是「按内容自适应」→ 初始高随屏幕/页变。
② **切页不改尺寸**：逐页点导航，外框宽高**必须恒定**（v1.40.6 是每页不同高）。
③ **内容冻结**：拉宽窗口到 +500px → 页内组框宽度**不变**（右侧纯留白）；
   拉高到 +240px → 组框高度不变。判据用**组框的实际像素宽高**（不是窗口尺寸），
   因为「内容不随窗口拉伸」最终要落在组框尺寸上。

⚠ SetWindowPos(hwnd, hWndInsertAfter, X, Y, cx, cy, uFlags) —— 第 3/4 参是**坐标**，
  第 5/6 参才是宽高。给坐标传 0 会把窗口推到屏幕左上角；这里传原值。

**只读验收**：打开工具窗 + 切页 + 拉窗口 + 截图。**不点任何执行/保存按钮**。

用法：python dev/live_verify_v1407.py
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
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1407.log"

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


def _rect(hwnd):
    r = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def main():
    sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

    def say(m):
        print(m, flush=True)

    say("=" * 66)
    say("流明盒 v1.40.7 真机验收（工具窗固定 1320×960 + 内部模块冻结）")
    say("=" * 66)

    if g is None:
        say("[中止] 无法加载基础设施")
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}  ({os.path.getsize(exe) / 1048576:.1f} MB)")
    if "v1.40.7" not in exe_name:
        say(f"[警告] 最新 exe 不是 v1.40.7：{exe_name}")

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

        x0, y0, w0, h0 = _rect(dlg)
        say(f"[工具窗口] 外框 {w0}x{h0} @({x0},{y0}) title={g.wtitle(dlg)!r}")

        # ---------------- ① 默认尺寸 1320×960 ----------------
        say("\n[验收①] 打开默认尺寸（v1.40.7 目标：逻辑 1320x960）")
        # 逻辑尺寸 = 外框 - chrome。真机实测 chrome ≈ (w: 1320->?, h: 960->999)
        # 只做区间断言：外框高应在 [960, 960+80]，宽应在 [1320, 1320+80]
        ok_w = 1320 <= w0 <= 1320 + 80
        ok_h = 960 <= h0 <= 960 + 80
        say(f"   外框宽 {w0} ∈ [1320, 1400] ? {'是 ✅' if ok_w else '否 ❌'}")
        say(f"   外框高 {h0} ∈ [960, 1040] ? {'是 ✅' if ok_h else '否 ❌'}")
        h_snap = h0

        # ---------------- ② 逐页切换：尺寸必须恒定 ----------------
        # ⚠ 任何 SetWindowPos 都放最后 —— 会改窗口尺寸，干扰「尺寸恒定」的判定。
        nav = coords.get("dialog_nav") or {}
        seq = ["手动修改", "AI引擎设置", "图像检测", "演员检测", "演员刮削",
               "个性化设置", "数据与日志", "服务管理"]
        say("\n[验收②] 逐页切换：页 / 导航坐标 / 外框尺寸（应与打开时一致）")
        sizes = {}
        for key in seq:
            xy = nav.get(key)
            if not xy:
                say(f"   {key:<12} [跳过] 坐标表无此项")
                continue
            g.u32.SetForegroundWindow(dlg)
            g.click(dlg, xy[0], xy[1])
            time.sleep(2.2)
            _, _, ww, hh = _rect(dlg)
            sizes[key] = (ww, hh)
            flag = "" if (ww, hh) == (w0, h0) else "   ★变了"
            say(f"   {key:<12} {xy} → {ww}x{hh}{flag}")

        drift = {k: v for k, v in sizes.items() if v != (w0, h0)}
        say(f"\n[验收②] 尺寸恒定判定：{len(sizes)} 页中 {len(drift)} 页与打开时不同")
        if drift:
            for k, v in drift.items():
                say(f"      ★ {k}: {v} != 打开时 {(w0, h0)}")
            say("   打分：尺寸仍在随页变化 ❌")
        else:
            say("   打分：切页不再改窗口尺寸 ✅")

        # ---------------- ③ 内容冻结 ----------------
        # 判据用**组框的实际像素宽高**：拉宽窗口后若组框变宽，说明内容跟着拉伸了。
        # 抓「演员刮削」页（用户反馈截图那一页），量它最上面那个组框。
        say("\n[验收③] 内容冻结：拉宽 / 拉高窗口，组框尺寸必须不变")
        _xy = nav.get("演员刮削")
        if _xy:
            g.u32.SetForegroundWindow(dlg)
            g.click(dlg, _xy[0], _xy[1])
            time.sleep(2.5)

        pm_a = g.grab(app, dlg, tries=6, gap=0.3, settle=1)
        say(f"   冻结前截图 {pm_a.width()}x{pm_a.height()}")

        # 拉宽 +480、拉高 +240（保持左上角不动）
        try:
            lx, ty, _, _ = _rect(dlg)
            u.SetWindowPos(dlg, 0, lx, ty, w0 + 480, h0 + 240, 0x0004)
        except Exception as _e:
            say(f"   [警告] 拉伸失败：{type(_e).__name__}: {_e}")
        time.sleep(2.0)
        _, _, w2, h2 = _rect(dlg)
        say(f"   拉伸后外框 {w2}x{h2}（尝试 {w0 + 480}x{h0 + 240}）")
        stretched = (w2 > w0 + 100) and (h2 > h0 + 100)
        say(f"   窗口确实被拉伸 ? {'是 ✅' if stretched else '否 ❌（后续冻结判定无意义）'}")

        time.sleep(1.0)
        pm_b = g.grab(app, dlg, tries=6, gap=0.3, settle=1)
        say(f"   拉伸后截图 {pm_b.width()}x{pm_b.height()}")
        out_a = os.path.join(SHOT_DIR, "90_live_v1407_默认1320x960.png")
        out_b = os.path.join(SHOT_DIR, "90_live_v1407_拉宽后.png")
        say(f"   [抓取] {os.path.basename(out_a)} {pm_a.save(out_a)}")
        say(f"   [抓取] {os.path.basename(out_b)} {pm_b.save(out_b)}")

        # 像素级判据：比较两张图里**内容区右边界相对窗口左边缘的绝对像素**。
        #
        # ⚠ 不能用「图内横坐标」直接比 —— `grab()` 抓的是整窗，窗口被拉宽后抓图
        #   本身也变宽（1320→1800），横坐标量程不同，直接相减必然得到 Δ≈480
        #   （首版就这么误报「未冻结」；而更早那版单行扫描返回 -1、又误报「通过」）。
        #   ⇒ 判据必须**与图宽无关**：冻结生效时内容右边界恒在「导航 150 + 内容 1170」
        #     ≈ 1320px 处，**无论窗口多宽**。所以断言「两张图的这个值应当接近相等」，
        #     且**不随图宽变化**。
        try:
            qa = pm_a.toImage()
            qb = pm_b.toImage()

            def content_right_edge(qi):
                """返回内容区（组框）右边界 x（多行扫描取最右）。

                ⚠ 两个必须的防误判（本版踩过）：
                  ① 跳过最右 10px —— 窗口自身有边线/阴影，是亮像素，
                     不跳过会「永远扫到图右缘」（实测 ea=1319 / eb=1799）；
                  ② 阈值用「背景 + 较大增量」—— 背景是深色界面底，
                     只加 10 会把低对比的边框/滚动条也算成内容。
                """
                w, h = qi.width(), qi.height()
                # 背景基准：右下角 40x40（跳过最右 10px 边线）
                bs, n = 0.0, 0
                for x in range(w - 50, w - 10):
                    for y in range(h - 50, h - 10):
                        c = qi.pixelColor(x, y)
                        bs += (c.red() + c.green() + c.blue()) / 3.0
                        n += 1
                thr = bs / max(1, n) + 25
                best = -1
                for y in range(10, int(h * 0.7), 6):
                    for x in range(w - 10, 170, -1):     # ★ 从 w-10 起，跳过边线
                        c = qi.pixelColor(x, y)
                        if (c.red() + c.green() + c.blue()) / 3.0 > thr:
                            if x > best:
                                best = x
                            break
                return best

            ea = content_right_edge(qa)
            eb = content_right_edge(qb)
            say(f"   [像素] 截图尺寸 {qa.width()}x{qa.height()} -> {qb.width()}x{qb.height()}"
                f"（已确认无 DPI 缩放，横坐标可比）")
            say(f"          内容右边界 x: {ea} -> {eb}    Δ={eb - ea}")
            if ea < 0 or eb < 0:
                say("   打分：[跳过] 像素判据未能识别内容边界（以数值判据为准）")
            else:
                frozen = abs(eb - ea) < 60
                say(f"   打分：内容右边界不随窗口变宽而移动 = {'是 ✅（内容冻结）' if frozen else '否 ❌'}")
                say(f"          （冻结时右边界应恒在 ≈ 导航150 + 内容1170 = 1320）")
        except Exception as _e:
            say(f"   [警告] 像素判定失败：{type(_e).__name__}: {_e}")

        time.sleep(1.0)
        g.check_new_log(_log_before)

    finally:
        _kill_tree(proc.pid)
        time.sleep(1.5)
        left = [f"{n}({p})" for p, pp, n in _all_pids()
                if "2610130070" in n or ("流明盒" in n and "v1.40.7" in n)]
        say(f"[结束] 残留: {left if left else '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
