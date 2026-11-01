# -*- coding: utf-8 -*-
"""v2.0.8（Build 2611010129）打包后真机验收。

本轮四条反馈，真机上能像素 / 数据自证的都验：

  ③ 表头「筛选 / 排序」图标只在**鼠标所在那一列**显示
     → 真鼠标 SetCursorPos 停在表头某列，停 0.5s 让重绘落定后抓图，
       在 `coords_v208.py` 离屏算出的图标中心 ±8px 里数「中性灰描边」像素：
         无悬停 → 4 列 × 2 枚全为 0；
         停在第 N 列 → 只有第 N 列的漏斗 + 三角有墨迹，其它列仍为 0；
         鼠标移开 → 又全部消失。

  ④ 首页列表「有点卡」的根因是整表填充（4 万条要 3.5s），改成视口懒填
     → 真机不可直接计时（grab 本身要几百毫秒，会把差异吃掉），
       改验「行为对不对」：滚到列表深处那一屏**仍有文字**（说明懒填充补得上）、
       点表头三角后 **0.9s 内**排序已生效并落盘（旧版 4 万条要 4.1s，
       3000 条也要 0.3s 级，这里同时验证「没有退化成整表重填」）、
       排序后列表仍满屏有字。

  ② 「评分」按钮白字 / 元数据行的 ★ 评分金色
     → 在详情页截图里按颜色找**连续 8~30 行、每行 ≥15 个金像素**的横带 =
       一段金色文字（★ 5.0）。不能用 find_box 一抓了事：`#HeroAct` 按钮的鎏金
       描边也是同一个黄，外接矩形会横跨整行 → 尺寸断言必然假红；而描边是线，
       每行只有 2 个像素，过不了「每行 ≥15」。
       同时断言详情页里**没有**链接蓝 `#66a9ff` 的文字带（蓝色评分已撤）。

  ① 标签芯片圆角 + 圆形 ×
     → 圆角在真机截图上无法判「透明」（底是磨砂剧照，颜色不恒定），
       所以这条只做**弱验证**：详情页里能找到「高 15~25px、每行 ≥80 像素」的
       `#27272a` 药丸填充带（= 标签芯片真的画出来了）。
       圆角半径 / × 是否居中的**硬断言**在离屏冒烟 ㉞ 段（像素级，偏移 ≤0.75px）。

踩坑（沿用前几版，勿删）：
  · 验收副本**必须另起 ASCII 名**：启动时 `_kill_other_instances()` 会杀掉同名进程。
  · **上一轮残留的 exe 必须先杀掉再删库**，否则 sqlite 句柄还在 → 删不掉 → 数据叠加。
  · `find_window(title_sub="Build")` —— 进程里第一个大窗口是启动画面（QSplashScreen）。
  · 点表头/卡片一律 PostMessage 到主窗 hwnd + **客户区坐标**；弹窗是独立顶层窗口。
  · 离屏算的坐标必须是 1920x1080 才对得上真机（coords 里有 main_size 校验）。
  · **悬停类断言必须用真鼠标**（SetCursorPos）：PostMessage 合成 MouseMove 不会
    让 QHeaderView 刷新 `_hover_section`（它靠真实 enter/leave 与 move 事件）。
"""

import ctypes
import ctypes.wintypes
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v208")
COORDS_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                           "lmc_coords_v208.json")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["LMC_NO_SYSMON"] = "1"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv          # noqa: E402  （导入时它会把自己的 stdout 重定向到日志）
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication      # noqa: E402
from PySide6.QtGui import QImage                # noqa: E402
from PIL import Image                           # noqa: E402

os.makedirs(SHOTS, exist_ok=True)
FAILS, OKS = [], []
T0 = time.time()
BUILD_TAG = "2611010129"
VER_TAG = "v2.0.8"

# 5 个头像的专属纯色。两条硬约束：
#  ① 互不接近；
#  ② **不能撞任何 UI 色**（早期踩过：灰 (120,120,120) 与 QSS 的 #71717a=(113,113,122)
#     在 tol=18 下判等；暖黄 (240,160,40) 与收藏金 #f5a524=(245,165,36) 也一样）。
C_P1 = (220, 40, 40)        # 女演员甲（带别名的那位）
C_P2 = (60, 220, 220)       # 女导演乙
C_P3 = (40, 200, 60)        # 男演员丙
C_P4 = (200, 60, 200)       # 男导演丁
C_P5 = (20, 20, 200)        # 未知戊（原来用棕 (150,100,60)，会和详情页底衬撞色，
                            # 外接矩形一下横跨整页 → 顺序判定把「未知」排到了最前面）
