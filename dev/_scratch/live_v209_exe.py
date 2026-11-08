# -*- coding: utf-8 -*-
"""v2.0.9 真机验收（启动打包 exe，真鼠标点击，量截图）。

四条反馈里，①②③ 是「图标没在正中央 / 叉太大」，④ 是「进度条上方多一行空白」。
离屏已由 `dev/_scratch/probe_v209_draw.py`（8/8）与冒烟 ㉟ 段（25 条）证明代码正确，
真机这一遍要证的是**打包后的 exe 在真实字体 / DPI 下同样成立**：

  ① 标签胶囊的 × 在徽章圆心（探出胶囊顶部那 7px 里能数到笔画）；
  ② 5 个头像的右上角各有一枚 ×，且每一枚都量得到笔画；
  ③ 两处「＋」的墨迹是**紧凑十字**（5~9px 见方），且落在自绘框的正中（框心偏移 ≤1px）；
  ④ 工具窗「演员刮削 → 执行」区：按钮行底到进度条中线 ≈ 离屏基准 15px（空标签回来会 +19px）。

环境：临时库 + 临时 settings（`LMC_CONFIG`），绝不碰真实索引。
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
                    "lmc_exe_v209")
COORDS_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                           "Temp", "lmc_coords_v208.json")
UI_COORDS_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                              "Temp", "lmc_ui_coords.json")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["LMC_NO_SYSMON"] = "1"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv          # noqa: E402  （导入时它把自己的 stdout 重定向到日志）
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication      # noqa: E402
from PySide6.QtGui import QImage                # noqa: E402
from PIL import Image                           # noqa: E402

os.makedirs(SHOTS, exist_ok=True)
FAILS, OKS = [], []
T0 = time.time()
BUILD_TAG = "2611030130"
VER_TAG = "v2.0.9"

# 5 个头像的专属纯色：互不接近，也不撞任何 UI 色（撞了 find_box 会横跨整页）
PHOTO_COLORS = [(220, 40, 40), (60, 220, 220), (40, 200, 60),
                (200, 60, 200), (20, 20, 200)]
CAST = [("女演员甲", "female", "Actor"), ("女导演乙", "female", "Director"),
        ("男演员丙", "male", "Actor"), ("男导演丁", "male", "Director"),
        ("未知戊", "", "Actor")]
PILL = (39, 39, 42)          # 标签胶囊底 #27272a
ACCENT = (228, 88, 124)


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


def find_box(im, rgb, tol=12, step=2, box=None):
    px = _px(im).load()
    x0, y0, x1, y1 = box or (0, 0, im.width, im.height)
    ax, ay, bx, by = 10 ** 9, 10 ** 9, -1, -1
    for y in range(max(0, y0), min(y1, im.height), step):
        for x in range(max(0, x0), min(x1, im.width), step):
            if near(px[x, y], rgb, tol):
                ax = min(ax, x)
                bx = max(bx, x)
                ay = min(ay, y)
                by = max(by, y)
    if bx < 0:
        return None
    return (ax, ay, bx, by)


def bright_mask(im, thr=170):
    """「亮到能确认是笔画」的像素集合（#d4d4d8 = 212；头像流光粉/蓝都够不着）。"""
    im = _px(im)
    px = im.load()
    pts = set()
    for y in range(im.height):
        for x in range(im.width):
            if min(px[x, y][:3]) >= thr:
                pts.add((x, y))
    return pts


def components(pts, gap=2):
    """把像素点聚成连通块（8 邻域 + 允许 gap 空隙），返回 [(x0,y0,x1,y1,n)]。"""
    pts = set(pts)
    out = []
    while pts:
        seed = pts.pop()
        stack, comp = [seed], [seed]
        while stack:
            cx, cy = stack.pop()
            for dx in range(-gap, gap + 1):
                for dy in range(-gap, gap + 1):
                    q = (cx + dx, cy + dy)
                    if q in pts:
                        pts.discard(q)
                        stack.append(q)
                        comp.append(q)
        xs = [q[0] for q in comp]
        ys = [q[1] for q in comp]
        out.append((min(xs), min(ys), max(xs), max(ys), len(comp)))
    return out


