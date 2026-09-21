# -*- coding: utf-8 -*-
"""v1.25.0 真机验收补丁 2：处理「执行写入」的模态确认框。

第一轮真机验收（Build 2609210034）在「标签优化」页翻了车：
点了「执行写入」之后，弹出的**模态确认框**把主窗口和工具窗口都置成 disabled
（实测 `IsWindowEnabled` 两个窗口都是 False），于是：
  · 截图 38 与 37 一模一样（抓的是被压在下面的工具窗口自己的像素）；
  · 后面「演员刮削 / 重复检测 / 开始检测」三下点击全部落在禁用窗口上，白点；
  · 夹具 nfo 一个字节没变（无 .bak、无新增标签）。
而脚本本身**不会报错**、日志里每一步都写「抓取成功」—— 典型的「静默失效」。
所以这里补：找到这个模态框 → 截图留证 → 按回车确认（Qt 默认按钮就是「确定」）。
用回车而不是鼠标点：按钮在框内的坐标随文案长度变化，写死容易失手。
"""
import os

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"


def patch(rel, label, old, new, count=1):
    p = os.path.join(ROOT, rel)
    with open(p, encoding="utf-8", newline="") as f:
        s = f.read()
    n = s.count(old)
    if n != count:
        print(f"[失败] {label}: 锚点命中 {n} 次（期望 {count}）")
        print("----- 锚点 -----")
        print(old[:400])
        raise SystemExit(1)
    s = s.replace(old, new, count)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print(f"[OK] {label}")


# 1) 两个工具函数：找模态框 + 按回车确认
patch(
    r"dev\live_verify.py",
    "live_verify：新增 find_modal / press_ok",
    "def scan_sidebar(path):",
    '''VK_RETURN, WM_KEYDOWN, WM_KEYUP = 0x0D, 0x0100, 0x0101


def find_modal(exe_name, extra, exclude=(), timeout=8):
    """找模态确认框：本进程里「除主窗 / 工具窗外」的可见顶层窗口。

    门槛比 find_window_ex 低 —— QMessageBox 常见尺寸只有 ~420x180，
    用 w>300 / h>200 会漏掉它，于是「找不到确认框」被误当成「没有确认框」。
    """
    hits, pids = [], [set(extra)]

    def cb(h, _):
        if h in exclude:
            return True
        if u32.IsWindowVisible(h) and wpid(h) in pids[0]:
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            w, ht = r.right - r.left, r.bottom - r.top
            if w > 150 and ht > 80:
                hits.append((w * ht, h))
        return True

    t0 = time.time()
    while time.time() - t0 < timeout:
        pids[0] = pids_of_exe(exe_name) | set(extra)
        hits.clear()
        u32.EnumWindows(EnumWindowsProc(cb), 0)
        if hits:
            hits.sort(reverse=True)
            return hits[0][1]
        time.sleep(0.4)
    return None


def press_ok(hwnd, tries=4):
    """给确认框按一次回车（Qt 的默认按钮 = 「确定」）；返回是否真的关掉了。"""
    u32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    for _ in range(tries):
        u32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 0)
        time.sleep(0.12)
        u32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, 0)
        time.sleep(0.8)
        if not u32.IsWindow(hwnd):
            return True
    return not bool(u32.IsWindow(hwnd))


def scan_sidebar(path):''',
)

# 2) 点完「执行写入」先把确认框点掉，再等写入完成
patch(
    r"dev\live_verify.py",
    "live_verify：执行写入前先确认模态框",
    '''                    rb = coords.get("tagopt_run_btn")
                    if rb:
                        print(f"[点击] 执行写入 @({rb[0]},{rb[1]})", flush=True)
                        click(dlg, rb[0], rb[1])
                        time.sleep(7.0)''',
    '''                    rb = coords.get("tagopt_run_btn")
                    if rb:
                        print(f"[点击] 执行写入 @({rb[0]},{rb[1]})", flush=True)
                        click(dlg, rb[0], rb[1])
                        time.sleep(1.5)
                        # 「执行写入」是个破坏性动作，代码里先弹一次确认框（模态）。
                        # 不把它点掉的话：主窗与工具窗都被置 disabled，后续所有点击
                        # 全部失效，而脚本日志照样一路写「抓取成功」（踩过）。
                        mb = find_modal(exe_name, {proc.pid},
                                        exclude={hwnd, dlg}, timeout=8)
                        if mb:
                            rmb = wt.RECT()
                            u32.GetWindowRect(mb, ctypes.byref(rmb))
                            print(f"[确认框] hwnd={mb} "
                                  f"{rmb.right - rmb.left}x{rmb.bottom - rmb.top} "
                                  f"title={wtitle(mb)!r}", flush=True)
                            out = os.path.join(
                                SHOT_DIR, "38a_live_tools_tagopt_confirm.png")
                            pm = grab(app, mb, tries=6, settle=3)
                            print(f"  [抓取] {pm.width()}x{pm.height()} -> "
                                  f"{os.path.basename(out)} {pm.save(out)}", flush=True)
                            print(f"[确认框] 已确认={press_ok(mb)}", flush=True)
                        else:
                            print("[警告] 没等到确认框；后续点击可能全部失效", flush=True)
                        time.sleep(7.0)''',
)

print("\n补丁 2 完成。")
