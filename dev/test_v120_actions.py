# -*- coding: utf-8 -*-
"""v1.20.0 验证：
  A. 详情页操作按钮「收藏 / 评分 / 刷新 / 更多」改用 #HeroAct —— 在明亮剧照上不再融入背景；
  B. 新增「刷新」按钮（排在「评分」之后）→ 只对本片重读 nfo 并刷新（保留收藏 / 评分 / 播放次数）。

离屏 QApplication + 注册中文字体（否则 sizeHint 虚高）；临时库，不碰真实索引。
"""
import os
import re
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = r"Z:\【01】自研软件\【26-19】本地影视中心\src"
sys.path.insert(0, SRC)

TMP = tempfile.mkdtemp(prefix="lmc_v120_")
DBP = os.path.join(TMP, "index_data", "media_center.db")

import database as db
db.db_path = lambda: DBP
db.init_db()

import applog
applog.log_dir = lambda: os.path.join(TMP, "logs")

from PySide6.QtGui import QFontDatabase, QFont, QPixmap, QColor, QPainter
from PySide6.QtWidgets import QApplication, QPushButton, QLabel
from PySide6.QtCore import QPoint

app = QApplication.instance() or QApplication(sys.argv)

FONT = r"C:\Windows\Fonts\msyh.ttc"
if os.path.exists(FONT):
    QFontDatabase.addApplicationFont(FONT)
    app.setFont(QFont("Microsoft YaHei", 9))

# 载入真实样式表（自行替换透明令牌，避免读真实 settings.json）
QSS_PATH = os.path.join(SRC, "style.qss")
QSS = open(QSS_PATH, encoding="utf-8").read()
for _tok, _val in (("__VEIL__", "180"), ("__PANEL__", "24"),
                   ("__SURF__", "54"), ("__DLG__", "232")):
    QSS = QSS.replace(_tok, _val)
app.setStyleSheet(QSS)

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  -> {detail}" if detail else ""))


import nfo_parser as nfo_mod
import scanner as scanner_mod
from ui_hero import HeroView


# ---------------- 造 nfo / 媒体 ----------------
def write_movie_nfo(path, title, year=2026, userrating=None):
    ur = f"<userrating>{userrating}</userrating>" if userrating is not None else ""
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<movie>'
                f"<title>{title}</title><year>{year}</year>{ur}"
                "<plot>剧情简介</plot><runtime>90</runtime><studio>StudioX</studio>"
                "<genre>剧情</genre><genre>爱情</genre>"
                "<country>Japan</country><mpaa>R-18</mpaa>"
                "<actor><name>演员甲</name><role>主演</role></actor>"
                "</movie>")


def write_episode_nfo(path, title, season=1, episode=2):
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<episodedetails>'
                f"<title>{title}</title><season>{season}</season><episode>{episode}</episode>"
                "<plot>分集简介</plot></episodedetails>")


def touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x00" * 16)


def mkdir(name):
    d = os.path.join(TMP, name)
    os.makedirs(d, exist_ok=True)
    return d


# ============ A. 样式：HeroAct 比 Ghost 明显得多 ============
m_hero = re.search(r"QPushButton#HeroAct\s*\{([^}]*)\}", QSS)
m_ghost = re.search(r"QPushButton#Ghost\s*\{([^}]*)\}", QSS)
check("A.QSS 定义了 #HeroAct", m_hero is not None, "")


def bg_alpha(block):
    m = re.search(r"background:\s*rgba\([^)]*?,\s*([0-9.]+)\s*\)", block)
    return float(m.group(1)) if m else None


a_hero = bg_alpha(m_hero.group(1)) if m_hero else None
a_ghost = bg_alpha(m_ghost.group(1)) if m_ghost else None
check("A.HeroAct 底色不透明度 > Ghost", a_hero is not None and a_ghost is not None and a_hero > a_ghost,
      f"hero_bg_alpha={a_hero} ghost_bg_alpha={a_ghost}")

# 像素对比：把按钮画在「明亮粉色剧照」上，测中心像素与底色的亮度差
def lum(c):
    return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()


def render_btn_on(dark_pink, objname, text="收藏"):
    btn = QPushButton(text)
    btn.setObjectName(objname)
    btn.setFixedSize(96, 34)
    btn.resize(96, 34)
    pm = QPixmap(200, 70)
    pm.fill(QColor(230, 158, 205))        # 亮粉色，模拟明亮剧照
    p = QPainter(pm)
    btn.render(p, QPoint(50, 18))
    p.end()
    img = pm.toImage()
    return lum(img.pixelColor(50 + 48, 18 + 17))   # 按钮中心


base = QColor(230, 158, 205)
g = render_btn_on(None, "Ghost")
h = render_btn_on(None, "HeroAct")
check("A.HeroAct 中心亮度明显低于 Ghost", h < g - 25, f"hero_lum={h:.1f} ghost_lum={g:.1f}")
check("A.HeroAct 与亮底形成足够反差", abs(lum(base) - h) >= 60,
      f"bg_lum={lum(base):.1f} hero_lum={h:.1f}")


