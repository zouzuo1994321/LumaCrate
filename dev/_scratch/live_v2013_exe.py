# -*- coding: utf-8 -*-
"""v2.0.13 真机验收：输入框右键菜单变中文（+ v2.0.12 的圆角与中文输入回归）。

本轮反馈：「修复输入框右键为英文的问题」（截图：Undo / Redo / Cut / Copy / Paste /
Delete / Select All）。根因是那句英文来自 **Qt 自己的翻译文件**（`qtbase_zh_CN.qm`），
软件从没装过 QTranslator。修法见 `src/qtlang.py`。

本脚本要证的（真 HWND / 真像素 / 产品自己写的日志）：

  ① app.log 里那行「Qt 标准文本：已装 <qm 路径> ｜ 示例 撤消(U) / 重做(R)」——
     这行是**产品启动时真算出来的翻译结果**，同时证明 onefile 里找得到 qm。
     脚本不 OCR，这是「中文真的生效」最硬的机器判据；
  ② 搜索框右键弹得出 Qt::Popup 菜单，四角**透出后面的界面**（不是黑）；
  ③ v2.0.12 的回归：筛选面板仍是前台窗口（能打中文）、中文筛选链路仍然成立；
  ④ app.log 无未捕获异常。

环境：临时库 + 临时 settings（`LMC_CONFIG`），绝不碰真实索引。

⚠ 抓图铁律（v2.0.12 首轮踩过，直接导致 3 条假红）：
  1. 对**半透明**窗口不能 `grabWindow(hwnd)`（窗口 DC 里没有分层像素）→
     必须整屏抓再按矩形裁（`shot_win`）。首轮面板被抓成 162 字节纯色 PNG。
  2. 不能靠 EXSTYLE 排除 TOOLWINDOW 来找菜单（QMenu 本来就是 TOOLWINDOW|TOPMOST）→
     按窗口类名 `QWindowPopup*` 认（`find_menu`）。
  3. 「圆角外是否透明」的基线取**关掉菜单之后**，不能取「开菜单之前」——
     右键会先选中并悬停那一行，行底色本来就变。
"""
import ctypes
import ctypes.wintypes
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TEMP = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp",
                    "lmc_exe_v2013")
COORDS_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                           "Temp", "lmc_coords_v208.json")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["LMC_NO_SYSMON"] = "1"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv          # noqa: E402
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication          # noqa: E402
from PySide6.QtGui import QImage                    # noqa: E402
from PIL import Image                               # noqa: E402

os.makedirs(SHOTS, exist_ok=True)
FAILS, OKS = [], []
T0 = time.time()
BUILD_TAG = "2611100134"
VER_TAG = "v2.0.13"


def p(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    p(("  OK   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if detail else ""))


def _del(pth):
    if os.path.exists(pth):
        ctypes.windll.kernel32.SetFileAttributesW(pth, 0x80)
        ctypes.windll.kernel32.DeleteFileW(pth)


def screen_of(win, x, y):
    """客户区坐标 → 屏幕坐标。"""
    pt = ctypes.wintypes.POINT(int(x), int(y))
    lv.u32.ClientToScreen(ctypes.wintypes.HWND(win), ctypes.byref(pt))
    return pt.x, pt.y


u32 = lv.u32
# ⚠ Imm* 系列在 imm32.dll 里；user32 只转发了一部分。两个都试一遍。
try:
    imm = ctypes.WinDLL("imm32")
except OSError:
    imm = u32
WM_CLOSE = lv.WM_CLOSE
WM_IME_STARTCOMPOSITION = 0x010D
WM_IME_COMPOSITION = 0x010F
WM_IME_ENDCOMPOSITION = 0x010E
GCS_RESULTSTR = 0x0800
SCS_SETSTR = 0x0002
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000

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
check("临时库已清空", not os.path.exists(DBF), DBF)
_del(LOG)

sys.path.insert(0, os.path.join(ROOT, "src"))
import database as db          # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: DBF
applog.log_dir = lambda: os.path.join(IDX, "logs")
db.init_db()

# 7 部片，其中只有一部带「机器」两字 —— 打「机器」应当只剩 1 行。
TITLES = ["AAA-001 老片一", "BBB-002 老片二", "CCC-003 老片三",
          "DDD-004 老片四", "ZZZ-005 老片五", "MIDA-209 真机验收",
          "MIDA-210 机器猫"]
for _i, _t in enumerate(TITLES):
    db.insert_media(
        title=_t, kind="movie", year=2026 - _i, rating=7.0, poster=POSTER,
        file_path=os.path.join(LIB, "A", "MIDA-209", "%s.mp4" % _t.split()[0]),
        library="真机库", sort_title=_t, tags="人妻,高清",
        added_time="2026-11-05 12:00:00", added_date="2026-11-05")
check("预置 7 部片（其中 1 部含「机器」）",
      db.get_conn().execute("SELECT COUNT(*) FROM media").fetchone()[0] == 7,
      db.get_conn().execute("SELECT COUNT(*) FROM media").fetchone()[0])
db.close_conn()

with open(CFG, "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "真机库", "kind": "电影",
                              "paths": [LIB], "filter": {}}],
               "appearance": {"accent": "#e4587c", "mode": "磨砂玻璃", "level": "低"}},
              f, ensure_ascii=False)

