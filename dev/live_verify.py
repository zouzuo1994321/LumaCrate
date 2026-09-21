# -*- coding: utf-8 -*-
"""真机验收脚本：启动根目录最新 exe，点击侧边栏逐页截图。

为什么需要它：离屏渲染（render_*.py）只能验证布局与逻辑，真机才能验证**打包后的
exe 是否真的能启动、真实字体下卡片是否完整**。二者互补，发布前都应过一遍。

用法：
    python dev/live_verify.py            # 全部页面
    python dev/live_verify.py 全部 演员库  # 指定页面

实现要点（踩过的坑）：
- 只按「本次启动的进程 PID」定位窗口，**绝不按进程名批杀**，否则会误杀同名的
  资源管理器窗口（目录名也叫「本地影视中心」）。
- onefile 下「引导器」与「应用」是两个同名进程，应用子进程 pid 在 Popen 之后才
  出现，故每轮都要重新采集 PID 集合。
- tasklist 输出是 GBK，`text=True` 会 UnicodeDecodeError，需自行 decode("gbk")。
- 侧边栏是自绘控件，用 PostMessage(WM_LBUTTONDOWN/UP) 点击客户区坐标即可；
  坐标随「主题/字号」变化，可用 --scan 模式先扫描文字行位置。
"""
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_live_verify.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "dev", "screenshots")

u32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202

# 侧边栏条目 -> 客户区坐标（1920x1080、默认 DPI 下测量；变更主题后需重扫）
# v1.24.0：导航多了「智能推荐」「导演库」，整列下移；y 由 dev/_probe_sidebar.py
#           直接量取控件几何（探针里会临时建一个叫「电影」的库，让「媒体库」分组头
#           也参与布局，第一个库行的 y 就不再靠推算）。改 _brand() / 导航后请重跑探针。
SIDEBAR = {
    "首页": (93, 87),
    "最近播放": (93, 124),
    "我的收藏": (93, 161),
    "智能推荐": (93, 198),
    "文件夹": (93, 235),
    "合集": (93, 272),
    "全部": (93, 354),
    "演员库": (93, 391),
    "导演库": (93, 428),
    "电影": (93, 510),
}
# 一次最多传 5 个页面名（页面截图编号 18~22，工具窗口固定占 30 起，不会撞号）
# v1.25.0（反馈 6）：首页排第一 —— 它要拍的是三个快捷筛选芯片被点中后的高亮差异，
# 而「首页」正是 _load() 后唯一会显示芯片的页面。
PAGES = ["首页", "全部", "智能推荐", "导演库", "合集"]


# v1.27.0：软件更名「流明盒」，exe 前缀随动；旧前缀一并保留，
# 这样要拿上一版做回归时不用改脚本。
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


def find_window(exe_name, extra, timeout=60, title_sub=None):
    """找主窗口。

    v1.24.0 坑：加了启动画面后，进程里**第一个**可见的大窗口是 `QSplashScreen`
    （v1.27.0 起 440×344，标题默认取 QApplication 的 applicationName，就是软件名），
    它会先于主窗口出现并通过宽高门槛 → 脚本抓住 splash，等它淡出销毁后 hwnd 失效，
    截图全变 0×0、点击也全落空。所以必须用标题里的版本号（主窗口标题形如
    「流明盒  v1.27.0 (Build 2609210037)」）把主窗口认出来 —— 这就是下面
    `title_sub="Build"` 的来历，与软件叫什么无关。
    """
    hits, pids = [], [set(extra)]

    def cb(h, _):
        if u32.IsWindowVisible(h) and wpid(h) in pids[0]:
            if title_sub and title_sub not in wtitle(h):
                return True
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            w, ht = r.right - r.left, r.bottom - r.top
            if w > 400 and ht > 300:
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