PHOTO_COLORS = [C_P1, C_P2, C_P3, C_P4, C_P5]
EXPECT_ORDER = ["女演员甲", "女导演乙", "男演员丙", "男导演丁", "未知戊"]
ACCENT = (228, 88, 124)     # #e4587c


def p(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    p(("  OK   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if detail else ""))


def _del(pth):
    if os.path.exists(pth):
        ctypes.windll.kernel32.SetFileAttributesW(pth, 0x80)
        ctypes.windll.kernel32.DeleteFileW(pth)


# ---------------- 像素工具 ----------------
def _px(im):
    return im.convert("RGB") if im.mode != "RGB" else im


def near(c, t, tol):
    return all(abs(c[i] - t[i]) <= tol for i in range(3))


def count_near(im, box, rgb, tol=26):
    x0, y0, x1, y1 = box
    px = _px(im).load()
    n = 0
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            if near(px[x, y], rgb, tol):
                n += 1
    return n


def count_gray_icon(im, box):
    """表头图标是 #a1a1aa 的描边（抗锯齿后向底色过渡）。

    判据放宽成「中性灰、亮度 95~215」—— 只认 #a1a1aa 会让 1.35px 描边的
    边缘像素全部落选，量出来只剩中心几个点。
    """
    x0, y0, x1, y1 = box
    px = _px(im).load()
    n = 0
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            r, g, b = px[x, y]
            if 95 <= r <= 215 and abs(r - g) <= 10 and 0 <= (b - r) <= 26:
                n += 1
    return n


def ink_count(im, box, thr=200):
    """一块区域里「亮到能确认是字」的像素数（占位符比它暗，不会被算进来）。"""
    x0, y0, x1, y1 = box
    px = _px(im).load()
    n = 0
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            if min(px[x, y][:3]) >= thr:
                n += 1
    return n


def click_confirm(pop, crop):
    """点面板的「确定」—— 只找**最底下一横条**，且用**紧**容差。

    两个坑（都真踩过）：
      · 容差放宽 → 选中的「≥」胶囊（rgba 强调色 0.22 叠深底）也算进来，
        外接矩形横跨整个面板，点中间等于点空地；
      · 不限纵向 → 输入框**获得焦点后的强调色描边**也在下方，和「确定」的
        外接矩形一合并，中心又落空。
    """
    w, h = crop.width, crop.height
    ox, oy = int(w * 0.35), max(0, h - 42)
    ab = find_box(crop.crop((ox, oy, w, h)), ACCENT, 14, 1)
    if ab is not None:
        real_click_popup(pop, ox + (ab[0] + ab[2]) // 2, oy + (ab[1] + ab[3]) // 2)
        return "accent"
    real_click_popup(pop, w - 32, h - 24)      # 兜底：右下角固定偏移
    return "corner"


def find_box(im, rgb, tol=18, step=2):
    px = _px(im).load()
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


def hbands(im, box, thr=140, gap=4, min_ink=2):
    """把一块区域按「有墨迹的行」切成横带（文字行）。返回 [(y0, y1), ...]。"""
    x0, y0, x1, y1 = box
    px = _px(im).load()
    out, cur = [], None
    for y in range(max(0, y0), min(y1, im.height)):
        n = 0
        for x in range(max(0, x0), min(x1, im.width)):
            if min(px[x, y][:3]) > thr:
                n += 1
                if n >= min_ink:
                    break
        if n >= min_ink:
            if cur is None:
                cur = [y, y]
            elif y - cur[1] <= gap:
                cur[1] = y
            else:
                out.append((cur[0], cur[1]))
                cur = [y, y]
    if cur:
        out.append((cur[0], cur[1]))
    return out


def band_top_color(im, box, thr=110, frac=0.25):
    """一条带里**最亮 frac** 像素的平均 RGB —— 这才是「字是什么颜色」。

    整带均值会把抗锯齿边缘（往底色过渡）全算进去：白字实测只能到 ~213，
    跟灰字分不开。取最亮的那一批，白字稳定落在 (250,250,250)。
    """
    x0, y0, x1, y1 = box
    px = _px(im).load()
    ps = []
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            c = px[x, y]
            if min(c[:3]) > thr:
                ps.append(c)
    if len(ps) < 8:
        return 0, None, 0
    ps.sort(key=lambda c: c[0] + c[1] + c[2])
    top = ps[int(len(ps) * (1.0 - frac)):]
    m = tuple(round(sum(c[i] for c in top) / len(top)) for i in range(3))
    return len(ps), m, len(top)


def ink_runs(im, box, thr=150, gap=2):
    """x 方向墨迹「段数」：两枚汉字 = 2 段，`Actor` = 4~5 段。

    比宽度更抗干扰 —— 11px 下「演员」≈22px、`Actor`≈28px，宽度阈值不好卡；
    段数则是硬差别。
    """
    x0, y0, x1, y1 = box
    px = _px(im).load()
    cols = []
    for x in range(max(0, x0), min(x1, im.width)):
        hit = False
        for y in range(max(0, y0), min(y1, im.height)):
            if min(px[x, y][:3]) > thr:
                hit = True
                break
        cols.append((x, hit))
    runs, cur = [], None
    for x, hit in cols:
        if hit:
            if cur is None:
                cur = [x, x]
            elif x - cur[1] <= gap:
                cur[1] = x
            else:
                runs.append(tuple(cur))
                cur = [x, x]
    if cur:
        runs.append(tuple(cur))
    return runs


def _pm2pil(pm):
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    buf = img.constBits()
    if buf is None:
        return None
    return Image.frombytes("RGB", (img.width(), img.height()), bytes(buf), "raw", "BGRX")


def grab_popup(pop):
    """抓**弹窗**的像素。

    ⚠ `grabWindow(pop)` 对这种 `Qt::Popup` 小窗返回一整块黑（DWM 合成层抓不到），
    所以要抓**整个桌面**再按弹窗的屏幕矩形裁。返回 (crop, (x0, y0), full)。
    """
    r_ = ctypes.wintypes.RECT()
    lv.u32.GetWindowRect(pop, ctypes.byref(r_))
    full = _pm2pil(app.primaryScreen().grabWindow(0))
    if full is None:
        return None, (0, 0), None
    x0, y0 = max(0, r_.left), max(0, r_.top)
    x1, y1 = min(full.width, r_.right), min(full.height, r_.bottom)
    if x1 - x0 < 20 or y1 - y0 < 20:
        return None, (x0, y0), full
    return full.crop((x0, y0, x1, y1)), (x0, y0), full


# ---------------- 输入 ----------------
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE = 0x0201, 0x0202, 0x0200
WM_MOUSEWHEEL, WM_CHAR, WM_KEYDOWN, WM_KEYUP = 0x020A, 0x0102, 0x0100, 0x0101


def dbl(hwnd, x, y):
    """两下快速 press/up —— Qt 自己按时间/距离判双击。"""
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    for _ in range(2):
        lv.u32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
        lv.u32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lp)
        time.sleep(0.03)
        lv.u32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)
        time.sleep(0.06)


def wheel(hwnd, notches=-3, at=(900, 600)):
    """往下滚。lParam 是屏幕坐标，wParam 高 16 位是 delta。"""
    lv.u32.SetForegroundWindow(hwnd)
    for _ in range(abs(notches)):
        delta = -120 if notches < 0 else 120
        lv.u32.PostMessageW(hwnd, WM_MOUSEWHEEL, ((delta & 0xFFFF) << 16),
                            ((at[1] & 0xFFFF) << 16) | (at[0] & 0xFFFF))
        time.sleep(0.12)


def type_text(hwnd, text):
    for ch in text:
        lv.u32.PostMessageW(hwnd, WM_CHAR, ord(ch), 0)
        time.sleep(0.05)


def real_type(text):
    for ch in text:
        vk = 0x30 + (ord(ch) - 0x30)
        lv.u32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        lv.u32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.05)


def _screen_of(hwnd_, x, y):
    pt = ctypes.wintypes.POINT(int(x), int(y))
    lv.u32.ClientToScreen(hwnd_, ctypes.byref(pt))
    return pt.x, pt.y


def real_click(hwnd_, x, y):
    """**真鼠标**点一下（SetCursorPos + mouse_event）。

    为什么不用 PostMessage：`LazyGrid` 的卡片与 `Qt::Popup` 面板对**合成事件**不买账 ——
    实测 PostMessage 在演员卡上点两下（间隔 90ms）根本不触发 doubleClicked，
    而真鼠标一下就开；弹窗里的输入框也只认真实点击给的**原生焦点**
    （键盘事件因此才能落到它身上，WM_CHAR / keybd_event 都要这个前提）。
    """
    lv.u32.SetForegroundWindow(hwnd_)
    time.sleep(0.15)
    sx, sy = _screen_of(hwnd_, x, y)
    lv.u32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.12)
    lv.u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.04)
    lv.u32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.15)


