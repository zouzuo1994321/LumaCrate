# -*- coding: utf-8 -*-
"""v1.35.1 离屏冒烟（构建期）。

① 智能推荐页「引导向量」芯片错位修复：
   - 芯片已从工具行搬出 → **工具行的最小宽度不随芯片数量变化**（核心断言）；
   - 芯片落在工具栏下方的独占行，FlowLayout 自动换行；
   - 命中数 > GUIDE_CHIP_LIMIT 时默认折叠，`_toggle_guides_expand()` 可展开全部；
   - 行序为 工具栏 < 引导行 < 网格；工具行子控件全部落在行内（无被裁）。
② 品牌图标切换到 logo-4.png（源码引用 + 资源存在 + 窗口图标可加载）。

使用临时数据库，绝不读写真实索引。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1351_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor, QLinearGradient, QFontDatabase
from PySide6.QtCore import QPoint
from PIL import Image

app = QApplication(sys.argv)

import database as db
import scanner as scanner_mod
import applog
import version as ver
import recommend as rec_mod
from main_window import MainWindow, load_style

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

# 量几何前必须先注册中文字体 + 套 QSS，否则 sizeHint 虚高（见 skill 第十节）
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

FAIL = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("   -> " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(name)


# ---------------- 造样本库 ----------------
def _poster(path, c1, c2, w=300, h=450):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(c1))
    g.setColorAt(1, QColor(c2))
    p.fillRect(0, 0, w, h, g)
    p.end()
    img.save(path)


PALETTE = [("#2b3a55", "#7a4a86"), ("#5a4326", "#c08a3e"), ("#1b2a4a", "#3d6a9e"),
           ("#26332b", "#5f7d63"), ("#4a2530", "#a6506a"), ("#31304a", "#6a6f9e")]

root = os.path.join(TMP, "lib")
for i in range(12):
    d = os.path.join(root, f"MV-{i:03d}")
    os.makedirs(d, exist_ok=True)
    c1, c2 = PALETTE[i % len(PALETTE)]
    _poster(os.path.join(d, "poster.jpg"), c1, c2)
    with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0"?>\n<movie>'
            f"<title>样本影片 {i}</title><year>{2010 + i}</year><runtime>120</runtime>"
            "<country>日本</country><genre>剧情,标签%d</genre>" % (i % 7) +
            "<plot>预览用简介。</plot><thumb>poster.jpg</thumb>"
            f"<uniqueid type='tmdb'>{i}</uniqueid></movie>")
    with open(os.path.join(d, "MV-%03d.mp4" % i), "w") as f:
        f.write("x" * 1024)

db.init_db()
scanner_mod.scan_library(root)
rows = db.movies()
print(f"[样本] 入库 {len(rows)} 部")
check("样本库已建好", len(rows) >= 8, len(rows))

# ---------------- 建主窗 ----------------
logo_path = os.path.join(ROOT, "logo-4.png")
load_style(app)
win = MainWindow(logo_path=logo_path)
win.resize(1080, 720)          # 用户截图那个宽度，能真正压到工具行
win.show()
app.processEvents()


def _fake_res():
    return {
        "picks": [], "algo": "normal", "engine": "", "pool": 47064,
        "meta": {"favorites": 867, "liked": 22617, "fav_people_n": 323},
        "profile_top": [("t标签%d" % i, 1.0) for i in range(6)],
    }


def _set_guides(n):
    win._smart_guides = [
        {"token": f"tag:item{i}", "dim": "tag", "key": f"模糊命中标签{i}", "weight": 2.0}
        for i in range(n)]


def _build(guides_n):
    win._smart_res = _fake_res()
    win._smart_picks = list(rows[:9])   # 已是完整 media 行（带 poster）
    _set_guides(guides_n)
    win.go(win._smart_wall)
    for _ in range(4):
        app.processEvents()
    return win.stack.currentWidget()


def _parts():
    tb = win.guide_edit.parentWidget()
    w = tb.parentWidget()
    return tb, w


def _dump_toolbar(tb, tag=""):
    """打印工具行每个子控件的最小宽度 —— 定位「谁不肯收缩」。"""
    lay = tb.layout()
    print(f"[工具栏明细{(' ' + tag) if tag else ''}] tb.min={tb.minimumSizeHint().width()}")
    for i in range(lay.count()):
        it = lay.itemAt(i)
        cw = it.widget()
        if cw is None:
            continue
        print(f"    - {type(cw).__name__:<12} obj={cw.objectName():<12} "
              f"min={cw.minimumSizeHint().width():>5} hint={cw.sizeHint().width():>5} "
              f"policy={cw.sizePolicy().horizontalPolicy().name}")


# ---------------- ① 无引导：记基线 ----------------
scroll0 = _build(0)
tb0, w0 = _parts()
base_min = tb0.minimumSizeHint().width()
print(f"[基线] 无引导 工具行 minimumSizeHint().width() = {base_min}")

# ---------------- ② 40 条模糊命中：核心断言 ----------------
scroll = _build(40)
tb, w = _parts()
vw = scroll.viewport().width()
many_min = tb.minimumSizeHint().width()
print(f"[对照] 40 条引导 工具行 minimumSizeHint().width() = {many_min}  (可视区 {vw})")
_dump_toolbar(tb, "40条引导")

check("工具行最小宽度不随芯片数量变化（芯片已搬出）",
      abs(many_min - base_min) <= 2, f"{base_min} -> {many_min}")
check("工具行不溢出可视区", many_min <= vw, f"{many_min} <= {vw}")

# 芯片在独占行里、不在工具行里
check("引导芯片不在工具行中", win.guide_chips.parentWidget() is not tb)
check("状态文案不在工具行中", win.guide_state.parentWidget() is not tb)
check("引导行 = 芯片 + 状态文案",
      win.guide_row is not None and win.guide_chips.parentWidget() is win.guide_row
      and win.guide_state.parentWidget() is win.guide_row)

# 行序：工具栏 < 引导行 < 网格
v = w.layout()
i_tb = v.indexOf(tb)
i_gr = v.indexOf(win.guide_row)
grid = getattr(w, "lazy_grid", None)
i_grid = v.indexOf(grid) if grid is not None else -1
check("行序 工具栏 < 引导行 < 网格", 0 <= i_tb < i_gr < i_grid, (i_tb, i_gr, i_grid))

# 工具行内所有子控件都在行内（没有一个被挤出右边界）
vtb = tb.layout()
bad = []
for i in range(vtb.count()):
    cw = vtb.itemAt(i).widget()
    if cw is None or not cw.isVisible():
        continue            # 隐藏控件不参与布局，几何是陈旧值 —— 跳过（如「加载更多」已全载入）
    x = cw.mapTo(tb, QPoint(0, 0)).x()
    if x < -1 or x + cw.width() > tb.width() + 1:
        bad.append((cw.objectName() or type(cw).__name__, x, cw.width(), tb.width()))
check("工具行子控件全部落在行内（无被裁）", not bad, bad)

# 芯片自动换行 + 默认折叠
limit = MainWindow.GUIDE_CHIP_LIMIT
disp = win.guide_chips_l.count()
check("默认折叠为 GUIDE_CHIP_LIMIT+1 项（含展开按钮）", disp == limit + 1, f"disp={disp} limit={limit}")
ch = win.guide_chips.height()
check("芯片自动换行（高度 > 单行）", ch > 30, f"guide_chips.height()={ch}")

# 展开全部
win._toggle_guides_expand()
for _ in range(3):
    app.processEvents()
exp = win.guide_chips_l.count()
check("展开后显示全部芯片 + 收起按钮", exp == 40 + 1, f"count={exp}")

# 工具行在展开后依然不溢出
check("展开全部后工具行仍不溢出", tb.minimumSizeHint().width() <= vw,
      f"{tb.minimumSizeHint().width()} <= {vw}")

# ---------------- 出图 ----------------
def shot(widget, name, bg=(13, 11, 10)):
    out = os.path.join(ROOT, "dev", "screenshots", name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = os.path.join(TMP, name)
    widget.grab().save(tmp)
    im = Image.open(tmp).convert("RGBA")
    base = Image.new("RGBA", im.size, bg + (255,))
    Image.alpha_composite(base, im).convert("RGB").save(out)
    print("saved", out)


shot(scroll, "v1351_smart_fuzzy.png")
win._toggle_guides_expand()      # 展开态也留一张（1080 窄窗）
for _ in range(3):
    app.processEvents()
shot(scroll, "v1351_smart_fuzzy_narrow_expanded.png")
win._toggle_guides_expand()

# ---------------- 1920（设计宽度）：无横向溢出 + 正式出图 ----------------
# LazyGrid 媒体墙固定 8 列（8*158+7*12 = 1348px），1080 窄窗必然横向滚动 ——
# 那是既有设计宽度问题，与本次工具栏错位无关。设计宽度 1920 下应当完全不溢出。
win.resize(1920, 1080)
scroll_w = _build(40)
for _ in range(4):
    app.processEvents()
hmax = scroll_w.horizontalScrollBar().maximum()
vw_w = scroll_w.viewport().width()
check("1920 设计宽度下无横向溢出", hmax == 0, f"hmax={hmax} viewport={vw_w}")
tbw, _ww = _parts()
check("工具行宽度不超可视区", tbw.width() <= vw_w, f"{tbw.width()} <= {vw_w}")
for i in range(tbw.layout().count()):
    cw = tbw.layout().itemAt(i).widget()
    if cw is None or not cw.isVisible():
        continue
    _x = cw.mapTo(tbw, QPoint(0, 0)).x()
    check(f"1920 下工具行子控件在行内（{cw.objectName() or type(cw).__name__}）",
          _x >= -1 and _x + cw.width() <= tbw.width() + 1,
          f"x={_x} w={cw.width()} tb={tbw.width()}")
shot(scroll_w, "v1351_smart_fuzzy_1920.png")
win._toggle_guides_expand()
for _ in range(3):
    app.processEvents()
shot(scroll_w, "v1351_smart_fuzzy_1920_expanded.png")
win._toggle_guides_expand()
for _ in range(3):
    app.processEvents()
shot(win, "v1351_window_1920.png")     # 整窗：确认侧栏品牌 logo = logo-4.png

# ---------------- ② logo ----------------
check("logo-4.png 存在", os.path.exists(logo_path), logo_path)
main_src = open(os.path.join(SRC, "main.py"), encoding="utf-8").read()
check("main.py 已切到 logo-4.png",
      'logo-4.png' in main_src and '_app_resource("logo-3.png")' not in main_src)
splash_src = open(os.path.join(SRC, "splash.py"), encoding="utf-8").read()
check("splash.py 已切到 logo-4.png",
      '"logo-4.png"' in splash_src and '"logo-3.png"' not in splash_src)
be_src = open(os.path.join(ROOT, "build_exe.py"), encoding="utf-8").read()
check("build_exe.py 已切到 logo-4.png",
      "'logo-4.png')" in be_src and "'logo-3.png')};" not in be_src)
check("窗口图标可加载（logo-4.png）", not win.windowIcon().isNull())

# ---------------- ③ 版本 ----------------
check("外部版本号 = v1.35.1", ver.VERSION == "v1.35.1", ver.VERSION)
check("内部构建号 = 2609300053", ver.BUILD == "2609300053", ver.BUILD)

print("")
print(f"==== v1.35.1 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  "
      f"(失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAIL:", n)
sys.exit(1 if FAIL else 0)
