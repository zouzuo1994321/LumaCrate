# -*- coding: utf-8 -*-
"""离屏算出真机上要点击的坐标，输出 JSON。

为什么单独一个脚本：live_verify.py 里已经有一个**真实平台**的 QApplication，
在里面再建窗口会真的弹出一个窗口（还会和待验收的 exe 抢焦点）。
所以坐标计算放到独立进程里用 offscreen 跑，live_verify 只读结果。

布局与真机一致的前提：同尺寸（1920×1080 / 对话框 1000×900）＋同字体。
"""
import json
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QGroupBox, QLabel
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint

OUT = "C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_coords_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow
from ui_settings import SettingsDialog, ToggleSwitch


def center(widget, ref):
    p = widget.mapTo(ref, QPoint(widget.width() // 2, widget.height() // 2))
    return [int(p.x()), int(p.y())]


res = {}

# ---------------- 主窗口：顶栏「工具」按钮（v1.24.0 由「设置」改名）
win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
for b in win.findChildren(QPushButton):
    if b.text() in ("工具", "设置"):
        res["main_settings_btn"] = center(b, win)
        res["main_settings_btn_text"] = b.text()
        break
res["main_size"] = [win.width(), win.height()]

# ---------------- 设置对话框（真机尺寸同 SettingsDialog.__init__ 的算法）
# 注意：offscreen 平台的 primaryScreen 只有 800×800，不能用它算 —— 真机是 1920×1080
# （可用高 ~1040），代入同一个公式得到 min(1000,·)=1000 × min(900,·)=900。
dw, dh = 1000, min(900, 1040 - 40)
res["dialog_size"] = [dw, dh]
res["dialog_size_note"] = "按 1920x1080 真机代入 SettingsDialog 的公式；offscreen 屏幕太小不能直接用"

dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(dw, dh)
dlg.show()
app.processEvents()

res["dialog_nav"] = {}
for k, b in dlg.sub_btns.items():
    res["dialog_nav"][k] = center(b, dlg)

# 内容卡片分组的位置（用于截图裁剪参考）
for g in dlg.findChildren(QGroupBox):
    if g.title() == "内容卡片":
        res["cards_group"] = [g.x(), g.y(), g.width(), g.height()]
    if g.title() == "导航菜单":
        res["nav_group"] = [g.x(), g.y(), g.width(), g.height()]

# 开关：只取「导航菜单」分组里的（在首屏可见、不用滚动）。
# 不能在 dlg 上 findChildren——非当前页的控件几何是陈旧的，坐标会乱。
dlg._show("个性化设置")
app.processEvents()
nav_gb = None
for g in dlg.findChildren(QGroupBox):
    if g.title() == "导航菜单":
        nav_gb = g
res["toggles_personal"] = ([center(t, dlg) for t in nav_gb.findChildren(ToggleSwitch)]
                           if nav_gb is not None else [])
res["toggles_note"] = "导航菜单分组的开关，首个在首屏可见；不点击（会改动用户 settings.json）"

# 演员刮削页：修复按钮 + 数据源箭头
dlg._show("演员刮削")
app.processEvents()
rep = [b for b in dlg.findChildren(QPushButton) if "修复历史资料" in b.text()]
res["repair_btn"] = center(rep[0], dlg) if rep else None
res["repair_btn_text"] = rep[0].text() if rep else None

# v1.24.0：新增两页也要真机点一下 —— 它们分别是 insight / recommend 两个
# hidden-import 模块的唯一入口，漏打包就会在这里炸。
dlg._show("画像概览")
app.processEvents()
_r = [b for b in dlg.findChildren(QPushButton) if "分析" in b.text()]
res["insight_run_btn"] = center(_r[0], dlg) if _r else None
# v1.24.1（反馈 4）：统计范围下拉也要能点到（真机验收靠 LMC_CONFIG 预置，这里只留坐标）
res["insight_scope_combo"] = center(dlg.ins_lib, dlg) if getattr(dlg, "ins_lib", None) else None

# v1.24.1（反馈 2）：智能推荐页的「检测本地 AI 引擎」按钮 —— 必须真点一次，
# 确认打包版里探测线程跑得通、并且点下去有可见反馈（截图会拍到带时间戳的结论）。
# 直接取属性而不是按文案匹配：文案里含空格，跨文件复制时容易被悄悄改动而匹配不上。
dlg._show("智能推荐")
app.processEvents()
_ai = getattr(dlg, "ai_test", None)
res["ai_test_btn"] = center(_ai, dlg) if _ai is not None else None
res["ai_test_btn_text"] = _ai.text() if _ai is not None else None
if _ai is None:
    print("[警告] dlg.ai_test 不存在，智能推荐页可能没建出来")

dlg._show("重复检测")
app.processEvents()
_d = [b for b in dlg.findChildren(QPushButton) if b.text() == "开始检测"]
res["dedupe_start_btn"] = center(_d[0], dlg) if _d else None
res["dedupe_excl_ck"] = center(dlg.dd_excl, dlg) if dlg.dd_excl else None
res["dedupe_verify_ck"] = center(dlg.dd_verify, dlg) if dlg.dd_verify else None

# v1.25.0（反馈 4）：新页「标签优化」是 tagopt 模块的唯一入口 —— 漏打包 only 在这里炸。
# 页面上的按钮全部按属性取（不按文案匹配），文案改一个字就不会悄悄失配。
dlg._show("标签优化")
app.processEvents()
for _k, _attr in (("tagopt_scan_btn", "btn_to_scan"),
                  ("tagopt_run_btn", "btn_to_run"),
                  ("tagopt_clear_btn", "btn_to_clear"),
                  ("tagopt_path_edit", "to_path"),
                  ("tagopt_lib_combo", "to_lib"),
                  ("tagopt_ai_rb", "rb_to_ai"),
                  ("tagopt_normal_rb", "rb_to_normal")):
    _w = getattr(dlg, _attr, None)
    res[_k] = center(_w, dlg) if _w is not None else None
    if _w is None:
        print(f"[警告] dlg.{_attr} 不存在，标签优化页可能没建出来")

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
