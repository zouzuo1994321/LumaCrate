# -*- coding: utf-8 -*-
"""v1.21.1 离屏冒烟：4 项反馈修复回归。

  反馈 1：minnano-av 测连 HTTP 500 —— 缺系统代理 + 请求头不像浏览器（WAF 拦）。
  反馈 2：「修复历史资料」重刮后数量不下降 —— 覆盖模式没清掉 v1.10.0 残留样板垃圾。
  反馈 3：切换/翻页时弹出只有「加载更多」的浮动小窗 —— 无父 more_btn 变顶层窗。
  反馈 4：首页详情页改收藏/评分后左表不实时刷新 —— HomeListView 没接 on_changed。
"""
import os
import sys
import json
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QLabel, QWidget

app = QApplication(sys.argv)

import database as db
import scanner as scanner_mod
import scraper as scraper_mod
from main_window import MainWindow, LazyGrid, load_style
from ui_home import HomeListView
from ui_hero import HeroView
from version import VERSION, BUILD

_TMPDB = tempfile.mkdtemp(prefix="lmc_tmpdb_")
db.db_path = lambda: os.path.join(_TMPDB, "index_data", "media_center.db")
_TMPMEDIA = tempfile.mkdtemp(prefix="lmc_v1211_")

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (("  -> " + extra) if extra else ""))

# ---------- 基础数据 ----------
db.init_db()
db.clear_media()

md = os.path.join(_TMPMEDIA, "La.La.Land.2016")
os.makedirs(md, exist_ok=True)
open(os.path.join(md, "poster.jpg"), "w").write("x")
open(os.path.join(md, "movie.nfo"), "w", encoding="utf-8").write("""<?xml version="1.0"?>
<movie><title>乐来越爱你</title><year>2016</year><runtime>128</runtime>
<country>美国</country><rating>7.9</rating><genre>喜剧</genre>
<actor><name>Emma Stone</name><role>Mia</role><type>Actor</type></actor>
<actor><name>Ryan Gosling</name><role>Sebastian</role><type>Actor</type></actor>
</movie>""")
open(os.path.join(md, "movie.mkv"), "w").write("x" * 5000)
scanner_mod.scan_library(_TMPMEDIA)
print("VERSION:", VERSION, BUILD)

# ============ 反馈 1：系统代理 + 浏览器头 ============
h = scraper_mod._browser_headers()
for k in ("Sec-Fetch-Site", "Sec-Fetch-Mode", "Sec-Fetch-User", "Sec-CH-UA",
          "Upgrade-Insecure-Requests"):
    check(f"反馈1 请求头含 {k}", k in h, h.get(k, ""))
# 系统代理读取不报错（沙箱里通常为空串，但函数必须可用）
try:
    px = scraper_mod._system_proxy()
    check("反馈1 _system_proxy 可调用", isinstance(px, str), repr(px))
except Exception as e:
    check("反馈1 _system_proxy 可调用", False, repr(e))

# ============ 反馈 2：覆盖模式清空 junk meta/bio ============
ppl = db.query_people(role_type="Actor", limit=20)
check("反馈2 存在待测演员", len(ppl) > 0, f"{len(ppl)} 位")
pid = ppl[0]["id"]
conn = db.get_conn()
conn.execute("UPDATE people SET meta=?, bio=?, birthday=?, source_url=? WHERE id=?",
             ("og:description 掲載します", "無料動画 情報交換", "1990-01-01",
              "http://example.com/x", pid))
conn.commit()
conn.close()
check("反馈2 _is_junk 识别样板", db._is_junk("og:description 掲載"))
check("反馈2 _is_junk 放行正常文案", not db._is_junk("这是一段正常的演员简介。"))
before = db.count_needing_repair()
n = db.update_person(pid, only_missing=False)        # 覆盖模式、未给 meta/bio
row = db.get_person(pid)
check("反馈2 覆盖清空 junk meta", row.get("meta") == "", repr(row.get("meta")))
check("反馈2 覆盖清空 junk bio", row.get("bio") == "", repr(row.get("bio")))
after = db.count_needing_repair()
check("反馈2 修复计数下降", after < before, f"{before} -> {after}")

# ============ 反馈 2 续（v1.21.2）：缺生日 / 干净资料不算待修复 ============
# 用户真机库「还是 14」的根因：14 人全是「干净资料 + 生日空 + 源=minnano」，
# minnano 不提供生日，重刮补不回来；v1.21.1 的 _repair_where 仍用 birthday=''
# 判定 → 计数永远降不下来。修复：修复集只认 v1.10.0 样板垃圾。
conn = db.get_conn()
conn.execute("""INSERT INTO people (name, role_type, source_url, scraped_at, meta, bio, birthday)
                VALUES (?,?,?,?,?,?,?)""",
             ("诊断测试人_干净", "Actor", "http://example.com/clean",
              "2026-01-01 00:00:00",
              json.dumps({"身高": "160cm"}), "身高 160cm ｜ 三围 B80/W60/H85", ""))
conn.commit()
cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
conn.close()
check("反馈2续 干净资料+生日空 不计入修复", db.count_needing_repair() == 0,
      f"count={db.count_needing_repair()}")
