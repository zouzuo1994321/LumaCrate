# -*- coding: utf-8 -*-
"""v2.0.0（Build 2610290119）打包后真机验收 —— 验「整代 UI 换血」没把功能弄坏。

v1 那套 live 脚本只验「起得来 / 日志干净」就够了（改动是局部的）；本版动的是
**全局组件套件 + 高亮色令牌链**，所以真机必须走这条完整链路：

  ① 主窗照常起、标题带新版本号；抓图留证（中性暗色 + 高亮蓝）。
  ② 「工具 → 个性化设置」真的切到那一页（**用导航高亮行反查**，不靠「点完就当成了」），
     并确认页面上真有那一排彩色圆点（在内容区数高饱和像素）。
  ③ **真点一次色卡换色**（玫红 #f31260）：settings.json 里的 accent 必须真的变成它 ——
     这条同时验了「点击 → _apply_accent → render_style 令牌替换 → 落盘 → 重绘」整条链。
  ④ 换色会走 `_apply_settings()` → **重建侧栏**，正是 v1.27.0 崩过的路径
     （采集线程挂在会被 deleteLater 的侧栏下 → QThread: Destroyed while running → abort），
     所以换完色必须断言进程还活着、还能再抓出非空白图。
  ⑤ 「服务管理」：v1.46.15 压过的列表行高不许回归。
  ⑥ 关窗 rc=0；app.log 无未捕获异常 / QThread 销毁警告。

踩过的坑（本脚本已规避）：
  · 工具窗刚 show 时控件还没建完，grabWindow 会拿到 0×0；太早点导航还会把整个程序关掉
    → 开窗后必须等 >= 2.4s。
  · 点完导航**页面切换是有动画的**，立刻抓图会抓到上一页 → 每次点完都回读导航高亮行确认。
  · 坐标是**客户区**坐标（dpi=96、dpr=1.0，实测 1:1，不需要乘缩放）。
"""
import os
import sys
import json
import time
import ctypes
import ctypes.wintypes
import shutil
import subprocess

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v200")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication
from PIL import Image

os.makedirs(SHOTS, exist_ok=True)
FAILS, OKS = [], []
T0 = time.time()


def p(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    p(("  OK   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if detail else ""))


def _del(pth):
    if os.path.exists(pth):
        ctypes.windll.kernel32.SetFileAttributesW(pth, 0x80)
        ctypes.windll.kernel32.DeleteFileW(pth)


os.makedirs(TEMP, exist_ok=True)
src = lv.newest_exe()
p("新 exe:", src)
assert src and os.path.exists(src)
check("根目录最新的 exe 就是 v2.0.0（2610290119）",
      "v2.0.0" in os.path.basename(src) and "2610290119" in os.path.basename(src),
      os.path.basename(src))
exe = os.path.join(TEMP, os.path.basename(src))
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)

LIBS = [
    {"name": "Javlibrary", "kind": "电影",
     "paths": ["D:/演示路径-%d" % i for i in range(14)], "filter": {}},
    {"name": "Jav-VR", "kind": "电影", "paths": ["D:/演示路径-vr"], "filter": {}},
    {"name": "Jav-临时", "kind": "混合", "paths": ["D:/演示路径-tmp"], "filter": {}},
]
cfg_path = os.path.join(TEMP, "settings.json")
# 故意写 v1 时代的旧高亮色：真机顺带验「老配置载入后迁到新色板」
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump({"libraries": LIBS, "appearance": {"accent": "#c0392b"}},
              f, ensure_ascii=False)
os.environ["LMC_CONFIG"] = cfg_path

idx = os.path.join(TEMP, "index_data")
if os.path.isdir(idx):
    for fn in os.listdir(idx):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(idx, fn))
_log = os.path.join(idx, "logs", "app.log")
_del(_log)


def accent():
    try:
        with open(cfg_path, encoding="utf-8") as f:
            return (json.load(f).get("appearance") or {}).get("accent")
    except Exception as e:
        return "err:%s" % e


COORDS = json.load(open(lv.COORDS, encoding="utf-8"))
TOOLS_BTN = tuple(COORDS["main_settings_btn"])
# 客户区坐标：来自 dev/_scratch/probe_v200_coords.py（离屏 mapTo(dlg)），已真机校准
NAV_APPEAR = (71, 63)         # 个性化设置 客户区 rect (8,46,128,35)
NAV_SERVICE = (71, 102)       # 服务管理   客户区 rect (8,85,128,35)
SWATCH_JADE = (356, 247)      # 翡翠 #17c964 客户区 rect (343,234,28,28)
ROW_APPEAR = (46, 80)
ROW_SERVICE = (85, 119)
p("坐标：工具", TOOLS_BTN, "个性化设置", NAV_APPEAR, "服务管理", NAV_SERVICE,
  "翡翠色卡", SWATCH_JADE)

exe_name = os.path.basename(exe)
subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)

