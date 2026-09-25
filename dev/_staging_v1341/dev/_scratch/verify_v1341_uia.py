# -*- coding: utf-8 -*-
"""v1.34.1 真机验收（UIA）—— 只盯本次三条反馈，全部用**数值**判据。

三条反馈对应的真机判据：
  反馈 3（智能推荐 数值 UI 重叠）：推荐墙工具行里的 QDoubleSpinBox
      → 真机矩形宽度必须 >= 120（修复前是 72，比 Qt 实测 minimumSizeHint 131 少 59px），
        且与「加强」按钮的**水平间距 >= 4px**（修复前挤在一起）。
  反馈 1（自动填充 数值和上下 UI 重叠）：对话框里 8 个 SpinBox
      → 每个宽度 >= 120，且**任意两个可见控件两两不相交**（>=4px² 判失败）。
  反馈 2（选「我的收藏」时高度有问题）：切范围前后
      → 对话框**整体高度跳变 <= 2px**；维度区 / 说明区 / 统计行的 y 跳变 <= 2px。

另外：抓图留证 + grep app.log 无「未捕获异常」/Traceback。

用法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/_scratch/verify_v1341_uia.py', run_name='__main__')"
"""
import ctypes
import ctypes.wintypes as wt
import glob
import io
import os
import subprocess
import sys
import time

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_verify_v1341.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1310"
SHOT = os.path.join(ROOT, "dev", "screenshots_v1341_live")
os.makedirs(SHOT, exist_ok=True)

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

ERR_MARK = "未捕获异常".encode("utf-8")

PASS, FAIL = [], []

# ---- SendInput(键盘) 结构体：给下拉框按方向键用（见 L15 的坑）----
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004
VK_DOWN = 0x28


class _KBD(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class _U(ctypes.Union):
    _fields_ = [("ki", _KBD)]


class _IN(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def vk(code, up=False):
    inp = _IN(INPUT_KEYBOARD, _U(ki=_KBD(code, 0, KEYEVENTF_KEYUP if up else 0, 0, None)))
    u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_IN))
    time.sleep(0.08)


# ---- 真实鼠标（SendInput 绝对坐标）：UIA 的 click_input 打不开 Qt 的下拉弹出层 ----
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE = 0x0001, 0x8000
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
SM_CXSCREEN, SM_CYSCREEN = 0, 1


class _M(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class _MU(ctypes.Union):
    _fields_ = [("mi", _M)]


class _MI(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _MU)]


def mouse_click(x, y, settle=0.9):
    sw, sh = u32.GetSystemMetrics(SM_CXSCREEN), u32.GetSystemMetrics(SM_CYSCREEN)
    ax, ay = int(x * 65535 / sw), int(y * 65535 / sh)
    for flags in (MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                  MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE,
                  MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE):
        inp = _MI(INPUT_MOUSE, _MU(mi=_M(ax, ay, 0, flags, 0, None)))
        u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_MI))
        time.sleep(0.08)
    time.sleep(settle)


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print(" [%s] %s  %s" % ("PASS" if cond else "FAIL", tag, detail), flush=True)