def real_click_popup(pop, x, y):
    """真鼠标点弹窗（弹窗是自己一个顶层窗口，客户端坐标 == 窗口内坐标）。"""
    r_ = ctypes.wintypes.RECT()
    lv.u32.GetWindowRect(pop, ctypes.byref(r_))
    # ⚠ **不要**在这里 SetForegroundWindow：Qt 的 Qt::Popup 一收到「窗口失活」就会
    #    自己关掉 —— 真机实测那样点两下，面板在点之前就没了，于是「确定」永远点不到。
    lv.u32.SetCursorPos(int(r_.left + x), int(r_.top + y))
    time.sleep(0.12)
    lv.u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.04)
    lv.u32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.18)


def real_dbl(hwnd_, x, y):
    """真鼠标双击（两次 press 间隔 ~70ms，Qt 自己判 doubleClicked）。"""
    lv.u32.SetForegroundWindow(hwnd_)
    time.sleep(0.15)
    sx, sy = _screen_of(hwnd_, x, y)
    lv.u32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.15)
    for _ in range(2):
        lv.u32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.03)
        lv.u32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.07)
    time.sleep(0.2)


# ---------------- 环境预置 ----------------
os.makedirs(TEMP, exist_ok=True)
src = lv.newest_exe()
p("新 exe:", src)
assert src and os.path.exists(src)
check("根目录最新 exe 就是 v2.0.8（2611010129）",
      VER_TAG in os.path.basename(src) and BUILD_TAG in os.path.basename(src),
      os.path.basename(src))
