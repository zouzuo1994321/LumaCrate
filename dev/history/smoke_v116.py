# -*- coding: utf-8 -*-
"""v1.16.0 离线冒烟：覆盖三条反馈。

反馈 1（强化筛选）：多维 chip 面板 FacetBar 能构造；每个新筛选维度
  （ident / progress / genre_other / country_other / has_collection）经 _media_where
  下推到 SQL 层，计数与列表口径一致。
反馈 2（随机排序 + 刷新）：search_media(sort="random") 用「会话种子伪随机置换」，
  分页（offset/limit）不重复、不漏项；db.reshuffle() 换种子后顺序改变；
  LazyGrid.refresh_btn 仅在 random 模式下可见（点「刷新一下」重洗牌）。
反馈 3（文件夹显示子目录）：_view_folders 会读出媒体库 paths 并逐条列出。

全部使用临时库 + 临时 settings.json，绝不触碰真实索引 / 配置。
运行：python -u -c "import runpy; runpy.run_path(r'<本文件>', run_name='__main__')"
"""
import os
import sys
import time
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import (QApplication, QLabel)
from PySide6.QtGui import QFontDatabase

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v116_")
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

from main_window import (MainWindow, load_style, LazyGrid, FacetBar)

ERRORS = []


def check(ok, msg, extra=None):
    line = ("OK   - " if ok else "FAIL - ") + msg + (f"   {extra}" if extra is not None else "")
    print(line, flush=True)
    if not ok:
        ERRORS.append(msg)


def pump_ms(ms=120):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()


# ---------------------------------------------------------------- 准备
db.init_db()
cfg.get_settings().save()
load_style(app)

check(ver.VERSION == "v1.16.0", "版本号为 v1.16.0", ver.FULL_VERSION)

# ================================================================ 反馈 1：每个筛选维度的数据准备
# 一行一个 tuple：(nfo_path, tmdb_id, year, quality, play_count, genres, country, collection)
# 各维度互不重叠，便于用 Python 镜像 SQL 的筛选意图来核对计数。
FL_ROWS = [
    ("nfo", "", 2020, "", 0, "剧情", "美国", ""),       # ident=nfo, 未观看
    ("", "tmdb123", 0, "", 5, "喜剧", "日本", "合集A"),   # ident=tmdb, 已观看, 有合集
    ("", "", 2021, "4K", 0, "实验", "巴西", ""),        # ident=smart, 风格其他, 地区其他
    ("", "", 0, "", 0, "", "", ""),                      # ident=none
    ("nfo", "", 0, "", 2, "西部", "法国", ""),           # ident=nfo, 已观看
]
FL_DIR = os.path.join(TMP, "FL")
os.makedirs(FL_DIR, exist_ok=True)
for i, (nfo, tmdb, year, qual, play, genres, country, coll) in enumerate(FL_ROWS):
    db.upsert_media_by_path(
        mode="overwrite", title=f"FL片{i}", sort_title=f"FL{i}", kind="movie",
        file_path=os.path.join(FL_DIR, f"fl{i}.mkv"), library="FL",
        nfo_path=(os.path.join(FL_DIR, f"fl{i}.nfo") if nfo else ""),
        tmdb_id=tmdb or None, year=year or None, quality=qual or "",
        play_count=play, genres=genres, country=country, collection=coll)

# Python 镜像：按 SQL 的判定意图算期望计数
def exp_ident(rows, kind):
    if kind == "nfo":
        return sum(1 for r in rows if r[0])
    if kind == "tmdb":
        return sum(1 for r in rows if r[1])
    if kind == "smart":
        return sum(1 for r in rows if not r[0] and (r[2] or r[3]))
    if kind == "none":
        return sum(1 for r in rows if not r[0] and not r[2] and not r[3])
    return 0

check(db.count_media(library="FL", ident="nfo") == exp_ident(FL_ROWS, "nfo"),
      "ident=nfo 计数正确", db.count_media(library="FL", ident="nfo"))
check(db.count_media(library="FL", ident="tmdb") == exp_ident(FL_ROWS, "tmdb"),
      "ident=tmdb 计数正确", db.count_media(library="FL", ident="tmdb"))