def grab(app, hwnd, tries=20, gap=0.4, settle=40):
    """grabWindow 偶发只返回 1x1（窗口尚未真正绘制 / 被遮挡 / 刚恢复未重绘）。

    实测：同一 exe 连跑两次，第二次所有页面截图都成了 1x1，害得把上一轮的好图覆盖掉。
    这里重试到拿到有效尺寸（>1x1）为止，拿不到也至少把窗口置前再试一次。

    v1.21.0 追加：还遇到「尺寸正常、但卡片区还没画」的帧（静态表头/标题有、卡片没有），
    会被误判成「页面空白」。所以拿到有效尺寸后再连拍几帧，取**内容最多**的一帧。

    v1.23.0 再修：原来「够 300 就提前收工」会把**上一页的残帧**当成当前页 ——
    实测阈值分不清：空墙 7 / 首页 1118 / 演员库 2260 / 满墙 9522，
    点开「全部」后头几秒抓到的仍是首页（1118 ≥ 300）就直接收工，
    而海报墙实际要 **~15 秒**才画满（dev/_probe_live_actors.py 实测第 6 帧才跳到 77287）。
    所以改成**不提前 break**，固定采样 settle 帧取最亮的一帧。
    """
    pm = app.primaryScreen().grabWindow(hwnd)
    for _ in range(tries):
        if pm.width() > 1 and pm.height() > 1:
            break
        u32.SetForegroundWindow(hwnd)
        time.sleep(gap)
        app.processEvents()
        pm = app.primaryScreen().grabWindow(hwnd)
    if pm.width() > 1:
        best, best_n = pm, bright_samples(pm)
        for _ in range(settle):
            time.sleep(0.5)
            app.processEvents()
            cand = app.primaryScreen().grabWindow(hwnd)
            if cand.width() <= 1:
                continue
            n = bright_samples(cand)
            if n > best_n:
                best, best_n = cand, n
        pm = best
    return pm


def bright_samples(pm, step=8, x0=210, y0=220):
    """抽样统计**内容区**亮像素数：空白页只有零星文字（几十），卡片页/表格页上千。

    v1.23.0 修：原先从 (0,0) 扫整窗，侧栏 + 顶栏 + 页头本身就贡献几百个亮像素，
    于是「只有头部画出来、卡片还没画」的**半成品帧**也能跨过 300 的门槛被当成好帧 ——
    结果 19_recent / 20_actors 两张图只有头部不同、内容区完全相同（实测用
    dev/_probe_live_actors.py 等 12 秒后内容区亮像素 18554，说明页面其实是好的）。
    现在只扫 x>=210 且 y>=220 的内容区，头部不再能蒙混过关。
    """
    img = pm.toImage()
    n = 0
    for y in range(y0, img.height(), step):
        for x in range(x0, img.width(), step):
            c = img.pixelColor(x, y)
            if c.red() > 100 or c.green() > 100 or c.blue() > 100:
                n += 1
    return n


# 设置对话框内部的点击坐标由 dev/_scratch/ui_coords.py 离屏算好写在这里。
# 为什么不让本脚本自己算：本进程已经有一个**真实平台**的 QApplication，
# 再建窗口会真的弹窗、还会和待验收的 exe 抢焦点；而且 offscreen 屏只有 800×800，
# 算出来的对话框尺寸（760）与真机（1000×900）不一致。
COORDS = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"
WM_CLOSE = 0x0010


def load_coords():
    import json
    try:
        with open(COORDS, encoding="utf-8") as f:
            c = json.load(f)
    except Exception as e:
        print("[跳过] 读不到界面坐标 %s: %s" % (COORDS, e), flush=True)
        return None
    if c.get("main_size") != [1920, 1080]:
        print("[跳过] 坐标是按 %s 算的，与真机 1920x1080 不符"
              % (c.get("main_size"),), flush=True)
        return None
    return c


def dump_windows(pids, label):
    """诊断用：列出该 PID 集合下所有顶层窗口（含不可见），定位「窗口没出来」的真因。"""
    rows = []

    def cb(h, _):
        if wpid(h) in pids:
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            rows.append((h, bool(u32.IsWindowVisible(h)), r.left, r.top,
                         r.right - r.left, r.bottom - r.top, wtitle(h)))
        return True
    u32.EnumWindows(EnumWindowsProc(cb), 0)
    print(f"--- 窗口快照 {label} ---", flush=True)
    for h, vis, x, y, w, ht, t in rows:
        print(f"  hwnd={h} vis={vis} pos=({x},{y}) size={w}x{ht} title={t!r}", flush=True)
    return rows