exe = os.path.join(TEMP, "LMC-probe-%s.exe" % BUILD_TAG)
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)
EXE_NAME = os.path.basename(exe).lower()

LIB = os.path.join(TEMP, "lib")
os.makedirs(os.path.join(LIB, "A", "MIDA-846"), exist_ok=True)
POSTER = os.path.join(TEMP, "poster.png")
# 海报给一个**专属色**：深灰 (58,58,70) 会和页面底色/面板底色撞，
# find_box 一找就是整片（实测外接矩形 38,278~1894,1070）→ 双击落空。
Image.new("RGB", (300, 450), (90, 150, 110)).save(POSTER)
PHOTOS = []
for _i, _c in enumerate(PHOTO_COLORS):
    _pth = os.path.join(TEMP, "photo_%d.png" % _i)
    Image.new("RGB", (240, 240), _c).save(_pth)
    PHOTOS.append(_pth)

CFG = os.path.join(TEMP, "settings.json")
IDX = os.path.join(TEMP, "index_data")
LOG = os.path.join(IDX, "logs", "app.log")
DBF = os.path.join(IDX, "media_center.db")

# ⚠ 顺序不能反：先杀残留进程，再删库。上一轮没杀掉时 sqlite 句柄还在 → 删不掉 →
#    本轮 6 部片会叠成 12 部，双击到的是上一轮的行（第一版的假红全是这个引起的）。
subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
time.sleep(1.0)
os.makedirs(os.path.join(IDX, "logs"), exist_ok=True)
for _try in range(6):
    for fn in os.listdir(IDX):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(IDX, fn))
    if not os.path.exists(DBF):
        break
    time.sleep(0.6)
check("临时库已清空（旧 sqlite 句柄没把文件钉住）", not os.path.exists(DBF), DBF)
_del(LOG)

sys.path.insert(0, os.path.join(ROOT, "src"))
import database as db          # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: DBF
applog.log_dir = lambda: os.path.join(IDX, "logs")
db.init_db()

