# -*- coding: utf-8 -*-
"""v1.30.0 真机验收：启动刚打好的 exe，真键盘鼠标点一遍四条反馈。

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/live_verify_v1300.py', run_name='__main__')"

与 `live_verify.py` 的分工：那个是全量巡检（画像概览要重算、去重要跑、标签优化会弹确认框，
一轮好几分钟）；本脚本只盯 v1.30.0 的四条反馈，几十秒跑完：

  1. 窗口标题带 v1.30.0（Build 2609230041）
  2. 演员库：真机 5909 位演员下，右侧 A-Z 索引条在
  3. 点索引条上的字母 → 列表真的按首字母重排并滚过去
  4. 导演库同样有索引条
  5. 工具窗：新页「手动修改」能开、能检索出片子、表单建得出来
  6. 工具窗：新页「图像检测」能开、点「开始检测」能真跑起来（真扫，看进度）
  7. app.log 里本会话不能有「未捕获异常」

日志写在 `C:/Users/zouzu/AppData/Local/Temp/lmc_live_v1300.log`（Bash 重定向会被 shim 吞掉，
所以脚本自己写文件）。
"""
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_v1300.log"
os.makedirs(os.path.dirname(LOG), exist_ok=True)
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots_v1300_live")
COORDS = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"

u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_CLOSE = 0x0200, 0x0201, 0x0202, 0x0010

