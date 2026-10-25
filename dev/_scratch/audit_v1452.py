# -*- coding: utf-8 -*-
"""v1.45.2 第二轮全量体检（只读）：编译/导入/版本/QSS/页面几何/风险点/真实库查询计划。"""
import io
import os
import py_compile
import sqlite3
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = tempfile.mkdtemp(prefix="lmc_audit2_")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtWidgets import QApplication, QGroupBox
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
if os.path.exists("C:/Windows/Fonts/msyh.ttc"):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")

print("== 1. 编译 ==")
bad = []
for f in sorted(os.listdir(SRC)):
    if f.endswith(".py"):
        try:
            py_compile.compile(os.path.join(SRC, f), doraise=True)
        except Exception as e:
            bad.append((f, str(e)[:100]))
print("  失败:", bad or "无")

import database as db
import config as cfg

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

print("== 2. 导入 ==")
imp = []
for m in ("applog", "backdrop", "backup", "duplicates", "i18n", "imagedetect", "insight",
          "nfo_parser", "player", "prefs", "scraper", "scanner", "sysmon", "tagopt",
          "ui_actorcheck", "ui_cleanup", "ui_hero", "ui_home", "ui_imagedetect",
          "ui_manualedit", "ui_settings", "main_window", "version"):
    try:
        __import__(m)
    except Exception as e:
        imp.append((m, f"{type(e).__name__}: {e}"[:120]))
print("  失败:", imp or "无")

import version as VER
import main_window as mw
import ui_settings as uis

print("== 3. 版本一致性 ==")
readme = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
print("  version.py:", VER.VERSION, VER.BUILD)
print("  README 徽章/下载名:", (VER.VERSION in readme and VER.BUILD in readme),
      readme.count(f"流明盒-{VER.VERSION}-{VER.BUILD}.exe"))
print("  根目录 exe:", os.path.exists(os.path.join(ROOT, f"流明盒-{VER.VERSION}-{VER.BUILD}.exe")))

print("== 4. QSS ==")
qss = mw.render_style(cfg.get_settings().appearance)
for k, ok in (("QMainWindow 不透明", "QMainWindow { background: #0d0b0a; }" in qss),
              ("状态栏面板色", "background: #1c1815" in qss),
              ("FooterNote/ToastNote", "QLabel#FooterNote" in qss and "QLabel#ToastNote" in qss),
              ("滑块 18/4", "width: 18px; margin: -3px 0; border-radius: 4px;" in qss),
              ("数据源滚轴", "QListWidget#SrcSourceList QScrollBar:vertical" in qss),
              ("无未替换令牌", not any(t in qss for t in ("__ACCENT__", "__PANEL__",
                                                        "__SURF__", "__DLG__", "__VEIL__")))):
    print("  [%s] %s" % ("OK" if ok else "!!", k))

print("== 5. 页面几何 ==")
win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
for _ in range(8):
    app.processEvents()
dlg = uis.SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
for _ in range(8):
    app.processEvents()
for name in ["个性化设置", "服务管理", "手动修改", "引擎设置", "演员刮削", "智能推荐",
             "标签优化", "重复检测", "演员检测", "图像检测", "画像概览",
             "数据管理", "日志中心"]:
    try:
        dlg._show(name)
        for _ in range(8):
            app.processEvents()
        pg = dlg.stack.currentWidget()
        inner = pg
        seen = 0
        while hasattr(inner, "widget") and seen < 3:
            w = inner.widget()
            if w is None:
                break
            inner = w
            seen += 1
        gs = inner.findChildren(QGroupBox)
        tiny = [g.title()[:16] for g in gs if g.height() < 30]
        print("  %-6s %4dx%-5d 组框 %d%s" % (name, inner.width(), inner.height(), len(gs),
                                          ("  ⚠" + str(tiny)) if tiny else ""))
    except Exception as e:
        print("  %-6s 失败: %s" % (name, e))

print("== 6. 风险点 ==")
mw_src = io.open(os.path.join(SRC, "main_window.py"), encoding="utf-8").read()
sc_src = io.open(os.path.join(SRC, "scraper.py"), encoding="utf-8").read()
pf_src = io.open(os.path.join(SRC, "prefs.py"), encoding="utf-8").read()
print("  showMessage 残留:", mw_src.count(".showMessage("))
print("  theporndb 残留:", sc_src.count("theporndb") + pf_src.count("theporndb"))
print("  gfriends 默认 ~/.lmacrate:", 'expanduser("~")' in sc_src)
print("  prefs 0 分语义已修:", 'it.get("user_rating") is not None' in pf_src)
print("  HeroView 回调点:", open(os.path.join(SRC, "ui_home.py"), encoding="utf-8").read()
      .count("on_open_actors=self.on_open_actors"))

print("== 7. 真实库（只读） ==")
dbp = os.path.join(ROOT, "index_data", "media_center.db")
con = sqlite3.connect("file:" + dbp.replace("\\", "/") + "?mode=ro", uri=True, timeout=8)
try:
    print("  integrity:", con.execute("PRAGMA integrity_check").fetchone()[0])
    print("  media/people/links:",
          con.execute("SELECT COUNT(*) FROM media").fetchone()[0],
          con.execute("SELECT COUNT(*) FROM people").fetchone()[0],
          con.execute("SELECT COUNT(*) FROM media_people").fetchone()[0])
    print("  media 索引数:", con.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='media'").fetchone()[0])
    for key, expr, asc in (("名称升序", "m.sort_title COLLATE NOCASE", "ASC"),
                           ("名称降序", "m.sort_title COLLATE NOCASE", "DESC"),
                           ("最近添加", "m.added_time", "DESC"),
                           ("播放次数", "m.play_count", "DESC")):
        sql = ("SELECT m.id FROM media m WHERE m.parent_id IS NULL ORDER BY %s %s, "
               "m.year DESC, m.id ASC LIMIT 60" % (expr, asc))
        plan = [r[-1] for r in con.execute("EXPLAIN QUERY PLAN " + sql)]
        t0 = time.perf_counter()
        con.execute(sql).fetchall()
        ms = (time.perf_counter() - t0) * 1000
        print("  %-6s %6.2f ms  %s" % (key, ms, "TEMP B-TREE!" if any("TEMP B-TREE" in p for p in plan) else "索引有序"))
    sql = ("SELECT p.id, COUNT(mp.media_id) c FROM people p "
           "LEFT JOIN media_people mp ON mp.person_id=p.id WHERE p.role_type='Actor' "
           "GROUP BY p.id ORDER BY p.pinned DESC, c DESC, p.name COLLATE NOCASE LIMIT 60")
    t0 = time.perf_counter()
    con.execute(sql).fetchall()
    print("  演员库首屏 %.1f ms（BUG-02 未修，见计划）" % ((time.perf_counter() - t0) * 1000))
finally:
    con.close()
print("AUDIT2_DONE")
