# -*- coding: utf-8 -*-
"""v1.32.0 界面坐标探针（离屏，1000x900 与真机同尺寸）。

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/_scratch/ui_coords_v1320.py', run_name='__main__')"

产出：合并进 `C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json`：
  - `dialog_nav`：**整段替换**（从 `dlg.sub_btns` 推导，插页/改名自动跟）
  - `v1320.common`：三检测页共有的 [普通算法单选, AI 算法单选, 极速模式勾选, 开始检测, 停止]
  - `v1320.actor_run` / `v1320.img_run` / `v1320.dd_run`：各页开始按钮（若类名不同）
  - `v1320.appearance`：外观页的 [语言下拉, 下拉第 1 项, 下拉第 2 项, 关于入口]
"""
import json
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="lmc_coords1320_")
INDEX = os.path.join(TMP, "index_data")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

_c = db.get_conn()
try:
    _c.execute("INSERT INTO media(kind,title,sort_title,year,file_path,library) "
               "VALUES(?,?,?,?,?,?)",
               ("movie", "验收用影片", "验收用影片", 2024, "X:/__probe__/VERIFY-001.mp4", "验收库"))
    _c.commit()
finally:
    _c.close()

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication, QPushButton, QRadioButton, QCheckBox,
                               QComboBox, QLabel)

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import backdrop

backdrop.auto_apply = lambda w, *a, **k: None

import main_window as mw

mw.load_style(app)

from ui_settings import SettingsDialog


