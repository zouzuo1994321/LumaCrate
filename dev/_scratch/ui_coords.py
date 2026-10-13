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


def unwrap(pg):
    """★ v1.40.7：`_freeze()` 把每页包成「滚动区 → 画布 → 页面」三层，
    所以这里的解包要**多剥一层**（滚动区 → 画布 → 页面）。

    历史（v1.40.4）：`_fit_page()` 在内容高于可视区时会把页面就地包进 QScrollArea，
    于是 `dlg._pg_*` 指向的可能是滚动区而不是页面。凡「取页面上的控件」的地方
    都先过这个函数解包，否则会拿到 AttributeError。

    v1.40.7 起页面结构恒定（不再有运行期包装），剥两层即可命中真页面：
    判据是「这一层是 QScrollArea」→ 取 widget（画布）→ 再看画布里固定宽的那个孩子。
    """
    from PySide6.QtWidgets import QScrollArea, QWidget
    seen = 0
    while isinstance(pg, QScrollArea) and seen < 4:
        inner = pg.widget()
        if inner is None:
            break
        pg = inner
        seen += 1
    # 现在 pg 是画布（或裸页）—— 若画布里只有「一个固定宽的孩子」，那一层才是真页面
    if isinstance(pg, QWidget) and pg.layout() is not None:
        lay = pg.layout()
        kids = []
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if w is not None and w.width() > 100 and w.layout() is not None:
                kids.append(w)
        if len(kids) == 1:
            pg = kids[0]
    return pg


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
# ★ v1.40.7：默认尺寸固定 1320×960（DEF_W/DEF_H），不再看屏幕宽高
#   （离屏平台 primaryScreen 只有 800×800，用它算会得到不该有的收敛值）。
dw, dh = 1320, 960
res["dialog_size"] = [dw, dh]
res["dialog_size_note"] = ("v1.40.7：固定默认 1320x960（DEF_W/DEF_H）；"
                           "offscreen 屏幕太小不能直接代入真机算法")

# ★ v1.40.7：把 screen() 换成假屏幕（复刻真机 2560×1392），
#   否则 `max(760, avail.width()-40)` 会被离屏的 800 兜底缩小，量出来的
#   对话框尺寸与真机不符 → 坐标全错。
from PySide6.QtCore import QRect as _QRect


class _FakeScr:
    def availableGeometry(self):
        return _QRect(0, 0, 2560, 1392)

    def geometry(self):
        return _QRect(0, 0, 2560, 1440)


import ui_settings as _uis
_uis.SettingsDialog.screen = lambda self: _FakeScr()

dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(dw, dh)
dlg.show()
app.processEvents()

res["dialog_nav"] = {}
for k, b in dlg.sub_btns.items():
    res["dialog_nav"][k] = center(b, dlg)

# v1.39.0（需求 3）：导航项旁边的转圈位置（ring 隐藏时也在布局里占位失败，
# 所以先 set_state(True) 让它显示出来再量，量完复位）。
# live_verify 用它从工具窗截图里裁出转圈区域，验证「进行中任务旁有转圈」。
res["dialog_nav_rings"] = {}
for k, ring in getattr(dlg, "nav_rings", {}).items():
    ring.set_state(True, 0, "coords")
    app.processEvents()
    _p = ring.mapTo(dlg, QPoint(0, 0))
    res["dialog_nav_rings"][k] = [_p.x(), _p.y(), ring.width(), ring.height()]
    ring.set_state(False)
    app.processEvents()

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

# v1.39.0（需求 1）：数据源行的「测试」按钮（行序 = SOURCE 顺序，第 0 个是 minnano）。
# 真机验收点它 → 截图应能看到 403 的人话提示（Cloudflare 指纹校验）或真的可用。
_tests = [b for b in dlg.findChildren(QPushButton) if b.text() == "测试"]
_tests.sort(key=lambda b: b.mapTo(dlg, QPoint(0, 0)).y())
res["scraper_test_btns"] = [center(b, dlg) for b in _tests]
res["scraper_test_note"] = "行序即 SOURCE 顺序：[0]=minnano(www.minnano-av.com)、[1]=IMDB"