check(db.count_media(library="FL", ident="smart") == exp_ident(FL_ROWS, "smart"),
      "ident=smart 计数正确", db.count_media(library="FL", ident="smart"))
check(db.count_media(library="FL", ident="none") == exp_ident(FL_ROWS, "none"),
      "ident=none 计数正确", db.count_media(library="FL", ident="none"))

check(db.count_media(library="FL", progress="watched") == sum(1 for r in FL_ROWS if r[4] > 0),
      "progress=watched 计数正确", db.count_media(library="FL", progress="watched"))
check(db.count_media(library="FL", progress="unwatched") == sum(1 for r in FL_ROWS if r[4] == 0),
      "progress=unwatched 计数正确", db.count_media(library="FL", progress="unwatched"))

# 「其他」＝不含任一已知风格/地区（空字符串也自然落入「其他」，与 SQL 语义一致）。
GENRE_FACETS = db.GENRE_FACETS
COUNTRY_FACETS = db.COUNTRY_FACETS
exp_genre_other = sum(1 for r in FL_ROWS if not any(g in (r[5] or "") for g in GENRE_FACETS))
exp_country_other = sum(1 for r in FL_ROWS if not any(c in (r[6] or "") for c in COUNTRY_FACETS))
check(db.count_media(library="FL", genre_other=True) == exp_genre_other,
      "genre_other 计数正确", db.count_media(library="FL", genre_other=True))
check(db.count_media(library="FL", country_other=True) == exp_country_other,
      "country_other 计数正确", db.count_media(library="FL", country_other=True))

check(db.count_media(library="FL", has_collection=True) == sum(1 for r in FL_ROWS if r[7]),
      "has_collection=True 计数正确", db.count_media(library="FL", has_collection=True))
check(db.count_media(library="FL", has_collection=False) == sum(1 for r in FL_ROWS if not r[7]),
      "has_collection=False 计数正确", db.count_media(library="FL", has_collection=False))

# 已知风格 / 地区 仍可用
check(db.count_media(library="FL", genre="剧情") == 1, "已知风格 genre=剧情 计数正确")
check(db.count_media(library="FL", country="美国") == 1, "已知地区 country=美国 计数正确")

# 维度可叠加：ident=nfo 且 未观看 → 仅 FL片0
check(db.count_media(library="FL", ident="nfo", progress="unwatched") == 1,
      "多维度叠加 (ident=nfo & progress=unwatched) 计数正确")
rows_comb = db.search_media(library="FL", ident="nfo", progress="unwatched", limit=10)
check(len(rows_comb) == 1 and "FL片0" in (rows_comb[0].get("title") or ""),
      "叠加筛选的列表结果正确", [r.get("title") for r in rows_comb])

# 列表与计数口径一致
tot_fl = db.count_media(library="FL")
check(len(db.search_media(library="FL", limit=100)) == tot_fl,
      "FL 列表与计数口径一致", f"{len(db.search_media(library='FL', limit=100))}/{tot_fl}")

# ================================================================ 反馈 2：随机排序分页不重复 + reshuffle 改变顺序
BIG = 480
BIG_DIR = os.path.join(TMP, "Big")
os.makedirs(BIG_DIR, exist_ok=True)
t0 = time.time()
for i in range(BIG):
    db.upsert_media_by_path(
        mode="overwrite", title=f"影片{i:04d}", sort_title=f"{i:04d}", kind="movie",
        file_path=os.path.join(BIG_DIR, f"v{i}.mkv"), library="Big",
        year=1990 + (i % 35), user_rating=(i % 10) if i % 3 == 0 else None,
        favorite=1 if i % 4 == 0 else 0, quality="4K" if i % 5 == 0 else "1080P",
        play_count=i % 7, genres="剧情", country="美国")
print(f"[准备] 写入 Big {BIG} 条用时 {time.time() - t0:.2f}s", flush=True)

big_total = db.count_media(library="Big")
check(big_total == BIG, "Big 库总数正确", big_total)

# 分页翻完所有页，收集全部 id，必须无重复且覆盖全集
seen = []
for off in range(0, BIG, 60):
    page = db.search_media(library="Big", sort="random", top_only=True,
                           limit=60, offset=off, light=True)
    seen.extend(r["id"] for r in page)