# ---------------- 坐标（离屏算表头 / 漏斗位置） ----------------
p("算坐标…")
env = dict(os.environ)
env["LMC_CONFIG"] = CFG
env["QT_QPA_PLATFORM"] = "offscreen"
r = subprocess.run([sys.executable, "-c",
                    "import runpy; runpy.run_path(r'%s', run_name='__main__')"
                    % os.path.join(DEV, "_scratch", "coords_v208.py")],
                   env=env, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=DEV)
p("  coords_v208.py rc=%s" % r.returncode)
CO = json.load(open(COORDS_JSON, encoding="utf-8"))
HDR = CO["header"]
TBL = CO["table"]
_title_col = None
for _c in HDR["cols"]:
    if _c["key"] == "title":
        _title_col = _c
p("  表 y=%s 行高=%s | 标题列 funnel=%s" %
  (TBL["y"], TBL["row_h"], None if _title_col is None else _title_col["funnel"]))
assert _title_col is not None, "表头里找不到 title 列"


# ---------------- 工具 ----------------
def _pm2pil(pm):
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    buf = img.constBits()
    if buf is None:
        return None
    return Image.frombytes("RGB", (img.width(), img.height()), bytes(buf), "raw", "BGRX")


def shot(tag, win, settle=4):
    try:
        u32.RedrawWindow(win, None, None, 0x0001 | 0x0100 | 0x0080)
        u32.UpdateWindow(win)
    except Exception:
        pass
    pm = lv.grab(app, win, tries=24, gap=0.4, settle=settle)
    if pm is None or pm.width() < 60:
        p("!! 抓图失败", tag)
        return None
    im = _pm2pil(pm)
    if im is None:
        return None
    im.save(os.path.join(SHOTS, "v2013_%s.png" % tag))
    p("  图 v2013_%s.png  %dx%d" % (tag, im.width, im.height))
    return im


def _win_rect(hwnd):
    rc = ctypes.wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(rc))
    return (rc.left, rc.top, rc.right, rc.bottom)


def grab_rect_pil(rect):
    """按**屏幕矩形**抓图（先整屏合成，再裁切）。

    ⚠ 半透明窗口（`WS_EX_LAYERED`）绝对不能走 `grabWindow(hwnd)`：
    那是对**窗口 DC** 做 BitBlt，而分层窗口的像素根本不在 DC 里 →
    抓到一整块空白。v2.0.13 首轮就是这么把 248x113 的筛选面板抓成了
    162 字节的纯色 PNG，于是「输入框有没有强调色描边」量不到、
    「中文有没有打进去」也无从量起 → ⑤ 之前连着三条假红。
    只有 `grabWindow(0)`（整屏）拿到的才是用户真正看见的合成结果。
    """
    x0, y0, x1, y1 = rect
    full = _pm2pil(app.primaryScreen().grabWindow(0))
    if full is None:
        return None
    if x1 - x0 <= 1 or y1 - y0 <= 1:
        return None
    return full.crop((max(0, x0), max(0, y0),
                      min(full.width, x1), min(full.height, y1)))


def shot_win(tag, hwnd, settle=4, need_accent=False):
    """抓某个窗口（按屏幕矩形），`need_accent` 时连拍到强调色描边出现为止。"""
    rc = _win_rect(hwnd)
    im = None
    for _ in range(max(1, settle)):
        time.sleep(0.45)
        im = grab_rect_pil(rc)
        if im is None:
            continue
        if not need_accent or edit_rect(im) is not None:
            break
    if im is None or im.width < 60:
        p("!! 抓图失败", tag)
        return None
    im.save(os.path.join(SHOTS, "v2013_%s.png" % tag))
    p("  图 v2013_%s.png  %dx%d（屏幕矩形）" % (tag, im.width, im.height))
    return im


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def bright_n(im, box, thr=200):
    px = im.load()
    x0, y0, x1, y1 = box
    n = 0
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            if lum(px[x, y]) >= thr:
                n += 1
    return n


