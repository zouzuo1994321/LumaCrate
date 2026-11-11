# -*- coding: utf-8 -*-
"""v2.0.14 真机验收：右键菜单黑角 + 输入框清空小叉。

两条反馈：「圆角外有黑色的小角」+「输入框输入内容后靠右出现小X，可以删除输入的内容」。
修法见 `src/editfix.py`。

判据全部落在**真 HWND / 真像素**上：

  ① 搜索框空着时，右端没有亮叉；
  ② 用真键盘打「ZZZ」→ 右端浮出一颗 8~10px 的亮叉（`#a1a1aa`，亮度 ~161）；
  ③ 用真鼠标点那颗叉 → 文本清空 + 叉自己消失（叉的亮像素归零）；
  ④ 右键搜索框 → 菜单窗口类是 `QWindowPopupSaveBits`（**没有 `DropShadow`**）——
     Qt 自建的标准菜单只会是 `QWindowPopupDropShadowSaveBits`，类名变了就证明
     菜单换成了我们自己的圆角壳；
  ⑤ 菜单四角不是黑：最亮通道 > 8，且与「菜单关掉后同一位置」的底色接近；
  ⑥ Esc 能关掉菜单；`app.log` 零未捕获异常、有「输入框收尾」一行。

⚠ 三轮诊断换来的四条量法（别再踩）：
  1. **清空叉的亮度只有 ~161**，用 170 当阈值会恒报 0 → 用 140；
     而且必须把搜索框自身的**粉色焦点描边**排除掉（它亮度 134，会顶到 100~120 档，
     把「有没有叉」淹没），所以取样区要内缩 3px。
  2. **不要拿列表墨迹当"文本有没有打进去"的代理量**：顶栏搜索框改的是别的视图，
     首页列表不一定跟着变；直接量搜索框左侧的亮字。
  3. 键盘注入要先 `AttachThreadInput` 到**目标窗口所在线程**再 `SetFocus`
     （`SetFocus` 只对调用线程自己的窗口生效），否则右键有反应、打字一个字都进不去。
  4. **绝不用普通字母键注入去"制造已提交文本"** —— 本机中文输入法在活动状态时，
     注入的 `VK_Z` 会进**组字串（preedit）**：框里看起来有字（底下那条**点线下划线**
     就是组字标志），但 `text()` 是空的、`textChanged` 不响、清空叉不该出现。
     0135/0136 两轮验收就被这个骗了，还误判成「打包后才有的缺陷」；按回车"叉才出现"
     其实是**回车提交了组字**。所以这里改用 **Ctrl+V 粘贴**（Ctrl 是修饰键，输入法不吃）。
  5. **清空之后左侧仍会剩 17 个亮像素，那是**输入框获得焦点后的**插入光标**（实测只有
     1 列、x=LX0+15、竖着 17 个像素）。所以"文字有没有被清空"不能数亮像素总数，
     要看**墨迹的横向宽度**：只剩光标时宽度 ≤3px，有字时十几到几十像素。
     （顺带记一下：未聚焦的空框里占位提示「在列表中搜索片名…」一个字都过不了 140 阈值，
     实测 0 —— 之前误以为是它，其实不是。）
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
                    "lmc_exe_v2014")
COORDS_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                           "Temp", "lmc_coords_v208.json")
sys.path.insert(0, DEV)
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["LMC_NO_SYSMON"] = "1"

_out, _err = sys.stdout, sys.stderr
import live_verify as lv                   # noqa: E402
sys.stdout, sys.stderr = _out, _err
from PySide6.QtWidgets import QApplication                 # noqa: E402
from PySide6.QtGui import QImage                            # noqa: E402
from PIL import Image                                       # noqa: E402

os.makedirs(SHOTS, exist_ok=True)
FAILS, OKS = [], []
T0 = time.time()
BUILD_TAG = "2611110137"
VER_TAG = "v2.0.14"

u32 = lv.u32
WM_CLOSE = lv.WM_CLOSE
GWL_EXSTYLE = -20


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
    pt = ctypes.wintypes.POINT(int(x), int(y))
    u32.ClientToScreen(ctypes.wintypes.HWND(int(win)), ctypes.byref(pt))
    return pt.x, pt.y


def win_client(win):
    rc = ctypes.wintypes.RECT()
    u32.GetClientRect(ctypes.wintypes.HWND(int(win)), ctypes.byref(rc))
    return rc.right - rc.left, rc.bottom - rc.top


def force_foreground(h):
    """抢前台 + 抢键盘焦点（必须附加到目标窗口线程，否则 SetFocus 静默失败）。"""
    hw = ctypes.wintypes.HWND(int(h))
    tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
    fg = u32.GetForegroundWindow()
    tid_fg = u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(fg), None) if fg else 0
    tid_t = u32.GetWindowThreadProcessId(hw, None)
    o1 = bool(u32.AttachThreadInput(tid_me, tid_fg, True)) if tid_fg and tid_fg != tid_me else False
    o2 = bool(u32.AttachThreadInput(tid_me, tid_t, True)) if tid_t and tid_t != tid_me else False
    u32.BringWindowToTop(hw)
    u32.SetForegroundWindow(hw)
    u32.SetFocus(hw)
    if o2:
        u32.AttachThreadInput(tid_me, tid_t, False)
    if o1:
        u32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.4)
    return u32.GetForegroundWindow() == int(h)


def left_click(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.25)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    u32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.5)


def right_click(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.25)
    u32.mouse_event(0x0008, 0, 0, 0, 0)
    time.sleep(0.09)
    u32.mouse_event(0x0010, 0, 0, 0, 0)
    time.sleep(0.9)


def key_tap(vk):
    u32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.06)
    u32.keybd_event(vk, 0, 2, 0)
    time.sleep(0.25)


VK_CONTROL, VK_V = 0x11, 0x56


def ctrl_v():
    """Ctrl+V —— Ctrl 是修饰键，输入法不会吃掉它后面的 V。"""
    u32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.08)
    u32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.08)
    u32.keybd_event(VK_V, 0, 2, 0)
    time.sleep(0.08)
    u32.keybd_event(VK_CONTROL, 0, 2, 0)
    time.sleep(0.6)


def set_clip_text(text):
    """用 Win32 直接把文本塞进剪贴板。

    **不能用 `app.clipboard().setText()`**：Qt 在 Windows 上是**延迟渲染** ——
    数据留在我们进程里，等对方进程来取时才产出，而我们还必须同时在跑事件循环。
    上一版正是这么写的，结果把 exe 的 UI 线程拖住（后面几张抓图全是 0x0）。
    这里 `GlobalAlloc` 一份真数据交给系统，谁取都立刻拿得到。
    """
    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    k32 = ctypes.windll.kernel32
    # ⚠ 必须显式声明 restype：ctypes 默认按 **32 位 int** 收返回值，HGLOBAL 是
    #   指针宽度，被截断后 GlobalLock 拿到一个假地址 → 写就 access violation。
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    u32.OpenClipboard.argtypes = [ctypes.c_void_p]
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not u32.OpenClipboard(None):
        return False
    u32.EmptyClipboard()
    h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    p = k32.GlobalLock(h) if h else None
    if not p:
        u32.CloseClipboard()
        return False
    ctypes.memmove(p, data, len(data))
    k32.GlobalUnlock(h)
    ok = u32.SetClipboardData(CF_UNICODETEXT, h)
    u32.CloseClipboard()
    time.sleep(0.3)
    return bool(ok)


def _pm2pil(pm):
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    buf = img.constBits()
    if buf is None:
        return None
    return Image.frombytes("RGB", (img.width(), img.height()), bytes(buf), "raw", "BGRX")


def grab_rect_pil(rect):
    x0, y0, x1, y1 = rect
    full = _pm2pil(app.primaryScreen().grabWindow(0))
    if full is None or x1 - x0 <= 1 or y1 - y0 <= 1:
        return None
    return full.crop((max(0, x0), max(0, y0), min(full.width, x1), min(full.height, y1)))


def win_rect(hwnd):
    rc = ctypes.wintypes.RECT()
    u32.GetWindowRect(ctypes.wintypes.HWND(int(hwnd)), ctypes.byref(rc))
    return (rc.left, rc.top, rc.right, rc.bottom)


def pid_of(h):
    q = ctypes.wintypes.DWORD()
    u32.GetWindowThreadProcessId(ctypes.wintypes.HWND(int(h)), ctypes.byref(q))
    return q.value


def win_class(h):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(ctypes.wintypes.HWND(int(h)), buf, 256)
    return buf.value


def popup_windows(pid, exclude):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def _cb(h, _l):
        try:
            if not u32.IsWindowVisible(h) or int(h) in exclude:
                return True
            q = ctypes.wintypes.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(q))
            if q.value != pid:
                return True
            rc = ctypes.wintypes.RECT()
            u32.GetWindowRect(h, ctypes.byref(rc))
            w, hh = rc.right - rc.left, rc.bottom - rc.top
            if w < 100 or hh < 50:
                return True
            out.append((int(h), w, hh))
        except Exception:
            pass
        return True

    u32.EnumWindows(_cb, 0)
    return out


def find_menu(pid, exclude, timeout=6.0, min_w=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for (h, w, hh) in popup_windows(pid, exclude):
            cls = win_class(h)
            if "Popup" in cls and w >= min_w:
                return h, w, hh, cls
        time.sleep(0.25)
    return None


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def bright_box(im, box, thr=140):
    """返回 (像素数, 包围盒)：包围盒是**绝对图像坐标**，找不到亮像素时返回 None。"""
    if im is None:
        return 0, None
    px = im.load()
    x0, y0, x1, y1 = box
    n, xs, ys = 0, [], []
    for y in range(max(0, y0), min(y1, im.height)):
        for x in range(max(0, x0), min(x1, im.width)):
            if lum(px[x, y]) >= thr:
                n += 1
                xs.append(x)
                ys.append(y)
    if not xs:
        return 0, None
    return n, (min(xs), min(ys), max(xs), max(ys))


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
for _i, _t in enumerate(["AAA-001 老片一", "BBB-002 老片二", "CCC-003 老片三",
                         "DDD-004 老片四", "ZZZ-005 老片五", "MIDA-209 真机验收",
                         "MIDA-210 机器猫"]):
    db.insert_media(title=_t, kind="movie", year=2026 - _i, rating=7.0, poster=POSTER,
                    file_path=os.path.join(LIB, "A", "MIDA-209", "%s.mp4" % _t.split()[0]),
                    library="真机库", sort_title=_t, tags="人妻,高清",
                    added_time="2026-11-05 12:00:00", added_date="2026-11-05")
check("预置 7 部片", db.get_conn().execute("SELECT COUNT(*) FROM media").fetchone()[0] == 7)
db.close_conn()

with open(CFG, "w", encoding="utf-8") as f:
    json.dump({"libraries": [{"name": "真机库", "kind": "电影",
                              "paths": [LIB], "filter": {}}],
               "appearance": {"accent": "#e4587c", "mode": "磨砂玻璃", "level": "低"}},
              f, ensure_ascii=False)

p("算坐标…")
env = dict(os.environ)
env["LMC_CONFIG"] = CFG
env["QT_QPA_PLATFORM"] = "offscreen"
subprocess.run([sys.executable, "-c",
                "import runpy; runpy.run_path(r'%s', run_name='__main__')"
                % os.path.join(DEV, "_scratch", "coords_v208.py")],
               env=env, capture_output=True, text=True, encoding="utf-8",
               errors="replace", cwd=DEV)
CO = json.load(open(COORDS_JSON, encoding="utf-8"))
SEARCH = CO.get("search")
check("坐标表里有顶栏搜索框", SEARCH is not None, SEARCH)
assert SEARCH is not None
SCX, SCY, SW, SH = SEARCH
SX0, SY0 = SCX - SW // 2, SCY - SH // 2
p("  顶栏搜索框 left=%d top=%d w=%d h=%d（右键菜单用它）" % (SX0, SY0, SW, SH))

# 清空小叉的验证**不用顶栏那个框**：真机客户区 1920x1080 而屏幕也是 1920x1080，
# 窗口比屏幕还大 → 顶栏框右端骑在屏幕边缘（实测叉在屏幕 x 1909..1931，一半在屏幕外），
# 那种位置「新显示的子控件要不要等整块重绘」本身就说不清。改用首页列表自带那个
# 完整落在屏内的输入框（「在列表中搜索片名…」）。
LS = CO.get("list_search")
check("坐标表里有列表搜索框（v2.0.14 加的字段）", LS is not None, LS)
assert LS is not None
LCX, LCY, LW, LH = LS
LX0, LY0 = LCX - LW // 2, LCY - LH // 2
p("  列表搜索框 left=%d top=%d w=%d h=%d（清空小叉用它）" % (LX0, LY0, LW, LH))

app = QApplication.instance() or QApplication(sys.argv)


def shot_main(tag):
    pm = lv.grab(app, hwnd, tries=24, gap=0.4, settle=4)
    im = _pm2pil(pm) if pm is not None else None
    if im is not None:
        im.save(os.path.join(SHOTS, "v2014_%s.png" % tag))
        p("  图 v2014_%s.png  %dx%d" % (tag, im.width, im.height))
    return im


#: 列表搜索框右端 40px 的取样区（**内缩 3px**，把自身粉色焦点描边排除掉）
BAND = (LX0 + LW - 40, LY0 + 3, LX0 + LW - 3, LY0 + LH - 3)
#: 列表搜索框左侧文字区
TEXTBOX = (LX0 + 12, LY0 + 3, LX0 + 200, LY0 + LH - 3)

# ---------------- 启动 ----------------
p("========== %s 真机验收（菜单黑角 + 清空小叉） ==========" % VER_TAG)
proc = subprocess.Popen([exe], cwd=TEMP, env=dict(os.environ))
p("已启动 pid=", proc.pid)
hwnd = lv.find_window(EXE_NAME, [proc.pid], timeout=200, title_sub="Build")
check("主窗口出现（标题含 Build）", hwnd is not None, hwnd)
if not hwnd:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)
    print("LIVE_V2014_FAIL", len(FAILS), flush=True)
    raise SystemExit(1)
time.sleep(4.5)

try:
    APP_PID = pid_of(hwnd)
    p("  bootloader pid=%s → 真正跑 UI 的 pid=%s" % (proc.pid, APP_PID))
    cw, ch = win_client(hwnd)
    check("主窗客户区与坐标表一致（±4px）",
          abs(cw - CO["main_size"][0]) <= 4 and abs(ch - CO["main_size"][1]) <= 4, (cw, ch))
    check("抢到前台与键盘焦点", force_foreground(hwnd))
    u32.SetCursorPos(*screen_of(hwnd, 1300, 980))
    time.sleep(1.0)

    # ---- ① 空输入框：右侧没有叉 ----
    im0 = shot_main("home")
    check("拿到首页截图", im0 is not None)
    n0, bb0 = bright_box(im0, BAND)
    p("  空输入框右端亮像素 =", n0)
    check("空输入框右侧没有亮叉（≤4 像素）", 0 <= n0 <= 4, n0)
    # 空框左侧的基线：未聚焦时占位提示一个字都过不了 140 阈值（实测 0），
    # 留这一项只为把「打进去的字确实比占位提示亮得多」量出来。
    n_base, _ = bright_box(im0, TEXTBOX)
    p("  占位提示文字的亮像素基线 =", n_base)

    # ---- ② 真粘贴一串字 → 右端浮出亮叉 ----
    # 用 Ctrl+V 而不是打字母：本机中文输入法活动时，注入的字母只会进组字串（preedit），
    # 框里看着有字、`text()` 却是空的（详见文件头 ⚠ 第 4 条）。
    left_click(*screen_of(hwnd, LCX, LCY))
    check("剪贴板里塞进了文本（Win32 直接写，不走 Qt 延迟渲染）",
          set_clip_text("ZZZ"))
    ctrl_v()
    time.sleep(1.2)
    im1 = shot_main("typed")
    n_flag, bb_flag = bright_box(im1, TEXTBOX)
    check("打进去的字出现在输入框左侧（比占位提示多出一截墨迹）",
          n_flag >= n_base + 10, (n_flag, n_base))
    n1, bb1 = bright_box(im1, BAND)
    p("  有内容时右端亮像素 = %d  包围盒 = %s" % (n1, bb1))
    check("输入框右侧浮出了清空小叉（≥8 像素）", n1 >= 8, n1)
    check("小叉是个 6~14px 的小图形（不是一整块亮底）",
          bb1 is not None and 5 <= bb1[2] - bb1[0] + 1 <= 14
          and 5 <= bb1[3] - bb1[1] + 1 <= 14, bb1)
    # 诊断：叉没出来时，看 exe 内部 `_sync_clear_btn` 到底有没有被 textChanged 叫到。
    # 日志来自 `LMC_DEBUG_EDITFIX=1`（本脚本的环境变量被 exe 继承）。
    _dbg = [ln for ln in (open(LOG, encoding="utf-8", errors="replace").read().splitlines()
                          if os.path.exists(LOG) else [])
            if "清空按钮同步" in ln]
    p("  [诊断] 清空按钮同步日志 %d 行：%s" % (len(_dbg), _dbg[-4:]))
    if bb1 is None:
        raise SystemExit("没有小叉可点，后面不再继续")
    cx = (bb1[0] + bb1[2]) // 2
    cy = (bb1[1] + bb1[3]) // 2
    p("  小叉中心(客户区) = (%d,%d)，距输入框右边 %d px" % (cx, cy, LX0 + LW - cx))
    # 放大存图：给人复核「这颗叉长什么样」
    crop = im1.crop((max(0, LX0 + LW - 90), max(0, LY0),
                     min(im1.width, LX0 + LW), min(im1.height, LY0 + LH)))
    crop.resize((crop.width * 6, crop.height * 6), Image.NEAREST).save(
        os.path.join(SHOTS, "v2014_clear_btn_live.png"))
    p("  图 v2014_clear_btn_live.png（右端 90px ×6）")

    # ---- ③ 真鼠标点那颗叉 → 清空 + 叉消失 ----
    left_click(*screen_of(hwnd, cx, cy))
    time.sleep(1.0)
    im2 = shot_main("cleared")
    n2, _ = bright_box(im2, BAND)
    n_src, bb_src = bright_box(im2, TEXTBOX)
    p("  点叉后：右端亮像素 = %s，左侧墨迹 = %s 包围盒 = %s（空框基线 %s）"
      % (n2, n_src, bb_src, n_base))
    # 只剩插入光标时墨迹只有 1~2px 宽；有字时是十几到几十像素。
    ink_w = (bb_src[2] - bb_src[0] + 1) if bb_src else 0
    check("点叉后文本被清空（左侧只剩插入光标，墨迹宽度 ≤3px）",
          ink_w <= 3, (n_src, ink_w, bb_src))
    check("点叉后小叉自己消失", n2 <= 4, n2)

    # ---- ④ 右键菜单：类名 / 四角 / Esc ----
    # 先在顶栏那个框里贴上几个字（与用户截图同态：框里有内容时右键）。
    # 同样用粘贴，不用字母注入 —— 组字串状态下 Qt 的标准菜单里「撤消/重做」的
    # 启用态不一样，跟用户看到的不是同一份。
    left_click(*screen_of(hwnd, SCX, SCY))
    set_clip_text("ZZ")
    ctrl_v()
    time.sleep(0.8)
    right_click(*screen_of(hwnd, SCX, SCY))
    time.sleep(0.8)
    found = find_menu(APP_PID, {int(hwnd)})
    check("右键弹出了 Qt 菜单窗口", found is not None, found)
    vals, base_pts = None, None
    if found:
        menu_hwnd, mw_, mh_, mcls = found
        p("  菜单 hwnd=%s %dx%d class=%s" % (menu_hwnd, mw_, mh_, mcls))
        check("菜单窗口类里没有 DropShadow（证明是我们自己的圆角壳）",
              "DropShadow" not in mcls, mcls)
        check("菜单尺寸合理（约 171x267：7 条 + 2 条分隔线）",
              140 <= mw_ <= 260 and 190 <= mh_ <= 360, (mw_, mh_))
        im_menu = grab_rect_pil(win_rect(menu_hwnd))
        if im_menu is not None:
            im_menu.save(os.path.join(SHOTS, "v2014_ctx_menu.png"))
            p("  图 v2014_ctx_menu.png  %dx%d" % (im_menu.width, im_menu.height))
            _w, _h = im_menu.width, im_menu.height
            q = [(2, 2), (_w - 3, 2), (2, _h - 3), (_w - 3, _h - 3)]
            vals = [im_menu.getpixel(t) for t in q]
            p("  四角像素 =", [(int(v[0]), int(v[1]), int(v[2])) for v in vals])
            hi = max(max(v) for v in vals)
            # 三档色阶：#000000~#060608 = 黑框伪影；更高 = 透出后面的界面色
            check("菜单四角不是黑洞（最亮通道 > 8）", hi > 8, hi)
            rc = win_rect(menu_hwnd)
            base_pts = [(rc[0] + t[0], rc[1] + t[1]) for t in q]
        key_tap(0x1B)
        time.sleep(1.0)
        check("Esc 能关掉菜单",
              find_menu(APP_PID, {int(hwnd)}, timeout=2.0) is None)
        if base_pts and vals:
            full = _pm2pil(app.primaryScreen().grabWindow(0))
            if full is not None:
                after = [full.getpixel(pt) for pt in base_pts]
                p("  同一位置（菜单关掉后）=",
                  [(int(v[0]), int(v[1]), int(v[2])) for v in after])
                diff = max(abs(vals[i][k] - after[i][k])
                           for i in range(len(vals)) for k in range(3))
                check("四角与「关掉后同位置」接近（差 ≤ 60，说明真透出背景）", diff <= 60, diff)

    # ---- ⑤ 日志 ----
    time.sleep(1.0)
    txt = open(LOG, encoding="utf-8", errors="replace").read() if os.path.exists(LOG) else ""
    bad = [ln for ln in txt.splitlines()
           if "未捕获异常" in ln or "Traceback" in ln or "QThread: Destroyed" in ln]
    check("app.log 零未捕获异常", not bad, bad[:3])
    check("app.log 有「输入框收尾」一行（editfix 真装上了）",
          any("输入框收尾" in ln for ln in txt.splitlines()))
    check("v2.0.13 的 qtlang 仍然生效（日志有 qtbase_zh_CN.qm）",
          any("qtbase_zh_CN.qm" in ln for ln in txt.splitlines()))

finally:
    try:
        u32.PostMessageW(ctypes.wintypes.HWND(int(hwnd)), WM_CLOSE, 0, 0)
    except Exception:
        pass
    time.sleep(1.5)
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)

p("==============================================")
p("通过 %d/%d" % (len(OKS), len(OKS) + len(FAILS)))
if FAILS:
    p("失败项:", FAILS)
    print("LIVE_V2014_FAIL", len(FAILS), flush=True)
else:
    print("LIVE_V2014_ALL_OK", len(OKS), flush=True)
