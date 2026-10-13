# -*- coding: utf-8 -*-
"""v1.40.5 离屏冒烟 —— 两条留白反馈的源码级 + 真建控件级断言。

自证：脚本开头 print 去重模块的 __file__，确认走的是 E 盘真源。
运行必须用 managed python（GUI 走 offscreen 平台）。
"""
import os
import sys
import re

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

E = r"E:\【01】自研软件\【26-19】本地影视中心"
SRC = os.path.join(E, "src")
sys.path.insert(0, SRC)
os.chdir(E)

USRC = open(os.path.join(SRC, "ui_settings.py"), encoding="utf-8").read()
SSRC = open(os.path.join(SRC, "scraper.py"), encoding="utf-8").read()
VSRC = open(os.path.join(SRC, "version.py"), encoding="utf-8").read()

import version as ver
print("[自证] version:", ver.__file__)
print("[自证] ui_settings:", os.path.join(SRC, "ui_settings.py"))
print("[自证] scraper:", os.path.join(SRC, "scraper.py"))
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
check(ver.VERSION == "v1.40.5", f"VERSION == v1.40.5（实际 {ver.VERSION}）")
check(ver.BUILD == "2610130068", f"BUILD == 2610130068（实际 {ver.BUILD}）")
check(ver.MINOR_ITER == 5, f"MINOR_ITER == 5（实际 {ver.MINOR_ITER}）")
check(ver.BUILD_SEQ == "0068", f"BUILD_SEQ == 0068（实际 {ver.BUILD_SEQ}）")
check("# 0068" in VSRC, "version.py 含 # 0068 说明段")

# ============================================================ ② 反馈 1：合并两组框为一行
print()
print("=== ② 反馈 1：开关行与统计行合并为一个组框的一行 ===")
# 旧的两个独立组框标题必须消失（只剩一个「演员刮削」）
_ge_cnt = USRC.count('QGroupBox("演员刮削")')
check(_ge_cnt == 1, f"源码里只出现一次 QGroupBox(演员刮削)（实际 {_ge_cnt}）")
check('QGroupBox("演员资料统计")' not in USRC,
      "旧的独立组框 QGroupBox(\"演员资料统计\") 已移除")
check('QGroupBox("演员刮削")' in USRC, "合并后的组框标题仍是「演员刮削」")
# 合并后的布局是水平布局 + 收紧的 contentsMargins
check(re.search(r'ge = QGroupBox\("演员刮削"\)\s*\n\s*geh = QHBoxLayout\(ge\)', USRC)
      is not None, "合并后用 QHBoxLayout（水平一行）")
check("geh.setContentsMargins(9, 4, 9, 4)" in USRC,
      "合并后组框内部上下留白收紧到 4（去掉两个各 30px 空白）")
check("geh.setSpacing(12)" in USRC, "合并后行内间距 12")
# 关键属性名必须保留
check("self.sc_enabled = ToggleSwitch(" in USRC, "self.sc_enabled 属性名保留")
check("self.sc_stats = QLabel(" in USRC, "self.sc_stats 属性名保留")
check("geh.addWidget(self.sc_enabled, 0)" in USRC, "开关加进合并行")
check("geh.addWidget(self.sc_stats, 1)" in USRC, "统计串加进合并行（弹性 1）")
check("geh.addStretch(1)" in USRC, "合并行中间有弹性分隔")
check(USRC.count("refresh.clicked.connect(self._refresh_scraper_stats)") == 1,
      "「刷新统计」按钮仍接 _refresh_scraper_stats")
check("v.addWidget(ge)" in USRC, "合并后的组框加进页面")
# 旧写法必须不再出现
check("gev = QVBoxLayout(ge)" not in USRC, "旧的 gev 垂直布局已移除")
check("gsv = QVBoxLayout(gs)" not in USRC, "旧的 gsv（统计组框）垂直布局已移除")

# ============================================================ ③ 反馈 2：按钮与提示同行
print()
print("=== ③ 反馈 2：数据源组框内「按钮 + 提示」同行 ===")
# src_hint 必须加进 sbh（按钮行的水平布局），而不是 g0v（组框垂直布局）
check("sbh.addWidget(self.src_hint, 3)" in USRC,
      "src_hint 加进按钮行的 QHBoxLayout（同行）")
check("g0v.addWidget(self.src_hint)" not in USRC,
      "src_hint **不再**作为组框里独立的一行（旧写法已移除）")
check("sbh.addStretch(1)" in USRC, "按钮与提示之间用弹性分隔")
# ⚠ 关键：折行 QLabel 同行时不能用 Ignored（会把组框 sizeHint 撑爆到 831）
check("self.src_hint.setSizePolicy(_SP.Minimum, _SP.Preferred)" in USRC,
      "src_hint 用 SizePolicy.Minimum（不是 Ignored）")
check("self.src_hint.setSizePolicy(_SP.Ignored" not in USRC,
      "src_hint **没有**用 Ignored（后者会撑爆组框到 831px）")
check("_SP.Ignored, _SP.Preferred)\n        g0v.addWidget(src_hint)" not in USRC,
      "旧「Ignored + 独立一行」的写法未复现")
