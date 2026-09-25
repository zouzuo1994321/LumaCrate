# -*- coding: utf-8 -*-
"""v1.31.0 真机验收：启动根目录最新 exe，对着**真实索引的副本**逐页截图。

与 v1.30.0 的差别：
  - 删掉 A-Z 索引条的点击段（该功能已撤销），改成核对「右侧没有那条竖条」。
  - 新增「工具 → 演员检测」：真点「开始检测」，看打包后的 exe 能否在真实
    5909 位演员上跑完并给出「建议合并 / 存疑」两棵树。
  - 工具窗导航坐标**从 lmc_ui_coords.json 的 dialog_nav 整段读取**
    （由 dev/_scratch/ui_coords_v1310.py 从布局推导，插页不会失配）。

用法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/live_verify_v1310.py', run_name='__main__')"
"""
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1310.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots_v1310_live")
os.makedirs(SHOT_DIR, exist_ok=True)
COORDS = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"

u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
WM_CLOSE, WM_KEYDOWN, WM_KEYUP = 0x0010, 0x0100, 0x0101
VK_DOWN = 0x28

# 主窗侧栏条目 -> 客户区坐标（1920x1080、默认 DPI）。v1.31.0 没动主窗侧栏，
# 沿用 v1.30.0 的实测值；若哪天改了主窗导航，重跑 dev/_probe_sidebar.py。
SIDEBAR = {"首页": (93, 87), "演员库": (93, 391), "导演库": (93, 428)}

EXE_GLOBS = ("流明盒-v*.exe", "本地影视中心-v*.exe")


def newest_exe():
    cand = []
    for pat in EXE_GLOBS:
        cand += glob.glob(os.path.join(ROOT, pat))
    cand = sorted(set(cand), key=os.path.getmtime)
    if not cand:
        raise SystemExit("根目录未找到 exe")
    return cand[-1]


def pids_of_exe(exe_name):
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=15).stdout or b""
    res = set()
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == exe_name and parts[1].isdigit():
            res.add(int(parts[1]))
    return res


