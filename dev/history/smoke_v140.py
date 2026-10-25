# -*- coding: utf-8 -*-
"""v1.14.0 离线冒烟：覆盖「海量数据性能 + 筛选排序 + 展示优化」8 条反馈。

全部使用临时数据库 + 临时 settings.json，绝不触碰真实索引 / 配置。
运行：python -u -c "import runpy; runpy.run_path(r'<本文件>', run_name='__main__')"

注：本文件名原先属于 v1.4.0 时代的旧冒烟，已改名为 dev/smoke_v140_legacy.py。
"""
import os
import sys
import time
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import (QApplication, QPushButton, QLabel, QMessageBox)
from PySide6.QtGui import QFontDatabase

TMP = tempfile.mkdtemp(prefix="lmc_smoke140_")
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

_LOG_TMP = os.path.join(TMP, "logs")
os.makedirs(_LOG_TMP, exist_ok=True)
applog.log_dir = lambda: _LOG_TMP

from main_window import (MainWindow, load_style, LazyGrid, FilterSortBar)
import ui_settings as us

ERRORS = []


def check(ok, msg, extra=None):
    line = ("OK   - " if ok else "FAIL - ") + msg + (f"   {extra}" if extra is not None else "")
    print(line, flush=True)
    if not ok:
        ERRORS.append(msg)