ROWS = [
    ("MIDA-846 真机验收 主演甲", 2026, 1, 7.5),
    ("ZZZ-005 老片五", 2010, 0, None),
    ("BBB-002 老片二", 2019, 1, 6.0),
    ("CCC-003 老片三", 2018, 0, None),
    ("DDD-004 老片四", 2020, 0, 8.1),
    ("AAA-001 老片一", 2015, 0, None),
]
MIDS = {}
for _t, _y, _f, _ur in ROWS:
    MIDS[_t] = db.insert_media(
        title=_t, kind="movie", year=_y, rating=7.0, poster=POSTER,
        file_path=os.path.join(LIB, "A", "MIDA-846", "%s.mp4" % _t.split()[0]),
        library="真机库", sort_title=_t, favorite=_f, user_rating=_ur,
        added_time="2026-11-01 12:00:00", added_date="2026-11-01")
M0 = MIDS[ROWS[0][0]]

CAST = [("男演员丙", "male", "Actor", 0),
        ("男导演丁", "male", "Director", 1),
        ("女演员甲", "female", "Actor", 2),
        ("女导演乙", "female", "Director", 3),
        ("未知戊", "", "Actor", 4)]
PHOTO_OF = {nm: PHOTOS[i] for i, nm in enumerate(EXPECT_ORDER)}
PIDS = {}
for _nm, _g, _role, _ord in CAST:
    _pid = db.upsert_person(_nm, _role)
    db.set_person_fields(_pid, gender=_g, photo_path=PHOTO_OF[_nm])
    db.link_media_person(M0, _pid, "导演" if _role == "Director" else "", _ord)
    PIDS[_nm] = _pid
db.set_person_fields(PIDS["女演员甲"], alias="あい【デリ嬢】、さな、相音さな、あいね")

# ---- 压测：再插 3000 条「顶层条目」，凑成 3006 条用于验证视口懒填充
# （v2.0.8 反馈 4 的「卡」只在几千条以上才显形，6 部片根本量不出来）。
# 单连接 + executemany：insert_media 每次 commit，3000 次会白等好几秒。
STRESS_N = 3000
_c0 = time.monotonic()
_c = db.get_conn()
try:
    _rows = []
    for _i in range(STRESS_N):
        _t = "P%04d 压测行" % _i
        _rows.append(("movie", _t, _t, 1990 + (_i % 37), 5.0 + (_i % 50) / 10.0,
                      POSTER, os.path.join(LIB, "A", "MIDA-846", "%s.mp4" % _t.split()[0]),
                      "真机库", "2026-11-01 12:00:00", "2026-11-01"))
    _c.executemany("INSERT INTO media(kind,title,sort_title,year,rating,poster,"
                   "file_path,library,added_time,added_date) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?)", _rows)
    _c.commit()
finally:
    db.close_conn()            # 真关掉（_PooledConn.close() 是 no-op）
p("压测灌入 %d 条，用时 %.0fms" % (STRESS_N, (time.monotonic() - _c0) * 1000))
_cc = sqlite3.connect(DBF, timeout=8)
try:
    _n_all = _cc.execute("SELECT COUNT(*) FROM media").fetchone()[0]
finally:
    _cc.close()
check("压测灌入后库里正好 3006 条", _n_all == 3006, _n_all)

# 刻意**不写 home_sort**：让列表开局是「未排序」（sort_col=-1，4 列三角全灰），
# 这样「点一下 = 升序、再点 = 降序」才是可预期的。
with open(CFG, "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "真机库", "kind": "电影", "paths": [LIB], "filter": {}}],
               "appearance": {"accent": "#e4587c", "mode": "磨砂玻璃", "level": "低"},
               "home_columns": ["title", "favorite", "year", "user_rating"],
               "home_column_widths": {"title": 300, "favorite": 110,
                                      "year": 120, "user_rating": 120},
               "home_split": [900, 640]},
              f, ensure_ascii=False, indent=2)
os.environ["LMC_CONFIG"] = CFG
p("预置：6 部片 / %d 位演职人员 / M0 id=%s" % (len(CAST), M0))