# 同一个人写入 junk → 应计入
conn = db.get_conn()
conn.execute("UPDATE people SET meta=? WHERE id=?", ("og:description 掲載します", cid))
conn.commit(); conn.close()
check("反馈2续 junk 命中即计入", db.count_needing_repair() == 1,
      f"count={db.count_needing_repair()}")
# 跑一次覆盖重刮（writer 清 junk），计数应归 0
def _fake_writer(pid, fields, only_missing):
    db.update_person(pid, only_missing=only_missing, **fields)
stats = scraper_mod.scrape_many(
    [db.get_person(cid)],
    {"overwrite": True, "sources": [], "download_photo": False,
     "fill_alias": False, "fill_birthday": False, "fill_bio": False},
    writer=_fake_writer)
check("反馈2续 重刮后 junk 清零→计数归0", db.count_needing_repair() == 0,
      f"after={db.count_needing_repair()} ok={stats.get('ok')} notfound={stats.get('notfound')}")
# 顺带验证「失败」分支在覆盖模式下也清 junk（数据源不可用场景，见 请求 1）
conn = db.get_conn()
conn.execute("UPDATE people SET meta=? WHERE id=?", ("content=掲載 無料動画", cid))
conn.commit(); conn.close()
assert db.count_needing_repair() == 1
_real_scrape_one = scraper_mod.scrape_one
def _boom(person, opts):
    raise RuntimeError("模拟数据源不可用（请求 1：HTTP 500 / WAF 截断）")
scraper_mod.scrape_one = _boom
try:
    stats = scraper_mod.scrape_many(
        [db.get_person(cid)],
        {"overwrite": True, "sources": [], "download_photo": False,
         "fill_alias": False, "fill_birthday": False, "fill_bio": False},
        writer=_fake_writer)
finally:
    scraper_mod.scrape_one = _real_scrape_one
check("反馈2续 失败分支也清 junk→计数归0", db.count_needing_repair() == 0,
      f"after={db.count_needing_repair()} failed={stats.get('failed')}")

# ============ 反馈 3：无父 more_btn 变浮动窗 ============
def _fetch(off, lim):
    return [{"id": i} for i in range(off, min(off + lim, 10))]
def _make(it):
    return QLabel(str(it))

g0 = LazyGrid(_fetch, _make, 0)          # total=0：不触发 _pump
check("反馈3 more_btn 有父(非顶层窗)", g0.more_btn.parent() is g0)
check("反馈3 未接管时按钮隐藏", g0.more_btn.isVisible() is False)
check("反馈3 未接管 _toolbar_ready=False", g0._toolbar_ready is False)

g1 = LazyGrid(_fetch, _make, 10)         # total>0：init 里会 _update_head(早退)+定时 _pump
check("反馈3 网格加载中按钮仍隐藏(未接管)", g1.more_btn.isHidden())
g1.mark_toolbar_placed()
check("反馈3 mark_toolbar_placed 置位", g1._toolbar_ready is True)
check("反馈3 接管后显式置为可见(非浮动窗)", not g1.more_btn.isHidden())
check("反馈3 接管后父仍为网格(非浮动)", g1.more_btn.parent() is g1)

# ============ 反馈 4：首页详情编辑后左表实时刷新 ============
home = HomeListView(on_open_actor=lambda p: None, on_open_media=lambda m: None,
                    on_hover_media=lambda m: None, on_changed=lambda: None)
check("反馈4 HomeListView 接受 on_changed", home.on_changed is not None)
home._cols = ["title", "favorite", "user_rating"]
home.table.setColumnCount(3)
home.table.setRowCount(1)
home._view = [{"id": 1, "title": "测试片", "favorite": 0, "user_rating": 0.0}]
home._detail_mid = 1
_real_get_media = db.get_media
db.get_media = lambda mid: {"id": 1, "title": "测试片", "favorite": 1, "user_rating": 8.5}
home._refresh_detail_row()
db.get_media = _real_get_media
fav_cell = home.table.item(0, 1).text() if home.table.item(0, 1) else ""
rate_cell = home.table.item(0, 2).text() if home.table.item(0, 2) else ""
check("反馈4 收藏列就地刷新为★", fav_cell == "★ 收藏", fav_cell)
check("反馈4 评分列就地刷新为8.5", rate_cell == "8.5", rate_cell)
# _show_detail 必须把 on_changed 透传给 HeroView（真实调用路径）
home._show_detail({"id": 1, "title": "X"})
hvw = home.detail_host.layout().itemAt(0).widget()
check("反馈4 _show_detail 透传 on_changed",
      hvw is not None and getattr(hvw.on_changed, "__func__", None) is HomeListView._detail_changed,
      "" if hvw is not None else "detail_host 无子控件")

# ============ 整体构建不崩 ============
load_style(app)
win = MainWindow()
win.show()
print("MAIN OK:", win.windowTitle())

# ---------- 汇总 ----------
fails = [r for r in results if not r[1]]
print("\n==== SMOKE %s : %d/%d PASS ====" % (VERSION, len(results) - len(fails), len(results)))
for r in results:
    if not r[1]:
        print("  FAIL:", r[0], r[2])
sys.exit(1 if fails else 0)
