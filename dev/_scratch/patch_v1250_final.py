# -*- coding: utf-8 -*-
"""v1.25.0 收尾补丁 3：
  A) live_verify —— 确认框要「点左边那个按钮」，不能按回车；
  B) smoke_v1250 —— 补 J 段（选中定时器复用 + 已析构对象兜底）并把版本号推到 0035。

为什么不能用回车（第二轮真机验收踩的）：
`ui_settings._tagopt_apply()` 用的是
    QMessageBox.question(self, "确认写入标签", …, Yes|No, **QMessageBox.No**)
—— **默认按钮被刻意设成 No**（破坏性动作的安全默认）。按回车 = 触发默认按钮 = No
= 直接 return，于是「确认框消失了、文件一个字节没变、日志里毫无异常」。
第一版验收脚本正是这么被坑的（夹具 nfo 无 .bak、无新增标签）。
"""
import os

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"


def patch(rel, label, old, new, count=1):
    p = os.path.join(ROOT, rel)
    with open(p, encoding="utf-8", newline="") as f:
        s = f.read()
    n = s.count(old)
    if n != count:
        print(f"[失败] {label}: 锚点命中 {n} 次（期望 {count}）")
        print("----- 锚点 -----")
        print(old[:400])
        raise SystemExit(1)
    s = s.replace(old, new, count)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print(f"[OK] {label}")


# ============================================================== A) live_verify
patch(
    r"dev\live_verify.py",
    "live_verify：新增 bottom_button_centers / confirm_modal_yes",
    "def scan_sidebar(path):",
    '''def bottom_button_centers(pm):
    """从确认框截图里找出底部按钮的横向中心（左 → 右）。

    为什么不用固定坐标：QMessageBox 的按钮宽度随文案 / 字体 / DPI 变化，写死会在
    改文案后**静默点空**。这里直接扫「底部条带里的亮像素列」——确认框底部只有按钮
    是亮的（本主题下按钮是浅色圆角块），聚类即得每个按钮的中心，天然自适应。
    """
    img = pm.toImage()
    w, h = img.width(), img.height()
    cols = []
    for x in range(w):
        n = 0
        for y in range(max(0, h - 34), max(1, h - 4)):
            c = img.pixelColor(x, y)
            if c.red() > 90 and c.green() > 90 and c.blue() > 90:
                n += 1
        cols.append(n)
    groups, cur = [], None
    for x, n in enumerate(cols):
        if n > 0 and cur is None:
            cur = x
        elif n == 0 and cur is not None:
            if x - cur >= 8:
                groups.append(((cur + x - 1) // 2, x - cur))
            cur = None
    if cur is not None:
        groups.append(((cur + w - 1) // 2, w - cur))
    groups.sort()
    return groups


def confirm_modal_yes(app, hwnd, label="确认框"):
    """点确认框里**最左边**那个按钮（Qt 的 `Yes | No` 顺序是 Yes 在前）。

    ⚠ 不能图省事按回车（v1.25.0 真机验收第二轮踩坑）：
    `ui_settings._tagopt_apply()` 是
        QMessageBox.question(..., Yes | No, QMessageBox.No)
    —— 默认按钮**刻意设成 No**（破坏性动作的安全默认）。回车 = 触发默认按钮 = No
    = 立刻 return，表现是「确认框消失了、目标文件一个字节没变、日志毫无异常」。
    """
    pm = grab(app, hwnd, tries=6, settle=3)
    grp = bottom_button_centers(pm)
    print(f"[{label}] 底部按钮中心(宽度): {grp}", flush=True)
    if not grp:
        print(f"[{label}] 没扫到按钮，退回「按回车」", flush=True)
        return press_ok(hwnd)
    cx = grp[0][0]
    cy = max(0, pm.height() - 22)
    print(f"[{label}] 点最左按钮 @({cx},{cy})", flush=True)
    click(hwnd, cx, cy)
    time.sleep(1.2)
    ok = not bool(u32.IsWindow(hwnd))
    if not ok:
        print(f"[{label}] 点完还在，改按回车兜底", flush=True)
        ok = press_ok(hwnd)
    return ok


def scan_sidebar(path):''',
)

patch(
    r"dev\live_verify.py",
    "live_verify：执行写入改走 confirm_modal_yes",
    '''                            print(f"[确认框] 已确认={press_ok(mb)}", flush=True)''',
    '''                            print(f"[确认框] 已确认={confirm_modal_yes(app, mb)}",
                                  flush=True)''',
)