# 组框 spacing 8 → 4
check(re.search(r'g0v = QVBoxLayout\(g0\)\s*\n\s*# v1\.40\.5[^\n]*\n\s*g0v\.setSpacing\(4\)', USRC)
      is not None, "数据源组框 spacing 已改为 4")

# ============================================================ ④ 真建控件
print()
print("=== ④ 真建控件：量各组件 sizeHint ===")
try:
    from PySide6.QtWidgets import (QApplication, QGroupBox, QScrollArea,
                                   QLabel, QPushButton, QWidget)
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
    dlg.resize(1334, 960)
    dlg.show()
    app.processEvents()

    pg = dlg._pg_scraper
    if isinstance(pg, QScrollArea):
        pg = pg.widget()
    lay = pg.layout()

    boxes = []
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if isinstance(w, QGroupBox):
            boxes.append((i, w))

    # ① 只剩一个「演员刮削」组框、高度显著下降
    ge = [w for _, w in boxes if w.title() == "演员刮削"]
    check(len(ge) == 1, f"刮削页只有一个「演员刮削」组框（实际 {len(ge)}）")
    ge = ge[0]
    ge_sh = ge.sizeHint().height()
    check(ge_sh < 100,
          f"「演员刮削」组框 sizeHint < 100（v1.40.4 两框合计 159；实际 {ge_sh}）")
    print(f"         [实测] 演员刮削行 sizeHint={ge_sh}（v1.40.4：78 + 81 = 159）")
    # 组框内是水平布局、无 QVBoxLayout
    check(ge.layout().count() == 5,
          f"合并行有 5 个子项（文字 / 开关 / 弹性 / 统计 / 按钮；实际 {ge.layout().count()}）")
    check("QSpacerItem" in [type(ge.layout().itemAt(j)).__name__ for j in range(ge.layout().count())],
          "合并行里确实有一个弹性分隔（QSpacerItem）")

    # ② 数据源组框显著变矮
    g0 = [w for _, w in boxes if w.title().startswith("演员刮削数据源")]
    check(len(g0) == 1, "找到数据源组框")
    g0 = g0[0]
    g0_sh = g0.sizeHint().height()
    check(g0_sh <= 240,
          f"数据源组框 sizeHint <= 240（v1.40.4 是 262；实际 {g0_sh}）")
    print(f"         [实测] 数据源组框 sizeHint={g0_sh}（v1.40.4：262）")

    # src_hint 与按钮在同一 widget 里（同一个 QHBoxLayout 父容器）
    hints = [w for w in pg.findChildren(QLabel) if w.text().startswith("提示：minnano-av")]
    check(len(hints) == 1, "找到唯一的 src_hint 标签")
    if hints:
        h = hints[0]
        parent = h.parentWidget()
        btns = [b for b in parent.findChildren(QPushButton)] if parent else []
        names = [b.text() for b in btns]
        check("测试全部数据源" in names,
              f"src_hint 与「测试全部数据源」同一父容器（实际按钮 {names}）")
        check("Cloudflare 验证…" in names,
              f"src_hint 与「Cloudflare 验证…」同一父容器")
        print(f"         [实测] src_hint 父容器 = {type(parent).__name__}，含按钮 {names}")

    # ③ 页面整体变矮
    page_sh = pg.sizeHint().height()
    check(page_sh <= 850,
          f"刮削页 sizeHint <= 850（v1.40.4 是 944；实际 {page_sh}）")
    print(f"         [实测] 刮削页 sizeHint={page_sh}（v1.40.4：944）")

    # ④ 高度硬锁未受影响（v1.40.4 回归）
    mn, mx = dlg.minimumHeight(), dlg.maximumHeight()
    check(mn == mx, f"工具窗高度仍被钉死（minH={mn} maxH={mx}）")

    dlg.close()
except Exception as e:
    import traceback
    traceback.print_exc()
    bad("真建控件段执行", f"{type(e).__name__}: {e}")

# ============================================================ ⑤ 回归
print()
print("=== ⑤ v1.40.4 回归 ===")
check("self.setFixedHeight(h)" in USRC, "工具窗高度硬锁 setFixedHeight(h) 仍在")
check(re.search(r"v\.addWidget\(g3\)\s*\n\s*self\._refresh_scraper_stats\(\)", USRC)
      is not None, "执行页仍无页尾弹簧（v1.40.4）")
check("g3v.addWidget(self.sc_log, 1)" not in USRC, "日志框仍不在组内吃 stretch=1")
check("self.sc_log.setFixedHeight(96)" in USRC, "日志框仍固定 96px")
check('out["stage"] = "waf"' in SSRC, "v1.40.4 的 stage=waf 档仍在")
check("def _waf_outlet(" in SSRC, "v1.40.4 的 _waf_outlet 仍在")
check("def _stage_cn(" in USRC, "v1.40.4 的 _stage_cn 仍在")
check("def diagnose_host(" in SSRC, "diagnose_host 仍存在")
check("self._restore_open_btn()" in USRC, "v1.40.3 的 _restore_open_btn 仍在")
check("on_top=True" in open(os.path.join(SRC, "cf_browser.py"), encoding="utf-8").read(),
      "cf_browser 的 on_top=True 仍在")

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
