# -*- coding: utf-8 -*-
"""v1.23.0 设置 → 重复检测 的离屏功能探针。

不只是断言方法存在，而是真的把 SettingsDialog 建出来、切到「重复检测」页、
跑一次检测（临时库 + 造好的重复数据），确认结果表真的填出了行。
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_dedupe_ui_")
os.makedirs(os.path.join(TMP, "index_data"), exist_ok=True)

import database as db  # noqa: E402
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
import applog  # noqa: E402
applog.log_dir = lambda: os.path.join(TMP, "logs")
db.init_db()

MB = 1048576


def add(lib, path, size, **kw):
    base = os.path.splitext(os.path.basename(path))[0]
    f = {"kind": "movie", "title": base, "sort_title": base, "file_path": path,
         "file_size": size, "library": lib, "runtime": "01:00:00"}
    f.update(kw)
    return db.insert_media(**f)


# 跨目录重复（番号一致）2 份 + 同目录分片 2 份
add("L", r"L:\A\ABC-123\ABC-123.mp4", 1000 * MB, year=2020)
add("L", r"L:\B\ABC-123\ABC-123.mp4", 700 * MB, year=2020)
add("L", r"L:\C\XYZ-777\XYZ-777-CD1.mp4", 300 * MB, year=2019)
add("L", r"L:\C\XYZ-777\XYZ-777-CD2.mp4", 300 * MB, year=2019)

from PySide6.QtWidgets import (QApplication, QListWidget, QPushButton,  # noqa: E402
                               QTableWidget, QComboBox)
from PySide6.QtGui import QFontDatabase  # noqa: E402

app = QApplication.instance() or QApplication([])
for f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import ui_settings as us  # noqa: E402
import main_window as mw  # noqa: E402
mw.load_style(app)

FAIL = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"   -> {extra}" if (extra and not cond) else ""))
    if not cond:
        FAIL.append(name)


dlg = us.SettingsDialog()

# 1) 导航顺序：设置页左侧导航是 QPushButton（self.sub_btns），不是 QListWidget。
#    既查声明顺序，也按控件实际 y 坐标查**视觉顺序**（防止字典序与布局序不一致）。
EXPECT = ["个性化设置", "演员刮削", "服务管理", "重复检测", "数据与日志"]
declared = list(dlg.sub_btns.keys())
check("导航声明顺序正确", declared == EXPECT, declared)
visual = sorted(dlg.sub_btns.items(), key=lambda kv: kv[1].y())
visual_keys = [k for k, _ in visual]
check("导航视觉顺序正确（按 y 排序）", visual_keys == EXPECT,
      [(k, v.y()) for k, v in visual])
check("重复检测 位于 服务管理 与 数据与日志 之间",
      visual_keys.index("服务管理") < visual_keys.index("重复检测") < visual_keys.index("数据与日志"),
      visual_keys)

# 2) 切到重复检测页
try:
    dlg._show("重复检测")
    app.processEvents()
    page = dlg._pg_dedupe
    texts = [b.text() for b in page.findChildren(QPushButton)]
    check("重复检测页有「开始检测」按钮", any("开始检测" in t for t in texts), texts)
    check("重复检测页有导出按钮",
          any("CSV" in t for t in texts) and any("JSON" in t for t in texts), texts)
    tbl = page.findChildren(QTableWidget)
    check("重复检测页有结果表", len(tbl) == 1, len(tbl))
    combos = page.findChildren(QComboBox)
    check("有媒体库/置信度下拉（≥2）", len(combos) >= 2, len(combos))
except Exception as e:
    check(f"切到重复检测页（异常 {type(e).__name__}: {e}）", False)

# 3) 真跑一次检测（同步调用，不等线程）
try:
    import duplicates as dup
    rep = dup.find_duplicates()
    s = rep.summary()
    check("检出 1 组重复（ABC-123 跨目录）", s["dup_groups"] == 1, s)
    check("同目录分片被排除（XYZ-777 不计重复）", s["multipart_groups"] == 1, s)
    check("可回收 = 700MB（保留最大的一份）", s["redundant_bytes"] == 700 * MB,
          s["redundant_text"])
    # 把结果灌进表格，确认 UI 能显示
    dlg._on_dedupe_done(rep)
    app.processEvents()
    tw = dlg._pg_dedupe.findChildren(QTableWidget)[0]
    check("结果表填出了行", tw.rowCount() >= 1, tw.rowCount())
except Exception as e:
    import traceback
    traceback.print_exc()
    check(f"跑一次检测（异常 {type(e).__name__}: {e}）", False)

print()
print("==== 重复检测 UI 探针：%s ====" % ("ALL PASS" if not FAIL else f"{len(FAIL)} FAIL"))
for f in FAIL:
    print("  FAIL:", f)
sys.exit(0 if not FAIL else 1)
