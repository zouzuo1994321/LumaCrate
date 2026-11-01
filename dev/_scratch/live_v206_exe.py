# -*- coding: utf-8 -*-
"""v2.0.5（Build 2611010126）打包后真机验收。

本轮三条反馈里，**能在这台机器的真机 exe 上像素自证的**都验：
  ① 扫描改成「逐路径 统计→扫描」—— 属于后台逻辑，真机演示库的路径（D:/演示路径-N）
     并不存在，点扫描只会一遍空走；取证放在离屏冒烟 ㉚ 段（真建 2 条路径、真删文件、
     真改 nfo，断言分母 2/1、变更 1、减少 1）。底部那行文案的版式见
     docs/preview/v206_scan_bar.png。
  ② 收藏影片名称金黄色 / 卡片标题靠左 —— **真机验**：预置索引里放一部**已收藏**的片，
     进「我的收藏」影片墙，按海报的独有色块定位卡片，再量标题带里的金像素与左边缘。
  ③ 回归：侧栏实色 / #PageTitle 跟色 / 色卡新粉无旧粉 / 透明度中性白 /
     换翡翠后标题变绿 / 手动修改页白字 / glyphs 落盘 / app.log 干净。

踩坑（沿用前几版，勿删）：
  · 验收副本**必须另起 ASCII 名**：启动时 `_kill_other_instances()` 会杀掉所有同名进程。
  · 工具窗刚 show 时控件没建完 → 先等 2.6s，否则 grabWindow 拿到 0×0。
  · 首页没有 #PageTitle（顶部是筛选 chip）→ 验标题必须点侧栏「最近播放」。
  · 侧栏导航只能用「最近播放」(90,160) 这个已知锚点；别的行靠 y 递增试探 +
    「抓到海报色块才算命中」来确认，不靠猜坐标。
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
                    "lmc_exe_v206")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication
from PIL import Image, ImageDraw

os.makedirs(SHOTS, exist_ok=True)
FAILS, OKS = [], []
T0 = time.time()
PINK = (228, 88, 124)
OLDPINK = (255, 127, 161)
JADE = "#17c964"
GOLD = (245, 165, 36)
POSTER_RGB = (128, 48, 176)
BUILD_TAG = "2611010126"
VER_TAG = "v2.0.5"


def p(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    p(("  OK   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if detail else ""))


def _del(pth):
    if os.path.exists(pth):
        ctypes.windll.kernel32.SetFileAttributesW(pth, 0x80)
        ctypes.windll.kernel32.DeleteFileW(pth)


def near(c, t, tol):
    return all(abs(c[i] - t[i]) <= tol for i in range(3))


def count_in(im, box, pred):
    x0, y0, x1, y1 = box
    px = im.load()
    n = 0
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            if pred(px[x, y]):
                n += 1
    return n


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


def is_gold(c):
    r, g, b = c
    # 金黄：红高、绿中高、蓝低（容忍 ClearType 抗锯齿把饱和压下来的边缘）
    return r >= 170 and 100 <= g <= 215 and b <= 110 and (r - b) >= 90


def find_box(im, rgb, tol=18, step=2):
    """在整张图里找近似 rgb 的色块外接矩形（用来定位预置的海报）。"""
    px = im.load()
    x0 = y0 = 10 ** 9
    x1 = y1 = -1
    for y in range(0, im.height, step):
        for x in range(0, im.width, step):
            if near(px[x, y], rgb, tol):
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
    if x1 < 0:
        return None
    return (x0, y0, x1, y1)


os.makedirs(TEMP, exist_ok=True)
src = lv.newest_exe()
p("新 exe:", src)
assert src and os.path.exists(src)
check("根目录最新的 exe 就是 v2.0.5（2611010126）",
      VER_TAG in os.path.basename(src) and BUILD_TAG in os.path.basename(src),
      os.path.basename(src))
exe = os.path.join(TEMP, "LMC-probe-%s.exe" % BUILD_TAG)
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)
EXE_NAME = os.path.basename(exe).lower()

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
NAV_RECENT = (90, 160)
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


def dot_centers(im, y_lo=200, y_hi=340, x_lo=230, x_hi=700):
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


TITLE_BAND = (200, 50, 900, 108)

# ============================================================
p("========== v2.0.5 真机验收（accent=#e4587c / 磨砂玻璃·低） ==========")
subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
if os.path.isdir(IDX):
    for fn in os.listdir(IDX):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(IDX, fn))
os.makedirs(IDX, exist_ok=True)
_del(LOG)

# ---- 预置一部「已收藏」的片（反馈 2/3 的真机取证靠它） ----
sys.path.insert(0, os.path.join(ROOT, "src"))
import database as db          # noqa: E402
import applog                  # noqa: E402

DBF = os.path.join(IDX, "media_center.db")
db.db_path = lambda: DBF
applog.log_dir = lambda: os.path.join(IDX, "logs")
db.init_db()
poster = os.path.join(TEMP, "fav_poster.png")
_img = Image.new("RGB", (316, 472), POSTER_RGB)
_d = ImageDraw.Draw(_img)
_d.rectangle([10, 10, 305, 200], fill=(160, 90, 210))
_img.save(poster)
_mid = db.upsert_media_by_path(
    mode="overwrite", kind="movie", title="峰不二子", sort_title="fengbuerzi",
    year=2025, rating=8.5, quality="4K", favorite=1, library="Javlibrary",
    poster=poster, file_path=os.path.join(TEMP, "fake", "fengbuerzi.mp4"),
    plot="真机验收用的预置条目", added_time="2026-11-01 10:00:00",
    added_date="2026-11-01")
p("预置条目 id=%s（收藏=1）" % _mid)

proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=120, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)

if hwnd:
    title = lv.wtitle(hwnd)
    p("  title:", title)
    check("标题含 v2.0.5", VER_TAG in title, title)
    check("标题含构建号 2611010126", BUILD_TAG in title, title)
    time.sleep(6)
    check("启动后不处于「未响应」", not bool(ctypes.windll.user32.IsHungAppWindow(hwnd)))

    im = shot(hwnd, min_w=1500)
    if im is None:
        check("主窗可抓图", False)
    else:
        im.save(os.path.join(SHOTS, "v206_exe_home.png"))
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

        # ---- ② 反馈 2/3：收藏 → 标题金色；标题靠左 ----
        # 侧栏只有「最近播放」(90,160) 是已知锚点，别的行按 +40 试探，
        # 命中判据是「抓到了预置海报的紫色块」，不靠猜。
        hero = None
        used_y = None
        for y in (200, 240, 280, 320, 360, 180):
            lv.click(hwnd, 90, y)
            time.sleep(1.5)
            imx = shot(hwnd, min_w=1500, tries=4, gap=0.3)
            if imx is None:
                continue
            box = find_box(imx, POSTER_RGB)
            if box and (box[2] - box[0]) > 60 and (box[3] - box[1]) > 90:
                hero, used_y = (imx, box), y
                break
        check("进入「我的收藏」影片墙并抓到预置海报", hero is not None,
              "点击 y=%s 命中" % used_y if hero else "6 个候选 y 都没抓到海报")
        if hero:
            imx, (bx0, by0, bx1, by1) = hero
            imx.save(os.path.join(SHOTS, "v206_exe_fav_card.png"))
            p("  海报外接框:", (bx0, by0, bx1, by1))
            band = (bx0 - 8, by1 + 2, bx1 + 12, by1 + 44)
            n_gold = count_in(imx, band, is_gold)
            check("收藏影片的卡片标题是金黄色（≥25 个金像素）", n_gold >= 25, n_gold)
            # 左对齐：标题带里最左的金像素应贴着海报左边（居中时短标题会缩进十几到几十像素）
            px2 = imx.load()
            left = None
            for x in range(band[0], band[2]):
                if any(is_gold(px2[x, y]) for y in range(band[1], band[3])):
                    left = x
                    break
            p("  标题最左金像素 x=%s / 海报左边 x=%s" % (left, bx0))
            check("标题贴着海报左边（靠左对齐，偏移 ≤ 10px）",
                  left is not None and abs(left - bx0) <= 10,
                  "left=%s poster=%s" % (left, bx0))

        # ③ 进「最近播放」页 —— 那里的 20px 标题才是 #PageTitle
        lv.click(hwnd, NAV_RECENT[0], NAV_RECENT[1])
        time.sleep(1.8)
        im_t = shot(hwnd, min_w=1500, tries=10)
        check("切到「最近播放」页并抓到图", im_t is not None)
        if im_t is not None:
            im_t.save(os.path.join(SHOTS, "v206_exe_title_pink.png"))
            n_pink = count_in(im_t, TITLE_BAND, is_pink)
            n_blue = count_in(im_t, TITLE_BAND, is_blue)
            check("大标题是**新粉**（≥150 个粉像素）", n_pink >= 150, n_pink)
            check("大标题里没有蓝像素（v2.0.1 之前是写死的 #66a9ff）", n_blue == 0, n_blue)

    gd = os.path.join(IDX, "ui_glyphs")
    have = sorted(os.listdir(gd)) if os.path.isdir(gd) else []
    p("  glyphs:", have)
    check("index_data/ui_glyphs 里有 3 个小图标",
          len([f for f in have if os.path.getsize(os.path.join(gd, f)) > 100]) >= 3, have)

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
            im.save(os.path.join(SHOTS, "v206_exe_appearance.png"))
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
            check("「窗口透明度 100%」不再是蓝色", n_blue == 0, n_blue)

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

            im3, why3 = click_nav(dlg, NAV_MANUAL, ROW_MANUAL)
            check("切到「手动修改」", im3 is not None
                  and any(abs(a - ROW_MANUAL[0]) <= 6 for a, b in nav_rows(im3)), why3)
            if im3 is not None:
                im3.save(os.path.join(SHOTS, "v206_exe_manual_title.png"))
                tband = (175, 40, 370, 110)
                n_blue3 = count_in(im3, tband, is_blue)
                n_white3 = count_in(im3, tband, is_neutral_bright)
                check("「检索并选择影片」是中性白（≥40 像素）", n_white3 >= 40, n_white3)
                check("这一带的标题不再是蓝色", n_blue3 == 0, n_blue3)

            im4, why4 = click_nav(dlg, NAV_SERVICE, ROW_SERVICE)
            check("切到「服务管理」", im4 is not None, why4)
            check("连切三页后工具窗仍响应",
                  not bool(ctypes.windll.user32.IsHungAppWindow(dlg)))

        lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
        time.sleep(1.4)

    im5 = shot(hwnd, min_w=1500, tries=10)
    check("换色后主窗仍能抓图", im5 is not None)
    if im5 is not None:
        im5.save(os.path.join(SHOTS, "v206_exe_title_jade.png"))
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
p("LIVE_V206_ALL_OK" if not FAILS else "LIVE_V206_HAS_FAIL")