# ============ B1. rescan_one：重读 nfo，保留用户态 ============
d1 = mkdir("t1_movie")
vid1 = os.path.join(d1, "ABC-001.mp4")
nfo1 = os.path.join(d1, "ABC-001.nfo")
touch(vid1)
write_movie_nfo(nfo1, "旧标题", 2019)
info = nfo_mod.parse_movie(nfo1)
COUNTS = {"movie": 0, "tvshow": 0, "episode": 0}
scanner_mod._index_movie(info, vid1, d1, d1, COUNTS, None, "TestLib", "overwrite")
mid1 = db.media_id_by_path(vid1)
db.set_user_rating(mid1, 7.5)
db.toggle_favorite(mid1)          # -> 1
for _ in range(3):
    db.mark_played(mid1)

r0 = db.get_media(mid1)
check("B1.初始：标题/年份写入", r0["title"] == "旧标题" and r0["year"] == 2019,
      f"title={r0['title']} year={r0['year']}")
check("B1.初始：用户态就位",
      r0["favorite"] == 1 and r0["user_rating"] == 7.5 and r0["play_count"] == 3,
      f"fav={r0['favorite']} ur={r0['user_rating']} pc={r0['play_count']}")

# 外部改写 nfo（不带 userrating）后刷新
write_movie_nfo(nfo1, "全新标题", 2024)
res = scanner_mod.rescan_one(mid1)
check("B1.刷新返回 ok", res.get("ok") is True, f"res={res}")
r1 = db.get_media(mid1)
check("B1.元数据已更新（标题/年份/时长/片商/类型/地区）",
      r1["title"] == "全新标题" and r1["year"] == 2024 and r1["runtime"] == "01:30:00"
      and r1["studio"] == "StudioX" and r1["genres"] == "剧情,爱情" and r1["country"] == "Japan",
      f"title={r1['title']} year={r1['year']} runtime={r1['runtime']} studio={r1['studio']}")
check("B1.收藏保留", r1["favorite"] == 1, f"fav={r1['favorite']}")
check("B1.播放次数保留", r1["play_count"] == 3, f"pc={r1['play_count']}")
check("B1.评分保留（nfo 未写 userrating 时不清空）", r1["user_rating"] == 7.5,
      f"ur={r1['user_rating']}")
check("B1.演员关联已重建", len(db.get_cast(mid1)) == 1, f"cast={len(db.get_cast(mid1))}")

# nfo 写了 userrating → nfo 优先
write_movie_nfo(nfo1, "全新标题", 2024, userrating=9.0)
scanner_mod.rescan_one(mid1)
r2 = db.get_media(mid1)
check("B1.nfo 有 userrating 时以 nfo 为准", r2["user_rating"] == 9.0, f"ur={r2['user_rating']}")


# ============ B2. 找不到 nfo → 明确报错，不静默成功 ============
d2 = mkdir("t2_nonfo")
vid2 = os.path.join(d2, "NO-NFO.mp4")
touch(vid2)
mid2 = db.upsert_media_by_path(mode="overwrite", kind="movie", title="无nfo",
                               file_path=vid2, nfo_path=None, library="TestLib")
res2 = scanner_mod.rescan_one(mid2)
check("B2.无 nfo 时返回 ok=False", res2.get("ok") is False, f"res={res2}")
check("B2.错误信息说明未找到 nfo", "未找到" in (res2.get("msg") or ""), f"msg={res2.get('msg')}")
r3 = db.get_media(mid2)
check("B2.失败时不改动数据", r3["title"] == "无nfo", f"title={r3['title']}")


# ============ B3. 分集：结构字段（parent_id/season/episode）不被刷新打散 ============
d3 = mkdir("t3_ep")
vid3 = os.path.join(d3, "S01E02.mp4")
nfo3 = os.path.join(d3, "S01E02.nfo")
touch(vid3)
write_episode_nfo(nfo3, "分集旧名", season=1, episode=2)
mid3 = db.upsert_media_by_path(mode="overwrite", kind="episode", title="分集旧名",
                               file_path=vid3, nfo_path=nfo3, library="TestLib",
                               parent_id=99, season=1, episode=2)
write_episode_nfo(nfo3, "分集新名", season=1, episode=2)
res3 = scanner_mod.rescan_one(mid3)
r4 = db.get_media(mid3)
check("B3.分集刷新 ok", res3.get("ok") is True, f"res={res3}")
check("B3.分集标题已更新", r4["title"] == "分集新名", f"title={r4['title']}")
check("B3.parent_id 未被清空", r4["parent_id"] == 99, f"parent_id={r4['parent_id']}")
check("B3.season/episode 未被打散", r4["season"] == 1 and r4["episode"] == 2,
      f"s={r4['season']} e={r4['episode']}")