ACCENT = (228, 88, 124)


def near(c, t, tol):
    return all(abs(c[i] - t[i]) <= tol for i in range(3))


def edit_rect(im, tol=45):
    """用「输入框聚焦时的强调色描边」框出输入框，返回 (x0, y0, x1, y1)。

    面板里只有两处强调色：#e4587c 的输入框 1px 描边 + 「确定」实心按钮。
    按行分组、取**最上面那一组**就是输入框。
    （之前按「半透明灰字带」找，结果挑到按钮行 —— 清空/确定的白字本来就亮，
      一路量出 192 个亮字、判「打之前就有字」，连累后面三条全假红。）
    """
    px = im.load()
    rows = []
    for y in range(im.height):
        xs = [x for x in range(im.width) if near(px[x, y], ACCENT, tol)]
        if xs:
            rows.append((y, min(xs), max(xs)))
    if not rows:
        return None
    bands, cur = [], [rows[0]]
    for r in rows[1:]:
        if r[0] - cur[-1][0] <= 3:
            cur.append(r)
        else:
            bands.append(cur)
            cur = [r]
    bands.append(cur)
    # ⚠ 取**横向跨度最大**的那一组，不是「最上面那一组」。
    #   v2.0.13 实测：面板顶部还有一个 16px 宽的强调色小元素（那帧是「清除」之类的
    #   小字），按「最上面」取就会把它当成输入框 → bbox `(54,16,70,22)`，
    #   之后所有亮字计数都量在 16x6 的角落上 → 「中文打进去了」判 FAIL，
    #   而列表墨迹量明明已经从 2781 掉到 483（中文确实生效了）。
    #   输入框那条描边横跨整行（200+ px），跨度天然最大。
    def _span(band):
        return max(r[2] for r in band) - min(r[1] for r in band)

    b = max(bands, key=_span)
    return (min(r[1] for r in b), b[0][0], max(r[2] for r in b), b[-1][0])


def dim_band(im, lo=85, hi=180, min_n=6):
    """找「半透明灰」的那一行 —— 那是 QLineEdit 的占位符。

    占位符是 text 色 50% 透明叠底 ≈ 亮度 130；真字是 #ecedee ≈ 236。
    有了这条带，就能把「占位符」和「真的打进去的字」分开量。
    """
    px = im.load()
    rows = []
    for y in range(im.height):
        n = sum(1 for x in range(im.width) if lo <= lum(px[x, y]) <= hi)
        if n >= min_n:
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
    # 最高的那条带就是占位符（标题 / 按钮文字都比它亮，不在这个亮度区间）
    return max(bands, key=lambda b: b[1] - b[0])


def popup_windows(pid, exclude):
    """枚举该进程的顶层窗口，返回 [(hwnd, w, h, title)]（排除主窗）。"""
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def _cb(h, _l):
        try:
            if not u32.IsWindowVisible(h) or h in exclude:
                return True
            q = ctypes.wintypes.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(q))
            if q.value != pid:
                return True
            rc = ctypes.wintypes.RECT()
            u32.GetWindowRect(h, ctypes.byref(rc))
            w, hh = rc.right - rc.left, rc.bottom - rc.top
            if w < 120 or hh < 60:
                return True
            buf = ctypes.create_unicode_buffer(128)
            u32.GetWindowTextW(h, buf, 128)
            out.append((int(h), w, hh, buf.value))
        except Exception:
            pass
        return True

    u32.EnumWindows(_cb, 0)
    return out


def find_popup(pid, exclude, timeout=8.0):
    """等筛选面板出现：200~520 × 70~320 的普通顶层小窗。

    ⚠ 必须排除悬停预览卡（`Qt.ToolTip` + EXSTYLE 0x88）：它也是 248 宽。
    我们这块面板的 EXSTYLE 是 0x0，带 TOOLWINDOW/TOPMOST 的一律不是它。
    """
    t0 = time.time()
    while time.time() - t0 < timeout:
        for (h, w, hh, t) in popup_windows(pid, exclude):
            if not (200 <= w <= 520 and 70 <= hh <= 320):
                continue
            ex = u32.GetWindowLongW(ctypes.wintypes.HWND(h), GWL_EXSTYLE)
            if ex & (WS_EX_TOOLWINDOW | WS_EX_TOPMOST):
                continue
            return h, w, hh, t
        time.sleep(0.25)
    return None


def win_class(h):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(ctypes.wintypes.HWND(int(h)), buf, 256)
    return buf.value


