# -*- coding: utf-8 -*-
"""v1.40.6 离屏冒烟 —— 「工具窗高度按页自适应 + 可拉伸」的源码级 + 真建控件级断言。

自证：脚本开头 print 去重模块的 __file__，确认走的是 E 盘真源。
运行必须用 managed python（GUI 走 offscreen 平台）。
"""
import os
import re
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

E = r"E:\【01】自研软件\【26-19】本地影视中心"
SRC = os.path.join(E, "src")
sys.path.insert(0, SRC)
os.chdir(E)

USRC = open(os.path.join(SRC, "ui_settings.py"), encoding="utf-8").read()
VSRC = open(os.path.join(SRC, "version.py"), encoding="utf-8").read()

import version as ver
print("[自证] version:", ver.__file__)
print("[自证] ui_settings:", os.path.join(SRC, "ui_settings.py"))
print()

PASS = []
FAIL = []


def ok(name):
    PASS.append(name)
    print("  [OK ]", name)


def bad(name, extra=""):
    FAIL.append(name)
    print("  [FAIL]", name, extra)


def check(cond, name, extra=""):
    if cond:
        ok(name)
    else:
        bad(name, extra)


# ============================================================ ① 版本号
print("=== ① 版本号 ===")
check(ver.VERSION == "v1.40.6", f"VERSION == v1.40.6（实际 {ver.VERSION}）")
check(ver.BUILD == "2610130069", f"BUILD == 2610130069（实际 {ver.BUILD}）")
check(ver.MINOR_ITER == 6, f"MINOR_ITER == 6（实际 {ver.MINOR_ITER}）")
check(ver.BUILD_SEQ == "0069", f"BUILD_SEQ == 0069（实际 {ver.BUILD_SEQ}）")
check("# 0069" in VSRC, "version.py 含 # 0069 说明段")

# ============================================================ ② 源码：取消硬锁
print()
print("=== ② 源码：取消纵向硬锁 + 引入上下界常量 ===")
check("MIN_H = 560" in USRC, "类常量 MIN_H = 560 在")
check("MAX_H = 960" in USRC, "类常量 MAX_H = 960 在")
check("self.setMinimumHeight(self.MIN_H)" in USRC,
      "__init__ 改 setMinimumHeight(MIN_H)")
# 对话框自身不得再用 setFixedHeight（子控件的不算）
_ge_block = USRC[USRC.find("class SettingsDialog"):USRC.find("def _build(self)")]
check("self.setFixedHeight(h)" not in USRC,
      "对话框**不再**调 setFixedHeight(h)（v1.40.4 的硬锁已取消）")
check("self.setFixedHeight" not in _ge_block,
      "SettingsDialog.__init__ 段内没有 self.setFixedHeight")
check("h = min(self.MAX_H," in USRC, "初始高公式改用 MAX_H")
check("self._program_resize = True" in USRC, "__init__ 里用 _program_resize 标记程序 resize")
check("self._auto_h = max(h, self.MIN_H)" in USRC, "__init__ 记 _auto_h")
check("self._user_resized_h = None" in USRC, "__init__ 初始化 _user_resized_h")

# ============================================================ ③ 源码：三个新方法
print()
print("=== ③ 源码：_compact_to / _unwrap_page / resizeEvent ===")
check("def _compact_to(" in USRC, "新增 _compact_to()（收矮窗口）")
check("def _unwrap_page(" in USRC, "新增 _unwrap_page()（解包滚动区）")
check("def resizeEvent(" in USRC, "新增 resizeEvent()（区分用户拖动）")
check("sc.takeWidget()" in USRC, "_unwrap_page 用 takeWidget() 摘出内层")
check("inner.setMinimumHeight(0)" in USRC,
      "_unwrap_page 复位内层 minimumHeight（_make_scrollable 钉过）")
check("self._compact_to(need)" in USRC, "_fit_page 放得下时调 _compact_to")
check("self._grow_to(need)" in USRC, "_fit_page 放不下时仍调 _grow_to")
# 关键：滚动页也要先解包再长高（v1.40.6 修的「滚动页永远不长高」）
check(USRC.count("self._unwrap_page(pg)") >= 1, "_fit_page 调用 _unwrap_page(pg)")
# ★ v1.40.6 第二轮（真机 1408 缺陷）：内容 > MAX_H 的页**不解包**（否则窗口被顶穿）
check("if need <= self.MAX_H:" in USRC,
      "_fit_page 先判「装得进 MAX_H 吗」再决定解包（真机 1408 缺陷的修法）")
check("内容 > MAX_H：**不解包**" in USRC,
      "内容超上限的页保持滚动区形态（不让布局最小高顶穿窗口）")
