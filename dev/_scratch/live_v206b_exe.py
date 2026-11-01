# -*- coding: utf-8 -*-
"""v2.0.6（Build 2611010127）打包后真机验收。

本轮四条反馈，真机上能**像素/数据自证**的都验：
  ① 详情页「评分」金色 / 评过之后「用户评分 7.5」橙色加粗
     → 两态各进一次详情页，量「暖色像素」的中位 g/r 比（金 0.67 / 橙 0.55），
       不靠坐标也不靠猜：页面里除这两处外没有暖色元素（海报刻意选洋红/墨绿，
       质量徽章留空，收藏 = 0 所以标题不是金色）。
  ② 重复检测结果：打开 / 定位 / 删除（删前确认是否删源文件）
     → 工具窗里真跑一次「开始检测 → 选中一行 → 删除… → 删除影片文件… →
        确认框点红色「删除」」，然后**从进程外读库 + 看磁盘**：
        两份副本只剩一份、索引也只剩一条。
  ③ 演职人员 ＋ / ×、标签 ×（反馈 3、4）
     → 真机点一次「第一位演职员的 ×」和「第一枚标签的 ×」，再回读库：
        media_people 3→2、tags 2→1。两个 × 的位置靠**颜色定位**（头像用纯色圆图、
        标签芯片用底色 #27272a），不用死坐标 —— 版面随文案变也不会点空。

踩坑（沿用前几版，勿删）：
  · 验收副本**必须另起 ASCII 名**：启动时 `_kill_other_instances()` 会杀掉同名进程。
  · 工具窗刚 show 时控件没建完 → 先等 2.6s，否则 grabWindow 拿到 0×0。
  · Qt 的双击是 QGuiApplication 按「两次 press 的时间/距离」自己判的，
    PostMessage 两次 down/up 就能触发（间隔要 < 400ms），不必真发 WM_LBUTTONDBLCLK。
  · QMenu 是**独立顶层窗口**：把鼠标消息投给对话框点不到菜单项，得先枚举出
    那个小窗口再往它里面投。
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
                    "lmc_exe_v206b")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv          # noqa: E402
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication      # noqa: E402
from PIL import Image, ImageDraw                # noqa: E402

os.makedirs(SHOTS, exist_ok=True)
FAILS, OKS = [], []
T0 = time.time()
BUILD_TAG = "2611010127"
VER_TAG = "v2.0.6"

# 预置素材的专属色（互不接近，且都不是「暖色」，不干扰评分那两项的量色）
C_MAGENTA = (128, 48, 176)      # 未打分那部的海报
C_TEAL = (48, 150, 132)         # 已打分那部的海报
C_AV1 = (60, 120, 220)          # 第 1 位演职员的头像（纯色圆图）
C_AV2 = (150, 60, 210)
C_AV3 = (30, 170, 190)
CHIP_BG = (39, 39, 42)          # 标签芯片底色 #27272a


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


def find_box(im, rgb, tol=14, step=2):
    """整图里找近似 rgb 的色块外接矩形（定位预置的海报 / 纯色头像）。"""
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


def is_warm(c):
    """金 / 橙的共同特征：红高、蓝极低。

    ⚠ 必须把「蓝 <= 90」也写进来：主题强调色是 #e4587c（洋红），r-b=104、r-g=140，
    前三条全过 —— 第一轮就是这么把整页粉色 UI 当成「评分按钮」量出 4336 个暖像素
    （中位 g/r=0.386）的。金 #f5a524 蓝=36、橙 #ff8c3a 蓝=58，都稳稳 <90。
    """
    r, g, b = c
    return r >= 140 and b <= 90 and (r - b) >= 90 and (r - g) >= 25


def warm_stats(im, box):
    """暖色像素数 + 中位 g/r 比。金 #f5a524 → 0.673；橙 #ff8c3a → 0.549。"""
    x0, y0, x1, y1 = box
    px = im.load()
    rs, gs = [], []
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            c = px[x, y]
            if is_warm(c):
                rs.append(c[0])
                gs.append(c[1])
    if not rs:
        return 0, None
    ratios = sorted(g / float(r) for r, g in zip(rs, gs))
    return len(ratios), ratios[len(ratios) // 2]


def max_bright(im, box):
    x0, y0, x1, y1 = box
    px = im.load()
    best = 0
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            r, g, b = px[x, y]
            v = (r + g + b) // 3
            if v > best:
                best = v
    return best


def dblclick(hwnd, x, y):
    """双击 = move / down / up / **dblclk** / up。

    ⚠ Qt 在 Windows 上只认系统发来的 WM_LBUTTONDBLCLK（qwindows 插件那条），
    自己连投两次 down/up **不会**被合成为双击 —— 第一轮就是这么「双击」了卡片，
    结果页面纹丝不动（截下来的还是海报墙，后面对着色块去找演员头像自然全错）。
    """
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    WM_LBUTTONDBLCLK = 0x0203
    lv.u32.PostMessageW(hwnd, lv.WM_MOUSEMOVE, 0, lp)
    time.sleep(0.05)
    lv.u32.PostMessageW(hwnd, lv.WM_LBUTTONDOWN, 1, lp)
    time.sleep(0.05)
    lv.u32.PostMessageW(hwnd, lv.WM_LBUTTONUP, 0, lp)
    time.sleep(0.05)
    lv.u32.PostMessageW(hwnd, WM_LBUTTONDBLCLK, 1, lp)
    time.sleep(0.05)
    lv.u32.PostMessageW(hwnd, lv.WM_LBUTTONUP, 0, lp)


def key(hwnd, vk):
    lv.u32.PostMessageW(hwnd, lv.WM_KEYDOWN, vk, 0)
    time.sleep(0.06)
    lv.u32.PostMessageW(hwnd, lv.WM_KEYUP, vk, 0)
    time.sleep(0.25)


def real_click(hwnd, cx, cy):
    """真鼠标点一下（SetCursorPos + mouse_event），用于**弹出菜单**。

    QMenu / 下拉这种 popup 是靠 hover 设 currentAction、release 时触发，
    投递的合成消息经常「菜单关掉了、项却没选中」（实测连续两轮都是这样）。
    真输入走的是系统那条路，和用户手点完全一致。
    """
    lv.u32.SetForegroundWindow(hwnd)
    pt = ctypes.wintypes.POINT(int(cx), int(cy))
    lv.u32.ClientToScreen(hwnd, ctypes.byref(pt))
    lv.u32.SetCursorPos(pt.x, pt.y)
    time.sleep(0.2)
    lv.u32.mouse_event(0x0002, 0, 0, 0, 0)      # LEFTDOWN
    time.sleep(0.09)
    lv.u32.mouse_event(0x0004, 0, 0, 0, 0)      # LEFTUP
    time.sleep(0.2)


def real_click_at(sx, sy):
    """真鼠标点**屏幕绝对坐标**（不做 ClientToScreen 换算）。

    为什么非要有这一版：确认框是**半透明无边框**窗口，`GetWindowRect` 拿到的那块
    区域未必等于 `PostMessage` 认的客户区（实测截图里红按钮在 (484..549, 279..309)，
    按客户区坐标投 WM_LBUTTONDOWN 却毫无反应 —— 连按三次都没关框）。真鼠标不管
    窗口身份、也不管客户区原点，屏幕上是哪块就点哪块，和我们自己用手点一模一样。
    """
    lv.u32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.25)
    lv.u32.mouse_event(0x0002, 0, 0, 0, 0)      # LEFTDOWN
    time.sleep(0.10)
    lv.u32.mouse_event(0x0004, 0, 0, 0, 0)      # LEFTUP
    time.sleep(0.25)


