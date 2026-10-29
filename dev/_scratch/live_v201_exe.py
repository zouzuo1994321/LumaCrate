# -*- coding: utf-8 -*-
"""v2.0.1（Build 2610290120）打包后真机验收 —— 7 条反馈里「能像素自证」的部分。

两个阶段（各起一次 exe，配置不同）：

  A 阶段（磨砂玻璃 / 浓度「低」）—— 玻璃与侧栏的关系只有在这个模式下才看得出来
    · 侧栏必须是不透明实色 (15,15,17)：半透明时会被模糊底衬染色，读数一定偏离
    · `index_data/ui_glyphs/` 里必须有 3 个 PNG（证明「QImage 画图 → 落盘 → QSS url()」
      这条链在**打包后**也通：PNG 走 imageformats 插件，缺插件就只能退 BMP）
    · 「外观」页上一排色卡仍有高饱和像素（12 色）
    · 白圆直径 ≥ 16（修前实测 15 —— 18px 把手被 15px 高的控件切平）
    · 换色链路（点翡翠）与连切三页不崩，沿用 v2.0.0 的回归项
  B 阶段（经典暗色）—— 直角只能在不透明背景上量
    · 首页右面板边框：竖直边最上端 y0 与水平边所在行 yt 必须几乎相等
      （圆角 14px 时 yt = y0 - 14，一眼可分）

踩坑（沿用 v2.0.0 脚本，勿删）：工具窗刚 show 时控件没建完，grabWindow 会拿到 0×0；
点完导航有切页动画，必须回读导航高亮行；坐标是客户区坐标（dpi=96 / dpr=1.0）。
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
                    "lmc_exe_v201")
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
check("根目录最新的 exe 就是 v2.0.1（2610290120）",
      "v2.0.1" in os.path.basename(src) and "2610290120" in os.path.basename(src),
      os.path.basename(src))
exe = os.path.join(TEMP, os.path.basename(src))
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)
EXE_NAME = os.path.basename(exe)

LIBS = [
    {"name": "Javlibrary", "kind": "电影",
     "paths": ["D:/演示路径-%d" % i for i in range(14)], "filter": {}},
    {"name": "Jav-VR", "kind": "电影", "paths": ["D:/演示路径-vr"], "filter": {}},
    {"name": "Jav-临时", "kind": "混合", "paths": ["D:/演示路径-tmp"], "filter": {}},
]
cfg_path = os.path.join(TEMP, "settings.json")


def write_cfg(mode, level, accent="#006fee"):
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({"libraries": LIBS,
                   "appearance": {"accent": accent, "mode": mode, "level": level}},
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
NAV_APPEAR = (71, 63)
NAV_SERVICE = (71, 102)
SWATCH_JADE = (356, 247)
ROW_APPEAR = (46, 80)
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


def launch(tag):
    write_cfg(*tag[0:2])
    if os.path.isdir(IDX):
        for fn in os.listdir(IDX):
            if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
                _del(os.path.join(IDX, fn))
    _del(LOG)
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
    p("已启动(%s) pid=" % tag[2], proc.pid)
    hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=120, title_sub="Build")
    return proc, hwnd


def close(proc, hwnd):
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
    return rc


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


def saturated(im, box):
    x0, y0, x1, y1 = box
    px = im.load()
    n = 0
    for y in range(y0, min(y1, im.height)):
        for x in range(x0, min(x1, im.width)):
            r, g, b = px[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            if mx > 90 and mx - mn > 70:
                n += 1
    return n


def mean_rgb(im, box):
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


def white_discs(im, box):
    """区域内「实心白圆」的直径列表（连通域 + 填充率过滤）。

    判据：近白像素连通块、外接框 12~30、填充率 ≥ 0.5（一圈白环/一行文字都过不了）。
    """
    x0, y0, x1, y1 = box
    W, H = min(x1, im.width) - x0, min(y1, im.height) - y0
    px = im.load()
    white = [[False] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            r, g, b = px[x + x0, y + y0]
            if r > 232 and g > 232 and b > 232:
                white[y][x] = True
    seen = [[False] * W for _ in range(H)]
    out = []
    for sy in range(H):
        for sx in range(W):
            if not white[sy][sx] or seen[sy][sx]:
                continue
            stack = [(sx, sy)]
            seen[sy][sx] = True
            pix = []
            while stack:
                cx, cy = stack.pop()
                pix.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                               (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < W and 0 <= ny < H and white[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            xs = [q[0] for q in pix]
            ys = [q[1] for q in pix]
            w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            if 12 <= w <= 30 and 12 <= h <= 30 and len(pix) / float(w * h) >= 0.5:
                out.append((min(w, h), w, h, len(pix), min(xs) + x0, min(ys) + y0))
    return sorted(out, reverse=True)


# ============================================================
p("========== A 阶段：磨砂玻璃 / 浓度低 ==========")
proc, hwnd = launch(("磨砂玻璃", "低", "A"))
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)
if hwnd:
    title = lv.wtitle(hwnd)
    p("  title:", title)
    check("标题含新版本号 v2.0.1", "v2.0.1" in title, title)
    check("标题含新构建号 2610290120", "2610290120" in title, title)
    time.sleep(6)
    check("启动后不处于「未响应」", not bool(ctypes.windll.user32.IsHungAppWindow(hwnd)))

    # ---- ⑥ 侧栏必须是不透明实色（玻璃模式下的关键读数）----
    im = shot(hwnd, min_w=1500)
    if im is None:
        check("主窗可抓图", False)
    else:
        im.save(os.path.join(SHOTS, "v201_exe_glass_main.png"))
        check("主窗可抓图（非空白）", True, im.size)
        px = im.load()
        col = []
        for y in range(150, min(950, im.height)):
            for x in (2, 3, 4):
                col.append(px[x, y])
        col.sort()
        mid = col[len(col) // 2]
        check("侧栏底色 = 实色 (15,15,17)（吃了半透明就会被模糊底衬染色）",
              abs(mid[0] - 15) <= 3 and abs(mid[1] - 15) <= 3 and abs(mid[2] - 17) <= 3,
              "median=%s  采样 %d 点" % (mid, len(col)))
        # 前提：这一轮真的是磨砂玻璃模式 —— 否则 __PANEL__ = 255，上面那条读数恒真、
        # 测不出任何东西。空媒体库时底衬只有 #0a0a0b + 两团柔光，靠「内容区是否更亮」
        # 判玻璃是判不出来的（试过，18/75 采样点超阈值，纯噪声）。
        try:
            _ap = json.load(open(cfg_path, encoding="utf-8")).get("appearance") or {}
        except Exception:
            _ap = {}
        check("本轮配置是「磨砂玻璃 / 低」（侧栏那条约等于在此前提下才有意义）",
              _ap.get("mode") == "磨砂玻璃" and _ap.get("level") == "低", _ap)

    # ---- ② ③ glyphs 在打包后能落盘 ----
    gd = os.path.join(IDX, "ui_glyphs")
    have = sorted(os.listdir(gd)) if os.path.isdir(gd) else []
    p("  glyphs:", have)
    check("exe 启动后在 index_data/ui_glyphs 生成了 3 个小图标",
          len(have) >= 3 and all(os.path.getsize(os.path.join(gd, f)) > 100 for f in have),
          [(f, os.path.getsize(os.path.join(gd, f))) for f in have])
    check("三个文件名对得上（箭头上下 + 勾）",
          any("arrow_up" in f for f in have) and any("arrow_down" in f for f in have)
          and any("check" in f for f in have), have)

    # ---- 工具窗 → 个性化设置：色卡 + 滑块白圆 ----
    lv.click(hwnd, TOOLS_BTN[0], TOOLS_BTN[1])
    dlg = lv.find_window_ex(EXE_NAME, [proc.pid], exclude=(hwnd,), timeout=25,
                            title_sub="工具")
    check("工具窗已打开（标题含「工具」）", dlg is not None, dlg)
    if dlg:
        time.sleep(2.6)
        im, why = click_nav(dlg, NAV_APPEAR, ROW_APPEAR)
        check("切到「个性化设置」（按导航高亮行核对）", im is not None
              and any(abs(a - ROW_APPEAR[0]) <= 6 for a, b in nav_rows(im)), why)
        if im is not None:
            im.save(os.path.join(SHOTS, "v201_exe_appearance.png"))
            n_dot = saturated(im, (220, 218, 900, 272))
            check("色卡一排仍有成片高饱和像素（12 色）", n_dot > 200, n_dot)
            discs = white_discs(im, (160, 150, 1300, 500))
            p("  白圆:", discs[:4])
            if discs:
                # ⚠ 不能取「最大的」：开关轨道上的白圆是 20px，恒比滑块把手(18)大，
                # 取最大就永远量到开关、这条断言就废了。滑块那一行在页面最上面
                # （y≈217），三个开关在 y≈290/326/362 —— 取**最靠上**的那个才是把手。
                d0 = sorted(discs, key=lambda d: d[5])[0]
                check("滑块把手直径 ≥ 16 且不窄于 17（修前实测 17×15 —— 上下被切）",
                      d0[0] >= 16 and d0[1] >= 17,
                      "w=%d h=%d (%d px) @(%d,%d)" % (d0[1], d0[2], d0[3], d0[4], d0[5]))
                # 被切平的圆：首行比末行宽（修前 10 vs 4）；完整的圆上下对称（4 vs 4）
                px0 = im.load()
                y_t, y_b = d0[5], d0[5] + d0[2] - 1
                n_t = sum(1 for x in range(d0[4], d0[4] + d0[1])
                          if all(c > 232 for c in px0[x, y_t]))
                n_b = sum(1 for x in range(d0[4], d0[4] + d0[1])
                          if all(c > 232 for c in px0[x, y_b]))
                check("把手上下对称（首行/末行白像素数接近 —— 被切平的首行会明显更宽）",
                      max(n_t, n_b) > 0 and min(n_t, n_b) / float(max(n_t, n_b)) >= 0.5,
                      "首行 %d / 末行 %d" % (n_t, n_b))
            else:
                check("滑块把手直径 ≥ 16 且不窄于 17（修前实测 17×15 —— 上下被切）",
                      False, "没找到任何实心白圆")

        # 换色链路（回归）
        _before = accent()
        check("点色卡前不是翡翠（否则测不出真假）", str(_before).lower() != "#17c964", _before)
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
            click_nav(dlg, NAV_APPEAR, ROW_APPEAR)
        check("点「翡翠」后 accent 从 %s 变成 #17c964" % _before, hit, accent())
        check("换色后进程仍活着（QThread 销毁崩退未复发）", proc.poll() is None, proc.poll())
        time.sleep(2.2)
        im2 = shot(dlg, min_w=1200, tries=10)
        check("换色后工具窗仍能抓出非空白图", im2 is not None)
        if im2 is not None:
            im2.save(os.path.join(SHOTS, "v201_exe_accent_jade.png"))
            _mr, _mg, _mb, _n = mean_rgb(im2, (1210, 236, 1284, 380))
            check("界面真的重绘了（开关轨道已变翡翠绿）",
                  _n > 500 and _mg > _mr + 60 and _mg > _mb + 40,
                  "mean=(%d,%d,%d) n=%d" % (_mr, _mg, _mb, _n))
        im3, why3 = click_nav(dlg, NAV_SERVICE, ROW_SERVICE)
        check("切到「服务管理」", im3 is not None, why3)
        check("连切三页后工具窗仍响应",
              not bool(ctypes.windll.user32.IsHungAppWindow(dlg)))
        lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
        time.sleep(1.2)

    rc = close(proc, hwnd)
    check("A 阶段关窗后正常退出（rc=0）", rc == 0, rc)
    bad = []
    if os.path.exists(LOG):
        txt = open(LOG, encoding="utf-8", errors="replace").read()
        bad = [k for k in ("未捕获异常", "Traceback", "QThread: Destroyed",
                           "生成界面小图标") if k in txt]
        p("  app.log 行数:", len(txt.splitlines()))
    check("A 阶段 app.log 无异常 / 无「生成小图标失败」", not bad, bad)

# ============================================================
p("========== B 阶段：经典暗色 / 首页面板直角 ==========")
proc, hwnd = launch(("经典暗色", "中", "B"))
check("主窗口再次出现", hwnd is not None, hwnd)
if hwnd:
    time.sleep(6)
    im = shot(hwnd, min_w=1500)
    check("B 阶段可抓图", im is not None, im.size if im is not None else None)
    if im is not None:
        im.save(os.path.join(SHOTS, "v201_exe_home_square.png"))
        px = im.load()
        W, H = im.size

        def bluish(x, y):
            r, g, b = px[x, y]
            return b > r + 30 and b > 55

        # 1) 在 y=400 这一横线上找 DetailHost 的**左边框**（右侧那块的竖边）
        xb, yb = None, 400
        for x in range(W // 2, W - 20):
            if bluish(x, yb) and not bluish(x - 3, yb) and not bluish(x + 3, yb):
                xb = x
                break
        check("首页右侧详情面板的竖边框可定位", xb is not None, xb)
        if xb:
            # 2) 竖直边的最高点
            y0 = None
            for y in range(60, yb):
                if bluish(xb, y):
                    y0 = y
                    break
            # 3) 水平边所在行：在 y∈[40,140] 里数 x∈[xb, xb+200] 的蓝像素
            rows = []
            for y in range(40, 160):
                n = sum(1 for x in range(xb, min(xb + 200, W)) if bluish(x, y))
                rows.append((n, y))
            rows.sort(reverse=True)
            yt = rows[0][1]
            p("  左边框 x=%d，竖边最上端 y0=%d，水平边框行 yt=%d（n=%d）"
              % (xb, y0, yt, rows[0][0]))
            check("水平边框确实存在（该行 > 150 个蓝像素）", rows[0][0] > 150, rows[0])
            check("面板是**直角**：竖边顶端与水平边几乎同一行（|yt-y0| ≤ 2；圆角 14 时差 14）",
                  y0 is not None and abs(yt - y0) <= 2, "yt-y0=%s" % (None if y0 is None else yt - y0))
            check("左上角点上有边框像素（圆角时该点是空的）", bluish(xb, yt), (xb, yt))
    rc = close(proc, hwnd)
    check("B 阶段关窗后正常退出（rc=0）", rc == 0, rc)

p("FAILS:", FAILS)
p("通过 %d/%d" % (len(OKS), len(OKS) + len(FAILS)))
p("LIVE_V201_ALL_OK" if not FAILS else "LIVE_V201_HAS_FAIL")