patch(
    r"dev\live_verify.py",
    "live_verify：等待写入完成更稳（先看状态栏再截图）",
    '''                        else:
                            print("[警告] 没等到确认框；后续点击可能全部失效", flush=True)
                        time.sleep(7.0)''',
    '''                        else:
                            print("[警告] 没等到确认框；后续点击可能全部失效", flush=True)
                        time.sleep(9.0)''',
)


# ============================================================== B) smoke_v1250
patch(
    r"dev\smoke_v1250.py",
    "smoke：版本号 0034 -> 0035",
    '''    check("A2 内部构建号 2609210034", ver.BUILD == "2609210034", ver.BUILD)''',
    '''    check("A2 内部构建号 2609210035", ver.BUILD == "2609210035", ver.BUILD)''',
)

patch(
    r"dev\smoke_v1250.py",
    "smoke：A 段标题同步",
    '''section("A. 版本号（v1.25.0 / Build 2609210034）")''',
    '''section("A. 版本号（v1.25.0 / Build 2609210035）")''',
)

patch(
    r"dev\smoke_v1250.py",
    "smoke：插入 J 段（定时器复用 + 已析构兜底）",
    '''# ============================================================ 汇总
print("\\n" + "=" * 72)''',
    '''# ============================================================ 汇总
section("J. 发布前加固：选中定时器复用 + 已析构对象兜底（Build 0035）")
try:
    import shiboken6
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import main_window as mw

    rows = [{"id": 9100 + i, "title": "加固%d" % i, "library": "L", "kind": "电影",
             "file_path": "Z:/x/%d.mp4" % i, "poster": "", "favorite": 0,
             "genres": "", "year": 2020, "rating": 0, "user_rating": 0}
            for i in range(2)]
    card = mw.PosterCard(rows[0], lambda *a: None, on_select=lambda *a: None)

    # 旧写法是「每次选中都新建 QTimer 并覆盖旧引用」→ 旧对象一旦被析构，
    # self._timer 就成了「已析构的 C++ 对象」。这里先钉死新写法是「只建一次、复用」。
    card.set_selected(True)
    t1 = card._timer
    check("J1 选中后建了定时器且在跑",
          t1 is not None and t1.isActive())
    card.set_selected(False)
    check("J2 取消选中是 stop 同一个定时器（不是把对象丢掉）",
          card._timer is t1 and not t1.isActive())
    card.set_selected(True)
    check("J3 再次选中复用同一个 QTimer（不再新建）",
          card._timer is t1 and t1.isActive())

    # 真机崩溃点：app.log 2026-09-21 09:25:33
    #   mousePressEvent → _select_card → set_selected
    #   RuntimeError: Internal C++ object (QTimer) already deleted
    shiboken6.delete(t1)
    card._selected = False
    err = ""
    try:
        card.set_selected(True)
    except Exception as e:
        err = "%s: %s" % (type(e).__name__, e)
    check("J4 定时器已被析构时 set_selected 不抛异常", err == "", err)
    t2 = card._timer
    check("J5 并且按需重建了一个可用的新定时器",
          err == "" and t2 is not None and t2 is not t1 and t2.isActive(),
          "err=%r timer=%r" % (err, t2))

    # _select_card 的目标卡片也可能已被换页/刷新析构（队列里残留的鼠标事件）。
    # 用「桩对象」直接调真实方法体，避免为了这一条去建一个完整 MainWindow。
    class _Stub:
        _selected_card = None

        def _apply_card_glow(self, c):
            pass

    stub = _Stub()
    victim = mw.PosterCard(rows[1], lambda *a: None, on_select=lambda *a: None)
    err2 = ""
    try:
        mw.MainWindow._select_card(stub, victim)
        shiboken6.delete(victim)
        mw.MainWindow._select_card(stub, victim)      # 已析构 → 必须安静跳过
    except Exception as e:
        err2 = "%s: %s" % (type(e).__name__, e)
    check("J6 对已析构的卡片调用 _select_card 不抛异常", err2 == "", err2)
    check("J7 目标已析构时不会把它记成当前选中项", stub._selected_card is not victim)

    # 旧写法必须真的消失（防止以后被改回去）
    _src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "src", "main_window.py"), encoding="utf-8").read()
    check("J8 源码里已无「每次新建定时器」的旧写法",
          "elif self._timer:" not in _src and
          _src.count("定时器「只建一次、之后复用」") == 2)
except Exception:
    check("J 加固", False, traceback.format_exc().splitlines()[-1])

print("\\n" + "=" * 72)''',
)

print("\n补丁 3 完成。")