check("self._make_scrollable(pg)\n                    pg = self.stack.currentWidget()" in USRC,
      "超上限页：裸页先包滚动区，再长高")
# _grow_to 补 MAX_H 封顶
check("min(need_content_h + extra + 8, self.MAX_H, scr_max)" in USRC,
      "_grow_to 已用 MAX_H 封顶")
check("availableGeometry().height() - 40" in USRC,
      "_grow_to 屏幕余量口径与 __init__ 统一为 -40")

# ============================================================ ④ 真建控件
print()
print("=== ④ 真建控件：可拉伸 + 自适应 + 用户拖动优先 ===")
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"):
        if os.path.isfile(fp):
            QFontDatabase.addApplicationFont(fp)
            break
    from main_window import load_style
    load_style(app)

    import ui_settings

    dlg = ui_settings.SettingsDialog()
    dlg.show()                    # 不预 resize，让 __init__ 的默认高生效
    app.processEvents()

    mn, mx = dlg.minimumHeight(), dlg.maximumHeight()
    check(mn == dlg.MIN_H, f"最小高 == MIN_H（{mn} vs {dlg.MIN_H}）")
    check(mn != mx, f"**不再是固定高**（minH={mn} maxH={mx} 应不等 → 可拉伸）")
    check(getattr(dlg, "_user_resized_h", "x") is None,
          f"刚 show 完未被误标成「用户拖过」（实际 {dlg._user_resized_h}）")
    check(getattr(dlg, "_auto_h", None) is not None,
          f"_auto_h 已记录（实际 {getattr(dlg, '_auto_h', None)}）")

    # 逐页切换：窗口高应随内容自适应
    print("         [逐页] 页 / content / 窗口高")
    seq = [("手动修改", 560), ("AI引擎设置", 616), ("图像检测", 693),
           ("演员检测", 766), ("个性化设置", None), ("演员刮削", None)]
    heights = {}
    for key, expect in seq:
        dlg._show(key)
        for _ in range(4):
            app.processEvents()
        pg = dlg.stack.currentWidget()
        inner = pg
        d = 0
        while hasattr(inner, "widget") and inner.widget() is not None and d < 4:
            inner = inner.widget()
            d += 1
        need = dlg._content_height(inner)
        h = dlg.height()
        heights[key] = h
        print("              %-12s content=%5d  窗口高=%4d" % (key, need, h))
        check(dlg.MIN_H <= h <= dlg.MAX_H,
              f"「{key}」窗口高在 [MIN_H, MAX_H]（实际 {h}）")

    # 矮页必须明显比高页矮（自适应生效的硬证据）
    check(heights["手动修改"] < heights["个性化设置"],
          f"「手动修改」({heights['手动修改']}) 比「个性化设置」({heights['个性化设置']}) 矮 → 自适应生效")
    check(heights["图像检测"] < heights["演员检测"],
          f"「图像检测」({heights['图像检测']}) 比「演员检测」({heights['演员检测']}) 矮")
    check(heights["手动修改"] == dlg.MIN_H,
          f"「手动修改」content=398 → 收到 MIN_H（实际 {heights['手动修改']}）")

    # 用户拖动之后，切页不再自动收放
    dlg.resize(dlg.width(), 700)
    app.processEvents()
    check(dlg._user_resized_h == 700,
          f"手动 resize 到 700 被记为「用户拖过」（实际 {dlg._user_resized_h}）")
    dlg._show("手动修改")
    for _ in range(4):
        app.processEvents()
    check(dlg.height() == 700,
          f"用户拖过后切「手动修改」不再自动收矮（实际 {dlg.height()}）")

    # 清掉标记后自适应恢复
    dlg._user_resized_h = None
    dlg._show("手动修改")
    for _ in range(4):
        app.processEvents()
    check(dlg.height() < 700,
          f"清标记后切「手动修改」恢复自适应（实际 {dlg.height()}）")

    # ★★★ v1.40.6 第二轮：**真机口径**下必须所有页都被 MAX_H 封顶
    #   离屏平台可用高只有 800 → 上限被压到 760，`MAX_H=960` 这条分支根本走不到。
    #   真机是 2560x1440（可用高 1392）→ h = min(960, 1352) = 960，才是「紧凑」的真实场景。
    #   所以这里把 screen() 换成假屏幕，复刻真机口径再逐页走一遍。
    print("         [真机口径] 模拟 2560x1440 屏幕后逐页复测")
    from PySide6.QtCore import QRect as _QRect

    class _FakeScr:
        def availableGeometry(self):
            return _QRect(0, 0, 2560, 1392)

        def geometry(self):
            return _QRect(0, 0, 2560, 1440)

    _fs = _FakeScr()
    _orig_screen = ui_settings.SettingsDialog.screen
    ui_settings.SettingsDialog.screen = lambda self: _fs
    try:
        dlg2 = ui_settings.SettingsDialog()
        dlg2.show()
        for _ in range(8):
            app.processEvents()
        check(dlg2.height() == dlg2.MAX_H,
              f"真机口径初始高 == MAX_H（实际 {dlg2.height()}）")
        real_pages = [("手动修改", "_pg_manual"), ("服务管理", "_pg_service"),
                      ("AI引擎设置", "_pg_aiengine"), ("图像检测", "_pg_imagedetect"),
                      ("演员检测", "_pg_actorcheck"), ("画像概览", "_pg_insight"),
                      ("演员刮削", "_pg_scraper"), ("重复检测", "_pg_dedupe"),
                      ("标签优化", "_pg_tagopt"), ("智能推荐", "_pg_smart"),
                      ("数据与日志", "_pg_data"), ("个性化设置", "_pg_personal")]
        over = []
        rh = {}
        for key, attr in real_pages:
            dlg2._show(key)
            for _ in range(8):
                app.processEvents()
            hh = dlg2.height()
            rh[key] = hh
            print("              %-12s 窗口高=%4d" % (key, hh))
            if not (dlg2.MIN_H <= hh <= dlg2.MAX_H):
                over.append((key, hh))
        check(not over,
              f"真机口径下 12 页窗口高全在 [{dlg2.MIN_H}, {dlg2.MAX_H}]"
              + (f"（超界：{over}）" if over else "（无超界）"))
        check(rh.get("个性化设置") == dlg2.MAX_H,
              f"★ 「个性化设置」(内容 1413) 被 MAX_H 封顶（实际 {rh.get('个性化设置')}）")
        check(rh.get("智能推荐") == dlg2.MAX_H,
              f"★ 「智能推荐」(内容 976) 被 MAX_H 封顶（实际 {rh.get('智能推荐')}）")
        check(rh.get("手动修改", 9999) < rh.get("个性化设置", 0),
              f"真机口径「手动修改」({rh.get('手动修改')}) < 「个性化设置」({rh.get('个性化设置')})")
        # 反复来回切，验证不漂
        for _ in range(3):
            dlg2._show("个性化设置")
            for _ in range(4):
                app.processEvents()
            dlg2._show("手动修改")
            for _ in range(4):
                app.processEvents()
        check(dlg2.height() == dlg2.MIN_H,
              f"来回切 3 轮后仍能收回 MIN_H（实际 {dlg2.height()}）")
        dlg2.close()
    finally:
        ui_settings.SettingsDialog.screen = _orig_screen

    dlg.close()
