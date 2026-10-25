# -*- coding: utf-8 -*-
"""v1.3.1 离线冒烟测试：导入全部模块 + 验证扫描(含裸视频) + 构建主窗口。"""
import os
import sys
import tempfile
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

# 离线渲染环境
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import scanner as scanner_mod
import config as cfg

# 使用临时数据库，避免清空真实索引（历史脚本会调用 clear_media）
_TMPDB = tempfile.mkdtemp(prefix="lmc_tmpdb_")
db.db_path = lambda: os.path.join(_TMPDB, "index_data", "media_center.db")

errors = []


def check(name, cond):
    print(("OK  " if cond else "FAIL") + " - " + name)
    if not cond:
        errors.append(name)


# 1) 导入 GUI 模块（确保无语法/导入错误）
try:
    from PySide6.QtWidgets import QApplication
    import ui_hero, ui_home, ui_settings, main_window
    check("import ui_hero/ui_home/ui_settings/main_window", True)
except Exception as e:
    check("import gui modules: " + repr(e), False)

# 2) 准备临时媒体库目录
tmp = tempfile.mkdtemp(prefix="lmc_smoke_")
try:
    # 电影(nfo 文件夹)
    mv = os.path.join(tmp, "Test Movie (2021) [1080p]")
    os.makedirs(mv)
    with open(os.path.join(mv, "movie.nfo"), "w", encoding="utf-8") as f:
        f.write('<movie><title>Test Movie</title><year>2021</year>'
                '<rating>8.1</rating><genre>Action</genre></movie>')
    # 伪造视频文件（实际不存在也可，scanner 仅 stat 大小；用真实空文件）
    with open(os.path.join(mv, "Test Movie (2021) [1080p].mkv"), "wb") as f:
        f.write(b"\x00" * 1024)

    # 裸视频文件（无 nfo）
    bare = os.path.join(tmp, "Bare Film 2019 2160p DoVi Atmos.mkv")
    with open(bare, "wb") as f:
        f.write(b"\x00" * 2048)

    # 剧集(nfo + season + episode nfo)
    tv = os.path.join(tmp, "Some Show")
    os.makedirs(os.path.join(tv, "Season 1"))
    with open(os.path.join(tv, "tvshow.nfo"), "w", encoding="utf-8") as f:
        f.write('<tvshow><title>Some Show</title><year>2020</year></tvshow>')
    with open(os.path.join(tv, "Season 1", "S01E01.nfo"), "w", encoding="utf-8") as f:
        f.write('<episodedetails><title>Pilot</title><season>1</season>'
                '<episode>1</episode></episodedetails>')
    with open(os.path.join(tv, "Season 1", "S01E01.mkv"), "wb") as f:
        f.write(b"\x00" * 512)

    # 3) 扫描（带命名库）
    db.init_db()
    db.clear_media()
    counts = scanner_mod.scan_library(tmp, None, library_name="测试库")
    print("counts:", counts)
    check("电影扫描>=1", counts["movie"] >= 1)
    check("剧集扫描>=1", counts["tvshow"] >= 1)
    check("分集扫描>=1", counts["episode"] >= 1)

    # 裸视频应被索引
    bare_row = db.search_media("Bare Film")
    check("裸视频被索引", any("Bare Film" in (m.get("title") or "") for m in bare_row))
    # 画质推断
    bm = next((m for m in bare_row if "Bare Film" in (m.get("title") or "")), None)
    if bm:
        print("bare quality:", bm.get("quality"), "year:", bm.get("year"))
        check("裸视频画质推断含4K", "4K" in (bm.get("quality") or ""))
        check("裸视频年份推断=2019", bm.get("year") == 2019)
        check("裸视频库名为命名库", bm.get("library") == "测试库")

    # 4) 去重：再次扫描不新增
    before = db.stats()
    scanner_mod.scan_library(tmp, None, library_name="测试库")
    after = db.stats()
    check("重复扫描不新增电影", before["movies"] == after["movies"])

    # 5) 配置层
    s = cfg.get_settings()
    s.set_nav_visible("banned", False)
    check("导航显隐持久化", s.nav_visible("banned") is False)
    s.set_nav_visible("banned", True)
    ok_lib = s.add_library("新库", "电影", [tmp])
    check("添加命名媒体库", ok_lib and "新库" in s.library_names())

    # 6) 构建主窗口（离线）
    app = QApplication.instance() or QApplication([])
    w = main_window.MainWindow()
    w.show()
    check("主窗口构建成功", w is not None)
    # 触发首页列表视图
    w.go(w._view_home)
    check("首页列表视图存在", w.stack.currentWidget() is not None)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n结果:", "全部通过" if not errors else ("失败: " + ", ".join(errors)))
sys.exit(1 if errors else 0)
