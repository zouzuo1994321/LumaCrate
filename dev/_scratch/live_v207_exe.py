# -*- coding: utf-8 -*-
"""v2.0.7（Build 2611010128）打包后真机验收。

本轮三条反馈，真机上能**像素/数据自证**的都验：

  ① 演员详情页「别名」改白
     → 把「信息块」按文字横带切段，取白核像素最多的那条（= 最长的那行白字 = 别名），
       再取该带**最亮 25%** 像素的均值：
         链接蓝 #66a9ff → (102,169,255)，b-r=153
         近白   #fafafa → (250,250,250)，b-r=0
       ⚠ 不能用「整带均值」也不能用「逐像素判蓝」：
         · 整带均值把大量抗锯齿边缘算进去，白字只能量到 ~213；
         · 深色**彩色底**上 ClearType 会出彩边（红底上白字边缘带蓝），
           逐像素判蓝会捞出 300+ 个假蓝点（第一版就是这么假红的）。

  ② 详情节底部职务中文化 + 女>男>未知、演员>导演
     → 5 个头像喂 5 个**互不接近的纯色**照片，按色块几何位置读出真实显示顺序。
       职务名两枚汉字 vs 拉丁字母：量墨迹宽度 + **x 方向墨迹段数**
       （「演员」= 2 段，「Actor」= 5 段）—— 同时证明「已中文化」和「没被截断」。

  ③ 首页列表表头：每列左漏斗 / 右三角，点漏斗筛选、点三角排序
     → 坐标由 `coords_v207.py` 离屏按同一套算式算出（PAD+ICON/2）。
       4 列两枚图标都在 → 点三角两下（点亮 + 朝向翻转，看**最宽那行**判朝向，
       重心会判反）→ 点「年份」漏斗 → 灌 2024 → 只剩 1 行 + 落盘 + 漏斗变实心。

踩坑（沿用前几版，勿删）：
  · 验收副本**必须另起 ASCII 名**：启动时 `_kill_other_instances()` 会杀掉同名进程。
  · **上一轮残留的 exe 必须先杀掉再删库**，否则 sqlite 句柄还在 → 删不掉 →
    本轮 6 部片叠成 12 部（第一版就是这样，且双击到的是别人的行）。
  · `find_window(title_sub="Build")` —— 进程里第一个大窗口是启动画面（QSplashScreen）。
  · 点表头/卡片一律 PostMessage 到主窗 hwnd + **客户区坐标**；弹窗是独立顶层窗口。
  · Qt 的双击由 QGuiApplication 按「两次 press 的间隔/距离」自己判（<400ms 即可）。
  · 离屏算的坐标必须是 1920x1080 才对得上真机（coords 里有 main_size 校验）。
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
                    "lmc_exe_v207")
COORDS_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                           "lmc_coords_v207.json")
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
BUILD_TAG = "2611010128"
VER_TAG = "v2.0.7"

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
check("根目录最新 exe 就是 v2.0.7（2611010128）",
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
                    % os.path.join(DEV, "_scratch", "coords_v207.py")],
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
p("========== v2.0.7 真机验收（accent=#e4587c / 磨砂玻璃·低） ==========")
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
    im.save(os.path.join(SHOTS, "v207_%s.png" % tag))
    p("  图 %s  %dx%d" % ("v207_%s.png" % tag, im.width, im.height))
    return im


try:
    # ============================================================
    # ③ 表头：每列 左漏斗 / 右三角
    # ============================================================
    p("========== ③ 表头漏斗 / 三角 ==========")
    im0 = shot("home_hdr")
    check("窗口截图尺寸合理（>1200x700）",
          bool(im0) and im0.width > 1200 and im0.height > 700,
          "%dx%d" % (im0.width, im0.height) if im0 else "-")

    funnel_ok, tri_ok, detail_hdr = 0, 0, []
    for key, c in COLS.items():
        fx, fy = c["funnel"]
        tx, ty = c["tri"]
        nf = count_gray_icon(im0, (fx - 8, fy - 8, fx + 8, fy + 8))
        nt = count_gray_icon(im0, (tx - 7, ty - 7, tx + 7, ty + 7))
        detail_hdr.append("%s:%d/%d" % (key, nf, nt))
        funnel_ok += 1 if nf >= 12 else 0
        tri_ok += 1 if nt >= 6 else 0
    check("③ 每一列左边都画出了漏斗（4/4）", funnel_ok == 4, "  ".join(detail_hdr))
    check("③ 每一列右边都画出了排序三角（4/4）", tri_ok == 4, "  ".join(detail_hdr))

    ROWBOX = (TBL["x"] + 6, TBL["y"] + HDR["h"] + 3, TBL["x"] + 290, TBL["y"] + HDR["h"] + 420)
    rows0 = hbands(im0, ROWBOX)
    check("③ 列表初始 6 行", len(rows0) == 6, len(rows0))

    def tri_orient(im, key):
        """量三角朝向：**最宽的那一行**在上半还是下半。

        ⚠ 不能用重心 —— 三角形面积集中在底边，尖朝上的那份重心反而更靠下
        （实测 13.8 > 11.2，判反）。
        """
        tx, ty = COLS[key]["tri"]
        px = _px(im).load()
        rows = {}
        for y in range(ty - 8, ty + 9):
            n = 0
            for x in range(tx - 8, tx + 9):
                if near(px[x, y], ACCENT, 34):
                    n += 1
            if n:
                rows[y] = n
        if not rows:
            return "?", "无强调色"
        base = max(rows.items(), key=lambda kv: kv[1])[0]
        return ("up" if base > ty else "down"), "base=%d cy=%d %s" % (base, ty, rows)

    p("→ 点「标题」列三角（第 1 次：升序）")
    lv.click(hwnd, *COLS["title"]["tri"])
    time.sleep(1.6)
    im1 = shot("home_sort_asc")
    acc1 = count_near(im1, (COLS["title"]["tri"][0] - 8, COLS["title"]["tri"][1] - 8,
                            COLS["title"]["tri"][0] + 8, COLS["title"]["tri"][1] + 8),
                      ACCENT, 34)
    d1, det1 = tri_orient(im1, "title")
    check("③ 点三角后该列三角点亮（强调色实心）", acc1 >= 25, "accent_px=%d" % acc1)
    check("③ 升序时三角尖朝上（最宽的行在下方）", d1 == "up", det1)

    p("→ 再点一次（第 2 次：降序）")
    lv.click(hwnd, *COLS["title"]["tri"])
    time.sleep(1.6)
    im2 = shot("home_sort_desc")
    d2, det2 = tri_orient(im2, "title")
    check("③ 再点一次三角 → 方向翻转（尖朝下）", d2 == "down", det2)
    sort_cfg = (read_cfg().get("home_sort") or {})
    check("③ 排序偏好已落盘（key=title / asc=False）",
          sort_cfg.get("key") == "title" and sort_cfg.get("asc") is False, sort_cfg)

    # ============================================================
    # ③ 点漏斗 → 筛选面板 → 真的筛出结果
    # ============================================================
    # 面板有两种形态：数值列（= ≥ ≤ + 输入框）、枚举列（一排胶囊 = 「下拉框」）。
    # 两条都验：先开数值列证明「输入框」在，再走枚举列把筛选真正施加下去
    # ——键入这条路在本机**打不进字**（见下面 `type_text(hwnd, …)` 的注释），
    # 所以「筛选生效」的证据落在胶囊上，输入框只做「形态存在 + 能出现在面板里」的佐证。

    def open_filter(col):
        for _ in range(2):                      # 先 Esc 清掉残留面板
            lv.u32.PostMessageW(hwnd, WM_KEYDOWN, 0x1B, 0)
            lv.u32.PostMessageW(hwnd, WM_KEYUP, 0x1B, 0)
            time.sleep(0.25)
        lv.click(hwnd, *COLS[col]["funnel"])
        time.sleep(1.4)
        return lv.find_modal(EXE_NAME, [proc.pid], exclude=(hwnd,), timeout=8)

    def text_clusters(im, box, thr=150, gap=7):
        """一行文字按「词间距」归并成若干块（= 一排胶囊各自的文字）。"""
        cl, cur = [], None
        for r in ink_runs(im, box, thr=thr, gap=3):
            if cur is None:
                cur = [r[0], r[1]]
            elif r[0] - cur[1] <= gap:
                cur[1] = r[1]
            else:
                cl.append(tuple(cur))
                cur = [r[0], r[1]]
        if cur:
            cl.append(tuple(cur))
        return cl

    def popup_rect(pop):
        r_ = ctypes.wintypes.RECT()
        lv.u32.GetWindowRect(pop, ctypes.byref(r_))
        return r_.right - r_.left, r_.bottom - r_.top, r_.left, r_.top

    applied_key, applied_spec = None, None

    # ---- ③-1 数值列（年份）：面板里应有「= ≥ ≤」+ 输入框 ----
    pop = open_filter("year")
    check("③ 点「年份」列漏斗弹出筛选面板（独立小窗）", pop is not None, pop)
    if pop:
        pw, ph = popup_rect(pop)[:2]
        p("  面板 %dx%d" % (pw, ph))
        check("③ 面板尺寸合理（宽 240~460、高 70~260）",
              240 <= pw <= 460 and 70 <= ph <= 260, "%dx%d" % (pw, ph))
        crop = grab_popup(pop)[0]
        if crop is not None:
            crop.save(os.path.join(SHOTS, "v207_popup_num.png"))
            # 运算符胶囊（= ≥ ≤）那一行：数一下有几块 → 3 块即「数值形态」
            chips = text_clusters(crop, (0, int(crop.height * 0.18),
                                         crop.width, int(crop.height * 0.42)))
            check("③ 数值列面板有「= ≥ ≤」三枚运算符（可切换比较符）",
                  len(chips) >= 3, "%d 块 %s" % (len(chips), chips))
            # 键入：向**主窗**投 WM_CHAR —— Qt 会把 App 内的按键转发给当前 popup。
            # （实测：直接投给 popup 窗口、或真实键盘 keybd_event，都进不去，
            #   因为 popup 窗口拿不到原生激活；只有 App 内的转发链能到 QLineEdit。）
            type_text(hwnd, "2024")
            time.sleep(0.5)
            crop2 = grab_popup(pop)[0] or crop
            crop2.save(os.path.join(SHOTS, "v207_popup_num_typed.png"))
            typed = ink_count(crop2, (10, int(crop2.height * 0.34),
                                      crop2.width - 10, int(crop2.height * 0.66)))
            p("  键入后输入框内亮色像素=%d / 面板还在=%s"
              % (typed, bool(lv.u32.IsWindow(pop))))
            # 回车 = QLineEdit.returnPressed → 直接 _apply()。
            # 比「按坐标点确定」稳：面板只有 253x149，按钮 49x25，坐标一偏就点到空地。
            check("③ 输入框能接受键入（面板里出现亮色数字）", typed >= 35, typed)
            lv.u32.PostMessageW(hwnd, WM_KEYDOWN, 0x0D, 0)
            time.sleep(0.06)
            lv.u32.PostMessageW(hwnd, WM_KEYUP, 0x0D, 0)
            time.sleep(1.6)
            applied_spec = (read_cfg().get("home_filters") or {}).get("year")
            if not applied_spec and lv.u32.IsWindow(pop):
                click_confirm(pop, crop2)
                time.sleep(1.8)
                applied_spec = (read_cfg().get("home_filters") or {}).get("year")
            if applied_spec:
                applied_key = "year"
                p("  数值筛选已生效：%s" % (applied_spec,))
        if applied_key is None and lv.u32.IsWindow(pop):
            lv.u32.PostMessageW(pop, lv.WM_CLOSE, 0, 0)
        time.sleep(0.7)

    # ---- ③-2 枚举列（收藏）：一排胶囊 = 「下拉框」，点一下就选 ----
    if applied_key is None:
        p("→ 改走枚举列「收藏」的胶囊（下拉框形态）")
        pop = open_filter("favorite")
        check("③ 点「收藏」列漏斗也能弹出面板", pop is not None, pop)
        if pop:
            crop = grab_popup(pop)[0]
            if crop is not None:
                crop.save(os.path.join(SHOTS, "v207_popup_eq.png"))
                bands = hbands(crop, (0, 0, crop.width, int(crop.height * 0.60)),
                               thr=150, gap=3)
                p("  面板文字行 %s" % (bands,))
                if len(bands) >= 2:
                    y0, y1 = bands[1]                    # 第 2 行 = 胶囊行
                    cl = text_clusters(crop, (0, y0, crop.width, y1 + 1), thr=150, gap=10)
                    # 面板右边缘常有 1~2px 的描边/滚动条被算成一块，按宽度滤掉
                    cl = [c for c in cl if c[1] - c[0] >= 6]
                    p("  胶囊文字块 %s" % (cl,))
                    check("③ 枚举列面板是「一排胶囊」（全部 / 已收藏 / 未收藏）",
                          len(cl) == 3, cl)
                    if len(cl) >= 2:
                        cx = (cl[1][0] + cl[1][1]) // 2
                        real_click_popup(pop, cx, (y0 + y1) // 2)
                        time.sleep(0.6)
                        crop = grab_popup(pop)[0] or crop
                        crop.save(os.path.join(SHOTS, "v207_popup_eq_checked.png"))
                click_confirm(pop, crop)
                time.sleep(1.8)
                applied_spec = (read_cfg().get("home_filters") or {}).get("favorite")
                if not applied_spec:
                    p("  点确定没生效，面板还在=%s" % bool(lv.u32.IsWindow(pop)))
                if applied_spec:
                    applied_key = "favorite"
            if applied_key is None and lv.u32.IsWindow(pop):
                lv.u32.PostMessageW(pop, lv.WM_CLOSE, 0, 0)
            time.sleep(0.7)

    EXPECT_ROWS = {"year": 1, "favorite": 2}
    check("③ 面板的选择真的提交了（筛选条件落盘）",
          applied_key is not None, "%s=%s" % (applied_key, applied_spec))
    if applied_key:
        im3 = shot("home_filtered")
        rows1 = hbands(im3, ROWBOX) if im3 else []
        check("③ 筛选后列表行数变少（%s 只剩 %d 行，原本 6 行）"
              % (applied_key, EXPECT_ROWS[applied_key]),
              len(rows1) == EXPECT_ROWS[applied_key], len(rows1))
        ffx, ffy = COLS[applied_key]["funnel"]
        acc_f = count_near(im3, (ffx - 8, ffy - 8, ffx + 8, ffy + 8), ACCENT, 34) if im3 else 0
        other = "user_rating" if applied_key != "user_rating" else "year"
        ox2, oy2 = COLS[other]["funnel"]
        acc_o = count_near(im3, (ox2 - 8, oy2 - 8, ox2 + 8, oy2 + 8), ACCENT, 34) if im3 else 0
        check("③ 已筛选那列的漏斗变强调色实心、没筛的列仍是灰",
              acc_f >= 30 and acc_o < 12, "%s=%d %s=%d" % (applied_key, acc_f, other, acc_o))

    # ⚠ 收尾必做：残留的 Qt.Popup 会**吞掉后续所有点击**（第一个点击只是把面板关掉，
    #    第二下才落到卡片上，于是「双击卡片」只剩单击 → 页面根本没跳）。
    for _ in range(3):
        left = lv.find_modal(EXE_NAME, [proc.pid], exclude=(hwnd,), timeout=0.6)
        if not left:
            break
        lv.u32.PostMessageW(left, lv.WM_CLOSE, 0, 0)
        lv.u32.PostMessageW(hwnd, WM_KEYDOWN, 0x1B, 0)
        lv.u32.PostMessageW(hwnd, WM_KEYUP, 0x1B, 0)
        time.sleep(0.5)
    check("③ 筛选面板用完即关（不留悬浮窗挡住后面的点击）",
          lv.find_modal(EXE_NAME, [proc.pid], exclude=(hwnd,), timeout=0.8) is None)

    # ============================================================
    # ① + ② 演员库 → 演员详情（别名白）→ 她的作品 → 媒体详情（演职人员）
    # ============================================================
    p("→ 进演员库 → 双击「女演员甲」")
    lv.click(hwnd, *NAV["演员库"])
    time.sleep(3.0)
    im5, b1 = None, None
    for _i in range(6):
        im5 = shot("actor_lib_%d" % _i, settle=8)
        if im5 is not None:
            b1 = find_box(im5, C_P1, 18, 3)
            if b1:
                break
        time.sleep(1.2)
    check("① 演员库里定位到目标演员卡（纯色照片）", b1 is not None, b1)

    if b1:
        real_dbl(hwnd, (b1[0] + b1[2]) // 2, (b1[1] + b1[3]) // 2)
        time.sleep(2.8)
        im6 = shot("actor_detail", settle=6)
        # 信息块：照片右侧那块（x 380~1300、顶部 y 40~320）
        box = (380, 40, min(1300, im6.width - 1), min(320, im6.height - 1))
        best = None
        for (y0, y1) in hbands(im6, box, thr=140, gap=4):
            n, col, topn = band_top_color(im6, (box[0], y0, box[2], y1 + 1))
            if col is None:
                continue
            white_core = count_near(im6, (box[0], y0, box[2], y1 + 1), (250, 250, 250), 6)
            if best is None or white_core > best[0]:
                best = (white_core, y0, y1, col, n)
        check("① 信息块里量到一条「白核最多」的文字带（= 别名那一行）",
              bool(best) and best[0] >= 60, best[:3] if best else None)
        if best:
            alias_col = best[3]
            p("  别名带 y=%d~%d  白核=%d  最亮25%%均值=%s"
              % (best[1], best[2], best[0], alias_col))
            check("① 那一行是近白 #fafafa（最亮25%均值 r>=235 且 |b-r|<=14）",
                  alias_col[0] >= 235 and abs(alias_col[2] - alias_col[0]) <= 14, alias_col)
            check("① 该行不含链接蓝 #66a9ff 的色调（b-r=153）",
                  (alias_col[2] - alias_col[0]) < 40, "b-r=%d" % (alias_col[2] - alias_col[0]))

    # ---- 从演员页双击她的作品卡 → 媒体详情 ----
    p("→ 双击演员页里的作品卡 → 媒体详情（演职人员）")
    im7 = shot("actor_works", settle=4)
    pb = find_box(im7, (90, 150, 110), 12, 2) if im7 else None
    check("② 演员页里定位到作品海报", pb is not None, pb)
    if pb:
        real_dbl(hwnd, (pb[0] + pb[2]) // 2, (pb[1] + pb[3]) // 2)
        time.sleep(3.0)
        im4, found = None, []
        for _i in range(10):
            im4 = shot("media_detail_%d" % _i, settle=5)
            if im4 is None:
                break
            found = [(c, find_box(im4, c, 18, 2)) for c in PHOTO_COLORS]
            got = [(c, b) for c, b in found if b]
            if len(got) >= 5:
                p("  5 个头像全部到齐（第 %d 帧）" % _i)
                break
            wheel(hwnd, notches=-3)
            time.sleep(1.3)
        boxes = {c: b for c, b in found if b}
        check("② 5 个头像全部定位到（纯色照片）", len(boxes) == 5,
              {c: b for c, b in boxes.items()})

        if len(boxes) == 5:
            items = sorted(boxes.items(), key=lambda kv: (kv[1][1] // 40, kv[1][0]))
            order = [EXPECT_ORDER[PHOTO_COLORS.index(c)] for c, _ in items]
            check("② 演职人员显示顺序 = 女>男>未知、演员>导演", order == EXPECT_ORDER, order)
            check("② 入库 person_order 是乱序的（证明真按新规则重排）",
                  db_one("SELECT person_order FROM media_people WHERE media_id=? AND "
                         "person_id=?", (M0, PIDS["女演员甲"])) == 2,
                  "女演员甲 person_order=2")

            role_det, role_ok = [], 0
            for c, b in items:
                nm = EXPECT_ORDER[PHOTO_COLORS.index(c)]
                bb = (b[0] - 24, b[3] + 2, b[2] + 24, min(b[3] + 68, im4.height - 1))
                bs = hbands(im4, bb, thr=150, gap=2)
                if not bs:
                    role_det.append("%s:无字" % nm)
                    continue
                y0, y1 = bs[-1]
                runs = ink_runs(im4, (bb[0], y0, bb[2], y1 + 1), thr=150, gap=2)
                total_w = (runs[-1][1] - runs[0][0] + 1) if runs else 0
                role_det.append("%s:%d段/%dpx" % (nm, len(runs), total_w))
                if len(runs) == 2 and 14 <= total_w <= 30:
                    role_ok += 1
            check("② 职务名已中文化（每条职务带 = 2 枚汉字、宽 14~30px；`Actor` 会是 4~5 段）",
                  role_ok == 5, "  ".join(role_det))
            im4.save(os.path.join(SHOTS, "v207_cast_roles.png"))
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
    print("LIVE_V207_FAIL", len(FAILS), flush=True)
else:
    print("LIVE_V207_ALL_OK", len(OKS), flush=True)
