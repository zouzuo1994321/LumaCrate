# -*- coding: utf-8 -*-
"""v1.13.0 离线冒烟：覆盖用户 8 条反馈的修复。

全部使用临时数据库 + 临时 settings.json，绝不触碰真实索引 / 配置。
运行：python -u -c "import runpy; runpy.run_path(r'<本文件>', run_name='__main__')"
"""
import os
import sys
import time
import shutil
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QPushButton, QProgressBar, QLineEdit, QLabel
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

TMP = tempfile.mkdtemp(prefix="lmc_smoke130_")
import database as db
import config as cfg

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")

app = QApplication.instance() or QApplication([])
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import version as ver
import applog

# 日志也指向临时目录，别把测试记录混进真实 index_data/logs/app.log
_LOG_TMP = os.path.join(TMP, "logs")
os.makedirs(_LOG_TMP, exist_ok=True)
applog.log_dir = lambda: _LOG_TMP

import backup as backup_mod
from main_window import (MainWindow, load_style, SCAN_MODE_CN, FolderScanDialog,
                         CountWorker, ScanWorker)
import ui_settings as us

ERRORS = []
INFO = []


def check(ok, msg, extra=None):
    tag = "OK  " if ok else "FAIL"
    line = f"{tag} - {msg}"
    if extra is not None:
        line += f"   {extra}"
    print(line, flush=True)
    (INFO if ok else ERRORS).append(line)


