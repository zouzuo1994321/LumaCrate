# -*- coding: utf-8 -*-
"""v1.42.2 真机探针 2：用「经典暗色」配置（不透明、可抓图）启动真 exe，
直接验证 exe 里数据源列表是 3 行（140px）还是 4 槽（184px）。"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import shutil
import subprocess
import sys
import time

sys.stdout = sys.stderr = open(
    r"C:/Users/zouzu/AppData/Local/Temp/live_exe_probe.log", "w", encoding="utf-8"
)

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
EXE = os.path.join(ROOT, "流明盒-v1.42.1-2610180084.exe")
EXE_NAME = os.path.basename(EXE).lower()
OUT = r"C:/Users/zouzu/AppData/Local/Temp/live_exe_scraper.png"

# 用户真实配置 + 经典暗色（避开磨砂黑屏；布局与主题无关）
CFG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_user_cfg.json"
shutil.copyfile(os.path.join(ROOT, "settings.json"), CFG)
_d = json.load(open(CFG, encoding="utf-8"))
_d["appearance"]["mode"] = "经典暗色"
json.dump(_d, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.environ["LMC_CONFIG"] = CFG
os.environ["LMC_NO_SYSMON"] = "1"

u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202


def pids_of():
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=20).stdout or b""
    res = set()
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == EXE_NAME and parts[1].isdigit():
            res.add(int(parts[1]))
    return res


def wpid(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def wtitle(h):
    n = u32.GetWindowTextLengthW(h)
    if n <= 0:
        return ""
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def enum_windows():
    rows = []

    def cb(h, _):
        if u32.IsWindowVisible(h):
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            rows.append((h, wpid(h), wtitle(h),
                         r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return rows


def click(hwnd, x, y):
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    for msg, wp in ((WM_MOUSEMOVE, 0), (WM_LBUTTONDOWN, 1), (WM_LBUTTONUP, 0)):
        u32.PostMessageW(hwnd, msg, wp, lp)
        time.sleep(0.12)


def main():
    # ---- 离屏算坐标 ----
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from PySide6.QtWidgets import QApplication, QPushButton
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtCore import Qt, QPoint, QRect

    app = QApplication(sys.argv)
    for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
        if os.path.exists(_f):
            QFontDatabase.addApplicationFont(_f)
    import tempfile
    import database as db
    import config as cfg
    TMP = tempfile.mkdtemp(prefix="lmc_coords_")
    db.db_path = lambda: os.path.join(TMP, "x.db")
    cfg.config_path = lambda: CFG
    cfg._SETTINGS = None
    db.init_db()
    try:
        import backdrop
        backdrop.auto_apply = lambda w, *a, **k: None
    except Exception:
        pass
    from main_window import MainWindow
    from ui_settings import SettingsDialog

    class _FakeScr:
        def availableGeometry(self):
            return QRect(0, 0, 2560, 1392)

        def geometry(self):
            return QRect(0, 0, 2560, 1440)

    SettingsDialog.screen = lambda self: _FakeScr()
    win = MainWindow()
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    win.resize(1920, 1080)
    win.show()
    app.processEvents()
    tool_btn = None
    for b in win.findChildren(QPushButton):
        if b.text() in ("工具", "设置"):
            tool_btn = b
            break
    tp = tool_btn.mapTo(win, QPoint(tool_btn.width() // 2, tool_btn.height() // 2))
    print("[coords] 工具按钮 =", tp.x(), tp.y(), flush=True)

    dlg = SettingsDialog(win)
    dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
    dlg.resize(1320, 960)
    dlg.show()
    app.processEvents()
    scraper_btn = None
    for k, b in dlg.sub_btns.items():
        if "刮削" in k:
            scraper_btn = b
            break
    sp = scraper_btn.mapTo(dlg, QPoint(scraper_btn.width() // 2, scraper_btn.height() // 2))
    print("[coords] 演员刮削导航 =", sp.x(), sp.y(), flush=True)

    # ---- 真机 ----
    del os.environ["QT_QPA_PLATFORM"]
    from PySide6.QtWidgets import QApplication as _QA
    live = _QA.instance() or _QA(sys.argv)
    proc = subprocess.Popen([EXE], close_fds=True, cwd=ROOT,
                            env=dict(os.environ))
    print("[Popen]", proc.pid, flush=True)
    main_h = None
    t0 = time.time()
    while time.time() - t0 < 60:
        for h, pid, title, x, y, w, hh in enum_windows():
            if pid in pids_of() and "Build" in title and w > 400 and hh > 300:
                main_h = h
                break
        if main_h:
            break
        time.sleep(1)
    print("[main window]", main_h, wtitle(main_h) if main_h else None, flush=True)
    if not main_h:
        for pid in pids_of():
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    time.sleep(3)
    # 主窗也抓一张（确认不透明、可抓）
    try:
        pm_m = live.primaryScreen().grabWindow(main_h)
        pm_m.save(r"C:/Users/zouzu/AppData/Local/Temp/live_exe_main.png")
        print("[main grab]", pm_m.width(), "x", pm_m.height(), flush=True)
    except Exception as e:
        print("[main grab err]", e, flush=True)
    click(main_h, tp.x(), tp.y())
    dlg_h = None
    t0 = time.time()
    while time.time() - t0 < 20:
        for h, pid, title, x, y, w, hh in enum_windows():
            if pid in pids_of() and h != main_h and w > 400 and hh > 300:
                dlg_h = h
                break
        if dlg_h:
            break
        time.sleep(0.8)
    print("[dialog window]", dlg_h, wtitle(dlg_h) if dlg_h else None, flush=True)
    if not dlg_h:
        for pid in pids_of():
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    time.sleep(2)
    click(dlg_h, sp.x(), sp.y())
    time.sleep(2.5)
    # 经典暗色 → grabWindow(hwnd) 直接拿真实内容
    pm = live.primaryScreen().grabWindow(dlg_h)
    if pm.width() > 1 and pm.height() > 1:
        pm.save(OUT)
        print("[saved]", OUT, pm.width(), "x", pm.height(), flush=True)
    r = wt.RECT()
    u32.GetWindowRect(dlg_h, ctypes.byref(r))
    print("[dialog rect]", r.left, r.top, r.right - r.left, r.bottom - r.top, flush=True)
    for pid in pids_of():
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    print("[清理完成] 残留:", pids_of(), flush=True)


main()
