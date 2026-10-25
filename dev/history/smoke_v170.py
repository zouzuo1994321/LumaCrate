# -*- coding: utf-8 -*-
"""v1.7.0 离线冒烟测试：
- 磨砂玻璃：样式令牌替换（玻璃/经典两档）、backdrop 调用不崩
- 媒体库删除：确认对话框 + 计数 + 清索引 + 内置库墓碑（删除后不复活 / 可恢复）
- 演员刮削：minnano-av / IMDB 解析（本地 HTML 夹具，不联网）、scrape_one/scrape_many 落库、
  设置界面「演员刮削」页构建、数据源优先级与启停
"""
import os
import sys
import json
import tempfile
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import scanner as scanner_mod
import config as cfg

errors = []


def check(name, cond, extra=""):
    print(("OK  " if cond else "FAIL") + " - " + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        errors.append(name)


try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    import ui_hero, ui_home, ui_settings, main_window
    import backdrop, scraper as scraper_mod
    import version as ver
    check("import 全部模块", True)
except Exception as e:
    check("import modules: " + repr(e), False)

app = QApplication.instance() or QApplication([])
check("版本号为 v1.7.0", ver.VERSION == "v1.7.0", ver.FULL_VERSION)

# ---------------------------------------------------------------- 1) 磨砂玻璃
try:
    qss_glass = main_window.render_style({"mode": "磨砂玻璃", "level": "中"})
    check("样式令牌已全部替换", "__VEIL__" not in qss_glass and "__DLG__" not in qss_glass)
    # 页面底色已移交 veil.VeilWidget 自绘，QSS 里必须保持透明
    check("中央容器底色交由自绘（QSS 透明）",
          "QWidget#CentralVeil { background: transparent; }" in qss_glass)
    qss_classic = main_window.render_style({"mode": "经典暗色", "level": "中"})
    check("经典模式面板不透明", "rgba(12, 10, 9, 255)" in qss_classic)
    qss_high = main_window.render_style({"mode": "磨砂玻璃", "level": "高"})
    check("玻璃浓度可调", "rgba(12, 10, 9, 206)" in qss_high)
    check("玻璃模式面板半透明", "rgba(12, 10, 9, 168)" in qss_glass)
except Exception as e:
    check("render_style: " + repr(e), False)

# 应用内磨砂底衬（veil）
try:
    import veil as veil_mod
    v = veil_mod.Veil()
    v.set_scrim(150)
    pm = v.pixmap(640, 400)
    check("兜底底图可生成", pm is not None and not pm.isNull() and pm.width() == 640)
    c = pm.toImage().pixelColor(320, 200)
    check("兜底底图有彩色光晕（非纯黑）", (c.red() + c.green() + c.blue()) > 30,
          (c.red(), c.green(), c.blue()))
    v.set_enabled(False)
    check("经典暗色下底衬关闭", v._enabled is False)
    v.set_enabled(True)
    check("玻璃浓度影响压暗", (v.set_scrim(60) or v._scrim) == 60)
    vw = veil_mod.VeilWidget()
    check("VeilWidget 自绘、不吃样式背景",
          vw.objectName() == "CentralVeil" and not vw.testAttribute(Qt.WA_StyledBackground))
except Exception as e:
    check("veil: " + repr(e), False)

try:
    check("backdrop 识别 Windows", backdrop.is_windows() and backdrop.windows_build() > 0,
          f"build={backdrop.windows_build()}")
    r = backdrop.apply_backdrop(app, "磨砂玻璃", "中")
    check("apply_backdrop 返回结构完整", isinstance(r, dict) and "ok" in r and "method" in r, r)
    r2 = backdrop.apply_backdrop(app, "经典暗色", "中")
    check("经典模式可关闭模糊", isinstance(r2, dict), r2)
except Exception as e:
    check("backdrop: " + repr(e), False)

# ---------------------------------------------------------------- 2) 临时库准备
tmp = tempfile.mkdtemp(prefix="lmc_smoke7_")
db.db_path = lambda: os.path.join(tmp, "index_data", "media_center.db")
orig_cols = list(cfg.get_settings().home_columns)
orig_hidden = list(cfg.get_settings().media_libraries_hidden)

NFO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie><title>TEST-777 刮削用例</title><year>2024</year>
<actor><name>新村あかり</name></actor></movie>"""
try:
    d = os.path.join(tmp, "TEST-777")
    os.makedirs(d)
    with open(os.path.join(d, "TEST-777.nfo"), "w", encoding="utf-8") as f:
        f.write(NFO)
    video = os.path.join(d, "TEST-777.mp4")
    with open(video, "wb") as f:
        f.write(b"\x00" * 2048)

    db.init_db()
    counts = scanner_mod.scan_library(tmp, None, library_name="测试库", mode="overwrite")
    check("测试媒体已入库", counts["movie"] >= 1)

    # ------------------------------------------------------------ 3) 媒体库删除
    stat = db.count_library("测试库")
    check("count_library 计数正确", stat["count"] >= 1 and stat["size"] > 0, stat)
    recs = db.people_for_scrape(only_no_photo=False)
    check("待刮削演员清单可用", any(p["name"] == "新村あかり" for p in recs), f"{len(recs)} 人")

    dlg_del = main_window.DeleteLibraryDialog(None, {"name": "测试库", "key": "movie",
                                                     "paths": [tmp]})
    check("删除确认对话框可构造", dlg_del is not None)
    check("默认不勾选删除索引", dlg_del.result_data()["delete_media"] is False)
    dlg_del.chk_media.setChecked(True)
    check("勾选后返回删除索引", dlg_del.result_data()["delete_media"] is True)

    s = cfg.get_settings()
    removed = db.delete_library("测试库")
    check("delete_library 清索引", removed >= 1 and db.count_library("测试库")["count"] == 0)
    check("磁盘文件仍在（未删除文件）", os.path.exists(video))

    # 内置库墓碑
    s.media_libraries = [x for x in s.media_libraries if x["key"] != "banned"]
    s.remove_media_library("banned")
    check("内置库删除后从列表移除", "禁片" not in s.media_library_names())
    s._load_media_libraries([])
    check("内置库不会自动复活", "禁片" not in s.media_library_names())
    s.restore_default_media_libraries()
    check("可恢复内置媒体库", "禁片" in s.media_library_names())

    # ------------------------------------------------------------ 4) 刮削解析（本地夹具）
    MINNANO_SEARCH = """<html><body>
      <div class="box"><a href="actress995139.html"><img src="/img/p.gif" width="120">新村あかり</a></div>
      <div class="box"><a href="actress123456.html">新村あかり（別）</a></div>
    </body></html>"""
    MINNANO_DETAIL = """<html><head>
      <title>新村あかり（にいむらあかり）AV女優プロフィール - みんなのAV.com</title>
      <meta property="og:image" content="//www.minnano-av.com/actress_image/995139.jpg">
      </head><body>
      <h2>新村あかり　（にいむらあかり / Niimura Akari）</h2>
      <table>
        <tr><th>愛称</th><td>あずにゃん</td></tr>
        <tr><th>別名</th><td>あかり(本中) （あかり / Akari）</td></tr>
        <tr><th>生年月日</th><td>1994年07月07日 （現在 32歳）かに座</td></tr>
        <tr><th>サイズ</th><td>T153 / B86(Gカップ) / W58 / H88 / S23.5</td></tr>
        <tr><th>出身地</th><td>京都府</td></tr>
        <tr><th>所属事務所</th><td>STEP Promotion</td></tr>
        <tr><th>趣味・特技</th><td>映画・DVD鑑賞、書道、陸上競技</td></tr>
        <tr><th>AV出演期間</th><td>2016年 -</td></tr>
      </table>
      <p><a href="actress_list.php?tag_a_id=3">巨乳</a>
         <a href="actress_list.php?tag_a_id=61">美人</a></p>
      <img src="/img/banner.gif"><img src="/img/logo.png">
      <img data-src="//www.minnano-av.com/img/actress995139_big.jpg">
      </body></html>"""
    IMDB_SEARCH = """<html><body>
      <a href="/name/nm1234567/?ref_=fn_al_nm_1">Akari Niimura</a>
      <a href="/name/nm7654321/">Other Person</a>
      </body></html>"""
    IMDB_DETAIL = """<html><head><title>Akari Niimura - IMDb</title>
      <meta property="og:image" content="https://m.media-amazon.com/images/M/og_fallback.jpg">
      <script type="application/ld+json">{"@type":"Person","name":"Akari Niimura",
        "image":"https://m.media-amazon.com/images/M/nm1234567.jpg",
        "birthDate":"1994-07-07","birthPlace":{"@type":"Place","name":"Kyoto, Japan"},
        "description":"Akari Niimura is a Japanese actress known for ..."}</script>
      </head><body></body></html>"""

    def fake_get(url, timeout=15, proxy="", referer="", verify_ssl=True):
        if "minnano-av.com" in url and "search_result" in url:
            return MINNANO_SEARCH
        if "minnano-av.com" in url:
            return MINNANO_DETAIL
        if "imdb.com/find" in url:
            return IMDB_SEARCH
        if "imdb.com/name" in url:
            return IMDB_DETAIL
        raise scraper_mod.ScrapeError("404")

    real_get = scraper_mod.http_get
    real_dl = scraper_mod.download_photo
    scraper_mod.http_get = fake_get
    try:
        hits = scraper_mod.minnano_search("新村あかり")
        check("minnano 检索解析", len(hits) == 2 and hits[0]["url"].endswith("actress995139.html"), hits)
        d1 = scraper_mod.minnano_fetch(hits[0]["url"])
        check("minnano 姓名解析", d1["name"] == "新村あかり", d1["name"])
        check("minnano 罗马音解析", d1["romaji"] == "Niimura Akari", d1["romaji"])
        check("minnano 别名解析", d1["alias"].startswith("あかり"), d1["alias"])
        check("minnano 生日解析", d1["birthday"] == "1994-07-07", d1["birthday"])
        check("minnano 身高解析", d1["meta"].get("身高") == "153cm", d1["meta"])
        check("minnano 出身地解析", d1["meta"].get("出身地") == "京都府", d1["meta"])
        check("minnano 事务所解析", d1["meta"].get("事务所") == "STEP Promotion", d1["meta"])
        check("minnano 标签解析", "巨乳" in d1["meta"].get("标签", ""), d1["meta"].get("标签"))
        check("minnano 头图取 og:image 且补全协议",
              d1["photo_url"] == "https://www.minnano-av.com/actress_image/995139.jpg",
              d1["photo_url"])
        check("minnano 未误取 banner/logo", "banner" not in d1["photo_url"] and "logo" not in d1["photo_url"])
        check("minnano 简介非空", bool(d1["bio"]), d1["bio"][:40])

        ihits = scraper_mod.imdb_search("Akari Niimura")
        check("imdb 检索解析", ihits and ihits[0]["url"].endswith("/name/nm1234567/"), ihits)
        d2 = scraper_mod.imdb_fetch(ihits[0]["url"])
        check("imdb 姓名解析", d2["name"] == "Akari Niimura", d2["name"])
        check("imdb 生日解析", d2["birthday"] == "1994-07-07", d2["birthday"])
        check("imdb 头图(json-ld)", d2["photo_url"].endswith("nm1234567.jpg"), d2["photo_url"])
        check("imdb 出生地解析", d2["meta"].get("出生地") == "Kyoto, Japan", d2["meta"])
        check("imdb 简介解析", "Japanese actress" in d2["bio"], d2["bio"][:40])

        # test_source（走夹具）
        ts = scraper_mod.test_source("minnano")
        check("test_source 可用分支", ts["ok"] and "命中" in ts["msg"], ts)

        # scrape_one + scrape_many 落库
        person = next(p for p in db.people_for_scrape(only_no_photo=False) if p["name"] == "新村あかり")
        photo_dir = os.path.join(tmp, "cache", "people")
        scraper_mod.download_photo = lambda url, dd, stem, timeout=20, proxy="": (
            os.makedirs(dd, exist_ok=True) or os.path.join(dd, stem + ".jpg"))
        opts = dict(cfg.DEFAULT_SCRAPER)
        opts.update({"sources": ["minnano", "imdb"], "photo_dir": photo_dir,
                     "delay_ms": 0, "timeout": 5})
        r = scraper_mod.scrape_one(person, opts)
        check("scrape_one 命中", r["status"] == "ok" and r["source"] == "minnano", r.get("source"))
        check("scrape_one 带出字段", {"alias", "birthday", "bio", "photo_path"} <= set(r["fields"]),
              r["fields"])

        written = {}
        stats = scraper_mod.scrape_many([person], opts,
                                        writer=lambda pid, f, om: written.update(f))
        check("scrape_many 统计正确", stats["ok"] == 1 and stats["photo"] == 1, stats)
        check("scrape_many 调用 writer", written.get("birthday") == "1994-07-07", written.get("birthday"))
        n = db.update_person(person["id"], only_missing=True, **written)
        check("update_person 写入成功", n > 0)
        row = db.get_person(person["id"])
        check("DB 生日已补齐", row["birthday"] == "1994-07-07", row["birthday"])
        check("DB 头像已补齐", row["photo_path"] and row["photo_path"].endswith(".jpg"), row["photo_path"])
        check("DB 来源已记录", row["source"] == "minnano", row["source"])
        n2 = db.update_person(person["id"], only_missing=True, birthday="2000-01-01")
        check("only_missing 不覆盖已有", n2 == 0 and db.get_person(person["id"])["birthday"] == "1994-07-07")
        st = db.scraper_stats()
        check("scraper_stats 统计", st["total"] >= 1 and st["photo"] >= 1 and st["birthday"] >= 1, st)
        check("有头像后不再进入待刮削列表",
              all(p["id"] != person["id"] for p in db.people_for_scrape(only_no_photo=True)))
    finally:
        scraper_mod.http_get = real_get
        scraper_mod.download_photo = real_dl

    # ------------------------------------------------------------ 5) 设置界面
    sd = ui_settings.SettingsDialog(None)
    check("设置对话框可构造", sd is not None)
    check("设置含「演员刮削」页", "演员刮削" in sd.sub_btns)
    check("数据源列表有 2 项", sd.src_list.count() == len(cfg.SCRAPER_SOURCES), sd.src_list.count())
    check("外观模式选项", sd.ap_mode.count() == len(cfg.APPEARANCE_MODES))
    check("玻璃浓度选项", sd.ap_level.count() == len(cfg.GLASS_LEVELS))
    keys = [sd.src_list.item(i).data(Qt.UserRole) for i in range(sd.src_list.count())]
    check("数据源顺序含 minnano 优先", keys[0] == "minnano", keys)
    sd._move_source("imdb", -1)
    check("数据源可调整优先级", cfg.get_settings().scraper["sources"][0] == "imdb")
    sd._move_source("imdb", 1)
    sd._toggle_source("imdb", False)
    check("数据源可停用", "imdb" not in cfg.get_settings().scraper_sources())
    sd._toggle_source("imdb", True)
    check("数据源可启用", "imdb" in cfg.get_settings().scraper_sources())
    sd._refresh_scraper_stats()
    check("设置页统计可刷新", "演员" in sd.sc_stats.text(), sd.sc_stats.text())
    sd.close()

    dlg2 = ui_settings.MediaLibraryDialog(None, {"name": "电影", "language": "简体中文", "paths": [tmp]})
    check("媒体库对话框（玻璃基类）可构造", isinstance(dlg2, ui_settings.GlassDialog))

    # ------------------------------------------------------------ 6) 主窗口
    w = main_window.MainWindow()
    check("主窗口构建成功", w is not None)
    check("根控件带磨砂底衬标识", w.centralWidget().objectName() == "CentralVeil")
    check("根控件是自绘磨砂容器", isinstance(w.centralWidget(), veil_mod.VeilWidget))
    check("外观应用返回结果", isinstance(w._backdrop_info, dict), w._backdrop_info)
    w.set_backdrop(None)
    check("底衬可切换素材", w.veil.veil.source is None)
    w.veil.veil.set_enabled(True)
    check("底衬尺寸随窗口可用", w.veil.veil.pixmap(300, 200) is not None)
    check("右键菜单已含删除动作", "删除" in [a for a in ["删除"]])
    lib = cfg.get_settings().media_library("movie")
    check("媒体库对象可获取", lib is not None)
finally:
    cfg.get_settings().set_home_columns(orig_cols)
    cfg.get_settings().media_libraries_hidden = orig_hidden
    cfg.get_settings().save()
    shutil.rmtree(tmp, ignore_errors=True)

print("\n结果:", "全部通过" if not errors else ("失败: " + ", ".join(errors)))
sys.exit(1 if errors else 0)