# ---------------------------------------------------------------- 窗口工具
def wtitle(h):
    n = u32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def wpid(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def client_size(h):
    r = wt.RECT()
    u32.GetClientRect(h, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


def window_rect(h):
    r = wt.RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def pids_of_exe(name):
    raw = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=15).stdout or b""
    res = set()
    for line in raw.decode("gbk", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == name and parts[1].isdigit():
            res.add(int(parts[1]))
    return res


def find_window(name, timeout=150):
    t0 = time.time()
    while time.time() - t0 < timeout:
        live = pids_of_exe(name)
        hit = []

        def cb(h, _l):
            if not u32.IsWindowVisible(h) or wpid(h) not in live:
                return True
            if "Build" not in wtitle(h):
                return True
            cw, ch = client_size(h)
            if cw < 400 or ch < 300:
                return True
            hit.append(h)
            return False

        u32.EnumWindows(EnumWindowsProc(cb), 0)
        if hit:
            return hit[0]
        time.sleep(0.5)
    return None


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BI(ctypes.Structure):
    _fields_ = [("bmiHeader", BIH), ("bmiColors", wt.DWORD * 3)]


def grab(hwnd, path):
    from PIL import Image
    cw, ch = client_size(hwnd)
    if cw <= 0 or ch <= 0:
        return None
    hdc = u32.GetDC(hwnd)
    mdc = g32.CreateCompatibleDC(hdc)
    hbmp = g32.CreateCompatibleBitmap(hdc, cw, ch)
    g32.SelectObject(mdc, hbmp)
    u32.PrintWindow(hwnd, mdc, 2)
    bi = BI()
    bi.bmiHeader.biSize = ctypes.sizeof(BIH)
    bi.bmiHeader.biWidth = cw
    bi.bmiHeader.biHeight = -ch
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(cw * ch * 4)
    g32.GetDIBits(mdc, hbmp, 0, ch, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (cw, ch), buf, "raw", "BGRA", 0, 1).convert("RGB")
    img.save(path)
    g32.DeleteObject(hbmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, hdc)
    return img


def applog():
    p = os.path.join(ROOT, "index_data", "logs", "app.log")
    return io.open(p, "rb").read() if os.path.isfile(p) else b""


# ---------------------------------------------------------------- UIA 工具
def txt(el):
    try:
        return el.window_text() or ""
    except Exception:
        return ""


def rect_of(el):
    try:
        r = el.rectangle()
        return (r.left, r.top, r.right, r.bottom)
    except Exception:
        return None


def area(a, b):
    """两个矩形的相交面积（px²）。"""
    x = min(a[2], b[2]) - max(a[0], b[0])
    y = min(a[3], b[3]) - max(a[1], b[1])
    return x * y if (x > 0 and y > 0) else 0


def find_btn(win, name):
    """按文字找按钮（先精确、后包含）。"""
    exact, fuzzy = None, None
    try:
        btns = win.descendants(control_type="Button")
    except Exception as e:
        print("   (descendants Button 失败 %r)" % e, flush=True)
        return None
    for b in btns:
        t = txt(b).strip()
        if t == name:
            exact = b
            break
        if name in t and fuzzy is None:
            fuzzy = b
    return exact or fuzzy


def click(el, tag):
    try:
        el.click_input()
        print("   [click] %s" % tag, flush=True)
        return True
    except Exception as e:
        print("   [click FAIL] %s: %r" % (tag, e), flush=True)
        return False


def dump(win, tag, types=("Spinner", "ComboBox", "Button", "Text", "CheckBox")):
    print("   ---- %s ----" % tag, flush=True)
    out = {}
    for ct in types:
        try:
            els = win.descendants(control_type=ct)
        except Exception:
            els = []
        for e in els:
            r = rect_of(e)
            if not r:
                continue
            print("    %-9s %-28s L%d T%d R%d B%d  w=%d h=%d" % (
                ct, repr(txt(e))[:28], r[0], r[1], r[2], r[3],
                r[2] - r[0], r[3] - r[1]), flush=True)
        out[ct] = els
    return out


def spin_report(win, tag):
    """返回 [(rect, element)] 并断言宽度。"""
    rs = []
    try:
        els = win.descendants(control_type="Spinner")
    except Exception:
        els = []
    for e in els:
        r = rect_of(e)
        if r:
            rs.append((r, e))
    print("   [%s] Spinner 数=%d" % (tag, len(rs)), flush=True)
    return rs


def overlap_report(win, tag, min_area=4):
    """可见控件两两求交，返回越界对列表。跳过「包含关系」（父子）。"""
    cts = ("Spinner", "Text", "Button", "CheckBox", "ComboBox", "Edit")
    items = []
    for ct in cts:
        try:
            els = win.descendants(control_type=ct)
        except Exception:
            els = []
        for e in els:
            r = rect_of(e)
            if r and (r[2] - r[0]) > 0 and (r[3] - r[1]) > 0:
                items.append((ct, txt(e), r))
    bad = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            ra, rb = a[2], b[2]
            inter = area(ra, rb)
            if inter < min_area:
                continue
            # 包含关系（父子/容器）跳过
            ca = (ra[0] <= rb[0] and ra[1] <= rb[1] and ra[2] >= rb[2] and ra[3] >= rb[3])
            cb = (rb[0] <= ra[0] and rb[1] <= ra[1] and rb[2] >= ra[2] and rb[3] >= ra[3])
            if ca or cb:
                continue
            bad.append((a[0], txt(a[1] if False else a[1])[:16], ra,
                        b[0], b[1][:16], rb, inter))
    print("   [%s] 控件数=%d  相交越界=%d" % (tag, len(items), len(bad)), flush=True)
    for x in bad[:12]:
        print("      ! %s(%s)%s  ×  %s(%s)%s  = %dpx²" % (
            x[0], x[1], x[2], x[3], x[4], x[5], x[6]), flush=True)
    return bad


# ---------------------------------------------------------------- 主流程
def main():
    from pywinauto import Desktop, Application

    exe = None
    for p in sorted(glob.glob(os.path.join(ROOT, "流明盒-v*.exe")), key=os.path.getmtime):
        if "2609250048" in p:
            exe = p
    if exe is None:
        exe = sorted(glob.glob(os.path.join(ROOT, "流明盒-v*.exe")),
                     key=os.path.getmtime)[-1]
    print("exe:", exe, flush=True)
    n0 = len(applog())
    proc = subprocess.Popen([exe], cwd=ROOT)

    try:
        h = find_window(os.path.basename(exe))
        check("L1 exe 启动且主窗出现", h is not None, "hwnd=%s" % h)
        if not h:
            return
        check("L2 标题是新版本 v1.34.1 / 2609250048",
              "2609250048" in wtitle(h) and "1.34.1" in wtitle(h), repr(wtitle(h)))
        print("  window rect =", window_rect(h), " client =", client_size(h), flush=True)

        time.sleep(6)
        u32.SetForegroundWindow(h)
        u32.ShowWindow(h, 9)
        time.sleep(1.5)

        # ⚠️ 坑：PyInstaller **onefile** 的应用跑在**子进程**里（`proc.pid` 是外壳父进程），
        # 用 `proc.pid` 过滤窗口会一个都匹配不到 → 工具窗/对话框全部「找不到」。
        # 必须从主窗 hwnd 反查真实 pid。
        main_pid = wpid(h)
        print("  proc.pid=%s  主窗 pid=%s  (onefile 子进程)" % (proc.pid, main_pid), flush=True)

        dk = Desktop(backend="uia")
        app = Application(backend="uia").connect(handle=h)
        win = app.window(handle=h)

        def child_windows(parent, keyword, depth=2):
            """在 UIA 树里按标题关键字找**子窗口**。

            ⚠️ 实测（v1.34.1 真机）：Qt 的对话框（工具窗 / 向量编辑 / 自动填充）
            在 UIA 里**不在 desktop 根下**，而是被挂成**父窗口的子 Window 节点**
            （desktop 根下只能看到主窗一个）。所以必须用 `descendants(control_type="Window")`
            从父窗口往下找，而不是 `Desktop().windows()`。
            """
            found = []

            def walk(node, lv):
                if lv > depth:
                    return
                try:
                    for w in node.descendants(control_type="Window"):
                        try:
                            t = w.window_text() or ""
                        except Exception:
                            continue
                        if keyword in t:
                            found.append(w)
                            return
                except Exception:
                    pass

            walk(parent, 0)
            return found[0] if found else None

        # ================= 反馈 3：智能推荐 工具行数值框 =================
        b_smart = find_btn(win, "智能推荐")
        check("L3 找到侧栏「智能推荐」", b_smart is not None)
        if b_smart is not None:
            click(b_smart, "侧栏 智能推荐")
        time.sleep(9)
        grab(h, os.path.join(SHOT, "l1_smart.png"))
        print("  [智能推荐] window rect =", window_rect(h), flush=True)

        spins = spin_report(win, "smart")
        check("L4 推荐墙工具行里有数值框", len(spins) >= 1, "n=%d" % len(spins))
        wide_ok = True
        for r, _e in spins:
            w = r[2] - r[0]
            print("      spinner w=%d  (L%d T%d R%d B%d)" % (w, r[0], r[1], r[2], r[3]),
                  flush=True)
            if w < 120:
                wide_ok = False
        check("L5 工具行数值框宽度 >= 120（修复前 72）", wide_ok and len(spins) >= 1)

        b_add = find_btn(win, "加强")
        gap = None
        if b_add is not None and spins:
            rb = rect_of(b_add)
            rs = spins[0][0]
            gap = rb[0] - rs[2]
            print("      「加强」rect=%s  spinner rect=%s  gap=%s" % (rb, rs, gap),
                  flush=True)
        check("L6 数值框与「加强」按钮间距 >= 4px",
              gap is not None and gap >= 4, "gap=%s" % gap)

        # ================= 反馈 1/2：自动填充对话框 =================
        b_tools = find_btn(win, "工具")
        check("L7 找到顶栏「工具」", b_tools is not None)
        tools_win = None
        if b_tools is not None:
            click(b_tools, "顶栏 工具")
            time.sleep(4)
            for _i in range(6):          # 工具窗要建十来个页面，给足时间
                tools_win = child_windows(win, "工具")
                if tools_win is not None:
                    break
                time.sleep(2)
        check("L8 工具窗口已打开", tools_win is not None,
              "rect=%s" % (str(rect_of(tools_win)) if tools_win is not None else "None"))

        b_nav = None
        if tools_win is not None:
            b_nav = find_btn(tools_win, "智能推荐")
            check("L9 工具里找到「智能推荐」页签", b_nav is not None)
            if b_nav is not None:
                click(b_nav, "工具 → 智能推荐")
                time.sleep(2.5)
                b_open = find_btn(tools_win, "打开向量编辑…")
                check("L10 找到「打开向量编辑…」", b_open is not None)
                if b_open is not None:
                    click(b_open, "打开向量编辑…")
                    time.sleep(2.5)

        vec_win = None
        for _i in range(6):
            vec_win = child_windows(tools_win, "向量编辑")
            if vec_win is None:
                vec_win = child_windows(win, "向量编辑")
            if vec_win is not None:
                break
            time.sleep(2)
        check("L11 向量编辑对话框已打开", vec_win is not None)
        if vec_win is None:
            return

        b_fill = find_btn(vec_win, "从画像自动填充…")
        check("L12 找到「从画像自动填充…」", b_fill is not None)
        if b_fill is None:
            return
        click(b_fill, "从画像自动填充…")
        time.sleep(3)

        dlg = None
        for _i in range(6):
            dlg = child_windows(vec_win, "从画像自动填充")
            if dlg is None:
                dlg = child_windows(win, "从画像自动填充")
            if dlg is not None:
                break
            time.sleep(2)
        check("L13 自动填充参数面板已打开", dlg is not None,
              "rect=%s" % (str(rect_of(dlg)) if dlg is not None else "None"))
        if dlg is None:
            return
        grab(vec_win.handle, os.path.join(SHOT, "l2_vector.png"))

        def measure(tag):
            d = {}
            try:
                d["rect"] = rect_of(dlg)
            except Exception:
                d["rect"] = None
            d["spins"] = [r for r, _e in spin_report(dlg, tag)]
            d["bad"] = overlap_report(dlg, tag)
            # 说明块 / 统计行：取最后两个 Text 控件（note / lb_est）
            try:
                texts = [rect_of(e) for e in dlg.descendants(control_type="Text")]
                texts = [t for t in texts if t]
                d["texts"] = texts
            except Exception:
                d["texts"] = []
            print("   [%s] dlg rect=%s" % (tag, d["rect"]), flush=True)
            if d["rect"]:
                print("   [%s] dlg h=%d w=%d" % (tag, d["rect"][3] - d["rect"][1],
                                                 d["rect"][2] - d["rect"][0]), flush=True)
            return d

        m_all = measure("scope=全部媒体库")
        try:
            grab(dlg.handle, os.path.join(SHOT, "l3_autofill_all.png"))
        except Exception as e:
            print("   (grab 失败 %r)" % e, flush=True)

        # --- 切到「我的收藏」 ---
        cb = None
        try:
            for c in dlg.descendants(control_type="ComboBox"):
                cb = c
                break
        except Exception:
            pass
        check("L14 对话框里有统计范围下拉框", cb is not None)
        # ⚠️ 坑（本轮实测）：pywinauto 的 `ComboBox.select("我的收藏（只统计收藏的影片）")`
        # 会抛 `IndexError: item ... not found or can't be accessed` ——
        # Qt 的 QComboBox 在 UIA 里**不把下拉项暴露成可选的 ListItem**（要展开才有）。
        # 正解：给下拉框焦点后**按方向键**（不可编辑的 QComboBox 按键即改选中项），
        # 然后把当前值读回来校验，确保真的切过去了。
        # ⚠️ 连踩两个坑（本轮实测）：
        #   ① `ComboBox.select("我的收藏（只统计收藏的影片）")` → IndexError，
        #      Qt 的 QComboBox 在 UIA 里**不把下拉项暴露成可选项**；
        #   ② 读 `cb.window_text()` 拿到的是**无障碍名**（QFormLayout 的行标签「统计」），
        #      **不是当前选中项** —— 拿它判「有没有切过去」永远是错的。
        # 正解：用**副作用**判定 —— 切到「我的收藏」后，面板里的范围提示文案会变成
        #   「只统计已收藏的影片 …」（见 `AutoFillDialog._refresh_est` 的三档文案）。
        def tip_texts():
            try:
                return [txt(e) for e in dlg.descendants(control_type="Text")]
            except Exception:
                return []

        def is_fav():
            return any("只统计已收藏的影片" in (t or "") for t in tip_texts())

        print("   combo 无障碍名 = %r（注意：不是当前值）" % txt(cb), flush=True)
        print("   切换前是「我的收藏」？%s" % is_fav(), flush=True)
        # 正解③（实测可行）：**真实鼠标**点开下拉 → 弹出层里 ListItem 才暴露出来
        # → 再真实鼠标点「我的收藏（只统计收藏的影片）」。
        # pywinauto 的 `click_input()` 打不开 Qt 的组合框弹出层（点了没反应），
        # 必须用 SendInput 的绝对坐标鼠标事件。
        switched = False
        if cb is not None:
            for attempt in range(3):
                try:
                    r = rect_of(cb)
                    mouse_click((r[0] + r[2]) // 2, (r[1] + r[3]) // 2, settle=1.2)
                    item = None
                    try:
                        for li in dlg.descendants(control_type="ListItem"):
                            if "我的收藏" in txt(li):
                                item = li
                                break
                    except Exception:
                        pass
                    if item is None:
                        print("   第 %d 次：没枚举到下拉项" % (attempt + 1), flush=True)
                        u32.SendInput(1, ctypes.byref(_IN(
                            INPUT_KEYBOARD, _U(ki=_KBD(0x1B, 0, 0, 0, None)))),
                            ctypes.sizeof(_IN))       # Esc 关掉弹出层
                        continue
                    ir = rect_of(item)
                    mouse_click((ir[0] + ir[2]) // 2, (ir[1] + ir[3]) // 2, settle=1.5)
                    time.sleep(2)
                    print("   第 %d 次切换后是「我的收藏」？%s" % (attempt + 1, is_fav()),
                          flush=True)
                    if is_fav():
                        switched = True
                        break
                except Exception as e:
                    print("   combo 切换失败: %r" % e, flush=True)
        time.sleep(3)
        m_fav = measure("scope=我的收藏")
        try:
            grab(dlg.handle, os.path.join(SHOT, "l4_autofill_fav.png"))
        except Exception as e:
            print("   (grab 失败 %r)" % e, flush=True)
        check("L15 下拉框切到「我的收藏」成功", switched)

        # ---- 判据 ----
        ha = m_all["rect"][3] - m_all["rect"][1] if m_all["rect"] else -1
        hf = m_fav["rect"][3] - m_fav["rect"][1] if m_fav["rect"] else -1
        check("L16 切范围前后对话框**高度**跳变 <= 2px（反馈 2）",
              ha > 0 and hf > 0 and abs(ha - hf) <= 2, "全部=%d 收藏=%d Δ=%d" % (ha, hf, abs(ha - hf)))

        all_spins = m_all["spins"] + m_fav["spins"]
        sw = [r[2] - r[0] for r in all_spins]
        check("L17 对话框里每个数值框宽度 >= 120（反馈 1，修复前 88/96）",
              len(sw) >= 8 and min(sw) >= 120,
              "n=%d min=%d max=%d" % (len(sw), min(sw) if sw else -1, max(sw) if sw else -1))

        check("L18 切「我的收藏」后任意控件两两不相交（反馈 1）",
              len(m_fav["bad"]) == 0, "越界对=%d" % len(m_fav["bad"]))
        check("L19 默认范围下任意控件两两不相交",
              len(m_all["bad"]) == 0, "越界对=%d" % len(m_all["bad"]))

        # Text 位置跳变
        ta, tf = m_all["texts"], m_fav["texts"]
        if len(ta) >= 2 and len(tf) >= 2:
            jump = [abs(a[1] - b[1]) for a, b in zip(ta[-2:], tf[-2:])]
            check("L20 说明块 / 统计行 y 跳变 <= 2px",
                  max(jump) <= 2, "jumps=%s" % jump)
        else:
            check("L20 说明块 / 统计行 y 跳变 <= 2px", False,
                  "texts=%d/%d" % (len(ta), len(tf)))

        # ---- 收尾 ----
        try:
            cb_cancel = find_btn(dlg, "取消")
            if cb_cancel is not None:
                click(cb_cancel, "取消")
        except Exception:
            pass
        time.sleep(1)

        fresh = applog()[n0:]
        check("L21 真机无「未捕获异常」", ERR_MARK not in fresh,
              "count=%d" % fresh.count(ERR_MARK))
        check("L22 真机无 Traceback", b"Traceback" not in fresh,
              "count=%d" % fresh.count(b"Traceback"))
    finally:
        time.sleep(1)
        try:
            proc.terminate()
        except Exception:
            pass
        time.sleep(2)
        try:
            proc.kill()
        except Exception:
            pass

    print("\n" + "=" * 74)
    print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    for f in FAIL:
        print("  -", f)
    print("=" * 74)


if __name__ == "__main__":
    main()
