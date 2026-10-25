# -*- coding: utf-8 -*-
"""v1.43.5 全量体检（只读）：编译 / 导入 / 版本一致性 / QSS 令牌 / 页面几何 /
已知风险点扫描。不写库、不改任何源码。"""
import io
import os
import py_compile
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = tempfile.mkdtemp(prefix="lmc_audit_")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtWidgets import QApplication, QGroupBox
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
if os.path.exists("C:/Windows/Fonts/msyh.ttc"):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")

print("== 1. 语法编译（全部 src/*.py）==")
bad = []
for f in sorted(os.listdir(SRC)):
    if f.endswith(".py"):
        try:
            py_compile.compile(os.path.join(SRC, f), doraise=True)
        except Exception as e:
            bad.append((f, str(e)[:120]))
print("  编译失败:", bad or "无")

print("== 2. 模块导入 ==")
import database as db
import config as cfg

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

mods = ["applog", "backdrop", "backup", "duplicates", "i18n", "imagedetect", "insight",
        "nfo_parser", "player", "prefs", "scraper", "scanner", "sysmon", "tagopt",
        "ui_actorcheck", "ui_cleanup", "ui_hero", "ui_home", "ui_imagedetect",
        "ui_manualedit", "ui_settings", "main_window", "version"]
imp_bad = []
for m in mods:
    try:
        __import__(m)
    except Exception as e:
        imp_bad.append((m, f"{type(e).__name__}: {e}"[:140]))
print("  导入失败:", imp_bad or "无")

import version as VER
import main_window as mw
import ui_settings as uis

print("== 3. 版本一致性 ==")
print("  version.py:", VER.VERSION, VER.BUILD)
readme = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
print("  README 徽章含当前版本:", VER.VERSION in readme and VER.BUILD in readme)
print("  README exe 名次数:", readme.count(f"流明盒-{VER.VERSION}-{VER.BUILD}.exe"))
print("  根目录 exe 存在:", os.path.exists(os.path.join(ROOT, f"流明盒-{VER.VERSION}-{VER.BUILD}.exe")))
print("  history 归档存在:", os.path.exists(os.path.join(ROOT, "history", f"流明盒-{VER.VERSION}-{VER.BUILD}.exe")))

print("== 4. QSS 关键令牌/规则 ==")
qss = mw.render_style(cfg.get_settings().appearance)
for k, ok in (
    ("QMainWindow 不透明底", "QMainWindow { background: #0d0b0a; }" in qss),
    ("状态栏面板色", "background: #1c1815" in qss),
    ("状态栏无 #0f0d0b", "background: #0f0d0b" not in qss),
    ("FooterNote 样式", "QLabel#FooterNote" in qss),
    ("滑块把手 18/4", "width: 18px; margin: -3px 0; border-radius: 4px;" in qss),
    ("数据源滚轴加粗", "QListWidget#SrcSourceList QScrollBar:vertical" in qss),
    ("ImageSplitH 透明", "QSplitter#ImageSplitH::handle:horizontal" in qss),
    ("无未替换令牌", "__ACCENT__" not in qss and "__PANEL__" not in qss
     and "__SURF__" not in qss and "__DLG__" not in qss and "__VEIL__" not in qss),
):
    print("  [%s] %s" % ("OK" if ok else "!!", k))

print("== 5. 工具页几何（是否有关键组被压扁 / 页面溢出）==")
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
PAGES = ["个性化设置", "服务管理", "手动修改", "AI引擎设置", "演员刮削", "智能推荐",
         "标签优化", "重复检测", "演员检测", "图像检测", "画像概览", "数据与日志"]
for name in PAGES:
    try:
        dlg._show(name)
        for _ in range(10):
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
        tiny = [(g.title()[:18], g.height()) for g in gs if g.height() < 30]
        print("  %-8s 页 %dx%d 组框 %d 个%s"
              % (name, inner.width(), inner.height(), len(gs),
                 ("  ⚠ 过矮:" + str(tiny)) if tiny else ""))
    except Exception as e:
        print("  %-8s 切换失败: %s" % (name, e))

print("== 6. 已知风险点扫描 ==")
def scan(path, needles):
    txt = io.open(path, encoding="utf-8", errors="replace").read()
    return {n: txt.count(n) for n in needles}

sc = scan(os.path.join(SRC, "scraper.py"), ['expanduser("~")', "lmacrate", "_TPDB_TOKEN"])
print("  gfriends 默认缓存目录 ~/.lmacrate 引用:", sc['expanduser("~")'], "| lmacrate:", sc["lmacrate"])
print("  根目录是否已有 .lmacrate:", os.path.isdir(os.path.join(os.path.expanduser("~"), ".lmacrate")))

pj = io.open(os.path.join(SRC, "prefs.py"), encoding="utf-8").read()
print("  prefs 导入：评分仅在 >0 时写回（无法恢复/清空 0 分）:",
      'if it.get("user_rating"):' in pj)
mw_txt = io.open(os.path.join(SRC, "main_window.py"), encoding="utf-8").read()
print("  状态栏仍用 showMessage 的位置数（应为临时消息）:", mw_txt.count(".showMessage("))
print("  HeroView 构造点（应有 on_open_actors）:", mw_txt.count("HeroView("))
hv = io.open(os.path.join(SRC, "ui_hero.py"), encoding="utf-8").read()
ui_home_txt = io.open(os.path.join(SRC, "ui_home.py"), encoding="utf-8").read()
print("  ui_home 透传 on_open_actors:", "on_open_actors=self.on_open_actors" in ui_home_txt)

print("== 7. i18n 完整性 ==")
import i18n
miss = [c for c in i18n.TOOL_KEYS if "数据与日志" not in i18n.TOOL_KEYS[c]]
print("  缺少「数据与日志」的语言数:", len(miss), miss[:5])
print("  旧键「元数据管理」残留:", sum(1 for c in i18n.TOOL_KEYS if "元数据管理" in i18n.TOOL_KEYS[c]))

print("== 8. 数据库关键函数 ==")
for fn in ("orphan_people", "delete_people", "search_people", "merge_people",
           "set_user_rating", "toggle_favorite", "query_people"):
    print("  %-18s %s" % (fn, hasattr(db, fn)))

print("== 9. 历史冒烟文件 ==")
dev = os.path.join(ROOT, "dev")
smo = sorted(f for f in os.listdir(dev) if f.startswith("smoke_v") and f.endswith(".py"))
print("  smoke 脚本:", smo)
print("AUDIT_DONE")
