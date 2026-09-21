# -*- coding: utf-8 -*-
"""v1.11.1 离线冒烟测试：5 项反馈的修复回归。

覆盖：
1. 演员信息：minnano 解析器把「出身地/生日/身高/三围」解析对（出身地只在 head 的
   description 里，正文整行缺席）＋旧库乱码在显示层被抢救、别名/名字不再带站内后缀
2. 内容卡片设置：年份 / 演员 / 导演 三个开关存在且生效；卡片按实际行数动态定高
3. 设置页导航 ↑ ↓ 按钮（窄按钮）不再被全局 padding 压没字形
4. 顶栏 ← → 按钮同上
5. ToggleSwitch 动画不再被 GC 冻结（parent 持有 + 终值对齐 + 颜色随进度插值）

全程离线：网络用本地 HTML 夹具 monkeypatch，数据库用临时库。
"""
import os
import sys
import json
import time
import tempfile
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import config as cfg
import scraper as scraper_mod
import version as ver

errors = []


def check(name, cond, extra=""):
    print(("OK  " if cond else "FAIL") + " - " + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        errors.append(name)


tmp = tempfile.mkdtemp(prefix="lmc_smoke112_")
DBP = os.path.join(tmp, "index_data", "media_center.db")
db.db_path = lambda: DBP
cfg.config_path = lambda: os.path.join(tmp, "settings.json")
cfg._SETTINGS = None

# ------------------------------------------------------------------ 夹具页面
# 结构照抄真机页面（minnano actress 页）：head 里有 og:description 样板，
# 正文表格里是「生年月日 / サイズ / 所属事務所 / AV出演期間 / デビュー作品」。
# 注意：正文里**没有**「出身地」这一行（实测真机 0 次），只能从 description 取。
BOILER = ("（生年月日、出身地、サイズ、所属事務所など）を掲載。現在27歳。"
          "AV女優、アダルトビデオ、無料動画について、みんなで情報交換しよう。")
FIXTURE = """<html><head>
<meta name="description" content="テスト花子（てすとはなこ）のプロフィール。{boil}出身地：山梨県。">
<meta property="og:description" content="テスト花子（てすとはなこ）。{boil}出身地：山梨県。">
<meta property="og:image" content="https://www.minnano-av.com/picture/actress999999.jpg">
<title>テスト花子 - みんなのAV女優</title>
</head><body>
<h1>テスト花子 てすとはなこ / Test Hanako</h1>
<table>
<tr><td><span>別名</span><p>朝海 汐「AV女優」 （あさみ しお / ）</p></td></tr>
<tr><td><span>生年月日</span><p>1999年04月03日 （現在 <a href="x">27歳</a>）おひつじ座</td></p></td></tr>
<tr><td><span>サイズ</span><p>T160 / B96(<a href="x">Jカップ</a>) / W58 / H92 / S</p></td></tr>
<tr><td><span>所属事務所</span><p><a href="x">ACT(アクト)</a></p></td></tr>
<tr><td><span>AV出演期間</span><p>2025年 -</p></td></tr>
<tr><td><span>デビュー作品</span><p>テスト（2025年09月 05日）</p></td></tr>
</table>
</body></html>""".replace("{boil}", BOILER)

try:
    from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QPushButton
    from PySide6.QtGui import QPixmap, QColor
    from main_window import (
        _parse_size, _parse_meta, _clean_meta_value, _person_status,
        ActorCard, PosterCard, MainWindow, poster_card_height,
        POSTER_H, POSTER_CARD_W, POSTER_CARD_H, _CARD_PAD, _CARD_SPACING,
        _TITLE_H, _SUB_H, _LINE_H, ACTOR_CARD_W, load_style,
    )
    import ui_settings as ui_set          # noqa: F401  （仅确认可导入）
    from ui_settings import SettingsDialog, ToggleSwitch
    check("import 全部模块", True)

    app = QApplication.instance() or QApplication([])
    # 先注册中文字体并套上 QSS 再建控件：单元格是富文本，sizeHint 走真实字体度量。
    # 不注册的话离屏会落到替代字体，量出来的宽度虚高（曾误报「出生」溢出）。
    from PySide6.QtGui import QFontDatabase
    for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
        if os.path.exists(_f):
            QFontDatabase.addApplicationFont(_f)
    load_style(app)
    check("版本号为 v1.11.1", ver.VERSION == "v1.11.1", ver.FULL_VERSION)

    # ============================================ 1) 演员信息：刮削解析（离线夹具）
    scraper_mod.http_get = lambda url, timeout=15, proxy="", referer="": FIXTURE
    d = scraper_mod.minnano_fetch("https://www.minnano-av.com/actress999999.html")
    check("姓名剥掉假名与罗马音", d["name"] == "テスト花子", repr(d["name"]))
    check("别名不是「データを編集」类页面文案",
          d["alias"] == "朝海 汐", repr(d["alias"]))
    check("生日解析（正文表格）", d["birthday"] == "1999-04-03", d["birthday"])
    check("身高解析", d["meta"].get("身高") == "160cm", d["meta"].get("身高"))
    check("三围尺寸解析", "B96" in (d["meta"].get("尺寸") or ""), d["meta"].get("尺寸"))
    check("罩杯解析", d["meta"].get("罩杯") == "J", d["meta"].get("罩杯"))
    check("出身地取自 description（正文没有该行）",
          d["meta"].get("出身地") == "山梨県", d["meta"].get("出身地"))
    check("事务所 / 出演期间 / 出道作", d["meta"].get("事务所") == "ACT(アクト)"
          and d["meta"].get("出演期間") == "2025年 -" and bool(d["meta"].get("出道作")),
          d["meta"].get("事务所"))
    check("状态由开区间出演期间推断为现役", d["status"] == "现役", d["status"])
    check("刮到的尺寸能被卡片解析成胸/腰/臀",
          _parse_size(d["meta"].get("尺寸")) == ("96", "58", "92"),
          _parse_size(d["meta"].get("尺寸")))
    junk = ("掲載", "情報交換", "無料動画", "アダルトビデオ", "og:", "property=", "content=")
    blob = json.dumps(d, ensure_ascii=False)
    check("解析结果不含任何站内样板文案", not any(j in blob for j in junk),
          [j for j in junk if j in blob])
    check("_valid_value 拦掉页面功能文案",
          not scraper_mod._valid_value("データを編集")
          and not scraper_mod._valid_value("ログイン後、編集できます")
          and scraper_mod._valid_value("朝海 汐"))
    check("_description_texts 能取出 description",
          any("出身地" in x for x in scraper_mod._description_texts(FIXTURE)))

    # ============================================ 1b) 老库乱码：显示层抢救
    junk_meta = json.dumps({"出身地": "：山梨県。AV女優、アダルトビデオ…\"> <meta property=\"og:descr",
                            "尺寸": "、所属事務所など）を掲載。現在27歳。AV女優、…\"> <meta property=\"og:d",
                            "出演期間": "2016年 -"}, ensure_ascii=False)
    check("_clean_meta_value 从乱码里抢救出出身地",
          _clean_meta_value("：山梨県。AV女優、アダルトビデオ…") == "山梨県",
          _clean_meta_value("：山梨県。AV女優、アダルトビデオ…"))
    check("_clean_meta_value 对无意义乱码返回空（宁缺勿脏）",
          _clean_meta_value("、所属事務所など）を掲載。現在27歳。AV女優、…") == "")
    p_junk = {"id": 1, "name": "测试演员", "meta": junk_meta, "birthday": None,
              "status": "现役", "favorite": 0, "pinned": 0, "thumb": "", "last_year": 2026}
    ac = ActorCard(p_junk, on_open=lambda p: None, on_fav=lambda p: None,
                   on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
    facts_txt = ac._facts.text()
    check("演员卡把抢救出的出身地显示出来", "山梨県" in facts_txt, facts_txt.replace("\n", " | "))
    check("演员卡不再出现乱码痕迹",
          not any(j in facts_txt for j in ("掲載", "og:", "青property", "property=")),
          facts_txt.replace("\n", " | "))
    ac_clean = ActorCard({"id": 2, "name": "干净", "meta": "{}", "birthday": "1999-04-03",
                          "status": "", "favorite": 0, "pinned": 0, "last_year": 2026},
                         on_open=lambda p: None, on_fav=lambda p: None,
                         on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
    check("演员卡出生字段显示生日", "1999-04-03" in ac_clean._facts.text())

    # 三围的值形如「胸92·腰58·臀89」，放半边卡（列宽 ≈101px）会被硬裁掉尾巴。
    p_sz = {"id": 3, "name": "尺寸测试", "birthday": "1994-01-16", "status": "现役",
            "favorite": 0, "pinned": 0, "thumb": "", "last_year": 2026,
            "meta": json.dumps({"尺寸": "T158 / B92(E) / W58 / H89", "身高": "158cm",
                                "出身地": "山梨県"}, ensure_ascii=False)}
    ac_sz = ActorCard(p_sz, on_open=lambda p: None, on_fav=lambda p: None,
                      on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
    ac_sz.show()
    app.processEvents()
    over = [(k, c.sizeHint().width(), c.width())
            for k, c in ac_sz._fact_cells.items() if c.sizeHint().width() > c.width()]
    check("演员卡五项信息都不超出单元格（长值不被裁）", not over, over)
    check("三围整行跨列（宽度接近整卡）",
          ac_sz._fact_cells["三围"].width() > ACTOR_CARD_W * 0.7,
          ac_sz._fact_cells["三围"].width())

    # ============================================ 1c) 修复清单（临时库）
    db.init_db()
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO people (id,name,role_type,alias,birthday,source_url,scraped_at,meta,bio)"
        " VALUES (1,'脏记录','Actor','朝海 汐「AV女優」',NULL,'https://x/1.html','2026-09-18 18:35:16',?,?)",
        (junk_meta, "出身地 山梨県 ｜ " + BOILER))
    conn.execute(
        "INSERT INTO people (id,name,role_type,birthday,source_url,scraped_at,meta)"
        " VALUES (2,'干净记录','Actor','1990-01-01','https://x/2.html','2026-09-18 18:35:16',?)",
        (json.dumps({"出身地": "東京都"}, ensure_ascii=False),))
    conn.commit()
    conn.close()
    rep = db.people_needing_repair()
    check("需修复清单只挑出被污染/缺生日的记录",
          [r["id"] for r in rep] == [1], [(r["id"], r["name"]) for r in rep])
    check("count_needing_repair 与清单一致", db.count_needing_repair() == len(rep))
    check("scraper_stats 带出 repair 计数", db.scraper_stats().get("repair") == len(rep),
          db.scraper_stats())

    # ============================================ 2) 内容卡片开关
    check("config 默认带 show_year/show_actors/show_directors",
          all(k in cfg.DEFAULT_CONTENT_CARDS
              for k in ("show_year", "show_actors", "show_directors")),
          sorted(cfg.DEFAULT_CONTENT_CARDS))
    s = cfg.get_settings()
    media = {"id": 1, "title": "T-1 测试标题", "year": 2026, "quality": "1080P",
             "rating": 9.1, "poster": "", "thumb": ""}

    def card_height(cc):
        s.content_cards.update(cc)
        c = PosterCard(media, lambda m: None, "演员甲", "导演乙")
        return c.height()

    h_all = card_height({"show_rating": True, "show_year": True, "show_quality": True,
                         "show_actors": True, "show_directors": True})
    check("全开时卡高 == POSTER_CARD_H", h_all == POSTER_CARD_H == 350,
          "h_all=%s POSTER_CARD_H=%s" % (h_all, POSTER_CARD_H))
    check("卡高不变式：poster_card_height(2,True) 与分区相加一致",
          poster_card_height(2, True) ==
          _CARD_PAD * 2 + POSTER_H + _CARD_SPACING * 3 + _TITLE_H + _SUB_H + _LINE_H * 2)
    h_all_off = card_height({"show_rating": False, "show_year": False, "show_quality": False,
                             "show_actors": False, "show_directors": False})
    check("全关时卡高 == poster_card_height(0,False)（不留空白）",
          h_all_off == poster_card_height(0, False), h_all_off)
    check("全关时卡片只作用于图片+标题", h_all_off < h_all)

    s.content_cards.update({"show_rating": True, "show_year": True, "show_quality": True,
                            "show_actors": True, "show_directors": False})
    c1 = PosterCard(media, lambda m: None, "演员甲", "导演乙")
    check("关导演后小字只有演员一行", c1._facts.text() == "演员：演员甲", repr(c1._facts.text()))
    check("关导演后卡高少一行", c1.height() == poster_card_height(1, True), c1.height())
    s.content_cards.update({"show_actors": False, "show_directors": True})
    c2 = PosterCard(media, lambda m: None, "演员甲", "导演乙")
    check("只显示导演时小字为导演一行", c2._facts.text() == "导演：导演乙", repr(c2._facts.text()))
    s.content_cards.update({"show_actors": True, "show_directors": True,
                            "show_year": False})
    c3 = PosterCard(media, lambda m: None, "演员甲", "导演乙")
    subs = [l.text() for l in c3.findChildren(QLabel) if l.objectName() == "CardSub"]
    check("关年份后副标题不含年份", subs and "2026" not in subs[0],
          subs)
    check("关年份后副标题仍有评分与画质", subs and "9.1" in subs[0] and "1080P" in subs[0],
          subs)
    s.content_cards.update({"show_year": True})
    c4 = PosterCard(media, lambda m: None, "演员甲", "导演乙")
    subs4 = [l.text() for l in c4.findChildren(QLabel) if l.objectName() == "CardSub"]
    check("开年份后副标题含年份", subs4 and "2026" in subs4[0], subs4)

    # 设置页 UI：三个新开关
    dlg = SettingsDialog()
    groups = [g for g in dlg.findChildren(QGroupBox) if g.title() == "内容卡片"]
    check("设置页存在「内容卡片」分组", len(groups) == 1)
    g = groups[0] if groups else None
    labels = [l.text() for l in g.findChildren(QLabel)] if g else []
    check("内容卡片分组含 显示年份 / 显示演员 / 显示导演",
          all(t in labels for t in ("显示年份", "显示演员", "显示导演")), labels)
    toggles = g.findChildren(ToggleSwitch) if g else []
    check("内容卡片开关数量为 6（评分/年份/画质/演员/导演/预告片）", len(toggles) == 6,
          len(toggles))

    def toggle_by_label(group, text):
        for sw in group.findChildren(ToggleSwitch):
            row = sw.parent()
            if any(l.text() == text for l in row.findChildren(QLabel)):
                return sw
        return None

    s.content_cards["show_actors"] = True
    sw_actors = toggle_by_label(g, "显示演员")
    if sw_actors is not None:
        sw_actors.setChecked(False)
    check("点「显示演员」开关写入 settings.content_cards",
          s.content_cards.get("show_actors") is False, s.content_cards.get("show_actors"))
    s.content_cards["show_actors"] = True

    # ============================================ 3) 4) 窄按钮不再被 padding 压没
    qss = open(os.path.join(_HERE, "..", "src", "style.qss"), encoding="utf-8").read()
    check("style.qss 有 compact 选择器把 padding 压到 0",
          'QPushButton[compact="1"]' in qss and "padding: 0 4px" in qss)
    w = MainWindow()
    check("顶栏 ← 按钮带 compact", w.back_btn.property("compact") == "1"
          and w.back_btn.text() == "←")
    check("顶栏 → 按钮带 compact", w.fwd_btn.property("compact") == "1"
          and w.fwd_btn.text() == "→")
    nav_btns = [b for b in dlg.findChildren(QPushButton) if b.text() in ("↑", "↓")]
    check("设置页 ↑/↓ 按钮存在且都带 compact", len(nav_btns) >= 4
          and all(b.property("compact") == "1" for b in nav_btns), len(nav_btns))
    narrow = [b for b in dlg.findChildren(QPushButton) if b.maximumWidth() <= 52]
    bad = [(b.text(), b.width()) for b in narrow if b.property("compact") != "1"]
    check("设置页所有窄按钮（≤52px）都打了 compact", not bad, bad)
    # QSS 里若写了 min-width，会把 setFixedSize 的最小宽度盖掉 → 按钮缩回 sizeHint
    # （36px 的 ← 变 23px、30px 的 ↑ 变 17px），尺寸和设计值对不上。
    check("窄按钮保留设计宽度（↑/↓ 未被压到 17px）",
          all(b.width() >= 28 for b in nav_btns),
          sorted({b.width() for b in nav_btns}))
    check("顶栏 ←/→ 保留设计宽度 36",
          w.back_btn.width() == 36 and w.fwd_btn.width() == 36,
          (w.back_btn.width(), w.fwd_btn.width()))

    # ============================================ 5) ToggleSwitch 动画
    swt = ToggleSwitch(checked=True)
    check("动画对象被 self 持有（不再被 GC 回收）",
          swt._anim.parent() is swt, swt._anim.parent())
    swt.setChecked(False)
    for _ in range(60):
        app.processEvents()
        time.sleep(0.008)
    check("关→开动画能跑到终值 0.0（旧实现会冻结在中途）",
          abs(swt.get_pos() - 0.0) < 1e-6, swt.get_pos())
    swt.setChecked(True)
    for _ in range(60):
        app.processEvents()
        time.sleep(0.008)
    check("开→关动画能跑到终值 1.0", abs(swt.get_pos() - 1.0) < 1e-6, swt.get_pos())

    def snap(sw):
        """把开关渲染到「已填形状色」的位图上。

        不能直接用 sw.grab()：圆形轨道外的 4 个角没有 paintEvent 覆盖，
        QPixmap 里是**未初始化内存**（曾读出 255 的假红），断言会随机 FAIL。
        """
        pm = QPixmap(sw.size())
        pm.fill(QColor("#000000"))
        sw.render(pm)
        return pm.toImage()

    def redness(sw):
        img = snap(sw)
        best = -999
        for y in range(1, sw.height() - 1, 2):
            for x in range(1, sw.width() - 1, 2):
                c = img.pixelColor(x, y)
                best = max(best, c.red() - c.green())
        return best

    def knob_center_x(sw):
        """圆点（#f3d9a0）重心的 x —— 直接对应「圆点卡在中位」这个反馈。"""
        img = snap(sw)
        tot = 0.0
        sx = 0.0
        for y in range(0, sw.height(), 2):
            for x in range(0, sw.width()):
                c = img.pixelColor(x, y)
                if abs(c.red() - 243) < 24 and abs(c.green() - 217) < 24 and abs(c.blue() - 160) < 30:
                    sx += x
                    tot += 1
        return (sx / tot) if tot else -1.0

    off = ToggleSwitch(checked=False)
    on = ToggleSwitch(checked=True)
    mid = ToggleSwitch(checked=False)
    mid.set_pos(0.5)
    r_off, r_on, r_mid = redness(off), redness(on), redness(mid)
    check("轨道颜色随开关状态变化（开偏红）", r_on > r_off + 60, (r_on, r_off))
    check("轨道颜色随动画进度插值（中位介于两者之间）",
          r_off < r_mid < r_on, (r_off, r_mid, r_on))

    k_off, k_on, k_mid = knob_center_x(off), knob_center_x(on), knob_center_x(mid)
    check("圆点位置随进度移动（关在左 / 中位居中 / 开在右）",
          k_off >= 0 and k_off < k_mid < k_on
          and abs(k_mid - (off.width() - 1) / 2.0) < 5.0,
          (k_off, k_mid, k_on))

finally:
    try:
        app.quit()      # noqa: F821
    except Exception:
        pass

print("\n==== %s ====" % ("全部通过" if not errors else ("失败 %d 项: %s" % (len(errors), errors))))
sys.exit(1 if errors else 0)