check("B3.kind 仍为 episode", r4["kind"] == "episode", f"kind={r4['kind']}")


# ============ B4. CD 分片：靠「基名 nfo」也能定位到 nfo ============
d4 = mkdir("t4_cd")
vid4 = os.path.join(d4, "SAVR-1144-8K-cd1.mp4")
nfo4 = os.path.join(d4, "SAVR-1144-8K.nfo")
touch(vid4)
write_movie_nfo(nfo4, "选集基名标题", 2025)
mid4 = db.upsert_media_by_path(mode="overwrite", kind="movie", title="占位",
                               file_path=vid4, nfo_path=None, library="TestLib")
res4 = scanner_mod.rescan_one(mid4)
r5 = db.get_media(mid4)
check("B4.CD 分片靠基名 nfo 刷新成功", res4.get("ok") is True, f"res={res4}")
check("B4.标题来自基名 nfo", r5["title"] == "选集基名标题", f"title={r5['title']}")
check("B4.nfo_path 已回填基名 nfo", (r5.get("nfo_path") or "").endswith("SAVR-1144-8K.nfo"),
      f"nfo_path={r5.get('nfo_path')}")


# ============ C. 详情页按钮：5 个、顺序正确、全在标题上方 ============
row_ui = db.get_media(mid1)
hero = HeroView(row_ui, on_open_actor=None, on_back=None)
hero.resize(1500, 1000)
hero.show()
app.processEvents()

prim = [b for b in hero.findChildren(QPushButton) if b.objectName() == "Primary"]
acts = [b for b in hero.findChildren(QPushButton) if b.objectName() == "HeroAct"]
check("C.播放按钮唯一且为 Primary", len(prim) == 1 and prim[0].text() == "播放",
      f"prim={[b.text() for b in prim]}")
check("C.#HeroAct 按钮共 4 个", len(acts) == 4, f"acts={[b.text() for b in acts]}")

texts = [b.text() for b in acts]
check("C.包含 收藏 / 评分 / 刷新 / 更多",
      any(t.startswith("收藏") or t.startswith("已收藏") for t in texts)
      and any(t.startswith("评分") for t in texts)
      and "刷新" in texts and "更多" in texts, f"texts={texts}")

btn_by_text = {}
for b in prim + acts:
    btn_by_text[b.text()] = b
title_lbl = None
for l in hero.findChildren(QLabel):
    if (l.text() or "").startswith(row_ui["title"]):
        title_lbl = l
        break
check("C.找到标题标签", title_lbl is not None, f"title={row_ui['title']!r}")
if title_lbl is not None:
    y_title = title_lbl.mapTo(hero.widget(), QPoint(0, 0)).y()
    ok_above = True
    for b in prim + acts:
        y = b.mapTo(hero.widget(), QPoint(0, 0)).y()
        if y >= y_title:
            ok_above = False
    check("C.5 个按钮全部在标题上方", ok_above, f"y_title={y_title}")

# 顺序：播放 → 收藏 → 评分 → 刷新 → 更多（宽面板下同一行，按 x 排序）
order = sorted(prim + acts, key=lambda b: b.mapTo(hero.widget(), QPoint(0, 0)).x())
seq = [b.text() for b in order]
expect_head = ["播放"]
check("C.按钮顺序 播放→收藏→评分→刷新→更多",
      seq[0] == "播放" and (seq[1].startswith("收藏") or seq[1].startswith("已收藏"))
      and seq[2].startswith("评分") and seq[3] == "刷新" and seq[4] == "更多",
      f"order={seq}")

refresh_btn = btn_by_text.get("刷新")
check("C.刷新按钮有说明性 tooltip", bool(refresh_btn and refresh_btn.toolTip()),
      f"tip={refresh_btn.toolTip() if refresh_btn else None}")

# ============ D. 点「刷新」→ 元数据即时刷新，页面重建 ============
write_movie_nfo(nfo1, "点刷新后的标题", 2030)
old_media = hero.media["title"]
refresh_btn.click()
app.processEvents()
check("D.点击刷新后 HeroView.media 已更新",
      hero.media.get("title") == "点刷新后的标题",
      f"before={old_media!r} after={hero.media.get('title')!r}")
lbl_now = [l.text() for l in hero.findChildren(QLabel)
           if l.text() and l.text().startswith("点刷新后的标题")]
check("D.页面标题标签已重建", len(lbl_now) >= 1, f"labels={lbl_now[:2]}")
check("D.刷新后评分仍在（用户态不丢）", hero.media.get("user_rating") == 9.0,
      f"ur={hero.media.get('user_rating')}")


failed = [n for n, ok, _ in results if not ok]
print("\n==== 结果 ====")
print(f"{len(results) - len(failed)}/{len(results)} 通过")
print("ALL PASS" if not failed else f"FAILED: {failed}")
sys.exit(0 if not failed else 1)
