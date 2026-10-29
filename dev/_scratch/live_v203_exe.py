# -*- coding: utf-8 -*-
"""v2.0.3（Build 2610290123）打包后真机验收 —— v2.0.2 六条反馈里「能像素自证」的部分。

v2.0.3 的第 7 条反馈（「收藏外不需要圆形」）**不在本脚本里验**：本机演示库只有
「演示路径」，海报墙上一张卡都没有，取不到卡片的稳定坐标。那条改动的取证在：
  冒烟 ㉙ 段（HAS_CIRCLE / 不透明像素比 / 圆内三点透明 / 星形柔影 / 悬停染色）
  预览图 docs/preview/v203_card_buttons.png、v203_btn_strip.png

一次启动（配置里 accent 直接给新粉 #e4587c，磨砂玻璃 / 低），按下面顺序取证：

  ① 侧栏仍是实色 (15,15,17)（v2.0.1 的回归项，玻璃模式下才测得出来）
  ② 侧栏点「最近播放」→ 那个 20px 大标题（用户截图里「最近播放 / 最近添加」）
     必须是**新粉**：v2.0.1 它是写死的 #66a9ff，该带量到 ~200 个蓝像素
  ③ 工具窗「个性化设置」：色卡里**有新粉、没有旧粉**；「窗口透明度 100%」是中性白
     （修前那个数字是 #66a9ff，量出来 96 个蓝像素）
  ④ 点「翡翠」换色 → 关掉工具窗**不再导航**直接抓主窗：同一页大标题变成翡翠绿
  ⑤ 工具窗 →「手动修改」：「检索并选择影片」是中性白、这一带没有蓝字
  ⑥ glyphs 三张 PNG 落盘 / 关窗 rc=0 / app.log 无「未捕获异常」

踩坑（沿用 v2.0.0 / v2.0.1 脚本，勿删）：
  · 工具窗刚 show 时控件没建完，grabWindow 会拿到 0×0 → 先等 2.6s
  · 点完导航有切页动画 → 必须回读导航高亮行确认，并留重试
  · 坐标是客户区坐标（dpi=96 / dpr=1.0）
  · ⚠ 首页（HomeListView）**没有**大标题，它顶部那排是「最近添加/我的收藏/合集」
    筛选 chip —— 拿它当「标题」量会受选中/悬停状态影响（实测两次跑一次 726 像素、
    一次 9 像素）。要验 #PageTitle 必须先进「最近播放」这种 `_page(title, …)` 页。
  · ⚠ 「100%」别拿「近白像素」找 —— 修前它是蓝的；改为在固定区域内数蓝 / 中性白。
  · ⚠ 白字压在 Primary（跟随高亮色）按钮上时，ClearType 次像素渲染会产出
    (71,228,231) 这类青色边缘 → 会被「蓝像素」判据误伤，取样区要避开按钮。
  · 色卡中心要**从截图里认**：选中态会被白环切开，按等距算会错位。
"""
import os
import sys
import json
import time
import ctypes
import shutil
import subprocess

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v203")
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
PINK = (228, 88, 124)
BUILD_TAG = "2610290123"
OLDPINK = (255, 127, 161)
JADE = "#17c964"


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
check("根目录最新的 exe 就是 v2.0.3（2610290123）",
      "v2.0.3" in os.path.basename(src) and "2610290123" in os.path.basename(src),
      os.path.basename(src))
# ⚠ 验收副本**必须另起一个 ASCII 名字**：程序启动时会调 `_kill_other_instances()`
# 杀掉所有**同名**进程（PyInstaller onefile 的父子两个都杀）。用原版名字跑验收，
# 会把「用户此刻正在用的那份」一起关掉 —— 实测用户手动打开 0122 时，
# 本脚本的验收实例反被对方杀掉，主窗抓图直接 0x0（8/11 假红，app.log 到 6 行戛然而止）。
# 换个名字双方互不干扰，版本号仍从 exe 内部的 title 核对。
exe = os.path.join(TEMP, "LMC-probe-%s.exe" % BUILD_TAG)
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)
EXE_NAME = os.path.basename(exe).lower()   # pids_of_exe 用 lower() 比对

