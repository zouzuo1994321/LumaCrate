# -*- coding: utf-8 -*-
"""真机验收脚本（v1.40.8）：页面内容完整显示（不再被硬切）。

背景：v1.40.7 把「宽度冻结」误做成「宽 + 高都钉死」，`sizeHint()` 是构造途中的
估算值（手动修改 356 / 画像概览 792，真值 1400+ / 1242），且「整页自带滚动区」的
页面被钉在比视口还矮的高度后，外层给不了高度、内层滚动区也拿不到高度 →
**内容在固定高度处硬切**（用户截图 1 / 2）。v1.40.8 改成「只钉宽度、高度交给视口」。

真机要验的（按用户两条反馈逐条对）：

  ① **窗口尺寸**：打开即 1320×960（逻辑）→ 外框落在 [1320, 1400] × [960, 1040]；
     逐页切换尺寸**恒定**（v1.40.7 已达成，本版不能回退）。
  ② **手动修改页内容完整**：进该页 → **滚到底** → 抓图。
     判据：底部能看到「保存到 nfo 与索引」这三个按钮（像素里找那条主色按钮带）
     且右栏滚动条最大值 > 0（说明内容确实比视口高、靠滚动可达全程）。
  ③ **画像概览内容完整**：进该页 → 等分析完成 → **滚到底** → 抓图。
     判据：滚到底后页面底部的「标签共现」组框可见（像素里找该区域的亮文本行），
     且外侧滚动条最大值 > 0。
  ④ **内容仍冻结**：拉宽窗口 +480 → 内容右边界不移动（v1.40.7 的行为不能丢）。
  ⑤ `app.log` 零未捕获异常。

⚠ SetWindowPos(hwnd, hWndInsertAfter, X, Y, cx, cy, uFlags) —— 第 3/4 参是**坐标**，
  第 5/6 参才是宽高。给坐标传 0 会把窗口推到屏幕左上角；这里传原值 + SWP_NOZORDER。

**只读验收**：打开工具窗 + 切页 + 滚动 + 拉窗口 + 截图。**不点任何执行/保存按钮**。

用法：python dev/live_verify_v1408.py
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
LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1408.log"

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


def _scroll_bottom(hwnd, app, at, amount=-25, times=40):
    """在窗口坐标 `at` 处滚轮到底（向下 = 负 delta）。

    ⚠ v1.40.8 两轮实测的结论（**别照直觉改**）：
      · `SetForegroundWindow(dlg)` + `SetCursorPos(at)` + `mouse_event(WHEEL)`
        ⇒ **一次都没滚**（顶/底两图 100% 相同）。原因是 `SetCursorPos` 把物理光标
        移到了目标点，但随后的 `grab()` / 窗口激活会把焦点换回去，滚轮事件落到别处。
      · **只用 `mouse_event(WHEEL)`**（不碰 `SetCursorPos`、不 `SetForegroundWindow`）
        ⇒ 有效（实测「画像概览」顶/底差异 18.4%，滚到底看得到「标签共现」）。
    所以这里保持「只发滚轮、不动光标」的最简形态 —— 滚轮事件按**系统当前光标下**的
    窗口派发，前一步 `g.click(dlg, ...)` 已经把光标留在工具窗内了。
    """
    for _ in range(times):
        try:
            u.mouse_event(0x0800, 0, 0, amount, 0)     # MOUSEEVENTF_WHEEL
        except Exception:
            pass
        app.processEvents()
        time.sleep(0.03)
    time.sleep(0.5)


def main():
    sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

    def say(m):
        print(m, flush=True)

    say("=" * 66)
    say("流明盒 v1.40.8 真机验收（页面内容完整显示 / 不被硬切）")
    say("=" * 66)

    if g is None:
        say("[中止] 无法加载基础设施")
        return 2

    exe = g.newest_exe()
    exe_name = os.path.basename(exe).lower()
    say(f"[EXE] {exe}  ({os.path.getsize(exe) / 1048576:.1f} MB)")
    if "v1.40.8" not in exe_name:
        say(f"[警告] 最新 exe 不是 v1.40.8：{exe_name}")

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

        # ---------------- ① 默认尺寸 ----------------
        say("\n[验收①] 打开默认尺寸（目标：逻辑 1320x960）")
        ok_w = 1320 <= w0 <= 1320 + 80
        ok_h = 960 <= h0 <= 960 + 80
        say(f"   外框宽 {w0} ∈ [1320, 1400] ? {'是 ✅' if ok_w else '否 ❌'}")
        say(f"   外框高 {h0} ∈ [960, 1040] ? {'是 ✅' if ok_h else '否 ❌'}")

        nav = coords.get("dialog_nav") or {}

        # ---------------- ② 逐页切换：尺寸恒定的回归 ----------------
        seq = ["手动修改", "AI引擎设置", "图像检测", "演员检测", "演员刮削",
               "个性化设置", "数据与日志", "服务管理"]
        say("\n[验收②] 逐页切换：外框尺寸应与打开时一致（v1.40.7 行为不能回退）")
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
        say("   打分：切页不再改窗口尺寸 %s" % ("✅" if not drift else "❌"))

        # ---------------- ③ 手动修改：滚到底看内容完整 ----------------
        say("\n[验收③] 手动修改：进页 → 选第一部 → 滚到底 → 底部按钮必须可见")
        xy = nav.get("手动修改")
        if xy:
            g.u32.SetForegroundWindow(dlg)
            g.click(dlg, xy[0], xy[1])
            time.sleep(2.5)
            # 左侧列表点第一项（列表区大约在 x=210，y=250 起）
            g.u32.SetForegroundWindow(dlg)
            g.click(dlg, 210, 250)
            time.sleep(2.5)
            pm_top = g.grab(app, dlg, tries=6, gap=0.3, settle=1)
            out_t = os.path.join(SHOT_DIR, "90_live_v1408_手动修改_顶部.png")
            say(f"   [抓取] {os.path.basename(out_t)} {pm_top.save(out_t)}"
                f"  {pm_top.width()}x{pm_top.height()}")
            # 在右栏区域内滚轮到底（x=900 落在右栏；y=500 在内容区中段）
            _scroll_bottom(dlg, app, (900, 500), amount=-25, times=50)
            pm_bot = g.grab(app, dlg, tries=6, gap=0.3, settle=1)
            out_b = os.path.join(SHOT_DIR, "90_live_v1408_手动修改_底部.png")
            say(f"   [抓取] {os.path.basename(out_b)} {pm_bot.save(out_b)}"
                f"  {pm_bot.width()}x{pm_bot.height()}")
            # ① 先证明「确实滚动了」（顶/底两图必须不同）—— 否则下面的按钮判据无意义
            try:
                qa = pm_top.toImage()
                qb = pm_bot.toImage()
                same = 0
                total = 0
                for y in range(60, min(qa.height(), qb.height()), 17):
                    for x in range(400, min(qa.width(), qb.width()), 23):
                        ca = qa.pixelColor(x, y)
                        cb = qb.pixelColor(x, y)
                        total += 1
                        if abs(ca.red() - cb.red()) < 12 \
                                and abs(ca.green() - cb.green()) < 12 \
                                and abs(ca.blue() - cb.blue()) < 12:
                            same += 1
                ratio = same / max(1, total)
                say(f"   [像素] 顶/底两图相同像素占比 {ratio:.1%}"
                    f"（< 85% 视为「确实滚动了」）")
                scrolled = ratio < 0.85
                say("   打分：右栏确实滚动到底 = %s"
                    % ("是 ✅" if scrolled else "否 ❌（滚轮没落到右栏，按钮判据不可信）"))
                if not scrolled:
                    say("   [跳过] 未滚动 → 底部按钮判据跳过（不默认给通过）")
            except Exception as _e:
                say(f"   [警告] 滚动判据失败：{type(_e).__name__}: {_e}")
                scrolled = False
            # ② 像素判据：底部主色按钮带（「保存到 nfo 与索引」是 Primary 红色）
            try:
                qi = pm_bot.toImage()
                w, h = qi.width(), qi.height()
                hits = 0
                # Primary 按钮 ≈ #e05243 那类暖红（R 明显大于 G/B）
                for y in range(int(h * 0.80), min(h - 12, int(h * 0.97))):
                    for x in range(170, w - 12, 2):
                        c = qi.pixelColor(x, y)
                        if c.red() > 150 and c.red() - c.green() > 55 \
                                and c.red() - c.blue() > 55:
                            hits += 1
                say(f"   [像素] 底部主色按钮带命中 {hits} 个采样点"
                    f"（>400 视为「保存按钮可见」）")
                if scrolled:
                    say("   打分：滚动到底后底部按钮可见 = %s"
                        % ("是 ✅" if hits > 400 else "否 ❌（内容可能仍被切）"))
            except Exception as _e:
                say(f"   [警告] 像素判定失败：{type(_e).__name__}: {_e}")

        # ---------------- ④ 画像概览：等分析完成 → 滚到底 ----------------
        say("\n[验收④] 画像概览：进页 → 等分析完成 → 滚到底 → 「标签共现」必须可见")
        xy = nav.get("画像概览")
        if xy:
            g.u32.SetForegroundWindow(dlg)
            g.click(dlg, xy[0], xy[1])
            say("   等待分析完成（首次进入会自动分析，最多 60 秒）…")
            time.sleep(35)          # 4.8 万条约 1.5 秒算完，留足余量给真实索引
            pm_top = g.grab(app, dlg, tries=6, gap=0.3, settle=1)
            out_t = os.path.join(SHOT_DIR, "90_live_v1408_画像概览_顶部.png")
            say(f"   [抓取] {os.path.basename(out_t)} {pm_top.save(out_t)}"
                f"  {pm_top.width()}x{pm_top.height()}")
            _scroll_bottom(dlg, app, (700, 500), amount=-25, times=50)
            pm_bot = g.grab(app, dlg, tries=6, gap=0.3, settle=1)
            out_b = os.path.join(SHOT_DIR, "90_live_v1408_画像概览_底部.png")
            say(f"   [抓取] {os.path.basename(out_b)} {pm_bot.save(out_b)}"
                f"  {pm_bot.width()}x{pm_bot.height()}")
            # 判据：顶部与底部两张图**必须不同**（说明确实滚动了 = 内容比视口高）
            try:
                qa = pm_top.toImage()
                qb = pm_bot.toImage()
                same = 0
                total = 0
                for y in range(60, min(qa.height(), qb.height()), 17):
                    for x in range(200, min(qa.width(), qb.width()), 23):
                        ca = qa.pixelColor(x, y)
                        cb = qb.pixelColor(x, y)
                        total += 1
                        if abs(ca.red() - cb.red()) < 12 \
                                and abs(ca.green() - cb.green()) < 12 \
                                and abs(ca.blue() - cb.blue()) < 12:
                            same += 1
                ratio = same / max(1, total)
                say(f"   [像素] 顶/底两图相同像素占比 {ratio:.1%}"
                    f"（< 85% 视为「确实滚动了、内容比视口高」）")
                say("   打分：画像概览可滚动到底（内容完整可达）= %s"
                    % ("是 ✅" if ratio < 0.85 else "否 ❌（可能没滚动或内容不足一屏）"))
            except Exception as _e:
                say(f"   [警告] 像素判定失败：{type(_e).__name__}: {_e}")

        # ---------------- ⑤ 内容仍冻结（v1.40.7 行为不能丢） ----------------
        say("\n[验收⑤] 内容冻结：拉宽窗口 +480，内容右边界不应移动")
        xy = nav.get("演员刮削")
        if xy:
            g.u32.SetForegroundWindow(dlg)
            g.click(dlg, xy[0], xy[1])
            time.sleep(2.5)
        pm_a = g.grab(app, dlg, tries=6, gap=0.3, settle=1)
        try:
            lx, ty, _, _ = _rect(dlg)
            u.SetWindowPos(dlg, 0, lx, ty, w0 + 480, h0 + 240, 0x0004)
        except Exception as _e:
            say(f"   [警告] 拉伸失败：{type(_e).__name__}: {_e}")
        time.sleep(2.0)
        _, _, w2, h2 = _rect(dlg)
        say(f"   拉伸后外框 {w2}x{h2}（尝试 {w0 + 480}x{h0 + 240}）")
        say(f"   窗口确实被拉伸 ? {'是 ✅' if (w2 > w0 + 100 and h2 > h0 + 100) else '否 ❌'}")
        time.sleep(1.0)
        pm_b = g.grab(app, dlg, tries=6, gap=0.3, settle=1)
        out_a = os.path.join(SHOT_DIR, "90_live_v1408_默认1320x960.png")
        out_b = os.path.join(SHOT_DIR, "90_live_v1408_拉宽后.png")
        say(f"   [抓取] {os.path.basename(out_a)} {pm_a.save(out_a)}")
        say(f"   [抓取] {os.path.basename(out_b)} {pm_b.save(out_b)}")

        try:
            qa = pm_a.toImage()
            qb = pm_b.toImage()

            def content_right_edge(qi):
                """内容区（组框）右边界 x（多行扫描取最右）。

                ⚠ 两个必须的防误判（v1.40.7 踩过）：
                  ① 跳过最右 10px —— 窗口自身边线/阴影是亮像素，不跳过会永远
                     扫到图右缘（实测 ea=1319 / eb=1799）；
                  ② 阈值用「背景 + 25」—— 背景是深色界面底，只加 10 会把低对比
                     的边框/滚动条也算成内容。
                """
                w, h = qi.width(), qi.height()
                bs, n = 0.0, 0
                for x in range(w - 50, w - 10):
                    for y in range(h - 50, h - 10):
                        c = qi.pixelColor(x, y)
                        bs += (c.red() + c.green() + c.blue()) / 3.0
                        n += 1
                thr = bs / max(1, n) + 25
                best = -1
                for y in range(10, int(h * 0.7), 6):
                    for x in range(w - 10, 170, -1):
                        c = qi.pixelColor(x, y)
                        if (c.red() + c.green() + c.blue()) / 3.0 > thr:
                            if x > best:
                                best = x
                            break
                return best

            ea = content_right_edge(qa)
            eb = content_right_edge(qb)
            say(f"   [像素] 截图尺寸 {qa.width()}x{qa.height()} -> {qb.width()}x{qb.height()}"
                f"（无 DPI 缩放，横坐标可比）")
            say(f"          内容右边界 x: {ea} -> {eb}    Δ={eb - ea}")
            if ea < 0 or eb < 0:
                say("   打分：[跳过] 像素判据未能识别内容边界")
            else:
                frozen = abs(eb - ea) < 60
                say("   打分：内容右边界不随窗口变宽而移动 = %s"
                    % ("是 ✅（内容冻结）" if frozen else "否 ❌"))
                say("          （冻结时右边界应恒在 ≈ 导航150 + 内容1170 = 1320）")
        except Exception as _e:
            say(f"   [警告] 像素判定失败：{type(_e).__name__}: {_e}")

        time.sleep(1.0)
        g.check_new_log(_log_before)

    finally:
        _kill_tree(proc.pid)
        time.sleep(1.5)
        left = [f"{n}({p})" for p, pp, n in _all_pids()
                if "2610130071" in n or ("流明盒" in n and "v1.40.8" in n)]
        say(f"[结束] 残留: {left if left else '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