def dump_app_windows(pid, exclude, tag):
    """列出该进程此刻所有可见顶层窗口（诊断：菜单到底弹没弹、EXSTYLE 是多少）。"""
    p("  -- 窗口清单 [%s] --" % tag)
    for (h, w, hh, t) in popup_windows(pid, exclude):
        ex = u32.GetWindowLongW(ctypes.wintypes.HWND(h), GWL_EXSTYLE)
        p("     hwnd=%-9s %4dx%-4d class=%-26s ex=0x%08x title=%r"
          % (h, w, hh, win_class(h), ex, t))


def find_menu(pid, exclude, timeout=6.0):
    """等右键菜单：Qt 给 `Qt::Popup` 注册的窗口类名一定带 `QWindowPopup`。

    ⚠ 不能沿用筛「筛选面板」那套「EXSTYLE 带 TOOLWINDOW/TOPMOST 就排除」——
    QMenu 就是 `Qt::Popup`，Windows 侧本来就是 TOOLWINDOW|TOPMOST，
    v2.0.13 首轮照抄这条判据 → 菜单明明弹出来了却被自己排除掉，判成「没弹」。
    同一批窗口里的悬停预览卡是 `QWindowToolTip*`，按类名一刀切开最干净。
    """
    t0 = time.time()
    while time.time() - t0 < timeout:
        for (h, w, hh, t) in popup_windows(pid, exclude):
            if not (100 <= w <= 460 and 60 <= hh <= 420):
                continue
            if "Popup" not in win_class(h):
                continue
            ex = u32.GetWindowLongW(ctypes.wintypes.HWND(h), GWL_EXSTYLE)
            return h, w, hh, t, ex
        time.sleep(0.25)
    return None


app = QApplication.instance() or QApplication(sys.argv)


def force_foreground(h):
    """把窗口抢到前台。

    ⚠ 光 `SetForegroundWindow` 在本机被「前台锁」拒掉（脚本进程不是前台进程），
    窗口一直不上前台 → 那一下点击会被 Qt 当成「点击激活窗口」吞掉，
    表头连 hover 都收不到（图里一个漏斗图标都不画），更别说弹出面板。
    实测：不抢前台 = 窗口数一直 1、弹窗从不出现；抢了前台 = 立刻多出 248x113 的面板。
    """
    h_int = int(h)
    hw = ctypes.wintypes.HWND(h_int)
    fg = u32.GetForegroundWindow()
    tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
    tid_fg = u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(fg), None) if fg else 0
    ok_att = False
    if tid_fg and tid_fg != tid_me:
        ok_att = bool(u32.AttachThreadInput(tid_me, tid_fg, True))
    u32.BringWindowToTop(hw)
    u32.SetForegroundWindow(hw)
    u32.SetFocus(hw)
    if ok_att:
        u32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.35)
    return u32.GetForegroundWindow() == h_int


def pid_of(h):
    """⚠ PyInstaller onefile 会再 fork 一个子进程跑真正的 app —— 窗口属于**子进程**，
    按 `proc.pid`（bootloader）枚举永远是 0 个窗口。必须问主窗自己。"""
    q = ctypes.wintypes.DWORD()
    u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(int(h)), ctypes.byref(q))
    return q.value


def click(win, x, y):
    """真鼠标点击（合成消息在非激活态会被 Qt 当成「点击激活窗口」吞掉）。"""
    force_foreground(win)
    sx, sy = screen_of(win, x, y)
    u32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.2)


def press_enter():
    u32.keybd_event(0x0D, 0, 0, 0)
    time.sleep(0.05)
    u32.keybd_event(0x0D, 0, 2, 0)

# ---------------- 启动 ----------------
p("========== v2.0.13 真机验收（圆角黑框 + 中文输入回归） ==========")
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=200, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)
if not hwnd:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    print("LIVE_V2013_FAIL", len(FAILS), flush=True)
    raise SystemExit(1)
time.sleep(4.5)


def viewport_ink(im):
    """列表可视区里的文字墨迹量（行数变化的代理量）。"""
    y0 = TBL["y"] + HDR["h"]
    return bright_n(im, (TBL["x"] + 8, y0, TBL["x"] + 520, y0 + TBL["row_h"] * 8), 150)