LIBS = [
    {"name": "Javlibrary", "kind": "电影",
     "paths": ["D:/演示路径-%d" % i for i in range(14)], "filter": {}},
    {"name": "Jav-VR", "kind": "电影", "paths": ["D:/演示路径-vr"], "filter": {}},
]
cfg_path = os.path.join(TEMP, "settings.json")
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump({"libraries": LIBS,
               "appearance": {"accent": "#e4587c", "mode": "磨砂玻璃", "level": "低"}},
              f, ensure_ascii=False)

os.environ["LMC_CONFIG"] = cfg_path
IDX = os.path.join(TEMP, "index_data")
LOG = os.path.join(IDX, "logs", "app.log")


def accent():
    try:
        with open(cfg_path, encoding="utf-8") as f:
            return (json.load(f).get("appearance") or {}).get("accent")
    except Exception as e:
        return "err:%s" % e


COORDS = json.load(open(lv.COORDS, encoding="utf-8"))
TOOLS_BTN = tuple(COORDS["main_settings_btn"])
NAV_RECENT = (90, 160)          # 侧栏「最近播放」（`_page(title, …)` 页，标题是 #PageTitle）
NAV_APPEAR = (71, 63)
ROW_APPEAR = (46, 80)
NAV_MANUAL = (71, 141)
ROW_MANUAL = (124, 158)
NAV_SERVICE = (71, 102)
ROW_SERVICE = (85, 119)

app = QApplication.instance() or QApplication([])
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


def click_nav(h, xy, want_row, tries=3):
    im = None
    for i in range(tries):
        lv.click(h, xy[0], xy[1])
        for _ in range(10):
            time.sleep(0.35)
            im = shot(h, min_w=1200, tries=2, gap=0.3)
            if im is None:
                continue
            for a, b in nav_rows(im):
                if abs(a - want_row[0]) <= 6 and abs(b - want_row[1]) <= 6:
                    return im, "第%d次点击命中 %s" % (i + 1, (a, b))
    return im, "未命中 want=%s" % (want_row,)


def count_in(im, box, pred):
    x0, y0, x1, y1 = box
    px = im.load()
    n = 0
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            if pred(px[x, y]):
                n += 1
    return n


def near(c, t, tol):
    return all(abs(c[i] - t[i]) <= tol for i in range(3))


def is_blue(c):
    r, g, b = c
    return b > r + 40 and b > 150


def is_neutral_bright(c):
    r, g, b = c
    return r > 170 and g > 170 and b > 170 and abs(r - b) < 25 and abs(r - g) < 25


def is_pink(c):
    return near(c, PINK, 60)


def is_jade(c):
    r, g, b = c
    return g > r + 60 and g > b + 40 and g > 140


def dot_centers(im, y_lo=200, y_hi=340, x_lo=230, x_hi=700):
    """在「高亮色」那一带里认出色点的中心 x（合并被白环切开的碎片）。"""
    px = im.load()
    best = (None, [])
    for y in range(y_lo, y_hi):
        runs = []
        cur = None
        for x in range(x_lo, x_hi):
            r, g, b = px[x, y]
            sat = max(r, g, b) > 100 and (max(r, g, b) - min(r, g, b)) > 50
            if sat:
                if cur is None:
                    cur = [x, x]
                else:
                    cur[1] = x
            else:
                if cur:
                    runs.append(tuple(cur))
                    cur = None
        if cur:
            runs.append(tuple(cur))
        merged = []
        for a, b in runs:
            if merged and a - merged[-1][1] <= 8:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        if len(merged) > len(best[1]):
            best = (y, [(a + b) // 2 for a, b in merged])
    return best


# 20px 大标题实际落在 y≈72~90（实测），下面 y≥125 是「排序：名称 / 筛选」那排 chip：
# 它们是用 ClearType 次像素渲染的，会产出 (66,124,188)/(129,184,216) 这种**偏蓝**边缘，
# 会被「蓝像素」判据误伤（实测 46 个全在 y=125~129）→ 下边界收到 108，只框标题本体。
TITLE_BAND = (200, 50, 900, 108)

# ============================================================
p("========== v2.0.3 真机验收（accent=#e4587c / 磨砂玻璃·低） ==========")
subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
if os.path.isdir(IDX):
    for fn in os.listdir(IDX):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(IDX, fn))
_del(LOG)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=120, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)

