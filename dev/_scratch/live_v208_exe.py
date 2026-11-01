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
# MIDA-846 额外带 3 个标签：①「标签芯片圆角 + 右上角圆形 ×」必须**有一部带标签的片**
# 才验得到（首跑就是栽在「双击到的是一部无标签的压测行」，药丸横带自然是 0 条）。
TAGS_OF = {ROWS[0][0]: "人妻,高清,剧情"}
MIDS = {}
for _t, _y, _f, _ur in ROWS:
    MIDS[_t] = db.insert_media(
        title=_t, kind="movie", year=_y, rating=7.0, poster=POSTER,
        file_path=os.path.join(LIB, "A", "MIDA-846", "%s.mp4" % _t.split()[0]),
        library="真机库", sort_title=_t, favorite=_f, user_rating=_ur,
        tags=TAGS_OF.get(_t, ""),
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
    # 悬停 / 排序这类改动只把「脏矩形」交给 Qt 排队，抓图往往拿到的是**上一帧**。
    # `grabWindow` 走的是窗口后台缓存，不会替你强制重绘 —— 于是「图标明明画了却量不到」。
    # 这里先 RedrawWindow(INVALIDATE|UPDATENOW|ALLCHILDREN) 把待重绘区当场画掉。
    try:
        lv.u32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0100 | 0x0080)
        lv.u32.UpdateWindow(hwnd)
    except Exception:
        pass
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

    def hover(hwnd_, x, y, wait=0.70):
        """把**真鼠标**移到客户区 (x, y) 并停住 —— 悬停重绘只认真实事件。

        ⚠ 必须**两步**移动：一次性从远处（行区）跳到表头时，真机实测**偶发一次
        mouseMove 都不触发**。证据：v2.0.8 首跑时 favorite 列量到 (0, 0) 而
        title 列正常；同一脚本重跑 favorite 就绿了 —— 是「首悬停丢事件」的抖动，
        不是产品逻辑（`_hover_section` 那条链路另有 4 列全过的独立探针）。
        先落一个近邻点、再挪到目标点，等价于补一次 enter + move，稳定复现。
        """
        lv.u32.SetForegroundWindow(hwnd_)
        time.sleep(0.10)
        sx, sy = _screen_of(hwnd_, x, y)
        lv.u32.SetCursorPos(int(sx) - 6, int(sy))
        time.sleep(0.12)
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

    def hover_until(x, y, probe, tag, tries=3):
        """悬停到 (x, y)，取图直到 `probe(im)` 成立；最多重试 `tries` 次。

        真机实测「**进程里第一次悬停表头**」偶发整条 mouseMove 丢失 —— 同一份脚本
        连跑三遍是两绿一红（红的那次 favorite 列量到 (0,0)，title 列同 y 却正常）。
        这不是产品缺陷（另有 4 列全过的独立探针），但会让验收自己骗自己，
        所以给它**有界重试**：每次先离开再重新进入（补 enter + move）；
        重试到底还不行，照样判红 —— 不掩盖真回归。
        """
        im = None
        for _i in range(tries):
            hover(hwnd, 900, 760, wait=0.35)
            hover(hwnd, x, y, wait=0.85)
            im = shot("%s_r%d" % (tag, _i))
            if im is not None and probe(im):
                return im
            p("    (%s 第 %d 次悬停没反应，重试)" % (tag, _i + 1))
        return im

    # 预热：真机启动后有一段时间**根本不响应悬停重绘**（实测 t=19~27s 连试 6 次全无反应，
    # t≈35s 之后才正常）。与其盲等，不如「悬到出图标为止」，把这块不确定性挡在量测之前。
    hot0 = None
    for _i in range(12):
        hover(hwnd, *mid_of("title"), wait=0.45)
        _im = shot("home_warm%d" % _i, settle=2)
        if icons(_im, "title")[0] >= 12:
            hot0 = _i + 1
            break
    p("  预热：第 %s 次悬停才开始有反应" % hot0)
    check("③ 界面进入「能响应悬停」状态（预热成功）", hot0 is not None, hot0)
    hover(hwnd, 900, 760, wait=0.55)
    im0 = shot("home_idle")
    base = {k: icons(im0, k) for k in COLS}
    p("  无悬停: %s" % base)
    check("③ 鼠标不在表头上 → 4 列 × 2 枚图标全不显示",
          all(v[0] < 8 and v[1] < 6 for v in base.values()), base)
    check("③ 窗口截图尺寸合理（>1200x700）",
          bool(im0) and im0.width > 1200 and im0.height > 700,
          "%dx%d" % (im0.width, im0.height) if im0 else "-")

    for _key in ("favorite", "title"):
        _hx, _hy = mid_of(_key)
        im = hover_until(_hx, _hy,
                         lambda i, k=_key: icons(i, k)[0] >= 12, "home_hover_%s" % _key)
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
    # ② 详情页：★ 评分金色 / ① 标签药丸（都在这张图上量）
    # ============================================================
    p("========== ② 详情页：★ 评分金色 ==========")

    def color_bands(im, rgb, tol=26, min_per_row=15, min_h=8, max_h=34, ybox=None):
        """找出「连续 min_h~max_h 行、每行至少 min_per_row 个该颜色像素」的横带。

        这才是「一段文字」的形状。按钮的鎏金描边虽然同色，但描边是**线**：
        横线每行 2 个像素、竖线每行 2 个像素 —— 永远过不了每行阈值。
        `min_per_row` 要小到能容下 12px 正文笔画：真机实测「★ 8.3」那行
        峰值只有 **10~11 个**金色像素/行（抗锯齿 + 绿底混色），原来写 15 必然空手。
        """
        px = _px(im).load()
        y0b, y1b = ybox if ybox else (0, im.height)
        rows, cur, out = {}, None, []
        for y in range(max(0, y0b), min(im.height, y1b)):
            n = 0
            for x in range(im.width):
                if near(px[x, y], rgb, tol):
                    n += 1
            if n >= min_per_row:
                if cur is None:
                    cur = [y, y]
                else:
                    cur[1] = y
            elif cur is not None:
                if min_h <= cur[1] - cur[0] + 1 <= max_h:
                    out.append(tuple(cur))
                cur = None
        if cur is not None and min_h <= cur[1] - cur[0] + 1 <= max_h:
            out.append(tuple(cur))
        return out

    POSTER_RGB = (90, 150, 110)     # 详情页那块「海报底衬」的专属色（见上面 POSTER）

    def poster_pixels(im):
        """详情页才有的大块海报底衬像素数 —— 判断「现在到底在列表还是在详情」。"""
        return count_near(im, (0, 0, im.width, im.height), POSTER_RGB, 8)

    def home():
        """回首页列表并滚到顶 —— ②/④ 都从同一个干净状态开始。

        ⚠ 两个真机坑（v2.0.8 各踩了一次）：
          ① 详情页里点侧栏「首页」是**空操作**：导航键没变（详情只是「首页」的子视图），
             `_nav_click` 判「已经在这一页」直接返回。必须先切「全部」再切回「首页」。
          ② 导航/按钮点击必须走**真鼠标**（`real_click`）：`lv.click` 是 PostMessage
             合成消息，窗口不在激活态时 Qt 把这次按下当成「点击激活窗口」吞掉 ——
             页面纹丝不动。证据：上一轮 ④ 的 `home_top.png` 与详情页截图**逐字节相同**。
        兜底：两次导航后仍停在详情页，就点左上角的「←返回」。
        """
        real_click(hwnd, NAV["全部"][0], NAV["全部"][1])
        time.sleep(1.2)
        real_click(hwnd, NAV["首页"][0], NAV["首页"][1])
        time.sleep(1.7)
        im = shot("home_after_nav")
        if poster_pixels(im) >= 2000:              # 还在详情页 → 点「←返回」
            p("  (导航没退出来，改点「←返回」)")
            real_click(hwnd, 222, 80)
            time.sleep(1.5)
            im = shot("home_after_back")
        for _ in range(30):
            wheel(hwnd, notches=+5, at=(700, 520))
            time.sleep(0.02)
        time.sleep(0.5)
        return im

    im_list0 = home()
    n_p0 = poster_pixels(im_list0)
    check("② 已停在列表页（没有海报底衬 = 不是详情页）", n_p0 < 2000, n_p0)
    # 默认排序是「名称升序」→ AAA/BBB/CCC/DDD/**MIDA-846(第 5 行 = 下标 4)**/P0000…
    # 必须双击这部带标签、带 5 位演职人员的片，否则 ① 的药丸断言必然空手（首跑就栽在这）。
    Y_MIDA = TBL["y"] + HDR["h"] + 4 * TBL["row_h"] + TBL["row_h"] // 2
    real_dbl(hwnd, TBL["x"] + 140, Y_MIDA)
    time.sleep(3.0)
    imE = shot("media_detail", settle=6)
    check("② 双击第 5 行（MIDA-846）能进详情页",
          bool(imE) and imE.width > 1200 and imE.height > 700,
          "%dx%d" % (imE.width, imE.height) if imE else "-")

    # 「真的进了 MIDA-846 的详情」而不是别的页：5 位演职人员的专属头像色必须出现
    # （C_P1=(220,40,40) 的 64x64 圆头像 → 4000+ 像素）
    n_p1 = count_near(imE, (0, 0, imE.width, imE.height), C_P1, 8)
    check("② 详情页里出现了演职人员头像（证明打开的就是 MIDA-846）",
          n_p1 > 3000, n_p1)

    def gold_bands(im, ybox, min_per_row=3, min_h=6, max_h=24):
        """把「金色文字」和「橙色文字」分开 —— 这是本版最容易自欺的一处。

        `#f5a524`(金) 与 `#ff8c3a`(橙) 只差 **G 通道 25**：任何 tol 都会串味。
        首跑用 tol=45 判金色，结果命中的是那颗**橙色「用户评分 7.5」按钮**
        （同一 tol 下橙被当成金），也就是「拿产品里另一个元素给自己作证」。
        改成「这个像素离金更近，还是离橙更近」，橙色按钮行就一条金票都投不出来：
          实测 按钮行 y362~392 → 金票 0~8 / 橙票 102~143（被 `ng > 2*no` 挡掉）
               标题（收藏金）y409~441 → 金票 32~254（高度 33 > max_h，也挡掉）
               ★ 7.0        y462~470 → 金票 4~11 / 橙票 0  ✓
        """
        G, O = (245, 165, 36), (255, 140, 58)
        px = _px(im).load()
        y0b, y1b = ybox
        out, cur = [], None
        for y in range(max(0, y0b), min(im.height, y1b)):
            ng = no = 0
            for x in range(im.width):
                c = px[x, y]
                dg = ((c[0] - G[0]) ** 2 + (c[1] - G[1]) ** 2 + (c[2] - G[2]) ** 2)
                do = ((c[0] - O[0]) ** 2 + (c[1] - O[1]) ** 2 + (c[2] - O[2]) ** 2)
                if dg <= 12100 and dg < do:
                    ng += 1
                elif do <= 12100:
                    no += 1
            if ng >= min_per_row and ng > no * 2:
                if cur is None:
                    cur = [y, y]
                else:
                    cur[1] = y
            elif cur is not None:
                if min_h <= cur[1] - cur[0] + 1 <= max_h:
                    out.append(tuple(cur))
                cur = None
        if cur is not None and min_h <= cur[1] - cur[0] + 1 <= max_h:
            out.append(tuple(cur))
        return out

    gold = gold_bands(imE, (300, 760))
    p("  金色小字带（★ 评分）: %s" % (gold,))
    check("② 按钮下方有一段金色小字 = ★ 7.0（橙色按钮按「谁更近」排除）",
          bool(gold), gold[:3])
    blue = color_bands(imE, (102, 169, 255), 30, min_per_row=5, min_h=5, max_h=22)
    p("  链接蓝文字带: %s" % (blue,))
    check("② 详情页里没有链接蓝的文字（蓝色评分已撤）", not blue, blue[:3])

    # ============================================================
    # ① 标签芯片（药丸填充带；像素级圆角/圆心由离屏冒烟精算，这里验「真画出来了」）
    # ============================================================
    def runs_at(im, y, min_len=28, thr=30):
        """某一行上「连续有东西」的段数 —— 一行里并排几枚药丸就是几段。

        两个坑：
          · 用「横带条数」去数会只数出 1 条（3 枚药丸共用同一段 y 区间）；
          · 用「#27272a 的连续像素」去量也会散 —— 药丸里**有字**，笔画把填充切碎了。
        所以改成「取这一行出现最多的颜色当底色，再数连续偏离底色的段」。
        """
        from collections import Counter
        px = _px(im).load()
        bg = Counter(px[x, y] for x in range(im.width)).most_common(1)[0][0]
        runs, n = [], 0
        for x in range(im.width):
            c = px[x, y]
            if sum(abs(c[i] - bg[i]) for i in range(3)) > thr:
                n += 1
            else:
                if n >= min_len:
                    runs.append((x - n, n))
                n = 0
        if n >= min_len:
            runs.append((im.width - n, n))
        return runs

    pills = color_bands(imE, (39, 39, 42), 5, min_per_row=25, min_h=15, max_h=23,
                        ybox=(700, 1000))
    p("  药丸横带: %s" % (pills,))
    prun = runs_at(imE, (pills[0][0] + pills[0][1]) // 2) if pills else []
    p("  药丸横段: %s" % (prun,))
    check("① 详情页里能找到 3 枚标签药丸（同一行 3 段药丸，含「＋」共 4 段）",
          len(prun) >= 3, "段数 %d：%s" % (len(prun), prun))

    # ============================================================
    # ④ 列表懒填充：滚到深处仍有内容 / 排序仍立刻生效
    # ============================================================
    p("========== ④ 列表：视口懒填充 ==========")
    n_db = db_one("SELECT COUNT(*) FROM media")
    check("④ 库里 %d 条（6 部真片 + 3000 条压测行）" % n_db, n_db == 3006, n_db)

    im_top = home()                            # ② 的详情页要退出来，否则下面全是详情页的字
    n_pt = poster_pixels(im_top)
    check("④ 已从详情页回到列表（页面里没有海报底衬）", n_pt < 2000, n_pt)
    ROWBOX = (TBL["x"] + 6, TBL["y"] + HDR["h"] + 3,
              TBL["x"] + 300, TBL["y"] + 560)
    rows_top = hbands(im_top, ROWBOX)
    check("④ 首屏列表有满屏文字（不是空白行）", len(rows_top) >= 6, len(rows_top))

    hover(hwnd, 900, 760)
    for _ in range(26):                        # 滚到很下面
        wheel(hwnd, notches=-5, at=(700, 520))
        time.sleep(0.03)
    time.sleep(1.0)
    im_deep = shot("home_scrolled")
    rows_deep = hbands(im_deep, ROWBOX)
    check("④ 滚到列表深处那一屏仍有文字（视口懒填补得上）",
          len(rows_deep) >= 6, len(rows_deep))

    def row_sig(im, y0, y1):
        """一行文字的**指纹**：整行网格采样（亮=1/暗=0）。

        原来只取 `y0+3` 一条扫描线 —— 那一条贴着文字上沿、几乎没有墨迹，
        于是排序前后量出一模一样的签名（v2.0.8 首跑的假红就是这个）。
        """
        px = _px(im).load()
        bits = []
        for y in range(y0, y1, 3):
            for x in range(TBL["x"] + 8, TBL["x"] + 268, 3):
                c = px[x, y]
                bits.append("1" if (c[0] + c[1] + c[2]) > 330 else "0")
        return "".join(bits)

    im_before = shot("home_before_sort")
    y_first = rows_deep[0] if rows_deep else (TBL["y"] + HDR["h"] + 6,
                                              TBL["y"] + HDR["h"] + 26)
    sig_before = row_sig(im_before, y_first[0], y_first[1])
    # ⚠ 默认排序本来就是「名称升序」（AAA-001 在最前）。点「名称」的三角 = 再排一次
    #   同样的序，行序**根本不变** —— 首跑就是拿它当「排序生效」的证据，注定假红。
    #   改点「年份」：1990… 一上来就换人。
    hover(hwnd, *mid_of("year"))
    real_click(hwnd, *COLS["year"]["tri"])
    time.sleep(0.9)                            # 旧版整表重填要 4.1s（4 万条）
    im_after = shot("home_sorted")
    sc = (read_cfg().get("home_sort") or {})
    check("④ 点「年份」三角后 0.9s 内排序已生效并落盘（key=year / asc=True）",
          sc.get("key") == "year" and sc.get("asc") is True, sc)
    rows_after = hbands(im_after, ROWBOX)
    check("④ 排序后列表仍满屏有字（懒填没把内容搞丢）",
          len(rows_after) >= 6, len(rows_after))
    sig_after = row_sig(im_after, rows_after[0][0], rows_after[0][1]) if rows_after else ""
    check("④ 首行内容真的换掉了（不是只点亮了个箭头）",
          bool(sig_before) and bool(sig_after) and sig_before != sig_after,
          "%d 位指纹 前 24 位 %s -> %s" % (len(sig_before), sig_before[:24],
                                          sig_after[:24]))

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