def db_one(sql, args=()):
    con = sqlite3.connect(DBF, timeout=8)
    try:
        row = con.execute(sql, args).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def read_cfg():
    try:
        with open(CFG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ---------------- 坐标（离屏算，与真机同尺寸同配置） ----------------
p("算坐标…")
env = dict(os.environ)
env["LMC_CONFIG"] = CFG
env["QT_QPA_PLATFORM"] = "offscreen"
r = subprocess.run([sys.executable, "-c",
                    "import runpy; runpy.run_path(r'%s', run_name='__main__')"
                    % os.path.join(DEV, "_scratch", "coords_v208.py")],
                   capture_output=True, timeout=240, env=env)
p("coords rc=%s" % r.returncode)
if r.returncode != 0:
    p((r.stdout or b"")[-1500:].decode("utf-8", "replace"))
    p((r.stderr or b"")[-2000:].decode("utf-8", "replace"))
CO = json.load(open(COORDS_JSON, encoding="utf-8"))
assert CO.get("main_size") == [1920, 1080], CO.get("main_size")
NAV = {k: tuple(v) for k, v in (CO.get("nav") or {}).items()}
HDR, TBL = CO["header"], CO["table"]
COLS = {c["key"]: c for c in HDR["cols"]}
p("导航:", NAV, "| 表头 x0=%s y=%s | 列 %s" % (HDR["x0"], HDR["y"],
                                             [(c["key"], c["w"]) for c in HDR["cols"]]))

# ---------------- 启动 ----------------
app = QApplication.instance() or QApplication(sys.argv)

hwnd = None
p("========== v2.0.8 真机验收（accent=#e4587c / 磨砂玻璃·低） ==========")
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=180, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)


def kill_exe():
    try:
        if hwnd:
            lv.u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
    except Exception:
        pass
    time.sleep(1.5)
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)


if not hwnd:
    kill_exe()
    raise SystemExit(1)
time.sleep(3.0)


def shot(tag, settle=4):
    pm = lv.grab(app, hwnd, tries=24, gap=0.4, settle=settle)
    if pm is None or pm.width() < 100:
        p("!! 抓图失败", tag)
        return None
    im = _pm2pil(pm)
    im.save(os.path.join(SHOTS, "v208_%s.png" % tag))
    p("  图 %s  %dx%d" % ("v208_%s.png" % tag, im.width, im.height))
    return im