if hwnd:
    title = lv.wtitle(hwnd)
    p("  title:", title)
    check("标题含 v2.0.3", "v2.0.3" in title, title)
    check("标题含构建号 2610290123", "2610290123" in title, title)
    time.sleep(6)
    check("启动后不处于「未响应」", not bool(ctypes.windll.user32.IsHungAppWindow(hwnd)))

    im = shot(hwnd, min_w=1500)
    if im is None:
        check("主窗可抓图", False)
    else:
        im.save(os.path.join(SHOTS, "v203_exe_home_pink.png"))
        check("主窗可抓图（非空白）", True, im.size)
        px = im.load()
        col = []
        for y in range(150, min(950, im.height)):
            for x in (2, 3, 4):
                col.append(px[x, y])
        col.sort()
        mid = col[len(col) // 2]
        check("侧栏底色仍是实色 (15,15,17)",
              abs(mid[0] - 15) <= 3 and abs(mid[1] - 15) <= 3 and abs(mid[2] - 17) <= 3,
              "median=%s" % (mid,))

        # ② 进「最近播放」页 —— 那里的 20px 标题才是 #PageTitle
        lv.click(hwnd, NAV_RECENT[0], NAV_RECENT[1])
        time.sleep(1.8)
        im_t = shot(hwnd, min_w=1500, tries=10)
        check("切到「最近播放」页并抓到图", im_t is not None)
        if im_t is not None:
            im_t.save(os.path.join(SHOTS, "v203_exe_title_pink.png"))
            n_pink = count_in(im_t, TITLE_BAND, is_pink)
            n_blue = count_in(im_t, TITLE_BAND, is_blue)
            check("大标题是**新粉**（≥150 个粉像素）", n_pink >= 150, n_pink)
            check("大标题里没有蓝像素（修前它是写死的 #66a9ff）", n_blue == 0, n_blue)

    # ③ glyphs 打包后仍能落盘
    gd = os.path.join(IDX, "ui_glyphs")
    have = sorted(os.listdir(gd)) if os.path.isdir(gd) else []
    p("  glyphs:", have)
    check("index_data/ui_glyphs 里有 3 个小图标",
          len([f for f in have if os.path.getsize(os.path.join(gd, f)) > 100]) >= 3, have)

    # ---- 工具窗 → 个性化设置 ----
    lv.click(hwnd, TOOLS_BTN[0], TOOLS_BTN[1])
    dlg = lv.find_window_ex(EXE_NAME, [proc.pid], exclude=(hwnd,), timeout=25,
                            title_sub="工具")
    check("工具窗已打开", dlg is not None, dlg)
    if dlg:
        time.sleep(2.6)
        im, why = click_nav(dlg, NAV_APPEAR, ROW_APPEAR)
        check("切到「个性化设置」（按导航高亮行核对）", im is not None
              and any(abs(a - ROW_APPEAR[0]) <= 6 for a, b in nav_rows(im)), why)
        dots_y, dots = (None, [])
        if im is not None:
            im.save(os.path.join(SHOTS, "v203_exe_appearance.png"))
            dots_y, dots = dot_centers(im)
            p("  色卡行 y=%s 中心=" % dots_y, dots)
            check("认出 ≥9 个饱和色点（12 色里前 10 个是饱和的）", len(dots) >= 9, len(dots))
            row_box = (235, dots_y - 8, 600, dots_y + 9) if dots_y else (235, 250, 600, 272)
            n_new = count_in(im, row_box, lambda c: near(c, PINK, 26))
            n_old = count_in(im, row_box, lambda c: near(c, OLDPINK, 18))
            check("色卡里出现新粉 #e4587c（≥40 像素）", n_new >= 40, n_new)
            check("色卡里已经没有旧粉 #ff7fa1（≤5 像素）", n_old <= 5, n_old)

            obox = (1226, 210, 1320, 242)
            n_blue = count_in(im, obox, is_blue)
            n_white = count_in(im, obox, is_neutral_bright)
            check("「窗口透明度 100%」是中性白（≥30 像素）", n_white >= 30, n_white)
            check("「窗口透明度 100%」不再是蓝色（修前 96 个）", n_blue == 0, n_blue)

        # ④ 点「翡翠」→ 关掉工具窗**不重新导航**，大标题应已变色
        if len(dots) >= 4 and dots_y:
            jade_x, jade_y = dots[3], dots_y
            p("  点翡翠 @", (jade_x, jade_y))
            hit = False
            for _i in range(3):
                lv.click(dlg, jade_x, jade_y)
                for _ in range(12):
                    time.sleep(0.3)
                    if proc.poll() is not None:
                        break
                    if str(accent()).lower() == JADE:
                        hit = True
                        break
                if hit or proc.poll() is not None:
                    break
            check("点「翡翠」后 accent 变成 #17c964", hit, accent())
            check("换色后进程仍活着", proc.poll() is None, proc.poll())
            time.sleep(1.6)

            # ⑤ 手动修改页：标题要是中性白（修前是写死蓝）
            im3, why3 = click_nav(dlg, NAV_MANUAL, ROW_MANUAL)
            check("切到「手动修改」", im3 is not None
                  and any(abs(a - ROW_MANUAL[0]) <= 6 for a, b in nav_rows(im3)), why3)
            if im3 is not None:
                im3.save(os.path.join(SHOTS, "v203_exe_manual_title.png"))
                # 右边界避开「搜索」按钮：白字压在 Primary 上会有 ClearType 青色边缘
                tband = (175, 40, 370, 110)
                n_blue3 = count_in(im3, tband, is_blue)
                n_white3 = count_in(im3, tband, is_neutral_bright)
                check("「检索并选择影片」是中性白（≥40 像素）", n_white3 >= 40, n_white3)
                check("这一带的标题不再是蓝色（修前 #66a9ff）", n_blue3 == 0, n_blue3)

            im4, why4 = click_nav(dlg, NAV_SERVICE, ROW_SERVICE)
            check("切到「服务管理」", im4 is not None, why4)
            check("连切三页后工具窗仍响应",
                  not bool(ctypes.windll.user32.IsHungAppWindow(dlg)))

        lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
        time.sleep(1.4)

    # ④' 关掉工具窗，**不点任何导航**直接抓主窗
    im5 = shot(hwnd, min_w=1500, tries=10)
    check("换色后主窗仍能抓图", im5 is not None)
    if im5 is not None:
        im5.save(os.path.join(SHOTS, "v203_exe_title_jade.png"))
        n_jade = count_in(im5, TITLE_BAND, is_jade)
        n_pink = count_in(im5, TITLE_BAND, is_pink)
        check("改主题色后同一个大标题变成翡翠绿（不用重新导航）", n_jade >= 150, n_jade)
        check("大标题不再是旧粉（说明真重绘了）", n_pink == 0, n_pink)

    try:
        lv.u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < 25 and proc.poll() is None:
        time.sleep(0.3)
    rc = proc.poll()
    if proc.poll() is None:
        proc.kill()
    check("关窗后正常退出（rc=0）", rc == 0, rc)

    bad = []
    if os.path.exists(LOG):
        txt = open(LOG, encoding="utf-8", errors="replace").read()
        bad = [k for k in ("未捕获异常", "Traceback", "QThread: Destroyed",
                           "生成界面小图标") if k in txt]
        p("  app.log 行数:", len(txt.splitlines()))
    check("app.log 无未捕获异常 / 无图标生成失败", not bad, bad)

p("FAILS:", FAILS)
p("通过 %d/%d" % (len(OKS), len(OKS) + len(FAILS)))
p("LIVE_V203_ALL_OK" if not FAILS else "LIVE_V203_HAS_FAIL")