def wpid(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def wtitle(h):
    n = u32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def client_size(h):
    r = wt.RECT()
    u32.GetClientRect(h, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


def find_window(exe_name, extra=(), timeout=60, title_sub="Build", minw=400, minh=300):
    """按「本次启动的 pid 集合」+ 标题子串 + 最小尺寸定位窗口，绝不按名字批杀。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        live = pids_of_exe(exe_name) | set(extra)
        hit = []

        def cb(h, _l):
            if not u32.IsWindowVisible(h):
                return True
            if wpid(h) not in live:
                return True
            t = wtitle(h)
            if title_sub and title_sub not in t:
                return True
            cw, ch = client_size(h)
            if cw < minw or ch < minh:
                return True
            hit.append(h)
            return False

        u32.EnumWindows(EnumWindowsProc(cb), 0)
        if hit:
            return hit[0]
        time.sleep(0.6)
    return None


def click(hwnd, x, y):
    lp = (y << 16) | (x & 0xFFFF)
    u32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
    u32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lp)
    u32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)


def grab(app, hwnd, tries=8, settle=10):
    from PySide6.QtGui import QGuiApplication
    for _ in range(tries):
        app.processEvents()
        time.sleep(0.05)
    scr = QGuiApplication.primaryScreen()
    if scr is None:
        return None
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    pm = scr.grabWindow(0, r.left, r.top, r.right - r.left, r.bottom - r.top)
    time.sleep(settle / 1000.0)
    app.processEvents()
    return pm


def shot(app, hwnd, name, settle=10):
    pm = grab(app, hwnd, settle=settle)
    if pm is None or pm.width() <= 1:
        print("   !! 抓图失败：%s" % name, flush=True)
        return None
    p = os.path.join(SHOT_DIR, name)
    pm.save(p)
    print("   %-40s %dx%d" % (name, pm.width(), pm.height()), flush=True)
    return p


def main():
    exe = newest_exe()
    exe_name = os.path.basename(exe)
    print("== v1.31.0 真机验收 ==\n exe: %s\n %d B\n ROOT: %s"
          % (exe, os.path.getsize(exe), ROOT), flush=True)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    proc = subprocess.Popen([exe], cwd=ROOT)
    print(" 已启动 pid=%s" % proc.pid, flush=True)
    win = find_window(exe_name, {proc.pid}, timeout=90, title_sub="Build")
    if not win:
        print("!! 没找到主窗口（带 Build 的标题）", flush=True)
        proc.kill()
        return 2
    title = wtitle(win)
    cw, ch = client_size(win)
    print(" 主窗口 hwnd=%s title=%r 客户区 %dx%d" % (win, title, cw, ch), flush=True)
    ok_title = "v1.31.0" in title and "2609240042" in title
    print(" [%s] 标题带 v1.31.0 (Build 2609240042)"
          % ("PASS" if ok_title else "FAIL"), flush=True)

    time.sleep(7)
    shot(app, win, "90_live_home.png", settle=6)

    # ---- 演员库：三围带加粗罩杯；右侧**不该**再有 A-Z 竖条 ----
    click(win, *SIDEBAR["演员库"])
    time.sleep(3)
    lib_png = shot(app, win, "91_live_actors_no_az.png", settle=14)

    # 「没有 A-Z 条」的像素判据：内容区最右侧 34px 竖带应当与滚动条同色，
    # 而不是索引条那种「高对比小字 + 当前字母高亮」的花纹。
    # 这里退一步做弱断言：竖带里**极亮像素**占比应当很低（索引条有白色字母）。
    try:
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen()
        r = wt.RECT()
        u32.GetWindowRect(win, ctypes.byref(r))
        pm = scr.grabWindow(0, r.left, r.top, r.right - r.left, r.bottom - r.top)
        img = pm.toImage()
        x0, x1 = cw - 34, cw - 4
        ys = range(140, min(ch - 60, 1000), 4)
        tot = bright = 0
        for y in ys:
            for x in range(x0, x1, 3):
                c = img.pixelColor(x, y)
                v = (c.red() + c.green() + c.blue()) / 3.0
                tot += 1
                if v > 170:
                    bright += 1
        ratio = bright / max(1, tot)
        print(" [%s] 演员库右侧 30px 竖带极亮像素占比 %.2f%%（索引条在时应明显偏高）"
              % ("PASS" if ratio < 0.02 else "FAIL", ratio * 100), flush=True)
    except Exception as e:
        print(" [跳过] 右侧竖带像素检查：%s" % e, flush=True)

    # ---- 导演库 ----
    click(win, *SIDEBAR["导演库"])
    time.sleep(3)
    shot(app, win, "92_live_directors_no_az.png", settle=12)

    # ---- 工具窗：演员检测 ----
    try:
        with open(COORDS, encoding="utf-8") as f:
            co = json.load(f)
        nav = co.get("dialog_nav") or {}
        tools_btn = co.get("main_settings_btn")
        v1310 = co.get("v1310") or {}
    except Exception as e:
        print(" [跳过] 读不到界面坐标：%s" % e, flush=True)
        nav, tools_btn, v1310 = {}, None, {}

    print(" 工具窗导航坐标共 %d 页：%s" % (len(nav), list(nav)), flush=True)

    if tools_btn and nav.get("演员检测"):
        click(win, tools_btn[0], tools_btn[1])
        time.sleep(3)
        dlg = find_window(exe_name, {proc.pid}, timeout=25, title_sub="工具",
                          minw=600, minh=400)
        if not dlg:
            print("!! 没找到工具窗", flush=True)
        else:
            print(" 工具窗 hwnd=%s size=%s" % (dlg, client_size(dlg)), flush=True)
            for key, png in (("演员检测", "93_live_tools_actorcheck.png"),
                             ("图像检测", "94_live_tools_image.png")):
                pt = nav.get(key)
                if not pt:
                    print("   !! 坐标里没有 %s" % key, flush=True)
                    continue
                click(dlg, pt[0], pt[1])
                time.sleep(2)
                shot(app, dlg, png, settle=8)

            # 回到演员检测，真跑「开始检测」（真实 5909 位演员）
            pt = nav.get("演员检测")
            click(dlg, pt[0], pt[1])
            time.sleep(3)
            run = v1310.get("run_btn")
            if run:
                print(" [点击] 演员检测 · 开始检测 @(%d,%d)" % (run[0], run[1]), flush=True)
                t0 = time.time()
                click(dlg, run[0], run[1])
                for tag, wait in (("a", 4), ("b", 8), ("c", 10)):
                    time.sleep(wait)
                    shot(app, dlg, "95%s_live_actorcheck_run.png" % tag, settle=3)
                print(" [检测] 点击后共等待 %.1fs" % (time.time() - t0), flush=True)

            # 试着点结果树的第一簇（树中心往下一点点）
            tree = v1310.get("tree")
            if tree:
                tx, ty = tree
                click(dlg, tx, ty - 14)
                time.sleep(1)
                u32.PostMessageW(dlg, WM_KEYDOWN, VK_DOWN, 0)
                u32.PostMessageW(dlg, WM_KEYUP, VK_DOWN, 0)
                u32.PostMessageW(dlg, WM_KEYDOWN, VK_DOWN, 0)
                u32.PostMessageW(dlg, WM_KEYUP, VK_DOWN, 0)
                time.sleep(3)
                shot(app, dlg, "96_live_actorcheck_detail.png", settle=8)

            # 下半：编辑区检索一位演员
            kw = v1310.get("kw")
            sb = v1310.get("search_btn")
            if kw and sb:
                click(dlg, kw[0], kw[1])
                time.sleep(1)
                for chx in "深田":
                    u32.PostMessageW(dlg, 0x0102, ord(chx), 0)   # WM_CHAR
                time.sleep(1)
                click(dlg, sb[0], sb[1])
                time.sleep(3)
                shot(app, dlg, "97_live_actorcheck_editor.png", settle=8)

            u32.PostMessageW(dlg, WM_CLOSE, 0, 0)
            time.sleep(2)

    time.sleep(2)
    u32.PostMessageW(win, WM_CLOSE, 0, 0)
    for _ in range(20):
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    if proc.poll() is None:
        proc.kill()
    print(" 已退出 rc=%s" % proc.returncode, flush=True)

    # ---- app.log 找未捕获异常 ----
    log_p = os.path.join(ROOT, "index_data", "logs", "app.log")
    bad = []
    if os.path.exists(log_p):
        with open(log_p, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for ln in lines[-500:]:
            if "未捕获异常" in ln or "Traceback" in ln:
                bad.append(ln.rstrip())
        print("\n app.log 末 10 行：", flush=True)
        for ln in lines[-10:]:
            print("   " + ln.rstrip(), flush=True)
    else:
        print(" !! 没找到 app.log：%s" % log_p, flush=True)
    print("\n [%s] app.log 无未捕获异常（命中 %d 条）"
          % ("PASS" if not bad else "FAIL", len(bad)), flush=True)
    for ln in bad[:8]:
        print("   " + ln, flush=True)

    print("\n 截图目录 %s：" % SHOT_DIR, flush=True)
    for s in sorted(os.listdir(SHOT_DIR)):
        print("   " + s, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