def win_alive(h):
    return bool(lv.u32.IsWindow(h) and lv.u32.IsWindowVisible(h))


VK_DOWN, VK_RETURN = 0x28, 0x0D


def _win_class(h):
    buf = ctypes.create_unicode_buffer(256)
    lv.u32.GetClassNameW(h, buf, 256)
    return buf.value


def top_windows(exe_name, extra, exclude=(), max_h=320, min_w=100):
    """本进程里**除主窗/工具窗之外**的可见顶层窗口。

    返回值带**窗口类名**：QMenu 是 `Qt6xxxQWindowPopupDropShadowSaveBits`，
    而它的投影是 `SysShadow`（点它什么都不会发生），tooltip 则另有其类。
    只靠尺寸/标题分不开（实测 tooltip 与菜单都是 152x80/157x85 这一档）。
    """
    pids = lv.pids_of_exe(exe_name) | set(extra)
    hits = []

    def cb(h, _):
        if h in exclude or not lv.u32.IsWindowVisible(h):
            return True
        if lv.wpid(h) not in pids:
            return True
        r = ctypes.wintypes.RECT()
        lv.u32.GetWindowRect(h, ctypes.byref(r))
        w, ht = r.right - r.left, r.bottom - r.top
        if w >= min_w and 20 <= ht <= max_h:
            hits.append((h, w, ht, lv.wtitle(h), _win_class(h)))
        return True

    lv.u32.EnumWindows(lv.EnumWindowsProc(cb), 0)
    return hits


