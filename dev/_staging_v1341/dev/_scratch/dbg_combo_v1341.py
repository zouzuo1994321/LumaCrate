# -*- coding: utf-8 -*-
"""诊断：自动填充面板里的「统计范围」下拉框，到底怎么才能用自动化切到「我的收藏」。

已排除：
  * `ComboBox.select("我的收藏（只统计收藏的影片）")` → IndexError（Qt 不暴露下拉项）；
  * `set_focus()` + SendInput(VK_DOWN) → 没生效；
  * `click_input()` + VK_DOWN + Enter → 没生效。
本脚本改用**真实鼠标**（SendInput 绝对坐标）点开下拉，再把弹出层里的项全量 dump 出来。
"""
import ctypes
import ctypes.wintypes as wt
import glob
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_dbg_combo.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1310"
u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
SM_CXSCREEN, SM_CYSCREEN = 0, 1


class _M(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class _MU(ctypes.Union):
    _fields_ = [("mi", _M)]


class _MI(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _MU)]


def mouse_click(x, y, settle=0.8):
    sw, sh = u32.GetSystemMetrics(SM_CXSCREEN), u32.GetSystemMetrics(SM_CYSCREEN)
    ax, ay = int(x * 65535 / sw), int(y * 65535 / sh)
    for flags in (MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                  MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE,
                  MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE):
        inp = _MI(INPUT_MOUSE, _MU(mi=_M(ax, ay, 0, flags, 0, None)))
        u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_MI))
        time.sleep(0.08)
    time.sleep(settle)


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
            if not u32.IsWindowVisible(h) or "Build" not in wtitle(h):
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


def child_window(parent, keyword):
    try:
        for w in parent.descendants(control_type="Window"):
            try:
                if keyword in (w.window_text() or ""):
                    return w
            except Exception:
                continue
    except Exception:
        pass
    return None


def txt(el):
    try:
        return el.window_text() or ""
    except Exception:
        return ""


def find_btn(win, name):
    ex = fz = None
    try:
        for b in win.descendants(control_type="Button"):
            t = txt(b).strip()
            if t == name:
                ex = b
                break
            if name in t and fz is None:
                fz = b
    except Exception:
        pass
    return ex or fz


def main():
    from pywinauto import Desktop, Application
    exe = [p for p in glob.glob(os.path.join(ROOT, "流明盒-v*.exe")) if "2609250048" in p][0]
    print("exe:", exe, flush=True)
    proc = subprocess.Popen([exe], cwd=ROOT)
    try:
        h = find_main()
        print("main hwnd=%s pid=%s" % (h, wpid(h)), flush=True)
        time.sleep(7)
        u32.SetForegroundWindow(h)
        u32.ShowWindow(h, 9)
        time.sleep(1)
        app = Application(backend="uia").connect(handle=h)
        win = app.window(handle=h)

        click(find_btn(win, "工具"), "工具")
        tools = None
        for _ in range(6):
            tools = child_window(win, "工具")
            if tools:
                break
            time.sleep(2)
        print("tools:", txt(tools), flush=True)
        click(find_btn(tools, "智能推荐"), "工具→智能推荐")
        time.sleep(2.5)
        click(find_btn(tools, "打开向量编辑…"), "打开向量编辑…")
        time.sleep(2.5)
        vec = None
        for _ in range(6):
            vec = child_window(tools, "向量编辑") or child_window(win, "向量编辑")
            if vec:
                break
            time.sleep(2)
        print("vec:", txt(vec), flush=True)
        click(find_btn(vec, "从画像自动填充…"), "从画像自动填充")
        time.sleep(3)
        dlg = None
        for _ in range(6):
            dlg = child_window(vec, "从画像自动填充") or child_window(win, "从画像自动填充")
            if dlg:
                break
            time.sleep(2)
        print("dlg:", txt(dlg), flush=True)
        if dlg is None:
            return

        cbs = list(dlg.descendants(control_type="ComboBox"))
        print("ComboBox 数=%d" % len(cbs), flush=True)
        for c in cbs:
            r = c.rectangle()
            print("  combo name=%r rect=L%d T%d R%d B%d" % (txt(c), r.left, r.top, r.right, r.bottom), flush=True)
        cb = cbs[0] if cbs else None
        if cb is None:
            return
        r = cb.rectangle()

        def tip_dump(tag):
            print("---- %s ----" % tag, flush=True)
            try:
                for e in dlg.descendants(control_type="Text"):
                    t = txt(e)
                    if t and ("统计" in t or "收藏" in t):
                        print("   Text: %r" % t[:110], flush=True)
            except Exception as e:
                print("   (dump err %r)" % e, flush=True)

        tip_dump("点击前")
        cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
        print("真实鼠标点击 combo 中心 (%d,%d)" % (cx, cy), flush=True)
        mouse_click(cx, cy)
        time.sleep(1.2)

        dk = Desktop(backend="uia")
        print("---- 弹出后枚举 ListItem ----", flush=True)
        try:
            for w in dk.windows():
                try:
                    if w.process_id() != wpid(h):
                        continue
                    for li in w.descendants(control_type="ListItem"):
                        lr = li.rectangle()
                        print("   [%s] %r  L%d T%d R%d B%d" % (
                            txt(w), txt(li)[:40], lr.left, lr.top, lr.right, lr.bottom),
                            flush=True)
                except Exception:
                    continue
        except Exception as e:
            print("   (enum err %r)" % e, flush=True)

        # 直接在 dlg 子树里找 ListItem（弹出层可能是 dlg 的子节点）
        try:
            for li in dlg.descendants(control_type="ListItem"):
                lr = li.rectangle()
                print("   dlg-child ListItem %r L%d T%d R%d B%d" % (
                    txt(li)[:40], lr.left, lr.top, lr.right, lr.bottom), flush=True)
        except Exception as e:
            print("   (dlg ListItem err %r)" % e, flush=True)

        # 尝试点第二项（我的收藏）
        target = None
        for w in dk.windows():
            try:
                if w.process_id() != wpid(h):
                    continue
                for li in w.descendants(control_type="ListItem"):
                    if "我的收藏" in txt(li):
                        target = li
                        break
            except Exception:
                continue
            if target:
                break
        if target is None:
            try:
                for li in dlg.descendants(control_type="ListItem"):
                    if "我的收藏" in txt(li):
                        target = li
                        break
            except Exception:
                pass
        print("target item: %r" % (txt(target)[:40] if target is not None else None), flush=True)
        if target is not None:
            tr = target.rectangle()
            mouse_click((tr.left + tr.right) // 2, (tr.top + tr.bottom) // 2, settle=1.5)
            time.sleep(2)
        tip_dump("点击后")
        print("dlg rect = %s" % (dlg.rectangle(),), flush=True)
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


def click(el, tag):
    if el is None:
        print("!! 找不到 %s" % tag, flush=True)
        return False
    try:
        el.click_input()
        print("clicked %s" % tag, flush=True)
        return True
    except Exception as e:
        print("click %s 失败 %r" % (tag, e), flush=True)
        return False


if __name__ == "__main__":
    main()
