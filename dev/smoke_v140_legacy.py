# -*- coding: utf-8 -*-
"""v1.4.0 离线冒烟测试：导入全部模块 + 扫描(裸视频/分集/本地图) + 列设置 + 库编辑 + 占位图。
扩展自 smoke_v131，新增：
- 首页列设置(写入/过滤非法键/恢复默认)
- 媒体库编辑(改名同步 DB + update_library)
- 标题清洗(剔除【】()/DoVi/HDR 等发行标签)
- 季目录裸视频按分集入库(而非顶层电影)
- 本地图片发现(poster/fanart 兜底)
- HeroView 无图占位不崩溃
"""
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


# 1) 导入 GUI 模块
try:
    from PySide6.QtWidgets import QApplication
    import ui_hero, ui_home, ui_settings, main_window
    import media_meta as mm
    check("import ui_hero/ui_home/ui_settings/main_window/media_meta", True)
except Exception as e:
    check("import gui modules: " + repr(e), False)

# 提前创建 QApplication（offscreen 下 QPixmap/QPainter 需 GUI 应用在前）
app = QApplication.instance() or QApplication([])

# 2) 占位图
try:
    pm = ui_hero.placeholder_pixmap(150, 225, text="影")
    check("placeholder_pixmap 返回非空图", not pm.isNull())
except Exception as e:
    check("placeholder_pixmap: " + repr(e), False)