def ink_in(im, box, thr=170):
    x0, y0, x1, y1 = box
    im = _px(im)
    px = im.load()
    n = 0
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            if min(px[x, y][:3]) >= thr:
                n += 1
    return n


def pill_runs(im):
    """找标签胶囊行：返回 (band_y0, band_y1, [(x0,x1), ...])。"""
    im = _px(im)
    px = im.load()
    rows = []
    for y in range(im.height):
        n = 0
        for x in range(0, im.width, 2):
            if near(px[x, y], PILL, 8):
                n += 1
        if 30 <= n <= 900:          # 顶栏那种「整行都是 #27272a」要先排除
            rows.append(y)
    if not rows:
        return None
    bands, cur = [], (rows[0], rows[0])
    for y in rows[1:]:
        if y - cur[1] <= 3:
            cur = (cur[0], y)
        else:
            bands.append(cur)
            cur = (y, y)
    bands.append(cur)
    # 胶囊净高 20（TagChip.PILL_H）—— 只有这个高度的横带才是标签行；
    # 顶栏 / 面板可能是同一个 #27272a，但高度对不上。
    for (y0, y1) in bands:
        if not (16 <= y1 - y0 <= 24):
            continue
        # ★ 用「列投影」而不是取横带中线那一行：中线正好穿文字笔画，
        #   胶囊底色会被字割成 <30px 的碎段，一枚都数不出来（第一版就栽在这）。
        #   按列统计带内有多少行是胶囊色 —— 文字只吃掉几行，列计数仍有 15±。
        cnt = []
        for x in range(im.width):
            n = 0
            for y in range(y0, y1 + 1):
                if near(px[x, y], PILL, 8):
                    n += 1
            cnt.append(n)
        hits = [c >= 3 for c in cnt]
        # 把 ≤2px 的小缺口并回去（圆角/抗锯齿会造成断点）
        for x in range(1, im.width - 1):
            if not hits[x] and hits[x - 1] and (hits[x + 1] or (x + 2 < im.width and hits[x + 2])):
                hits[x] = True
        runs, st = [], None
        for x in range(im.width):
            if hits[x] and st is None:
                st = x
            elif not hits[x] and st is not None:
                if 30 <= x - st <= 220:     # 一枚胶囊 ~40px；整条通栏的不要
                    runs.append((st, x - 1))
                st = None
        if st is not None and 30 <= im.width - st <= 220:
            runs.append((st, im.width - 1))
        if runs:
            return y0, y1, runs
    return None


def _screen_of(hwnd_, x, y):
    pt = ctypes.wintypes.POINT(int(x), int(y))
    lv.u32.ClientToScreen(hwnd_, ctypes.byref(pt))
    return pt.x, pt.y


def real_click(hwnd_, x, y):
    lv.u32.SetForegroundWindow(hwnd_)
    time.sleep(0.15)
    sx, sy = _screen_of(hwnd_, x, y)
    lv.u32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.12)
    lv.u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.04)
    lv.u32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.15)


def real_dbl(hwnd_, x, y):
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
    time.sleep(0.25)


# ---------------- 环境预置 ----------------
os.makedirs(TEMP, exist_ok=True)
src = lv.newest_exe()
p("新 exe:", src)
assert src and os.path.exists(src)
check("根目录最新 exe 就是 %s（%s）" % (VER_TAG, BUILD_TAG),
      VER_TAG in os.path.basename(src) and BUILD_TAG in os.path.basename(src),
      os.path.basename(src))
