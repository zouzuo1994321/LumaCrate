# -*- coding: utf-8 -*-
"""v1.43.0 离屏冒烟：6 条需求逐项断言（离线，不联网）。

① 「数据导入/导出」→ 元数据管理（导航/页面身份/分组标题）
② 偏好管理：按番号导出/导入 收藏·观看·评分（评分回写 nfo）、人物收藏置顶
③ 演员库清理：孤儿查询 / 批量删除 / 默认排除收藏置顶
④ 新源：SCRAPER_SOURCES 6 源、SEARCHERS/FETCHERS 注册、老配置迁移、
   kana→romaji、维基 wikitext 解析（真实结构 fixture）、gfriends 直链、theporndb 无 Key 静默
⑤ 缺陷：QMainWindow 不透明底色 + 激活重绘
⑥ 缺陷：「更多 → 查看演员库」真正触发回调
回归：刮削页 6 行列表高 272、SRC_ROW_H 44、数据页分组顺序
"""
import json
import os
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1430_")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtWidgets import (QApplication, QGroupBox, QPushButton, QListWidgetItem,
                               QScrollArea, QVBoxLayout, QWidget)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg
import applog

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP
db.init_db()

FAILS = []
TOTAL = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    print(("  [✓] " if cond else "  [✗] ") + label + ("  (%s)" % detail if detail else ""))
    if not cond:
        FAILS.append(label)


import version as VER
import prefs as prefs_mod
import scraper as sc
import ui_settings as uis
import ui_cleanup as uic
import main_window as mw
from ui_hero import HeroView

print("== 版本 ==")
check("VERSION == v1.46.8", VER.VERSION == "v1.46.8", VER.VERSION)
check("BUILD == 2610230110", VER.BUILD == "2610230110", VER.BUILD)

# ============================================================
print("== ① 导航名：数据与日志（v1.43.1 回改） ==")
check("NAV_GROUPS 拆成「数据管理」+「日志中心」",
      any("数据管理" in g[1] for g in uis.SettingsDialog.NAV_GROUPS)
      and any("日志中心" in g[1] for g in uis.SettingsDialog.NAV_GROUPS))
check("NAV_GROUPS 不再含合并页「数据与日志」", not any("数据与日志" in g[1]
                                             for g in uis.SettingsDialog.NAV_GROUPS))
check("导航项已改名「引擎设置」（v1.45.2）",
      any("引擎设置" in g[1] or g[1] == ["引擎设置"] for g in uis.SettingsDialog.NAV_GROUPS)
      and not any("AI引擎设置" in g[1] for g in uis.SettingsDialog.NAV_GROUPS))
import i18n
check("i18n(zh) 词典键 = 数据管理/日志中心",
      "数据管理" in i18n.TOOL_KEYS["zh_CN"] and "日志中心" in i18n.TOOL_KEYS["zh_CN"])

# ============================================================
print("== ② 偏好管理：按番号导出 / 导入 ==")


def add_media(title, path, fav=0, play=0, rating=0.0, nfo=""):
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO media (kind,title,file_path,nfo_path,favorite,play_count,user_rating,library)"
        " VALUES ('movie',?,?,?,?,?,?,'测试库')",
        (title, path, nfo, fav, play, rating))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]


