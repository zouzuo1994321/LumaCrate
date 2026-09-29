# -*- coding: utf-8 -*-
"""v1.34.3 功能全量核查（离屏）。
构造 MainWindow 并访问全部导航页 + 构造 SettingsDialog 验证全部工具页 + 数据层函数真实调用。
输出结构化日志，供汇总「功能状态表」使用。
"""
import os
import sys
import glob
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "src")   # C:/lmc_build/src
sys.path.insert(0, SRC)

TMP = os.path.join(HERE, "_audit_tmp_v1343")
os.makedirs(TMP, exist_ok=True)

results = []


def chk(group, name, cond, extra=""):
    results.append((group, name, bool(cond), extra))
    print(("[OK] " if cond else "[XX] "), f"{group} / {name}", ("  " + extra) if extra else "", flush=True)


print("=" * 70)
print("v1.34.3 功能全量核查")
print("=" * 70)

# ---------- 0) 导入全部模块 ----------
print("\n[0] 导入全部 src 模块…")
import importlib
mod_errors = []
py_files = sorted(glob.glob(os.path.join(SRC, "*.py")))
for pf in py_files:
    name = os.path.splitext(os.path.basename(pf))[0]
    try:
        importlib.import_module(name)
    except Exception as e:
        mod_errors.append((name, f"{type(e).__name__}: {e}"))
chk("模块", f"全部 {len(py_files)} 个模块导入", len(mod_errors) == 0,
    f"失败 {len(mod_errors)}: {mod_errors[:5]}")
del importlib

# ---------- 重定向 db / applog 到临时库 ----------
import database as db
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
import applog
applog.log_dir = lambda: os.path.join(TMP, "logs")

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

# 加载 style（accent token 占位）
qss = open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()
for tok in ("__ACCENT__", "__ACCENT_DARK__", "__ACCENT_DEEP__", "__ACCENT_LIGHT__"):
    qss = qss.replace(tok, "#e05243")
app.setStyleSheet(qss)

# ---------- 1) 数据层：建表 + 播种 + 真实调用 ----------
print("\n[1] 数据层函数真实调用（临时库播种 2 演员 + 1 影片）…")
db.init_db()
conn = db.get_conn()
conn.execute("INSERT INTO people (id,name,role_type) VALUES (1,'Alice','Actor'),(2,'Bob','Actor')")
conn.execute("INSERT INTO media (id,kind,title,sort_title,library,file_path,poster) "
             "VALUES (1,'movie','Test','Test','Lib','x.mp4','p.jpg')")
conn.execute("INSERT INTO media_people (media_id,person_id) VALUES (1,1)")
conn.commit()

try:
    wc = db.person_work_counts()
    chk("数据层", "person_work_counts()", isinstance(wc, dict) and wc.get(1) == 1, str(wc))
except Exception as e:
    chk("数据层", "person_work_counts()", False, f"{type(e).__name__}: {e}")

try:
    pm = db.people_for_match("Actor")
    chk("数据层", "people_for_match()", isinstance(pm, (list, tuple)), f"len={len(pm)}")
except Exception as e:
    chk("数据层", "people_for_match()", False, f"{type(e).__name__}: {e}")

try:
    r = db.set_person_fields(1, bio="test")
    chk("数据层", "set_person_fields()", isinstance(r, int), f"updated={r}")
except Exception as e:
    chk("数据层", "set_person_fields()", False, f"{type(e).__name__}: {e}")

try:
    mg = db.merge_people(1, 2)
    chk("数据层", "merge_people()", isinstance(mg, dict), str(mg))
except Exception as e:
    chk("数据层", "merge_people()", False, f"{type(e).__name__}: {e}")

try:
    mis = db.media_for_imagescan(None)
    chk("数据层", "media_for_imagescan()", isinstance(mis, (list, tuple)), f"len={len(mis)}")
except Exception as e:
    chk("数据层", "media_for_imagescan()", False, f"{type(e).__name__}: {e}")

# 基础查询
try:
    n = db.count_media(); q = db.search_media(limit=10, light=True)
    chk("数据层", "count_media/search_media", n >= 1 and isinstance(q, list), f"count={n}")
except Exception as e:
    chk("数据层", "count_media/search_media", False, f"{type(e).__name__}: {e}")

try:
    p = db.query_people(role_type="Actor", limit=10)
    chk("数据层", "query_people()", isinstance(p, list), f"len={len(p)}")
except Exception as e:
    chk("数据层", "query_people()", False, f"{type(e).__name__}: {e}")

# ---------- 2) 标签优化 / 重复检测 导出导入往返 ----------
print("\n[2] tagopt / duplicates 导出-导入往返…")
import tagopt as tagopt_mod
try:
    plan = [{"file": "x.mp4", "title": "Test", "old_tags": ["a"], "new_tags": ["b"], "error": ""}]
    jp = os.path.join(TMP, "tagopt_plan.json")
    tagopt_mod.export_json(plan, jp)
    back = tagopt_mod.import_json(jp)
    chk("标签优化", "export_json/import_json 往返", len(back) == 1 and back[0]["title"] == "Test",
        f"back={len(back)}")