exe = os.path.join(TEMP, "LMC-probe-%s.exe" % BUILD_TAG)
if not os.path.exists(exe) or os.path.getsize(exe) != os.path.getsize(src):
    shutil.copy2(src, exe)
EXE_NAME = os.path.basename(exe).lower()

LIB = os.path.join(TEMP, "lib")
os.makedirs(os.path.join(LIB, "A", "MIDA-209"), exist_ok=True)
POSTER = os.path.join(TEMP, "poster.png")
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

# ⚠ 每一部片都带同样的 3 个标签 + 同样的 5 位演职人员：
#   首页列表的首行取决于默认排序，**不猜哪一行是「我们的片」** —— 双击哪行都成立。
TAGS = "人妻,高清,剧情"
MIDS = []
for _i, _t in enumerate(["MIDA-209 真机验收 主演甲", "ZZZ-005 老片五", "BBB-002 老片二",
                         "CCC-003 老片三", "DDD-004 老片四", "AAA-001 老片一"]):
    _mid = db.insert_media(
        title=_t, kind="movie", year=2026 - _i, rating=7.0, poster=POSTER,
        file_path=os.path.join(LIB, "A", "MIDA-209", "%s.mp4" % _t.split()[0]),
        library="真机库", sort_title=_t, tags=TAGS,
        added_time="2026-11-01 12:00:00", added_date="2026-11-01")
    MIDS.append(_mid)
for _mid in MIDS:
    for _i, (_nm, _g, _role) in enumerate(CAST):
        _pid = db.upsert_person(_nm, _role)
        db.set_person_fields(_pid, gender=_g, photo_path=PHOTOS[_i])
        db.link_media_person(_mid, _pid, "导演" if _role == "Director" else "", _i)
check("预置 6 部片（每部 3 个标签 + 5 位演职人员）",
      len(MIDS) == 6 and len(db.get_cast(MIDS[0])) == 5,
      len(db.get_cast(MIDS[0])))
db.close_conn()        # 真关掉，别在验收期间一直占着库文件

with open(CFG, "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "真机库", "kind": "电影",
                              "paths": [LIB], "filter": {}}],
               "appearance": {"accent": "#e4587c", "mode": "磨砂玻璃", "level": "低"}},
              f, ensure_ascii=False)

# ---------------- 坐标（离屏算） ----------------
p("算坐标…")
env = dict(os.environ)
env["LMC_CONFIG"] = CFG
env["QT_QPA_PLATFORM"] = "offscreen"
for _script, _json in (("coords_v208.py", COORDS_JSON), ("ui_coords.py", UI_COORDS_JSON)):
    _r = subprocess.run([sys.executable, "-c",
                         "import runpy; runpy.run_path(r'%s', run_name='__main__')"
                         % os.path.join(DEV, "_scratch", _script)],
                        capture_output=True, timeout=300,
                        env=dict(env, LMC_CONFIG=(CFG if _script.startswith("coords") else "")))
    p("  %s rc=%s" % (_script, _r.returncode))
    if _r.returncode != 0:
        p((_r.stdout or b"")[-1200:].decode("utf-8", "replace"))
        p((_r.stderr or b"")[-1500:].decode("utf-8", "replace"))
CO = json.load(open(COORDS_JSON, encoding="utf-8"))
UI = json.load(open(UI_COORDS_JSON, encoding="utf-8"))
assert CO.get("main_size") == [1920, 1080], CO.get("main_size")
TBL, HDR = CO["table"], CO["header"]
GAP_CENTER = UI.get("sc_gap_btn_to_prog_center")
p("表 x=%s y=%s 行高=%s 表头高=%s | 执行区基准 %spx | 提示标签隐藏=%s"
  % (TBL["x"], TBL["y"], TBL["row_h"], HDR["h"], GAP_CENTER, UI.get("sc_mode_hint_hidden")))
check("离屏基准：执行区「按钮底 → 进度条中线」= 15px（v2.0.8 含空行时是 34px）",
      14 <= (GAP_CENTER or 0) <= 16, GAP_CENTER)