try:
    # ============================================================
    # ③ 表头图标只在「鼠标所在那一列」显示
    # ============================================================
    p("========== ③ 表头：图标只在悬停列 ==========")

    def hover(hwnd_, x, y, wait=0.55):
        """把**真鼠标**移到客户区 (x, y) 并停住 —— 悬停重绘只认真实事件。"""
        lv.u32.SetForegroundWindow(hwnd_)
        time.sleep(0.12)
        sx, sy = _screen_of(hwnd_, x, y)
        lv.u32.SetCursorPos(int(sx), int(sy))
        time.sleep(wait)

    def icons(im, key):
        """量某一列「左漏斗 / 右三角」两处图标区的墨迹像素。"""
        fx, fy = COLS[key]["funnel"]
        tx, ty = COLS[key]["tri"]
        return (count_gray_icon(im, (fx - 8, fy - 8, fx + 8, fy + 8)),
                count_gray_icon(im, (tx - 7, ty - 7, tx + 7, ty + 7)))

    def mid_of(key):
        fx, fy = COLS[key]["funnel"]
        tx, _ = COLS[key]["tri"]
        return (fx + tx) // 2, fy

    hover(hwnd, 900, 720)                      # 先把鼠标挪离表头
    im0 = shot("home_idle")
    base = {k: icons(im0, k) for k in COLS}
    p("  无悬停: %s" % base)
    check("③ 鼠标不在表头上 → 4 列 × 2 枚图标全不显示",
          all(v[0] < 8 and v[1] < 6 for v in base.values()), base)
    check("③ 窗口截图尺寸合理（>1200x700）",
          bool(im0) and im0.width > 1200 and im0.height > 700,
          "%dx%d" % (im0.width, im0.height) if im0 else "-")

    for _key in ("favorite", "title"):
        hover(hwnd, *mid_of(_key))
        im = shot("home_hover_%s" % _key)
        now = {k: icons(im, k) for k in COLS}
        p("  悬停 %s: %s" % (_key, now))
        check("③ 鼠标停在「%s」列 → 这一列的漏斗 + 三角都出现" % _key,
              now[_key][0] >= 12 and now[_key][1] >= 6, now[_key])
        others = {k: v for k, v in now.items() if k != _key}
        check("③ 其它列仍然一个图标都没有（只有悬停那一列有）",
              all(v[0] < 8 and v[1] < 6 for v in others.values()), others)

    hover(hwnd, 900, 720)
    im_leave = shot("home_leave")
    gone = {k: icons(im_leave, k) for k in COLS}
    check("③ 鼠标移开后图标又全部消失", 
          all(v[0] < 8 and v[1] < 6 for v in gone.values()), gone)

    # ============================================================
    # ============================================================
    # ③bis 逐列悬停：图标画了没 / 这一列到底被重绘了没
    # ============================================================
    p("========== ③bis 逐列悬停诊断 ==========")

    def ink_map(im):
        out = {}
        for k, c in COLS.items():
            fx, fy = c["funnel"]
            tx, ty = c["tri"]
            out[k] = (count_gray_icon(im, (fx - 9, fy - 9, fx + 9, fy + 9)),
                      count_gray_icon(im, (tx - 8, ty - 8, tx + 8, ty + 8)))
        return out

    def diff_map(a, b):
        """两张图在「各列表头条」上的像素差总数 —— 用来判断哪一列真的被重绘过。"""
        pa, pb = _px(a).load(), _px(b).load()
        res = {}
        for k, c in COLS.items():
            x0 = c["funnel"][0] - 6
            x1 = c["tri"][0] + 6
            y0, y1 = HDR["y"] - 15, HDR["y"] + 15
            n = 0
            for y in range(max(0, y0), min(a.height, y1)):
                for x in range(max(0, x0), min(a.width, x1)):
                    q, w = pa[x, y], pb[x, y]
                    if abs(q[0] - w[0]) + abs(q[1] - w[1]) + abs(q[2] - w[2]) > 60:
                        n += 1
            res[k] = n
        return res

    # 表头各列的真实边界（自己算，不依赖 _zones，避免「用被测代码验被测代码」）
    edges = []
    for _k, _c in COLS.items():
        pass
    x0h = HDR["x0"]
    acc = x0h
    for _c in HDR["cols"]:
        edges.append((_c["key"], acc, acc + _c["w"]))
        acc += _c["w"]
    p("  表头列边界: %s" % (edges,))

    hover(hwnd, 900, 760)
    im_idle = shot("probe208_idle")
    base = ink_map(im_idle)
    p("  [idle] %s" % (base,))

    for _k, _a, _b in edges:
        xm = (_a + _b) // 2
        # 两步移动：先到这一列左边界内侧，再挪到中心 —— 确保 Qt 收到真实 move 事件
        hover(hwnd, _a + 6, HDR["y"], wait=0.45)
        hover(hwnd, xm, HDR["y"], wait=1.0)
        im = shot("probe208_hov_%s" % _k)
        now = ink_map(im)
        d = diff_map(im_idle, im)
        p("  [hover %s @x=%d] ink=%s" % (_k, xm, now))
        p("                        diff=%s" % (d,))
        hit = _k
        check("③bis 悬停 %s 列 → 该列左漏斗有墨" % _k, now[hit][0] >= 8, now[hit][0])
        check("③bis 悬停 %s 列 → 该列右三角有墨" % _k, now[hit][1] >= 4, now[hit][1])
        check("③bis 悬停 %s 列 → 该列表头确实被重绘（与 idle 有像素差）" % _k,
              d.get(hit, 0) > 30, d.get(hit, 0))
        check("③bis 悬停 %s 列 → 其它列表头保持静止" % _k,
              max(v for kk, v in d.items() if kk != hit) < 30,
              dict((kk, v) for kk, v in d.items() if kk != hit))

    hover(hwnd, 900, 760)
    im_end = shot("probe208_leave")
    p("  [leave] %s" % (ink_map(im_end),))
    check("③bis 移开后全部归零",
          all(v[0] < 8 and v[1] < 4 for v in ink_map(im_end).values()),
          ink_map(im_end))

finally:
    kill_exe()

# ---------------- 日志 ----------------
log_txt = ""
if os.path.exists(LOG):
    with open(LOG, encoding="utf-8", errors="replace") as f:
        log_txt = f.read()
exc = [ln for ln in log_txt.splitlines()
       if ("未捕获异常" in ln or "Traceback (most recent call last)" in ln)]
check("真机 app.log 里没有未捕获异常 / Traceback", not exc, exc[:3])
check("app.log 有内容（真的跑起来了）", len(log_txt) > 120, "%d 字节" % len(log_txt))

p("========== 结果 ==========")
p("通过 %d / %d" % (len(OKS), len(OKS) + len(FAILS)))
if FAILS:
    p("失败：")
    for f in FAILS:
        p("  · " + f)
    print("LIVE_V208_FAIL", len(FAILS), flush=True)
else:
    print("LIVE_V208_ALL_OK", len(OKS), flush=True)
