# -*- coding: utf-8 -*-
"""v1.32.0 真机验收：启动根目录最新 exe，对着**真实索引的副本**逐页截图。

与 v1.31.0 的差别（本轮四条反馈）：
  - 反馈 1：工具窗三检测页（重复 / 图像 / 演员）都该看到「普通算法 / AI 算法」单选
    + 「极速模式」勾选 —— 真机逐页抓图核对（离屏只能验源码与控件存在）。
  - 反馈 3：主窗切语言（个性化 → 外观 → 界面语言）后，侧栏文字应真变；切回中文恢复。
    RTL（阿拉伯语）只翻文字、版面不镜像。
  - 反馈 4：打开「关于」看新正文（九模块 + 版本号 + 版权 + 链接）。
  - 反馈 2：截图引用已在 README，真机只验 docs/screenshots 目录存在且 23 张齐。

用法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/live_verify_v1320.py', run_name='__main__')"
"""
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify_v1320.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots_v1320_live")
os.makedirs(SHOT_DIR, exist_ok=True)
COORDS = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"

u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
WM_CLOSE, WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0010, 0x0100, 0x0101, 0x0102
VK_DOWN, VK_RETURN = 0x28, 0x0D

# 主窗侧栏条目 -> 客户区坐标（1920x1080、默认 DPI）。
SIDEBAR = {"首页": (93, 87), "演员库": (93, 391), "导演库": (93, 428)}

EXE_GLOBS = ("流明盒-v*.exe", "本地影视中心-v*.exe")

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print(" [%s] %s  %s" % ("PASS" if cond else "FAIL", tag, detail), flush=True)


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


def dump_running_modal(exe_name, extra=()):
    """打印当前属于本进程的可见窗口（排查模态框/子窗用）。"""
    live = pids_of_exe(exe_name) | set(extra)
    out = []

    def cb(h, _l):
        if u32.IsWindowVisible(h) and wpid(h) in live:
            out.append((h, wtitle(h), client_size(h)))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    for h, t, s in out:
        print("   窗 hwnd=%s %r %s" % (h, t, s), flush=True)
    return out


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
    print("   %-44s %dx%d" % (name, pm.width(), pm.height()), flush=True)
    return p


def ocr_like_brightness(app, hwnd, region):
    """某区域的平均亮度（粗判「有没有内容」）。region=(x0,y0,x1,y1) 客户区坐标。"""
    from PySide6.QtGui import QGuiApplication
    scr = QGuiApplication.primaryScreen()
    if scr is None:
        return None
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    pm = scr.grabWindow(0, r.left, r.top, r.right - r.left, r.top + r.bottom - r.top)
    img = pm.toImage()
    x0, y0, x1, y1 = region
    tot = 0
    lum = 0.0
    for y in range(max(0, y0), min(img.height(), y1), 4):
        for x in range(max(0, x0), min(img.width(), x1), 4):
            c = img.pixelColor(x, y)
            lum += (c.red() + c.green() + c.blue()) / 3.0
            tot += 1
    return lum / max(1, tot)


