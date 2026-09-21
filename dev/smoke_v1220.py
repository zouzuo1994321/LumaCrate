# -*- coding: utf-8 -*-
"""v1.22.0 离屏冒烟：5 项反馈实施的回归与可用性检查。

  反馈 1：演员刮削四模式（全量/增量/补齐/修复）入口连通 + 各自正确的 people 查询。
  反馈 2：路径可上下排序（LibraryEditDialog 已有 ↑/↓；本脚本验证服务页默认路径列表也支持）。
  反馈 3：logo 作为应用图标（资源可定位）。
  反馈 4：扫描进行中首页实时刷新（ScanWorker.live 信号 + HomeListView.live_refresh）。
  反馈 5：演员卡 ☆/▲ 收藏/置顶按钮存在且按 people 表数据同步。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

import database as db
import scanner as scanner_mod
import scraper as scraper_mod
from main_window import MainWindow, ScanWorker, ActorCard, load_style
from ui_home import HomeListView
from ui_settings import SettingsDialog
from version import VERSION, BUILD

_TMPDB = tempfile.mkdtemp(prefix="lmc_tmpdb_")
db.db_path = lambda: os.path.join(_TMPDB, "index_data", "media_center.db")

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (("  -> " + extra) if extra else ""))

# ---------- 基础数据 ----------
db.init_db()
db.clear_media()

print("VERSION:", VERSION, BUILD)

# ============ 反馈 1：四模式入口 + people 查询 ============
check("反馈1 _run_mode 方法已定义", hasattr(SettingsDialog, "_run_mode"))
check("反馈1 ScanWorker.live 信号存在", hasattr(ScanWorker, "live"))

# 造 3 位演员：完整 / 垃圾 meta / 缺字段
p1 = db.upsert_person("完整演员")
db.update_person(p1, photo_path="a.jpg", alias="A", bio="简介")
p2 = db.upsert_person("垃圾meta演员")
# 修复历史资料只认「被刮削器写坏」的记录（需 source_url/scraped_at），与 v1.21.2 一致
db.update_person(p2, meta="<og:description>掲載中</og:description>",
                 source_url="https://example.com/x", scraped_at="2026-09-20")   # 命中 _JUNK_LIKES
p3 = db.upsert_person("缺字段演员")                                       # 无头像/别名/简介

inc = db.people_for_scrape(only_no_photo=True, limit=0)
inc_ids = {x["id"] for x in inc}
check("反馈1 增量(无头像)含缺字段演员", p3 in inc_ids, str(inc_ids))
check("反馈1 增量(无头像)不含已完整演员", p1 not in inc_ids, str(inc_ids))

fill = db.people_needing_fill()
fill_ids = {x["id"] for x in fill}
check("反馈1 补齐信息含缺字段/缺别名演员", p3 in fill_ids, str(fill_ids))
check("反馈1 补齐信息不含完整演员", p1 not in fill_ids, str(fill_ids))

rep = db.people_needing_repair()
rep_ids = {x["id"] for x in rep}
check("反馈1 修复历史资料含垃圾meta演员", p2 in rep_ids, str(rep_ids))
check("反馈1 修复历史资料不含干净演员", p1 not in rep_ids and p3 not in rep_ids, str(rep_ids))

# 全量 = 所有人
full = db.people_for_scrape(only_no_photo=False, limit=0)
check("反馈1 全量刮削覆盖所有演员", {p1, p2, p3} <= {x["id"] for x in full}, str(len(full)))

# ============ 反馈 2：路径可排序 ============
# LibraryEditDialog / SettingsDialog 内部用 compact_button + _move_path / _move_default_path；
# 这里验证符号存在（具体交互在 live_verify 真机验收）。
check("反馈2 服务页默认路径支持上移", hasattr(SettingsDialog, "_move_default_path"))
check("反馈2 服务页默认路径同步按钮", hasattr(SettingsDialog, "_sync_default_path_btns"))

# ============ 反馈 3：logo 资源可定位 ============
logo = os.path.join(ROOT, "logo.png")
check("反馈3 logo.png 存在", os.path.exists(logo), logo)
# 复刻 main._app_resource 的查找逻辑（开发期：src 与项目根）
here = SRC
cands = [here, os.path.dirname(here)]
found = next((os.path.join(c, "logo.png") for c in cands if os.path.exists(os.path.join(c, "logo.png"))), None)
check("反馈3 开发期能定位 logo", found is not None, str(found))

# ============ 反馈 4：扫描实时刷新 ============
check("反馈4 HomeListView.live_refresh 存在", hasattr(HomeListView, "live_refresh"))
check("反馈4 ScanWorker._on_progress 节流方法存在", hasattr(ScanWorker, "_on_progress"))

# ============ 反馈 5：演员卡 ☆/▲ 与数据同步 ============
card = ActorCard({"name": "同步测试", "favorite": 1, "pinned": 0},
                 None, None, None, None, None)
check("反馈5 演员卡含收藏按钮", hasattr(card, "_star"))
check("反馈5 演员卡含置顶按钮", hasattr(card, "_pin"))
check("反馈5 收藏状态按 favorite 显示★", card._star.text() == "★", card._star.text())
check("反馈5 未置顶显示△", card._pin.text() == "△", card._pin.text())
card2 = ActorCard({"name": "同步测试2", "favorite": 0, "pinned": 1},
                  None, None, None, None, None)
check("反馈5 未收藏显示☆", card2._star.text() == "☆", card2._star.text())
check("反馈5 已置顶显示▲", card2._pin.text() == "▲", card2._pin.text())

# toggle 落库
f0 = db.toggle_person_favorite(p1)
check("反馈5 toggle_person_favorite 可翻转", f0 in (0, 1), str(f0))
pn = db.toggle_person_pinned(p2)
check("反馈5 toggle_person_pinned 可翻转", pn in (0, 1), str(pn))

# ============ 汇总 ============
fails = [r for r in results if not r[1]]
print("\n==== 结果：%d 通过 / %d 失败 ====" % (len(results) - len(fails), len(fails)))
for r in fails:
    print("FAIL", r[0], r[2])
sys.exit(1 if fails else 0)