except Exception as e:
    import traceback
    traceback.print_exc()
    bad("真建控件段执行", f"{type(e).__name__}: {e}")

# ============================================================ ⑤ v1.40.5 回归
print()
print("=== ⑤ v1.40.5 / v1.40.4 回归 ===")
check('QGroupBox("演员刮削")' in USRC, "v1.40.5 合并后的「演员刮削」组框仍在")
check('QGroupBox("演员资料统计")' not in USRC, "旧「演员资料统计」独立组框仍不在")
check("geh.setContentsMargins(9, 4, 9, 4)" in USRC, "v1.40.5 组框内边距收紧仍在")
check("self.src_hint.setSizePolicy(_SP.Minimum, _SP.Preferred)" in USRC,
      "v1.40.5 的 src_hint SizePolicy.Minimum 仍在")
check("sbh.addWidget(self.src_hint, 3)" in USRC, "v1.40.5 的「按钮 + 提示同行」仍在")
check("g0v.setSpacing(4)" in USRC, "v1.40.5 数据源组框 spacing=4 仍在")
check("self.sc_log.setFixedHeight(96)" in USRC, "日志框固定 96px 仍在")
check("def _make_scrollable(" in USRC, "_make_scrollable 仍在（v1.40.0）")
check(re.search(r"v\.addWidget\(g3\)\s*\n\s*self\._refresh_scraper_stats\(\)", USRC)
      is not None, "执行页仍无页尾弹簧（v1.40.4）")
check("def diagnose_host(" in open(os.path.join(SRC, "scraper.py"),
                                   encoding="utf-8").read(),
      "v1.40.4 的 diagnose_host 仍在")

# ============================================================ 汇总
print()
print("=" * 60)
print(f"结果：{len(PASS)} 项通过 / {len(FAIL)} 项失败")
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("   -", f)
    sys.exit(1)
print("全部通过 ✅")