def main():
    exe = newest_exe()
    exe_name = os.path.basename(exe)
    print("== v1.32.0 真机验收 ==\n exe: %s\n %d B\n ROOT: %s"
          % (exe, os.path.getsize(exe), ROOT), flush=True)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    # --- 反馈 2 静态核查：截图目录齐 ---
    ss = os.path.join(ROOT, "docs", "screenshots")
    n_png = len([f for f in os.listdir(ss) if f.endswith(".png")]) if os.path.isdir(ss) else 0
    check("反馈 2 docs/screenshots 齐 23 张", n_png == 23, n_png)

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
    check("标题带 v1.32.0 与构建号 2609240043",
          "v1.32.0" in title and "2609240043" in title, title)

    time.sleep(8)
    shot(app, win, "90_live_home.png", settle=6)

    # ---- 主窗中文基准：侧栏分组标题应为中文 ----
    click(win, *SIDEBAR["演员库"])
    time.sleep(3)
    shot(app, win, "91_live_actors_zh.png", settle=12)
    click(win, *SIDEBAR["首页"])
    time.sleep(2)

    # ---- 工具窗坐标 ----
    try:
        with open(COORDS, encoding="utf-8") as f:
            co = json.load(f)
        nav = co.get("dialog_nav") or {}
        tools_btn = co.get("main_settings_btn")
        v1320 = co.get("v1320") or co.get("v1310") or {}
        ap = (co.get("v1320") or {}).get("appearance") or {}
    except Exception as e:
        print(" [跳过] 读不到界面坐标：%s" % e, flush=True)
        nav, tools_btn, v1320, ap = {}, None, {}, {}
    print(" 工具窗导航坐标共 %d 页：%s" % (len(nav), list(nav)), flush=True)

    dlg = None
    if tools_btn and nav:
        click(win, tools_btn[0], tools_btn[1])
        time.sleep(4)
        dlg = find_window(exe_name, {proc.pid}, timeout=25, title_sub="工具",
                          minw=600, minh=400)
        if not dlg:
            print("!! 没找到工具窗；当前可见窗口：", flush=True)
            dump_running_modal(exe_name, {proc.pid})
        else:
            print(" 工具窗 hwnd=%s size=%s" % (dlg, client_size(dlg)), flush=True)
            dcw, dch = client_size(dlg)

            # ---- 反馈 1：三检测页逐页抓图（看双算法 + 极速模式） ----
            for key, png in (("重复检测", "92_live_tools_dedupe_algo.png"),
                             ("图像检测", "93_live_tools_image_algo.png"),
                             ("演员检测", "94_live_tools_actor_algo.png")):
                pt = nav.get(key)
                if not pt:
                    print("   !! 坐标里没有 %s" % key, flush=True)
                    continue
                click(dlg, pt[0], pt[1])
                time.sleep(2.5)
                shot(app, dlg, png, settle=8)

            # ---- 反馈 1：真点一次「普通算法」跑图像检测（秒出，不依赖 Ollama） ----
            pt = nav.get("图像检测")
            if pt:
                click(dlg, pt[0], pt[1])
                time.sleep(2)
                run = (v1320.get("image") or {}).get("run_btn")
                if run:
                    print(" [点击] 图像检测 · 开始检测 @(%d,%d)" % (run[0], run[1]), flush=True)
                    t0 = time.time()
                    click(dlg, run[0], run[1])
                    for tag, wait in (("a", 3), ("b", 6), ("c", 8)):
                        time.sleep(wait)
                        shot(app, dlg, "95%s_live_image_run.png" % tag, settle=3)
                    print(" [检测] 图像检测点击后共等待 %.1fs" % (time.time() - t0), flush=True)

            # ---- 反馈 1：真点一次「普通算法」跑演员检测（真实 5909 位演员） ----
            pt = nav.get("演员检测")
            if pt:
                click(dlg, pt[0], pt[1])
                time.sleep(2.5)
                run = (v1320.get("actor") or {}).get("run_btn")
                if run:
                    print(" [点击] 演员检测 · 开始检测 @(%d,%d)" % (run[0], run[1]), flush=True)
                    t0 = time.time()
                    click(dlg, run[0], run[1])
                    for tag, wait in (("a", 4), ("b", 8), ("c", 10)):
                        time.sleep(wait)
                        shot(app, dlg, "96%s_live_actor_run.png" % tag, settle=3)
                    print(" [检测] 演员检测点击后共等待 %.1fs" % (time.time() - t0), flush=True)

            # ---- 反馈 3：个性化 → 外观 → 切语言（真机验证立即生效） ----
            pt = nav.get("个性化设置")
            if pt:
                click(dlg, pt[0], pt[1])
                time.sleep(2.5)
                shot(app, dlg, "97_live_tools_personal_zh.png", settle=8)
                lang_cb = ap.get("lang_combo")
                if lang_cb:
                    print(" [点击] 语言下拉 @(%d,%d)" % (lang_cb[0], lang_cb[1]), flush=True)
                    click(dlg, lang_cb[0], lang_cb[1])
                    time.sleep(1.5)
                    shot(app, dlg, "98_live_lang_combo_open.png", settle=6)
                    # 下拉列表第 2 项 = en（简体中文排第一）
                    item = ap.get("lang_item2")
                    if item:
                        click(dlg, item[0], item[1])
                    else:
                        u32.PostMessageW(dlg, WM_KEYDOWN, VK_DOWN, 0)
                        u32.PostMessageW(dlg, WM_KEYUP, VK_DOWN, 0)
                        u32.PostMessageW(dlg, WM_KEYDOWN, VK_RETURN, 0)
                        u32.PostMessageW(dlg, WM_KEYUP, VK_RETURN, 0)
                    time.sleep(3)
                    shot(app, dlg, "99_live_tools_personal_en.png", settle=8)
                    # 主窗是否也跟着变（侧栏重建）
                    time.sleep(2)
                    shot(app, win, "99b_live_main_en.png", settle=8)
                    # 切回简体中文（第 1 项）
                    click(dlg, lang_cb[0], lang_cb[1])
                    time.sleep(1.2)
                    item1 = ap.get("lang_item1")
                    if item1:
                        click(dlg, item1[0], item1[1])
                    else:
                        u32.PostMessageW(dlg, WM_KEYDOWN, VK_DOWN, 0)
                        u32.PostMessageW(dlg, WM_KEYUP, VK_DOWN, 0)
                        u32.PostMessageW(dlg, WM_KEYDOWN, VK_RETURN, 0)
                        u32.PostMessageW(dlg, WM_KEYUP, VK_RETURN, 0)
                    time.sleep(3)
                    shot(app, dlg, "99c_live_tools_personal_back_zh.png", settle=8)
                    shot(app, win, "99d_live_main_back_zh.png", settle=8)

            u32.PostMessageW(dlg, WM_CLOSE, 0, 0)
            time.sleep(2)

    # ---- 反馈 4：「关于」窗 ----
    about_btn = (v1320 or {}).get("about_btn") or {}
    try:
        # 优先用坐标里的「关于」入口；没有就点侧栏品牌区（REPO_URL 热区不弹窗），
        # 退而求其次用快捷键式菜单——真机这轮以抓主窗为主。
        if about_btn:
            click(win, about_btn[0], about_btn[1])
            time.sleep(2.5)
            aw = find_window(exe_name, {proc.pid}, timeout=15, title_sub="关于",
                             minw=300, minh=200)
            if aw:
                shot(app, aw, "A0_live_about.png", settle=10)
                u32.PostMessageW(aw, WM_CLOSE, 0, 0)
            else:
                print(" !! 没找到「关于」窗", flush=True)
                dump_running_modal(exe_name, {proc.pid})
    except Exception as e:
        print(" [跳过] 关于窗：%s" % e, flush=True)

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
    lines = []
    if os.path.exists(log_p):
        with open(log_p, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for ln in lines[-800:]:
            if "未捕获异常" in ln or "Traceback" in ln:
                bad.append(ln.rstrip())
        print("\n app.log 末 14 行：", flush=True)
        for ln in lines[-14:]:
            print("   " + ln.rstrip(), flush=True)
        # v1.27.0 命门：日志里出现第二行「实时状态：采集能力」= 面板被重建过
        n_sysmon = sum(1 for ln in lines if "实时状态：采集能力" in ln or "采集能力" in ln)
        print(" 「采集能力」出现 %d 次（>1 说明面板重建过，需核对线程单例）" % n_sysmon, flush=True)
    else:
        print(" !! 没找到 app.log：%s" % log_p, flush=True)
    check("app.log 无未捕获异常", not bad, bad[:3])

    print("\n 截图目录 %s：" % SHOT_DIR, flush=True)
    for s in sorted(os.listdir(SHOT_DIR)):
        print("   " + s, flush=True)

    print("\n" + "=" * 70, flush=True)
    print("真机 PASS %d / FAIL %d" % (len(PASS), len(FAIL)), flush=True)
    for t in FAIL:
        print("  - " + t, flush=True)
    print("=" * 70, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