def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def frame_of(im_, cx, cy, R=18):
    """以「＋」的墨迹中心为锚，量出外面那枚自绘框的四边。

    坑（第一版就假红在这）：RoundPlus 的框是 rgba(255,255,255,36) 叠在
    **深绿渐变底**（46,75,55）上 → 实测边框 (71,97,79)，最大通道冲到 97、
    max-min=26 根本不算中性色。旧判据「45≤min 且 max≤78 且中性」在离屏的
    #efefef 白底上能过，到真机一片 FAIL。
    改成按**相对底色的亮度档位**切：
      框线 ≈ bg+24    ，「＋」笔画 ≈ bg+60…150 ，而底色自己 = bg。
    再取「尺寸对得上的那个连通环」当框 —— 隔壁标题字的抗锯齿碎点尺寸不合，自然被滤掉。
    """
    im2 = _px(im_)
    px = im2.load()
    W, H = im2.size

    # 详情页背景是竖向渐变 → 底色必须就近取（窗口四角的中位亮度）
    vals = []
    for (dx, dy) in ((-R, -R), (R, -R), (-R, R), (R, R)):
        x, y = cx + dx, cy + dy
        if 0 <= x < W and 0 <= y < H:
            vals.append(_lum(px[x, y]))
    if not vals:
        return None
    vals.sort()
    bg = vals[len(vals) // 2]

    pts = set()
    for y in range(max(0, cy - R), min(H, cy + R + 1)):
        for x in range(max(0, cx - R), min(W, cx + R + 1)):
            L = _lum(px[x, y])
            if bg + 12 <= L < bg + 45:       # 框线档；「＋」自己更亮，排除
                pts.add((x, y))
    if not pts:
        return None

    best = None
    for (x0, y0, x1, y1, _n) in components(pts, gap=2):
        w, h = x1 - x0 + 1, y1 - y0 + 1
        if not (24 <= w <= 32 and 20 <= h <= 28):
            continue
        d = abs((x0 + x1) / 2.0 - cx) + abs((y0 + y1) / 2.0 - cy)
        if d > 6:
            continue
        if best is None or d < best[0]:
            best = (d, (x0, y0, x1, y1))
    return None if best is None else best[1]


def analyze_detail(im):
    """①②③：标签胶囊的 × / 头像右上角的 × / 两处「＋」的位置。"""
    if im is None:
        check("详情页截图可用", False)
        return

    # ---- ① 标签胶囊 ----
    p("========== ① 标签胶囊与它的 × ==========")
    res = pill_runs(im)
    ok_pills = res is not None and len(res[2]) >= 3
    check("详情页里数到 ≥3 枚标签胶囊（同一行）",
          ok_pills, None if res is None else (res[0], res[1], res[2]))
    if ok_pills:
        y0, y1, runs = res
        # 徽章圆心几乎正压在胶囊「右上角」上：实测胶囊 215..256 / 顶边 821，
        # × 那枚深色小圆占 x252..262、y814..825，亮笔画在 x254..261 / y817..822。
        # 所以取框要往**右上方**偏，(x1-8 … x1+10, y0-10 … y0+3) 才包得住；
        # 取到 x1+2 会只括进半个 ×，只剩 6 个亮点（旧判据就是这么假红的）。
        def badge_box(x1):
            return (x1 - 8, y0 - 10, x1 + 11, y0 + 3)

        protrude, above = 0, 0
        for (x0, x1) in runs:
            n = ink_in(im, badge_box(x1))
            if n >= 6:
                protrude += 1
            n2 = ink_in(im, (x1 - 8, y0 - 10, x1 + 11, y0))
            above += n2
            p("    胶囊 x%d..%d 角落笔画 %d（其中在顶边上方 %d）" % (x0, x1, n, n2))
        check("每枚胶囊的右上角都探出一枚 ×（徽章压角）",
              protrude == len(runs), "%d/%d" % (protrude, len(runs)))
        check("× 的笔画确实超出了胶囊顶边（不是只碰到边线）", above >= 6 * len(runs), above)

    # ---- ② 头像右上角的 × ----
    p("========== ② 演员头像右上角的 × ==========")
    boxes = {}
    for _i, _c in enumerate(PHOTO_COLORS):
        boxes[_i] = find_box(im, _c, tol=10)
    p("    头像色块:", {k: v for k, v in boxes.items()})
    found = sum(1 for v in boxes.values() if v and (v[2] - v[0]) >= 40)
    check("5 个演员头像都画出来了", found == 5, "%d/5" % found)
    if found == 5:
        badge_ok, offs = 0, []
        for _i, b in boxes.items():
            x0, y0, x1, y1 = b
            n = ink_in(im, (max(0, x1 - 34), max(0, y0 - 2), min(im.width, x1 - 4), y0 + 22))
            if n >= 6:
                badge_ok += 1
            offs.append(n)
        check("每枚头像右上角都有 ×（5/5 都量到笔画）", badge_ok == 5, offs)
        span = [b[2] - b[0] for b in boxes.values()]
        check("5 枚头像等大（圆形直径一致，±2px）", max(span) - min(span) <= 2, span)

    # ---- ③ 两处「＋」 ----
    p("========== ③ 「＋」是不是在正中央 ==========")
    cands = []
    for (x0, y0, x1, y1, n) in components(bright_mask(im, 170)):
        w, h = x1 - x0 + 1, y1 - y0 + 1
        if 5 <= w <= 9 and 5 <= h <= 9 and n >= 12 and abs(w - h) <= 2:
            cands.append((x0, y0, x1, y1, n))
    p("    候选十字 %d 个" % len(cands))
    got = 0
    for (x0, y0, x1, y1, n) in cands:
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        fr = frame_of(im, int(cx), int(cy))
        if fr is None:
            continue
        fw, fh = fr[2] - fr[0] + 1, fr[3] - fr[1] + 1
        # ⚠ 判据核心：RoundPlus 的框是 28×24；× 徽章只有 14/18。
        #   不加这条，「＋」会全部量到隔壁那些 × 徽章上（第一版就是这么假绿的）。
        if not (26 <= fw <= 30 and 22 <= fh <= 26):
            continue
        fx, fy = (fr[0] + fr[2]) / 2.0, (fr[1] + fr[3]) / 2.0
        dx, dy = cx - fx, cy - fy
        w, h = x1 - x0 + 1, y1 - y0 + 1
        p("    ＋ @(%.0f,%.0f) 框 %dx%d 框心(%.1f,%.1f) 偏移(%+.1f,%+.1f)"
          % (cx, cy, fw, fh, fx, fy, dx, dy))
        check("「＋」外接 %dx%d（紧凑十字，不是被压扁的字形）" % (w, h),
              5 <= w <= 9 and 5 <= h <= 9 and abs(w - h) <= 2, "%dx%d" % (w, h))
        check("「＋」落在 28×24 框的正中央（偏移 ≤1.5px）",
              abs(dx) <= 1.5 and abs(dy) <= 1.5, "(%+.2f, %+.2f)" % (dx, dy))
        got += 1
    check("至少量到一处 28×24 框里的「＋」", got >= 1, got)


def accent_band(dim, y_hint, x0=120, x1=560, thr=60):
    """在截图里找「模式按钮」那一横带（4 枚粉色实心按钮），返回 (y0, y1)。

    只看执行区左边那一竖条（x 120..560）：右侧那些粉色开关一枚才 ~44px，
    行内计数到不了 60；而按钮行在中线以上被文字挖掉几行后仍有 90+，很干净。
    """
    im2 = _px(dim)
    px = im2.load()
    W, H = im2.size
    x1 = min(x1, W)
    rows = []
    for y in range(H):
        n = 0
        for x in range(min(x0, W), x1):
            if near(px[x, y], ACCENT, 40):
                n += 1
        if n >= thr:
            rows.append(y)
    if not rows:
        return None
    bands, cur = [], [rows[0], rows[0]]
    for y in rows[1:]:
        if y - cur[1] <= 3:
            cur[1] = y
        else:
            bands.append(tuple(cur))
            cur = [y, y]
    bands.append(tuple(cur))
    bands = [b for b in bands if 20 <= b[1] - b[0] + 1 <= 44]   # 按钮高 ~31
    if not bands:
        return None
    return min(bands, key=lambda b: abs(b[0] - y_hint))


def analyze_exec(dim):
    """④：按钮行底 → 进度条「0%」首行的距离。"""
    p("========== ④ 进度条上方那行空白 ==========")
    if dim is None:
        check("「演员刮削」页截图可用", False)
        return
    br = UI.get("sc_mode_btn_rect")
    pr = UI.get("sc_prog_rect")
    if not br or not pr:
        check("拿到执行区几何基准（按钮 / 进度条）", False, (br, pr))
        return
    # ★ 别拿 br 的绝对 y 当按钮底：离屏 ui_coords 量出来的执行区比真机画面低 14px
    #   （真机按钮行 722..752，基准算出来是 767）→ 直接减就把整段间距吞掉，量出 gap=2。
    #   改成「在截图里自己找那一行粉色实心按钮」，两端都在同一张图上量，与基准无关。
    btn_band = accent_band(dim, br[1])
    check("截图里定位到「模式按钮」那一行（粉色实心，4 枚）", btn_band is not None, btn_band)
    if btn_band is None:
        return
    btn_bottom = btn_band[1]
    cx = pr[0] + pr[2] // 2
    band = None
    for y in range(btn_bottom + 2, min(dim.height - 1, btn_bottom + 90)):
        if ink_in(dim, (cx - 120, y, cx + 120, y + 1), 170) >= 3:
            band = y
            break
    check("按钮行下方能数到进度条的「0%」", band is not None, band)
    if band is not None:
        gap = band - btn_bottom
        # 离屏基准 sc_gap_btn_to_prog_center=15（按钮底 → 进度条中线），
        # 「0%」字号 10px 居中在 16px 高的进度条里 → 文字首行约在中线上方 4px。
        expect = (GAP_CENTER or 15) - 4
        check("按钮行底 → 「0%」首行 = " + str(gap) + "px（期望 ≈" + str(expect)
              + "，空标签回来会 +19）", abs(gap - expect) <= 3,
              "gap=" + str(gap) + " expect=" + str(expect))
    check("模式说明标签在真机上也处于隐藏态", UI.get("sc_mode_hint_hidden") is True,
          UI.get("sc_mode_hint_hidden"))


def summarize():
    p("========== 结果 ==========")
    p("通过 %d / %d" % (len(OKS), len(OKS) + len(FAILS)))
    if FAILS:
        for f in FAILS:
            p("  失败:", f)
        print("LIVE_V209_FAIL", len(FAILS), flush=True)
    else:
        print("LIVE_V209_ALL_OK", len(OKS), flush=True)



# ★ 只分析已有截图（）：不用重启 exe，改了判据可以立刻复核。
if os.environ.get("V209_SHOT_ONLY") == "1":
    p("只分析已有截图：v209_detail.png / v209_tools_scraper.png")
    analyze_detail(Image.open(os.path.join(SHOTS, "v209_detail.png")))
    analyze_exec(Image.open(os.path.join(SHOTS, "v209_tools_scraper.png")))
    summarize()
    raise SystemExit(0)


# ---------------- 启动 ----------------
p("========== v2.0.9 真机验收（accent=#e4587c / 磨砂玻璃·低） ==========")
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=200, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)
if not hwnd:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    print("LIVE_V209_FAIL", len(FAILS), flush=True)
    raise SystemExit(1)
