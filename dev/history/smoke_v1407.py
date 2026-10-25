# -*- coding: utf-8 -*-
"""v1.40.7 离屏冒烟 —— 「工具窗固定默认 1320×960 + 内部模块冻结」的源码级 + 真建控件级断言。

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
check(ver.VERSION == "v1.40.7", f"VERSION == v1.40.7（实际 {ver.VERSION}）")
check(ver.BUILD == "2610130070", f"BUILD == 2610130070（实际 {ver.BUILD}）")
check(ver.MINOR_ITER == 7, f"MINOR_ITER == 7（实际 {ver.MINOR_ITER}）")
check(ver.BUILD_SEQ == "0070", f"BUILD_SEQ == 0070（实际 {ver.BUILD_SEQ}）")
check("# 0070" in VSRC, "version.py 含 # 0070 说明段")

# ============================================================ ② 源码：固定默认尺寸
print()
print("=== ② 源码：固定默认尺寸 1320×960 + 新常量 ===")
check("DEF_W = 1320" in USRC, "类常量 DEF_W = 1320 在")
check("DEF_H = 960" in USRC, "类常量 DEF_H = 960 在")
check("NAV_W = 150" in USRC, "类常量 NAV_W = 150 在")
check("CONTENT_W = DEF_W - NAV_W" in USRC, "CONTENT_W = DEF_W - NAV_W（= 1170）")
check("self.resize(w, h)" in USRC, "__init__ 仍用 resize(w, h)")
check("w = min(self.DEF_W, max(760, avail.width() - 40))" in USRC,
      "默认宽取 DEF_W（仅小屏收敛）")
check("h = min(self.DEF_H, max(self.MIN_H, avail.height() - 40))" in USRC,
      "默认高取 DEF_H（仅小屏收敛）")
check("self.setMinimumHeight(self.MIN_H)" in USRC,
      "仍 setMinimumHeight(MIN_H) —— 保留可拖拽（不 setFixedSize）")
_dlg_block = USRC[USRC.find("class SettingsDialog"):]
check("self.setFixedSize(" not in _dlg_block,
      "对话框**没有** self.setFixedSize（用户要「可以手动再调整宽度和高度」）")

# ============================================================ ③ 源码：撤销按页自适应
print()
print("=== ③ 源码：撤销按页自适应的收放 ===")
check("def _fit_page(" in USRC, "_fit_page 仍在（留空壳防 AttributeError）")
check("def _compact_to(" in USRC, "_compact_to 仍在（空壳）")
check("def _grow_to(" in USRC, "_grow_to 仍在（空壳）")
# 三个方法体必须是空的（只剩 return）
for name in ("_fit_page", "_compact_to", "_grow_to", "_unwrap_page", "_make_scrollable"):
    m = re.search(r"def %s\([^)]*\):.*?(?=\n    def |\n    @|\nclass )" % name, USRC, re.S)
    body = m.group(0) if m else ""
    # 去掉 docstring 后应只剩 return / pass
    stripped = re.sub(r'""".*?"""', "", body, flags=re.S)
    code = [l.strip() for l in stripped.splitlines()[1:] if l.strip()]
    check(len(code) <= 2, f"{name} 已停用（函数体只剩 return/pass，实际 {code[:3]}）")
check("self._user_resized_h" not in USRC, "_user_resized_h 状态机已移除")
check("self._auto_h" not in USRC, "_auto_h 状态机已移除")
check("self._program_resize" not in USRC, "_program_resize 状态机已移除")
check("self._install_fit_guard" in USRC, "_install_fit_guard 保留（空壳）")

# ============================================================ ④ 源码：内容冻结
print()
print("=== ④ 源码：内部模块冻结（Task #236）===")
check("def _freeze(" in USRC, "新增 _freeze(widget, scroll=True)")
check("def _page_scroll(" in USRC, "_page_scroll 保留（薄包装）")
check("return self._freeze(widget, scroll=True)" in USRC,
      "_page_scroll 转发到 _freeze")
check("page.setFixedWidth(self.CONTENT_W)" in USRC, "页面 setFixedWidth(CONTENT_W)")
check("page.setFixedHeight(need)" in USRC,
      "★ 页面 setFixedHeight(sizeHint) —— 高度也钉死（只钉最小高会被父布局拉高）")
check("Qt.AlignTop | Qt.AlignLeft" in USRC,
      "★ 画布内页面以 顶对齐+左对齐 摆放（左对齐 = 拉宽时右侧留白）")
check("cv.addStretch(1)" in USRC and "右侧留白" in USRC, "画布右侧留白弹簧在")
check('sc.setProperty("lmc_frozen", True)' in USRC, "滚动区带 lmc_frozen 标记（供探针识别）")
check("self._freeze(self._build_scraper())" in USRC,
      "「演员刮削」页改走 _freeze（原来不套滚动）")
check("self._freeze(ui_actorcheck.ActorCheckPage(), scroll=False)" in USRC,
      "「演员检测」页走 _freeze(scroll=False)（不额外套滚动区）")

# ============================================================ ⑤ 真建控件
print()
print("=== ⑤ 真建控件：默认 1320×960 + 切页不改尺寸 + 内容冻结 ===")
try:
    from PySide6.QtCore import QRect as _QRect
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication, QScrollArea

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"):
        if os.path.isfile(fp):
            QFontDatabase.addApplicationFont(fp)
            break
    from main_window import load_style

    load_style(app)

    import ui_settings

    # ★ 假屏幕复刻真机口径（2560×1440 / 可用高 1392）。
    #   离屏平台默认可用区只有 800×800 → 默认尺寸会被小屏兜底缩小，
    #   测不到 1320×960，`DEF_W/DEF_H` 这两条分支就走不到（v1.40.6 的教训）。
    class _FakeScr:
        def availableGeometry(self):
            return _QRect(0, 0, 2560, 1392)

        def geometry(self):
            return _QRect(0, 0, 2560, 1440)

    _fs = _FakeScr()
    _orig_screen = ui_settings.SettingsDialog.screen
    ui_settings.SettingsDialog.screen = lambda self: _fs
    try:
        dlg = ui_settings.SettingsDialog()
        dlg.show()
        for _ in range(8):
            app.processEvents()

        # --- 默认尺寸
        check(dlg.width() == 1320, f"打开默认宽 1320（实际 {dlg.width()}）")
        check(dlg.height() == 960, f"打开默认高 960（实际 {dlg.height()}）")
        check(dlg.minimumHeight() == dlg.MIN_H,
              f"最小高 == MIN_H(560)（实际 {dlg.minimumHeight()}）")
        check(dlg.minimumHeight() != dlg.maximumHeight(),
              f"**可拖拽**（minH={dlg.minimumHeight()} maxH={dlg.maximumHeight()} 应不等）")
        check(ui_settings.SettingsDialog.CONTENT_W == 1170,
              f"CONTENT_W == 1170（实际 {ui_settings.SettingsDialog.CONTENT_W}）")

        # --- 切页不再改窗口尺寸
        keys = ["个性化设置", "手动修改", "AI引擎设置", "演员刮削", "演员检测",
                "图像检测", "数据与日志", "服务管理", "标签优化", "智能推荐",
                "重复检测", "画像概览"]
        base = (dlg.width(), dlg.height())
        moved = []
        for k in keys:
            dlg._show(k)
            for _ in range(4):
                app.processEvents()
            if (dlg.width(), dlg.height()) != base:
                moved.append((k, dlg.width(), dlg.height()))
        check(not moved,
              f"12 页切遍后窗口尺寸恒为 {base}" + (f"（变了：{moved}）" if moved else "（未变）"))

        # --- 每页内容固定宽 1170
        pages = [("个性化设置", "_pg_personal"), ("手动修改", "_pg_manual"),
                 ("画像概览", "_pg_insight"), ("演员刮削", "_pg_scraper"),
                 ("智能推荐", "_pg_smart"), ("标签优化", "_pg_tagopt"),
                 ("服务管理", "_pg_service"), ("AI引擎设置", "_pg_aiengine"),
                 ("重复检测", "_pg_dedupe"), ("演员检测", "_pg_actorcheck"),
                 ("图像检测", "_pg_imagedetect"), ("数据与日志", "_pg_data")]
        print("         [逐页] 页 / 是滚动区 / 页宽 / 页高")
        badw = []
        for key, attr in pages:
            pg = getattr(dlg, attr)
            if isinstance(pg, QScrollArea):
                canvas = pg.widget()
                inner = None
                lay = canvas.layout() if canvas is not None else None
                for i in range(lay.count() if lay else 0):
                    w = lay.itemAt(i).widget()
                    if w is not None and w.width() > 100:
                        inner = w
                        break
                pw = inner.width() if inner is not None else -1
                ph = inner.height() if inner is not None else -1
                is_sc = True
            else:
                pw, ph, is_sc = pg.width(), pg.height(), False
            print("              %-12s scroll=%-5s page=%4d x %4d" % (key, is_sc, pw, ph))
            if is_sc and pw != ui_settings.SettingsDialog.CONTENT_W:
                badw.append((key, pw))
        check(not badw, "每页内容宽恒为 1170" + (f"（异常：{badw}）" if badw else "（全部一致）"))

        # --- 拉宽窗口：页宽不变、画布变宽（内容冻结的核心）
        dlg.resize(1900, 960)
        for _ in range(6):
            app.processEvents()
        dlg._show("演员刮削")
        for _ in range(6):
            app.processEvents()
        sc = dlg._pg_scraper
        canvas = sc.widget()
        lay = canvas.layout()
        inner = None
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if w is not None and w.width() > 100:
                inner = w
                break
        check(inner.width() == 1170,
              f"★ 拉宽到 1900 后页宽仍 1170（实际 {inner.width()}）")
        check(canvas.width() == sc.viewport().width(),
              f"画布宽度跟随视口（{canvas.width()} == {sc.viewport().width()}）")

        # --- 拉高窗口：页高不变
        h_before = inner.height()
        dlg.resize(1900, 1200)
        for _ in range(6):
            app.processEvents()
        dlg._show("演员刮削")
        for _ in range(6):
            app.processEvents()
        lay = canvas.layout()
        inner2 = None
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if w is not None and w.width() > 100:
                inner2 = w
                break
        check(inner2.height() == h_before,
              f"★ 拉高到 1200 后页高不变（{h_before} -> {inner2.height()}）")

        # --- 压窄到比内容窄：内容不被压缩（出现横向滚动条）
        dlg.resize(900, 960)
        for _ in range(6):
            app.processEvents()
        dlg._show("演员刮削")
        for _ in range(6):
            app.processEvents()
        sc = dlg._pg_scraper
        canvas = sc.widget()
        lay = canvas.layout()
        inner3 = None
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if w is not None and w.width() > 100:
                inner3 = w
                break
        check(inner3.width() == 1170,
              f"压窄到 900 后内容仍 1170（不被压缩，实际 {inner3.width()}）")

        dlg.close()
    finally:
        ui_settings.SettingsDialog.screen = _orig_screen
except Exception as e:
    import traceback

    traceback.print_exc()
    bad("真建控件段执行", f"{type(e).__name__}: {e}")

# ============================================================ ⑥ 回归
print()
print("=== ⑥ v1.40.6 / v1.40.5 / v1.40.4 回归 ===")
check("MIN_H = 560" in USRC, "类常量 MIN_H = 560 仍在（拖拽下限）")
check("MAX_H = 960" in USRC, "类常量 MAX_H = 960 仍在（兜底）")
check('QGroupBox("演员刮削")' in USRC, "v1.40.5 合并后的「演员刮削」组框仍在")
check('QGroupBox("演员资料统计")' not in USRC, "旧「演员资料统计」独立组框仍不在")
check("geh.setContentsMargins(9, 4, 9, 4)" in USRC, "v1.40.5 组框内边距收紧仍在")
check("self.src_hint.setSizePolicy(_SP.Minimum, _SP.Preferred)" in USRC,
      "v1.40.5 的 src_hint SizePolicy.Minimum 仍在")
check("sbh.addWidget(self.src_hint, 3)" in USRC, "v1.40.5 的「按钮 + 提示同行」仍在")
check("g0v.setSpacing(4)" in USRC, "v1.40.5 数据源组框 spacing=4 仍在")
check("self.sc_log.setFixedHeight(96)" in USRC, "日志框固定 96px 仍在")
check(re.search(r"v\.addWidget\(g3\)\s*\n\s*self\._refresh_scraper_stats\(\)", USRC)
      is not None, "执行页仍无页尾弹簧（v1.40.4）")
check("def diagnose_host(" in open(os.path.join(SRC, "scraper.py"),
                                   encoding="utf-8").read(),
      "v1.40.4 的 diagnose_host 仍在")
check("from PySide6.QtWidgets import (" in USRC and "QScrollArea" in USRC.split("import config")[0],
      "QScrollArea 已提到模块级 import（v1.40.7 _freeze 需要）")

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
