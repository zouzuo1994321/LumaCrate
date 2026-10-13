# -*- coding: utf-8 -*-
"""v1.38.0 离屏冒烟（构建期）。

两条变更的回归与单元断言：
① bug 修复：多目录「顺序即扫描优先级，自上而下依次扫描」过程中首页数量不更新 ——
   三处扫描入口（媒体库右键 _scan_library_cat / 文件夹扫描对话框 FolderScanDialog._start_scan /
   后台定时扫描 _bg_scan_next）创建 ScanWorker 时都必须连接 live 信号到 _on_scan_live。
② 功能新增：演员检测多选批量确认关联 —— 结果树新增「选择」复选框列 + 全选/全不选/
   批量合并工具栏；_merge_checked 按各簇默认保留艺名逐簇调用 db.merge_people。

使用临时数据库与临时配置，绝不读写真实索引 / 真实 settings.json。
"""
import os
import sys
import inspect
import shutil
import tempfile
import faulthandler

faulthandler.enable()

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1380_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase

app = QApplication(sys.argv)

import database as db
import config as cfg
import version as ver
import applog
import ui_actorcheck as ack_page
from main_window import MainWindow, FolderScanDialog, load_style

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

FAIL = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("   -> " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(name)


# ================================================================ ① 三处扫描入口连 live
print("\n---- ① 扫描入口 live 信号连接（首页实时刷新修复）----")
src_scan = inspect.getsource(MainWindow._scan_library_cat)
src_folder = inspect.getsource(FolderScanDialog._start_scan)
src_bg = inspect.getsource(MainWindow._bg_scan_next)
check("右键「扫描」( _scan_library_cat ) 连接 live 信号",
      "live.connect(self._on_scan_live)" in src_scan)
check("文件夹扫描对话框( FolderScanDialog._start_scan ) 连接 live 信号",
      "live.connect(self._on_scan_live)" in src_folder)
check("后台定时扫描( _bg_scan_next ) 连接 live 信号",
      "live.connect(self._on_scan_live)" in src_bg)
# 第一入口（顶栏「扫描媒体库」）原本就连着，顺带确认没被误删
src_top = inspect.getsource(MainWindow._scan)
check("顶栏「扫描媒体库」( _scan ) 仍连 live 信号（不回归）",
      "live.connect(self._on_scan_live)" in src_top)


# ================================================================ ② 演员检测多选批量合并
print("\n---- ② 演员检测：选择列 + 批量合并工具栏 ----")
page = ack_page.ActorCheckPage()
check("演员检测页可离屏构建", page is not None)
check("结果树有 5 列（含最左「选择」列）", page.tree.columnCount() == 5, page.tree.columnCount())
check("第 0 列表头为「选择」", page.tree.headerItem().text(0) == "选择",
      page.tree.headerItem().text(0))
check("批量工具栏：全选 / 全不选 / 批量合并 三按钮齐全",
      hasattr(page, "sel_all_btn") and hasattr(page, "sel_none_btn")
      and hasattr(page, "batch_merge_btn"))
check("批量合并按钮初始禁用且文案含「合并 0 簇」",
      (not page.batch_merge_btn.isEnabled())
      and "合并 0 簇" in page.batch_merge_btn.text(), page.batch_merge_btn.text())

# 造两份假簇 → 填入树
page._res = {"merge_people": 2}
page._suspects = []
page._clusters = [
    {"ids": [10, 20], "keep_id": 10, "score": 90, "tier": "铁证",
     "reasons": ["罗马音一致"], "total_works": 6,
     "members": [{"id": 10, "name": "明里つくし", "works": 5, "photo": ""},
                 {"id": 20, "name": "つくし明里", "works": 1, "photo": ""}]},
    {"ids": [11, 21], "keep_id": 11, "score": 85, "tier": "很高",
     "reasons": ["别名互指"], "total_works": 3,
     "members": [{"id": 11, "name": "佐藤さん", "works": 2, "photo": ""},
                 {"id": 21, "name": "サトウ", "works": 1, "photo": ""}]},
]


def _cluster_items():
    out = []
    for i in range(page.tree.topLevelItemCount()):
        top = page.tree.topLevelItem(i)
        for j in range(top.childCount()):
            it = top.child(j)
            if it.data(0, page.ROLE_KIND) == "cluster":
                out.append(it)
    return out


page._fill_tree()
items = _cluster_items()
check("填入 2 个建议合并簇", len(items) == 2, len(items))
check("簇行带复选框(ItemIsUserCheckable)",
      bool(items[0].flags() & ack_page.Qt.ItemIsUserCheckable))
check("簇行初始未勾选", items[0].checkState(0) == ack_page.Qt.Unchecked)

# 勾选 1 簇 → 计数与按钮状态
items[0].setCheckState(0, ack_page.Qt.Checked)
check("勾选 1 簇后计数 = 1", page._count_checked_clusters() == 1, page._count_checked_clusters())
check("勾选后批量按钮启用且文案含「合并 1 簇」",
      page.batch_merge_btn.isEnabled()
      and "合并 1 簇" in page.batch_merge_btn.text(), page.batch_merge_btn.text())

# 批量合并（mock 掉确认弹窗 + db.merge_people，验证逐簇调用与标记逻辑）
captured = []
orig_merge = db.merge_people
db.merge_people = lambda keep, drop: (captured.append((keep, drop)),
                                      {"ok": True, "moved": 3})[1]
orig_exec = ack_page.QMessageBox.exec
ack_page.QMessageBox.exec = lambda self: ack_page.QMessageBox.Yes
try:
    page._merge_checked()
finally:
    db.merge_people = orig_merge
    ack_page.QMessageBox.exec = orig_exec
check("批量合并只调 keep_id→drop_id（10→20）", captured == [(10, 20)], captured)
check("合并后该行标记为「已合并」", items[0].text(3) == "已合并", items[0].text(3))
check("合并后该行复选框自动取消", items[0].checkState(0) == ack_page.Qt.Unchecked)
check("合并后批量按钮回到「合并 0 簇」且禁用",
      (not page.batch_merge_btn.isEnabled())
      and "合并 0 簇" in page.batch_merge_btn.text(), page.batch_merge_btn.text())

# 全选 / 全不选
page._fill_tree()
items2 = _cluster_items()
items2[0].setCheckState(0, ack_page.Qt.Checked)
items2[1].setCheckState(0, ack_page.Qt.Checked)
check("全选两个后计数 = 2", page._count_checked_clusters() == 2, page._count_checked_clusters())
page._uncheck_all()
check("全不选后计数 = 0", page._count_checked_clusters() == 0, page._count_checked_clusters())


# ================================================================ ③ 树勾选框样式
print("\n---- ③ 树控件复选框样式（暗色主题可见性）----")
qss_src = open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()
check("style.qss 含 QTreeView::indicator 规则（树行内复选框）",
      "QTreeView::indicator" in qss_src)
check("QTreeView::indicator:checked 勾选态用高亮色",
      "QTreeView::indicator:checked { background: __ACCENT__" in qss_src)
load_style(app)
ss = app.styleSheet()
check("render_style 后无残留 __ACCENT 令牌", "__ACCENT" not in ss)
check("QTreeView::indicator 已进入已解析样式表", "QTreeView::indicator" in ss)


# ================================================================ ④ 版本号
print("\n---- ④ 版本号 ----")
check("外部版本号 = v1.38.0", ver.VERSION == "v1.38.0", ver.VERSION)
check("内部构建号 = 2610120056", ver.BUILD == "2610120056", ver.BUILD)

print("")
print(f"==== v1.38.0 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  (失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAIL:", n)

try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if FAIL else 0)