def pump(cond, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def pump_ms(ms=120):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()
        time.sleep(0.01)


# ---------------------------------------------------------------- 准备数据（1500 条，模拟海量）
db.init_db()
cfg.get_settings().save()
load_style(app)

N_BIG = 1500
lib_dir = os.path.join(TMP, "LibBig")
os.makedirs(lib_dir, exist_ok=True)
t0 = time.time()
for i in range(N_BIG):
    db.upsert_media_by_path(
        mode="overwrite", title=f"影片 {i:04d}", sort_title=f"{i:04d}", kind="movie",
        file_path=os.path.join(lib_dir, f"v{i}.mkv"), library="大库",
        year=1990 + (i % 35), rating=(i % 100) / 10.0,
        user_rating=(i % 10) if i % 3 == 0 else None,
        favorite=1 if i % 4 == 0 else 0,
        quality="4K" if i % 5 == 0 else "1080P",
        runtime="01:40:00", file_size=1_000_000 + i,
        added_date="2026-09-19 00:00:00", plot="简介" * 100)
print(f"[准备] 写入 {N_BIG} 条用时 {time.time() - t0:.2f}s", flush=True)

db.upsert_media_by_path(mode="overwrite", title="小库片", sort_title="x", kind="movie",
                        file_path=os.path.join(TMP, "small.mkv"), library="小库",
                        year=2020, favorite=1)

s = cfg.get_settings()
s.add_library("大库", "电影", [lib_dir])
s.add_library("小库", "电影", [TMP])
s.save()
cfg._SETTINGS = None
s = cfg.get_settings()

win = MainWindow()
win.resize(1600, 900)
win.show()
app.processEvents()

# ================================================================ 1) 版本
check(ver.VERSION == "v1.14.0", "版本号为 v1.14.0", ver.FULL_VERSION)

# ================================================================ 反馈 8：数据层深度优化
conn = db.get_conn()
check(str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal",
      "数据库启用 WAL（读写不再互相阻塞）")
check(conn is db.get_conn(), "连接按线程复用（不再每次 connect/close）")
idx = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
need = {"idx_media_library", "idx_media_favorite", "idx_media_year", "idx_media_userrating",
        "idx_media_added_time", "idx_mp_person", "idx_mp_media", "idx_people_role"}
check(need <= idx, "筛选/排序/关联所需索引齐备", sorted(need - idx) or "全部存在")

t0 = time.time()
total_all = db.count_media()
count_sec = time.time() - t0
check(total_all == N_BIG + 1, "count_media 总数正确", total_all)
check(count_sec < 1.0, "count_media 在 1500 条下 < 1s", f"{count_sec * 1000:.0f}ms")

t0 = time.time()
first_page = db.search_media(limit=60, offset=0, light=True)
page_sec = time.time() - t0
check(len(first_page) == 60, "分页取 60 条", len(first_page))
check(page_sec < 0.5, "单页查询 < 0.5s", f"{page_sec * 1000:.0f}ms")
check("plot" not in first_page[0], "light 投影不取 plot 大字段（省内存）")
check("plot" in db.search_media(limit=1)[0], "详情仍可拿到 plot")

asc = db.search_media(limit=1000, sort="year", asc=True, light=True)
check([x["year"] for x in asc] == sorted(x["year"] for x in asc), "按年份升序排序正确")
check(db.count_media(favorite=True) == 376, "筛选「已收藏」计数正确", db.count_media(favorite=True))
check(db.count_media(min_user_rating=5) == len([i for i in range(N_BIG) if i % 3 == 0 and (i % 10) >= 5]),
      "筛选「用户评分≥5」计数正确", db.count_media(min_user_rating=5))
check(db.count_media(quality="4K") == len([i for i in range(N_BIG) if i % 5 == 0]),
      "筛选「画质 4K」计数正确", db.count_media(quality="4K"))
check(len(db.search_media(favorite=True, limit=10)) == min(10, db.count_media(favorite=True)),
      "筛选与分页口径一致")

one_id = first_page[0]["id"]
scoped = db.cast_crew_map([one_id])
check(set(scoped) <= {one_id}, "cast_crew_map(ids) 只返回请求的 id", sorted(scoped))
check(len(db.cast_crew_map()) >= len(scoped), "全量模式仍可用（向后兼容）")

# ================================================================ 反馈 1 / 3：读取进度 + 分批载入
t0 = time.time()
page = win._wall_page("大库", {"library": "大库"})
build_sec = time.time() - t0
grid = page.findChild(LazyGrid)
check(grid is not None, "媒体库页用增量网格 LazyGrid 承载")
check(build_sec < 1.0, "打开 1500 条的库，页面构建 < 1s（不再同步建全部卡片）",
      f"{build_sec * 1000:.0f}ms")
check(grid._total == N_BIG, "网格总数 = 该库影片数", grid._total)
check(grid.count_lbl.text() != "", "顶部有读取状态文字", grid.count_lbl.text())

pump_ms(150)
first_loaded = grid._loaded
check(0 < first_loaded < grid._total, "首屏只渲染一部分卡片（其余按需加载）",
      f"{first_loaded}/{grid._total}")
check("已加载" in grid.count_lbl.text() or "已全部载入" in grid.count_lbl.text(),
      "进度文字显示已加载/总数", grid.count_lbl.text())
check(grid.bar.maximum() == 100, "进度条按百分比显示", grid.bar.value())

pump(lambda: grid._loaded >= grid._total)
check(grid._loaded == grid._total, "自动续载可把结果全部载入", grid._loaded)
check("已全部载入" in grid.count_lbl.text(), "载入完成后提示已全部载入", grid.count_lbl.text())
check(grid.bar.value() == 100, "载入完成后进度 100%")
check(grid._grid.itemAtPosition(0, 7) is not None and grid._grid.itemAtPosition(0, 8) is None,
      "影片墙仍为每行 8 个")
check(grid.batch <= 200, "每批渲染量受控（不会一次建上千控件）", grid.batch)

# ================================================================ 反馈 2：库名后显示影片总数
app.processEvents()
btn = win._lib_btns.get("大库")
check(btn is not None, "侧边栏有「大库」按钮")
check(btn is not None and f"（{N_BIG}）" in btn.text(), "侧边栏库名后显示影片总数",
      btn.text() if btn else None)
btn_small = win._lib_btns.get("小库")
check(btn_small is not None and "（1）" in btn_small.text(), "小库计数正确",
      btn_small.text() if btn_small else None)

lib_view = win._lib_view(s.library("大库"))
h1 = [l.text() for l in lib_view.findChildren(QLabel) if l.text().startswith("大库")]
check(any(f"（{N_BIG} 部）" in t for t in h1), "媒体库页标题显示总数", h1[:3])

counts = db.library_counts()
check(counts.get("大库") == N_BIG and counts.get("小库") == 1, "library_counts 一次分组统计", counts)

folders = win._view_folders()
texts = [b.text() for b in folders.findChildren(QPushButton)]
check(any(f"（{N_BIG} 项）" in t for t in texts), "文件夹页按钮显示项数", texts[:3])

# ================================================================ 反馈 4：影片墙筛选 + 排序
bar = FilterSortBar("media")
fired = []
bar.changed.connect(lambda: fired.append(1))
sort_keys = [k for k, _l, _e in bar._sorts]
label_of = {k: l for k, l, _e in bar._sorts}
for k in ("sort_title", "kind", "added_time", "premiere", "rating"):
    check(k in sort_keys, f"排序菜单含「{label_of.get(k, k)}」")
check("year" in sort_keys and "user_rating" in sort_keys, "排序菜单含年份/用户评分")
check("↑" in bar.sort_btn.text() or "↓" in bar.sort_btn.text(), "排序按钮显示升降序",
      bar.sort_btn.text())
bar._set_sort("year", False)
check(bar.sort() == "year" and bar.asc() is False, "点选排序后状态更新", bar.sort_btn.text())
check(len(fired) >= 1, "排序变更会通知页面重载")

combo, options = bar._combos["favorite"]
combo.setCurrentIndex([t for t, _v in options].index("已收藏"))
check(bar.filters() == {"favorite": True}, "筛选「已收藏」映射成查询条件", bar.filters())
combo2, opt2 = bar._combos["urating"]
combo2.setCurrentIndex([t for t, _v in opt2].index("≥ 7 分"))
check(bar.filters() == {"favorite": True, "min_user_rating": 7}, "多个筛选条件可叠加", bar.filters())
bar._reset()
check(bar.filters() == {}, "「重置」清空筛选")

cfg.get_settings().set_wall_prefs("sort_title", True, {"favorite": True})
cfg._SETTINGS = None
s2 = cfg.get_settings()
check(s2.wall_prefs["filters"] == {"favorite": True}, "筛选偏好落盘", s2.wall_prefs)
page_fav = win._wall_page("大库", {"library": "大库"})
grid_fav = page_fav.findChild(LazyGrid)
check(grid_fav._total == db.count_media(library="大库", favorite=True),
      "应用筛选后页面总数 = 筛选后的条数", grid_fav._total)
check(db.count_media(library="大库") == N_BIG, "基础条件（媒体库）仍生效，不被筛选条改写")

s2.set_wall_prefs("rating", False, {"quality": "4K"})
cfg._SETTINGS = None
s3 = cfg.get_settings()
check(s3.wall_prefs["sort"] == "rating" and s3.wall_prefs["asc"] is False
      and s3.wall_prefs["filters"] == {"quality": "4K"}, "筛选排序偏好可往返持久化", s3.wall_prefs)

# ================================================================ 反馈 5：演员库筛选 + 排序
for i in range(40):
    pid = db.upsert_person(f"演员{i:02d}")
    db.update_person(pid, only_missing=False,
                     birthday=f"19{70 + i % 30}-01-01",
                     photo_path=(os.path.join(TMP, f"p{i}.jpg") if i % 2 == 0 else ""),
                     meta='{"身高": "160cm"}')
    db.link_media_person(i + 1, pid, "", 0)
for i in range(6):
    db.upsert_person(f"导演{i}", role_type="Director")

abar = FilterSortBar("actor")
akeys = [k for k, _l, _e in abar._sorts]
check({"works", "name", "birthday", "last_year"} <= set(akeys),
      "演员排序含 作品数/姓名/生日/最新作品", akeys)
aspecs = {k for k, _l, _o in abar._specs}
check(aspecs == {"favorite", "pinned", "status", "photo"}, "演员筛选维度 = 收藏/置顶/状态/头像",
      sorted(aspecs))
acombo, aopt = abar._combos["photo"]
acombo.setCurrentIndex([t for t, _v in aopt].index("无头像"))
check(abar.filters() == {"has_photo": False}, "演员筛选映射成查询条件", abar.filters())
abar._reset()
check(abar.filters() == {}, "演员筛选可重置")

check(db.count_people() == 40, "演员库总数（仅 Actor）", db.count_people())
check(db.count_people(has_photo=True) == 20, "按有无头像筛选", db.count_people(has_photo=True))
people_asc = db.query_people(sort="name", asc=True, limit=5)
check([p["name"] for p in people_asc] == sorted(p["name"] for p in people_asc),
      "按姓名升序查询正确", [p["name"] for p in people_asc])
check(db.query_people(sort="birthday", asc=True, limit=1)[0].get("birthday"),
      "按生日排序可用")

actor_page = win._view_actors()
pump_ms(120)
agrid = actor_page.findChild(LazyGrid)
check(agrid is not None and agrid._total == 40, "演员库也用增量网格",
      agrid._total if agrid else None)
check(agrid is not None and agrid._cols == 5, "演员库每行 5 个")

cfg.get_settings().set_actor_prefs("birthday", True, {"has_photo": True})
cfg._SETTINGS = None
s4 = cfg.get_settings()
check(s4.actor_prefs["sort"] == "birthday" and s4.actor_prefs["filters"] == {"has_photo": True},
      "演员筛选排序偏好落盘", s4.actor_prefs)

# ================================================================ 反馈 6：设置里媒体库行高
sd = us.SettingsDialog(win)
sd.resize(1080, 800)
sd.show()
pump_ms(150)
row_h = sd.lib_list.sizeHintForRow(0)
check(row_h == us.LIB_ROW_H, "媒体库列表行高 = 设定常量", f"{row_h} vs {us.LIB_ROW_H}")
row0 = sd.lib_list.itemWidget(sd.lib_list.item(0))
btns = row0.findChildren(QPushButton) if row0 else []
check(len(btns) >= 3, "每行有 编辑/扫描/删除 三个按钮", [b.text() for b in btns])
if btns:
    bh = max(b.height() for b in btns)
    check(row_h >= bh + 8, "行高足够容纳按钮（按钮不再被裁）", f"行高{row_h} 按钮{bh}")
    check(all(b.height() >= 28 for b in btns), "按钮高度固定，字形完整",
          [b.height() for b in btns])
n_lib = len(sd.s.libraries)
check(sd.lib_list.height() == min(n_lib, 4) * us.LIB_ROW_H + 10,
      "列表高度随条目数自适应", f"{sd.lib_list.height()} n={n_lib}")

# ================================================================ 反馈 7：设置不阻塞主体
win._open_settings()
pump_ms(150)
dlg = win._settings_dlg
check(dlg is not None and dlg.isVisible(), "点「设置」会打开设置窗口")
check(dlg is not None and dlg.isModal() is False, "设置窗口是**非模态**的（主界面仍可操作）")
win._open_settings()
check(win._settings_dlg is dlg, "重复点「设置」不重复开窗，只把已开的抬到前面")

before = [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()]
dlg._on_scan_done({"movie": 3, "tvshow": 1, "episode": 0}, "大库")
pump_ms(80)
after = [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()]
check(len(before) == 0 and len(after) == 0, "扫描完成不弹模态对话框（改为状态栏文字）", len(after))
check("扫描完成" in dlg.lib_status.text(), "扫描结果就地显示在设置页", dlg.lib_status.text())
check(dlg.isModal() is False, "扫描期间设置窗口也未变模态")
check(win.isVisible(), "主窗口始终可用")

win.close()
pump_ms(100)
check(not dlg.isVisible(), "关闭主窗口时设置窗口一并关闭")

# ================================================================ 收尾
db.close_all()
if ERRORS:
    print(f"\n==== 失败 {len(ERRORS)} 项: {ERRORS} ====", flush=True)
else:
    print("\n==== 全部通过 ====", flush=True)
sys.exit(1 if ERRORS else 0)