nfo1 = os.path.join(TMP, "MIDE-823.nfo")
with open(nfo1, "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="utf-8"?>\n<movie><title>MIDE-823</title></movie>\n')

m1 = add_media("MIDE-823 テスト作品", os.path.join(TMP, "lib", "MIDE-823.mp4"),
               fav=1, play=3, rating=9.0, nfo=nfo1)
m2 = add_media("SSIS-001 もう一本", os.path.join(TMP, "lib", "SSIS-001.mkv"),
               rating=7.5)
m3 = add_media("无番号的纪录片", os.path.join(TMP, "lib", "doc.mp4"), fav=1)
conn = db.get_conn()
conn.execute("INSERT INTO people (name, role_type, favorite, pinned) VALUES (?,?,?,?)",
             ("三上悠亜", "Actor", 1, 0))
conn.execute("INSERT INTO people (name, role_type, favorite, pinned) VALUES (?,?,?,?)",
             ("監督テスト", "Director", 0, 1))
conn.commit()

prefs_path = os.path.join(TMP, "prefs.json")
r = prefs_mod.export_prefs(prefs_path)
check("export ok", r.get("ok"), r.get("error", ""))
check("导出影片 3 条（含无番号 1 条）", r.get("media") == 3, r.get("media"))
check("导出人物 2 位", r.get("people") == 2, r.get("people"))
with open(prefs_path, encoding="utf-8") as f:
    payload = json.load(f)
check("type == lmc-prefs", payload.get("type") == "lmc-prefs")
nums = [x.get("num") for x in payload["media"]]
check("番号已归一化成 mide823 / ssis001", "mide823" in nums and "ssis001" in nums, nums)

# 清空偏好（模拟换机器 / nfo 被覆盖）
conn.execute("UPDATE media SET favorite=0, play_count=0, user_rating=0")
conn.execute("UPDATE people SET favorite=0, pinned=0")
conn.commit()
r2 = prefs_mod.import_prefs(prefs_path)
check("import ok", r2.get("ok"), r2.get("error", ""))
check("影片命中 3 条、无未匹配", r2.get("media_ok") == 3 and r2.get("media_miss") == 0,
      f"ok={r2.get('media_ok')} miss={r2.get('media_miss')}")
check("人物命中 2 位", r2.get("people_ok") == 2, r2.get("people_ok"))
row = db.get_conn().execute(
    "SELECT favorite, play_count, user_rating FROM media WHERE id=?", (m1,)).fetchone()
check("MIDE-823 偏好已恢复（收藏/观看/评分）",
      row["favorite"] == 1 and row["play_count"] == 3 and abs(row["user_rating"] - 9.0) < 1e-6,
      dict(row))
row2 = db.get_conn().execute("SELECT favorite, user_rating FROM media WHERE id=?",
                             (m2,)).fetchone()
check("SSIS-001 评分已恢复 7.5", abs((row2["user_rating"] or 0) - 7.5) < 1e-6,
      row2["user_rating"])
row3 = db.get_conn().execute("SELECT favorite FROM media WHERE id=?", (m3,)).fetchone()
check("无番号片按标题兜底恢复收藏", row3["favorite"] == 1, row3["favorite"])
with open(nfo1, encoding="utf-8") as f:
    nfo_txt = f.read()
check("nfo 已写回 <userrating>9.0", "<userrating>9.0</userrating>" in nfo_txt,
      nfo_txt[-60:].replace("\n", " "))
check("people 收藏/置顶已恢复",
      db.get_conn().execute(
          "SELECT COUNT(*) c FROM people WHERE favorite=1 OR pinned=1").fetchone()["c"] == 2)

# 未匹配统计
p2 = os.path.join(TMP, "prefs_bad.json")
with open(payload_path := prefs_path, encoding="utf-8") as f:
    bad = json.load(f)
bad["media"].append({"num": "zzzz999", "title": "不存在", "favorite": 1})
with open(p2, "w", encoding="utf-8") as f:
    json.dump(bad, f, ensure_ascii=False)
r3 = prefs_mod.import_prefs(p2)
check("假番号计入未匹配", r3.get("media_miss") == 1, r3.get("media_miss"))

# v1.44.2：范围导出 / 导入预览 / 0 分语义
p_fav = os.path.join(TMP, "prefs_fav.json")
r_sc = prefs_mod.export_prefs(p_fav, "favorite")
check("仅收藏范围导出只含收藏片", r_sc.get("ok") and r_sc.get("media") == 2,
      r_sc.get("media"))
r_rt = prefs_mod.export_prefs(os.path.join(TMP, "prefs_rt.json"), "rating")
check("仅评分范围导出只含评过分片", r_rt.get("ok") and r_rt.get("media") == 2,
      r_rt.get("media"))
db.get_conn().execute("UPDATE media SET favorite=0")
db.get_conn().commit()
_dry = prefs_mod.import_prefs(prefs_path, dry_run=True)
_still = db.get_conn().execute("SELECT COUNT(*) c FROM media WHERE favorite=1").fetchone()["c"]
check("导入预览（dry_run）不改库", _dry.get("dry_run") is True and _still == 0,
      f"dry={_dry.get('dry_run')} fav={_still}")
prefs_mod.import_prefs(prefs_path)
check("预览后真正导入仍生效",
      db.get_conn().execute("SELECT COUNT(*) c FROM media WHERE favorite=1").fetchone()["c"] == 2)
# 0 分：把评分清成 0 并写回 nfo（删 <userrating> 节点）
p_zero = os.path.join(TMP, "prefs_zero.json")
with open(p_zero, "w", encoding="utf-8") as f:
    json.dump({"type": "lmc-prefs", "media": [{"num": "mide823", "user_rating": 0}],
               "people": []}, f, ensure_ascii=False)
prefs_mod.import_prefs(p_zero)
_z = db.get_conn().execute("SELECT user_rating FROM media WHERE id=?", (m1,)).fetchone()["user_rating"]
check("0 分可写回（清空评分）", (_z or 0) == 0, _z)
check("0 分同时从 nfo 删掉 <userrating>",
      "<userrating>" not in open(nfo1, encoding="utf-8").read())

# ============================================================
print("== ③ 演员库清理 ==")
conn = db.get_conn()
orphan_id = conn.execute("INSERT INTO people (name, role_type) VALUES ('无作品演员','Actor')").lastrowid
fav_orphan = conn.execute(
    "INSERT INTO people (name, role_type, favorite) VALUES ('收藏但无作品','Actor',1)").lastrowid
conn.execute("INSERT INTO people (name, role_type) VALUES ('无作品导演','Director')")
conn.commit()
rows = db.orphan_people("Actor")
names = [x["name"] for x in rows]
check("孤儿查询含「无作品演员」", "无作品演员" in names, names)
check("孤儿查询排除收藏者", "收藏但无作品" not in names)
check("导演孤儿单独按 role_type 查", any(x["name"] == "无作品导演"
                                     for x in db.orphan_people("Director")))
# 给一个孤儿挂作品后应消失
conn.execute("INSERT INTO media_people (media_id, person_id, char_role, person_order)"
             " VALUES (?,?,?,0)", (m1, orphan_id, "主演"))
conn.commit()
check("有作品后不再算孤儿", "无作品演员" not in [x["name"] for x in db.orphan_people("Actor")])
conn.execute("DELETE FROM media_people WHERE person_id=?", (orphan_id,))
conn.commit()
n_del = db.delete_people([orphan_id])
check("delete_people 删除 1 条", n_del == 1, n_del)
check("删除后 people 里查不到",
      db.get_conn().execute("SELECT COUNT(*) c FROM people WHERE id=?",
                            (orphan_id,)).fetchone()["c"] == 0)
check("delete_people 空输入返回 0", db.delete_people([]) == 0)

# ============================================================
print("== ④ 新数据源 + gfriends ==")
keys = [x["key"] for x in cfg.SCRAPER_SOURCES]
check("SCRAPER_SOURCES 五源（ThePornDB 已删）", keys == ["minnano", "imdb", "avbase",
                                         "wikipedia", "javdb"], keys)
check("SEARCHERS 注册五源", set(sc.SEARCHERS) == set(keys), sorted(sc.SEARCHERS))
check("FETCHERS 注册五源", set(sc.FETCHERS) == set(keys), sorted(sc.FETCHERS))
check("SOURCE_NAMES 含 gfriends", "gfriends" in sc.SOURCE_NAMES)

# 老配置迁移（3 源、无新键）
old = {"scraper": {"sources": ["avbase", "minnano", "imdb"],
                   "sources_enabled": {"avbase": True, "minnano": True, "imdb": True}}}
with open(cfg.config_path(), "w", encoding="utf-8") as f:
    json.dump(old, f)
cfg._SETTINGS = None
s2 = cfg.get_settings()
check("老配置自动补上新源", set(s2.scraper["sources"]) == set(keys), s2.scraper["sources"])
check("javdb 默认关（新键按 DEFAULT 而非一律 True）",
      s2.scraper["sources_enabled"].get("javdb") is False,
      s2.scraper["sources_enabled"].get("javdb"))
check("wikipedia 默认开", s2.scraper["sources_enabled"].get("wikipedia") is True)
check("gfriends_photo 默认 True", s2.scraper.get("gfriends_photo") is True)
check("ThePornDB 配置已彻底移除", "theporndb" not in s2.scraper.get("sources", [])
      and "theporndb_token" not in s2.scraper)
check("Cookie 存活检测接口存在", hasattr(sc, "test_cookie")
      and len(getattr(sc, "SOURCE_BASES", {})) == 5)
check("未获取 Cookie 时给出明确结论",
      sc.test_cookie("avbase")["has_cookie"] in (True, False))

# 假名转写
check("みかみ ゆあ → mikami yua", sc.kana_to_romaji("みかみ ゆあ") == "mikami yua",
      sc.kana_to_romaji("みかみ ゆあ"))
check("片假名同等转写", sc.kana_to_romaji("ミカミ ユア") == "mikami yua")
check("拗音 きょうこ → kyouko", sc.kana_to_romaji("きょうこ") == "kyouko",
      sc.kana_to_romaji("きょうこ"))
check("假名转写仍可用于检索（ThePornDB 已删）",
      sc.kana_to_romaji("みかみ ゆあ") == "mikami yua")

# 维基解析（真实结构 fixture：YouTube 信息框 + ref 里 2019 日期 + 首段 1993 生日）
WIKITEXT = """{{Infobox YouTube personality
| channel_display_name = ゆあちゃんねる!
| years_active = [[2016年]] -
| subscribers = 112万人<ref name="YouTube">{{Cite web|url=https://x/|accessdate=2025-10-10}}</ref>
}}
'''三上悠亜'''（みかみ ゆあ、本名：'''鬼頭 桃菜'''〈きとう ももな〉<ref>2023-08-16</ref>'''、
[[1993年]]〈[[平成5年]]〉[[8月16日]]{{R|livedoor}} - ）は、日本のタレント。
身長159cm。[[愛知県]][[名古屋市]]出身<ref>2019年1月14日</ref>。
"""
wi = sc._wiki_parse("三上悠亜", WIKITEXT, "https://img/x.jpg", "https://ja.wikipedia.org/wiki/x")
check("维基生日不被 ref 日期污染", wi["birthday"] == "1993-08-16", wi["birthday"])
check("维基读出读音 みかみ ゆあ", wi["romaji"] == "みかみ ゆあ", wi["romaji"])
check("维基头图透传", wi["photo_url"] == "https://img/x.jpg")
check("维基姓名取首段加粗", wi["name"] == "三上悠亜", wi["name"])

# gfriends 直链（假树，断言 URL 编码）
FAKE = {"Content": {"y-Minnano": {"三上悠亜.jpg": "三上悠亜.jpg?t=1658331539"},
                    "z-DMM(骑)": {"三上悠亜.jpg": "AI-Fix-三上悠亜.jpg?t=1607433629"}}}
_orig_tree = sc.gfriends_tree
sc.gfriends_tree = lambda *a, **k: FAKE
try:
    u = sc.gfriends_photo_url("三上悠亜")
    check("gfriends 直链 URL 编码正确",
          u == ("https://raw.githubusercontent.com/gfriends/gfriends/master/Content/"
                "y-Minnano/%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C.jpg"), u)
    check("gfriends 未命中返回空串", sc.gfriends_photo_url("不存在名字") == "")
finally:
    sc.gfriends_tree = _orig_tree

# theporndb 无 Key 时静默（不发请求、不报错）
check("ThePornDB 检索函数已删除", not hasattr(sc, "theporndb_search"))
check("ThePornDB Token 接口已删除", not hasattr(sc, "set_theporndb_token"))

# ============================================================
print("== ⑤ 底部变黑缺陷 ==")
qss = mw.render_style(cfg.get_settings().appearance)
check("QMainWindow 使用不透明底色（不再 transparent）",
      "QMainWindow { background: #0d0b0a; }" in qss)
check("状态栏为不透明面板色（v1.43.4：不再是近纯黑 #0f0d0b）",
      "background: #1c1815" in qss and "background: #241f1b" in qss
      and "background: #0f0d0b" not in qss)
check("菜单关闭后强制重绘（v1.43.1 反馈 3 保险）",
      hasattr(HeroView, "_repaint_after_menu"))
check("_repaint_after_menu 空值安全（v1.43.4：修 app.log 里 HeroView 已销毁的 RuntimeError）",
      HeroView._repaint_after_menu(None) is None)
# v1.43.2（反馈 2 真根因）：主窗**不再**启用系统级 backdrop（Win11 Acrylic 失活变黑）
import backdrop
check("backdrop 提供 apply_plain_dark", hasattr(backdrop, "apply_plain_dark"))
check("MainWindow 有激活重绘入口",
      hasattr(mw.MainWindow, "changeEvent") and hasattr(mw.MainWindow, "_repaint_shell"))

win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
try:
    win._repaint_shell()
    ok = True
except Exception as e:
    ok = False
    print("     _repaint_shell 异常:", e)
check("_repaint_shell 可安全调用", ok)
check("MainWindow 有不透明底兜底 paintEvent", hasattr(mw.MainWindow, "paintEvent"))
# v1.44.0（需求 1）：版权**左下常驻**、临时消息**右下**且超时自动消失
check("底部版权为常驻标签（不再用 showMessage）",
      hasattr(win, "_footer_lbl") and VER.FULL_VERSION in win._footer_lbl.text(),
      getattr(getattr(win, "_footer_lbl", None), "text", lambda: "无")()[:40])
check("版权标签左对齐（左下常驻）",
      bool(win._footer_lbl.alignment() & Qt.AlignLeft))
win._toast("测试临时消息", 1500)
app.processEvents()
check("临时消息显示在右下且不覆盖版权",
      win._toast_lbl.isVisible() and win._toast_lbl.text() == "测试临时消息"
      and VER.FULL_VERSION in win._footer_lbl.text())
check("临时消息标签右对齐", bool(win._toast_lbl.alignment() & Qt.AlignRight))
win._clear_toast()
check("临时消息可清空", not win._toast_lbl.isVisible())
_src_mw = open(os.path.join(ROOT, "src", "main_window.py"), encoding="utf-8").read()
check("主窗已不再使用 showMessage", ".showMessage(" not in _src_mw)
# v1.43.5（反馈 1）：透明度滑块把手由正圆改圆角扁平方形
_qss2 = mw.render_style(cfg.get_settings().appearance)
check("滑块把手为 18×12 圆角扁平方形（radius 4，不再是 16/radius 8）",
      "width: 18px; margin: -3px 0; border-radius: 4px;" in _qss2)
check("底部版权标签有专属样式", "QLabel#FooterNote" in _qss2)
check("状态栏存在且可见", win.statusBar() is not None)
# v1.43.2：主窗 backdrop 必须是 plain-dark（系统 Acrylic 已关）
check("主窗 backdrop 已改为 plain-dark（无系统材质）",
      (getattr(win, "_backdrop_info", {}) or {}).get("method") == "plain-dark",
      (getattr(win, "_backdrop_info", {}) or {}).get("method"))

# ============================================================
print("== ⑥ 查看演员库 ==")
called = {"n": 0}
hv = HeroView({"id": m1, "title": "MIDE-823", "file_path": os.path.join(TMP, "lib", "MIDE-823.mp4")},
              on_open_actors=lambda: called.__setitem__("n", called["n"] + 1))
hv.setAttribute(Qt.WA_DontShowOnScreen, True)
hv.show()
app.processEvents()
hv._open_actor_lib()
check("查看演员库触发回调", called["n"] == 1, called["n"])
check("HeroView 签名含 on_open_actors", "on_open_actors" in HeroView.__init__.__code__.co_varnames)

# v1.43.1（反馈 4）：**首页右侧详情**同样是 HeroView，必须也接上回调
from ui_home import HomeListView
hit = {"n": 0}
hlv = HomeListView(on_open_actors=lambda: hit.__setitem__("n", hit["n"] + 1))
hlv.setAttribute(Qt.WA_DontShowOnScreen, True)
hlv.resize(1200, 700)
hlv.show()
app.processEvents()
hlv._show_detail({"id": m1, "title": "MIDE-823 テスト作品",
                  "file_path": os.path.join(TMP, "lib", "MIDE-823.mp4")})
for _ in range(6):
    app.processEvents()
_hv2 = hlv.detail_host.layout().itemAt(0).widget()
_hv2._open_actor_lib()
check("首页详情的「查看演员库」也触发回调", hit["n"] == 1, hit["n"])
check("HomeListView 签名含 on_open_actors",
      "on_open_actors" in HomeListView.__init__.__code__.co_varnames)

# ============================================================
print("== 回归：刮削页 / 数据页布局 ==")
dlg = uis.SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
for _ in range(8):
    app.processEvents()
dlg._show("演员刮削")
for _ in range(12):
    app.processEvents()
# v1.43.1（反馈 1）：刮削页必须是「画布高=内容高 + 可滚」，组框不许吸拉伸
check("刮削页 widgetResizable == False（不吸余量）",
      dlg._pg_scraper.widgetResizable() is False)
_pg_s = dlg._pg_scraper.widget() if hasattr(dlg._pg_scraper, "widget") else dlg._pg_scraper
_gb_top = [g for g in _pg_s.findChildren(QGroupBox) if g.title() == "演员刮削"]
check("顶部「演员刮削」组框没被撑高",
      bool(_gb_top) and _gb_top[0].height() <= _gb_top[0].sizeHint().height() + 8,
      f"{_gb_top[0].height()} vs sizeHint {_gb_top[0].sizeHint().height()}" if _gb_top else "无")
check("数据源列表 5 行", dlg.src_list.count() == 5, dlg.src_list.count())
check("列表只露三行（v1.43.1 反馈 5：高 == 44*3+8 == 140）",
      dlg.src_list.height() == 140, dlg.src_list.height())
# v1.43.2（反馈 1）：三行装不下 6 个源，必须有可用的竖向滚轴
_sb = dlg.src_list.verticalScrollBar()
check("竖向滚轴已启用（AsNeeded）",
      dlg.src_list.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded)
check("滚轴可滚（maximum > 0）且可见", _sb.maximum() > 0 and _sb.isVisible(),
      f"max={_sb.maximum()} vis={_sb.isVisible()}")
check("滚轴样式已加粗（objectName 规则）",
      "QListWidget#SrcSourceList QScrollBar:vertical" in mw.render_style(cfg.get_settings().appearance))
check("SRC_ROW_H == 44", uis.SRC_ROW_H == 44, uis.SRC_ROW_H)
check("ssc_clean 按钮存在", hasattr(dlg, "sc_clean") and dlg.sc_clean.text() == "演员库清理…")
check("gfriends 开关存在、ThePornDB Key 已移除",
      hasattr(dlg, "sc_gf") and not hasattr(dlg, "sc_tpdb"))
check("演员刮削有「Cookie 获取…」与「测试全部 Cookie 存活」",
      any(b.text() == "Cookie 获取…" for b in dlg.findChildren(QPushButton))
      and any(b.text() == "测试全部 Cookie 存活" for b in dlg.findChildren(QPushButton)))

dlg._show("数据管理")
for _ in range(12):
    app.processEvents()
pg = dlg._pg_data.widget() if hasattr(dlg._pg_data, "widget") else dlg._pg_data
groups = [g.title() for g in pg.findChildren(QGroupBox)]
check("数据管理页分组正确（元数据 / 偏好 / 维护与重置）",
      len(groups) >= 3 and groups[0] == "元数据导出 / 导入"
      and groups[1].startswith("偏好管理")
      and groups[-1].startswith("维护与重置"), groups)
_bn = [b.text() for b in pg.findChildren(QPushButton)]
check("4 个危险操作按钮齐全",
      all(x in _bn for x in ("清理缓存", "删除数据库", "恢复默认设置", "初始化软件")), _bn[-6:])
check("危险操作有二次确认入口", hasattr(dlg, "_confirm_twice")
      and all(hasattr(dlg, f) for f in ("_clean_cache", "_drop_database",
                                        "_reset_settings", "_factory_reset")))
# 日志中心独立成页
_lg = dlg._pg_logs.widget() if hasattr(dlg._pg_logs, "widget") else dlg._pg_logs
_lg_groups = [g.title() for g in _lg.findChildren(QGroupBox)]
check("日志中心含刮削诊断 + 运行日志两块",
      "运行日志" in _lg_groups and "运行日志（实时）" in _lg_groups
      and any(g.startswith("刮削诊断") for g in _lg_groups), _lg_groups)
check("日志中心已注册到 stack", dlg.stack.indexOf(dlg._pg_logs) >= 0
      and dlg.stack.indexOf(dlg._pg_data) >= 0)
btns = [b.text() for b in pg.findChildren(QPushButton)]
check("偏好按钮存在且不裁字", "导出偏好…" in btns and "导入偏好…" in btns)
check("偏好说明标签存在", hasattr(dlg, "pref_hint"))
# v1.43.4（反馈 1）：高亮色卡由正圆改圆角扁平方形
_sw = list(getattr(dlg, "_accent_btns", {}).values())
check("色卡为 30x24 圆角扁平方形",
      bool(_sw) and all(b.width() == 30 and b.height() == 24 for b in _sw),
      f"{_sw[0].width()}x{_sw[0].height()}" if _sw else "无")
check("色卡是自绘 _AccentSwatch（不依赖字体勾号）",
      bool(_sw) and hasattr(_sw[0], "set_on")
      and type(_sw[0]).__name__ == "_AccentSwatch", type(_sw[0]).__name__ if _sw else "")

# 演员库清理对话框（构建 + 列表填充 + 勾选计数）
clean = uic.PeopleCleanDialog(win)
clean.setAttribute(Qt.WA_DontShowOnScreen, True)
clean.show()
app.processEvents()
check("清理对话框列出孤儿", clean.list.count() >= 1, clean.list.count())
clean._set_all(True)
check("全选后计数一致", len(clean._checked_ids()) == clean.list.count(),
      f"{len(clean._checked_ids())}/{clean.list.count()}")
clean._set_all(False)
check("全不选后为 0", len(clean._checked_ids()) == 0)
clean.close()

# ============================================================
print("== ⑦ 拖动条：虚线 + 5 点可抓（v1.43.3）==")
import ui_imagedetect as uid
import ui_actorcheck as uac
from PySide6.QtCore import QPointF, QEvent
from PySide6.QtGui import QMouseEvent

pg_img = uid.ImageDetectPage()
pg_img.setAttribute(Qt.WA_DontShowOnScreen, True)
pg_img.resize(1200, 800)
pg_img.show()
for _ in range(10):
    app.processEvents()
_splits = pg_img.findChildren(uac._GripSplitter)
check("图像检测页使用 _GripSplitter", len(_splits) == 1, len(_splits))
_s = _splits[0]
check("图像检测把手 objectName == ImageSplitH", _s.objectName() == "ImageSplitH",
      _s.objectName())
check("图像检测把手宽 14", _s.handleWidth() == 14, _s.handleWidth())
_h = _s.handle(1)
check("图像检测把手是 _GripHandle", isinstance(_h, uac._GripHandle), type(_h).__name__)

img = _h.grab().toImage()
_w, _hh = img.width(), img.height()
_dash = 0
for _y in range(1, _hh - 1):
    _a = img.pixelColor(_w // 2, _y).alpha()
    if 0 < _a <= 90:
        _dash += 1
check("把手上画出了虚线（淡像素 > 20 个）", _dash > 20, _dash)

_pad = uac._GripHandle._PAD
_cy = int(_pad + (_hh - _pad * 2) * 0.5)
_before = list(_s.sizes())
_h.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(_w / 2, _cy),
                               Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
check("按住点簇进入抓取态", _h._grip_drag is True)
_h.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(_w / 2, _cy + 60),
                              Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
check("拖动后点簇位置变化", _h.grip_pos() > 0.5, round(_h.grip_pos(), 3))
check("抓点拖动不改分栏尺寸", list(_s.sizes()) == _before, f"{_before} -> {list(_s.sizes())}")
_h.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPointF(_w / 2, _cy + 60),
                                 Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
check("松开后退出抓取态", _h._grip_drag is False)
_pg_actor = uac.ActorCheckPage()
_pg_actor.setAttribute(Qt.WA_DontShowOnScreen, True)
_pg_actor.resize(1200, 900)
_pg_actor.show()
for _ in range(8):
    app.processEvents()
check("演员检测页两个把手同样都是 _GripHandle",
      len(_pg_actor.findChildren(uac._GripSplitter)) == 2
      and all(isinstance(sp.handle(1), uac._GripHandle)
              for sp in _pg_actor.findChildren(uac._GripSplitter)),
      len(_pg_actor.findChildren(uac._GripSplitter)))
_pg_actor.close()
pg_img.close()

# ============================================================
print("== ⑧ 查询性能：影片墙排序必须走索引（v1.43.6）==")
perf_db = os.path.join(TMP, "perf.db")
db.close_all()
db.db_path = lambda: perf_db
db.init_db()
_pc = db.get_conn()
_pc.executemany(
    "INSERT INTO media (kind,title,file_path,library,year) VALUES (?,?,?,?,?)",
    [("movie", "Title %06d" % i, "/x/%d.mp4" % i, "测试库", i % 4000 + 1)
     for i in range(20000)])
_pc.commit()
db.init_db()      # 第二次：建索引 + ANALYZE
_bad = []
for _key, _asc in (("sort_title", True), ("sort_title", False), ("added_time", False),
                   ("rating", False), ("user_rating", False), ("play_count", False),
                   ("file_size", False)):
    _expr = db._SORT_EXPR[_key]
    _sql = ("SELECT m.id FROM media m WHERE m.parent_id IS NULL ORDER BY %s %s, "
            "m.year DESC, m.id ASC LIMIT 60" % (_expr, "ASC" if _asc else "DESC"))
    _plan = [r[-1] for r in _pc.execute("EXPLAIN QUERY PLAN " + _sql)]
    if any("TEMP B-TREE" in p for p in _plan):
        _bad.append(_key + ("_asc" if _asc else "_desc"))
    print("    %-12s %-4s %s" % (_key, "ASC" if _asc else "DESC", _plan))
check("7 个常用排序的计划均无 TEMP B-TREE", not _bad, _bad)
_names = {r[0] for r in _pc.execute("SELECT name FROM sqlite_master WHERE type='index'")}
_need = {"idx_wallp_title", "idx_wallp_title_d", "idx_wallp_time", "idx_wallp_rating",
         "idx_wallp_urating", "idx_wallp_play", "idx_wallp_size"}
check("7 条 parent_id 打头的复合索引都已创建", _need <= _names, sorted(_need - _names))
# 恢复主库，避免影响后续（本轮已到末尾，仍保持干净）
db.close_all()
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")


# ============================================================
print("== ⑨ v1.45.3：简介 2 行省略 / 演员库冗余列 / 缓存目录 / 作品分批 ==")
# —— 简介最多 2 行，超出用「 ...」
import ui_hero as uh
_long = "这是一段很长的简介。" * 60
_el = uh.ElidedLabel(_long, max_lines=2)
_el.resize(220, 40)
app.processEvents()
_fm = _el.fontMetrics()
check("ElidedLabel 高度锁定 2 行",
      0 < _el.minimumHeight() <= int(_fm.lineSpacing() * 2 + 10), _el.minimumHeight())
_shown = _el._shown(220)
check("ElidedLabel 超长以「 ...」结尾", _shown.endswith(" ..."), _shown[-14:])
check("ElidedLabel 省略后正好 2 行",
      len(_shown) < len(_long) and _el._count_lines(_shown, 218) == 2, len(_shown))
_el2 = uh.ElidedLabel("短简介", max_lines=2)
check("ElidedLabel 短文本不截断", _el2._shown(220) == "短简介", _el2._shown(220))

# —— people.works / last_year 冗余列 + 触发器
_cols = {r[1] for r in db.get_conn().execute("PRAGMA table_info(people)")}
check("people 已有 works / last_year 列", {"works", "last_year"} <= _cols, sorted(_cols))
_pid = db.upsert_person("触发器测试演员", "Actor")
_w0 = db.get_conn().execute(
    "SELECT COALESCE(works,0) w FROM people WHERE id=?", (_pid,)).fetchone()["w"]
check("新建人物 works 初始为 0", _w0 == 0, _w0)
db.link_media_person(m1, _pid, "Test", 1)
_w1 = db.get_conn().execute(
    "SELECT COALESCE(works,0) w FROM people WHERE id=?", (_pid,)).fetchone()["w"]
check("插入关联后 works +1（触发器）", _w1 == _w0 + 1, f"{_w0}→{_w1}")
_c = db.get_conn()
_c.execute("DELETE FROM media_people WHERE media_id=? AND person_id=?", (m1, _pid))
_c.commit()
_w2 = _c.execute("SELECT COALESCE(works,0) w FROM people WHERE id=?", (_pid,)).fetchone()["w"]
check("删除关联后 works -1（触发器）", _w2 == _w0, f"{_w1}→{_w2}")
# query_people / count_people 同口径
_q = db.query_people("Actor", limit=200)
_ct = db.count_people("Actor")
check("演员查询与计数同口径（works 列）",
      len(_q) == min(200, _ct), f"rows={len(_q)} count={_ct}")

# —— gfriends 默认缓存目录不再落到用户主目录
_sc_src = open(os.path.join(ROOT, "src", "scraper.py"), encoding="utf-8").read()
check("gfriends 默认缓存改到 index_data/cache/gfriends",
      '"index_data", "cache", "gfriends"' in _sc_src
      and 'expanduser("~"), ".lmacrate"' not in _sc_src)

# —— 演员「全部作品」按批补演员信息（不再对整份列表一次查）
check("_grid 走 LazyGrid 且按批 _crewed",
      "lambda off, lim: self._crewed(items[off:off + lim])" in open(
          os.path.join(ROOT, "src", "main_window.py"), encoding="utf-8").read())



# ============================================================
print("== ⑩ v1.45.4：标题 2 行 / 演员性别（筛选 + 卡片符号 + 刮削）==")
# —— 标题也是 ElidedLabel 且最多 2 行
_hv = uh.HeroView({"id": 9, "title": "DJIN-027 キラメキナイトと怪しいキャバギャルに…" * 4,
                   "plot": "简介", "year": 2026})
_hv.setAttribute(Qt.WA_DontShowOnScreen, True)
_hv.resize(420, 700); _hv.show()
for _ in range(8):
    app.processEvents()
_tls = [l for l in _hv.findChildren(uh.ElidedLabel)]
check("详情标题用 ElidedLabel（2 行）",
      len(_tls) >= 2 and any(l._max_lines == 2 for l in _tls), len(_tls))
_t0 = _tls[0]
check("标题省略后 2 行且以「 ...」结尾",
      _t0._shown(420).endswith(" ...") and _t0._count_lines(_t0._shown(420), 418) == 2,
      _t0._shown(420)[-10:])
_hv.close()

# —— 性别：列 / 筛选 / 卡片符号
_pc = {r[1] for r in db.get_conn().execute("PRAGMA table_info(people)")}
check("people 已有 gender 列", "gender" in _pc, sorted(_pc))
_g1 = db.upsert_person("性别测试-女", "Actor")
_g2 = db.upsert_person("性别测试-男", "Actor")
db.update_person(_g1, gender="female")
db.update_person(_g2, gender="male")
check("性别筛选 female 命中",
      any(p["id"] == _g1 for p in db.query_people("Actor", limit=300, gender="female")))
check("性别筛选 male 命中",
      any(p["id"] == _g2 for p in db.query_people("Actor", limit=300, gender="male")))
check("性别人数与查询同口径",
      db.count_people("Actor", gender="female") == len(db.query_people("Actor", limit=0, gender="female")))

# —— 刮削解析性别
check("性別=女性 → female", sc._gender_of("性別：女性 生年 1992") == "female")
check("性別=男性 → male", sc._gender_of("性别 男性") == "male")
check("女優（无性別字段）→ female", sc._gender_of("日本のAV女優。") == "female")
check("未标注 → 空", sc._gender_of("某位艺人，职业不详") == "")

# —— 卡片符号
_card_f = mw.ActorCard({"id": _g1, "name": "森沢かな", "gender": "female"},
                    on_open=lambda *_: None, on_fav=lambda *_: None,
                    on_pin=lambda *_: None, on_select=lambda *_: None, main_win=win)
_card_m = mw.ActorCard({"id": _g2, "name": "男演员", "gender": "male"},
                    on_open=lambda *_: None, on_fav=lambda *_: None,
                    on_pin=lambda *_: None, on_select=lambda *_: None, main_win=win)
check("卡片显示 ♀（粉）", "♀" in _card_f._name.text() and "#e6739f" in _card_f._name.text())
check("卡片显示 ♂（蓝）", "♂" in _card_m._name.text() and "#5aa9e6" in _card_m._name.text())
_card_f.deleteLater(); _card_m.deleteLater()


# ============================================================
print("== ⑪ v1.45.5：标题字号/悬停、性别筛选、偏好勾选、日志诊断 ==")
# —— 标题/简介：字号随 DPI、悬停看全文
_hv2 = uh.HeroView({"id": 8, "title": "长标题" * 30, "plot": "长简介" * 60, "year": 2026})
_hv2.setAttribute(Qt.WA_DontShowOnScreen, True); _hv2.resize(460, 700); _hv2.show()
for _ in range(8):
    app.processEvents()
_lab = _hv2.findChildren(uh.ElidedLabel)
_t, _p = _lab[0], _lab[1]
check("标题/简介都带完整文本 tooltip", _t.toolTip() == _t.full_text() and _p.toolTip() == _p.full_text())
check("字号按逻辑像素保存（标题 34 / 简介 12）", _t._px == 34 and _p._px == 12,
      "%d/%d" % (_t._px, _p._px))
_eff = _t._eff_font().pixelSize()
check("绘制字号 = px × dpr", _eff == int(round(34 * _t.devicePixelRatioF())), _eff)
_hv2.close()

# —— 性别筛选要能穿过 config 白名单
_s = cfg.get_settings()
_s.set_actor_prefs(filters={"gender": "female"})
_rt = cfg.get_settings().actor_prefs.get("filters", {}).get("gender")
check("性别筛选能落盘（ACTOR_FILTER_KEYS 已含 gender）", _rt == "female", _rt)
_s.set_actor_prefs(filters={})

# —— 偏好导出可勾选字段
_pf = os.path.join(TMP, "prefs_favonly.json")
_r = prefs_mod.export_prefs(_pf, "all", ["favorite"])
with open(_pf, encoding="utf-8") as f:
    _pay = json.load(f)
_item = (_pay.get("media") or [{}])[0]
check("只勾『收藏』时导出不含观看/评分",
      _r.get("ok") and "favorite" in _item and "play_count" not in _item
      and "user_rating" not in _item, sorted(_item))
check("导出内容记录在 include 里", _pay.get("include") == ["favorite"], _pay.get("include"))
_pf2 = os.path.join(TMP, "prefs_gender.json")
_r2 = prefs_mod.export_prefs(_pf2, "all", ["gender"])
with open(_pf2, encoding="utf-8") as f:
    _pay2 = json.load(f)
check("勾『性别』时 people 带 gender 字段",
      _r2.get("ok") and any("gender" in p for p in (_pay2.get("people") or [])),
      (_pay2.get("people") or [{}])[0])

# —— 日志中心：刮削诊断 + 过滤搜索
dlg._show("日志中心")
for _ in range(10):
    app.processEvents()
check("日志中心有刮削诊断表", hasattr(dlg, "diag_tbl") and dlg.diag_tbl.columnCount() == 5)
dlg._refresh_diag()
check("诊断表能填充数据源行", dlg.diag_tbl.rowCount() >= 5, dlg.diag_tbl.rowCount())
check("日志有搜索框与只看错误开关", hasattr(dlg, "log_kw") and hasattr(dlg, "log_err_only"))
dlg.log_err_only.setChecked(True)
dlg.log_kw.setText("Traceback")
app.processEvents()
_txt = dlg._log_view.toPlainText()
check("日志过滤生效（只含匹配行或提示）",
      ("Traceback" in _txt) or ("没有匹配" in _txt), _txt[:40])
dlg.log_err_only.setChecked(False); dlg.log_kw.setText("")

# —— 演员库治理口径
check("清理口径 4 种", len(db.CLEANUP_KINDS) == 4, str(len(db.CLEANUP_KINDS)))
check("people_for_cleanup 可查无性别",
      isinstance(db.people_for_cleanup("nogender", "Actor"), list))


# ============================================================
print("== ⑫ v1.46.0：卡片虚拟化 / 性别符号开关 / 编辑性别 ==")
# —— 虚拟化：5000 条只建可视区
_fake = [{"id": i, "title": "T%d" % i} for i in range(5000)]
def _vf(off, lim):
    return _fake[off:off + lim]
def _vm(item):
    w = mw.QFrame(); w.setFixedSize(200, 120); return w
_sc = mw.QScrollArea(); _host = mw.QWidget(); _hl = mw.QVBoxLayout(_host)
_hl.setContentsMargins(0, 0, 0, 0)
_vg = mw.LazyGrid(_vf, _vm, len(_fake), kind="media", virtual=True)
_hl.addWidget(_vg); _sc.setWidget(_host); _sc.setWidgetResizable(True)
_sc.resize(900, 700); _sc.show()
_vg.attach_scroll(_sc.verticalScrollBar(), _sc.viewport())
for _ in range(6):
    app.processEvents()
_vg._render()
for _ in range(4):
    app.processEvents()
check("虚拟化：首屏只建可视区卡片（远少于 5000）", 0 < len(_vg._built) <= 160, len(_vg._built))
check("虚拟化：滚动条高度按总条数撑开", _sc.verticalScrollBar().maximum() > 1000,
      _sc.verticalScrollBar().maximum())
_vsb = _sc.verticalScrollBar()
_vsb.setValue(int(_vsb.maximum() * 0.85))
for _ in range(4):
    app.processEvents()
_vg._render()
check("虚拟化：滚到后段仍只建少量卡", 0 < len(_vg._built) <= 160 and _vg._window[0] > 100,
      "row0=%d cards=%d" % (_vg._window[0], len(_vg._built)))
_vg.jump_to(4999)
for _ in range(4):
    app.processEvents()
check("虚拟化：跳转到底部能取到卡片", _vg.card_at(4999) is not None)
check("虚拟化：控件总数与总量无关", len(_vg.findChildren(mw.QFrame)) <= 200,
      len(_vg.findChildren(mw.QFrame)))
_sc.close()

# —— 性别符号开关
_top = mw.MainWindow()
_top.setAttribute(Qt.WA_DontShowOnScreen, True); _top.resize(1400, 800); _top.show()
for _ in range(6):
    app.processEvents()
_pf = {"id": 991, "name": "开关测试", "gender": "female"}
cfg.get_settings().set_appearance(show_gender=True)
_c1 = mw.ActorCard(_pf, on_open=lambda *a: None, on_fav=lambda *a: None,
                   on_pin=lambda *a: None, on_select=lambda *a: None, main_win=_top)
check("开关开：卡片显示 ♀", "♀" in _c1._name.text())
cfg.get_settings().set_appearance(show_gender=False)
_c2 = mw.ActorCard(_pf, on_open=lambda *a: None, on_fav=lambda *a: None,
                   on_pin=lambda *a: None, on_select=lambda *a: None, main_win=_top)
check("开关关：卡片不显示符号", "♀" not in _c2._name.text() and _c2._name.text() == "开关测试")
cfg.get_settings().set_appearance(show_gender=True)

# —— 手动编辑性别（写入后可用筛选查到）
_gid = db.upsert_person("编辑性别测试", "Actor")
db.set_person_fields(_gid, gender="male")
check("手动编辑性别可落库并筛出",
      any(p["id"] == _gid for p in db.query_people("Actor", limit=400, gender="male")))
check("编辑面板含性别下拉", "gender_box" in open(
    os.path.join(ROOT, "src", "ui_actorcheck.py"), encoding="utf-8").read())


# ============================================================
print("== ⑬ v1.46.1：切页无弹窗 / 滚动增量换卡 ==")
_mw_src = open(os.path.join(ROOT, "src", "main_window.py"), encoding="utf-8").read()
check("切页时收起残留 tooltip", "QToolTip.hideText" in _mw_src)
check("切页销毁旧页（不残留顶层空窗）", "old.setParent(None)" in _mw_src)
check("虚拟化卡片按绝对行坐标摆放（滚动不出空洞）", "row * rh" in _mw_src)
check("虚拟化用绝对定位（不再先清后建）", "_cards" in _mw_src and "setGeometry(" in _mw_src)

# —— 同一实例滚一行：只应新建约 1 行的卡片
_sc2 = mw.QScrollArea(); _h2 = mw.QWidget(); _l2 = mw.QVBoxLayout(_h2)
_l2.setContentsMargins(0, 0, 0, 0)
_data = [{"id": i, "title": "V%d" % i} for i in range(3000)]
_vg2 = mw.LazyGrid(lambda o, l: _data[o:o + l],
                   lambda it: mw.QFrame().setFixedSize(200, 120) or None, len(_data),
                   kind="media", virtual=True)
# 上面 lambda 返回 None，换成品：直接用一个小工厂
class _Box(mw.QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(200, 120)
_vg2._make = lambda it: _Box()
_l2.addWidget(_vg2); _sc2.setWidget(_h2); _sc2.setWidgetResizable(True)
_sc2.resize(900, 700); _sc2.show()
_vg2.attach_scroll(_sc2.verticalScrollBar(), _sc2.viewport())
for _ in range(6):
    app.processEvents()
_vg2._render()
for _ in range(3):
    app.processEvents()
_n0 = len(_vg2._cards)
_made = []
_orig_make = _vg2._make
_vg2._make = lambda it: (_made.append(1), _orig_make(it))[1]
_sb2 = _sc2.verticalScrollBar()
_sb2.setValue(_sb2.value() + _vg2._row_h)
for _ in range(3):
    app.processEvents()
_vg2._render()
check("滚一行只新建约一行卡片（增量换卡）",
      0 < len(_made) <= _vg2._cols * 2, "%d 张 / cols=%d" % (len(_made), _vg2._cols))
check("卡片总数保持在窗口规模", len(_vg2._cards) <= _n0 + _vg2._cols, len(_vg2._cards))
check("滚动后不残留旧窗口外控件", len(_vg2._cards) == len(_vg2._built))
_sc2.close()


# ============================================================
print("== ⑭ v1.46.3：横向滚动条 / 自适应列数 / 窗口尺寸 ==")
check("容器宽度随视口（去掉页面边距，不产生横向条）", "vpw - 40 - 20" in _mw_src)
check("网格页禁用横向滚动条", "ScrollBarAlwaysOff" in _mw_src)
check("列数按宽度自适应", "_cols_now" in _mw_src)
check("按 pitch 均分铺满整行（v1.46.6）", "_pitch" in _mw_src and "pitch" in _mw_src)
check("窗口最小尺寸 1680×960（按屏钳制）", "min(1680, avail.width())" in _mw_src)
win.resize(1920, 1080)
for _ in range(6):
    app.processEvents()
win.go(lambda: win._wall_page("全部"))
for _ in range(12):
    app.processEvents()
_pg = win.stack.currentWidget()
_lg = _pg.widget().findChildren(mw.LazyGrid)[0]
_lg._render()
for _ in range(6):
    app.processEvents()
check("影片墙横向滚动条为 0", _pg.horizontalScrollBar().maximum() == 0,
      _pg.horizontalScrollBar().maximum())
check("列数随宽度自适应（且不超过总数）",
      1 <= _lg._cols_now <= max(1, _lg._total),
      "cols_now=%d total=%d nominal=%d" % (_lg._cols_now, _lg._total, _lg._cols))
_xs = sorted({c.x() for c in _lg._cards.values()}) if _lg._cards else []
_right = max((c.x() + c.width()) for c in _lg._cards.values()) if _lg._cards else 0
_pitch_ok = all(abs((_xs[i + 1] - _xs[i]) - _lg._pitch) <= 1.5
                for i in range(len(_xs) - 1))
check("卡片等距成列、从左边贴齐（不出界）",
      bool(_xs) and _pitch_ok and _xs[0] <= 10 and _right <= _lg._body.width(),
      "cols=%d 左=%d right=%d body=%d" % (len(_xs), _xs[0], _right, _lg._body.width()))
check("海报卡不被拉伸（仍 172 宽）",
      bool(_lg._cards) and all(c.width() == mw.POSTER_CARD_W
                               for c in _lg._cards.values()),
      next(iter(_lg._cards.values())).width() if _lg._cards else -1)


# ============================================================
print("== ⑮ v1.46.4：状态栏进度条 / 本程序内存 ==")
check("全局忙信号总线存在", hasattr(mw, "BUSY") and hasattr(mw, "set_busy"))
_b = getattr(win, "_busy_bar", None)
check("状态栏有常驻进度条", _b is not None and _b.isVisible())


def _wait_busy_idle(_ms=700):
    """v1.46.8：进度条加了「最短可见时长」，断言空闲态前先等它真的回落。"""
    _end = time.monotonic() + _ms / 1000.0
    while time.monotonic() < _end:
        app.processEvents()
        time.sleep(0.005)


mw.set_busy(None)
_wait_busy_idle()
check("空闲态为空槽（不填色）", _b.maximum() == 1 and _b.value() == 0
      and not bool(_b.property("busy")),
      "max=%d v=%d" % (_b.maximum(), _b.value()))
mw.set_busy(-1, "载入中")
app.processEvents()
check("载入中 → 不确定进度且高亮", _b.maximum() == 0 and bool(_b.property("busy")),
      "max=%d busy=%s" % (_b.maximum(), _b.property("busy")))
mw.set_busy(45, "缓存")
app.processEvents()
check("确定进度可显示 45%", _b.maximum() == 100 and _b.value() == 45
      and bool(_b.property("busy")))
mw.set_busy(None)
_wait_busy_idle()
check("回到空闲恢复空槽", _b.maximum() == 1 and _b.value() == 0
      and not bool(_b.property("busy")),
      "max=%d v=%d" % (_b.maximum(), _b.value()))
_qss_txt = open(os.path.join(ROOT, "src", "style.qss"), encoding="utf-8").read()
check("进度条有空槽/高亮两套样式",
      'QProgressBar#BusyBar::chunk' in _qss_txt
      and 'QProgressBar#BusyBar[busy="true"]::chunk' in _qss_txt
      and "transparent" in _qss_txt.split("QProgressBar#BusyBar::chunk")[-1][:200])

# —— 本程序内存
import sysmon as _sm
_pm = _sm.SysMetrics().proc_mem()
check("能读到本进程内存（MB）", _pm is not None and _pm > 0, _pm)
_panel = _sm.SysMonitorPanel()
_panel.apply({"cpu": 10, "mem": 40, "gpu": 5, "proc_mb": 512.0, "net_on": True, "ollama_on": False})
check("实时状态显示本程序内存", "512 MB" in _panel.proc_row.text(),
      _panel.proc_row.text())

# ============================================================
print("== ⑯ v1.46.5：其他数据源（自定义站点取 Cookie） ==")
# —— 网址规整
check("normalize：补 https", sc.normalize_base_url("javdb.com") == "https://javdb.com",
      sc.normalize_base_url("javdb.com"))
check("normalize：保留 http 与路径",
      sc.normalize_base_url("http://a.b.com/x") == "http://a.b.com/x",
      sc.normalize_base_url("http://a.b.com/x"))
check("normalize：空 / 无域名 / 怪 scheme 一律判无效",
      sc.normalize_base_url("") == "" and sc.normalize_base_url("   ") == ""
      and sc.normalize_base_url("localhost") == ""
      and sc.normalize_base_url("ftp://a.b.com") == "")
# —— Cookie 检测（自定义站点路径）
_r = sc.test_cookie_url("", "", 3)
check("test_cookie_url：空网址给可读提示",
      _r["ok"] is False and not _r["has_cookie"] and "网址" in _r["msg"], _r["msg"])
_r2 = sc.test_cookie_url("https://example.invalid", "", 3)
check("test_cookie_url：未取过 cookie → has_cookie=False",
      _r2["ok"] is False and not _r2["has_cookie"], _r2["msg"])
# —— 设置页控件
check("数据源区有「其他数据源」单选与网址框",
      hasattr(dlg, "sc_cf_other") and hasattr(dlg, "sc_other_url")
      and dlg.sc_cf_other.text() == "其他数据源")
_orig_on = bool(dlg.s.scraper.get("other_source_on", False))
_orig_url = str(dlg.s.scraper.get("other_source_url") or "")
dlg.sc_cf_auto.setChecked(True)
app.processEvents()
check("选「自动」时网址框/测试按钮禁用",
      not dlg.sc_other_url.isEnabled() and not dlg.sc_other_test.isEnabled())
dlg.sc_cf_other.setChecked(True)
app.processEvents()
check("两个 radio 互斥（选其他 → 自动取消）",
      dlg.sc_cf_other.isChecked() and not dlg.sc_cf_auto.isChecked())
check("选「其他数据源」后网址框可用", dlg.sc_other_url.isEnabled())
check("单选状态已落盘 other_source_on=True",
      bool(dlg.s.scraper.get("other_source_on")))
dlg.sc_other_url.setText("javdb.com")
dlg._save_other_url()
check("网址保存时自动补全 scheme",
      (dlg.s.scraper.get("other_source_url") or "").startswith("https://javdb.com"),
      dlg.s.scraper.get("other_source_url"))
check("Cookie 目标解析为自定义网址",
      dlg._cookie_target() == ("https://javdb.com", "其他数据源", True),
      str(dlg._cookie_target()))
dlg.sc_other_url.setText("not a url")
dlg._save_other_url()
check("无效网址不进配置（保留上一次的有效值）",
      "not a url" not in (dlg.s.scraper.get("other_source_url") or ""))
# —— 自动目标：真实按 SOURCE_BASES 解析（修「选了 javdb 却去 minnano 取 cookie」）
_src_bak = list(dlg.s.scraper.get("sources", []))
_en_bak = dict(dlg.s.scraper.get("sources_enabled") or {})
dlg.s.scraper["sources"] = ["javdb"]
dlg.s.scraper["sources_enabled"] = {"javdb": True}
dlg.sc_cf_auto.setChecked(True)
app.processEvents()
check("自动目标按 SOURCE_BASES 解析（javdb → JAVDB_BASE）",
      dlg._cookie_target()[0] == sc.JAVDB_BASE, str(dlg._cookie_target()))
dlg.s.scraper["sources"] = _src_bak
dlg.s.scraper["sources_enabled"] = _en_bak
dlg.s.scraper["other_source_on"] = _orig_on
dlg.s.scraper["other_source_url"] = _orig_url
dlg.s.save()
check("冒烟结束后偏好已复位", (dlg.s.scraper.get("other_source_url") or "") == _orig_url)

# ============================================================
print("== ⑰ v1.46.6：演员库/导演库铺满 + 尾部可达 + 复测对象 ==")
# —— 复测对象解析（v1.46.6 反馈 4：原来非 minnano 一律当 imdb）
check("source_of_url：minnano", sc.source_of_url(sc.MINNANO_BASE) == "minnano",
      sc.MINNANO_BASE)
check("source_of_url：avbase", sc.source_of_url(sc.AVBASE_BASE) == "avbase",
      sc.AVBASE_BASE)
check("source_of_url：javdb", sc.source_of_url(sc.JAVDB_BASE) == "javdb")
check("source_of_url：wikipedia", sc.source_of_url(sc.WIKI_BASE) == "wikipedia")
check("source_of_url：自定义站点 → 空", sc.source_of_url("https://example.com") == "")
check("source_of_url：www 前缀容忍",
      sc.source_of_url("https://www.minnano-av.com/actress.html") == "minnano")
check("test_source_url 空网址给可读提示",
      sc.test_source_url("")["ok"] is False and "网址" in sc.test_source_url("")["msg"])
check("TestSourceWorker 支持 as_url（不再写死 imdb）",
      "as_url" in uis.TestSourceWorker.__init__.__code__.co_varnames)
check("_verify_now 不再硬编码 minnano/imdb",
      '"minnano" if "minnano" in self.host_url else "imdb"' not in
      open(os.path.join(ROOT, "src", "ui_settings.py"), encoding="utf-8").read())

# —— 演员库：列数随宽度、铺满、尾部可达
# 造 400 位演员（虚拟化只建可视区那几十张，不会拖慢冒烟）
_conn = db.get_conn()
_conn.executemany(
    "INSERT INTO people (name, role_type, works) VALUES (?,?,?)",
    [("冒烟演员%03d" % i, "Actor", 100 + i) for i in range(400)])
_conn.commit()
_apage = win._view_actors()
win.stack.addWidget(_apage)
win.stack.setCurrentWidget(_apage)
for _ in range(30):
    app.processEvents()
_ag = _apage.findChildren(mw.LazyGrid)[0]
_rows = {}
for _w in (1920, 1680, 1500):
    win.resize(_w, 1080 if _w == 1920 else 960)
    for _ in range(10):
        app.processEvents()
    _ag._scrollbar.setValue(0)
    for _ in range(10):
        app.processEvents()
    _x = sorted({c.x() for c in _ag._cards.values()}) if _ag._cards else []
    _r = max((c.x() + c.width()) for c in _ag._cards.values()) if _ag._cards else 0
    _rows[_w] = (len(_x), _ag._cell_w, _x[0] if _x else -1,
                 _ag._body.width() - _r, _ag._cols_now)
check("演员卡宽度可选（≥236 且 ≤320）",
      all(236 <= v[1] <= 320 for v in _rows.values()),
      {k: v[1] for k, v in _rows.items()})
check("演员库两侧零留白（≤10px）",
      all(v[2] <= 10 and v[3] <= 10 for v in _rows.values()),
      {k: (v[2], v[3]) for k, v in _rows.items()})
check("演员库列数随窗口宽度变化", len({v[4] for v in _rows.values()}) >= 2,
      {k: v[4] for k, v in _rows.items()})
# 尾部可达：以前 total_rows 用标称 6 列算，1680 宽（5 列）时末索引停在 4949
for _w in (1680, 1500):
    win.resize(_w, 960)
    for _ in range(8):
        app.processEvents()
    _ag._scrollbar.setValue(_ag._scrollbar.maximum())
    for _ in range(16):
        app.processEvents()
_idx = sorted(_ag._cards.keys())
check("演员库尾部可达（修「后面不载入」）",
      bool(_idx) and _idx[-1] >= _ag._total - 1 - _ag._cols_now,
      "末索引=%s 总数=%d cols=%d" % (_idx[-1] if _idx else -1, _ag._total, _ag._cols_now))
check("演员卡高度未被拉伸（160）",
      bool(_ag._cards) and all(c.height() == mw.ACTOR_CARD_H for c in _ag._cards.values()),
      next(iter(_ag._cards.values())).height() if _ag._cards else -1)

# —— 导演库（同样造 300 位，验证铺满 + 尾部可达）
_conn.executemany(
    "INSERT INTO people (name, role_type, works) VALUES (?,?,?)",
    [("冒烟导演%03d" % i, "Director", 50 + i) for i in range(300)])
_conn.commit()
win.resize(1920, 1080)
for _ in range(8):
    app.processEvents()
_dpage = win._view_directors()
win.stack.addWidget(_dpage)
win.stack.setCurrentWidget(_dpage)
for _ in range(30):
    app.processEvents()
_dg = _dpage.findChildren(mw.LazyGrid)[0]
_xd = sorted({c.x() for c in _dg._cards.values()}) if _dg._cards else []
_dr = max((c.x() + c.width()) for c in _dg._cards.values()) if _dg._cards else 0
check("导演库两侧零留白（≤10px）",
      bool(_xd) and _xd[0] <= 10 and (_dg._body.width() - _dr) <= 10,
      "左=%d 右=%d body=%d" % (_xd[0] if _xd else -1, _dg._body.width() - _dr,
                               _dg._body.width()))
check("导演卡高度未被拉伸（118）",
      bool(_dg._cards) and all(c.height() == mw.DIRECTOR_CARD_H
                               for c in _dg._cards.values()))
_dg._scrollbar.setValue(_dg._scrollbar.maximum())
for _ in range(16):
    app.processEvents()
_id = sorted(_dg._cards.keys())
check("导演库尾部可达",
      bool(_id) and _id[-1] >= _dg._total - 1 - _dg._cols_now,
      "末索引=%s 总数=%d" % (_id[-1] if _id else -1, _dg._total))

# ============================================================
print("== ⑱ v1.46.7：「全部作品」页网格必须挂上滚动条（修「卡在 48 部」） ==")
# 根因：`_view_actor_detail` 把 `_grid(works)` 套进普通 QWidget 再交给 `_page()`，
# 而 `_page()` 只认 `body_widget.lazy_grid` / `body_widget.attach_scroll` →
# 滚动条从未挂上 → 虚拟网格 y 恒 0、视口高退回 700 兜底 → 只渲染前 5~6 行。
_c2 = db.get_conn()
_c2.execute("DELETE FROM people WHERE name=?", ("冒烟作品演员",))
_c2.execute("INSERT INTO people (name, role_type, works) VALUES (?,?,?)",
            ("冒烟作品演员", "Actor", 200))
_c2.commit()
_pid2 = _c2.execute("SELECT id FROM people WHERE name=?", ("冒烟作品演员",)).fetchone()[0]
_c2.executemany(
    "INSERT INTO media (kind,title,file_path,nfo_path,favorite,play_count,user_rating,library)"
    " VALUES (?,?,?,?,?,?,?,?)",
    [("movie", "WKS-%03d" % i, os.path.join(TMP, "lib", "WKS-%03d.mp4" % i),
      "", 0, 0, 0, "") for i in range(200)])
_c2.commit()
_ids2 = [r[0] for r in _c2.execute(
    "SELECT id FROM media WHERE title LIKE 'WKS-%'").fetchall()]
_c2.executemany(
    "INSERT OR IGNORE INTO media_people (media_id, person_id, char_role, person_order)"
    " VALUES (?,?,?,?)", [(_i, _pid2, "actor", 0) for _i in _ids2])
_c2.commit()
_wpage = win._view_actor_detail(_pid2)
win.stack.addWidget(_wpage)
win.stack.setCurrentWidget(_wpage)
for _ in range(35):
    app.processEvents()
_wg = _wpage.findChildren(mw.LazyGrid)[0]
check("「全部作品」总数 = 200", _wg._total == 200, _wg._total)
check("「全部作品」网格挂上滚动条", _wg._scrollbar is not None,
      "None 表示 _page 没找到网格")
check("「全部作品」网格拿到视口", _wg._viewport is not None)
check("「全部作品」列数为自适应值（>0）", _wg._cols_now > 0, _wg._cols_now)
if _wg._scrollbar is not None:
    check("「全部作品」滚动条能撑出范围（>0）", _wg._scrollbar.maximum() > 0,
          _wg._scrollbar.maximum())
    _wg._scrollbar.setValue(_wg._scrollbar.maximum())
    for _ in range(20):
        app.processEvents()
_wk = sorted(_wg._cards.keys())
check("「全部作品」尾部可达（修「卡在 48 部」）",
      bool(_wk) and _wk[-1] >= _wg._total - 1 - _wg._cols_now,
      "末索引=%s 总数=%d cols=%d" % (_wk[-1] if _wk else -1, _wg._total, _wg._cols_now))

# —— 自愈兜底：网格不经 _page、直接丢进 QScrollArea，也要自己认领滚动条
_sa = QScrollArea()
_sa.setWidgetResizable(True)
_sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
_holder = QWidget()
_hl = QVBoxLayout(_holder)
_hl.setContentsMargins(20, 16, 20, 20)
_g3 = mw.LazyGrid(lambda off, lim: [{"id": 9000 + i, "title": "自愈-%03d" % i}
                                    for i in range(int(lim))],
                  lambda m: mw.PosterCard(m, None, "", ""),
                  300, kind="media", virtual=True)
_hl.addWidget(_g3)
_sa.setWidget(_holder)
_sa.resize(1200, 700)
_sa.show()
for _ in range(30):
    app.processEvents()
check("网格自愈：没被显式 attach 也能认领 QScrollArea",
      _g3._scrollbar is not None and _g3._viewport is not None,
      "sb=%s vp=%s" % (_g3._scrollbar is not None, _g3._viewport is not None))
check("_render 里调用了 _adopt_scroll（源码级）",
      "_adopt_scroll()" in open(os.path.join(ROOT, "src", "main_window.py"),
                                encoding="utf-8").read())
_sa.close()
_sa.deleteLater()
for _ in range(6):
    app.processEvents()

print()
print("== ⑲ v1.46.8：状态栏进度条「载入/缓存中」必须看得见 ==")
# 根因：虚拟网格建一屏卡只要几毫秒，`set_busy(-1)` 紧跟 `set_busy(None)` →
# 朱红还没画出来就回落成空槽，用户看到的一直是空槽（"高亮没了"）。
from PIL import Image as _PILImage
from PySide6.QtGui import QImage as _QImage
import time as _time


def _img_of(_w):
    _im = _w.grab().toImage().convertToFormat(_QImage.Format_RGBA8888)
    _iw, _ih = _im.width(), _im.height()
    _bg = _PILImage.new("RGB", (_iw, _ih), (34, 29, 25))
    _raw = _PILImage.frombytes("RGBA", (_iw, _ih), bytes(_im.constBits()))
    return _PILImage.alpha_composite(_bg.convert("RGBA"), _raw).convert("RGB")


def _accent_n(_im):
    _n = 0
    _px = _im.load()
    for _y in range(_im.height):
        for _x in range(_im.width):
            _r, _g, _b = _px[_x, _y]
            if _r > 110 and _r - _g > 40 and _r - _b > 35:
                _n += 1
    return _n


def _spin(_ms):
    _end = _time.monotonic() + _ms / 1000.0
    while _time.monotonic() < _end:
        app.processEvents()
        _time.sleep(0.004)


_bb = win._busy_bar
mw.set_busy(None, ""); _spin(600)
check("进度条空闲 = 空槽（0 朱红像素）", _accent_n(_img_of(_bb)) == 0,
      _accent_n(_img_of(_bb)))
mw.set_busy(-1, "载入中"); _spin(15)
_n1 = _accent_n(_img_of(_bb))
check("进度条不确定态高亮", _n1 > 0, "朱红像素=%d" % _n1)
mw.set_busy(45, "缓存中"); _spin(15)
_n2 = _accent_n(_img_of(_bb))
check("进度条确定态(45%)高亮", _n2 > 0, "朱红像素=%d" % _n2)
# 核心：快闪（-1 → None 只隔几毫秒）仍要看得见
mw.set_busy(None, ""); _spin(600)
mw.set_busy(-1, "载入中"); mw.set_busy(None, "")
_spin(30)
_n3 = _accent_n(_img_of(_bb))
check("快闪后 30ms 仍可见朱红（最短可见时长）", _n3 > 0,
      "朱红像素=%d（未修时恒为 0）" % _n3)
_spin(700)
check("700ms 后回落空槽（不卡高亮）", _accent_n(_img_of(_bb)) == 0,
      _accent_n(_img_of(_bb)))
check("busy 属性已回 False", bool(_bb.property("busy")) is False)
check("BUSY_MIN_MS 常量存在且 ≥300",
      int(getattr(mw, "BUSY_MIN_MS", 0)) >= 300, getattr(mw, "BUSY_MIN_MS", None))

# 滚动续载也要点亮（D 场景）。
# ⚠ 不能靠 grab 抓像素：`_render()` 是**同步查库**，真库 >1s 期间事件循环被卡住，
# 抓图只能等它返回（那时已回落）。改成断言**上报行为**：滚动必须推出
# `(-1, "缓存中")`，外加源码级确认点亮时走了同步 repaint（阻塞前先画出去）。
_SEEN = []


def _on_busy_probe(_p, _t=""):
    _SEEN.append((_p, _t))


_wall2 = win._wall_page(None)
win.stack.addWidget(_wall2)
win.stack.setCurrentWidget(_wall2)
_spin(600)
_g4 = _wall2.findChildren(mw.LazyGrid)[0]
mw.BUSY.changed.connect(_on_busy_probe)
_g4._scrollbar.setValue(int(_g4._scrollbar.maximum() * 0.3))
_spin(1500)
mw.BUSY.changed.disconnect(_on_busy_probe)
check("滚动换卡时上报「缓存中」", any(_p == -1 and _t == "缓存中" for _p, _t in _SEEN),
      _SEEN[-4:])
_mw_txt = open(os.path.join(ROOT, "src", "main_window.py"), encoding="utf-8").read()
check("点亮时同步 repaint（阻塞前先画出来）", "bar.repaint()" in _mw_txt)
check("BUSY_MIN_MS 已接入 _on_busy 延迟回落",
      "BUSY_MIN_MS" in _mw_txt and "_busy_on_at" in _mw_txt)

# 首页列表载入也必须上报（真机「正在载入列表… 16200 / 48708」时进度条是空槽的真凶）
_SEEN2 = []


def _on_busy_probe2(_p, _t=""):
    _SEEN2.append((_p, _t))


mw.BUSY.changed.connect(_on_busy_probe2)
_home = win._view_home()
win.stack.addWidget(_home)
win.stack.setCurrentWidget(_home)
_spin(1500)
mw.BUSY.changed.disconnect(_on_busy_probe2)
check("首页列表载入上报状态栏进度",
      any(isinstance(_p, (int, float)) and _p >= 0 and _t == "载入列表" for _p, _t in _SEEN2),
      _SEEN2[:4])
_ui_home_txt = open(os.path.join(ROOT, "src", "ui_home.py"), encoding="utf-8").read()
check("ui_home 已接入 set_busy", "def _busy(" in _ui_home_txt
      and "_busy(-1" in _ui_home_txt and "载入列表" in _ui_home_txt)

print()
print("通过 %d/%d" % (TOTAL[0] - len(FAILS), TOTAL[0]))
if FAILS:
    print("失败项:", FAILS)
else:
    print("SMOKE_V1430_ALL_OK")