def find_avatar(im):
    """按「纯色头像」反查第一位演职员的位置。

    必须要求**方块状**（宽高都 ≥50）：第一轮在**海报墙**上按颜色找，量到的是
    一条 y0==y1 的横线（海报卡片的高亮边），拿它去点等于乱点。
    """
    for rgb in (C_AV1, C_AV2, C_AV3):
        box = find_box(im, rgb, tol=10, step=1)
        if box and (box[2] - box[0]) >= 50 and (box[3] - box[1]) >= 50:
            return box
    return None


def chip_row(im, y_lo, span=800):
    """从 y_lo 往下找「一横排标签芯片」，返回 (行中心 y, [芯片 x 区间…])。

    实测（dev/_scratch/ana_v206_chips.py 对真机截图逐行统计）：芯片那一排的
    **上内边距**干净可读 —— 芯片底色恰好 #27272a，两枚各 67px、中间隔 11px：
        814: [(215, 281), (292, 358)]
    再往下一行走过字形，颜色被打断成十几段。所以：
      · 合并间隙只放 4px（字形断口 1~2px，芯片之间的间隙 11px —— 之前放到 12px
        把两枚芯片并成一条 143px 的长条，再接「宽度 ≤90」一筛就全没了）；
      · 宽度 40~120、两两间隙 ≤16、自上而下取**第一条**（下面的「文件信息」区
        也有一排深色行，之前挑最多的那行就挑到它去了）；
      · 芯片高约 18px，返回的 y 再 +8 落在芯片中线上，点 × 更稳。
    """
    px = im.load()
    for y in range(y_lo, min(im.height - 16, y_lo + span), 2):
        xs = [x for x in range(200, min(1500, im.width)) if near(px[x, y], CHIP_BG, 4)]
        if len(xs) < 90:
            continue
        runs, cur = [], None
        for x in xs:
            if cur is None:
                cur = [x, x]
            elif x - cur[1] <= 4:
                cur[1] = x
            else:
                runs.append(tuple(cur))
                cur = [x, x]
        if cur:
            runs.append(tuple(cur))
        chips = [r for r in runs if 40 <= r[1] - r[0] <= 120]
        if len(chips) < 2 or not (0 <= chips[1][0] - chips[0][1] <= 16):
            continue
        return y + 8, chips
    return None, []


os.makedirs(TEMP, exist_ok=True)
src = lv.newest_exe()
p("新 exe:", src)
assert src and os.path.exists(src)
check("根目录最新的 exe 就是 v2.0.6（2611010127）",
      VER_TAG in os.path.basename(src) and BUILD_TAG in os.path.basename(src),
      os.path.basename(src))
exe = os.path.join(TEMP, "LMC-probe-%s.exe" % BUILD_TAG)
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)
EXE_NAME = os.path.basename(exe).lower()

# ---------------- 预置环境 ----------------
LIB = os.path.join(TEMP, "lib")
for _d in ("A", "B"):
    os.makedirs(os.path.join(LIB, _d, "ID-900"), exist_ok=True)
POSTER_A = os.path.join(TEMP, "poster_a.png")
POSTER_B = os.path.join(TEMP, "poster_b.png")
for _pth, _col in ((POSTER_A, C_MAGENTA), (POSTER_B, C_TEAL)):
    _img = Image.new("RGB", (316, 472), _col)
    _dr = ImageDraw.Draw(_img)
    _dr.rectangle([12, 12, 303, 210], fill=tuple(min(255, v + 40) for v in _col))
    _img.save(_pth)
THUMBS = []
for _i, _col in enumerate((C_AV1, C_AV2, C_AV3)):
    _pth = os.path.join(TEMP, "thumb_%d.png" % _i)
    Image.new("RGB", (200, 200), _col).save(_pth)
    THUMBS.append(_pth)

# 两份真正的「同名同大小」副本（删除流程要有真文件可删）
DUP = []
for _d in ("A", "B"):
    _fp = os.path.join(LIB, _d, "ID-900", "ID-900.mp4")
    with open(_fp, "wb") as _f:
        _f.write(b"\0" * 4096)
    DUP.append(_fp)

cfg_path = os.path.join(TEMP, "settings.json")
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "真机库", "kind": "电影", "paths": [LIB], "filter": {}}],
               "appearance": {"accent": "#e4587c", "mode": "磨砂玻璃", "level": "低"}},
              f, ensure_ascii=False)
os.environ["LMC_CONFIG"] = cfg_path
IDX = os.path.join(TEMP, "index_data")
LOG = os.path.join(IDX, "logs", "app.log")
DBF = os.path.join(IDX, "media_center.db")

subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
if os.path.isdir(IDX):
    for fn in os.listdir(IDX):
        if fn.lower().endswith((".db", ".db-wal", ".db-shm")):
            _del(os.path.join(IDX, fn))
os.makedirs(IDX, exist_ok=True)
_del(LOG)

sys.path.insert(0, os.path.join(ROOT, "src"))
import database as db          # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: DBF
applog.log_dir = lambda: os.path.join(IDX, "logs")
db.init_db()

MA = db.insert_media(title="未打分的那部", kind="movie", year=2024, rating=8.2,
                     file_path=os.path.join(TEMP, "fake", "a.mp4"), library="真机库",
                     sort_title="a", poster=POSTER_A, favorite=0,
                     added_time="2026-11-01 12:00:00", added_date="2026-11-01")
MB = db.insert_media(title="打过分的这部", kind="movie", year=2023, rating=7.8,
                     file_path=os.path.join(TEMP, "fake", "b.mp4"), library="真机库",
                     sort_title="b", poster=POSTER_B, favorite=0, user_rating=7.5,
                     tags="标签甲,标签乙",
                     added_time="2026-11-01 11:00:00", added_date="2026-11-01")
CAST_IDS = []
for _i, (_nm, _role) in enumerate((("真机女优甲", "Actor"), ("真机女优乙", "Actor"),
                                   ("真机导演丙", "Director"))):
    _pid = db.upsert_person(_nm, _role, thumb=THUMBS[_i])
    db.link_media_person(MB, _pid, "", _i)
    CAST_IDS.append(_pid)
DUP_IDS = []
for _fp in DUP:
    DUP_IDS.append(db.insert_media(title="重复的那部", kind="movie", year=2020, rating=6.0,
                                   file_path=_fp, library="真机库", sort_title="dup",
                                   added_time="2026-10-01 10:00:00", added_date="2026-10-01"))
p("预置：未打分 id=%s / 已打分 id=%s（演职员 %s）/ 重复 id=%s"
  % (MA, MB, len(CAST_IDS), DUP_IDS))


def db_one(sql, args=()):
    con = sqlite3.connect(DBF, timeout=8)
    try:
        row = con.execute(sql, args).fetchone()
        return row[0] if row else None
    finally:
        con.close()


# ============================================================
p("========== v2.0.6 真机验收（accent=#e4587c / 磨砂玻璃·低） ==========")
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=120, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)

COORDS = json.load(open(lv.COORDS, encoding="utf-8"))
TOOLS_BTN = tuple(COORDS["main_settings_btn"])
# 「全部」页（侧栏 y≈360）才是海报墙；「最近播放」在这台机器上是一片空（真机截图
# dbg_nav_160.png 内容区只有 398 个亮像素），别拿它当墙用 —— 这是第一轮假红的原因。
NAV_WALL = (90, 360)
V206 = json.load(open("C:/Users/zouzu/AppData/Local/Temp/lmc_coords_v206.json",
                      encoding="utf-8"))
DD_NAV = tuple(V206["dedupe_nav"])
# ⚠ 离屏算出来的 dd_start_btn=(470,240) 是**别页**的「开始检测」（dialog.findChildren
#   把「演员检测 / 图像检测」页的同类按钮也扫进来了）。真机截图里它在右上角：
#   1320×960 的窗口、按钮中心 ≈ (1234, 255)。
DD_START = (1234, 255)
DD_DEL = tuple(V206["dd_del"])
DD_TREE = tuple(V206["dd_tree"])
DD_BTNS = [tuple(V206[k]) for k in ("dd_play", "dd_reveal", "dd_open_dir", "dd_del")]
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