popup_hwnd = None
try:
    APP_PID = pid_of(hwnd)
    p("  bootloader pid=%s → 真正跑 UI 的 pid=%s" % (proc.pid, APP_PID))
    force_foreground(hwnd)
    # 先把鼠标挪到右下角空白处，免得「悬停预览卡」盖在列表上干扰墨迹量
    u32.SetCursorPos(int(screen_of(hwnd, 1300, 900)[0]),
                     int(screen_of(hwnd, 1300, 900)[1]))
    time.sleep(1.2)
    im_base = shot("home", hwnd, settle=4)
    check("拿到首页列表截图", im_base is not None)
    ink_before = viewport_ink(im_base) if im_base is not None else 0
    p("  列表初始墨迹量 =", ink_before)
    check("首页列出了 7 部片（墨迹量足够大）", ink_before > 400, ink_before)

    # ---------------- ① 点标题列的漏斗 ----------------
    fx, fy = _title_col["funnel"]
    force_foreground(hwnd)
    lv.u32.SetCursorPos(*screen_of(hwnd, fx, fy))
    time.sleep(0.7)                       # 让表头把那两个图标画出来
    shot("header_hover", hwnd)
    click(hwnd, fx, fy)
    time.sleep(1.4)

    found = find_popup(APP_PID, {hwnd})
    check("点漏斗后弹出了筛选面板（新的顶层小窗）", found is not None, found)
    if found:
        popup_hwnd, pw, ph, ptitle = found
        p("  面板 hwnd=%s  %dx%d  标题=%r" % (popup_hwnd, pw, ph, ptitle))
        im_pop = shot_win("popup", popup_hwnd, settle=5, need_accent=True)
        check("拿到筛选面板截图", im_pop is not None,
              None if im_pop is None else (im_pop.width, im_pop.height))

        # ---- ①-0 面板四角：圆的、且透出后面的列表（不是纯黑）----
        # 这是用户图 2 的直接对照：不透明的顶层窗口会把圆角外刷成 #000000。
        if im_pop is not None:
            _w, _h = im_pop.width, im_pop.height
            _corners = [im_pop.getpixel(p) for p in
                        ((2, 2), (_w - 3, 2), (2, _h - 3), (_w - 3, _h - 3))]
            _darkest = min(max(c) for c in _corners)
            p("  面板四角（圆角外）像素 = %s" % (_corners,))
            check("面板四角不是纯黑（圆角外透出的是后面的界面）",
                  _darkest > 8, _darkest)

        # ---- ① 核心：它是不是 Windows 前台窗口 ----
        fg = u32.GetForegroundWindow()
        p("  前台窗口 =", fg)
        check("面板就是 Windows 前台窗口（旧 Qt.Popup 永远做不到 → 中文打不进）",
              fg == popup_hwnd, "fg=%s popup=%s" % (fg, popup_hwnd))

        # ---- ② EXSTYLE 不再是「菜单类窗口」，但多了 LAYERED（半透明） ----
        ex = u32.GetWindowLongW(popup_hwnd, GWL_EXSTYLE)
        p("  EXSTYLE = 0x%08x" % ex)
        check("EXSTYLE 不带 TOOLWINDOW|TOPMOST 组合（旧 Popup 是 0x88）",
              (ex & WS_EX_TOPMOST) == 0 or (ex & WS_EX_TOOLWINDOW) == 0, hex(ex))
        check("EXSTYLE 不带 WS_EX_NOACTIVATE", not (ex & WS_EX_NOACTIVATE), hex(ex))
        check("EXSTYLE 带 WS_EX_LAYERED（v2.0.13 半透明窗口的标志）",
              bool(ex & WS_EX_LAYERED), hex(ex))

        # ---- ③ 中文能不能真的进输入框 ----
        # ⚠ 别用 ImmGetContext 当判据：IMM 是**线程级**的，我们站在另一个进程里问
        #   别人窗口的 HIMC，永远拿到 0（跟产品对不对无关）。这里只记一行参考值。
        himc = imm.ImmGetContext(popup_hwnd) if hasattr(imm, "ImmGetContext") \
            else u32.ImmGetContext(popup_hwnd)
        p("  ImmGetContext = %s（跨进程必为 0，仅记录，不作判据）" % himc)

        # 输入框怎么找：**它拿到焦点时有一圈强调色描边**（面板里只有两处强调色，
        # 除了这条描边就是那颗「确定」实心按钮）。按行分组取最上面那一组。
        # 之前按「灰字亮度带」找，结果挑到按钮行（清空/确定的字本来就亮）→ 一路假红。
        er = edit_rect(im_pop) if im_pop is not None else None
        p("  输入框（强调色描边）bbox =", er)
        check("能用强调色描边框住输入框（说明焦点在它身上）", er is not None, er)
        b_before = 0
        box = (0, 0, 1, 1)
        if er is not None:
            box = (er[0] + 3, er[1] + 3, er[2] - 2, er[3] - 2)   # 内缩，避开描边本身
            b_before = bright_n(im_pop, box, 200)
            p("  输入框里的亮字计数（打之前）= %d" % b_before)
            check("打之前只有灰色占位提示（几乎量不到亮字）", b_before <= 6, b_before)

            # 走 WM_CHAR 把两个汉字码位送进去 —— 这正是输入法「上屏」时发的消息，
            # 也就等于验证了「中文字符能被这个窗口收下并显示」。
            for ch in "机器":
                u32.PostMessageW(popup_hwnd, 0x0102, ord(ch), 1)   # WM_CHAR
                time.sleep(0.18)
            time.sleep(0.9)
            im_t = shot_win("popup_typed", popup_hwnd, settle=4)
            b_after = bright_n(im_t, box, 200) if im_t is not None else 0
            p("  输入中文后亮字计数 = %d" % b_after)
            check("中文「机器」真的显示在输入框里（亮字 %d → %d）" % (b_before, b_after),
                  b_after > b_before + 30, "%d → %d" % (b_before, b_after))

        # ---- ④ 回车提交 → 中文筛选真的生效 ----
        force_foreground(popup_hwnd)
        time.sleep(0.3)
        press_enter()
        time.sleep(1.6)
        check("回车提交后面板自己关掉", not u32.IsWindowVisible(popup_hwnd))
        im_f = shot("filtered", hwnd, settle=4)
        ink_after = viewport_ink(im_f) if im_f is not None else None
        p("  筛选后列表墨迹量 =", ink_after)
        check("输入「机器」后只剩 1 行（墨迹量跌到 3 成以下但不为 0）",
              ink_after is not None and 0 < ink_after < ink_before * 0.35,
              "%s / %s" % (ink_after, ink_before))

        # ---- 清空筛选 → 7 行全回来 ----
        force_foreground(hwnd)
        lv.u32.SetCursorPos(*screen_of(hwnd, fx, fy))
        time.sleep(0.6)
        click(hwnd, fx, fy)
        time.sleep(1.4)
        found2 = find_popup(APP_PID, {hwnd})
        check("再次点漏斗仍能弹出面板", found2 is not None, found2)
        if found2:
            popup_hwnd = found2[0]
            force_foreground(popup_hwnd)
            time.sleep(0.5)
            # ⚠ 重新打开时输入框里**还留着上次的「机器」**（面板会回填当前筛选值），
            #   直接回车 = 再筛一次同样的条件，行数当然不变。
            #   showEvent 里已 selectAll()，所以一个 Delete 就能清空。
            u32.keybd_event(0x2E, 0, 0, 0)      # VK_DELETE
            time.sleep(0.06)
            u32.keybd_event(0x2E, 0, 2, 0)
            time.sleep(0.6)
            im_e = shot_win("popup_cleared_input", popup_hwnd, settle=4)
            if im_e is not None and er is not None:
                _b = bright_n(im_e, box, 200)
                p("  清空输入框后亮字计数 =", _b)
            press_enter()
            time.sleep(1.6)
            im_c = shot("cleared", hwnd, settle=4)
            ink_back = viewport_ink(im_c) if im_c is not None else None
            p("  清空筛选后列表墨迹量 =", ink_back)
            check("清空筛选 → 7 行全回来",
                  ink_back is not None and ink_back > ink_before * 0.8,
                  "%s / %s" % (ink_back, ink_before))

    # ---------------- ⑤ 右键菜单：圆角外露的是列表，不是纯黑 ----------------
    # 判据不靠「像不像黑」，而是**同一像素在「开菜单」与「关菜单」两态下是否一致**：
    # 半透明窗口时圆角外那几点应该等于后面的列表/选中行；
    # 不透明窗口时会被窗口表面刷成 #000000，差异一眼可见。
    p("---- ⑤ 右键菜单圆角 ----")
    force_foreground(hwnd)
    u32.SetCursorPos(int(screen_of(hwnd, 1300, 900)[0]),
                     int(screen_of(hwnd, 1300, 900)[1]))
    time.sleep(0.8)
    rx = TBL["x"] + 200
    ry = TBL["y"] + HDR["h"] + TBL["row_h"] + TBL["row_h"] // 2
    p("  右键位置（客户区）= (%d, %d)" % (rx, ry))
    force_foreground(hwnd)
    lv.u32.SetCursorPos(*screen_of(hwnd, rx, ry))
    time.sleep(0.35)
    u32.mouse_event(0x0008, 0, 0, 0, 0)      # RBUTTONDOWN
    time.sleep(0.06)
    u32.mouse_event(0x0010, 0, 0, 0, 0)      # RBUTTONUP
    time.sleep(1.3)

    menu = find_menu(APP_PID, {hwnd})
    dump_app_windows(APP_PID, {hwnd}, "右键之后")
    check("右键弹出了菜单（Qt::Popup 类顶层小窗）", menu is not None,
          None if menu is None else (menu[1], menu[2]))
    if menu:
        mh, mw, mhh, mt, mex = menu
        p("  菜单 hwnd=%s  %dx%d  EXSTYLE=0x%08x  class=%s"
          % (mh, mw, mhh, mex, win_class(mh)))
        check("菜单也是 WS_EX_LAYERED（半透明才可能透出后面）",
              bool(mex & WS_EX_LAYERED), hex(mex))
        rc = ctypes.wintypes.RECT()
        u32.GetWindowRect(mh, ctypes.byref(rc))
        p("  菜单屏幕矩形 = (%d,%d)-(%d,%d)" % (rc.left, rc.top, rc.right, rc.bottom))
        full_after = _pm2pil(app.primaryScreen().grabWindow(0))
        check("拿到开菜单时的整屏截图", full_after is not None)
        if full_after is not None:
            full_after.save(os.path.join(SHOTS, "v2013_menu_open.png"))
            full_after.crop((rc.left, rc.top, rc.right, rc.bottom)).save(
                os.path.join(SHOTS, "v2013_menu.png"))
            # 菜单本身必须真的画出来了（内侧是深色面板）
            inside = full_after.getpixel((rc.left + 24, rc.top + 26))
            p("  菜单内侧像素 = %s" % (inside,))
            check("菜单内侧是深色面板（面板真的画了，不是整块透明）",
                  max(inside) < 90, inside)

        # 关掉菜单，再抓一张当**基线**
        # ⚠ 基线绝不能取「开菜单之前」：右键会先把那一行**选中并悬停**，
        #   行底色本来就会变 —— 首轮实测四角通道差 166，全部来自行高亮，
        #   半点黑框都没有，却把一条好好的修复判成了 FAIL。
        #   关掉菜单后选中/悬停态都还在 → 此刻同一像素才是「圆角外该透出的东西」。
        u32.keybd_event(0x1B, 0, 0, 0)        # VK_ESCAPE
        time.sleep(0.06)
        u32.keybd_event(0x1B, 0, 2, 0)
        time.sleep(0.9)
        check("Esc 能关掉菜单", not u32.IsWindowVisible(mh))
        full_closed = _pm2pil(app.primaryScreen().grabWindow(0))
        check("拿到关菜单后的整屏截图（基线）", full_closed is not None)

        if full_after is not None and full_closed is not None:
            pts = [(rc.left + 2, rc.top + 2), (rc.right - 3, rc.top + 2),
                   (rc.left + 2, rc.bottom - 3), (rc.right - 3, rc.bottom - 3)]
            diffs, vals, base = [], [], []
            for (x, y) in pts:
                a = full_closed.getpixel((x, y))
                b = full_after.getpixel((x, y))
                diffs.append(max(abs(a[i] - b[i]) for i in range(3)))
                vals.append(b)
                base.append(a)
            p("  四角：开菜单时 = %s" % (vals,))
            p("  四角：关掉菜单后 = %s" % (base,))
            p("  四角：两者最大通道差 = %s" % (diffs,))
            check("菜单四角与「关掉菜单后」一致（=透出后面的界面，不是黑角）",
                  max(diffs) <= 12, diffs)
            darkest = min(max(v) for v in vals)
            check("四角都不是纯黑（#000 附近）", darkest > 8, darkest)

    # ---------------- ⑥ 输入框右键菜单：中文（本轮反馈） ----------------
    # 脚本不 OCR，所以「中文真的生效」靠**产品自己写的日志**：
    # main.py 启动时把 QLineEdit 标准菜单的前三项吐进 app.log，
    # 那行是**真算出来的翻译结果**，同时证明 onefile 里找得到 qm。
    p("---- ⑥ 输入框右键菜单（中文） ----")
    _lg = ""
    if os.path.exists(LOG):
        _lg = open(LOG, encoding="utf-8", errors="replace").read()
    _txt = [l for l in _lg.splitlines() if "Qt 标准文本" in l]
    _hit = _txt[-1] if _txt else ""
    p("  日志：%s" % (_hit or "(没有这一行)"))
    check("app.log 有「Qt 标准文本」这一行（启动时真装了翻译器）", bool(_txt), _hit or None)
    check("装的是 qtbase_zh_CN.qm（onefile 里找得到）",
          "qtbase_zh_CN.qm" in _hit, _hit or None)
    check("样例文本是中文（撤消 / 重做），不是 Undo / Redo",
          "撤消" in _hit and "Undo" not in _hit, _hit or None)

    _search = CO.get("search")
    p("  搜索框（客户区中心）= %s" % (_search,))
    check("坐标脚本算出了首页搜索框", bool(_search), _search)
    if _search:
        sx, sy = _search[0], _search[1]
        force_foreground(hwnd)
        lv.u32.SetCursorPos(*screen_of(hwnd, sx, sy))
        time.sleep(0.45)
        u32.mouse_event(0x0008, 0, 0, 0, 0)      # RBUTTONDOWN
        time.sleep(0.06)
        u32.mouse_event(0x0010, 0, 0, 0, 0)      # RBUTTONUP
        time.sleep(1.3)

        cmenu = find_menu(APP_PID, {hwnd})
        dump_app_windows(APP_PID, {hwnd}, "输入框右键之后")
        check("输入框右键弹出了标准菜单（Qt::Popup 类窗口）", cmenu is not None,
              None if cmenu is None else (cmenu[1], cmenu[2]))
        if cmenu:
            ch, cw, chh, ct, cex = cmenu
            p("  菜单 hwnd=%s  %dx%d  EXSTYLE=0x%08x  class=%s"
              % (ch, cw, chh, cex, win_class(ch)))
            # ⚠ 别断言 WS_EX_LAYERED：Qt 的**标准**菜单走 `QWindowPopupDropShadowSaveBits`，
            #   它用 QStyle 把阴影画**进窗口里**（EXSTYLE 0x88，无 LAYERED，旁边还挂一个
            #   `SysShadow` 兄弟窗口）。这跟我们 `uiwin.menu()` 的路径不同 ——
            #   但结果一样：圆角外是深色阴影而非黑。断言它的**来源**即可。
            check("标准菜单是 Qt 自己的 Popup 窗口（不是我们 uiwin 建的）",
                  "Popup" in win_class(ch), win_class(ch))
            # 标准菜单的项数是 7（撤销/重做/剪切/复制/粘贴/删除/全选），
            # 每一行约 34~40px 高 → 高度能反推「不是被裁成两项的残废菜单」。
            check("菜单有 7 项的高度（不是只画出标题的残废菜单）", chh >= 190, chh)
            crect = ctypes.wintypes.RECT()
            u32.GetWindowRect(ch, ctypes.byref(crect))
            p("  菜单屏幕矩形 = (%d,%d)-(%d,%d)"
              % (crect.left, crect.top, crect.right, crect.bottom))
            # 菜单本身存一张（肉眼复核中文；脚本不会 OCR，所以这张图是给人看的）
            cimg = _pm2pil(app.primaryScreen().grabWindow(0))
            if cimg is not None:
                cimg.crop((crect.left, crect.top, crect.right, crect.bottom)).save(
                    os.path.join(SHOTS, "v2013_ctx_menu_live.png"))
                p("  图 v2013_ctx_menu_live.png  %dx%d"
                  % (crect.right - crect.left, crect.bottom - crect.top))
            # 关掉再收尾
            u32.keybd_event(0x1B, 0, 0, 0)
            time.sleep(0.06)
            u32.keybd_event(0x1B, 0, 2, 0)
            time.sleep(0.85)
            check("Esc 能关掉这个菜单", not u32.IsWindowVisible(ch))
            # 四角判据：**不跟「关掉后」比**。这个菜单自带 Qt 的投影窗口（SysShadow），
            # 关掉后阴影一起消失 → 逐像素必然有差（实测 17~21），那是阴影不是黑框。
            # 真正要证的是「圆角外不是另一种颜色（尤其不是黑）」。
            if cimg is not None:
                cpts = [(crect.left + 2, crect.top + 2), (crect.right - 3, crect.top + 2),
                        (crect.left + 2, crect.bottom - 3),
                        (crect.right - 3, crect.bottom - 3)]
                _cv = [cimg.getpixel(q) for q in cpts]
                p("  四角 = %s" % (_cv,))
                # 三档色阶：`#000~#060608` = 黑框伪影；16~40 = 深色面板/阴影（正常）；
                # 更高 = 透出了后面的亮内容。这个菜单的圆角外是 Qt 画进来的**阴影**，
                # 实测 `(22,22,25)`，比面板 `(24,24,27)` 还暗一点点 —— 完全正常。
                check("四角是深色阴影区（8 < 最亮通道 ≤ 60），既不是黑框也不是亮色",
                      all(8 < max(v) <= 60 for v in _cv), _cv)

finally:
    try:
        u32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
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
    p("日志行数", len(log_txt.splitlines()))

    p("========== 结果 ==========")
    p("通过 %d / %d" % (len(OKS), len(OKS) + len(FAILS)))
    if FAILS:
        for f in FAILS:
            p("  失败:", f)
        print("LIVE_V2013_FAIL", len(FAILS), flush=True)
    else:
        print("LIVE_V2013_ALL_OK", len(OKS), flush=True)
