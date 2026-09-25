# -*- coding: utf-8 -*-
"""诊断：点「工具」之后，SettingsDialog 在 UIA 树里到底在哪一层？

上一轮 `Desktop(backend='uia').windows()` 只看到主窗一个 —— 可能是：
  a) 对话框被 UIA 挂成**主窗的子节点**（Qt 给了 parent），desktop 根下就看不到；
  b) 点击根本没生效（按钮名匹配错 / 没点中）；
  c) 建窗口太慢（工具窗要建 10 来个页面）。
这里三种情况一次查清。
"""
import ctypes
import ctypes.wintypes as wt
import glob
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_dbg_tools.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1310"
u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def wtitle(h):
    n = u32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def wpid(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def find_main(timeout=150):
    t0 = time.time()
    while time.time() - t0 < timeout:
        hit = []

        def cb(h, _l):
            if not u32.IsWindowVisible(h):
                return True
            if "Build" not in wtitle(h):
                return True
            r = wt.RECT()
            u32.GetClientRect(h, ctypes.byref(r))
            if (r.right - r.left) < 400:
                return True
            hit.append(h)
            return False

        u32.EnumWindows(EnumWindowsProc(cb), 0)
        if hit:
            return hit[0]
        time.sleep(0.5)
    return None


def main():
    from pywinauto import Desktop, Application
    exe = [p for p in glob.glob(os.path.join(ROOT, "流明盒-v*.exe"))
           if "2609250048" in p][0]
    print("exe:", exe, flush=True)
    proc = subprocess.Popen([exe], cwd=ROOT)
    try:
        h = find_main()
        print("main hwnd=%s title=%r pid=%s" % (h, wtitle(h), wpid(h)), flush=True)
        time.sleep(7)
        u32.SetForegroundWindow(h)
        u32.ShowWindow(h, 9)
        time.sleep(1)

        app = Application(backend="uia").connect(handle=h)
        win = app.window(handle=h)

        # 找「工具」按钮
        tgt = None
        for b in win.descendants(control_type="Button"):
            t = (b.window_text() or "").strip()
            if t == "工具":
                tgt = b
                print("btn 工具 rect=%s enabled=%s" % (b.rectangle(), b.is_enabled()),
                      flush=True)
                break
        if tgt is None:
            print("!! 没找到文字为『工具』的按钮，全部按钮：", flush=True)
            for b in win.descendants(control_type="Button"):
                print("   %r" % ((b.window_text() or "")[:30],), flush=True)
            return
        try:
            tgt.click_input()
            print("clicked", flush=True)
        except Exception as e:
            print("click_input 失败 %r" % e, flush=True)
            try:
                tgt.invoke()
                print("invoke ok", flush=True)
            except Exception as e2:
                print("invoke 失败 %r" % e2, flush=True)

        for wait in (3, 6, 10):
            time.sleep(wait if wait == 3 else wait - 3)
            print("---- 等待 %ss ----" % wait, flush=True)
            # 1) Win32 枚举所有可见窗口（不按 pid 过滤）
            seen = []

            def cb2(hh, _l):
                if u32.IsWindowVisible(hh) and wtitle(hh):
                    seen.append((hh, wtitle(hh), wpid(hh)))
                return True

            u32.EnumWindows(EnumWindowsProc(cb2), 0)
            for hh, t, p in seen:
                if p in (wpid(h), proc.pid):
                    print("   win32: hwnd=%s pid=%s %r" % (hh, p, t), flush=True)
            # 2) UIA desktop 根
            dk = Desktop(backend="uia")
            try:
                for w in dk.windows():
                    try:
                        print("   uia-desktop: pid=%s vis=%s %r" % (
                            w.process_id(), w.is_visible(), w.window_text()), flush=True)
                    except Exception as e:
                        print("   uia-desktop: (err %r)" % e, flush=True)
            except Exception as e:
                print("   Desktop.windows 失败 %r" % e, flush=True)
            # 3) 主窗子树里的 Window/Pane
            try:
                for w in win.descendants(control_type="Window"):
                    try:
                        print("   uia-child Window: %r rect=%s" % (
                            w.window_text(), w.rectangle()), flush=True)
                    except Exception:
                        pass
            except Exception as e:
                print("   descendants Window 失败 %r" % e, flush=True)
    finally:
        time.sleep(1)
        try:
            proc.terminate()
        except Exception:
            pass
        time.sleep(2)
        try:
            proc.kill()
        except Exception:
            pass
    print("done", flush=True)


if __name__ == "__main__":
    main()
