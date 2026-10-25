# -*- coding: utf-8 -*-
"""v1.9.0 离线冒烟测试：
- 需求1 首页布局/分栏位置持久化（列宽 / 排序 / 左表右详情分栏）
- 需求2 详情页「打分」改名「评分」+ 点击手动输入分数（保留清除）
- 需求3 单实例启动（关闭旧进程）+ 关闭即彻底退出（closeEvent）
- 需求4 数据源显示异常修复（点测试不再整行变红）+ 演员刮削页一屏无滚动
"""
import os
import sys
import tempfile
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import scanner as scanner_mod
import scraper as scraper_mod
import config as cfg
import nfo_parser as nfo_mod

errors = []


def check(name, cond, extra=""):
    print(("OK  " if cond else "FAIL") + " - " + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        errors.append(name)


# ---------------------------------------------------------------- 临时库 + 隔离配置
tmp = tempfile.mkdtemp(prefix="lmc_smoke9_")
db.db_path = lambda: os.path.join(tmp, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(tmp, "settings.json")   # 隔离，避免污染真实 settings.json
cfg._SETTINGS = None

try:
    from PySide6.QtWidgets import QApplication, QAbstractItemView
    import ui_home, ui_settings, ui_hero, main_window, main as app_main, version as ver
    check("import 全部模块", True)
except Exception as e:
    check("import modules: " + repr(e), False)

app = QApplication.instance() or QApplication([])
check("版本号为 v1.9.0", ver.VERSION == "v1.9.0", ver.FULL_VERSION)

NFO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie><title>TEST-999 用例</title><year>2024</year>
<actor><name>测试演员</name></actor></movie>"""
try:
    d = os.path.join(tmp, "TEST-999")
    os.makedirs(d)
    with open(os.path.join(d, "TEST-999.nfo"), "w", encoding="utf-8") as f:
        f.write(NFO)
    video = os.path.join(d, "TEST-999.mp4")
    with open(video, "wb") as f:
        f.write(b"\x00" * 2048)
    db.init_db()
    counts = scanner_mod.scan_library(tmp, None, library_name="测试库", mode="overwrite")
    check("测试媒体已入库", counts["movie"] >= 1)
    mid = db.media_id_by_path(video)
    check("媒体 id 可取", mid is not None)

    s = cfg.get_settings()

    # ------------------------------------------------------------ 需求1 首页布局/分栏持久化
    hv = ui_home.HomeListView()
    check("首页视图可构造", hv is not None)
    hv._sort(0)
    check("点击排序写入 home_sort", s.home_sort.get("key") == "title", s.home_sort)
    hdr = hv.table.horizontalHeader()
    hdr.resizeSection(0, 222)
    hv._commit_width()
    check("列宽写入 home_column_widths", s.home_column_widths.get("title") == 222, s.home_column_widths)
    # 分栏位置（离屏下控件无真实宽度，setSizes 会按比例缩放；校验「写入↔恢复」往返一致）
    hv.split.setSizes([640, 360])
    hv._commit_split()
    saved_split = list(s.home_split)
    check("分栏位置写入 home_split(往返一致)", saved_split == hv.split.sizes(), saved_split)
    hv2 = ui_home.HomeListView()
    check("新视图恢复列宽", hv2.table.horizontalHeader().sectionSize(0) == 222)
    check("新视图恢复排序列", hv2._sort_col == 0)
    check("新视图恢复分栏位置", hv2.split.sizes() == saved_split, (hv2.split.sizes(), saved_split))
    # 用户自定义后最后一列不再被拉伸污染
    check("自定义后关闭末列拉伸", not hv2.table.horizontalHeader().stretchLastSection())
    # 恢复默认（隔离库，无残留）
    s.set_home_column_widths({})
    s.set_home_split([])
    s.set_home_sort(None, True)

    # ------------------------------------------------------------ 需求2 评分 改名 + 手动输入
    db.set_user_rating(mid, 7.5)
    m = db.get_media(mid)
    hero = ui_hero.HeroView(m, on_open_actor=None, on_back=None)
    check("详情页按钮改名「评分」", hasattr(hero, "_rate_btn") and "评分" in hero._rate_btn.text(), hero._rate_btn.text())
    check("评分按钮不再显示「打分」", "打分" not in hero._rate_btn.text())
    rd = ui_hero.RateDialog(None, 7.5)
    check("评分对话框构造(初始值)", abs(rd.spin.value() - 7.5) < 1e-9)
    check("评分对话框为可输入spinbox(0-10,1位)",
          rd.spin.minimum() == 0.0 and rd.spin.maximum() == 10.0 and rd.spin.decimals() == 1)
    rd2 = ui_hero.RateDialog(None, None)
    check("评分对话框构造(无评分=0.0)", abs(rd2.spin.value()) < 1e-9)
    # nfo 写回链路仍可用
    NFO2 = '<?xml version="1.0" encoding="UTF-8"?>\n<movie><title>X</title><year>2020</year></movie>'
    np2 = os.path.join(tmp, "X.nfo")
    with open(np2, "w", encoding="utf-8") as f:
        f.write(NFO2)
    check("nfo 写回用户评分", nfo_mod.write_user_rating(np2, 8.5))
    check("nfo 读出用户评分", nfo_mod.parse_movie(np2).get("user_rating") == 8.5)
    check("nfo 清除用户评分", nfo_mod.write_user_rating(np2, None) and "<userrating" not in open(np2, encoding="utf-8").read())

    # ------------------------------------------------------------ 需求3 单实例 + 干净退出
    check("main 含单实例关闭逻辑", hasattr(app_main, "_kill_other_instances"))
    check("MainWindow 重写 closeEvent", hasattr(main_window.MainWindow, "closeEvent"))
    w = main_window.MainWindow()
    check("主窗口构造成功", w is not None)
    w.close()   # 触发 closeEvent（停后台定时器），验证不抛错
    check("closeEvent 执行无异常", True)

    # ------------------------------------------------------------ 需求4 数据源显示 + 一屏
    sd = ui_settings.SettingsDialog(None)
    sd.resize(1000, 900)   # 模拟 1080p 屏幕下的真实对话框尺寸
    check("数据源行存结果标签", len(sd._src_rows) == len(cfg.SCRAPER_SOURCES), len(sd._src_rows))
    check("数据源列表 NoSelection(点测试不变红)",
          sd.src_list.selectionMode() == QAbstractItemView.NoSelection,
          sd.src_list.selectionMode())
    real_test_src = scraper_mod.test_source
    scraper_mod.test_source = lambda *a, **k: {"ok": True, "msg": "命中(测试桩)", "ms": 1}
    sd._test_source("minnano")
    check("测试开始显示 测试中", sd._src_rows["minnano"].text() == "测试中…", sd._src_rows["minnano"].text())
    for _ in range(200):
        app.processEvents()
    scraper_mod.test_source = real_test_src
    check("测试结果回写(可用/不可用)", sd._src_rows["minnano"].text() in ("可用", "不可用"),
          sd._src_rows["minnano"].text())
    check("对话框尺寸已放大(>=760高)", sd.height() >= 760, sd.height())
    sd._show("演员刮削")
    page_h = sd._pg_scraper.sizeHint().height()
    avail_h = sd.height() - 60   # 减去标题/边距
    check("演员刮削页一屏无滚动", page_h <= avail_h, f"page_h={page_h} avail_h={avail_h}")
    sd.close()

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n结果:", "全部通过" if not errors else ("失败: " + ", ".join(errors)))
sys.exit(1 if errors else 0)