check(len(seen) == len(set(seen)), "随机排序分页无重复 id",
      f"去重后 {len(set(seen))}/{len(seen)}")
check(len(seen) == BIG, "随机排序分页覆盖全部条目（不漏项）", f"{len(seen)}/{BIG}")
check(len(set(seen)) == BIG, "随机排序是全排列（无重复无遗漏）")

# reshuffle 改变顺序
order_before = [r["id"] for r in db.search_media(library="Big", sort="random",
                                                 top_only=True, limit=BIG, light=True)]
seed_before = db._RANDOM_SEED
new_seed = db.reshuffle()
check(new_seed != seed_before, "reshuffle 更换了会话种子", f"{seed_before}->{new_seed}")
order_after = [r["id"] for r in db.search_media(library="Big", sort="random",
                                                top_only=True, limit=BIG, light=True)]
check(set(order_before) == set(order_after), "reshuffle 不改变数据集（只是重排）")
check(order_before != order_after, "reshuffle 后顺序确实改变",
      f"首元素 {order_before[0]} -> {order_after[0]}")

# ================================================================ 反馈 2：GUI —— 刷新按钮仅随机模式可见
bar = FacetBar()
check(isinstance(bar, FacetBar), "FacetBar 能构造")
check(bar.sort() == "sort_title", "FacetBar 默认排序=名称")
bar_rand = FacetBar(sort="random", asc=True, filters={})
check(bar_rand.sort() == "random", "FacetBar 可初始化为 random 排序")

def dummy_fetch(off, lim):
    return [{"id": off + i, "title": f"x{i}"} for i in range(min(lim, 10 - off))]

def dummy_card(item):
    return QLabel(str(item.get("id")))

grid_rand = LazyGrid(dummy_fetch, dummy_card, total=10, kind="media",
                     refreshable=True)
grid_rand.show(); app.processEvents()
check(grid_rand.refresh_btn.isVisible() is True, "random 模式 LazyGrid 「刷新一下」按钮可见")
grid_norm = LazyGrid(dummy_fetch, dummy_card, total=10, kind="media",
                     refreshable=False)
grid_norm.show(); app.processEvents()
check(grid_norm.refresh_btn.isVisible() is False, "普通排序 LazyGrid 「刷新一下」按钮隐藏")

# 真实页面：wall_prefs sort=random → 内嵌栅格的刷新按钮可见
win = MainWindow()
win.resize(1600, 900)
app.processEvents()
cfg.get_settings().set_wall_prefs("random", True, {})
cfg._SETTINGS = None
page_rand = win._wall_page("Big", {"library": "Big"})
page_rand.show(); app.processEvents()
g_rand = page_rand.findChild(LazyGrid)
check(g_rand is not None and g_rand.refresh_btn.isVisible() is True,
      "影片墙(random) 内嵌栅格刷新按钮可见")
cfg.get_settings().set_wall_prefs("sort_title", True, {})
cfg._SETTINGS = None
page_norm = win._wall_page("Big", {"library": "Big"})
page_norm.show(); app.processEvents()
g_norm = page_norm.findChild(LazyGrid)
check(g_norm is not None and g_norm.refresh_btn.isVisible() is False,
      "影片墙(名称排序) 内嵌栅格刷新按钮隐藏")

# ================================================================ 反馈 3：文件夹显示子目录
s = cfg.get_settings()
s.add_library("FL", "电影", [FL_DIR])
s.add_library("Big", "电影", [BIG_DIR])
s.save()
cfg._SETTINGS = None
folders = win._view_folders()
labels = [l.text() for l in folders.findChildren(QLabel)]
check(any(FL_DIR in t for t in labels), "文件夹页列出媒体库 FL 的子目录路径",
      [t for t in labels if "FL" in t][:2])
check(any(BIG_DIR in t for t in labels), "文件夹页列出媒体库 Big 的子目录路径")

# ================================================================ 收尾
db.close_all()
win.close()
if ERRORS:
    print(f"\n==== 失败 {len(ERRORS)} 项: {ERRORS} ====", flush=True)
else:
    print("\n==== 全部通过 ====", flush=True)
sys.exit(1 if ERRORS else 0)
