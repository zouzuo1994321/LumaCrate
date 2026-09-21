# -*- coding: utf-8 -*-
"""v1.24.0 界面预览（离屏渲染出 PNG，供人工核对视觉）

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/preview_v1240.py', run_name='__main__')"

产出：`dev/screenshots_v1240/*.png`

约定（踩过的坑）：
- `QPixmap/QPainter` 必须在 `QApplication` 之后创建，否则 offscreen 原生崩 127；
- 渲染前先注册中文字体（msyh.ttc）+ `load_style(app)`，否则字体回退导致 sizeHint 虚高、看起来像溢出；
- 用 `QPixmap(w,h)→fill(已知底色)→render()`，**不要**用 `widget.grab()`（未初始化内存随机）；
- LazyGrid 的卡片要等事件循环，渲染前必须反复 `processEvents()`。
"""
import os
import sys
import time
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

OUT = os.path.join(ROOT, "dev", "screenshots_v1240")
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(tempfile.gettempdir(), "lmc_preview_v1240")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SPLASH"] = "1"          # 启动画面单独渲染，不让它弹出来

import applog
applog.log_dir = lambda: os.path.join(TMP, "index_data", "logs")
applog.log_path = lambda: os.path.join(TMP, "index_data", "logs", "app.log")

import config as cfg
import database as db
cfg.config_path = lambda: os.path.join(TMP, "settings.json")   # 绝不碰用户真实配置

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QPixmap, QColor, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication.instance() or QApplication(sys.argv)
for cand in (os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "msyh.ttc"),
             os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "msyhbd.ttc")):
    if os.path.exists(cand):
        QFontDatabase.addApplicationFont(cand)

import main_window as mw
mw.load_style(app)


def pump(n=14):
    """推事件循环。

    **必须带真实 sleep**：LazyGrid 用 `QTimer.singleShot(1, self._pump)` 分批建卡，
    光调 `processEvents()` 在 <1ms 内连推十几次，那个 1ms 定时器根本没到期 →
    页面永远停在 0 张卡（v1.24.0 出图时踩过：导演库/合集页全空白）。
    """
    for _ in range(n):
        QCoreApplication.processEvents()
        app.processEvents()
        time.sleep(0.012)


def diag(win, tag, cls=None):
    """打印当前页的卡片数 / 网格进度，便于判断「空白」是真空白还是没推够。"""
    cur = win.stack.currentWidget()
    if cur is None:
        print(f"    [{tag}] 当前页为空")
        return
    n = len(cur.findChildren(cls)) if cls is not None else -1
    grids = cur.findChildren(mw.LazyGrid)
    for g in grids:
        print(f"    [{tag}] 卡片={n} 已建={g._loaded} 总数={g._total} "
              f"批次={g.batch} 页宽={g.width()}x{g.height()} 错误={g._error!r}")
    if not grids:
        print(f"    [{tag}] 无 LazyGrid；子控件 {len(cur.findChildren(QWidget))} 个")


def shot(widget, name, w=None, h=None):
    """离屏渲染成 PNG（先 fill 底色再 render，避免读到未初始化内存）。"""
    widget.ensurePolished()
    if w is None or h is None:
        w, h = widget.width(), widget.height()
    w, h = max(int(w), 200), max(int(h), 160)
    pm = QPixmap(w, h)
    pm.fill(QColor("#0f0d0b"))
    widget.render(pm)
    path = os.path.join(OUT, f"{name}.png")
    pm.save(path, "PNG")
    print(f"  已保存 {os.path.relpath(path, ROOT)}  {w}x{h}")
    return path


# ---------------------------------------------------------------- 1) 启动画面
print("[1/8] 启动画面")
os.environ.pop("LMC_NO_SPLASH", None)
import splash as splash_mod
sp = splash_mod.SplashScreen(os.path.join(ROOT, "logo.png"))
sp.setProgress(64, "正在载入界面样式…")
sp.show()
pump(4)
shot(sp, "01_启动画面_蓝色", sp.W, sp.H)
sp.close()
os.environ["LMC_NO_SPLASH"] = "1"

# ---------------------------------------------------------------- 2) 主界面（侧栏进度环 + 工具按钮）
print("[2/8] 主界面（含扫描进度环）")
s = cfg.get_settings()
if not s.library_names():
    s.add_library("Jav-library", "电影", [os.path.join(TMP, "lib")])
    s.add_library("Jav-VR", "电影", [os.path.join(TMP, "vr")])
