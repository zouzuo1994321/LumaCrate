# -*- coding: utf-8 -*-
"""v1.31.0 界面坐标探针（离屏，1000x900 与真机同尺寸）。

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/_scratch/ui_coords_v1310.py', run_name='__main__')"

产出：写回 `C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json`：
  - `dialog_nav`：**全部**导航页的 [x,y] —— 这一版改成**直接从 `dlg.sub_btns` 推导**，
    不再手量。原因是 v1.31.0 给导航插了 4 个分组小标题，后面所有页的 y 整体下移，
    手量的坐标静默失配（点错页 / 点空），而 `sub_btns` 的几何是布局算出来的，插页自动跟。
  - `main_settings_btn`：主窗「工具」按钮。
  - `v1310`：演员检测页里几个要点的控件（开始检测 / 结果树 / 检索框 / 检索按钮 / 列表）。
"""
import json
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="lmc_coords1310_")
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

# 造一条可检索的演员，让演员检测页的编辑表单首行有东西
_c = db.get_conn()
try:
    _c.execute("INSERT INTO media(kind,title,sort_title,year,file_path,library) "
               "VALUES(?,?,?,?,?,?)",
               ("movie", "验收用影片", "验收用影片", 2024, "X:/__probe__/VERIFY-001.mp4", "验收库"))
    _c.commit()
finally:
    _c.close()
_p = db.upsert_person("验收用演员", role_type="Actor")
db.set_person_fields(_p, name="验收用演员", romaji="Verify Actor", status="现役",
                     meta='{"身高": "160cm", "尺寸": "T160 / B88( Fカップ ) / W58 / H88 / S"}')

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import backdrop

backdrop.auto_apply = lambda w, *a, **k: None

# ⚠ 必须加载 QSS 再建控件！不带样式时 `QPushButton` 没有 `padding:7px 14px`，
#   导航行高只有 29px，而真机（带 QSS）是 36px —— 坐标会整体偏上、点错页。
#   （第一轮探针漏了这行，真机点「演员检测」落到了「标签优化」上。）
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

# ---- 1. 导航坐标：从控件几何推导（不再手量，插页自动跟） ----
nav = {}
for key, btn in dlg.sub_btns.items():
    nav[key] = center(btn, dlg)
res["dialog_nav"] = nav
res["dialog_nav_keys"] = list(nav)
res["dialog_size"] = [dlg.width(), dlg.height()]
print("导航 %d 页：" % len(nav))
for k in nav:
    print("   %-10s %s" % (k, nav[k]))

# 分组小标题的位置（真机验收里核对「标题在按钮之前」）
try:
    from PySide6.QtWidgets import QLabel
    secs = [l for l in dlg.findChildren(QLabel) if l.objectName() == "Section"]
    res["dialog_sections"] = {l.text(): center(l, dlg) for l in secs[:4]}
except Exception as e:
    print("分组标题坐标失败：%s" % e)

# ---- 2. 演员检测页里的关键控件 ----
dlg._show("演员检测")
app.processEvents()
pg = dlg.stack.currentWidget()
res["v1310"] = {
    "run_btn": center(pg.run_btn, dlg),
    "stop_btn": center(pg.stop_btn, dlg),
    "rb_normal": center(pg.rb_normal, dlg),
    "rb_ai": center(pg.rb_ai, dlg),
    "tree": center(pg.tree, dlg),
    "kw": center(pg.kw, dlg),
}
for b in pg.findChildren(QPushButton):
    if b.text() == "检索":
        res["v1310"]["search_btn"] = center(b, dlg)
res["v1310"]["first_cluster"] = None
print("演员检测页：run_btn=%s tree=%s kw=%s" %
      (res["v1310"]["run_btn"], res["v1310"]["tree"], res["v1310"]["kw"]))

# ---- 3. 主窗「工具」按钮 ----
win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
for b in win.findChildren(QPushButton):
    if b.text() in ("工具", "设置"):
        res["main_settings_btn"] = center(b, win)
        break
res["main_size"] = [win.width(), win.height()]

print(json.dumps({k: v for k, v in res.items() if k != "dialog_nav"},
                 ensure_ascii=False, indent=1))

# ---- 合并进真机验收用的坐标文件 ----
dst = r"C:/Users/zouzu/AppData/Local/Temp/lmc_ui_coords.json"
try:
    with open(dst, encoding="utf-8") as f:
        old = json.load(f)
except Exception:
    old = {}
old["dialog_nav"] = res.pop("dialog_nav")     # 整段替换：这是本轮「自动跟布局」的关键
old.setdefault("v1310", {}).update(res.pop("v1310"))
old.update(res)
with open(dst, "w", encoding="utf-8") as f:
    json.dump(old, f, ensure_ascii=False, indent=1)
print("\n已合并到 %s" % dst)