def find_window_ex(exe_name, extra, exclude=(), timeout=25, title_sub=""):
    """在同一 PID 下找**另一个**可见顶层窗口（设置对话框）。"""
    hits, pids = [], [set(extra)]

    def cb(h, _):
        if h in exclude:
            return True
        if u32.IsWindowVisible(h) and wpid(h) in pids[0]:
            if title_sub and title_sub not in wtitle(h):
                return True
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            w, ht = r.right - r.left, r.bottom - r.top
            if w > 300 and ht > 200:
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
        time.sleep(0.8)
    return None


VK_RETURN, WM_KEYDOWN, WM_KEYUP = 0x0D, 0x0100, 0x0101


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


def bottom_button_centers(pm):
    """从确认框截图里找出底部按钮的横向中心（左 → 右）。

    为什么不用固定坐标：QMessageBox 的按钮宽度随文案 / 字体 / DPI 变化，写死会在
    改文案后**静默点空**。这里直接扫「底部条带里的亮像素列」——确认框底部只有按钮
    是亮的（本主题下按钮是浅色圆角块），聚类即得每个按钮的中心，天然自适应。
    """
    img = pm.toImage()
    w, h = img.width(), img.height()
    cols = []
    for x in range(w):
        n = 0
        for y in range(max(0, h - 34), max(1, h - 4)):
            c = img.pixelColor(x, y)
            if c.red() > 90 and c.green() > 90 and c.blue() > 90:
                n += 1
        cols.append(n)
    groups, cur = [], None
    for x, n in enumerate(cols):
        if n > 0 and cur is None:
            cur = x
        elif n == 0 and cur is not None:
            if x - cur >= 8:
                groups.append(((cur + x - 1) // 2, x - cur))
            cur = None
    if cur is not None:
        groups.append(((cur + w - 1) // 2, w - cur))
    groups.sort()
    return groups


def confirm_modal_yes(app, hwnd, label="确认框"):
    """点确认框里**最左边**那个按钮（Qt 的 `Yes | No` 顺序是 Yes 在前）。

    ⚠ 不能图省事按回车（v1.25.0 真机验收第二轮踩坑）：
    `ui_settings._tagopt_apply()` 是
        QMessageBox.question(..., Yes | No, QMessageBox.No)
    —— 默认按钮**刻意设成 No**（破坏性动作的安全默认）。回车 = 触发默认按钮 = No
    = 立刻 return，表现是「确认框消失了、目标文件一个字节没变、日志毫无异常」。
    """
    pm = grab(app, hwnd, tries=6, settle=3)
    grp = bottom_button_centers(pm)
    print(f"[{label}] 底部按钮中心(宽度): {grp}", flush=True)
    if not grp:
        print(f"[{label}] 没扫到按钮，退回「按回车」", flush=True)
        return press_ok(hwnd)
    cx = grp[0][0]
    cy = max(0, pm.height() - 22)
    print(f"[{label}] 点最左按钮 @({cx},{cy})", flush=True)
    click(hwnd, cx, cy)
    time.sleep(1.2)
    ok = not bool(u32.IsWindow(hwnd))
    if not ok:
        print(f"[{label}] 点完还在，改按回车兜底", flush=True)
        ok = press_ok(hwnd)
    return ok


def scan_sidebar(path):
    """扫描侧边栏文字行的纵向中心，用于刷新 SIDEBAR 坐标。"""
    from PIL import Image
    im = Image.open(path).convert("L")
    px = im.load()
    bands, cur = [], None
    for y in range(60, 700):
        bright = sum(1 for x in range(10, 135) if px[x, y] > 90)
        if bright >= 3 and cur is None:
            cur = y
        elif bright < 3 and cur is not None:
            if y - cur >= 6:
                bands.append((cur + y - 1) // 2)
            cur = None
    print("[侧边栏行中心]", bands, flush=True)
    return bands


def make_temp_settings(scope_favorites=True):
    """写一份**临时** settings.json，让打包后的 exe 用它启动（v1.24.1）。

    为什么需要：反馈 4 要验的「画像概览统计范围选我的收藏」是个下拉项，靠 PostMessage
    在两个进程之间点下拉列表非常不可靠。改成预置偏好 —— 而预置偏好绝不能碰用户真实的
    `settings.json`，所以把真实配置**拷一份到临时目录**、改掉 `insight` 再通过
    `LMC_CONFIG` 环境变量指过去（见 `config.config_path()`）。数据库仍读真实索引。
    """
    src = os.path.join(ROOT, "settings.json")
    dst = os.path.join(os.path.dirname(LOG), "lmc_live_settings.json")
    try:
        with open(src, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[警告] 读不到 {src}（{e}），用空配置", flush=True)
        data = {}
    data["insight"] = {"scope": "", "favorites_only": bool(scope_favorites)}
    # v1.25.0（反馈 4）：标签优化页要真按一次「扫描并预览」+「执行写入」才算验过。
    # 写入目标是 %TEMP% 下的**夹具 nfo**，绝不碰用户真实媒体文件。
    fixdir = make_tagopt_fixture()
    data["tagopt"] = {"scope": "folder", "path": fixdir, "library": "",
                      "algo": "normal", "translate": True, "overwrite": False,
                      "complete": True, "backup": True}
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[临时配置] {dst} insight={data['insight']} tagopt={data['tagopt']}",
          flush=True)
    return dst


def make_tagopt_fixture():
    """在 %TEMP%/lmc_live_tagopt/fix 下造 3 个 nfo，供真机验收「标签优化」写入。

    刻意混入：① 日文标签（要能译成中文）② 技术标签 1080p（必须原样保留）
    ③ 片商 / 系列伪标签（要能从 nfo 推断出来）④ 中文标签（不该被动）。
    """
    import xml.etree.ElementTree as ET
    base = os.path.join(os.path.dirname(LOG), "lmc_live_tagopt", "fix")
    os.makedirs(base, exist_ok=True)
    rows = [
        ("ABC-001", "ABC-001 単体作品 巨乳 中出し", ["中出し", "巨乳", "単体作品", "1080p"],
         "冒烟社", "冒烟系列"),
        ("ABC-002", "ABC-002 潮吹き 痴女", ["潮吹き", "痴女", "720p"], "冒烟社", ""),
        ("ABC-003", "ABC-003 3P 顔射 巨乳", ["3P", "顔射", "巨乳", "1080p"], "试作社", ""),
    ]
    for code, title, genres, studio, series in rows:
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = title
        ET.SubElement(root, "plot").text = "真机验收夹具，可随时删除。"
        for g in genres:
            ET.SubElement(root, "genre").text = g
        ET.SubElement(root, "studio").text = studio
        if series:
            st = ET.SubElement(root, "set")
            ET.SubElement(st, "name").text = series
        ET.SubElement(root, "uniqueid", {"type": "tmdb", "default": "true"}).text = "70000"
        tree = ET.ElementTree(root)
        try:
            ET.indent(tree, space="  ")
        except Exception:
            pass
        tree.write(os.path.join(base, code + ".nfo"), encoding="utf-8",
                   xml_declaration=True)
    print(f"[夹具] {base} -> {len(rows)} 个 nfo", flush=True)
    return base


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    exe = newest_exe()
    exe_name = os.path.basename(exe).lower()
    pages = args or PAGES
    print("[EXE]", exe, flush=True)

    env = dict(os.environ)
    env["LMC_CONFIG"] = make_temp_settings()

    proc = subprocess.Popen([exe], close_fds=True, env=env)
    # 主窗口标题里带 "(Build …)"，用它把启动画面（标题只有软件名）区分开
    hwnd = find_window(exe_name, {proc.pid}, title_sub="Build")
    if not hwnd:
        print("[警告] 按标题没找到主窗口，回退到「最大可见窗口」", flush=True)
        hwnd = find_window(exe_name, {proc.pid})
    if not hwnd:
        print("[失败] 未发现主窗口", flush=True)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        return 1
    print(f"[窗口] hwnd={hwnd} pid={wpid(hwnd)} title={wtitle(hwnd)!r}", flush=True)

    u32.ShowWindow(hwnd, 9)
    u32.SetForegroundWindow(hwnd)
    time.sleep(2.5)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    os.makedirs(SHOT_DIR, exist_ok=True)
    home_png = os.path.join(SHOT_DIR, "17_live_window.png")
    grab(app, hwnd).save(home_png)
    print("[基准页]", home_png, flush=True)

    slug = {"全部": "grid", "最近播放": "recent", "演员库": "actors", "首页": "home",
            "文件夹": "folders", "智能推荐": "smart", "导演库": "directors",
            "合集": "collections"}
    # 注意：页面截图编号从 18 起连续（最多 5 页 → 18~22），工具窗口占 30 起，不撞号。
    for i, name in enumerate(pages, start=18):
        if name not in SIDEBAR:
            print(f"[跳过] 未知页面 {name}", flush=True)
            continue
        x, y = SIDEBAR[name]
        print(f"[点击] {name} @({x},{y})", flush=True)
        click(hwnd, x, y)
        time.sleep(4.0)
        out = os.path.join(SHOT_DIR, "%d_live_%s.png" % (i, slug.get(name, name)))
        pm = grab(app, hwnd)
        print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} {pm.save(out)}",
              flush=True)

    # ---------------- 工具窗口（v1.24.0 起「设置」改名「工具」）
    coords = load_coords()
    if coords:
        sx, sy = coords["main_settings_btn"]
        # 单击可能被上一拍的事件吞掉（v1.13.0 实测）→ 重试几次，每次之间给足反应时间
        dlg = None
        for attempt in range(3):
            print(f"[点击] 顶栏「工具」@({sx},{sy}) 第 {attempt + 1} 次", flush=True)
            u32.SetForegroundWindow(hwnd)
            click(hwnd, sx, sy)
            dlg = find_window_ex(exe_name, {proc.pid}, exclude={hwnd},
                                 title_sub="工具", timeout=8)
            if dlg:
                break
        if not dlg:
            print("[失败] 工具窗口没出来；主窗口 hwnd=%s pid=%s；当前 pid 集合=%s"
                  % (hwnd, wpid(hwnd), sorted(pids_of_exe(exe_name) | {proc.pid})),
                  flush=True)
            dump_windows(pids_of_exe(exe_name) | {proc.pid}, "工具点击失败现场")
        else:
            r = wt.RECT()
            u32.GetWindowRect(dlg, ctypes.byref(r))
            print(f"[工具窗口] hwnd={dlg} {r.right - r.left}x{r.bottom - r.top} "
                  f"title={wtitle(dlg)!r}", flush=True)
            time.sleep(2.5)
            out = os.path.join(SHOT_DIR, "30_live_tools_personal.png")
            pm = grab(app, dlg)
            print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                  f"{pm.save(out)}", flush=True)

            # v1.24.0：画像概览页真点一次「重新分析」—— insight 只是 hidden-import，
            # 打开页面 + 跑一遍才会真正 import 到它，漏打包就在这一步炸。
            # v1.24.1（反馈 4）：exe 是用**临时配置**启动的，其中 insight 预设成
            # 「★ 我的收藏」，所以进页面自动算出来的就是收藏范围 —— 截图即证据。
            dn = coords["dialog_nav"].get("画像概览")
            if dn:
                nx, ny = dn
                print(f"[点击] 工具·画像概览 @({nx},{ny})（统计范围预设为「我的收藏」）",
                      flush=True)
                click(dlg, nx, ny)
                time.sleep(6.0)          # 进页面会自动算一次，多等一会
                ib = coords.get("insight_run_btn")
                if ib:
                    print(f"[点击] 重新分析 @({ib[0]},{ib[1]})", flush=True)
                    click(dlg, ib[0], ib[1])
                    time.sleep(5.0)
                out = os.path.join(SHOT_DIR, "31_live_tools_insight.png")
                pm = grab(app, dlg)
                print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                      f"{pm.save(out)}", flush=True)

            # 智能推荐设置页 —— recommend 模块的唯一入口
            # v1.24.1（反馈 2）：顺便真点一次「检测本地 AI 引擎」，截图应拍到
            # **带时间戳的结论**（本机没装 Ollama → ⚠ 未检测到）。
            dn2 = coords["dialog_nav"].get("智能推荐")
            if dn2:
                nx, ny = dn2
                print(f"[点击] 工具·智能推荐 @({nx},{ny})", flush=True)
                click(dlg, nx, ny)
                time.sleep(2.0)
                out = os.path.join(SHOT_DIR, "32_live_tools_smart.png")
                pm = grab(app, dlg)
                print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                      f"{pm.save(out)}", flush=True)

                ai = coords.get("ai_test_btn")
                if ai:
                    ax, ay = ai
                    print(f"[点击] 检测本地 AI 引擎 @({ax},{ay})", flush=True)
                    click(dlg, ax, ay)
                    time.sleep(3.0)
                    out = os.path.join(SHOT_DIR, "32b_live_tools_ai_probe.png")
                    pm = grab(app, dlg)
                    print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                          f"{pm.save(out)}", flush=True)
                else:
                    print("[跳过] 坐标里没有 ai_test_btn", flush=True)

            # 标签优化（v1.25.0 反馈 4）：tagopt 只是 hidden-import，只有打开这一页
            # 并真的跑一次读写才会 import 到它 —— 漏打包就在这里炸。
            dn_to = coords["dialog_nav"].get("标签优化")
            if dn_to:
                nx, ny = dn_to
                print(f"[点击] 工具·标签优化 @({nx},{ny})", flush=True)
                click(dlg, nx, ny)
                time.sleep(2.5)
                out = os.path.join(SHOT_DIR, "36_live_tools_tagopt.png")
                pm = grab(app, dlg)
                print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                      f"{pm.save(out)}", flush=True)

                sb = coords.get("tagopt_scan_btn")
                if sb:
                    print(f"[点击] 扫描并预览 @({sb[0]},{sb[1]})", flush=True)
                    click(dlg, sb[0], sb[1])
                    time.sleep(6.0)
                    out = os.path.join(SHOT_DIR, "37_live_tools_tagopt_scan.png")
                    pm = grab(app, dlg)
                    print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                          f"{pm.save(out)}", flush=True)
                    rb = coords.get("tagopt_run_btn")
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
                            print(f"[确认框] 已确认={confirm_modal_yes(app, mb)}",
                                  flush=True)
                        else:
                            print("[警告] 没等到确认框；后续点击可能全部失效", flush=True)
                        time.sleep(9.0)
                        out = os.path.join(SHOT_DIR, "38_live_tools_tagopt_run.png")
                        pm = grab(app, dlg)
                        print(f"  [抓取] {pm.width()}x{pm.height()} -> "
                              f"{os.path.basename(out)} {pm.save(out)}", flush=True)
            else:
                print("[跳过] 坐标里没有「标签优化」页（ui_coords 需重跑）", flush=True)

            dn3 = coords["dialog_nav"].get("演员刮削")
            if dn3:
                nx, ny = dn3
                print(f"[点击] 工具·演员刮削 @({nx},{ny})", flush=True)
                click(dlg, nx, ny)
                time.sleep(2.0)
                out = os.path.join(SHOT_DIR, "33_live_tools_scraper.png")
                pm = grab(app, dlg)
                print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                      f"{pm.save(out)}", flush=True)

            # 重复检测：证明打包后的 exe 里 duplicates 模块真的可用
            # （它只是 hidden-import，打开页面才会 import，漏了就在这里炸）。
            dn4 = coords["dialog_nav"].get("重复检测")
            if dn4:
                nx, ny = dn4
                print(f"[点击] 工具·重复检测 @({nx},{ny})", flush=True)
                click(dlg, nx, ny)
                time.sleep(2.0)
                out = os.path.join(SHOT_DIR, "34_live_tools_dedupe.png")
                pm = grab(app, dlg)
                print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                      f"{pm.save(out)}", flush=True)
                # 真按一次「开始检测」，确认后台线程 + 失效行剪枝 + 结果树在打包版里跑得通。
                # 真机 4.8 万条要逐条 os.path.exists 校验，实测 ~880 条/秒 → 全量约 57 秒；
                # 等 12 秒只能截到 24%、55 秒才到 96%（v1.24.0 踩了两次），给足 85 秒。
                db_start = coords.get("dedupe_start_btn")
                if db_start:
                    bx, by = db_start
                    print(f"[点击] 开始检测 @({bx},{by})", flush=True)
                    click(dlg, bx, by)
                    time.sleep(85.0)
                    out = os.path.join(SHOT_DIR, "35_live_tools_dedupe_done.png")
                    pm = grab(app, dlg)
                    print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                          f"{pm.save(out)}", flush=True)

            u32.PostMessageW(dlg, WM_CLOSE, 0, 0)
            time.sleep(1.0)
            print("[工具窗口] 已关闭", flush=True)
    else:
        print("[跳过] 工具窗口验收", flush=True)

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    time.sleep(1.5)
    print("[结束] 残留同名进程:", sorted(pids_of_exe(exe_name)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