# v1.40.0（反馈 4）：「Cloudflare 验证…」按钮 —— 真机验收点它应弹出三步走对话框。
# 它和数据源按钮行是同一排（`测试全部数据源` 右边），所以必须**先确保当前页是
# 演员刮削**再量（非当前页的控件几何是陈旧的，坐标会乱）。
_cf = [b for b in dlg.findChildren(QPushButton) if "Cloudflare" in b.text()]
res["scraper_cf_btn"] = center(_cf[0], dlg) if _cf else None
res["scraper_cf_btn_text"] = _cf[0].text() if _cf else None

# v1.40.1（反馈 3）：站点验证对话框**内部**的按钮坐标 —— 真机验收要实测
# 「打开内置浏览器」真的能拉起子进程。对话框是常驻实例（`dlg._cf_dlg`），
# 打开它、按客户区量出按钮中心（相对对话框自身）。
try:
    dlg._open_cloudflare()
    app.processEvents()
    _cfd = getattr(dlg, "_cf_dlg", None)
    if _cfd is not None:
        _cfd.resize(_cfd.sizeHint())
        _cfd.show()
        app.processEvents()
        res["cf_dlg_open_builtin"] = center(_cfd.btn_open, _cfd)
        res["cf_dlg_open_builtin_text"] = _cfd.btn_open.text()
        # v1.40.2（反馈 2）：新增的**独立**「读取 Cookie」按钮坐标
        res["cf_dlg_read_btn"] = center(_cfd.btn_read, _cfd)
        res["cf_dlg_read_btn_text"] = _cfd.btn_read.text()
        res["cf_dlg_check_wv"] = center(_cfd.btn_webview, _cfd)
        res["cf_dlg_save"] = center(_cfd.btn_save, _cfd)
        res["cf_dlg_clear"] = center(_cfd.btn_clear, _cfd)
        res["cf_dlg_close"] = center(_cfd.btn_close, _cfd)
        res["cf_dlg_adv"] = center(_cfd.btn_adv, _cfd)
        res["cf_dlg_client"] = [_cfd.width(), _cfd.height()]
        res["cf_dlg_adv_visible"] = bool(_cfd.adv.isVisibleTo(_cfd))
        _cfd.close()
        app.processEvents()
except Exception as _e:
    print(f"[警告] CloudflareDialog 坐标测量失败：{type(_e).__name__}: {_e}")

# v1.40.0（反馈 3）：代理显式开关 + 输入框（真机验收要看它关着时输入框置灰）。
_sp = getattr(dlg, "sc_proxy", None)
_so = getattr(dlg, "sc_proxy_on", None)
res["scraper_proxy_edit"] = center(_sp, dlg) if _sp is not None else None
res["scraper_proxy_toggle"] = center(_so, dlg) if _so is not None else None
res["scraper_proxy_note"] = ("v1.40.0 反馈 3：代理由 sc_proxy_on 显式开关决定；"
                             "关掉时输入框置灰、且请求纯直连（不套系统代理）")

# v1.40.0（反馈 1/2）：三个模块的标题与日志区位置（供截图裁剪与肉眼核对）。
res["scraper_modules"] = [g.title() for g in dlg.findChildren(QGroupBox)]
_sl = getattr(dlg, "sc_log", None)
res["scraper_log_rect"] = ([_sl.x(), _sl.y(), _sl.width(), _sl.height()]
                           if _sl is not None else None)

# v1.38.0（需求 2）：演员检测页的多选批量工具栏。
# 只取坐标，**真机验收不得点「批量确认关联」** —— 它会对真实索引执行
# db.merge_people（删除演员记录、搬移作品关联），是不可逆的写操作。
# 验收只做到：进页 → 开始检测（只读）→ 全选（只改复选框状态）→ 截图。
dlg._show("演员检测")
app.processEvents()
_pg = unwrap(dlg._pg_actorcheck)
for _k, _attr in (("actorcheck_run_btn", "run_btn"),
                  ("actorcheck_sel_all", "sel_all_btn"),
                  ("actorcheck_sel_none", "sel_none_btn"),
                  ("actorcheck_batch_merge", "batch_merge_btn")):
    _w = getattr(_pg, _attr, None)
    res[_k] = center(_w, dlg) if _w is not None else None
    if _w is None:
        print(f"[警告] ActorCheckPage.{_attr} 不存在，演员检测页工具栏可能没建出来")
res["actorcheck_tree_header"] = [_pg.tree.headerItem().text(i)
                                 for i in range(_pg.tree.columnCount())]

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