time.sleep(4.0)


def _pm2pil(pm):
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    buf = img.constBits()
    if buf is None:
        return None
    return Image.frombytes("RGB", (img.width(), img.height()), bytes(buf), "raw", "BGRX")


def shot(tag, win=None, settle=4):
    win = win or hwnd
    try:
        lv.u32.RedrawWindow(win, None, None, 0x0001 | 0x0100 | 0x0080)
        lv.u32.UpdateWindow(win)
    except Exception:
        pass
    pm = lv.grab(app, win, tries=24, gap=0.4, settle=settle)
    if pm is None or pm.width() < 100:
        p("!! 抓图失败", tag)
        return None
    im = _pm2pil(pm)
    if im is None:
        p("!! 转图失败", tag)
        return None
    im.save(os.path.join(SHOTS, "v209_%s.png" % tag))
    p("  图 v209_%s.png  %dx%d" % (tag, im.width, im.height))
    return im


app = QApplication.instance() or QApplication(sys.argv)

try:
    # ============================================================
    # ① 打开详情页：标签胶囊 + 每枚的 ×
    # ============================================================
    p("========== ① 标签胶囊与它的 × ==========")
    rx = TBL["x"] + 240
    ry = TBL["y"] + HDR["h"] + TBL["row_h"] // 2
    real_dbl(hwnd, rx, ry)
    time.sleep(2.5)
    im = shot("detail")
    check("双击列表首行后拿到详情页截图", im is not None)
    analyze_detail(im)

    # ============================================================
    # ④ 工具窗 → 演员刮削：「执行」区不再空一行
    # ============================================================
    p("========== ④ 进度条上方那行空白 ==========")
    sx, sy = UI["main_settings_btn"]
    dlg = None
    for _a in range(3):
        lv.u32.SetForegroundWindow(hwnd)
        real_click(hwnd, sx, sy)
        dlg = lv.find_window_ex(EXE_NAME, {proc.pid}, exclude={hwnd},
                                title_sub="工具", timeout=8)
        if dlg:
            break
    check("工具窗口打开了", dlg is not None, dlg)
    if dlg:
        time.sleep(2.0)
        dn = UI["dialog_nav"].get("演员刮削")
        real_click(dlg, dn[0], dn[1])
        time.sleep(2.5)
        dim = shot("tools_scraper", win=dlg, settle=5)
        check("拿到「演员刮削」页截图", dim is not None)
        analyze_exec(dim)
        try:
            lv.u32.PostMessageW(dlg, lv.WM_CLOSE, 0, 0)
        except Exception:
            pass
        time.sleep(1.0)

finally:
    # ============================================================
    # 收尾：关窗 + 扫 app.log 的未捕获异常
    # ============================================================
    try:
        lv.u32.PostMessageW(hwnd, lv.WM_CLOSE, 0, 0)
    except Exception:
        pass
    time.sleep(1.5)
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    time.sleep(0.6)
    log_txt = ""
    if os.path.exists(LOG):
        log_txt = open(LOG, encoding="utf-8", errors="replace").read()
    bad = [l for l in log_txt.splitlines()
           if "未捕获异常" in l or "Traceback" in l or "QThread: Destroyed" in l]
    check("app.log 里没有「未捕获异常 / Traceback / QThread 崩溃」", not bad, bad[:3])
    p("日志行数 %d" % len(log_txt.splitlines()))
    p("========== 结果 ==========")
    p("通过 %d / %d" % (len(OKS), len(OKS) + len(FAILS)))
    if FAILS:
        for f in FAILS:
            p("  失败:", f)
        print("LIVE_V209_FAIL", len(FAILS), flush=True)
    else:
        print("LIVE_V209_ALL_OK", len(OKS), flush=True)