win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
win.resize(1440, 900)
# **必须 show()**：不 show 的话 Qt 不会激活布局，卡片控件的几何全是默认值（640x480
# 那种），render() 出来就是一张只有工具栏没有卡片的空页（v1.24.0 出图时误判过）。
win.show()
pump(10)
names = list(win._lib_rings)
if names:
    win._lib_ring(names[0], True, 37, "正在扫描")     # 造一个「正在刷新」的态
pump(4)
shot(win, "02_主界面_侧栏扫描进度环")

# ---------------------------------------------------------------- 3) 导演库
print("[3/8] 导演库（不含生日/出身地/身高/胸围/三围）")
win.go(win._view_directors)
pump(30)
diag(win, "导演库", mw.DirectorCard)
shot(win, "03_导演库")

# ---------------------------------------------------------------- 4) 合集（卡片墙）
print("[4/8] 合集（影片墙样式卡片）")
win.go(win._view_collections)
pump(30)
diag(win, "合集", mw.FolderCard)
shot(win, "04_合集卡片墙")

# ---------------------------------------------------------------- 5) 智能推荐
print("[5/8] 智能推荐（真实推荐结果）")
res = None
try:
    import recommend as rec_mod
    res = rec_mod.recommend(page=1, limit=24, algo="normal")
except Exception as e:
    print("   推荐失败：", e)
if res is not None:
    win._smart_res = res
    win._smart_picks = [dict(p) for p in res.get("picks", [])]
    win._smart_algo = "normal"
    win.go(lambda: win._smart_wall())
    pump(30)
    diag(win, "智能推荐", mw.PosterCard)
    shot(win, "05_智能推荐")

# ---------------------------------------------------------------- 6~8) 工具各页
print("[6/8] 工具窗口：画像概览 / 智能推荐 / 重复检测 / 数据导出")
win._open_settings()
dlg = win._settings_dlg
dlg.resize(1000, 880)
dlg.show()
pump(6)

# 6) 画像概览：真的算一遍（约 1.5 秒）
dlg._show("画像概览")
dlg._on_insight_done(insight_data := __import__("insight").Portrait().build())
pump(10)
shot(dlg, "06_工具_画像概览")
print("   雷达值：", [(l, round(v, 2)) for l, v, _d in insight_data["radar"]])

# 7) 智能推荐设置页
dlg._show("智能推荐")
pump(6)
shot(dlg, "07_工具_智能推荐")

# 8) 重复检测（用一份离线样本报告填充树，避免真机跑几分钟）
dlg._show("重复检测")
import duplicates as dup_mod
m1 = dup_mod.DupMember(movie_id=1, path=r"Z:\A\ABP-123\ABP-123.mp4",
                       folder=r"Z:\A\ABP-123", nfo_name="ABP-123.mp4", num="ABP-123",
                       title="ABP-123 示例作品", year=2023, resolution="1080P",
                       video_size=5 * 1024 ** 3, duration_sec=7200, source="Jav-library")
m2 = dup_mod.DupMember(movie_id=2, path=r"X:\B\ABP-123\ABP-123.mkv",
                       folder=r"X:\B\ABP-123", nfo_name="ABP-123.mkv", num="ABP-123",
                       title="ABP-123 示例作品", year=2023, resolution="1080P",
                       video_size=3 * 1024 ** 3, duration_sec=7200, source="Jav-VR")
g = dup_mod.DupGroup(key="ABP123", kind="num", label="ABP-123",
                     members=sorted([m1, m2], key=lambda x: -x.size),
                     by_folder={m1.folder: [m1], m2.folder: [m2]}, confidence="极高")
g.total_bytes = m1.size + m2.size
g.redundant_bytes = min(m1.size, m2.size)
rep = dup_mod.DupReport(groups=[g], multipart=[], scanned=48079, elapsed=6.4,
                        generated_at="2026-09-21 01:40:00", missing=41)
dlg._on_dedupe_done(rep)
dlg.dd_tree.expandAll()
pump(6)
shot(dlg, "08_工具_重复检测_可展开")

dlg._show("数据与日志")
pump(6)
shot(dlg, "09_工具_数据与日志_分类导出")
dlg.close()
win.close()
pump(4)

print("\n预览完成 →", os.path.relpath(OUT, ROOT))
