# -*- coding: utf-8 -*-
"""v1.40.4 离屏冒烟 —— 两条反馈的源码级 + 真建控件级断言。

自证：脚本开头 print 出去重模块的 __file__，确认走的是 E 盘真源。
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
check(ver.VERSION == "v1.40.4", f"VERSION == v1.40.4（实际 {ver.VERSION}）")
check(ver.BUILD == "2610130067", f"BUILD == 2610130067（实际 {ver.BUILD}）")
check(ver.MINOR_ITER == 4, f"MINOR_ITER == 4（实际 {ver.MINOR_ITER}）")
check(ver.BUILD_SEQ == "0067", f"BUILD_SEQ == 0067（实际 {ver.BUILD_SEQ}）")
check("# 0067" in open(os.path.join(SRC, "version.py"), encoding="utf-8").read(),
      "version.py 含 # 0067 说明段")

# ============================================================ ② 反馈 1：硬锁 960
print()
print("=== ② 反馈 1：整窗高度硬锁 960 + 取消执行页弹性 ===")
check("self.setFixedHeight(h)" in USRC, "SettingsDialog 调用了 setFixedHeight(h) 钉死高度")
check("h = min(960, (avail.height() if avail else 1040) - 40)" in USRC,
      "高度公式仍为 min(960, 可用高 - 40)")
# 去掉页尾弹簧：执行组框 addWidget(g3) 之后不能紧跟 addStretch
check("v.addWidget(g3)\n        v.addStretch(1)" not in USRC,
      "执行页**已去掉**页尾 addStretch(1)（g3 后不再跟弹簧）")
check(re.search(r"v\.addWidget\(g3\)\s*\n\s*self\._refresh_scraper_stats\(\)", USRC)
      is not None,
      "g3 之后直接收尾（_refresh_scraper_stats），中间无任何可伸缩项")
check("v.addWidget(g3, 1)" not in USRC, "执行组框**没有**吃 stretch=1（旧错误改法未复现）")
check("g3v.addWidget(self.sc_log, 1)" not in USRC, "日志框**没有**在组内吃 stretch=1")
check("self.sc_log.setFixedHeight(96)" in USRC, "日志框固定 96px")
check("self.sc_log.setMinimumHeight(120)" not in USRC, "日志框**没有**旧的 setMinimumHeight(120)")

# ============================================================ ③ 反馈 2：判因
print()
print("=== ③ 反馈 2：WAF 挑战页精准判因 ===")
check("out[\"waf\"]" in SSRC, "diagnose_host 输出新增 waf 字段")
check("out[\"body_len\"]" in SSRC, "diagnose_host 输出新增 body_len 字段")
check("out[\"http_code\"]" in SSRC, "diagnose_host 输出新增 http_code 字段")
check('out["stage"] = "waf"' in SSRC, "diagnose_host 新增 stage='waf' 档")
check("def _waf_outlet(" in SSRC, "新增 _waf_outlet() 按数据源给出路")
check("aws-waf-token" in SSRC, "_waf_outlet 提到 IMDB 的 aws-waf-token")
check("challenge.js" in SSRC, "_waf_outlet 提到 challenge.js")
check("回 HTTP 200/202 也是挑战页" in SSRC, "_explain WAF 分支说明状态码不可信")
check("_waf_outlet(source)" in SSRC, "_explain WAF 分支改用 _waf_outlet")
# 旧的误导性 verdict 必须消失
check("网络链路正常（TCP + TLS 都通）—— 若仍被拦，才是 cookie / WAF 层的问题。"
      not in SSRC, "旧空话 verdict（把球踢回用户）已删除")
# 关键实现细节：不能用 http_get 的返回值判挑战页
check("is_waf_challenge(body)" in SSRC, "HTTP 层探测用 is_waf_challenge(body) 判挑战页")
check("_opener(proxy, False).open(req" in SSRC,
      "HTTP 层探测自己发请求（绕开 http_get 的 202 抛错）")
check("def _stage_cn(" in USRC, "UI 新增 _stage_cn() 把失败层译中文")
check('"waf": "HTTP 正文（反爬挑战页）"' in USRC, "_stage_cn 含 waf 档中文名")
check('elif diag.get("stage") == "waf":' in USRC, "_on_verified 补 stage=waf 分支")
check('elif diag.get("stage") == "http":' in USRC, "_on_verified 补 stage=http 分支")
check('if stage == "waf":' in USRC, "_on_test_done 按 waf 追加下一步")
check("waf={diag.get('waf')} body_len={diag.get('body_len')}" in USRC,
      "日报日志含 waf=/body_len= 字段")

# ============================================================ ④ 真建控件
print()
print("=== ④ 真建控件：高度与页面结构 ===")
try:
    from PySide6.QtWidgets import (QApplication, QDialog, QGroupBox,
                                   QPlainTextEdit, QStackedWidget)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFontDatabase

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"):
        if os.path.isfile(fp):
            QFontDatabase.addApplicationFont(fp)
            break
    from main_window import load_style
    load_style(app)

    import config as cfg
    import ui_settings

    dlg = ui_settings.SettingsDialog()
    dlg.show()

    mn, mx = dlg.minimumHeight(), dlg.maximumHeight()
    check(mn == mx, f"对话框高度被钉死（minH={mn} maxH={mx} 应相等）")
    check(0 < mn <= 960, f"钉死的高度在 (0,960] 内（实际 {mn}）")
    dlg.resize(dlg.width(), 1200)
    check(dlg.height() == mn, f"尝试 resize 到 1200 高 → 实际仍 {dlg.height()}（锁生效）")

    pg = dlg._pg_scraper
    lay = pg.layout()
    last = lay.itemAt(lay.count() - 1)
    check(last.widget() is not None,
          "执行页末项是控件（不是弹簧）—— 弹性已取消")
    last_name = last.widget().title() if isinstance(last.widget(), QGroupBox) else type(last.widget()).__name__
    check(last_name == "执行", f"执行页末项是「执行」组框（实际 {last_name}）")

    # 执行组框 stretch 必须为 0
    g3 = last.widget()
    idx = lay.count() - 1
    g3_stretch = 0
    for i in range(lay.count()):
        if lay.itemAt(i).widget() is g3:
            # QBoxLayout 无直接 stretch 读取；用「有没有弹簧」+ 子项数验证
            break
    check(all(lay.itemAt(i).spacerItem() is None for i in range(lay.count())),
          "执行页内无 SpacerItem（无弹簧）")

    # 日志框固定 96
    logs = pg.findChildren(QPlainTextEdit)
    check(len(logs) >= 1, "执行页能找到 QPlainTextEdit 日志框")
    if logs:
        lg = logs[0]
        check(lg.minimumHeight() == 96 and lg.maximumHeight() == 96,
              f"日志框 minH==maxH==96（实际 {lg.minimumHeight()}/{lg.maximumHeight()}）")

    # 组框内 stretch：sc_log 所在布局的 stretch 必须为 0
    g3lay = g3.layout()
    check(g3lay is not None, "执行组框有布局")
    if g3lay is not None:
        max_st = 0
        for i in range(g3lay.count()):
            max_st = max(max_st, g3lay.stretch(i))
        check(max_st == 0, f"执行组框内最大 stretch == 0（实际 {max_st}）")

    h_before = g3.sizeHint().height()
    check(h_before <= 340, f"执行组框 sizeHint <= 340（实际 {h_before}）")
    print(f"         [实测] 执行组框 sizeHint={h_before}；窗口 minH=maxH={mn}")

    dlg.close()
except Exception as e:
    import traceback
    traceback.print_exc()
    bad("真建控件段执行", f"{type(e).__name__}: {e}")

# ============================================================ ⑤ 回归
print()
print("=== ⑤ v1.40.2 / v1.40.3 回归 ===")
check("def diagnose_host(" in SSRC, "diagnose_host 仍存在（分层诊断未删）")
check("self._restore_open_btn()" in USRC, "v1.40.3 的 _restore_open_btn 仍在")
check("_focus_builtin_window" in USRC, "v1.40.3 的 _focus_builtin_window 仍在")
check("on_top=True" in open(os.path.join(SRC, "cf_browser.py"), encoding="utf-8").read(),
      "cf_browser 的 on_top=True 仍在")
check("_manual_cookie_header" in SSRC, "curl_cffi 手工 cookie 头仍在")

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
