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
check("VERSION == v2.0.4", VER.VERSION == "v2.0.4", VER.VERSION)
check("BUILD == 2610290125", VER.BUILD == "2610290125", VER.BUILD)

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
check("QMainWindow 使用不透明底色（v2.0.0：HeroUI 页面底 #0a0a0b）",
      "QMainWindow { background: #0a0a0b; }" in qss)
check("状态栏为不透明面板色（v2.0.0：#111113，hover #17171a；不再是近纯黑 #0f0d0b）",
      "background: #111113" in qss and "background: #17171a" in qss
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
check("滑块把手为 18×18 正圆（radius 9，HeroUI 纯白圆点）",
      "width: 18px; height: 18px; margin: -6px 0; border-radius: 9px;" in _qss2)
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
check("色卡为 28x28 正圆（HeroUI 色点，选中套白环 + 勾）",
      bool(_sw) and all(b.width() == 28 and b.height() == 28 for b in _sw),
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
check("卡片显示 ♀（玫红 #f31260）",
      "♀" in _card_f._name.text() and "#f31260" in _card_f._name.text())
check("卡片显示 ♂（天青 #338ef7）",
      "♂" in _card_m._name.text() and "#338ef7" in _card_m._name.text())
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
    _bg = _PILImage.new("RGB", (_iw, _ih), (17, 17, 19))
    _raw = _PILImage.frombytes("RGBA", (_iw, _ih), bytes(_im.constBits()))
    return _PILImage.alpha_composite(_bg.convert("RGBA"), _raw).convert("RGB")


def _accent_n(_im):
    """数「强调色」像素：与**当前高亮色**三通道差都 <= 46。

    v1 时这里写死判红（r>110 且 r-g>40 且 r-b>35）；v2.0.0 默认色换成 #006fee
    之后那套判据恒为 0（三条断言集体假红）。改成按 ACCENT_RGB 做距离判定，
    换任何高亮色都成立，也不再叫「朱红像素」。
    """
    _ar, _ag, _ab = tuple(mw.ACCENT_RGB)[:3]
    _n = 0
    _px = _im.load()
    for _y in range(_im.height):
        for _x in range(_im.width):
            _r, _g, _b = _px[_x, _y]
            if max(abs(_r - _ar), abs(_g - _ag), abs(_b - _ab)) <= 46:
                _n += 1
    return _n


def _spin(_ms):
    _end = _time.monotonic() + _ms / 1000.0
    while _time.monotonic() < _end:
        app.processEvents()
        _time.sleep(0.004)


_bb = win._busy_bar
mw.set_busy(None, ""); _spin(600)
check("进度条空闲 = 空槽（0 强调色像素）", _accent_n(_img_of(_bb)) == 0,
      _accent_n(_img_of(_bb)))
mw.set_busy(-1, "载入中"); _spin(15)
_n1 = _accent_n(_img_of(_bb))
check("进度条不确定态高亮", _n1 > 0, "强调色像素=%d" % _n1)
mw.set_busy(45, "缓存中"); _spin(15)
_n2 = _accent_n(_img_of(_bb))
check("进度条确定态(45%)高亮", _n2 > 0, "强调色像素=%d" % _n2)
# 核心：快闪（-1 → None 只隔几毫秒）仍要看得见
mw.set_busy(None, ""); _spin(600)
mw.set_busy(-1, "载入中"); mw.set_busy(None, "")
_spin(30)
_n3 = _accent_n(_img_of(_bb))
check("快闪后 30ms 仍可见高亮色（最短可见时长）", _n3 > 0,
      "强调色像素=%d（未修时恒为 0）" % _n3)
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
print("== ⑳ v1.46.9：标题按行数收高 / extrafanart 剧照横条 / 标签增删 ==")
import ui_hero as _uh
import nfo_parser as _nfo

_hero_src = open(os.path.join(ROOT, "src", "ui_hero.py"), encoding="utf-8").read()

# ---- 反馈 1：标题只有 1 行时不该留第 2 行的空白 ----
_host = QWidget()
_host.resize(900, 300)
_hv = QVBoxLayout(_host)
_hv.setContentsMargins(0, 0, 0, 0)
_short = _uh.ElidedLabel("短标题", max_lines=2, px=34)
_long = _uh.ElidedLabel("这是一个足够长的标题" * 6, max_lines=2, px=34)
_hv.addWidget(_short)
_hv.addWidget(_long)
_host.show()
for _ in range(20):
    app.processEvents()
_ls = _short._eff_font_metrics().lineSpacing()
check("反馈1 单行标题只占 1 行高度（不再锁 2 行）",
      _short._lines == 1 and _short.height() <= _ls + 6 + 2,
      "lines=%d h=%d lineSpacing=%d" % (_short._lines, _short.height(), _ls))
check("反馈1 长标题仍是 2 行（并带省略号）",
      _long._lines == 2 and _long.height() > _ls + 6,
      "lines=%d h=%d" % (_long._lines, _long.height()))
check("反馈1 两种行数的高度差正好一行",
      (_long.height() - _short.height()) >= _ls - 2,
      "diff=%d" % (_long.height() - _short.height()))
check("反馈1 高度重算挂在 resize/show 上（防止回退成 __init__ 一次性锁死）",
      "def _apply_lines" in _hero_src and "def resizeEvent" in _hero_src
      and "def showEvent" in _hero_src and "setFixedHeight" in _hero_src)

# ---- 反馈 2：extrafanart 剧照 ----
_mov = os.path.join(TMP, "smoke_stills", "LMC-900")
_st = os.path.join(_mov, "extrafanart")
os.makedirs(_st, exist_ok=True)
from PySide6.QtGui import QPixmap as _QPixmap, QColor as _QColor
for _i in range(4):
    _pm = _QPixmap(320, 180)
    _pm.fill(_QColor(40 + _i * 20, 30, 25))
    _pm.save(os.path.join(_st, "fanart%d.jpg" % (_i + 1)))
_mov_file = os.path.join(_mov, "LMC-900.mp4")
open(_mov_file, "wb").write(b"\x00" * 64)
_mdict = {"file_path": _mov_file, "nfo_path": os.path.join(_mov, "movie.nfo")}
_found = _uh.find_extrafanart(_mdict)
check("反馈2 识别 extrafanart 目录里的 4 张剧照", len(_found) == 4, len(_found))
check("反馈2 自然序（fanart1..4）",
      [os.path.basename(p) for p in _found] == ["fanart%d.jpg" % (i + 1) for i in range(4)],
      [os.path.basename(p) for p in _found])
_empty_dir = os.path.join(TMP, "smoke_no_stills")
os.makedirs(_empty_dir, exist_ok=True)
check("反馈2 无 extrafanart 目录时不误报",
      _uh.find_extrafanart({"file_path": os.path.join(_empty_dir, "x.mp4"),
                            "nfo_path": os.path.join(_empty_dir, "x.nfo")}) == [])
_strip = _uh.StillStrip()
_strip.setFixedSize(500, 160)
_strip_host = QWidget()
from PySide6.QtWidgets import QHBoxLayout as _QHBox, QLabel as _QLabel
_shl = _QHBox(_strip_host)
_shl.setContentsMargins(0, 0, 0, 0)
for _p in _found:
    _lab = _QLabel()
    _lab.setFixedSize(_uh._STILL_W, _uh._STILL_H)
    _lab.setPixmap(_uh.cover_pixmap(_p, _uh._STILL_W, _uh._STILL_H))
    _shl.addWidget(_lab)
_strip.setWidget(_strip_host)
_strip.show()
for _ in range(20):
    app.processEvents()
_sbar = _strip.horizontalScrollBar()
check("反馈2 剧照条可左右滑（横向滚动范围 > 0）", _sbar.maximum() > 0,
      "max=%d viewport=%d" % (_sbar.maximum(), _strip.viewport().width()))
check("反馈2 剧照条不出现竖向滚动条",
      _strip.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff)
_old_v = _sbar.value()
_strip.page(1)
check("反馈2 ‹ › 翻页真的移动了", _sbar.value() > _old_v, _sbar.value())
_strip.setFixedWidth(420)
for _ in range(1):
    app.processEvents()
check("反馈2 详情页把剧照段接进主体（没有该目录则整块不建）",
      "self._extrafanart_section(m)" in _hero_src and "if still_box is not None" in _hero_src)

# ---- 反馈 3：标签 ----
_media_id = db.upsert_media_by_path(
    mode="overwrite", kind="movie", title="SMOKE-900", file_path=_mov_file,
    nfo_path=os.path.join(TMP, "smoke_no_stills", "movie.nfo"))
_mid = db.set_media_tags(_media_id, [" 已看 ", "已看", "", "收藏向"])
check("反馈3 标签落库 + 归一化（去空/去重/去空白）", _mid == "已看,收藏向", _mid)
check("反馈3 库里能读回 tags", (db.get_media(_media_id).get("tags") or "") == "已看,收藏向",
      db.get_media(_media_id).get("tags"))

_nfo_file = os.path.join(TMP, "smoke_tags.nfo")
open(_nfo_file, "w", encoding="utf-8").write(
    '<?xml version="1.0" encoding="utf-8"?>\n<movie>\n  <title>T</title>\n'
    "  <tag>旧标签</tag>\n  <genre>剧情</genre>\n</movie>\n")
check("反馈3 nfo 能解析 <tag>", _nfo.read_tags(_nfo_file) == ["旧标签"], _nfo.read_tags(_nfo_file))
check("反馈3 parse_movie 带出 tags 字段",
      _nfo.parse_movie(_nfo_file).get("tags") == "旧标签",
      _nfo.parse_movie(_nfo_file).get("tags"))
_nfo.write_tags(_nfo_file, ["新标签", "第二个"])
check("反馈3 标签能写回 nfo", _nfo.read_tags(_nfo_file) == ["新标签", "第二个"],
      _nfo.read_tags(_nfo_file))
_genre_left = "<genre>剧情</genre>" in open(_nfo_file, encoding="utf-8").read()
check("反馈3 写标签不动 <genre>（两回事）", _genre_left)
_nfo.write_tags(_nfo_file, [])
check("反馈3 清空标签后不留空节点", _nfo.read_tags(_nfo_file) == [])

import nfo_editor as _nfe
check("反馈3 nfo 编辑器里也有「标签」字段",
      any(k == "tag" and t == "multi" for k, _l, t in _nfe.FIELDS),
      [f[0] for f in _nfe.FIELDS if f[2] == "multi"])
check("反馈3 media 表已有 tags 列",
      "tags" in {r["name"] for r in db.get_conn().execute("PRAGMA table_info(media)").fetchall()})
check("反馈3 详情页有 ＋/－ 按钮与落库调用",
      "添加标签" in _hero_src and "删除标签" in _hero_src
      and "db.set_media_tags" in _hero_src and "nfo_mod.write_tags" in _hero_src)

# 真点一次「＋」：QInputDialog 打桩返回文本，断言按钮 → 落库 → nfo 全链路
_hero_media = db.get_media(_media_id)
_hv2 = _uh.HeroView(dict(_hero_media))
_hv2.resize(1100, 1000)
_hv2.show()
for _ in range(20):
    app.processEvents()
_plus = [b for b in _hv2.findChildren(_uh.QPushButton) if b.text() == "＋"]
check("反馈3 找得到「＋」按钮", len(_plus) == 1, len(_plus))
if _plus:
    _orig_get = _uh.QInputDialog.getText
    _uh.QInputDialog.getText = staticmethod(lambda *a, **k: ("真机标签, 第二个", True))
    try:
        _plus[0].click()
        for _ in range(20):
            app.processEvents()
    finally:
        _uh.QInputDialog.getText = _orig_get
    _saved = db.get_media(_media_id).get("tags") or ""
    check("反馈3 点「＋」后按钮路径真落库", "真机标签" in _saved and "第二个" in _saved, _saved)

print()
print("== ㉑ v1.46.10：演职人员并入基本信息右侧 / 右键搜索框可打中文 ==")
from PySide6.QtCore import QPoint as _QPoint, QEvent as _QEvent
from PySide6.QtGui import QMouseEvent as _QMouseEvent

# ---- 反馈 1：_intro_section 改成「海报 | 基本信息 | 演职人员」三栏 ----
_poster_f = os.path.join(TMP, "smoke_cast_poster.jpg")
_pm = _QPixmap(300, 450)
_pm.fill(_QColor(60, 44, 36))
_pm.save(_poster_f)
_fan_f = os.path.join(TMP, "smoke_cast_fan.jpg")
_pm = _QPixmap(1200, 500)
_pm.fill(_QColor(50, 36, 28))
_pm.save(_fan_f)
_v901 = os.path.join(TMP, "smoke_stills", "SMOKE-901.mp4")
_mid2 = db.upsert_media_by_path(
    mode="overwrite", kind="movie", title="SMOKE-901", year=2026,
    plot="简介一行。", file_path=_v901, library="演示库", genres="剧情",
    poster=_poster_f, fanart=_fan_f)
for _i, (_nm, _role) in enumerate([("枳アリス", "Actor"), ("赤井彗星", "Director")]):
    _pid = db.upsert_person(_nm, role_type=_role)
    db.link_media_person(_mid2, _pid, "", _i)
_hv3 = _uh.HeroView(dict(db.get_media(_mid2)))
_hv3.resize(1200, 1500)
_hv3.show()
for _ in range(30):
    app.processEvents()
check("反馈1 演职人员区块在横向 intro 布局里",
      _hv3._cast_layout is not None and _hv3._cast_layout.indexOf(_hv3._cast_box) >= 0,
      _hv3._cast_layout.indexOf(_hv3._cast_box) if _hv3._cast_layout else None)
check("反馈1 主体竖向布局里不再有它（不再独占一整行）",
      _hv3._body_layout.indexOf(_hv3._cast_box) < 0)
_hw = _hv3.widget()
_poster_lbl = None
_facts_lbl = None
_file_lbl = None
for _w in _hv3.findChildren(_QLabel):
    if _w.text() == "基本信息":
        _facts_lbl = _w
    elif _w.text() == "文件信息":
        _file_lbl = _w
    elif _w.pixmap() is not None and not _w.pixmap().isNull() \
            and _w.width() == 150 and _w.height() == 225:
        _poster_lbl = _w
check("反馈1 找得到海报 / 「基本信息」/「文件信息」",
      _poster_lbl is not None and _facts_lbl is not None and _file_lbl is not None)
_cast_geo = _hv3._cast_box.mapTo(_hw, _QPoint(0, 0))
if _poster_lbl is not None and _facts_lbl is not None:
    _px = _poster_lbl.mapTo(_hw, _QPoint(0, 0)).x()
    _fx = _facts_lbl.mapTo(_hw, _QPoint(0, 0)).x()
    _fy = _facts_lbl.mapTo(_hw, _QPoint(0, 0)).y()
    check("反馈1 顺序：海报 → 基本信息 → 演职人员",
          _px < _fx < _cast_geo.x(),
          "poster=%d facts=%d cast=%d" % (_px, _fx, _cast_geo.x()))
    check("反馈1 演职人员与「基本信息」同一行（不是压到下面）",
          _cast_geo.x() > _fx + 100 and abs(_cast_geo.y() - _fy) <= 24,
          "cast_x=%d facts_x=%d dy=%d" % (_cast_geo.x(), _fx, _cast_geo.y() - _fy))
    check("反馈1 演职人员没有挤到海报下方",
          _cast_geo.y() < _poster_lbl.mapTo(_hw, _QPoint(0, 0)).y() + 225)
if _file_lbl is not None:
    check("反馈1 「文件信息」仍在底部（在演职人员栏下方）",
          _file_lbl.mapTo(_hw, _QPoint(0, 0)).y() > _cast_geo.y() + 60,
          "file.y=%d cast.y=%d" % (_file_lbl.mapTo(_hw, _QPoint(0, 0)).y(), _cast_geo.y()))
_hv3.resize(700, 1400)
for _ in range(25):
    app.processEvents()
check("反馈1 700px 窄栏下不撑出页面级横向滚动条",
      _hv3.horizontalScrollBar().maximum() == 0, _hv3.horizontalScrollBar().maximum())
_old_cb = _hv3._cast_box
_idx_before = _hv3._cast_layout.indexOf(_old_cb)
_hv3._refresh_cast()
for _ in range(10):
    app.processEvents()
check("反馈1 右键替换演员后就地重建、仍插回同一栏位",
      _hv3._cast_box is not _old_cb
      and _hv3._cast_layout.indexOf(_hv3._cast_box) == _idx_before,
      "idx=%s" % _hv3._cast_layout.indexOf(_hv3._cast_box))

# ---- 反馈 2：右键搜索弹层能被激活（输入法的前提）----
_dlg = _uh.PersonSearchDialog(initial="", old_name="八森わかな", parent=_hw.window())
_flags = _dlg.windowFlags()
# Qt.Popup 的值是 0x9（Window|Popup），直接 `flags & Qt.Popup` 会被 Window 位污染，
# 必须先用 WindowType_Mask 取基类型再比。
_base = int(_flags) & int(Qt.WindowType_Mask)
check("反馈2 基类型是 Dialog 不是 Popup（Popup 不被激活 → 输入法挂不上）",
      _base == int(Qt.Dialog)
      and _base != (int(Qt.Popup) & int(Qt.WindowType_Mask)),
      "base=0x%x flags=0x%x" % (_base, int(_flags)))
check("反馈2 仍是无边框面板", (int(_flags) & int(Qt.FramelessWindowHint)) != 0)
check("反馈2 窗口允许激活（WA_ShowWithoutActivating 为假）",
      not _dlg.testAttribute(Qt.WA_ShowWithoutActivating))
check("反馈2 输入框接受输入法事件（WA_InputMethodEnabled + ImhNone）",
      _dlg._edit.testAttribute(Qt.WA_InputMethodEnabled)
      and _dlg._edit.inputMethodHints() == Qt.ImhNone,
      "attr=%s hints=%s" % (_dlg._edit.testAttribute(Qt.WA_InputMethodEnabled),
                            _dlg._edit.inputMethodHints()))
_dlg.move_to(_QPoint(600, 400))
_dlg.show()
for _ in range(15):
    app.processEvents()
check("反馈2 弹出后装了「点外面关闭」过滤器", _dlg._outside is not None)
check("反馈2 输入框拿到焦点", _dlg._edit.hasFocus())
_vis_before = _dlg.isVisible()
_dlg._outside.eventFilter(
    _dlg, _QMouseEvent(_QEvent.MouseButtonPress, _QPoint(-50, -50), _QPoint(-50, -50),
                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
for _ in range(5):
    app.processEvents()
check("反馈2 点面板外面会关闭（原 Qt.Popup 自带能力已补回）",
      _vis_before and not _dlg.isVisible())
check("反馈2 关闭后事件过滤器已摘除（不泄漏）", _dlg._outside is None)
check("反馈2 源码里不再用 Qt.Popup 做输入弹层",
      "Qt.Popup | Qt.FramelessWindowHint" not in _hero_src
      and "class ClickOutsideCloser" in _hero_src)

print()
print("== ㉒ v1.46.11：列表右键批量操作 / 首页悬停不再叠加 ==")
import inspect as _inspect
import ui_home as _uhome

_calls = []
_lvx = _uhome.HomeListView(on_bulk_action=lambda a, ms: _calls.append((a, len(ms))))
_lvx.resize(1100, 760)
_lvx.show()
for _ in range(60):
    app.processEvents()

check("反馈1 表格走自定义右键菜单",
      _lvx.table.contextMenuPolicy() == Qt.CustomContextMenu,
      _lvx.table.contextMenuPolicy())
_ctx_src = _inspect.getsource(_uhome.HomeListView._on_context_menu)
check("反馈1 右键命中用 viewport 坐标（customContextMenuRequested 实测给的就是它）",
      "self.table.indexAt(pos)" in _ctx_src and "mapFrom(self.table, pos)" not in _ctx_src)

_lvx.table.clearSelection()
_lvx.table.selectRow(0)
_one = _lvx.selected_medias()
check("反馈1 单选 → selected_medias 1 项", len(_one) == 1, len(_one))
_m1 = _lvx._build_context_menu(_one)
_t1 = [a.text() for a in _m1.actions() if not a.isSeparator()]
check("反馈1 五项且顺序固定",
      _t1 == ["播放选中视频", "打开视频文件夹", "刷新数据", "删除数据", "删除源文件"], _t1)
check("反馈1 单选时不加数量后缀", all("项）" not in t for t in _t1), _t1)

_lvx.table.selectAll()
_many = _lvx.selected_medias()
check("反馈1 全选 → selected_medias 拿到全部行",
      len(_many) == _lvx.table.rowCount() and len(_many) >= 2, len(_many))
_m2 = _lvx._build_context_menu(_many)
_t2 = [a.text() for a in _m2.actions() if not a.isSeparator()]
check("反馈1 多选时每项都带「（N 项）」",
      all(t.endswith("（%d 项）" % len(_many)) for t in _t2), _t2)
_acts = getattr(_m2, "_actions_by_key", {})
check("反馈1 五个动作键齐全",
      set(_acts) == {"play", "folder", "refresh", "delete_index", "delete_files"},
      sorted(_acts))
if _acts:
    _acts["refresh"].trigger()
check("反馈1 点菜单真的回调到主窗口（动作键 + 整批）",
      _calls and _calls[-1] == ("refresh", len(_many)), _calls)

# 就地回写：删一条 / 刷一条
_n0, _r0 = len(_lvx._view), _lvx.table.rowCount()
_victim = _lvx._view[0]
_lvx.drop_ids([_victim.get("id")])
check("反馈1 drop_ids 同时减 _view 与表格行",
      len(_lvx._view) == _n0 - 1 and _lvx.table.rowCount() == _r0 - 1,
      str((len(_lvx._view), _lvx.table.rowCount())))
_tgt = _lvx._view[0]
db.update_media_fields(_tgt["id"], title="SMOKE-REFRESHED")
_hit = _lvx.refresh_ids([_tgt["id"]])
check("反馈1 refresh_ids 从库里读回最新值", _hit == 1 and _tgt.get("title") == "SMOKE-REFRESHED",
      str((_hit, _tgt.get("title"))))

# 反馈 2：悬停叠层的两个来源
_setrow_src = _inspect.getsource(_uhome.HomeListView._set_row)
check("反馈2 单元格不再挂 tooltip（与悬停卡叠层的来源）",
      "item.setToolTip" not in _setrow_src, "item.setToolTip" in _setrow_src)
_qss_src = open(os.path.join(ROOT, "src", "style.qss"), encoding="utf-8").read()
_card_seg = _qss_src.split("QFrame#HoverCard")[1][:180]
check("反馈2 悬停卡不再半透明（v2.0.0：#18181b，列表文字不会透上来）",
      "#18181b" in _card_seg and "__DLG__" not in _card_seg, _card_seg.split("}")[0])
_pvx = _lvx._preview
# 用一份字段齐全的 media 喂卡片（列表里的行不一定都带 year/studio，别让断言依赖数据）
_pvx.set_media({"title": "卡片完整度 SMOKE", "year": 2026, "runtime": "01:12:00",
                "rating": 4.5, "actors_text": "三上悠亜", "genres": "剧情",
                "studio": "同人配信", "premiere": "2026-10-01"})
check("反馈2 悬停卡信息完整（标题 / 副行 / 演员类型制片上映）",
      _pvx.title.text() and _pvx.sub.text() and "制片" in _pvx.info.text(),
      str((_pvx.title.text()[:12], _pvx.sub.text(),
           _pvx.info.text().replace("\n", " | "))))

# 删除源文件走回收站（真调 SHFileOperationW，不触碰真实媒体文件）
_vfile = os.path.join(TMP, "smoke_recycle.txt")
open(_vfile, "w", encoding="utf-8").write("x")
_okr, _badr = mw.MainWindow._recycle_paths(None, [_vfile])
check("反馈1 删源文件走回收站（文件确实消失、无失败）",
      _okr == [_vfile] and not _badr and not os.path.exists(_vfile), str((_okr, _badr)))
_okm, _badm = mw.MainWindow._recycle_paths(None, [os.path.join(TMP, "smoke_missing.mp4")])
check("反馈1 文件已不存在 → 只清索引，不报错", _okm and not _badm, str((_okm, _badm)))

print()
print("== ㉓ v1.46.12：偏好导入 / 导出的进度（后台线程，不再「未响应」） ==")

# ---- prefs 侧：progress 回调 ----
_ev = []
_xjson = os.path.join(TMP, "prefs_prog.json")
_rp = prefs_mod.export_prefs(_xjson, "all", None,
                             progress=lambda a, b, c: _ev.append((a, b, c)))
check("导出接受 progress 回调并上报", _rp.get("ok") and len(_ev) >= 3, str(len(_ev)))
check("导出首条是不定长阶段（读库前 total=0）", _ev[0][1] == 0, str(_ev[0]))
check("导出随后转定量（total=行数）", any(b > 0 for _a, b, _c in _ev),
      str([b for _a, b, _c in _ev]))
check("导出最后一条是「写入文件」", "写入文件" in _ev[-1][2], _ev[-1][2])

_cx = os.path.join(TMP, "prefs_cancel.json")
_n = {"n": 0}


def _cancel_cb(a, b, c):
    _n["n"] += 1
    return _n["n"] >= 2                 # 第二次回调起要求停止


_rc = prefs_mod.export_prefs(_cx, "all", None, progress=_cancel_cb)
check("导出中止 → cancelled=True 且不生成文件",
      _rc.get("cancelled") is True and not os.path.exists(_cx), str(_rc))

# ---- import 侧同样有进度 / 可中止 ----
_imp = {"type": "lmc-prefs", "app": VER.APP_NAME, "version": VER.FULL_VERSION,
        "exported_at": "2026-10-28 00:00:00",
        "media": [{"num": "smoke-0001", "favorite": 1}],
        "people": [{"name": "冒烟演员", "role_type": "Actor", "favorite": 1}]}
_jp = os.path.join(TMP, "prefs_import.json")
with open(_jp, "w", encoding="utf-8") as _f:
    json.dump(_imp, _f, ensure_ascii=False)
_ev2 = []
_r3 = prefs_mod.import_prefs(_jp, dry_run=True,
                             progress=lambda a, b, c: _ev2.append((a, b, c)))
_lab2 = [c for _a, _b, c in _ev2]
check("导入成功且上报了阶段", _r3.get("ok") and len(_ev2) >= 4, str(len(_ev2)))
check("导入有「建立番号索引」阶段", any("番号索引" in c for c in _lab2), str(_lab2[:2]))
check("导入有「合并影片」阶段", any("合并影片" in c for c in _lab2))
check("导入有「合并人物」阶段", any("合并人物" in c for c in _lab2))
check("导入 dry_run 不标取消", not _r3.get("cancelled"), str(_r3.get("cancelled")))
_n2 = {"n": 0}


def _cancel_cb2(a, b, c):
    _n2["n"] += 1
    return _n2["n"] >= 1


_r4 = prefs_mod.import_prefs(_jp, dry_run=True, progress=_cancel_cb2)
check("导入中止 → cancelled=True（合并前就停，命中 0）",
      _r4.get("ok") and _r4.get("cancelled") is True and _r4.get("media_ok") == 0,
      str({k: _r4.get(k) for k in ("ok", "cancelled", "media_ok")}))

# ---- UI 侧：后台线程 + 忙碌态 + 停止 ----
from PySide6.QtWidgets import QMessageBox as _QMB
_src_ui = open(os.path.join(ROOT, "src", "ui_settings.py"), encoding="utf-8").read()
check("新增 PrefsWorker（QThread 子类）",
      hasattr(uis, "PrefsWorker") and getattr(uis.PrefsWorker, "__mro__", None)
      and "QThread" in [c.__name__ for c in uis.PrefsWorker.__mro__])
check("导入/导出不再在 GUI 线程直接调 prefs（都交给 worker）",
      "prefs_mod.export_prefs(path" not in _src_ui
      and "prefs_mod.import_prefs(path" not in _src_ui
      and "PrefsWorker(mode, path" in _src_ui)
check("关闭工具窗会先停偏好线程（避免 QThread 被销毁 abort）",
      '"_prefs_worker", None' in _src_ui
      and "pw.request_stop()" in _src_ui and "pw.wait(" in _src_ui)
check("导航忙碌映射含「数据管理」", '("_prefs_worker", "数据管理")' in _src_ui)

_dlg = uis.SettingsDialog(None)
_dlg.show()                       # 不 show 的话子控件 isVisible() 恒为 False
_dlg._show("数据管理")
for _ in range(5):
    app.processEvents()
check("进度行默认隐藏", not _dlg.pref_prog_row.isVisible())
check("停止按钮默认隐藏", not _dlg.pref_stop.isVisible())

# 用「慢速导出」替身验忙碌态与停止（真导出太快，断言会跟线程赛跑）
_orig_export = prefs_mod.export_prefs


def _slow_export(path, scope="all", include=None, progress=None):
    for _i in range(11):
        time.sleep(0.02)
        if progress and progress(_i * 10, 100, "冒烟导出 %d/100" % (_i * 10)):
            return {"ok": False, "cancelled": True}
    return {"ok": True, "path": path, "media": 0, "people": 0, "no_code": 0}


_q_info, _q_warn = _QMB.information, _QMB.warning
_QMB.information = staticmethod(lambda *a, **k: None)
_QMB.warning = staticmethod(lambda *a, **k: None)
prefs_mod.export_prefs = _slow_export
try:
    _dlg._prefs_run("export", os.path.join(TMP, "ui_async.json"),
                    ["favorite", "play", "rating", "people", "gender"])
    check("启动后两个按钮禁用",
          not _dlg.pref_ex.isEnabled() and not _dlg.pref_im.isEnabled())
    check("启动后进度行 / 停止按钮可见",
          _dlg.pref_prog_row.isVisible() and _dlg.pref_stop.isVisible())
    check("启动后先是不定长进度条", _dlg.pref_bar.maximum() == 0,
          _dlg.pref_bar.maximum())
    # 让 worker 先吐几条真进度
    _t0 = time.time()
    while time.time() - _t0 < 0.12:
        app.processEvents()
        time.sleep(0.005)
    check("跑起来后进度条转定量并跟随",
          _dlg.pref_bar.maximum() == 100 and _dlg.pref_bar.value() > 0,
          str((_dlg.pref_bar.maximum(), _dlg.pref_bar.value())))
    check("状态文字是当前阶段", "冒烟导出" in _dlg.pref_status.text(),
          _dlg.pref_status.text())
    check("过程中按钮保持禁用（不会重复触发）", not _dlg.pref_ex.isEnabled())
    _dlg._stop_prefs()
    check("点停止 → 置停止标志 + 停用停止按钮",
          getattr(_dlg._prefs_worker, "_stop", False) is True
          and not _dlg.pref_stop.isEnabled())
    _t0 = time.time()
    while _dlg._prefs_running() and time.time() - _t0 < 20:
        app.processEvents()
        time.sleep(0.01)
    for _ in range(6):
        app.processEvents()
        time.sleep(0.01)
    check("停止后后台线程已结束", not _dlg._prefs_running())
    check("停止后按钮恢复", _dlg.pref_ex.isEnabled() and _dlg.pref_im.isEnabled())
    check("停止后进度行隐藏", not _dlg.pref_prog_row.isVisible())
    check("停止后提示写明已取消", "取消" in _dlg.pref_hint.text(), _dlg.pref_hint.text())
finally:
    prefs_mod.export_prefs = _orig_export
    _QMB.information, _QMB.warning = _q_info, _q_warn
_dlg.close()

print("== ㉔ v1.46.13：扫描逐路径自上而下 / 边扫边出 / 底部扫描状态与进度条 ==")

import inspect

import scanner as _scanner

# ---- ① 扫描器：每个处理过的条目都回报（**含已存在**，否则百分比永远 0%） ----
_scanroot = os.path.join(TMP, "scan_lib")
_pa = os.path.join(_scanroot, "path-1")
_pb = os.path.join(_scanroot, "path-2")
for _p, _tag in ((_pa, "A"), (_pb, "B")):
    _d = os.path.join(_p, "S_" + _tag)
    os.makedirs(_d, exist_ok=True)
    with open(os.path.join(_d, "movie.nfo"), "w", encoding="utf-8") as _f:
        _f.write('<?xml version="1.0" encoding="UTF-8"?>'
                 '<movie><title>%s</title><year>2021</year></movie>' % _tag)
    with open(os.path.join(_d, "S_%s.mp4" % _tag), "wb") as _f:
        _f.write(b"\0" * 1024)

_it1 = []
_r1 = _scanner.scan_library(_pa, None, library_name="冒烟库", mode="new",
                            on_item=lambda d: _it1.append(dict(d)), path_index=1, path_total=2)
check("on_item：新条目回报 1 条且标 new",
      len(_it1) == 1 and _it1[0]["new"] is True, _it1)
check("on_item：带 path_index / path_total",
      _it1 and _it1[0]["index"] == 1 and _it1[0]["total"] == 2, _it1)
_it2 = []
_r2 = _scanner.scan_library(_pa, None, library_name="冒烟库", mode="new",
                            on_item=lambda d: _it2.append(dict(d)), path_index=1, path_total=2)
check("on_item：已存在的条目也回报（v1.46.13 之前是 0 条 → 进度恒 0%）",
      len(_it2) == 1 and _it2[0]["new"] is False, _it2)
check("scan_library：不传 on_item 也不报错（老调用点兼容）",
      _scanner.scan_library(_pa, None, library_name="冒烟库", mode="new").get("movie") == 0)

# ---- ② ScanWorker：按传入顺序逐条扫 + 进度口径是「已处理/总数」 ----
_wk = mw.ScanWorker([_pa, _pb], library_name="冒烟库", mode="new")
_tk, _lv, _dn = [], [], []
_wk.tick.connect(lambda d, t, m: _tk.append((d, t, m)))
_wk.live.connect(lambda: _lv.append(1))
_wk.done.connect(lambda c: _dn.append(dict(c)))
_wk.run()
_seq = []
for _dd, _tt, _mm in _tk:
    for _s in _mm.split(" · "):
        if _s.startswith("路径 ") and _s not in _seq:
            _seq.append(_s)
check("ScanWorker：按传入顺序逐条扫（路径 1/2 → 2/2）", _seq == ["路径 1/2", "路径 2/2"], _seq)
check("ScanWorker：最后一条 tick 是定量 2/2",
      bool(_tk) and _tk[-1][0] == 2 and _tk[-1][1] == 2,
      str(_tk[-1]) if _tk else "")
check("ScanWorker：有新片才发 live（边扫边刷新）", len(_lv) >= 1, len(_lv))
check("ScanWorker：done 带统计", _dn and "movie" in _dn[0], _dn)
_wk2 = mw.ScanWorker([_pa, _pb], library_name="冒烟库", mode="new", quiet=True)
_tk2 = []
_wk2.tick.connect(lambda d, t, m: _tk2.append(1))
_wk2.run()
check("ScanWorker(quiet=True)：后台扫描不上报 tick", len(_tk2) == 0, len(_tk2))

# ---- ③ 底部状态栏三态（真 MainWindow） ----
win._scan_begin("冒烟库", 2, "新添加和修改的")
check("开始：底部写出扫描情况（库名+模式+路径数）",
      win._scan_lbl.isVisible()
      and all(x in win._scan_lbl.text() for x in ("冒烟库", "新添加和修改的", "2 个路径")),
      win._scan_lbl.text())
check("开始：进度条交给扫描独占（BusyBus 暂时断开）",
      getattr(win, "_scan_busy_owned", False) is True
      and getattr(win, "_busy_bus_on", True) is False)
check("开始：起步是不定长", win._busy_bar.maximum() == 0, win._busy_bar.maximum())
win._on_scan_tick("冒烟库", 1, 4, "扫描 冒烟库 · 路径 1/2 · path-1 · 1/4")
check("进行中：进度条定量 25%",
      win._busy_bar.maximum() == 100 and win._busy_bar.value() == 25,
      str((win._busy_bar.maximum(), win._busy_bar.value())))
check("进行中：文字就是扫描文案（不再弹 toast）",
      win._scan_lbl.text().endswith("1/4"), win._scan_lbl.text())
check("进行中：进度条已点亮（busy=True）", win._busy_bar.property("busy") is True)
win._scan_end()
check("结束：文字收回", not win._scan_lbl.isVisible())
check("结束：进度条还给 BusyBus",
      getattr(win, "_busy_bus_on", False) is True
      and getattr(win, "_scan_busy_owned", True) is False)

# ---- ④ 结构自检（这些是「静默失效」的高危点，必须钉住） ----
_src_mw = inspect.getsource(mw)
check("_scan_library_cat 原样传 paths（不乱序）+ 接上 tick/live/done",
      "ScanWorker(paths, library_name=name, mode=mode)" in _src_mw
      and "_on_scan_tick(N, d, t, m)" in _src_mw
      and "_scan_end()" in _src_mw)
check("_on_scan_live 会刷新影片墙（且认得出套了一层的网格）",
      "live_reload()" in inspect.getsource(mw.MainWindow._on_scan_live)
      and "findChildren(LazyGrid)" in inspect.getsource(mw.MainWindow._on_scan_live))
check("LazyGrid 有 count_fn / live_reload / _upgrade_virtual",
      "count_fn" in inspect.signature(mw.LazyGrid.__init__).parameters
      and hasattr(mw.LazyGrid, "live_reload") and hasattr(mw.LazyGrid, "_upgrade_virtual"))
check("空库建页也能升级为窗口化（_virtual 不是死路）",
      "_upgrade_virtual" in inspect.getsource(mw.LazyGrid.live_reload))
check("_wall_page 传入 count_fn（总数能跟着扫描变）",
      "count_fn=lambda: db.count_media" in inspect.getsource(mw.MainWindow._wall_page))
check("_page 把标题标签挂到页面上（扫描中改「（N 部）」用）",
      "scroll.title_lbl = ttl" in inspect.getsource(mw.MainWindow._page))
import ui_home as _ui_home
check("首页 live_refresh 有自适应节流（不再固定 1.2s 死刷全库）",
      "_live_next_at" in inspect.getsource(_ui_home.HomeListView.live_refresh))
check("后台定时扫描走 quiet=True", "quiet=True" in _src_mw)
_src_qss = open(os.path.join(ROOT, "src", "style.qss"), encoding="utf-8").read()
check("QSS：有 #ScanNote，且没有多余的第二条进度条（ScanBar）",
      "QLabel#ScanNote" in _src_qss and "ScanBar" not in _src_qss)

# =============== ㉕ v1.46.14：「我的评分」去掉空按钮块 + 宽度收到内容 ===============
print("== ㉕ v1.46.14：「我的评分」对话框（错位 / 左右留空）==")
from PySide6.QtWidgets import QAbstractSpinBox, QSizePolicy, QLabel
import ui_hero

rd = ui_hero.RateDialog(None, 7.5)
rd.show()
for _ in range(4):
    app.processEvents()

# v2.0.2（反馈 3）：v1.46.14 当时因为箭头画不出来改成了 NoButtons；
# v2.0.1 的 glyphs + `image:` 方案已让箭头真机可见，本版恢复 UpDownArrows。
check("数值框恢复了上下微调按钮（v2.0.2：箭头已能靠 image: 画出来）",
      rd.spin.buttonSymbols() == QAbstractSpinBox.UpDownArrows, rd.spin.buttonSymbols())
check("数值框改成撑满整行（不再是 setFixedWidth(140)）",
      rd.spin.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
      and rd.spin.minimumWidth() >= 120
      and rd.spin.maximumWidth() > 1000,
      str((rd.spin.sizePolicy().horizontalPolicy(), rd.spin.minimumWidth(),
           rd.spin.maximumWidth())))
check("数值框真的铺到右内边距（右侧不再空 130px）",
      rd.spin.geometry().right() >= rd.width() - 17,
      str((rd.spin.geometry().right(), rd.width())))
check("窗口宽度收紧（302 → 240，留 ±8 余量）",
      200 <= rd.sizeHint().width() <= 248, rd.sizeHint().width())

_btns = {b.text(): b for b in rd.findChildren(QPushButton)}
check("三个按钮都在（清除 / 取消 / 确定）",
      set(_btns) >= {"清除", "取消", "确定"}, str(sorted(_btns)))
if {"清除", "取消", "确定"} <= set(_btns):
    g_clear, g_cancel, g_ok = (_btns["清除"].geometry(), _btns["取消"].geometry(),
                              _btns["确定"].geometry())
    check("「清除」贴左（左下不再空 82px）", g_clear.x() <= 17, g_clear.x())
    check("「清除」与「取消/确定」之间有分组间距",
          g_cancel.x() - (g_clear.x() + g_clear.width()) >= 20,
          g_cancel.x() - (g_clear.x() + g_clear.width()))
    check("「确定」贴右内边距", g_ok.right() >= rd.width() - 17,
          str((g_ok.right(), rd.width())))
    check("顺序：清除 → 取消 → 确定", g_clear.x() < g_cancel.x() < g_ok.x())

_hint = [w for w in rd.findChildren(QLabel) if "范围" in w.text()]
check("提示文字不再重复「清除」的作用（已挪进按钮 tooltip）",
      bool(_hint) and "清除" not in _hint[0].text()
      and "清除" in _btns["清除"].toolTip(),
      _hint[0].text() if _hint else "没找到提示标签")

# 行为不许回归：NoButtons 下键盘/代码仍能步进；确定回写、清除置空
_before = rd.spin.value()
rd.spin.stepBy(1)
check("去掉按钮后仍能步进（键盘 ↑↓ / 滚轮照常）",
      abs(rd.spin.value() - (_before + 0.1)) < 1e-6, str((_before, rd.spin.value())))
rd.spin.setValue(6.3)
rd._ok()
check("「确定」把当前分值回写到 value（v1.19.0 反馈 100 不许回归）",
      abs(rd.value - 6.3) < 1e-6, rd.value)
rd2 = ui_hero.RateDialog(None, None)
rd2._clear()
check("「清除」把 value 置空", rd2.value is None, rd2.value)
check("空评分打开时数值框显示 0.0（不是空）",
      abs(rd2.spin.value()) < 1e-9, rd2.spin.value())
rd.close()
rd2.close()

# =============== ㉖ v1.46.15：压缩「已配置的媒体库」列表高度 ===============
print("== ㉖ v1.46.15：「服务管理 → 已配置的媒体库」列表行距压紧 ==")

# 本段要量「真实样式下的几何」，必须先上全局样式表（前面各段都没上）。
mw.load_style(app)

_s3 = cfg.get_settings()
_orig_libs = _s3.libraries
_LIBS3 = [
    {"name": "Javlibrary", "kind": "电影",
     "paths": ["D:/a%d" % _i for _i in range(14)], "filter": {}},
    {"name": "Jav-VR", "kind": "电影", "paths": ["D:/vr"], "filter": {}},
    {"name": "Jav-临时", "kind": "混合", "paths": ["D:/tmp"], "filter": {}},
]
_dlg3 = uis.SettingsDialog(None)
_dlg3.resize(uis.SettingsDialog.DEF_W, uis.SettingsDialog.DEF_H)
_dlg3.show()                       # 不 show 几何恒为 0
_dlg3._show("服务管理")
_dlg3.s.libraries = [dict(_x) for _x in _LIBS3]
_dlg3._rebuild_lib_list()
for _ in range(10):
    app.processEvents()

_lst = _dlg3.lib_list
check("LIB_ROW_H 压到 44（原 54；28px 按钮 + 行内边距 8 仍放得下）",
      uis.LIB_ROW_H == 44, uis.LIB_ROW_H)
check("列表余量抽成常量 LIST_CHROME = 6（原写死的 +10 是给 5px item padding 留的）",
      uis.LIST_CHROME == 6, uis.LIST_CHROME)
check("该列表单独命名 LibList（QSS 命名作用域只影响它，不动全站）",
      _lst.objectName() == "LibList", _lst.objectName())
check("3 个库时列表高 == min(3,4)*44 + 6 == 138（原 172）",
      _lst.height() == 3 * uis.LIB_ROW_H + uis.LIST_CHROME, _lst.height())

_rows = []
for _i in range(_lst.count()):
    _it = _lst.item(_i)
    _w = _lst.itemWidget(_it)
    _r = _lst.visualItemRect(_it)
    _rows.append((_it.sizeHint().height(), _r.height(),
                  _w.height() if _w is not None else -1, _w))
check("每项 sizeHint 高跟着 LIB_ROW_H 走（3 行都是 44）",
      [_x[0] for _x in _rows] == [44, 44, 44], str([_x[0] for _x in _rows]))
check("visualRect 高 = 44 —— item padding 已从 5px 压到 2px",
      [_x[1] for _x in _rows] == [44, 44, 44], str([_x[1] for _x in _rows]))
check("交给 setItemWidget 的行控件高 = 40（原 44；h 差 10 → 4）",
      [_x[2] for _x in _rows] == [uis.LIB_ROW_H - 4] * 3, str([_x[2] for _x in _rows]))

_btn_ok, _btn_dbg = True, []
for _i, (_sh, _vr, _rh, _w) in enumerate(_rows):
    if _w is None:
        _btn_ok = False
        _btn_dbg.append("item%d 没挂行控件" % _i)
        continue
    _bs = _w.findChildren(QPushButton)
    if len(_bs) != 3:
        _btn_ok = False
        _btn_dbg.append("item%d 按钮数 %d" % (_i, len(_bs)))
    for _b in _bs:
        _g = _b.geometry()
        if _g.height() != 28 or _g.y() < 0 or _g.y() + _g.height() > _rh:
            _btn_ok = False
        if _i == 0:
            _btn_dbg.append("%s:%dpx@%d" % (_b.text(), _g.height(), _g.y()))
check("三个按钮仍是完整 28px、且不越出行控件（v1.14.0 反馈 6 不许回归）",
      _btn_ok, str(_btn_dbg))

# v1.46.15 重打（用户真机截图：「压缩后这些按钮显示不全了」）：根因是**按钮内边距**——
# 全局 QSS `QPushButton{padding:7px 14px}` 让 28px 高的框只剩 12px 内容区，字上下各被切 3px。
_btns0 = _rows[0][3].findChildren(QPushButton) if _rows[0][3] is not None else []
check("三个按钮都走了 compact_button（带 compact 属性 → QSS 内边距压成 0）",
      bool(_btns0) and all(b.property("compact") == "1" for b in _btns0),
      str([b.property("compact") for b in _btns0]))
check("按钮的 sizeHint 高不再超过实际高度（内边距没把内容区压负）",
      bool(_btns0) and all(b.sizeHint().height() <= b.height() for b in _btns0),
      str([(b.sizeHint().height(), b.height()) for b in _btns0]))
check("按钮尺寸仍是 56×28（宽度给足两个字，行内不挤压）",
      bool(_btns0) and all((b.width(), b.height()) == (56, 28) for b in _btns0),
      str([(b.width(), b.height()) for b in _btns0]))
check("3 个库时不出竖向滚动条",
      _lst.verticalScrollBar().maximum() == 0,
      _lst.verticalScrollBar().maximum())

# 条目数超过 4：高度封顶在 4 行，其余靠滚动
_dlg3.s.libraries = [_x for _x in _LIBS3] + [
    {"name": "L%d" % _i, "kind": "电影", "paths": ["D:/z%d" % _i], "filter": {}}
    for _i in range(3)]
_dlg3._rebuild_lib_list()
for _ in range(4):
    app.processEvents()
check("6 个库时高度封顶 4*44 + 6 == 182（不再无脑按条目数长高）",
      _dlg3.lib_list.height() == 4 * uis.LIB_ROW_H + uis.LIST_CHROME,
      _dlg3.lib_list.height())
check("6 个库时确实出现竖向滚动条",
      _dlg3.lib_list.verticalScrollBar().maximum() > 0,
      _dlg3.lib_list.verticalScrollBar().maximum())

# 空库分支：也必须走 LIST_CHROME，否则会多出一条空白
_dlg3.s.libraries = []
_dlg3._rebuild_lib_list()
for _ in range(4):
    app.processEvents()
check("空库分支同样用 LIB_ROW_H + LIST_CHROME（不再写死 +10）",
      _dlg3.lib_list.height() == uis.LIB_ROW_H + uis.LIST_CHROME,
      _dlg3.lib_list.height())

_qss = open(os.path.join(ROOT, "src", "style.qss"), encoding="utf-8").read()
check("QSS 里给 #LibList::item 单独把 padding 压到 2px",
      "QListWidget#LibList::item" in _qss and "padding: 2px 4px" in _qss)
_seg = _qss.split("QListWidget#LibList::item", 1)[1].split("}", 1)[0]
check("该选择器只改 padding，不写 height/min-height（否则盖掉按条目数自适应）",
      "height" not in _seg, _seg.strip().replace("\n", " ")[:60])

_dlg3.close()
_s3.libraries = _orig_libs

# =============== ㉗ v2.0.0：组件套件切 HeroUI 暗色语言 ===============
print("== ㉗ v2.0.0：HeroUI 组件套件 / 色板迁移 / 拖拽条原样保留 ==")
import ui_actorcheck as uac

# ---- 色板 ----
check("色板换成 HeroUI 语义 12 色（v2.0.1 在玫红后补「粉色」）",
      len(cfg.ACCENT_COLORS) == 12, len(cfg.ACCENT_COLORS))
check("默认高亮色是 HeroUI primary #006fee",
      cfg.ACCENT_DEFAULT == "#006fee", cfg.ACCENT_DEFAULT)
check("色板里每个 hex 都合法且不重复",
      len({h for _n, h in cfg.ACCENT_COLORS}) == 12
      and all(len(h) == 7 and h.startswith("#") for _n, h in cfg.ACCENT_COLORS),
      str([h for _n, h in cfg.ACCENT_COLORS]))
check("默认色确实在色板里（否则载入会被归一闪打回默认，看不出差别）",
      cfg.ACCENT_DEFAULT in [h for _n, h in cfg.ACCENT_COLORS])

# ---- 旧色迁移表：必须**幂等**，否则老用户升级后每存一次配置就漂一格 ----
_MAP = cfg.LEGACY_ACCENT_MAP
check("旧朱红 #c0392b 迁到玫红 #f31260",
      _MAP.get("#c0392b") == "#f31260", _MAP.get("#c0392b"))
check("旧鎏金 #d4af37 迁到琥珀金 #eab308",
      _MAP.get("#d4af37") == "#eab308", _MAP.get("#d4af37"))
check("迁移表是幂等的：映射目标本身不再被映射（不会二次漂移）",
      all(v not in _MAP for v in _MAP.values()),
      str([v for v in _MAP.values() if v in _MAP]))
check("迁移目标全部落在新色板里（否则归一闪会把它打回默认）",
      all(v in [h for _n, h in cfg.ACCENT_COLORS] for v in _MAP.values()),
      str([v for v in _MAP.values() if v not in [h for _n, h in cfg.ACCENT_COLORS]]))

# load() 里迁移必须发生在「必须是色板之一」的归一闪**之前**。
# 别用文本序判（ACCENT_COLORS 在文件顶部还有定义处，find 到的是那一处），
# 直接造老配置跑一遍 load() —— 这才是真行为。
import json as _json
_cfg_file = cfg.config_path()
_old_settings = getattr(cfg, "_SETTINGS", None)
try:
    for _old_hex, _want in (("#c0392b", "#f31260"), ("#d4af37", "#eab308"),
                            ("#f31260", "#f31260")):
        with open(_cfg_file, "w", encoding="utf-8") as _f:
            _json.dump({"appearance": {"accent": _old_hex, "style": "glass"}},
                       _f, ensure_ascii=False)
        cfg._SETTINGS = None
        _got = cfg.get_settings().appearance.get("accent")
        check("老配置 accent=%s 载入后迁成 %s（迁移幂等，已在新色板的值不动）"
              % (_old_hex, _want),
              _got == _want, str(_got))
finally:
    cfg._SETTINGS = _old_settings

# ---- 派生色：亮度必须单调，不然按下态会比常态更亮 ----
def _lum(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


_sh = cfg.accent_shades("#006fee")
check("accent_shades 仍返回 base/dark/deep/light 四档",
      set(_sh) == {"base", "dark", "deep", "light"}, str(sorted(_sh)))
check("base 就是原色", _sh["base"] == (0, 111, 238), str(_sh["base"]))
check("dark < deep < base < light（亮度单调，按下不会比常态更亮）",
      _lum(_sh["dark"]) < _lum(_sh["deep"]) < _lum(_sh["base"]) < _lum(_sh["light"]),
      "%.1f/%.1f/%.1f/%.1f" % (_lum(_sh["dark"]), _lum(_sh["deep"]),
                              _lum(_sh["base"]), _lum(_sh["light"])))
check("对每个色板色都能派生（不抛异常、四档齐全）",
      all(set(cfg.accent_shades(h)) == {"base", "dark", "deep", "light"}
          for _n, h in cfg.ACCENT_COLORS))

# ---- QSS：新令牌渲染干净 + 旧墨金不再出现 ----
_q = mw.render_style({"accent": "#006fee", "style": "glass", "alpha": None})
_import_re = __import__("re")
# 注释里会提到「原来是与墨金底衬配套的 #1c1815」这类历史说明，检查必须去掉注释
_qb = _import_re.sub(r"/\*.*?\*/", "", _q, flags=_import_re.S)
check("渲染后没有剩下任何 __XXX__ 令牌",
      _import_re.search(r"__[A-Z_]+__", _q) is None,
      str(_import_re.findall(r"__[A-Z_]+__", _q)[:6]))
check("render_style 顺手把 ACCENT_RGB 刷成 (0, 111, 238)",
      tuple(mw.ACCENT_RGB) == (0, 111, 238), str(mw.ACCENT_RGB))
check("QSS 里已无旧鎏金 #d4af37", "#d4af37" not in _qb.lower())
check("QSS 里已无旧墨底 #1c1815", "#1c1815" not in _qb.lower())
check("QSS 用上了 HeroUI 中性色阶 #0a0a0b / #18181b / #27272a",
      all(c in _qb.lower() for c in ("#0a0a0b", "#18181b", "#27272a")))
check("选中态改成高亮色柔光底 rgba(0, 111, 238, 0.22)",
      "rgba(0, 111, 238, 0.22)" in _q)

# 裸令牌必须替换成 #rrggbb（塞 "r, g, b" 会让整条声明被 Qt 静默丢掉）
_bad = _import_re.findall(r":\s*\d+,\s*\d+,\s*\d+\s*;", _q)
check("没有把 \"r, g, b\" 误填成裸值（那会让整条声明被丢掉）",
      not _bad, str(_bad[:4]))

# ---- 拖拽条：用户明确要求「只保留这两条拖拽条」→ handle 必须仍是透明的 ----
for _name in ("ActorSplitV", "ActorSplitH", "ImageSplitH"):
    _key = "QSplitter#%s::handle" % _name
    check("QSS 仍有 %s 规则（拖拽条不许被重写掉）" % _key, _key in _q, _key)
    _seg2 = _q.split(_key, 1)[1].split("}", 1)[0] if _key in _q else ""
    check("%s 仍是 transparent 且 margin: 0（把手靠自绘，不能被底色盖住）" % _name,
          "transparent" in _seg2 and "margin: 0" in _seg2,
          _seg2.strip().replace("\n", " ")[:70])
check("自绘把手类 _GripHandle 仍在", hasattr(uac, "_GripHandle"))
check("_GripSplitter 仍在（5 点把手的分发器）", hasattr(uac, "_GripSplitter"))

# ---- 色卡：HeroUI 正圆 + 白环 + 勾 ----
check("_AccentSwatch 是 28×28 正圆尺寸", (uis._AccentSwatch.W, uis._AccentSwatch.H) == (28, 28),
      "%sx%s" % (uis._AccentSwatch.W, uis._AccentSwatch.H))
check("选中态用「色点缩一点 + 外环」两层（R_DOT_ON < R_DOT < R_RING）",
      uis._AccentSwatch.R_DOT_ON < uis._AccentSwatch.R_DOT < uis._AccentSwatch.R_RING,
      "%s/%s/%s" % (uis._AccentSwatch.R_DOT_ON, uis._AccentSwatch.R_DOT,
                    uis._AccentSwatch.R_RING))
_sw = uis._AccentSwatch("#006fee", "极光蓝")
_sw.set_on(True)
check("色卡实例的固定尺寸就是 28×28",
      (_sw.width(), _sw.height()) == (28, 28), "%dx%d" % (_sw.width(), _sw.height()))
_sw.set_on(False)
check("set_on(False) 可切回未选中（不抛异常）", True)

# ---- 开关轨道：旧的暖棕 → 中性，兜底开态 → HeroUI 蓝 ----
check("开关关态轨道换成 #3f3f46（原暖棕 #4a4038）",
      uis.ToggleSwitch._OFF == (0x3F, 0x3F, 0x46), str(uis.ToggleSwitch._OFF))
check("开关开态兜底换成 #006fee（原朱红 #c0392b）",
      uis.ToggleSwitch._ON == (0x00, 0x6F, 0xEE), str(uis.ToggleSwitch._ON))
check("开关绘制时仍现取高亮色（不自锁在兜底值）",
      uis.ToggleSwitch.accent_on() == (0, 111, 238), str(uis.ToggleSwitch.accent_on()))

# ---- 源码里不再有旧墨金色系（config.py 例外：迁移表的键就是旧值）----
_OLD_HEX = ("#d4af37", "#ece5d8", "#a2967f", "#8c8071", "#1c1815", "#2a241c",
            "#362e23", "#c0392b", "#e08a7a", "#9ecf8a")
_leak = []
for _fn in sorted(os.listdir(os.path.join(ROOT, "src"))):
    if not _fn.endswith(".py") or _fn in ("config.py", "version.py"):
        continue
    _txt = open(os.path.join(ROOT, "src", _fn), encoding="utf-8").read().lower()
    for _h in _OLD_HEX:
        if _h in _txt:
            _leak.append("%s:%s" % (_fn, _h))
check("src/*.py 里没有旧墨金色系残留（version.py 是历史记录、config.py 是迁移表）",
      not _leak, str(_leak[:8]))

# ---- 底衬跟着高亮色走（veil / 字母条都懒读 ACCENT_RGB）----
check("veil.accent_rgb() 取到当前高亮色",
      __import__("veil").accent_rgb() == (0, 111, 238),
      str(__import__("veil").accent_rgb()))
check("letter_index._accent_rgb() 取到当前高亮色",
      __import__("letter_index")._accent_rgb() == (0, 111, 238),
      str(__import__("letter_index")._accent_rgb()))

# =============== ㉘ v2.0.1：7 条真机反馈 ===============
print("== ㉘ v2.0.1：滑块行高 / 上下箭头 / 选中对勾 / 性别流光 / 粉色 / 侧栏实色 / 直角面板 ==")
import glyphs
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QSlider, QCheckBox, QLabel as _QL
import ui_hero as uhero

_q8 = mw.render_style({"accent": "#006fee"})

# ---- ① 「窗口透明度」滑块：18px 圆球要整体露出来 ----
_seg_sl = _q8.split("QSlider {", 1)[1].split("}", 1)[0]
check("QSS 给 QSlider 加了 24px 高度下限（圆球 18 + 上下余量）",
      "min-height: 24px" in _seg_sl, _seg_sl.strip().replace("\n", " "))
_dlg4 = uis.SettingsDialog(None)
_dlg4.resize(uis.SettingsDialog.DEF_W, uis.SettingsDialog.DEF_H)
_dlg4.show()                       # 离屏也必须 show()，否则几何全是 0
app.processEvents()
_dlg4._show("外观")
app.processEvents()
check("「窗口透明度」滑块控件高 ≥ 24（默认 sizeHint 只有 15，会把圆球切平）",
      _dlg4.op_slider.height() >= 24, _dlg4.op_slider.height())
check("智能推荐「多样性」滑块同样 ≥ 24", _dlg4.sl_div.height() >= 24, _dlg4.sl_div.height())
GAP_OP = _dlg4.op_slider.height() - 18
check("滑块比圆球至少高 6px（上下各留 3px）", GAP_OP >= 6, GAP_OP)

# ---- ② 数值框上下按钮里的箭头 / ③ 勾选框选中态的对勾 ----
# QSS 画不了矢量图形：`::up-arrow` 的 color 无效、`::indicator:checked` 只能换底色。
# 唯一的路是 image: url(...)，图片由 glyphs.py 在渲染样式表时现画成 PNG。
_gl = glyphs.ensure(force=True)
check("glyphs 生成 3 个小图标（箭头 ×2 + 对勾）",
      set(_gl) == {"arrow_up", "arrow_down", "check"}, str(sorted(_gl)))
check("三个 PNG 都真落盘且非空",
      all(os.path.exists(p) and os.path.getsize(p) > 100 for p in _gl.values()),
      str({k: os.path.getsize(p) for k, p in _gl.items() if os.path.exists(p)}))


def _opaque_mask(path):
    im = QImage(path)
    m = []
    for y in range(im.height()):
        row = []
        for x in range(im.width()):
            row.append(im.pixelColor(x, y).alpha() > 40)
        m.append(row)
    return m


_m_up = _opaque_mask(_gl["arrow_up"])
_m_dn = _opaque_mask(_gl["arrow_down"])
_m_ck = _opaque_mask(_gl["check"])


def _first_y(mask, xs):
    for y in range(len(mask)):
        if any(mask[y][x] for x in xs):
            return y
    return -1


def _bbox(mask):
    ys = [y for y, row in enumerate(mask) if any(row)]
    xs = [x for x in range(len(mask[0])) if any(row[x] for row in mask)]
    return (min(xs), min(ys), max(xs), max(ys)) if ys else (0, 0, 0, 0)


_bu, _bd, _bc = _bbox(_m_up), _bbox(_m_dn), _bbox(_m_ck)
_wu, _hu = _bu[2] - _bu[0], _bu[3] - _bu[1]
_wc, _hc = _bc[2] - _bc[0], _bc[3] - _bc[1]


def _quad(mask, box):
    """bbox 内四个象限各有几个不透明像素 —— 用来判「折线朝哪个方向」。"""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    q = {"tl": 0, "tr": 0, "bl": 0, "br": 0}
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if mask[y][x]:
                q[("t" if y <= cy else "b") + ("l" if x <= cx else "r")] += 1
    return q


check("上箭头是「宽扁」的折线：宽 ≥ 6、且宽高比 > 1.4（不是三角形）",
      _wu >= 6 and _hu > 0 and _wu / float(_hu) > 1.4, "%dx%d" % (_wu, _hu))
check("上箭头尖端在顶端（中列最高点比靠近两端的列更高）",
      _first_y(_m_up, [len(_m_up[0]) // 2]) < _first_y(_m_up, [2, len(_m_up[0]) - 3]),
      "%d vs %d" % (_first_y(_m_up, [len(_m_up[0]) // 2]),
                    _first_y(_m_up, [2, len(_m_up[0]) - 3])))
check("下箭头是上箭头的上下镜像（尖端在中列最底）",
      _first_y(list(reversed(_m_dn)), [len(_m_dn[0]) // 2])
      < _first_y(list(reversed(_m_dn)), [2, len(_m_dn[0]) - 3]))
_qc = _quad(_m_ck, _bc)
check("对勾有两笔：左下 + 右上都有像素，左上（起笔侧）最空",
      _qc["bl"] > 0 and _qc["tr"] > 0
      and _qc["tl"] < _qc["tr"] and _qc["tl"] < _qc["bl"], str(_qc))
check("对勾比箭头厚（勾的笔画 ≥ 8×7）", _wc >= 8 and _hc >= 7, "%dx%d" % (_wc, _hc))

_seg_ua = _q8.split("QSpinBox::up-arrow", 1)[1].split("}", 1)[0]
_seg_da = _q8.split("QSpinBox::down-arrow", 1)[1].split("}", 1)[0]
check("QSS 的 up-arrow 走 image: url(\"...arrow_up...)",
      "image: url(" in _seg_ua and "arrow_up" in _seg_ua,
      _seg_ua.strip().replace("\n", " ")[:60])
check("QSS 的 down-arrow 走 image: url(\"...arrow_down...)",
      "image: url(" in _seg_da and "arrow_down" in _seg_da,
      _seg_da.strip().replace("\n", " ")[:60])
check("箭头不再靠 color 着色（QSS 的 color 对箭头无效，留着只会误导）",
      "color:" not in _seg_ua.replace("border-color:", ""))
for _sel in ("QCheckBox::indicator:checked", "QListWidget::indicator:checked",
             "QTreeView::indicator:checked"):
    _seg_ck = _q8.split(_sel, 1)[1].split("}", 1)[0]
    check("%s 里带了 image: url(...check...)" % _sel,
          "image: url(" in _seg_ck and "check_" in _seg_ck,
          _seg_ck.strip().replace("\n", " ")[:60])
check("单选按钮 checked **没有**加对勾（它该是实心圆点）",
      "image:" not in _q8.split("QRadioButton::indicator:checked", 1)[1].split("}", 1)[0])

# 真画一遍：勾选框选中态的方框里必须出现白像素（只换底色时一个白点都没有）
_ck = QCheckBox("真机对勾")
_ck.setChecked(True)
_ck.setStyleSheet("background:#18181b;color:#ecedee;")
_ck.resize(140, 24)
_ck.show()
app.processEvents()
_grab = _ck.grab().toImage()
_white = 0
for _y in range(min(22, _grab.height())):
    for _x in range(22):
        _c = _grab.pixelColor(_x, _y)
        if _c.red() > 200 and _c.green() > 200 and _c.blue() > 200:
            _white += 1
check("勾选框选中态真画出了白色对勾（≥12 个近白像素）", _white >= 12, _white)
_ck.deleteLater()

# ---- ④ 演职人员头像按性别加流光 ----
_face = os.path.join(TMP, "face.png")
# ⚠ 照片必须是**中性灰**：暖色（#c8b9a8 这类）本身 r>b+20，会被下面的「粉像素」统计
# 当成流光一起数进去（第一版就是这么假红的）。
_pm = __import__("PySide6.QtGui", fromlist=["QPixmap"]).QPixmap(80, 80)
_pm.fill(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor("#808080"))
_pm.save(_face)


def _halo_counts(av):
    """数整张头像图里的「粉」与「蓝」像素 —— 流光就是这两类像素。"""
    lab = [w for w in av.findChildren(_QL) if w.pixmap() is not None
           and not w.pixmap().isNull()]
    if not lab:
        return 0, 0, None
    pm = lab[0].pixmap()
    img = pm.toImage()
    pink = blue = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 30:
                continue
            if c.red() > c.blue() + 20 and c.red() > 120:
                pink += 1
            elif c.blue() > c.red() + 20 and c.blue() > 120:
                blue += 1
    return pink, blue, pm


_av_f = uhero.CastAvatar({"name": "女", "gender": "female", "photo_path": _face}, None)
_av_m = uhero.CastAvatar({"name": "男", "gender": "male", "photo_path": _face}, None)
_av_u = uhero.CastAvatar({"name": "未知", "gender": "", "photo_path": _face}, None)
for _a in (_av_f, _av_m, _av_u):
    _a.show()
app.processEvents()
_pf, _bf, _sf = _halo_counts(_av_f)
_pm2, _bm, _sm = _halo_counts(_av_m)
_pu, _bu, _su = _halo_counts(_av_u)
check("女性头像画布比海报大 2×6（96 → 108）", _sf.width() == 108, _sf.width())
check("男性头像画布同样 108", _sm.width() == 108, _sm.width())
check("未知性别头像**不外扩**（画布仍 96，不留空圈）", _su.width() == 96, _su.width())
check("女性有粉色流光、没有蓝像素", _pf > 100 and _bf == 0, "pink=%d blue=%d" % (_pf, _bf))
check("男性有蓝色流光、没有粉像素", _bm > 100 and _pm2 == 0, "pink=%d blue=%d" % (_pm2, _bm))
check("未知性别一个流光像素都没有（干净）", _pu == 0 and _bu == 0,
      "pink=%d blue=%d" % (_pu, _bu))
check("流光宽度常量 GLOW_W == 6", uhero.GLOW_W == 6, uhero.GLOW_W)
check("女性/男性能量级相当（不是只有一侧生效）",
      abs(_pf - _bm) < max(_pf, _bm) * 0.25, "%d vs %d" % (_pf, _bm))
for _a in (_av_f, _av_m, _av_u):
    _a.deleteLater()

# ---- ⑤ 色板：玫红后面补「粉色」 ----
_hexes = [h for _n, h in cfg.ACCENT_COLORS]
_names = {h: n for n, h in cfg.ACCENT_COLORS}
check("色板 11 → 12 色", len(_hexes) == 12, len(_hexes))
# v2.0.2（反馈 2）：用户把粉色从 #ff7fa1 换成 #e4587c → 本节断言跟着换色值。
check("「粉色」#e4587c 已加入色板", "#e4587c" in _hexes, str(_hexes))
check("粉色紧跟玫红（顺序 = 界面上的色卡顺序）",
      _hexes.index("#e4587c") == _hexes.index("#f31260") + 1,
      "%d / %d" % (_hexes.index("#f31260"), _hexes.index("#e4587c")))
check("粉色名字叫「粉色」", _names.get("#e4587c") == "粉色", str(_names.get("#e4587c")))
_sh8 = cfg.accent_shades("#e4587c")
check("粉色能派生四档且亮度单调",
      _lum(_sh8["dark"]) < _lum(_sh8["deep"]) < _lum(_sh8["base"]) < _lum(_sh8["light"]),
      "%.1f/%.1f/%.1f/%.1f" % (_lum(_sh8["dark"]), _lum(_sh8["deep"]),
                              _lum(_sh8["base"]), _lum(_sh8["light"])))
check("粉色仍在色板里（换了它不会被归一闪打回默认）",
      cfg.get_settings().appearance.get("accent") in _hexes)

# ---- ⑥ 磨砂玻璃不作用到导航栏 ----
_seg_sb = _q8.split("QFrame#Sidebar {", 1)[1].split("}", 1)[0]
check("侧栏背景改成实色 #0f0f11（不再吃 __PANEL__ 的半透明）",
      "background: #0f0f11" in _seg_sb, _seg_sb.strip().replace("\n", " ")[:70])
check("侧栏背景里不再有 rgba(（有就说明还在跟着玻璃浓度走）",
      "rgba(" not in _seg_sb.split("border-right")[0],
      _seg_sb.strip().replace("\n", " ")[:70])
_q8_glass = mw.render_style({"accent": "#006fee", "mode": "磨砂玻璃", "level": "低"})
check("把浓度调到「低」时侧栏仍是同一个实色（与浓度档无关）",
      "background: #0f0f11" in _q8_glass.split("QFrame#Sidebar {", 1)[1].split("}", 1)[0])

# ---- ⑦ 首页 / 详情页面板上下圆角改直角 ----
_seg_dh = _q8.split("QWidget#DetailHost {", 1)[1].split("}", 1)[0]
check("DetailHost 圆角 14 → 0（上下都变直角）",
      "border-radius: 0px" in _seg_dh and "14px" not in _seg_dh,
      _seg_dh.strip().replace("\n", " ")[:70])
check("DetailHost 仍保留强调色描边（只改圆角，不删边框）",
      "border: 1px solid rgba(" in _seg_dh, _seg_dh.strip().replace("\n", " ")[:70])

# =============== ㉙ v2.0.2 六条真机反馈（v2.0.3 补第 7 条） ===============
print("== ㉙ v2.0.2：圆形等大按钮 / 粉色换值 / 微调箭头 / 标签搜索 / 标题跟色 / 两处白字 ==")
print("   v2.0.3：收藏钮去掉圆底（用户：收藏外不需要圆形）")
import inspect
from PySide6.QtCore import QPoint as _QP9
from PySide6.QtGui import QPixmap as _QPM9, QColor as _QC9, QLinearGradient as _QLG9
from PySide6.QtGui import QPainter as _QPT9
import ui_manualedit as uime

_q9 = mw.render_style({"accent": "#e4587c"})       # 顺带把 ACCENT_RGB 刷成新粉
_ACC9 = (228, 88, 124)


def _lc9(c):
    return 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()


# ---- ① 收藏 / 播放：圆、等大、有阴影 ----
check("按钮控件边长 _CARD_BTN == 34（圆 28 + 阴影环 3×2）", mw._CARD_BTN == 34, mw._CARD_BTN)
check("圆本体直径 _BTN_CIRCLE == 28", mw._BTN_CIRCLE == 28, mw._BTN_CIRCLE)
check("收藏与播放共用同一套尺寸常量",
      mw._PLAY_BTN == mw._STAR_BTN == mw._CARD_BTN,
      "%s/%s/%s" % (mw._PLAY_BTN, mw._STAR_BTN, mw._CARD_BTN))
check("两个按钮是同一个基类（不再一个走 QSS 一个裸画）",
      issubclass(mw._PlayGlyphButton, mw._CardRoundButton)
      and issubclass(mw._FavStarButton, mw._CardRoundButton))
check("QSS 不再给 #CardPlay 写背景/圆角（自绘圆底，写两层会双描边）",
      "QPushButton#CardPlay" not in _q9)

_poster9 = os.path.join(TMP, "poster_bright.png")
_pm9 = _QPM9(158, 236)
_g9 = _QLG9(0, 0, 0, 236)
_g9.setColorAt(0.0, _QC9("#f2e6d2"))
_g9.setColorAt(1.0, _QC9("#d8c3a0"))
_pt9 = _QPT9(_pm9)
_pt9.fillRect(_pm9.rect(), _g9)
_pt9.end()
_pm9.save(_poster9)

_media9 = {"id": 9001, "title": "TEST-001 测试片", "poster": _poster9,
           "rating": 8.5, "year": 2025, "quality": "4K", "favorite": 0,
           "file_path": "X:/t/t.mp4", "plot": "", "tags": ""}
_card9 = mw.PosterCard(_media9, lambda *_a: None, on_play=lambda *_a: None,
                       on_fav=lambda *_a: None)
_card9.show()
for _ in range(3):
    app.processEvents()
_pb9, _fb9 = _card9.play_btn, _card9.fav_btn
check("播放 / 收藏两个按钮都建出来了", _pb9 is not None and _fb9 is not None)
check("两个按钮尺寸完全一致（34×34）",
      (_pb9.width(), _pb9.height()) == (_fb9.width(), _fb9.height()) == (34, 34),
      "%dx%d / %dx%d" % (_pb9.width(), _pb9.height(), _fb9.width(), _fb9.height()))
check("左右对称：两个按钮到海报左右边的距离相等",
      (_fb9.x() - mw._CARD_PAD) == (mw._CARD_PAD + mw.POSTER_W - (_pb9.x() + _pb9.width())),
      "%d / %d" % (_fb9.x() - mw._CARD_PAD,
                   mw._CARD_PAD + mw.POSTER_W - (_pb9.x() + _pb9.width())))
check("两者底边齐平", _pb9.y() == _fb9.y(), "%d / %d" % (_pb9.y(), _fb9.y()))

_img9 = _card9.grab().toImage()
check("卡片上两个按钮的可见区域互不重叠（左右对称摆放）",
      _pb9.x() > _fb9.x() + _fb9.width() + 40,
      "%d / %d" % (_fb9.x() + _fb9.width(), _pb9.x()))

# ⚠ 量圆 / 量阴影必须**单独 grab 按钮本身**：卡片是不透明海报，在卡片图上取
# 「角落像素」量到的是 poster（alpha 恒 255），第一版就是这么假红的。
_pbi = _pb9.grab().toImage()
_fbi = _fb9.grab().toImage()


def _al(img, x, y):
    return img.pixelColor(x, y).alpha()


check("按钮自身画布 34×34（含 3px 阴影环）",
      (_pbi.width(), _pbi.height()) == (34, 34), "%dx%d" % (_pbi.width(), _pbi.height()))
check("圆本体外接框的角上是透明的（方形 → 角一定不透明）",
      _al(_pbi, 4, 4) == 0 and _al(_fbi, 4, 4) == 0,
      "%d / %d" % (_al(_pbi, 4, 4), _al(_fbi, 4, 4)))
check("播放钮圆内 45°（8,8）是实心的",
      _al(_pbi, 8, 8) > 200, _al(_pbi, 8, 8))


def _disc_r9(img):
    """沿水平中线从圆心往外扫，返回最后一个「基本不透明」像素的距离（≈14）。

    ⚠ 上界必须 `< width // 2`：`pixelColor(34, 17)` 这种越界坐标返回的是**无效 QColor**，
    它的 alpha() 是 255 —— 第一版就把「越界读到的 255」当成了半径 17。
    """
    far = 0
    for d in range(1, img.width() // 2):
        if _al(img, img.width() // 2 + d, img.height() // 2) > 150:
            far = d
    return far


def _opaque9(img):
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 150:
                n += 1
    return n


# ---- v2.0.3：收藏钮「外不需要圆形」 ----
check("播放钮 HAS_CIRCLE 为 True（圆底保留）", mw._PlayGlyphButton.HAS_CIRCLE is True,
      mw._PlayGlyphButton.HAS_CIRCLE)
check("收藏钮 HAS_CIRCLE 为 False（v2.0.3 去掉圆底）",
      mw._FavStarButton.HAS_CIRCLE is False, mw._FavStarButton.HAS_CIRCLE)
_rp9 = _disc_r9(_pbi)
check("播放钮圆半径 13~15（圆本体 28px）", 13 <= _rp9 <= 15, _rp9)
_np9, _nf9 = _opaque9(_pbi), _opaque9(_fbi)
check("收藏钮不再是实心圆底（不透明像素不到播放钮的 55%）",
      _nf9 < _np9 * 0.55, "%d / %d" % (_nf9, _np9))
check("收藏钮「圆内偏左」(6,17) 基本透明（有圆底时这里必然实心 >150）",
      _al(_fbi, 6, 17) <= 40, _al(_fbi, 6, 17))
check("收藏钮「圆内偏右」(28,17) 透明", _al(_fbi, 28, 17) <= 40, _al(_fbi, 28, 17))
check("收藏钮「圆内偏下」(17,28) 透明", _al(_fbi, 17, 28) <= 40, _al(_fbi, 17, 28))
check("收藏钮仍然画得出星形本体（不透明像素 ≥ 60）", _nf9 >= 60, _nf9)
_sf9 = 0
for _y in range(_fbi.height()):
    for _x in range(_fbi.width()):
        if 25 <= _fbi.pixelColor(_x, _y).alpha() <= 140:
            _sf9 += 1
check("收藏钮沿星形轮廓有柔影（25<alpha<140 的像素 ≥ 30，亮剧照上白星才压得住）",
      _sf9 >= 30, _sf9)
# 播放钮的投影：圆本体外（半径 15 处）要有半透明黑影
_sh9 = _al(_pbi, 17, 33)
check("播放钮圆下方有半透明投影（alpha > 40）", _sh9 > 40, _sh9)
_shc9 = _pbi.pixelColor(17, 33)
check("投影是黑色系（不是描边漏出来的白）", _shc9.red() < 90 and _shc9.blue() < 90,
      "%d,%d,%d a=%d" % (_shc9.red(), _shc9.green(), _shc9.blue(), _shc9.alpha()))

# 悬停：播放钮圆底换高亮色；收藏钮只把星形描边染成高亮色、**不许冒出圆底**。
# ⚠ 别取圆心 —— 播放三角/星都盖在圆心，量到的是白的。
_pb9.setAttribute(Qt.WA_UnderMouse, True)
_pb9.update()
for _ in range(3):
    app.processEvents()
_hc9 = _pb9.grab().toImage().pixelColor(5, 17)
check("播放钮悬停时圆底换成当前高亮色（#e4587c）",
      abs(_hc9.red() - _ACC9[0]) < 45 and abs(_hc9.green() - _ACC9[1]) < 45
      and abs(_hc9.blue() - _ACC9[2]) < 45,
      "%d,%d,%d" % (_hc9.red(), _hc9.green(), _hc9.blue()))
_pb9.setAttribute(Qt.WA_UnderMouse, False)
_pb9.update()
_fb9.setAttribute(Qt.WA_UnderMouse, True)
_fb9.update()
for _ in range(3):
    app.processEvents()
_fbi2 = _fb9.grab().toImage()
_hp9 = 0
for _y in range(_fbi2.height()):
    for _x in range(_fbi2.width()):
        _c2 = _fbi2.pixelColor(_x, _y)
        if _c2.alpha() > 150 and abs(_c2.red() - _ACC9[0]) < 60 \
                and abs(_c2.green() - _ACC9[1]) < 60 and abs(_c2.blue() - _ACC9[2]) < 60:
            _hp9 += 1
check("收藏钮悬停：星形描边染成高亮色（≥20 个粉像素）", _hp9 >= 20, _hp9)
check("收藏钮悬停时 (6,17) 依然基本透明（没有冒出圆底）",
      _fbi2.pixelColor(6, 17).alpha() <= 40, _fbi2.pixelColor(6, 17).alpha())
_fb9.setAttribute(Qt.WA_UnderMouse, False)
_fb9.update()

# 已收藏 = 金色实心星（在深色圆底上仍要看得清）
_fb9.set_on(True)
_fb9.update()
for _ in range(3):
    app.processEvents()
_img9c = _card9.grab().toImage()
_gold9 = 0
for _y in range(_fb9.y(), _fb9.y() + _fb9.height()):
    for _x in range(_fb9.x(), _fb9.x() + _fb9.width()):
        _cc = _img9c.pixelColor(_x, _y)
        if _cc.red() > 200 and 130 < _cc.green() < 205 and _cc.blue() < 100:
            _gold9 += 1
check("已收藏态仍是金色实心星（≥20 个金色像素）", _gold9 >= 20, _gold9)
_card9.deleteLater()

# ---- ② 粉色 #ff7fa1 → #e4587c ----
check("色板里已无旧粉 #ff7fa1", "#ff7fa1" not in _hexes, str(_hexes))
check("迁移表把旧粉映射到新粉（否则 v2.0.1 选过粉色的用户升级会掉回默认蓝）",
      cfg.LEGACY_ACCENT_MAP.get("#ff7fa1") == "#e4587c",
      str(cfg.LEGACY_ACCENT_MAP.get("#ff7fa1")))
check("女性流光颜色同步换成新粉", uhero.GLOW_FEMALE.lower() == "#e4587c", uhero.GLOW_FEMALE)
_cfg9 = cfg.config_path()
_keep9 = getattr(cfg, "_SETTINGS", None)
try:
    with open(_cfg9, "w", encoding="utf-8") as _f:
        _json.dump({"appearance": {"accent": "#ff7fa1"}}, _f)
    cfg._SETTINGS = None
    check("老配置 accent=#ff7fa1 载入后迁成 #e4587c",
          cfg.get_settings().appearance.get("accent") == "#e4587c",
          str(cfg.get_settings().appearance.get("accent")))
finally:
    cfg._SETTINGS = _keep9

# ---- ③ 「我的评分」上下微调按钮（与其它数值框同一套样式）----
_rd9 = uhero.RateDialog(None, 10.0)
_rd9.show()
for _ in range(3):
    app.processEvents()
check("数值框恢复 UpDownArrows",
      _rd9.spin.buttonSymbols() == QAbstractSpinBox.UpDownArrows,
      _rd9.spin.buttonSymbols())
check("最小宽度 = cfg.SPIN_MIN_W（「10.0 分」不再被压成省略号）",
      _rd9.spin.minimumWidth() == cfg.SPIN_MIN_W, _rd9.spin.minimumWidth())
_ri9 = _rd9.grab().toImage()
_org9 = _rd9.spin.mapTo(_rd9, _QP9(0, 0))
_x09 = _org9.x() + _rd9.spin.width() - 18
_y09, _y19 = _org9.y() + 2, _org9.y() + _rd9.spin.height() - 3
_up9 = _dn9 = 0
for _y in range(max(0, _y09), min(_ri9.height(), _y19)):
    for _x in range(max(0, _x09), min(_ri9.width(), _x09 + 17)):
        _cc = _ri9.pixelColor(_x, _y)
        if _cc.red() > 120 and _cc.green() > 120 and _cc.blue() > 120:
            if _y < (_y09 + _y19) // 2:
                _up9 += 1
            else:
                _dn9 += 1
check("上 / 下两个箭头都真画出来了（各 ≥ 8 个亮像素）", _up9 >= 8 and _dn9 >= 8,
      "up=%d dn=%d" % (_up9, _dn9))
_rd9.deleteLater()

# ---- ④ 顶栏搜索：关键词也搜「标签」----
_cn9 = db.get_conn()
_cn9.execute("INSERT INTO media (kind,title,file_path,library,tags) VALUES "
             "('movie','无关标题甲','X:/tags/t1.mp4','测试库','标签戊,标签己')")
_cn9.execute("INSERT INTO media (kind,title,file_path,library,plot) VALUES "
             "('movie','无关标题乙','X:/tags/t2.mp4','测试库','简介唯一词丁戊')")
_cn9.commit()
check("按标签能搜到", len(db.search_media("标签戊")) >= 1, len(db.search_media("标签戊")))
check("count_media 与 search_media 口径一致（共用 _media_where）",
      db.count_media("标签戊") == len(db.search_media("标签戊")),
      "%d / %d" % (db.count_media("标签戊"), len(db.search_media("标签戊"))))
check("标题搜索没被改坏", len(db.search_media("无关标题甲")) >= 1)
check("简介搜索没被改坏", len(db.search_media("简介唯一词丁戊")) >= 1)
check("不存在的词仍然是 0 条", len(db.search_media("绝不存在的词zzz")) == 0,
      len(db.search_media("绝不存在的词zzz")))
check("keyword 子句三个 OR（title / plot / tags）",
      "m.title LIKE ? OR m.plot LIKE ? OR IFNULL(m.tags,'') LIKE ?" in
      inspect.getsource(db._media_where))

# ---- ⑤ 页面 / 面板标题跟着高亮色走 ----
_seg_pt9 = _q9.split("QLabel#PageTitle {", 1)[1].split("}", 1)[0]
check("#PageTitle 用当前高亮色渲染（#e4587c）", "color: #e4587c" in _seg_pt9,
      _seg_pt9.strip().replace("\n", " "))
_q9b = mw.render_style({"accent": "#17c964"})
check("换成翡翠后同一选择器就是新色（走令牌，不是写死）",
      "color: #17c964" in _q9b.split("QLabel#PageTitle {", 1)[1].split("}", 1)[0])
check("#PanelTitle 同样走高亮色",
      "color: #17c964" in _q9b.split("QLabel#PanelTitle {", 1)[1].split("}", 1)[0])
check("#PanelTitleSm 同样走高亮色",
      "color: #17c964" in _q9b.split("QLabel#PanelTitleSm {", 1)[1].split("}", 1)[0])
_h9 = mw.MainWindow._h1(None, "最近播放 / 最近添加")
check("_h1 返回 #PageTitle（不再内联写死颜色）",
      _h9.objectName() == "PageTitle" and "color" not in _h9.styleSheet(),
      "%s / %r" % (_h9.objectName(), _h9.styleSheet()))
check("_h1 里没有写死的 #66a9ff 声明（注释里提到旧值不算）",
      "color:#66a9ff" not in inspect.getsource(mw.MainWindow._h1)
      and "color: #66a9ff" not in inspect.getsource(mw.MainWindow._h1))
check("_mktitle 返回 #PanelTitle",
      uime.ManualEditPage._mktitle("X").objectName() == "PanelTitle")
check("工具窗画像的列标题也走 PanelTitleSm",
      "66a9ff" not in inspect.getsource(uis.SettingsDialog._page_insight)
      if hasattr(uis.SettingsDialog, "_page_insight") else True)

# ---- ⑥ 两处用户点名要白色的字 ----
check("#PlainValue 是白色 #fafafa",
      "color: #fafafa" in _q9.split("QLabel#PlainValue {", 1)[1].split("}", 1)[0])
check("#PlainTitle 是白色 #fafafa",
      "color: #fafafa" in _q9.split("QLabel#PlainTitle {", 1)[1].split("}", 1)[0])
check("窗口透明度读数 objectName == PlainValue",
      _dlg4.op_val.objectName() == "PlainValue", _dlg4.op_val.objectName())
check("窗口透明度读数不再写死 #66a9ff",
      "66a9ff" not in _dlg4.op_val.styleSheet(), _dlg4.op_val.styleSheet())
check("「检索并选择影片」标记成 PlainTitle",
      'setObjectName("PlainTitle")' in inspect.getsource(uime.ManualEditPage._build_shell))
check("「检索并选择影片」不再写死颜色（注释里提到旧值不算）",
      "color:#66a9ff" not in inspect.getsource(uime.ManualEditPage._build_shell)
      and "color: #66a9ff" not in inspect.getsource(uime.ManualEditPage._build_shell))

# ---- 顶栏搜索提示语：19 个语言都补上了「标签」----
_ph9 = "搜索 (Ctrl+K)   片名 / 类型 / 演员 / 标签  （用 @ 指定演员）"
check("i18n 键已带「标签」", _ph9 in i18n.COMMON["zh_CN"],
      "" if _ph9 in i18n.COMMON["zh_CN"] else "缺失")
check("英 / 日 / 韩 / 德 四个语言的提示语都提到 Tag",
      all("Tag" in i18n.COMMON[k][_ph9] or "タグ" in i18n.COMMON[k][_ph9]
          or "태그" in i18n.COMMON[k][_ph9] or "Tag" in i18n.COMMON[k][_ph9]
          for k in ("en", "ja", "ko", "de")),
      str([i18n.COMMON[k].get(_ph9, "")[:40] for k in ("en", "ja", "ko", "de")]))
check("19 个语言块都填了这一条",
      sum(1 for k in i18n.COMMON if _ph9 in i18n.COMMON[k]) == len(i18n.COMMON),
      "%d / %d" % (sum(1 for k in i18n.COMMON if _ph9 in i18n.COMMON[k]),
                   len(i18n.COMMON)))

# ---- v2.0.3（反馈 8）：演职员名字按身份着色 ----
# 女演员粉 / 男演员蓝 / 导演黄 / 未知白；卡片小字与详情页演职人员共用
# `ui_hero.crew_name_color` 这一处真源（两边永远同色）。
print("   --- 反馈 8：演职员名字配色 ---")
check("女演员 → 粉 #e4587c", uhero.crew_name_color("female") == "#e4587c",
      uhero.crew_name_color("female"))
check("男演员 → 蓝 #338ef7", uhero.crew_name_color("male") == "#338ef7",
      uhero.crew_name_color("male"))
check("未知 → 白 #fafafa", uhero.crew_name_color("") == "#fafafa",
      uhero.crew_name_color(""))
check("导演 → 黄 #f5a524（优先于性别）",
      uhero.crew_name_color("male", True) == uhero.crew_name_color("female", True) == "#f5a524",
      "%s / %s" % (uhero.crew_name_color("male", True),
                   uhero.crew_name_color("female", True)))
check("性别大小写 / 空格都能认（FEMALE / ' male '）",
      uhero.crew_name_color("FEMALE") == "#e4587c"
      and uhero.crew_name_color(" male ") == "#338ef7")
check("角色串认得出 Director / 导演",
      uhero.is_director_role("Director") and uhero.is_director_role("导演")
      and not uhero.is_director_role("Actor"))

# v2.0.4（反馈 9）：默认灰 / 收藏才高亮 / 置顶加粗 —— 三档语义互不重叠
_DIM9 = mw._CREW_NAME_DIM
check("卡片小字默认色是弱化灰 #a1a1aa（与「演员：」标签同色）",
      _DIM9 == "#a1a1aa", _DIM9)
# 卡片上「演员：/导演：」标签本身是在 PosterCard 里内联写死的灰，
# 两个色值必须一致，否则「标签灰 + 名字另一种灰」会看出来。
check("PosterCard 的 #CardCrew 内联色与 _CREW_NAME_DIM 一致",
      ("color:%s" % _DIM9) in inspect.getsource(mw.PosterCard), _DIM9)

_h8n = mw._crew_names_html([("女A", 0, 0, "female"), ("男B", 0, 0, "male"),
                            ("未C", 0, 0, "")], "", "actor")
check("未收藏：三个名字全是灰的（不再按性别铺色）",
      _h8n.count(_DIM9) == 3 and "#e4587c" not in _h8n
      and "#338ef7" not in _h8n and "#fafafa" not in _h8n, _h8n[:90])
check("未收藏：也没有加粗", "font-weight:bold" not in _h8n)

_h8 = mw._crew_names_html([("女A", 1, 0, "female"), ("男B", 1, 0, "male"),
                           ("未C", 1, 0, "")], "", "actor")
check("收藏后：三个名字分别高亮成 粉 / 蓝 / 白", 
      "#e4587c" in _h8 and "#338ef7" in _h8 and "#fafafa" in _h8, _h8[:90])
check("收藏后：灰色一个都不剩", _DIM9 not in _h8)
_h8d = mw._crew_names_html([("某导演", 1, 0, "male")], "", "director")
check("收藏的导演：名字是黄色（哪怕性别是男）",
      "#f5a524" in _h8d and "#338ef7" not in _h8d, _h8d)
check("未收藏的导演：名字仍是灰的（不预先上色）",
      _DIM9 in mw._crew_names_html([("某导演", 0, 0, "male")], "", "director"))
_h8old = mw._crew_names_html([("老三元组", 1, 0)], "", "actor")
check("旧三元组（没有 gender）收藏后落成白色",
      "#fafafa" in _h8old, _h8old)
_h8p = mw._crew_names_html([("置顶的", 0, 1, "female")], "", "actor")
check("置顶（未收藏）：只是加粗，颜色还是灰",
      "font-weight:bold" in _h8p and _DIM9 in _h8p and "#e4587c" not in _h8p, _h8p)
_h8fp = mw._crew_names_html([("收藏又置顶", 1, 1, "female")], "", "actor")
check("收藏 + 置顶：高亮色 + 加粗",
      "#e4587c" in _h8fp and "font-weight:bold" in _h8fp, _h8fp)
check("卡片小字里不再有下划线（v2.0.3 那版发明过，用户没要）",
      "underline" not in _h8fp and "underline" not in _h8p)
check("旧的金色 #66a9ff 不再出现在卡片小字里",
      "#66a9ff" not in _h8 and "#66a9ff" not in _h8p)

import inspect as _insp8
_src8 = _insp8.getsource(db.cast_crew_map_ex)
check("cast_crew_map_ex 查了 gender 字段", "p.gender" in _src8)
check("cast_crew_map_ex 元组带上性别（4 项）",
      'r["gender"]' in _src8 or "r.get(\"gender\")" in _src8)
check("cast_crew_map 不再写死三元组解包（会 ValueError）",
      "t[0] for t in" in _insp8.getsource(db.cast_crew_map))

# 详情页演职人员：真建 CastAvatar，看名字 QLabel 的实际颜色
# ⚠ 必须把控件本身**留住引用**：CastAvatar 没有 parent，函数一返回就被 GC，
#   它里面的 QLabel 在 C++ 侧一起析构 → 再读 styleSheet()/font() 会
#   `RuntimeError: Internal C++ object already deleted`（第一版就这么崩的）。
_CA8 = []


def _castlabel(person):
    w = uhero.CastAvatar(person, None, size=88)
    _CA8.append(w)
    for _l in w.findChildren(QLabel):
        if _l.text() == person["name"]:
            return _l
    return None


# v2.0.5（反馈 10）：详情页沿用卡片的三档规则 —— 默认灰 / 收藏才上身份色 / 置顶加粗
for _nm, _g, _role in (("女演员", "female", "Actor"),
                       ("男演员", "male", "Actor"),
                       ("未知人", "", "Actor"),
                       ("某导演", "male", "导演")):
    _lb = _castlabel({"name": _nm, "gender": _g, "char_role": _role,
                      "role_type": "Director" if _role == "导演" else "Actor"})
    check("详情页「%s」未收藏时名字是默认灰" % _nm,
          _lb is not None and mw._CREW_NAME_DIM in _lb.styleSheet(),
          _lb.styleSheet() if _lb is not None else "没找到名字 QLabel")

for _nm, _g, _role, _want in (("收藏的女演员", "female", "Actor", "#e4587c"),
                              ("收藏的男演员", "male", "Actor", "#338ef7"),
                              ("收藏的未知人", "", "Actor", "#fafafa"),
                              ("收藏的导演", "male", "导演", "#f5a524")):
    _lb = _castlabel({"name": _nm, "gender": _g, "char_role": _role,
                      "role_type": "Director" if _role == "导演" else "Actor",
                      "favorite": 1})
    check("详情页「%s」收藏后名字是 %s" % (_nm, _want),
          _lb is not None and _want in _lb.styleSheet(),
          _lb.styleSheet() if _lb is not None else "没找到名字 QLabel")
_lbf = _castlabel({"name": "收藏的人", "gender": "female", "char_role": "Actor",
                   "favorite": 1})
check("详情页：收藏但未置顶 → 不上粗、更不画下划线",
      _lbf is not None and "bold" not in _lbf.styleSheet()
      and not _lbf.font().underline(),
      _lbf.styleSheet() if _lbf is not None else "?")
_lbp = _castlabel({"name": "置顶的人", "gender": "male", "char_role": "Actor", "pinned": 1})
check("详情页：只置顶 → 加粗 + 仍是默认灰",
      _lbp is not None and "bold" in _lbp.styleSheet()
      and mw._CREW_NAME_DIM in _lbp.styleSheet(), 
      _lbp.styleSheet() if _lbp is not None else "?")
_lbfp = _castlabel({"name": "既收藏又置顶", "gender": "female", "char_role": "Actor",
                    "favorite": 1, "pinned": 1})
check("详情页：收藏 + 置顶 → 身份色 + 加粗",
      _lbfp is not None and "#e4587c" in _lbfp.styleSheet()
      and "bold" in _lbfp.styleSheet(),
      _lbfp.styleSheet() if _lbfp is not None else "?")
check("详情页角色小字（Actor / 导演）与默认灰同色",
      uhero.CREW_NAME_DIM == mw._CREW_NAME_DIM == "#a1a1aa",
      uhero.CREW_NAME_DIM)
check("默认灰只有一个真源（main_window 里的常量就是 ui_hero 那份）",
      mw._CREW_NAME_DIM is uhero.CREW_NAME_DIM,
      "%r / %r" % (mw._CREW_NAME_DIM, uhero.CREW_NAME_DIM))

print("通过 %d/%d" % (TOTAL[0] - len(FAILS), TOTAL[0]))
if FAILS:
    print("失败项:", FAILS)
else:
    print("SMOKE_V1430_ALL_OK")