# 3) 准备临时媒体库目录
tmp = tempfile.mkdtemp(prefix="lmc_smoke_")
tmp2 = tempfile.mkdtemp(prefix="lmc_smoke2_")
try:
    # 电影(nfo 文件夹) + 本地图兜底
    mv = os.path.join(tmp, "Test Movie (2021) [1080p]")
    os.makedirs(mv)
    with open(os.path.join(mv, "movie.nfo"), "w", encoding="utf-8") as f:
        f.write('<movie><title>Test Movie</title><year>2021</year>'
                '<rating>8.1</rating><genre>Action</genre></movie>')
    with open(os.path.join(mv, "Test Movie (2021) [1080p].mkv"), "wb") as f:
        f.write(b"\x00" * 1024)
    # 本地封面/背景兜底
    with open(os.path.join(mv, "poster.jpg"), "wb") as f:
        f.write(b"\xff\xd8\xff\xe0")  # 伪 JPEG 头，仅验证路径发现
    with open(os.path.join(mv, "fanart.jpg"), "wb") as f:
        f.write(b"\xff\xd8\xff\xe0")

    # 裸视频：含括号 + 发行标签，验证标题清洗
    bare = os.path.join(tmp, "【官方】My Film (2022) [BluRay] 1080p DoVi.mkv")
    with open(bare, "wb") as f:
        f.write(b"\x00" * 2048)

    # 剧集(nfo + season + episode nfo + 季目录裸视频)
    tv = os.path.join(tmp, "Some Show")
    os.makedirs(os.path.join(tv, "Season 1"))
    with open(os.path.join(tv, "tvshow.nfo"), "w", encoding="utf-8") as f:
        f.write('<tvshow><title>Some Show</title><year>2020</year></tvshow>')
    with open(os.path.join(tv, "Season 1", "S01E01.nfo"), "w", encoding="utf-8") as f:
        f.write('<episodedetails><title>Pilot</title><season>1</season>'
                '<episode>1</episode></episodedetails>')
    with open(os.path.join(tv, "Season 1", "S01E01.mkv"), "wb") as f:
        f.write(b"\x00" * 512)
    # 季目录下的裸视频(无同名 nfo) -> 应作为分集而非电影
    bare_ep = os.path.join(tv, "Season 1", "S01E05 Hidden Treasure.mkv")
    with open(bare_ep, "wb") as f:
        f.write(b"\x00" * 512)

    # 4) 扫描
    db.init_db()
    db.clear_media()
    counts = scanner_mod.scan_library(tmp, None, library_name="测试库")
    print("counts:", counts)
    check("电影扫描>=1", counts["movie"] >= 1)
    check("剧集扫描>=1", counts["tvshow"] >= 1)
    check("分集扫描>=1", counts["episode"] >= 1)

    # 裸视频标题清洗
    bare_row = db.search_media("My Film")
    bm = next((m for m in bare_row if "My Film" in (m.get("title") or "")), None)
    check("裸视频被索引", bm is not None)
    if bm:
        print("bare title:", bm.get("title"), "year:", bm.get("year"))
        check("标题剔除【】()/BluRay/DoVi", bm.get("title") == "My Film")
        check("年份推断=2022", bm.get("year") == 2022)
        check("画质推断含 1080P", "1080P" in (bm.get("quality") or ""))
        check("库名为命名库", bm.get("library") == "测试库")

    # 季目录裸视频按分集入库
    ep_row = db.search_media("Hidden Treasure")
    em = next((m for m in ep_row if "Hidden Treasure" in (m.get("title") or "")), None)
    check("季裸视频被索引为分集", em is not None and em.get("kind") == "episode")
    if em:
        check("分集带 parent_id", em.get("parent_id") is not None)
        check("分集季/集号识别", em.get("season") == 1 and em.get("episode") == 5)

    # 本地图片发现
    mv_row = db.search_media("Test Movie")
    mvm = next((m for m in mv_row if m.get("title") == "Test Movie"), None)
    check("电影 poster 由本地图兜底", bool(mvm and mvm.get("poster")))
    check("电影 fanart 由本地图兜底", bool(mvm and mvm.get("fanart")))

    # 5) 去重
    before = db.stats()
    scanner_mod.scan_library(tmp, None, library_name="测试库")
    after = db.stats()
    check("重复扫描不新增电影", before["movies"] == after["movies"])

    # 6) 首页列设置
    s = cfg.get_settings()
    s.set_home_columns(["title", "rating", "file_size"])
    check("首页列设置写入", s.home_columns == ["title", "rating", "file_size"])
    s.set_home_columns(["title", "not_a_key", "year"])
    check("非法列被过滤", "not_a_key" not in s.home_columns)
    s.set_home_columns(cfg.DEFAULT_HOME_COLUMNS)
    check("恢复默认列", s.home_columns == list(cfg.DEFAULT_HOME_COLUMNS))

    # 7) 媒体库编辑(改名同步 DB)
    s.add_library("旧库", "电影", [tmp2])
    # 在 tmp2 放一个裸视频并归属 旧库
    b2 = os.path.join(tmp2, "Lib Film 2023 1080p.mkv")
    with open(b2, "wb") as f:
        f.write(b"\x00" * 1024)
    scanner_mod.scan_library(tmp2, None, library_name="旧库")
    check("编辑前存在旧库", "旧库" in s.library_names())
    db.rename_library("旧库", "新库名")
    ok = s.update_library("旧库", "新库名", "剧集", [tmp2])
    check("媒体库编辑(update_library)成功", ok)
    check("改名后新名存在", "新库名" in s.library_names())
    check("改名后旧名消失", "旧库" not in s.library_names())
    synced = db.search_media(library="新库名")
    check("DB 媒体 library 同步改名", any(m.get("library") == "新库名" for m in synced))
    # 清理测试库
    s.remove_library("新库名")
    db.clear_media()

    # 8) 配置持久化(导航显隐) 注：v1.5.0 起 banned 已改为媒体库，改用 folders
    s.set_nav_visible("folders", False)
    check("导航显隐持久化", s.nav_visible("folders") is False)
    s.set_nav_visible("folders", True)

    # 9) 构建主窗口 + 首页视图(含动态列)
    app = QApplication.instance() or QApplication([])
    w = main_window.MainWindow()
    w.show()
    check("主窗口构建成功", w is not None)
    w.go(w._view_home)
    hl = w.stack.currentWidget()
    check("首页列表视图存在", hl is not None)
    if hl is not None:
        cols = getattr(hl, "_cols", [])
        check("首页列来自设置(home_columns)", len(cols) == len(s.home_columns))
        # 打开列设置对话框对象可构造
        dlg = ui_home.ColumnSettingsDialog(hl)
        check("列设置对话框可构造", dlg is not None)

    # 10) HeroView 无图占位不崩溃
    hv = ui_hero.HeroView({"title": "占位测试", "kind": "movie"})
    check("HeroView 无 poster/fanart 不崩溃", hv is not None)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(tmp2, ignore_errors=True)

print("\n结果:", "全部通过" if not errors else ("失败: " + ", ".join(errors)))
sys.exit(1 if errors else 0)
