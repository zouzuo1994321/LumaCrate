# -*- coding: utf-8 -*-
"""v2.0.10 真机验收：首页表头「筛选」面板能不能打中文。

反馈原话：「首页筛选无法正常输入中文」。
离屏（probe_v2010_ime2.py 15/15 + 冒烟 ㊱ 16 条）已证明窗口类型、属性、中文数据链路都对；
但**离屏平台没有真 HWND、没有前台窗口、没有系统输入法**，那三条判据只能在真机上量。
本脚本要证的就是这三条 + 端到端效果：

  ① 点漏斗后弹出的面板，**是不是 Windows 前台窗口**（旧 Qt.Popup 永远不是 → 输入法挂不上）；
  ② 它的 EXSTYLE 不再带「菜单类窗口」签名（WS_EX_TOOLWINDOW|WS_EX_TOPMOST = 0x88）；
  ③ 能拿到输入法上下文 ImmGetContext；往 HWND 投 IME 组字结果，中文真的进到输入框里
     （占位符是半透明灰 ≈130 亮度，真字是 #ecedee ≈236 —— 用亮度差判，不靠猜）；
  ④ 中文筛选**真的生效**：输入「机器」只剩「MIDA-210 机器猫」1 行；清空后 7 行全回来。

环境：临时库 + 临时 settings（`LMC_CONFIG`），绝不碰真实索引。
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
                    "lmc_exe_v2010")
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
BUILD_TAG = "2611050131"
VER_TAG = "v2.0.10"


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
    im.save(os.path.join(SHOTS, "v2010_%s.png" % tag))
    p("  图 v2010_%s.png  %dx%d" % (tag, im.width, im.height))
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
    b = bands[0]
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
p("========== v2.0.10 真机验收（首页筛选中文输入） ==========")
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=200, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)
if not hwnd:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    print("LIVE_V2010_FAIL", len(FAILS), flush=True)
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
        im_pop = shot("popup", popup_hwnd, settle=3)
        check("拿到筛选面板截图", im_pop is not None,
              None if im_pop is None else (im_pop.width, im_pop.height))

        # ---- ① 核心：它是不是 Windows 前台窗口 ----
        fg = u32.GetForegroundWindow()
        p("  前台窗口 =", fg)
        check("面板就是 Windows 前台窗口（旧 Qt.Popup 永远做不到 → 中文打不进）",
              fg == popup_hwnd, "fg=%s popup=%s" % (fg, popup_hwnd))

        # ---- ② EXSTYLE 不再是「菜单类窗口」 ----
        ex = u32.GetWindowLongW(popup_hwnd, GWL_EXSTYLE)
        p("  EXSTYLE = 0x%08x" % ex)
        check("EXSTYLE 不带 TOOLWINDOW|TOPMOST 组合（旧 Popup 是 0x88）",
              (ex & WS_EX_TOPMOST) == 0 or (ex & WS_EX_TOOLWINDOW) == 0, hex(ex))
        check("EXSTYLE 不带 WS_EX_NOACTIVATE", not (ex & WS_EX_NOACTIVATE), hex(ex))

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
            im_t = shot("popup_typed", popup_hwnd, settle=3)
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
            im_e = shot("popup_cleared_input", popup_hwnd, settle=3)
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
        print("LIVE_V2010_FAIL", len(FAILS), flush=True)
    else:
        print("LIVE_V2010_ALL_OK", len(OKS), flush=True)