app = QApplication.instance() or QApplication([])
hwnd = lv.find_window(exe_name, [proc.pid], timeout=120, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)

TMPPNG = os.path.join(TEMP, "_shot.png")


def shot(h, min_w=1000, tries=8, gap=0.5):
    pm = None
    for _ in range(tries):
        pm = app.primaryScreen().grabWindow(h)
        if pm is not None and pm.width() >= min_w:
            break
        time.sleep(gap)
        app.processEvents()
    if pm is None or pm.width() < min_w:
        return None
    pm.save(TMPPNG, "PNG")
    return Image.open(TMPPNG).convert("RGB")


def nav_rows(im):
    """导航列 x∈[12,130] 里比中位亮度高 4 以上的连续行 → 高亮菜单项。"""
    px = im.load()
    means = []
    for y in range(im.height):
        s = 0
        for x in range(12, 130, 2):
            r, g, b = px[x, y]
            s += (r + g + b) / 3.0
        means.append(s / 59.0)
    base = sorted(means)[len(means) // 2]
    runs = []
    for y, v in enumerate(means):
        if v > base + 4.0:
            if runs and y - runs[-1][1] <= 2:
                runs[-1][1] = y
            else:
                runs.append([y, y])
    return [(a, b) for a, b in runs if b - a >= 12]


def has_swatch_row(im):
    """内容区 y∈[228,268] x∈[236,600] 里数高饱和像素（11 个正圆色点）。"""
    px = im.load()
    n = 0
    for y in range(228, min(268, im.height)):
        for x in range(236, min(600, im.width)):
            r, g, b = px[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            if mx > 90 and mx - mn > 70:
                n += 1
    return n


def mean_rgb(im, box):
    """区域里**高饱和像素**的平均色（背景/文字都是灰的，会被过滤掉）。

    开关轨道是实心高亮色，所以这个均值就等于「当前高亮色」——
    用它判「换色后界面有没有真重绘」比找具体像素稳。
    """
    x0, y0, x1, y1 = box
    n = r = g = b = 0
    px = im.load()
    for y in range(y0, min(y1, im.height)):
        for x in range(x0, min(x1, im.width)):
            _r, _g, _b = px[x, y]
            mx, mn = max(_r, _g, _b), min(_r, _g, _b)
            if mx > 70 and mx - mn > 50:
                r += _r; g += _g; b += _b; n += 1
    if not n:
        return (0, 0, 0, 0)
    return (r // n, g // n, b // n, n)

def click_nav(h, xy, want_row, tries=3):
    """点导航 → 回读高亮行确认页面真切过去了（页面切换有动画，不能点完就抓）。"""
    for i in range(tries):
        lv.click(h, xy[0], xy[1])
        for _ in range(10):
            time.sleep(0.35)
            if proc.poll() is not None:
                return None, "进程已退出"
            im = shot(h, min_w=1200, tries=2, gap=0.3)
            if im is None:
                continue
            rows = nav_rows(im)
            for a, b in rows:
                if abs(a - want_row[0]) <= 6 and abs(b - want_row[1]) <= 6:
                    return im, "第%d次点击命中 %s" % (i + 1, (a, b))
    return im, "未命中 want=%s got=%s" % (want_row, rows if im is not None else None)


if hwnd:
    title = lv.wtitle(hwnd)
    p("  title:", title)
    check("标题含新版本号 v2.0.0", "v2.0.0" in title, title)
    check("标题含新构建号 2610290119", "2610290119" in title, title)
    time.sleep(6)
    check("启动后不处于「未响应」",
          not bool(ctypes.windll.user32.IsHungAppWindow(hwnd)))
    pm = app.primaryScreen().grabWindow(hwnd)
    ok = pm.width() > 1000 and pm.save(os.path.join(SHOTS, "v200_exe_main.png"), "PNG")
    check("主窗可抓图（非空白）", bool(ok), (pm.width(), pm.height()))
    # 老配置 #c0392b 载入后必须已迁成新版玫红
    check("老配置 accent=#c0392b 载入后迁成 #f31260", accent() == "#f31260", accent())

    # ---- 工具窗 → 个性化设置 ----
    lv.click(hwnd, TOOLS_BTN[0], TOOLS_BTN[1])
    dlg = lv.find_window_ex(exe_name, [proc.pid], exclude=(hwnd,), timeout=25,
                            title_sub="工具")
    check("工具窗已打开（标题含「工具」）", dlg is not None, dlg)
    if dlg:
        time.sleep(2.6)
        _r = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(dlg, ctypes.byref(_r))
        _w, _h = _r.right - _r.left, _r.bottom - _r.top
        check("工具窗尺寸接近 1320×960", _w >= 1200 and _h >= 800, (_w, _h))

        im, why = click_nav(dlg, NAV_APPEAR, ROW_APPEAR)
        check("切到「个性化设置」（按导航高亮行核对）", im is not None
              and any(abs(a - ROW_APPEAR[0]) <= 6 for a, b in nav_rows(im)), why)
        n_dot = has_swatch_row(im) if im is not None else -1
        check("页面上真有那一排彩色圆点（内容区高饱和像素 > 200）", n_dot > 200, n_dot)
        if im is not None:
            im.save(os.path.join(SHOTS, "v200_exe_appearance.png"))
        check("该页进程仍活着", proc.poll() is None, proc.poll())

        # ---- 点玫红色卡换色（会走 _apply_settings → 重建侧栏）----
        _before = accent()
        # 起始色是迁移后的玫红 #f31260 → **必须点一个不同的**，否则「点前=点后」测不出真假
        check("点色卡前的高亮色不是翡翠（否则这条断言测不出东西）",
              str(_before).lower() != "#17c964", _before)
        hit = False
        for _i in range(3):
            lv.click(dlg, SWATCH_JADE[0], SWATCH_JADE[1])
            for _ in range(12):
                time.sleep(0.3)
                if proc.poll() is not None:
                    break
                if str(accent()).lower() == "#17c964":
                    hit = True
                    break
            if hit or proc.poll() is not None:
                break
            # 没生效 → 可能页面动画还没停，重新确认页面再点
            click_nav(dlg, NAV_APPEAR, ROW_APPEAR)
        check("点「翡翠」色卡后 settings.json 的 accent 从 %s 变成 #17c964" % _before,
              str(accent()).lower() == "#17c964", "%s (点击前 %s)" % (accent(), _before))
        check("换色后进程仍活着（v1.27.0 的 QThread 销毁崩退没有复发）",
              proc.poll() is None, proc.poll())
        # 生效设置 → 重载样式表 → 重建侧栏/各页是**异步**的（settings.json 先落盘），
        # 必须等重绘完再抓，否则会抓到还挂着旧色的那一帧（本轮真踩到）。
        TOGGLE_BOX = (1210, 236, 1284, 380)     # 「外观」卡片右侧那几个开关的轨道
        time.sleep(2.2)
        im2 = shot(dlg, min_w=1200, tries=10)
        ok2 = im2 is not None
        if ok2:
            im2.save(os.path.join(SHOTS, "v200_exe_accent_jade.png"))
        check("换色后工具窗仍能抓出非空白图", ok2,
              im2.size if im2 is not None else None)
        check("换色后圆点仍画得出来（色卡没被新令牌搞坏）",
              ok2 and has_swatch_row(im2) > 200, has_swatch_row(im2) if ok2 else -1)
        if ok2:
            _mr, _mg, _mb, _n = mean_rgb(im2, TOGGLE_BOX)
            check("换色后界面真的重绘了（开关轨道已是翡翠绿：g 远大于 r/b）",
                  _n > 500 and _mg > _mr + 60 and _mg > _mb + 40,
                  "mean=(%d,%d,%d) n=%d" % (_mr, _mg, _mb, _n))

        # ---- 服务管理：v1.46.15 的列表行高不许回归 ----
        im3, why3 = click_nav(dlg, NAV_SERVICE, ROW_SERVICE)
        check("切到「服务管理」（按导航高亮行核对）", im3 is not None
              and any(abs(a - ROW_SERVICE[0]) <= 6 for a, b in nav_rows(im3)), why3)
        if im3 is not None:
            im3.save(os.path.join(SHOTS, "v200_exe_service.png"))
        check("切到服务管理后进程仍活着", proc.poll() is None, proc.poll())
        check("工具窗仍活着（连切三页没崩）",
              not bool(ctypes.windll.user32.IsHungAppWindow(dlg)))
        lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
        time.sleep(1.2)

    check("进程仍在运行（没有崩退）", proc.poll() is None, proc.poll())
    lv.u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
    t0 = time.time()
    while time.time() - t0 < 25 and proc.poll() is None:
        time.sleep(0.3)
    check("关窗后正常退出（rc=0）", proc.poll() == 0, proc.poll())
    if proc.poll() is None:
        proc.kill()

bad = []
if os.path.exists(_log):
    txt = open(_log, encoding="utf-8", errors="replace").read()
    bad = [k for k in ("未捕获异常", "Traceback", "QThread: Destroyed", "Fatal") if k in txt]
    p("  app.log 行数:", len(txt.splitlines()))
    check("app.log 里不再出现旧高亮色 #c0392b", "#c0392b" not in txt.lower())
check("app.log 无未捕获异常 / Traceback / QThread 销毁", not bad, bad)

p("FAILS:", FAILS)
p("通过 %d/%d" % (len(OKS), len(OKS) + len(FAILS)))
p("LIVE_V200_ALL_OK" if not FAILS else "LIVE_V200_HAS_FAIL")
