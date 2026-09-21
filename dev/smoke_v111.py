# -*- coding: utf-8 -*-
"""v1.11.0 离线冒烟测试：修复「所有卡片都异常」。

覆盖：
- 演员卡：☆/▲ 可见（全局 QPushButton padding 压没字形的根因）、紧凑定高无大片空白、
          六项信息恒显示（缺→—）、现役绿/退役黄/选中粉、乱码 meta 被清洗
- 影片卡：高度分区相加 = 卡片高（原先溢出 14px 把「导演」行裁掉）、小字恒两行、选中流光内缩不裁
- 数据层：_clean_meta_value / _parse_meta 容错 / _person_status 推断 / all_people_ordered.last_year
- 回填：scanner.backfill_people_links 给旧索引补 Director 关联（幂等）
- 刮削：minnano 不再把 <meta og:description> 样板文案写进 meta（真机乱码根因）
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
import nfo_parser as nfo_mod
import scraper as scraper_mod
import version as ver

errors = []


def check(name, cond, extra=""):
    print(("OK  " if cond else "FAIL") + " - " + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        errors.append(name)


tmp = tempfile.mkdtemp(prefix="lmc_smoke11_")
db.db_path = lambda: os.path.join(tmp, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(tmp, "settings.json")
cfg._SETTINGS = None

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from main_window import (
        _parse_size, _parse_meta, _clean_meta_value, _person_status, _clip_text,
        ActorCard, PosterCard, MainWindow,
        POSTER_H, POSTER_CARD_W, POSTER_CARD_H,
        _CARD_PAD, _CARD_SPACING, _TITLE_H, _SUB_H, _CREW_H,
        ACTOR_CARD_W, ACTOR_CARD_H, _ACTOR_FACTS,
    )
    check("import 全部模块", True)

    app = QApplication.instance() or QApplication([])
    check("版本号为 v1.11.0", ver.VERSION == "v1.11.0", ver.FULL_VERSION)

    # ============================================================ 影片卡高度（无溢出/无裁切）
    need = _CARD_PAD * 2 + POSTER_H + _CARD_SPACING * 3 + _TITLE_H + _SUB_H + _CREW_H
    check("影片卡高 = 各分区相加（不再溢出）", POSTER_CARD_H == need,
          "card=%s need=%s" % (POSTER_CARD_H, need))
    check("影片卡高不再等于旧的 POSTER_H+92", POSTER_CARD_H != POSTER_H + 92,
          POSTER_CARD_H)

    # ============================================================ 需求4 导演抓取 + 影片卡
    NFO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <movie><title>DIRTEST 导演用例</title><year>2024</year>
    <actor><name>演员甲</name></actor>
    <actor><name>演员乙</name></actor>
    <director>导演一</director>
    <director>导演二</director>
    </movie>"""
    d = os.path.join(tmp, "DIRTEST")
    os.makedirs(d)
    with open(os.path.join(d, "DIRTEST.nfo"), "w", encoding="utf-8") as f:
        f.write(NFO)
    video = os.path.join(d, "DIRTEST.mp4")
    with open(video, "wb") as f:
        f.write(b"\x00" * 2048)
    db.init_db()
    counts = scanner_mod.scan_library(tmp, None, library_name="测试库", mode="overwrite")
    check("测试媒体已入库", counts["movie"] >= 1)
    mid = db.media_id_by_path(video)
    crew = db.cast_crew_map().get(mid, {})
    check("导演被抓取并关联",
          "导演一" in crew.get("directors", "") and "导演二" in crew.get("directors", ""), crew)
    check("演员被抓取并关联",
          "演员甲" in crew.get("actors", "") and "演员乙" in crew.get("actors", ""), crew)
    check("nfo_parser.parse_any 分派 movie", nfo_mod.parse_any(
        os.path.join(d, "DIRTEST.nfo")).get("kind") == "movie")

    media = db.get_media(mid)
    card = PosterCard(media, lambda m: None, crew.get("actors", ""), crew.get("directors", ""))
    card.show()
    app.processEvents()
    check("影片卡渲染不崩(offscreen)", True)
    txt = card._facts.text()
    check("影片卡小字有「演员：」行", "演员：" in txt, txt)
    check("影片卡小字有「导演：」行（此前被裁掉）", "导演：" in txt, txt)
    check("影片卡小字两行都在可视区内",
          card._facts.geometry().bottom() <= card.height() - _CARD_PAD and
          card._facts.geometry().top() >= 0,
          (card._facts.geometry().top(), card._facts.geometry().bottom(), card.height()))
    # 无演员/导演时也要有占位，避免高度塌陷
    c2 = PosterCard(media, lambda m: None, "", "")
    c2.show(); app.processEvents()
    check("影片卡无演员导演时显示占位 —", "演员：—" in c2._facts.text()
          and "导演：—" in c2._facts.text(), c2._facts.text())
    check("影片卡带导演文字", "导演：导演一" in txt, txt)
    card.set_selected(True)
    app.processEvents()
    check("影片卡选中态(粉色流光)不崩", card._selected is True)
    card.set_selected(False)
    check("影片卡取消选中", card._selected is False)

    # 超长标题必须压进 2 行（否则第 3 行被定高裁掉一半，看着就是「卡片异常」）
    long_m = db.get_media(mid)
    long_m["title"] = ("390JAC-240 【デカ乳マゾ雌】セフレの品格。富裕層の貪欲な肉欲、"
                       "キャビアよりJP産精子。25歳、社長秘書。 「白雪美月」")
    lc = PosterCard(long_m, lambda m: None, "白雪美月", "真咲南朋")
    lc.show(); app.processEvents()
    tl = [x for x in lc.findChildren(type(card._facts))
          if x.objectName() == "CardTitle"][0]
    _fm = tl.fontMetrics()
    _h = _fm.boundingRect(0, 0, tl.width(), 100000, Qt.TextWordWrap, tl.text()).height()
    check("超长标题压进 2 行（不再露出半截第三行）",
          _h <= _fm.lineSpacing() * 2, (_h, _fm.lineSpacing() * 2, tl.text()))
    check("超长标题以 … 收尾", tl.text().endswith("…"), tl.text())
    check("标题完整文本进 tooltip", tl.toolTip() == long_m["title"][:len(tl.toolTip())] or
          tl.toolTip() == long_m["title"], tl.toolTip()[:40])
    lc.close()
    c2.close()
    card.close()

    # ============================================================ 演员卡：尺寸 / 按钮 / 字段
    pids = [db.upsert_person(nm, "Actor", None) for nm in ("绿现役", "黄退役", "灰未知")]
    db.update_person(pids[0], only_missing=False, birthday="1999-01-01", status="现役",
                     meta=json.dumps({"出身地": "东京", "身高": "163cm", "尺寸": "T163/B85/W58/H83"}))
    db.update_person(pids[1], only_missing=False, birthday="1990-05-05", status="退役",
                     meta=json.dumps({"出身地": "大阪", "身高": "158cm", "尺寸": "T158/B80/W55/H80"}))
    db.toggle_person_favorite(pids[2])
    db.toggle_person_pinned(pids[1])
    ordered = db.all_people_ordered("Actor")
    idx = {p["id"]: i for i, p in enumerate(ordered)}
    check("排序：置顶在第一", ordered[0]["id"] == pids[1], [p["name"] for p in ordered])
    check("排序：收藏在其次", ordered[1]["id"] == pids[2])
    check("排序：置顶>收藏>其余(三者相对序正确)",
          idx[pids[1]] < idx[pids[2]] < idx[pids[0]], idx)
    check("all_people_ordered 带出 last_year 字段", "last_year" in ordered[0],
          list(ordered[0].keys())[:6])

    ac0 = ActorCard(db.get_person(pids[0]), on_open=lambda p: None, on_fav=lambda p: None,
                    on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
    ac0.show(); app.processEvents()
    check("演员卡(现役)渲染不崩", True)
    check("演员卡紧凑定高（无大片空白）", ACTOR_CARD_H <= 170, ACTOR_CARD_H)
    check("演员卡尺寸固定", ac0.width() == ACTOR_CARD_W and ac0.height() == ACTOR_CARD_H)
    f = ac0._facts.text()
    check("演员卡六项信息齐全",
          all(k in f for k in ("出生", "出身地", "身高", "三围", "胸围")), f)
    check("演员卡值正确（生日/出身地/身高）",
          "1999-01-01" in f and "东京" in f and "163cm" in f, f)
    check("演员卡三围/胸围解析", "胸85" in f and "腰58" in f and "臀83" in f and "85cm" in f, f)

    # ☆/▲ 可见性 —— 根因是全局 QSS `QPushButton{padding:7px 14px}` 把 26×26 内容区压负
    st_ss, pn_ss = ac0._star.styleSheet(), ac0._pin.styleSheet()
    check("☆按钮样式补 padding:0（否则字形被裁没）",
          "padding:0" in st_ss and "min-width:0" in st_ss, st_ss)
    check("▲按钮样式补 padding:0", "padding:0" in pn_ss and "min-width:0" in pn_ss, pn_ss)
    check("☆/▲ 非零尺寸", ac0._star.width() > 0 and ac0._star.height() > 0,
          (ac0._star.size().toTuple(), ac0._pin.size().toTuple()))
    check("☆/▲ 落在卡片内（右上角）",
          ac0._star.x() + ac0._star.width() <= ac0.width() and
          ac0._pin.x() >= 0 and ac0._star.y() < ac0.height() // 2,
          (ac0._pin.pos().toTuple(), ac0._star.pos().toTuple(), ac0.width()))
    check("☆ 字形宽度放得下（padding:0 后内容区足够）",
          ac0._star.fontMetrics().horizontalAdvance("☆") <= ac0._star.width() + 4,
          (ac0._star.fontMetrics().horizontalAdvance("☆"), ac0._star.width()))
    check("未收藏/未置顶显示 ☆ / △",
          ac0._star.text() == "☆" and ac0._pin.text() == "△",
          (ac0._star.text(), ac0._pin.text()))
    # 现役 → 绿；徽标文字
    check("现役状态徽标", "现役" in ac0._status_badge.text(), ac0._status_badge.text())

    ac1 = ActorCard(db.get_person(pids[1]), on_open=lambda p: None, on_fav=lambda p: None,
                    on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
    ac1.show(); app.processEvents()
    check("退役状态徽标", "退役" in ac1._status_badge.text(), ac1._status_badge.text())
    check("已置顶显示 ▲ / 收藏显示 ★",
          ac1._pin.text() == "▲" and ac1._star.text() == "☆",
          (ac1._pin.text(), ac1._star.text()))
    ac2 = ActorCard(db.get_person(pids[2]), on_open=lambda p: None, on_fav=lambda p: None,
                    on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
    ac2.show(); app.processEvents()
    check("已收藏显示 ★", ac2._star.text() == "★", ac2._star.text())
    ac1.set_selected(True); app.processEvents()
    check("演员卡选中(粉色流光)不崩", ac1._selected is True)
    ac1.set_selected(False); app.processEvents()
    check("演员卡取消选中不崩", ac1._selected is False)
    ac0.close(); ac1.close(); ac2.close()

    # ============================================================ 乱码清洗（真机库数据）
    RAW_ADDR = "：東京都。AV女優、アダルトビデオ、無料動画について、みんなで情報交換しよう。\"> <meta property=\"og:description\" content=\"北岡"
    check("_clean_meta_value 抢救乱码出身地 → 東京都",
          _clean_meta_value(RAW_ADDR) == "東京都", _clean_meta_value(RAW_ADDR))
    check("_clean_meta_value 丢弃纯样板（尺寸/事务所）",
          _clean_meta_value("、所属事務所など）を掲載。現在30歳。AV女優、アダルトビデオ。") == "",
          _clean_meta_value("、所属事務所など）を掲載。現在30歳。AV女優、アダルトビデオ。"))
    check("_clean_meta_value 保留正常值", _clean_meta_value("東京都") == "東京都")
    check("_clean_meta_value 保留正常尺寸串",
          _clean_meta_value("T153 / B86 / W58 / H88") == "T153 / B86 / W58 / H88")

    pid_g = db.upsert_person("乱码演员", "Actor", None)
    db.update_person(pid_g, only_missing=False, birthday="", status="",
                     meta=json.dumps({"出身地": RAW_ADDR,
                                      "尺寸": "、所属事務所など）を掲載。現在30歳。AV女優。",
                                      "身高": "など）を掲載。現在23歳。AV女優。"}))
    acg = ActorCard(db.get_person(pid_g), on_open=lambda p: None, on_fav=lambda p: None,
                    on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
    acg.show(); app.processEvents()
    gt = acg._facts.text()
    check("乱码 meta 不落到卡片上", not any(t in gt for t in
          ("property=", "content=", "og:", "<meta", "掲載")), gt)
    check("乱码 meta 中的出身地被抢救显示", "東京都" in gt, gt)
    check("无法抢救的字段回落到 —", gt.count("—") >= 2, gt)
    acg.close()

    # 非法 JSON 的 meta（真机库里 6 条属此类）也要尽量读出来
    bad_meta = '{"出身地": "：福岡県。AV女優、', # 被截断
    pm = _parse_meta(bad_meta)
    check("_parse_meta 容错非法 JSON", pm.get("出身地", "").startswith("：福岡県"),
          pm)
    check("_parse_meta 正常 JSON", _parse_meta(json.dumps({"a": "b"})) == {"a": "b"})

    # ============================================================ 状态推断（作品年份）
    check("_person_status 手动值优先（现役）",
          _person_status({"status": "现役", "last_year": 2001}) == "现役")
    check("_person_status 手动值优先（退役）",
          _person_status({"status": "退役", "last_year": 2099}) == "退役")
    check("_person_status 近两年作品 → 现役",
          _person_status({"status": "", "last_year": 2026}) == "现役")
    check("_person_status 陈旧作品 → 退役",
          _person_status({"status": "", "last_year": 2012}) == "退役")
    check("_person_status 无作品 → 空（未知）",
          _person_status({"status": "", "last_year": None}) == "")
    # 详情页也要能推断：get_person 必须带出 last_year（否则永远判成「未知」）
    gp = db.get_person(pids[0])
    check("get_person 带出 works / last_year",
          "works" in gp and "last_year" in gp, sorted(gp.keys())[-4:])
    check("get_person 的 last_year 可喂给 _person_status",
          _person_status(db.get_person(pids[1])) == "退役")
    # 真机场景：85 位演员 status 全空、靠 last_year 着色
    db.update_person(pid_g, only_missing=False, status="")
    check("演员卡不因 status 空而报错", ActorCard(
        db.get_person(pid_g), on_open=lambda p: None, on_fav=lambda p: None,
        on_pin=lambda p: None, on_select=lambda c: None, main_win=None).width() > 0)

    # ============================================================ 导演关联回填（旧索引）
    # 模拟旧版索引：只留 Actor 关联、把 Director 关联清掉
    db.clear_media_people(mid)
    scanner_mod._link_actors(mid, nfo_mod.parse_any(os.path.join(d, "DIRTEST.nfo"))["actors"])
    check("模拟旧索引：Director 关联为 0", db.count_people_links("Director") == 0,
          db.count_people_links("Director"))
    stats = scanner_mod.backfill_people_links()
    check("回填执行（有变更才写库）", stats["media"] >= 1, stats)
    crew2 = db.cast_crew_map().get(mid, {})
    check("回填后导演关联已补齐",
          "导演一" in crew2.get("directors", "") and "导演二" in crew2.get("directors", ""), crew2)
    check("回填后演员仍在", "演员甲" in crew2.get("actors", ""), crew2)
    stats2 = scanner_mod.backfill_people_links()
    check("回填幂等（内容一致即跳过）", stats2["media"] == 0 and stats2["skipped"] >= 1, stats2)

    # ============================================================ 刮削：不再写样板文案乱码
    PAGE = """<html><head>
    <meta property="og:description" content="みんなのAV。生年月日、出身地、サイズ、所属事務所など）を掲載。現在30歳。出身地：東京都。AV女優、アダルトビデオ、無料動画について、みんなで情報交換しよう。">
    <meta property="og:image" content="https://www.minnano-av.com/img/actress999.jpg">
    <title>新村あかりAV女優プロフィール - みんなのAV</title></head>
    <body>
    <h1>新村あかり（にいむらあかり / Niimura Akari）</h1>
    <table class="profile">
      <tr><th>生年月日</th><td>1994年07月07日 （現在 32歳）かに座</td></tr>
      <tr><th>サイズ</th><td>T153 / B86(Gカップ) / W58 / H88</td></tr>
      <tr><th>出身地</th><td>京都府</td></tr>
      <tr><th>所属事務所</th><td>テストプロ</td></tr>
      <tr><th>AV出演期間</th><td>2023年 - 現在</td></tr>
      <tr><th>趣味・特技</th><td>お菓子作り</td></tr>
    </table>
    </body></html>"""
    real_get = scraper_mod.http_get
    scraper_mod.http_get = lambda url, timeout=15, proxy="", referer="", **kw: PAGE
    try:
        sd = scraper_mod.minnano_fetch("https://www.minnano-av.com/actress999.html")
        sm = sd.get("meta", {})
        check("刮削：出身地取自正文表格（不再是 head 样板）", sm.get("出身地") == "京都府", sm)
        check("刮削：事务所取正文", sm.get("事务所") == "テストプロ", sm.get("事务所"))
        check("刮削：尺寸取正文", "B86" in sm.get("尺寸", ""), sm.get("尺寸"))
        check("刮削：生日解析", sd.get("birthday") == "1994-07-07", sd.get("birthday"))
        check("刮削：meta 里不再有 HTML 残片/样板文案",
              not any(t in str(sm) for t in ("property=", "content=", "og:", "<meta", "掲載", "情報交換")),
              sm)
        check("刮削：出演期間开区间 → 现役", sd.get("status") == "现役", sd.get("status"))
        # 闭区间 → 退役；全角数字也要能识别
        scraper_mod.http_get = lambda url, timeout=15, proxy="", referer="", **kw: PAGE.replace(
            "2023年 - 現在", "2015年 - 2019年")
        sd2 = scraper_mod.minnano_fetch("https://www.minnano-av.com/actress999.html")
        check("刮削：闭区间 → 退役", sd2.get("status") == "退役", sd2.get("status"))
        scraper_mod.http_get = lambda url, timeout=15, proxy="", referer="", **kw: PAGE.replace(
            "2023年 - 現在", "２０２４～")
        sd3 = scraper_mod.minnano_fetch("https://www.minnano-av.com/actress999.html")
        check("刮削：全角数字+开区间 → 现役", sd3.get("status") == "现役", sd3.get("status"))
    finally:
        scraper_mod.http_get = real_get

    # ============================================================ 主窗口
    w = MainWindow()
    check("主窗口构造成功（含演职员关联回填）", w is not None)
    ap = w._view_actors()
    check("演员库页面可构造(卡片网格)", ap is not None)
    w._select_card(None)
    w._backfill_crew()
    check("_backfill_crew 二次调用无异常（幂等）", True)
    w.close()
    check("closeEvent 执行无异常", True)

except Exception as e:
    check("运行期异常: " + repr(e), False)
    import traceback
    traceback.print_exc()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n结果:", "全部通过" if not errors else ("失败: " + ", ".join(errors)))
sys.exit(1 if errors else 0)