def center(widget, ref):
    p = widget.mapTo(ref, QPoint(widget.width() // 2, widget.height() // 2))
    return [int(p.x()), int(p.y())]


dlg = SettingsDialog()
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1000, 900)
dlg.show()
app.processEvents()

res = {}

# ---- 1. 导航坐标：整段替换 ----
nav = {}
for key, btn in dlg.sub_btns.items():
    nav[key] = center(btn, dlg)
res["dialog_nav"] = nav
res["dialog_nav_keys"] = list(nav)
res["dialog_size"] = [dlg.width(), dlg.height()]
print("导航 %d 页：" % len(nav))
for k in nav:
    print("   %-10s %s" % (k, nav[k]))

try:
    secs = [l for l in dlg.findChildren(QLabel) if l.objectName() == "Section"]
    res["dialog_sections"] = {l.text(): center(l, dlg) for l in secs[:4]}
except Exception as e:
    print("分组标题坐标失败：%s" % e)

# ---- 2. 三检测页的双算法控件 ----
v1320 = {}


def probe_detect_page(page_key, tag):
    """抓一页检测页的 [普通算法](https://) 控件坐标。"""
    dlg._show(page_key)
    app.processEvents()
    pg = dlg.stack.currentWidget()
    # 有些页被 _page_scroll 包了一层 → 真页在 QScrollArea 里
    inner = pg
    try:
        from PySide6.QtWidgets import QScrollArea
        if isinstance(pg, QScrollArea) and pg.widget():
            inner = pg.widget()
    except Exception:
        pass
    out = {}
    for r in inner.findChildren(QRadioButton):
        txt = r.text()
        if "普通算法" in txt:
            out["rb_normal"] = center(r, dlg)
        elif "AI 算法" in txt:
            out["rb_ai"] = center(r, dlg)
    for c in inner.findChildren(QCheckBox):
        if "极速" in c.text():
            out["fast_chk"] = center(c, dlg)
    # ⚠ 按「属性名」取，不要按文案模糊匹配 —— 页里还有个「检测本地 AI 引擎」按钮，
    #   模糊匹配会把它当成开始按钮（第一轮就踩了）。属性名：dedupe=dd_run，其余=run_btn。
    # ⚠ 只从**页内**取，不要回落到 dlg —— 重复检测的 dd_run 挂在 dlg 上，
    #   回落会让三页都拿到同一个按钮（第二轮踩了）。
    for attr in ("dd_run", "run_btn"):
        w = getattr(inner, attr, None)
        if w is not None:
            out["run_btn"] = center(w, dlg)
            out["run_btn_text"] = w.text()
            out["run_attr"] = attr
            break
    for b in inner.findChildren(QPushButton):
        if "停止" in b.text():
            out.setdefault("stop_btn", center(b, dlg))
    v1320[tag] = out
    print("%s（%s）：%s" % (page_key, tag, out))
    return out


_dd = probe_detect_page("重复检测", "dedupe")
# 重复检测页的 dd_run 挂在 dlg 上（页体不是独立 QWidget），补一次
_w = getattr(dlg, "dd_run", None)
if _w is not None:
    _dd["run_btn"] = center(_w, dlg)
    _dd["run_btn_text"] = _w.text()
    _dd["run_attr"] = "dd_run"
    print("重复检测（dd_run@dlg）：%s" % _dd)
probe_detect_page("图像检测", "image")
probe_detect_page("演员检测", "actor")

# ---- 3. 外观页：语言下拉 / 关于入口 ----
dlg._show("个性化设置")
app.processEvents()
pg = dlg.stack.currentWidget()
try:
    from PySide6.QtWidgets import QScrollArea
    if isinstance(pg, QScrollArea) and pg.widget():
        pg = pg.widget()
except Exception:
    pass

ap = {}
cb = getattr(dlg, "ap_lang", None)
if cb is None:
    for c in pg.findChildren(QComboBox):
        if c.count() >= 19:
            cb = c
            break
if cb is not None:
    ap["lang_combo"] = center(cb, dlg)
    rect = cb.rect()
    # 下拉展开后每一项的大致高度（QComboBox 默认 view item 约 22-26px）
    _rowh = 24
    _x = center(cb, dlg)[0]
    _y0 = center(cb, dlg)[1] + rect.height() // 2 + _rowh // 2
    ap["lang_item1"] = [_x, int(_y0)]
    ap["lang_item2"] = [_x, int(_y0 + _rowh)]
else:
    print("!! 没找到语言下拉")

# 外观开关（沿用 v1.30.0 那组坐标的定位方式：给「通用」组里的复选框）
for c in pg.findChildren(QCheckBox):
    if c.text() and ("实时状态" in c.text() or "数据统计" in c.text()):
        ap.setdefault("toggles", []).append(center(c, dlg))

v1320["appearance"] = ap

# 「关于」入口：主窗侧栏品牌区（REPO_URL 是外链，不是关于）—— 改找主窗菜单/按钮
win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
v1320["main_settings_btn"] = None
for b in win.findChildren(QPushButton):
    if b.text() in ("工具", "设置"):
        v1320["main_settings_btn"] = center(b, win)
        break
if v1320["main_settings_btn"]:
    res["main_settings_btn"] = v1320["main_settings_btn"]
res["main_size"] = [win.width(), win.height()]

# 关于窗：直接造一个，量「确定」按钮（便于关闭）
try:
    ad = mw.AboutDialog()
    ad.setAttribute(Qt.WA_DontShowOnScreen, True)
    ad.show()
    app.processEvents()
    v1320["about"] = {"size": [ad.width(), ad.height()]}
    for b in ad.findChildren(QPushButton):
        v1320["about"]["ok_btn"] = center(b, ad)
        v1320["about"]["ok_text"] = b.text()
        break
    print("关于窗：%s" % v1320["about"])
    ad.close()
except Exception as e:
    print("关于窗坐标失败：%s" % e)

res["v1320"] = v1320
print(json.dumps({k: v for k, v in res.items() if k != "dialog_nav"},
                 ensure_ascii=False, indent=1))

dst = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"
try:
    with open(dst, encoding="utf-8") as f:
        old = json.load(f)
except Exception:
    old = {}
old["dialog_nav"] = res.pop("dialog_nav")     # 整段替换：自动跟布局
old["v1320"] = res.pop("v1320")
old.update(res)
with open(dst, "w", encoding="utf-8") as f:
    json.dump(old, f, ensure_ascii=False, indent=1)
print("\n已合并到 %s" % dst)