def pump(cond, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------- 准备数据
db.init_db()
cfg.get_settings().save()
load_style(app)

# 建一个临时"媒体库"目录（含两个视频文件，无 nfo → 会按裸视频入库）
lib_dir = os.path.join(TMP, "LibA")
os.makedirs(os.path.join(lib_dir, "A"), exist_ok=True)
for n in ("01.mp4", "02.mp4"):
    with open(os.path.join(lib_dir, "A", n), "wb") as f:
        f.write(b"x" * 1024)

cfg.get_settings().add_library("测试库", "电影", [lib_dir])

# 直接写入 9 条媒体记录，用于验证影片墙列数
for i in range(9):
    db.upsert_media_by_path(mode="overwrite", title=f"M{i}", kind="movie",
                            file_path=os.path.join(TMP, f"m{i}.mkv"),
                            year=2000 + i, library="测试库",
                            added_date="2026-09-18 00:00:00")

win = MainWindow()
win.resize(1600, 900)
win.show()
app.processEvents()

# ---------------------------------------------------------------- 1) 版本
check(ver.VERSION == "v1.13.0", "版本号为 v1.13.0", ver.FULL_VERSION)

# ---------------------------------------------------------------- 8) 影片墙每行 8 个
items = db.search_media()
w = win._grid(items)
# v1.14.0：`_grid` 现在返回增量渲染的 LazyGrid（内层才是 QGridLayout），
# 且首屏之后才建卡 → 先 pump 到全部载入，再断言列数。
from main_window import LazyGrid                     # noqa: E402
_grid_widget = w if isinstance(w, LazyGrid) else w.findChild(LazyGrid)
pump(lambda: _grid_widget is not None and _grid_widget._loaded >= len(items))
lay = _grid_widget._grid
check(lay.itemAtPosition(0, 7) is not None, "影片墙第 1 行第 8 列有卡片")
check(lay.itemAtPosition(0, 8) is None, "影片墙第 1 行第 9 列无卡片（每行恰好 8 个）")
check(lay.itemAtPosition(1, 0) is not None, "第 9 个卡片换到第 2 行")

# ---------------------------------------------------------------- 4) 左下角统计刷新
before = win.stat_label.text()
db.upsert_media_by_path(mode="overwrite", title="Extra", kind="movie",
                        file_path=os.path.join(TMP, "extra.mkv"), library="测试库",
                        added_date="2026-09-18 00:00:00")
win._refresh_view()
after = win.stat_label.text()
check(before != after, "「刷新」会重算左下角统计（数量确实变化）",
      f"{before.splitlines()[0]} -> {after.splitlines()[0]}")
check("电影" in after and "演员" in after, "统计包含电影/剧集/分集/演员四项")
check(hasattr(win, "_refresh_view"), "MainWindow 有 _refresh_view 入口")

# ---------------------------------------------------------------- 3) 文件夹右键扫描
folders_page = win._view_folders()
fbtns = [b for b in folders_page.findChildren(QPushButton) if "项）" in (b.text() or "")]
check(len(fbtns) >= 1, "文件夹视图列出了媒体库按钮", [b.text() for b in fbtns])
if fbtns:
    check(fbtns[0].contextMenuPolicy() == Qt.CustomContextMenu,
          "文件夹按钮启用了右键菜单（CustomContextMenu）")
check(all(k in SCAN_MODE_CN for k in ("new", "fill", "overwrite")),
      "三种扫描模式文案齐备", list(SCAN_MODE_CN.values()))
check(hasattr(win, "_folder_menu") and hasattr(win, "_scan_folder"),
      "MainWindow 有 _folder_menu / _scan_folder")
check(CountWorker is not None and ScanWorker is not None, "CountWorker / ScanWorker 可用")

# FolderScanDialog：先统计数量 → 可确认 → 扫描并出进度
lib_cfg = cfg.get_settings().library("测试库")
dlg = FolderScanDialog(win, lib_cfg, "new")
dlg.show()
ok = pump(lambda: dlg.start.isEnabled(), timeout=30)
check(ok, "扫描对话框先统计出数量后才允许「开始扫描」")
check("共发现" in dlg.count_lbl.text(), "对话框显示统计数量", dlg.count_lbl.text())
check(isinstance(dlg.bar, QProgressBar), "对话框有进度条（显示扫描进度）")
dlg._start_scan()
pump(lambda: not dlg._scanning, timeout=40)
check(not dlg._scanning, "扫描已结束")
check(isinstance(dlg.result, dict) and "error" not in dlg.result,
      "扫描返回统计（无错误）", dlg.result)
dlg.close()

# ---------------------------------------------------------------- 5) 名称框样式一致
qss = open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()
check("QDialog QLineEdit" in qss, "QSS 有「对话框内 QLineEdit 与下拉框一致」规则")
check("border-radius: 8px; padding: 5px 10px" in qss,
      "该规则使用与 QComboBox 相同的圆角/内边距")

# ---------------------------------------------------------------- 设置页
sd = us.SettingsDialog(win)
sd.resize(1080, 800)
sd.show()
app.processEvents()

# 1) 导航菜单行距 + 7) 去掉下方空白
check(sd.nav_list.height() == len(sd.s.nav) * us.NAV_ROW_H + 14,
      "导航菜单列表高度贴合条目数（无多余空白）",
      f"h={sd.nav_list.height()} rows={len(sd.s.nav)} rowH={us.NAV_ROW_H}")
check(us.NAV_ROW_H >= 40, "导航菜单行高已加大", us.NAV_ROW_H)

# 2) 数据源行距 + 描述完整显示
wrapped = [l for l in sd.src_list.findChildren(QLabel) if l.wordWrap()]
check(us.SRC_ROW_H >= 44, "数据源行高已加大", us.SRC_ROW_H)
check(len(wrapped) >= 1, "数据源描述标签允许换行（完整显示不再被裁）")

# 6) 数据与日志页
check("数据与日志" in sd.sub_btns, "设置导航含「数据与日志」")
check(getattr(sd, "_pg_data", None) is not None, "数据与日志页已加入 stack")
sd._show("数据与日志")
app.processEvents()
all_btns = [b.text() for b in sd._pg_data.findChildren(QPushButton)]
for want in ("导出数据…", "导入数据…", "导出日志…", "打开日志文件夹"):
    check(want in all_btns, f"数据与日志页有按钮：{want}", all_btns)
check("日志位置" in sd.log_path_lbl.text(), "显示日志文件位置")

# 日志系统
applog.log("smoke_v130 测试日志条目")
check(os.path.exists(applog.log_path()), "日志文件已生成", applog.log_path())
log_zip = os.path.join(TMP, "logs.zip")
r = applog.export_logs(log_zip)
check(r.get("ok") and os.path.exists(log_zip), "日志可打包导出", r)

# 数据导出 / 导入
data_zip = os.path.join(TMP, "backup.zip")
r = backup_mod.export_data(data_zip)
check(r.get("ok") and os.path.exists(data_zip), "数据可打包导出", r)
if r.get("ok"):
    import zipfile
    names = set(zipfile.ZipFile(data_zip).namelist())
    check("media_center.db" in names, "备份包含数据库快照", sorted(names))
    check("backup_info.txt" in names, "备份包含版本/时间信息")
r2 = backup_mod.import_data(data_zip)
check(r2.get("ok"), "备份可导入恢复", r2)

sd.close()

print()
if ERRORS:
    print(f"==== 有 {len(ERRORS)} 项失败 ====")
    for e in ERRORS:
        print(e)
    raise SystemExit(1)
print(f"==== 全部通过（{len(INFO)} 项） ====")