except Exception as e:
    chk("标签优化", "export_json/import_json 往返", False, f"{type(e).__name__}: {e}")

import duplicates as dup_mod
try:
    chk("重复检测", "export_json/import_json 可调用",
        callable(getattr(dup_mod, "export_json", None)) and callable(getattr(dup_mod, "import_json", None)))
except Exception as e:
    chk("重复检测", "export_json/import_json 可调用", False, f"{type(e).__name__}: {e}")

# ---------- 3) MainWindow：构造 + 访问全部导航页 ----------
print("\n[3] MainWindow 构造并访问 9 个导航页…")
import main_window as mw
try:
    win = mw.MainWindow()
    win.show()
    app.processEvents()
    chk("主窗口", "MainWindow 构造", True)
except Exception as e:
    traceback.print_exc()
    chk("主窗口", "MainWindow 构造", False, f"{type(e).__name__}: {e}")
    win = None

if win is not None:
    builders = win._nav_builders()
    for key, b in builders.items():
        try:
            win.go(b)
            app.processEvents()
            chk("导航页", f"_{key} 页面构建", True)
        except Exception as e:
            chk("导航页", f"_{key} 页面构建", False, f"{type(e).__name__}: {e}")

    # 详情页 / 演员详情页（用播种数据走通）
    try:
        row = db.search_media(limit=1, light=False)
        if row:
            win._open_media(row[0])
            app.processEvents()
            chk("详情页", "HeroView 打开", True)
        else:
            chk("详情页", "HeroView 打开", False, "无媒体行")
    except Exception as e:
        chk("详情页", "HeroView 打开", False, f"{type(e).__name__}: {e}")
    try:
        win._view_actor_detail(1)
        app.processEvents()
        chk("演员详情", "演员详情页构建", True)
    except Exception as e:
        chk("演员详情", "演员详情页构建", False, f"{type(e).__name__}: {e}")

    # 媒体库管理：新建一个库再删（配置层，不碰真实 settings）
    try:
        libs0 = len(win.s.libraries)
        win.s.libraries.append({"name": "_audit_lib", "kind": "电影", "paths": ["C:/tmp"], "filter": ""})
        win._build_sidebar()
        app.processEvents()
        has = any(l.get("name") == "_audit_lib" for l in win.s.libraries)
        chk("媒体库管理", "新增/重建侧栏", has)
        win.s.libraries = [l for l in win.s.libraries if l.get("name") != "_audit_lib"]
    except Exception as e:
        chk("媒体库管理", "新增/重建侧栏", False, f"{type(e).__name__}: {e}")

# ---------- 4) SettingsDialog：全部工具页构建 ----------
print("\n[4] SettingsDialog 构造并验证 11 个工具页…")
from ui_settings import SettingsDialog
try:
    dlg = SettingsDialog()
    dlg.show()
    app.processEvents()
    chk("工具窗", "SettingsDialog 构造（全部工具页）", True)
except Exception as e:
    traceback.print_exc()
    chk("工具窗", "SettingsDialog 构造（全部工具页）", False, f"{type(e).__name__}: {e}")
    dlg = None

if dlg is not None:
    # 工具页属性存在性
    for attr in ("_pg_personal", "_pg_manual", "_pg_insight", "_pg_scraper", "_pg_smart",
                 "_pg_tagopt", "_pg_service", "_pg_dedupe", "_pg_actorcheck",
                 "_pg_imagedetect", "_pg_data"):
        chk("工具页", attr.replace("_pg_", "") + " 构建", hasattr(dlg, attr) and getattr(dlg, attr) is not None)
    # 反馈 2 回归：标签优化 AI 按钮
    btn = getattr(dlg, "to_ai_btn", None)
    chk("反馈2回归", "标签优化 to_ai_btn", btn is not None and btn.objectName() == "Ghost")
    # 反馈 3 回归：演员检测 SpinBox 宽度
    pg_ac = getattr(dlg, "_pg_actorcheck", None)
    if pg_ac is not None:
        sp = getattr(pg_ac, "min_works", None)
        if sp is not None:
            import config as cfg
            chk("反馈3回归", "演员检测 min_works 宽>=131",
                sp.minimumWidth() >= cfg.SPIN_MIN_W, f"min={sp.minimumWidth()}")
        else:
            chk("反馈3回归", "演员检测 min_works", False, "无 min_works")
    dlg.close()

# ---------- 5) 汇总 ----------
n_ok = sum(1 for _, _, c, _ in results if c)
n_bad = sum(1 for _, _, c, _ in results if not c)
print("\n" + "=" * 70)
print(f"功能核查汇总：{n_ok} 通过 / {n_bad} 异常 / 共 {len(results)} 项")
print("=" * 70)
sys.exit(1 if n_bad else 0)