# 侧边栏条目 -> 客户区坐标（1920x1080 默认 DPI，与 live_verify.py 同一张表）
SIDEBAR = {"演员库": (93, 391), "导演库": (93, 428), "首页": (93, 87)}

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
    if n <= 0:
        return ""
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def client_size(h):
    r = wt.RECT()
    u32.GetClientRect(h, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


def find_window(exe_name, extra=(), timeout=60, title_sub="Build", minw=400, minh=300):
    """找可见的顶层窗口；主窗口 / 工具窗都用 `Build` 之外的特征区分（见下面 title_sub）。"""
    hits, pids = [], [set(extra)]
    _mw = {"w": 0}

    def cb(h, _):
        if u32.IsWindowVisible(h) and wpid(h) in pids[0]:
            if title_sub and title_sub not in wtitle(h):
                return True
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            w, ht = r.right - r.left, r.bottom - r.top
            if w > minw and ht > minh:
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
        time.sleep(1)
    return None


def click(hwnd, x, y):
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    for msg, wp in ((WM_MOUSEMOVE, 0), (WM_LBUTTONDOWN, 1), (WM_LBUTTONUP, 0)):
        u32.PostMessageW(hwnd, msg, wp, lp)
        time.sleep(0.08)


def bright(pm, step=8, x0=210, y0=220):
    img = pm.toImage()
    n = 0
    for y in range(y0, min(img.height(), y0 + 700), step):
        for x in range(x0, img.width(), step):
            c = img.pixelColor(x, y)
            if c.red() > 100 or c.green() > 100 or c.blue() > 100:
                n += 1
    return n


def grab(app, hwnd, tries=8, settle=10):
    pm = None
    for _ in range(tries):
        pm = app.primaryScreen().grabWindow(hwnd)
        if pm.width() > 1 and pm.height() > 1:
            break
        u32.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        app.processEvents()
    if pm is None or pm.width() <= 1:
        return pm
    best, best_n = pm, bright(pm)
    for _ in range(settle):
        time.sleep(0.5)
        app.processEvents()
        cand = app.primaryScreen().grabWindow(hwnd)
        if cand.width() <= 1:
            continue
        n = bright(cand)
        if n > best_n:
            best, best_n = cand, n
    return best


def shot(app, hwnd, name, settle=10):
    os.makedirs(SHOT_DIR, exist_ok=True)
    pm = grab(app, hwnd, settle=settle)
    p = os.path.join(SHOT_DIR, name)
    if pm is not None and pm.width() > 1:
        pm.save(p)
        print("  [抓图] %-34s %dx%d  content=%d" % (name, pm.width(), pm.height(), bright(pm)), flush=True)
        return p
    print("  [抓图] %-34s 失败（0x0）" % name, flush=True)
    return None


def main():
    exe = newest_exe()
    exe_name = os.path.basename(exe)
    print("== v1.30.0 真机验收 ==\n exe: %s\n %d B" % (exe, os.path.getsize(exe)), flush=True)

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
    print(" 主窗口 hwnd=%s title=%r" % (win, title), flush=True)
    ok_title = "v1.30.0" in title and "2609230041" in title
    print(" [%s] 标题带 v1.30.0 (Build 2609230041)" % ("PASS" if ok_title else "FAIL"), flush=True)
    cw, ch = client_size(win)
    print(" 客户区 %dx%d" % (cw, ch), flush=True)

    time.sleep(6)
    shot(app, win, "90_live_home.png", settle=6)

    # ---- 演员库 + A-Z 索引条 ----
    click(win, *SIDEBAR["演员库"])
    time.sleep(3)
    actors_png = shot(app, win, "91_live_actors_az.png", settle=12)

    # 索引条：贴在内容区最右，宽 30；27 行均分内容区高度
    rail_x = cw - 15
    top = 60                      # 顶栏 + 页标题大致占掉的高度（只求落在某一行内，不求精确）
    rail_h = ch - top - 30
    row = rail_h / 27.0
    letter_i = 2                  # 第 3 行 = 'C'
    rail_y = int(top + row * (letter_i + 0.5))
    print(" [点击] 索引条 'C' @(%d,%d)（行高 %.1f）" % (rail_x, rail_y, row), flush=True)
    click(win, rail_x, rail_y)
    time.sleep(4)
    shot(app, win, "92_live_actors_jump_C.png", settle=12)

    # ---- 导演库 ----
    click(win, *SIDEBAR["导演库"])
    time.sleep(3)
    shot(app, win, "93_live_directors_az.png", settle=12)

    # ---- 工具窗：新两页 ----
    try:
        with open(COORDS, encoding="utf-8") as f:
            co = json.load(f)
        nav = co.get("dialog_nav") or {}
        tools_btn = co.get("main_settings_btn")
    except Exception as e:
        print(" [跳过] 读不到界面坐标：%s" % e, flush=True)
        nav, tools_btn = {}, None

    if tools_btn:
        click(win, tools_btn[0], tools_btn[1])
        time.sleep(3)
        dlg = find_window(exe_name, {proc.pid}, timeout=25, title_sub="工具", minw=600, minh=400)
        if not dlg:
            print("!! 没找到工具窗", flush=True)
        else:
            print(" 工具窗 hwnd=%s title=%r size=%s" % (dlg, wtitle(dlg), client_size(dlg)), flush=True)
            v13 = co.get("v1300") or {}
            for key, png in (("手动修改", "94_live_tools_manual.png"),
                             ("图像检测", "95_live_tools_image.png")):
                pt = nav.get(key)
                if not pt:
                    continue
                click(dlg, pt[0], pt[1])
                time.sleep(2)
                shot(app, dlg, png, settle=6)
            # 「手动修改」：真点一下列表首行，看右侧表单是否建出来
            if v13.get("manual_first_row"):
                pt = v13["manual_first_row"]
                print(" [点击] 手动修改·列表首行 @(%d,%d)" % (pt[0], pt[1]), flush=True)
                click(dlg, pt[0], pt[1])
                time.sleep(2)
                shot(app, dlg, "94b_live_tools_manual_form.png", settle=8)
            # 「图像检测」：真点「开始检测」，看后台线程是否真跑起来
            if v13.get("image_run_btn"):
                # 先把工具窗切回「图像检测」
                pt = nav.get("图像检测")
                if pt:
                    click(dlg, pt[0], pt[1])
                    time.sleep(1)
                pt = v13["image_run_btn"]
                print(" [点击] 图像检测·开始检测 @(%d,%d)" % (pt[0], pt[1]), flush=True)
                click(dlg, pt[0], pt[1])
                time.sleep(12)
                shot(app, dlg, "96_live_tools_image_running.png", settle=6)
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

    # ---- app.log 里找未捕获异常 ----
    log_p = os.path.join(ROOT, "index_data", "logs", "app.log")
    bad = []
    if os.path.exists(log_p):
        with open(log_p, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        # 只看本会话（最后 400 行足够；上一轮的记录不会出现在这个新目录里）
        for ln in lines[-400:]:
            if "未捕获异常" in ln or "Traceback" in ln:
                bad.append(ln.rstrip())
        print("\n app.log 末 8 行：", flush=True)
        for ln in lines[-8:]:
            print("   " + ln.rstrip(), flush=True)
    else:
        print(" !! 没找到 app.log：%s" % log_p, flush=True)
    print("\n [%s] app.log 无未捕获异常（命中 %d 条）"
          % ("PASS" if not bad else "FAIL", len(bad)), flush=True)
    for ln in bad[:8]:
        print("   " + ln, flush=True)

    shots = sorted(os.listdir(SHOT_DIR)) if os.path.isdir(SHOT_DIR) else []
    print("\n 截图目录 %s：" % SHOT_DIR, flush=True)
    for s in shots:
        print("   " + s, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
