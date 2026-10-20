# -*- coding: utf-8 -*-
"""v1.42.2 真机探针：启动真 exe → 工具 → 演员刮削 → 截图设置对话框，
测量「IMDB 行下方留白」在真机上的真实构成（离屏实测只有 4~6px，用户截图显示 ~44px）。"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

sys.stdout = sys.stderr = open(
    r"C:/Users/zouzu/AppData/Local/Temp/live_gap_probe.log", "w", encoding="utf-8"
)

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
EXE = os.path.join(ROOT, "流明盒-v1.42.1-2610180084.exe")
EXE_NAME = os.path.basename(EXE).lower()
OUT = r"C:/Users/zouzu/AppData/Local/Temp/live_scraper_page.png"

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
    # ---- 离屏算坐标（与 ui_coords.py 同口径：假屏 2560x1392 + 对话框 1320x960）----
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
    cfg.config_path = lambda: os.path.join(TMP, "s.json")
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
    # 顺便量离屏下 src_list / 按钮行几何（对照用）
    for k, b in dlg.sub_btns.items():
        if "刮削" in k:
            b.click()
            break
    app.processEvents()
    sl = dlg.src_list
    print("[offscreen] src_list h =", sl.height(), "count =", sl.count(),
          "rows =", [sl.itemWidget(sl.item(i)).height() for i in range(sl.count())],
          flush=True)

    # ---- 真机 ----
    del os.environ["QT_QPA_PLATFORM"]
    from PySide6.QtWidgets import QApplication as _QA
    from PySide6.QtGui import QImage
    live = _QA.instance() or _QA(sys.argv)
    proc = subprocess.Popen([EXE], close_fds=True, cwd=ROOT)
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
    time.sleep(2.5)
    click(main_h, tp.x(), tp.y())
    # 等设置对话框出现（同进程的新顶层窗）
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
    time.sleep(1.5)
    # 多屏虚拟环境：窗口可能落在不渲染的屏上 → 先挪到主屏左上角再抓
    SWP_NOSIZE, SWP_SHOWWINDOW, HWND_TOP = 0x0001, 0x0040, 0
    u32.SetWindowPos(dlg_h, HWND_TOP, 100, 100, 0, 0,
                     SWP_NOSIZE | SWP_SHOWWINDOW)
    time.sleep(0.5)
    click(dlg_h, sp.x(), sp.y())
    time.sleep(2.5)

    def grab_composited(hwnd, tries=15):
        """磨砂玻璃模式下 grabWindow(hwnd) 只拿到透明底（全黑）——
        必须抓**桌面合成后**的画面：按窗口屏幕矩形 grabWindow(0, x, y, w, h)。"""
        for _ in range(tries):
            u32.SetForegroundWindow(hwnd)
            u32.ShowWindow(hwnd, 9)
            time.sleep(0.3)
            live.processEvents()
            r = wt.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            pm = live.primaryScreen().grabWindow(0, r.left, r.top, w, h)
            if pm.width() > 1 and pm.height() > 1:
                img = pm.toImage()
                bright = sum(1 for y in range(0, img.height(), 16)
                             for x in range(0, img.width(), 16)
                             if img.pixelColor(x, y).lightness() > 60)
                if bright > 50:
                    return pm
            time.sleep(0.5)
        return pm

    pm = grab_composited(dlg_h)
    if pm is not None and pm.width() > 1:
        pm.save(OUT)
        print("[saved]", OUT, pm.width(), "x", pm.height(), flush=True)
    else:
        print("[grab 失败]", flush=True)
    # 窗口矩形（供换算客户区坐标）
    r = wt.RECT()
    u32.GetWindowRect(dlg_h, ctypes.byref(r))
    print("[dialog rect]", r.left, r.top, r.right - r.left, r.bottom - r.top, flush=True)
    for pid in pids_of():
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    print("[清理完成] 残留:", pids_of(), flush=True)


main()