def find_poster(im, rgb, tol=12, min_pts=300):
    """在影片墙上定位一块**海报大小**的色块（不是「所有同色像素的外接框」）。

    第一轮直接用 find_box 取外接框，结果 (48,150,132) 那把量出 62..568 × 198..1036
    的巨框（页面上零散同色像素把它撑大了）→ 双击点在了空白处，页面纹丝不动。
    这里先按「中位数中心」聚一簇，再要求尺寸像海报（宽 100~280 / 高 150~420）。
    """
    px = im.load()
    pts = []
    for y in range(60, min(im.height, 960), 2):
        for x in range(210, im.width - 16, 2):
            if near(px[x, y], rgb, tol):
                pts.append((x, y))
    if len(pts) < min_pts:
        return None
    xs = sorted(p[0] for p in pts)
    ys = sorted(p[1] for p in pts)
    mx, my = xs[len(xs) // 2], ys[len(ys) // 2]
    keep = [(x, y) for x, y in pts if abs(x - mx) <= 150 and abs(y - my) <= 180]
    if len(keep) < min_pts:
        return None
    bx0 = min(p[0] for p in keep)
    bx1 = max(p[0] for p in keep)
    by0 = min(p[1] for p in keep)
    by1 = max(p[1] for p in keep)
    if not (100 <= bx1 - bx0 <= 280 and 150 <= by1 - by0 <= 420):
        return None
    return (bx0, by0, bx1, by1)


def shot_rect(hwnd, tries=10, gap=0.5):
    """按窗口矩形抓**屏幕**上的那一片（不用 grabWindow(hwnd)）。

    为什么：`DupDeleteDialog` 是半透明（WA_TranslucentBackground）的无边框窗口，
    `grabWindow(hwnd)` 对它做 BitBlt 长期返回 0×0 —— 连试 14 次都拿不到图，
    于是「找红色删除按钮」这一步整体被跳过，确认框一直开着（上一轮的现象）。
    改成抓桌面那块区域（0 = 屏幕）就绕开了逐窗口合成的限制。
    """
    r = ctypes.wintypes.RECT()
    lv.u32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w < 50 or h < 50:
        return None
    for _ in range(tries):
        pm = app.primaryScreen().grabWindow(0, r.left, r.top, w, h)
        if pm is not None and pm.width() >= w - 2 and pm.height() >= h - 2:
            pm.save(TMPPNG, "PNG")
            return Image.open(TMPPNG).convert("RGB")
        time.sleep(gap)
        app.processEvents()
    return None


def _count_near(im, rgb, tol=12):
    px = im.load()
    n = 0
    for y in range(60, min(im.height, 960), 2):
        for x in range(210, im.width - 16, 2):
            if near(px[x, y], rgb, tol):
                n += 1
    return n


def open_card_by_color(h, rgb, other_rgb, tries=4):
    """在「全部」影片墙上按海报色块找到卡片并双击进详情页。

    返回 (图, 是否真的进了详情页)。判据：墙上同时躺着两部的海报，
    进详情页后**只剩这一部**的海报色 → 「另一部」的海报色必须消失。
    光判「图抓到了」是不够的（第一轮就是这么假绿的）。
    """
    for _ in range(tries):
        im = shot(h, min_w=1500, tries=6)
        if im is None:
            continue
        box = find_poster(im, rgb)
        if not box:
            tag = "%s_%s" % (rgb, int(time.time() - T0))
            im.save(os.path.join(SHOTS, "dbg_noposter_%s.png" % tag))
            p("  没找到 %s 的海报色块（点数 %d），已存 dbg_noposter_%s.png"
              % (rgb, _count_near(im, rgb), tag))
            time.sleep(0.8)
            continue
        cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
        p("  卡片 %s 外接框 %s → 双击 (%d,%d)" % (rgb, box, cx, cy))
        dblclick(h, cx, cy)
        time.sleep(2.2)
        im2 = shot(h, min_w=1500, tries=8)
        if im2 is None:
            continue
        still = find_poster(im2, other_rgb)
        if still:
            p("  另一部的海报还在 %s → 没进详情页，重试" % (still,))
            continue
        return im2, True
    return None, False


DETAIL_BOX = None      # 内容区（排除侧栏与底栏），量暖色只在这里量
if hwnd:
    title = lv.wtitle(hwnd)
    p("  title:", title)
    check("标题含 v2.0.6", VER_TAG in title, title)
    check("标题含构建号 2611010127", BUILD_TAG in title, title)
    time.sleep(6)
    check("启动后不处于「未响应」", not bool(ctypes.windll.user32.IsHungAppWindow(hwnd)))

    im = shot(hwnd, min_w=1500)
    if im is None:
        check("主窗可抓图", False)
    else:
        im.save(os.path.join(SHOTS, "v206_exe_home.png"))
        check("主窗可抓图（非空白）", True, im.size)
        px = im.load()
        col = [px[x, y] for y in range(150, min(950, im.height)) for x in (2, 3, 4)]
        col.sort()
        mid = col[len(col) // 2]
        check("侧栏底色仍是实色 (15,15,17)",
              abs(mid[0] - 15) <= 3 and abs(mid[1] - 15) <= 3 and abs(mid[2] - 17) <= 3,
              "median=%s" % (mid,))
        DETAIL_BOX = (200, 70, im.width, im.height - 110)

    # ---------------- ① 详情页评分配色 ----------------
    lv.click(hwnd, NAV_WALL[0], NAV_WALL[1])
    time.sleep(2.0)
    im_a, ok_a = open_card_by_color(hwnd, C_MAGENTA, C_TEAL)
    check("进入「未打分」那部的详情页（另一部的海报已不在画面里）", ok_a)
    if im_a is not None:
        im_a.save(os.path.join(SHOTS, "v206b_exe_rate_gold.png"))
        n, ratio = warm_stats(im_a, DETAIL_BOX)
        p("  未打分：暖色像素 %s / 中位 g/r=%s" % (n, "%.3f" % ratio if ratio else None))
        check("没评过 → 「评分」两个字是**金色**（暖色像素 ≥12 且 g/r≈0.67）",
              n >= 12 and ratio is not None and 0.60 <= ratio <= 0.78, (n, ratio))

    lv.click(hwnd, NAV_WALL[0], NAV_WALL[1])
    time.sleep(2.0)
    im_b, ok_b = open_card_by_color(hwnd, C_TEAL, C_MAGENTA)
    check("进入「已打分」那部的详情页（另一部的海报已不在画面里）", ok_b)
    if im_b is not None:
        im_b.save(os.path.join(SHOTS, "v206b_exe_rate_orange.png"))
        n2, ratio2 = warm_stats(im_b, DETAIL_BOX)
        p("  已打分：暖色像素 %s / 中位 g/r=%s" % (n2, "%.3f" % ratio2 if ratio2 else None))
        check("评过 7.5 → 「用户评分 7.5」是**橙色**（暖色像素 ≥25 且 g/r≈0.55）",
              n2 >= 25 and ratio2 is not None and 0.45 <= ratio2 <= 0.62, (n2, ratio2))

        # ---------------- ③ 演职员 × / 标签 × ----------------
        av = find_avatar(im_b)
        check("定位到第一位演职员的纯色头像（方形状色块，不是一条线）", av is not None, av)
        before_cast = db_one("SELECT COUNT(*) FROM media_people WHERE media_id=?", (MB,))
        if av:
            cx, cy = av[0] + 95, av[1] + 5     # 头像外框右上角那枚 18×18 的「×」
            p("  点演职员 × @(%d,%d)（头像框 %s）" % (cx, cy, av))
            lv.click(hwnd, cx, cy)
            time.sleep(1.8)
            after_cast = db_one("SELECT COUNT(*) FROM media_people WHERE media_id=?", (MB,))
            check("点头像右上角的「×」→ 本片少一位演职员（3→2）",
                  before_cast == 3 and after_cast == 2, (before_cast, after_cast))
            im_b2 = shot(hwnd, min_w=1500, tries=6)
            if im_b2 is not None:
                im_b2.save(os.path.join(SHOTS, "v206b_exe_cast_after_x.png"))

        # 标签芯片：底色 #27272a，在头像下方找「一横排芯片」所在的那一行
        im_c = shot(hwnd, min_w=1500, tries=6) or im_b
        y_lo = (av[3] + 20) if av else 600
        ymid, chips = chip_row(im_c, y_lo)
        check("认出标签芯片那一横排（底色 #27272a，≥2 枚）",
              ymid is not None, (ymid, chips))
        before_tags = db_one("SELECT tags FROM media WHERE id=?", (MB,))
        if ymid is not None and chips:
            cx2 = chips[0][1] - 11
            p("  点第一枚芯片的 × @(%d,%d)" % (cx2, ymid))
            lv.click(hwnd, cx2, ymid)
            time.sleep(2.0)
            after_tags = db_one("SELECT tags FROM media WHERE id=?", (MB,))
            check("点标签芯片的「×」→ 库里少一个标签（标签甲,标签乙 → 标签乙）",
                  (after_tags or "").count(",") == 0 and "标签甲" not in (after_tags or "")
                  and "标签乙" in (after_tags or ""),
                  (before_tags, after_tags))
            im_d = shot(hwnd, min_w=1500, tries=6)
            if im_d is not None:
                im_d.save(os.path.join(SHOTS, "v206b_exe_tag_after_x.png"))

    # ---------------- ② 重复检测：打开 / 删除 ----------------
    lv.click(hwnd, TOOLS_BTN[0], TOOLS_BTN[1])
    dlg = lv.find_window_ex(EXE_NAME, [proc.pid], exclude=(hwnd,), timeout=25, title_sub="工具")
    check("工具窗已打开", dlg is not None, dlg)
    if dlg:
        time.sleep(2.6)
        lv.click(dlg, DD_NAV[0], DD_NAV[1])
        time.sleep(1.6)
        im_dd = shot(dlg, min_w=1000, tries=8)
        check("切到「重复检测」页并抓到图", im_dd is not None)
        dis_before = []
        if im_dd is not None:
            im_dd.save(os.path.join(SHOTS, "v206b_exe_dedupe_page.png"))
            for bx, by in DD_BTNS:
                dis_before.append(max_bright(im_dd, (bx - 26, by - 10, bx + 26, by + 10)))
            p("  四枚按钮的最亮值（初始应全灰）:", dis_before)
            check("没选中结果时四枚按钮都是灰的（最亮 <170）",
                  all(v < 170 for v in dis_before), dis_before)

        lv.click(dlg, DD_START[0], DD_START[1])
        p("  已点「开始检测」，等结果进树…")
        rows_ok = False
        for _ in range(20):
            time.sleep(1.0)
            im_dd2 = shot(dlg, min_w=1000, tries=2, gap=0.3)
            if im_dd2 is None:
                continue
            tx0, ty0, tw, th = DD_TREE
            n_txt = count_in(im_dd2, (tx0, ty0 + 26, tx0 + tw, ty0 + th),
                             lambda c: c[0] > 120 and c[1] > 120 and c[2] > 120)
            if n_txt > 200:
                rows_ok = True
                im_dd2.save(os.path.join(SHOTS, "v206b_exe_dedupe_result.png"))
                p("  树里出现 %d 个亮像素（>200 说明有结果行）" % n_txt)
                break
        check("点「开始检测」后结果进了树", rows_ok)

        if rows_ok:
            tx0, ty0, tw, th = DD_TREE
            lv.click(dlg, tx0 + 90, ty0 + 26 + 14)      # 第一行（分组行）
            time.sleep(0.6)
            key(dlg, VK_DOWN)                           # 下移 → 第一个成员行
            time.sleep(0.6)
            im_dd3 = shot(dlg, min_w=1000, tries=4, gap=0.3)
            en_after = []
            if im_dd3 is not None:
                for bx, by in DD_BTNS:
                    en_after.append(max_bright(im_dd3, (bx - 26, by - 10, bx + 26, by + 10)))
                p("  选中一行后四枚按钮的最亮值:", en_after)
            check("选中一行后四枚按钮都可点（最亮 >190）",
                  bool(en_after) and all(v > 190 for v in en_after), en_after)

            # 「删除…」→ 弹出二选一菜单（菜单是独立顶层窗口）
            lv.click(dlg, DD_DEL[0], DD_DEL[1])
            # ⚠ 顺手把鼠标挪开：按钮悬停会弹 **tooltip**，它也是个顶层小窗，
            #   枚举时排在第一，点它等于什么都没点（第二轮就是这么失败的）。
            lv.u32.PostMessageW(dlg, lv.WM_MOUSEMOVE, 0, ((5 & 0xFFFF) << 16) | 5)
            time.sleep(1.0)
            menus = top_windows(EXE_NAME, [proc.pid], exclude=(hwnd, dlg))
            p("  弹出的顶层小窗:", [(w, h, t, c) for _i, w, h, t, c in menus])
            pops = [m for m in menus if "QWindowPopup" in m[4]]
            check("点「删除…」→ 弹出菜单（窗口类是 Qt 的 QWindowPopup）",
                  bool(pops), [(m[1], m[2], m[4]) for m in menus])
            if pops:
                # 菜单只有两项。**点坐标打不稳**（实测点完菜单关了、项却没被触发 ——
                # 因为 QMenu 是靠 hover 设 currentAction 再在 release 里触发的，
                # 合成消息很容易「关掉但没选中」）。所以先走键盘：Down 选中第一项、
                # Return 触发，比算像素坐标可靠；不行再退回去点。
                def _popups():
                    return [m for m in top_windows(EXE_NAME, [proc.pid], exclude=(hwnd, dlg))
                            if "QWindowPopup" in m[4]]

                def _close_popups():
                    for _m in _popups():
                        lv.u32.PostMessageW(_m[0], lv.WM_KEYDOWN, 0x1B, 0)
                        time.sleep(0.1)
                        lv.u32.PostMessageW(_m[0], lv.WM_KEYUP, 0x1B, 0)
                        time.sleep(0.6)

                def _open_del_menu():
                    _close_popups()
                    lv.click(dlg, DD_DEL[0], DD_DEL[1])
                    lv.u32.PostMessageW(dlg, lv.WM_MOUSEMOVE, 0, ((5 & 0xFFFF) << 16) | 5)
                    time.sleep(1.0)
                    _p = _popups()
                    return _p[0] if _p else None

                mod = None
                for _st in ("real", "key", "click_mid"):
                    pop = _open_del_menu()
                    if pop is None:
                        p("  菜单没弹出来（%s 策略）" % _st)
                        break
                    if _st == "real":
                        real_click(pop[0], pop[1] // 2, 21)    # 真鼠标点第一项
                    elif _st == "key":
                        key(pop[0], VK_DOWN)
                        key(pop[0], VK_RETURN)
                    else:
                        lv.click(pop[0], pop[1] // 2, 21)
                    time.sleep(1.8)
                    hit = lv.find_modal(EXE_NAME, [proc.pid], exclude=(hwnd, dlg))
                    if hit:
                        _r = ctypes.wintypes.RECT()
                        lv.u32.GetWindowRect(hit, ctypes.byref(_r))
                        if (_r.right - _r.left) >= 300 and (_r.bottom - _r.top) >= 150:
                            mod = hit
                            break
                check("选「删除影片文件…」→ 弹出确认框（问是否删源文件）", mod is not None, mod)
                if mod:
                    # 模态框刚弹出来时控件还没画完 → 多等再接；且必须用屏幕区域抓
                    time.sleep(1.6)
                    pm = shot_rect(mod)
                    if pm is not None:
                        pm.save(os.path.join(SHOTS, "v206b_exe_dup_confirm.png"))
                        w, hh = pm.size
                        cxp = pm.load()
                        # 把红按钮的 **bbox** 整块量出来（原来只扫最后 60 行的列范围，
                        # 再拿 hh-30 当 y —— 那个 y 是猜的）。实测按钮就压在
                        # (484..549, 279..309)，中心 (516,294)。
                        xs, ys = [], []
                        for y in range(max(0, hh - 90), hh - 2):
                            for x in range(w):
                                r, g, b = cxp[x, y]
                                if r > 150 and g < 90 and b < 90:
                                    xs.append(x)
                                    ys.append(y)
                        p("  确认框 %sx%s，红色「删除」按钮 bbox=%s"
                          % (w, hh, (min(xs), min(ys), max(xs), max(ys)) if xs else None))
                        check("确认框底部有一枚**红色**主按钮（删）", bool(xs))
                        if xs:
                            bx = (min(xs) + max(xs)) // 2
                            by = (min(ys) + max(ys)) // 2
                            _wr = ctypes.wintypes.RECT()
                            lv.u32.GetWindowRect(mod, ctypes.byref(_wr))
                            _cr = ctypes.wintypes.RECT()
                            lv.u32.GetClientRect(mod, ctypes.byref(_cr))
                            p("  确认框 window 原点=(%s,%s) 尺寸=%sx%s client=%sx%s 红块中心=%s"
                              % (_wr.left, _wr.top, w, hh, _cr.right, _cr.bottom, (bx, by)))
                            # ① 真鼠标点屏幕绝对坐标（最贴近用户操作，也不受客户区原点影响）
                            real_click_at(_wr.left + bx, _wr.top + by)
                            time.sleep(2.2)
                            if not win_alive(mod):
                                p("  ① 真鼠标点屏幕坐标 → 框关了")
                            else:
                                # ② 投递客户区坐标（原点无偏移时等价于①）
                                p("  ① 真鼠标没关掉框，改用投递消息")
                                lv.click(mod, bx, by)
                                time.sleep(1.8)
                                if not win_alive(mod):
                                    p("  ② 投递客户区坐标 → 框关了")
                                else:
                                    # ③ 最后退化为回车（QDialog 的默认按钮）
                                    p("  ② 也没关掉框，改用回车")
                                    key(mod, VK_RETURN)
                                    time.sleep(1.8)
                            time.sleep(2.6)       # 等 SHFileOperationW 走完
                        still = None
                        if win_alive(mod):
                            still = mod
                            _im_still = shot_rect(mod)
                            if _im_still is not None:
                                _im_still.save(os.path.join(SHOTS, "v206b_exe_dup_still.png"))
                        check("确认框已关掉（删除真的执行了）", still is None, still)
            alive = [os.path.exists(f) for f in DUP]
            p("  两份副本现存:", alive)
            check("删掉一份后磁盘上只剩一份（另一份进了回收站）",
                  alive.count(True) == 1, alive)
            left = db_one("SELECT COUNT(*) FROM media WHERE title='重复的那部'")
            check("索引里那条记录也只剩 1 条", left == 1, left)
            im_dd4 = shot(dlg, min_w=1000, tries=4, gap=0.3)
            if im_dd4 is not None:
                im_dd4.save(os.path.join(SHOTS, "v206b_exe_dedupe_after_del.png"))

        lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
        time.sleep(1.4)

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
                           "Internal C++ object") if k in txt]
        p("  app.log 行数:", len(txt.splitlines()))
    check("app.log 无未捕获异常 / 无线程或对象已析构", not bad, bad)

p("FAILS:", FAILS)
p("通过 %d/%d" % (len(OKS), len(OKS) + len(FAILS)))
p("LIVE_V206B_ALL_OK" if not FAILS else "LIVE_V206B_HAS_FAIL")
