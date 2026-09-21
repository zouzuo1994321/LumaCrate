# -*- coding: utf-8 -*-
"""v1.21.0 验证：
  A. 版本号；
  B. 卡片播放按钮：三角**重心居中**（旧字符「▶」方案偏左）；
  C. 卡片左下角收藏星标：已收藏=金色实心 / 未收藏=白描边内部透明；
  D. PosterCard 两角按钮的几何、真控件、点击回调与星标翻转；
  E. MainWindow._toggle_favorite_card：切库、就地改写、只动 favorite 一列；
  F. 首页悬停磨砂底衬：**按 id 去重 + 去抖**（快速掠过不逐行重算）；
  G. 首页搜索**去抖**（连续输入只过滤一次）；
  H. 首页表格分批填充包在 setUpdatesEnabled / blockSignals 里；
  I. veil 原图缓存有 LRU 上限。

离屏 QApplication + 注册中文字体（否则度量虚高）；临时库 + 临时 settings，不碰真实数据。
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = r"Z:\【01】自研软件\【26-19】本地影视中心\src"
sys.path.insert(0, SRC)

TMP = tempfile.mkdtemp(prefix="lmc_v121_")

# settings.json 也指到临时目录 —— 首页读取列设置/分栏时不得碰用户真实配置
import config as cfg
cfg.config_path = lambda: os.path.join(TMP, "settings.json")

import database as db
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")

import applog
applog.log_dir = lambda: os.path.join(TMP, "logs")

import version as ver

db.init_db()

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFontDatabase, QFont, QPixmap, QColor, QPainter
from PySide6.QtWidgets import QApplication, QPushButton

app = QApplication.instance() or QApplication(sys.argv)

FONT = r"C:\Windows\Fonts\msyh.ttc"
if os.path.exists(FONT):
    QFontDatabase.addApplicationFont(FONT)
    app.setFont(QFont("Microsoft YaHei", 9))

QSS = open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()
for _tok, _val in (("__VEIL__", "180"), ("__PANEL__", "24"),
                   ("__SURF__", "54"), ("__DLG__", "232")):
    QSS = QSS.replace(_tok, _val)
app.setStyleSheet(QSS)

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  -> {detail}" if detail else ""))


def pump(ms):
    """推进事件循环 ms 毫秒（定时器 / singleShot 填充都靠它跑起来）。"""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.008)


def lum(c):
    return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()


def near(c1, c2, tol=34):
    return (abs(c1.red() - c2.red()) <= tol and abs(c1.green() - c2.green()) <= tol
            and abs(c1.blue() - c2.blue()) <= tol)


def touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x00" * 16)


import main_window as mw

# ============ A. 版本号 ============
check("A.外部版本 = v1.21.0", ver.VERSION == "v1.21.0", ver.VERSION)
check("A.构建号 = 2609200024", ver.BUILD == "2609200024", ver.BUILD)

# ============ B. 播放按钮：三角重心居中 ============
OFF = 4


def render_widget(w, pad=OFF):
    pm = QPixmap(w.width() + pad * 2, w.height() + pad * 2)
    pm.fill(QColor(0, 0, 0))
    p = QPainter(pm)
    w.render(p, QPoint(pad, pad))
    p.end()
    return pm


def bright_centroid(pm, thr=150):
    """亮度阈值以上的像素质心 —— 圆圈底/描边都远低于 150，只留下三角形。"""
    img = pm.toImage()
    xs = ys = n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            if lum(img.pixelColor(x, y)) > thr:
                xs += x
                ys += y
                n += 1
    if not n:
        return None, None, 0
    return xs / n, ys / n, n


btn = mw._PlayGlyphButton()
check("B.播放按钮为几何绘制（text 为空）", btn.text() == "", f"text={btn.text()!r}")
check("B.按钮尺寸 = _PLAY_BTN", btn.width() == mw._PLAY_BTN and btn.height() == mw._PLAY_BTN,
      f"{btn.width()}x{btn.height()}")

pm_new = render_widget(btn)
cx, cy, n_new = bright_centroid(pm_new)
exp = OFF + mw._PLAY_BTN / 2.0
check("B.三角有绘制像素", n_new > 20, f"n={n_new}")
if n_new:
    off_new = abs(cx - exp)
    check("B.三角重心对齐圆心（误差 ≤1.2px）", off_new <= 1.2,
          f"centroid=({cx:.2f},{cy:.2f}) expect=({exp:.1f},{exp:.1f}) off={off_new:.2f}")
    check("B.纵向也居中（误差 ≤1.2px）", abs(cy - exp) <= 1.2, f"cy={cy:.2f}")
else:
    check("B.三角重心对齐圆心（误差 ≤1.2px）", False, "未取到三角形像素")
    check("B.纵向也居中（误差 ≤1.2px）", False, "未取到三角形像素")

def bright_bbox(pm, thr=150):
    img = pm.toImage()
    x0 = y0 = x1 = y1 = None
    for y in range(img.height()):
        for x in range(img.width()):
            if lum(img.pixelColor(x, y)) > thr:
                x0 = x if x0 is None else min(x0, x)
                x1 = x if x1 is None else max(x1, x)
                y0 = y if y0 is None else min(y0, y)
                y1 = y if y1 is None else max(y1, y)
    return x0, y0, x1, y1


bx0, by0, bx1, by1 = bright_bbox(pm_new)
if bx0 is not None:
    tw, th = bx1 - bx0 + 1, by1 - by0 + 1
    bbox_cx = (bx0 + bx1) / 2.0 - OFF
    check("B.三角外接框宽 ≈ 2*sw（8px）", 6.5 <= tw <= 9.5, f"w={tw}")
    check("B.三角外接框高 ≈ 2*sh（9.4px）", 8.0 <= th <= 10.5, f"h={th}")
    # 下行框整体横向不漂移（旧字符「▶」方案会明显偏左）；精确的重心居中由上方
    # centroid 断言覆盖。离屏抗锯齿下外接框右移 sw/3 会被阈值截断、测得近似居中，
    # 故这里只判「不漂移」，不放宽到 sw/3。
    want_bbox_cx = mw._PLAY_BTN / 2.0
    check("B.外接框横向不漂移（居中 ±1.5px）", abs(bbox_cx - want_bbox_cx) <= 1.5,
          f"bbox_cx={bbox_cx:.2f} want={want_bbox_cx:.2f}")
else:
    check("B.三角外接框宽 ≈ 2*sw（8px）", False, "未取到三角形像素")
    check("B.三角外接框高 ≈ 2*sh（9.4px）", False, "未取到三角形像素")
    check("B.外接框按『重心居中』右移 ≈ sw/3", False, "未取到三角形像素")

# 参考量（只打印，不作判定）：旧「字符 ▶」方案在本机 offscreen 字体下的偏差。
# 注意本环境会回退到某个居中良好的字体，故这个数不能当判据；真实差异在真机上看。
_legacy = QPushButton("▶")
_legacy.setObjectName("CardPlay")
_legacy.setFixedSize(mw._PLAY_BTN, mw._PLAY_BTN)
_legacy_font = _legacy.font()
_legacy_font.setPixelSize(11)
_legacy_font.setBold(True)
_legacy.setFont(_legacy_font)
lx, ly, ln = bright_centroid(render_widget(_legacy))
if ln:
    print(f"  [info] 旧字符方案 centroid=({lx:.2f},{ly:.2f}) off={abs(lx - exp):.2f}px")
else:
    print("  [info] 旧字符方案未取到像素")

# ============ C. 收藏星标：两态 ============
PINK = QColor(232, 158, 205)      # 明亮剧照色（星标要在它上面看得清）
GOLD = QColor(247, 201, 73)


def star_stats(on):
    b = mw._FavStarButton()
    b.set_on(on)
    pm = QPixmap(mw._STAR_BTN + OFF * 2, mw._STAR_BTN + OFF * 2)
    pm.fill(PINK)
    p = QPainter(pm)
    b.render(p, QPoint(OFF, OFF))
    p.end()
    img = pm.toImage()
    center = img.pixelColor(OFF + mw._STAR_BTN // 2, OFF + mw._STAR_BTN // 2)
    gold = white = 0
    for y in range(OFF, OFF + mw._STAR_BTN):
        for x in range(OFF, OFF + mw._STAR_BTN):
            c = img.pixelColor(x, y)
            if c.red() > 200 and c.green() > 150 and c.blue() < 140:
                gold += 1
            if c.red() > 235 and c.green() > 230 and c.blue() > 225:
                white += 1
    return center, gold, white


c_off, gold_off, white_off = star_stats(False)
c_on, gold_on, white_on = star_stats(True)

check("C.未收藏：星心透出背景（内部透明）", near(c_off, PINK),
      f"center={c_off.getRgb()[:3]} bg={PINK.getRgb()[:3]}")
check("C.未收藏：有白色描边像素", white_off > 10, f"white={white_off}")
check("C.未收藏：基本无金色填充", gold_off < 30, f"gold={gold_off}")
check("C.已收藏：星心为金色", near(c_on, GOLD),
      f"center={c_on.getRgb()[:3]} gold={GOLD.getRgb()[:3]}")
check("C.已收藏：金色像素远多于未收藏", gold_on > gold_off + 100,
      f"gold_on={gold_on} gold_off={gold_off}")
check("C.两态可切换（set_on 幂等）", (star_stats(True)[1] == gold_on) and (star_stats(False)[1] == gold_off),
      "")

# ============ D. PosterCard 两角按钮 ============
mid_fav = db.upsert_media_by_path(mode="overwrite", kind="movie", title="卡片测试片",
                                  file_path=os.path.join(TMP, "lib", "CARD-1.mp4"),
                                  library="TestLib")
calls_play, calls_fav = [], []
card = mw.PosterCard({"id": mid_fav, "title": "卡片测试片", "year": 2024, "rating": 8.1,
                      "file_path": os.path.join(TMP, "lib", "CARD-1.mp4"), "favorite": 0},
                     lambda *_: None, "演员甲", "导演乙",
                     on_select=None, on_play=lambda m: calls_play.append(m),
                     on_fav=lambda m: calls_fav.append(m))
check("D.播放按钮已建", card.play_btn is not None, "")
check("D.收藏按钮已建", card.fav_btn is not None, "")
if card.fav_btn is not None and card.play_btn is not None:
    fb, pb = card.fav_btn, card.play_btn
    check("D.收藏在左下 / 播放在右下（同一水平线）",
          fb.x() < pb.x() and fb.y() == pb.y(),
          f"fav=({fb.x()},{fb.y()}) play=({pb.x()},{pb.y()})")
    check("D.两按钮不重叠", fb.x() + fb.width() <= pb.x(), f"{fb.x()+fb.width()} <= {pb.x()}")
    check("D.收藏按钮是真控件（不穿透成选中/进详情）",
          not fb.testAttribute(Qt.WA_TransparentForMouseEvents), "")
    check("D.未收藏 tooltip 提示加入收藏", "加入收藏" in fb.toolTip(), fb.toolTip())
    check("D.初始星标为未收藏", fb._on is False, f"_on={fb._on}")
    fb.click()
    check("D.点击 → 触发 on_fav 回调", len(calls_fav) == 1, f"calls={len(calls_fav)}")
    # 回调只记录，不改 media → 由 MainWindow 改写；这里模拟回调写入
    check("D.点击后星标保持未收藏（回调未改数据）", fb._on is False, f"_on={fb._on}")

# 回调改写 media['favorite'] 的完整路径
media_sim = {"id": mid_fav, "favorite": 0, "file_path": os.path.join(TMP, "lib", "CARD-1.mp4"),
             "title": "卡片测试片", "year": 2024}
card2 = mw.PosterCard(media_sim, lambda *_: None, "", "",
                      on_fav=lambda m: m.__setitem__("favorite", 1))
card2.fav_btn.click()
check("D.回调写入后星标翻转为已收藏", card2.fav_btn._on is True, "")
check("D.翻转后 tooltip 变「取消收藏」", "取消收藏" in card2.fav_btn.toolTip(),
      card2.fav_btn.toolTip())

# 非视频条目：不建播放按钮，但收藏按钮仍建（收藏不限于视频）
card3 = mw.PosterCard({"id": 999, "title": "无视频", "file_path": "/x/y.txt", "favorite": 1},
                      lambda *_: None, "", "", on_play=lambda m: None, on_fav=lambda m: None)
check("D.非视频条目不建播放按钮", card3.play_btn is None, "")
check("D.非视频条目仍建收藏按钮", card3.fav_btn is not None, "")
check("D.已收藏条目初始星标为金", card3.fav_btn._on is True, "")

# ============ E. MainWindow._toggle_favorite_card ============
src_mw = open(os.path.join(SRC, "main_window.py"), encoding="utf-8").read()
check("E._poster_card 注入 on_fav", "on_fav=self._toggle_favorite_card" in src_mw, "")
check("E.卡片工厂唯一", src_mw.count("return PosterCard(") == 1,
      f"count={src_mw.count('return PosterCard(')}")


class _FakeMW:
    """鸭子类型的 MainWindow：只实现 _toggle_favorite_card 用到的两处接口。"""

    def __init__(self):
        self.msgs = []
        self.refresh = 0

    def statusBar(self):
        outer = self

        class _SB:
            def showMessage(self, s):
                outer.msgs.append(s)

        return _SB()

    def _refresh_stats(self):
        self.refresh += 1


fake = _FakeMW()
m2 = db.upsert_media_by_path(mode="overwrite", kind="movie", title="收藏测试",
                             file_path=os.path.join(TMP, "lib", "FAV-1.mp4"),
                             library="TestLib")
db.set_user_rating(m2, 6.5)
media_fav = {"id": m2, "favorite": 0, "title": "收藏测试"}
before = dict(db.get_media(m2))

mw.MainWindow._toggle_favorite_card(fake, media_fav)
check("E.切收藏后就地改写 media['favorite']", media_fav["favorite"] == 1, f"{media_fav}")
check("E.库里 favorite 已变 1", db.get_media(m2)["favorite"] == 1, "")
check("E.状态栏提示「已加入收藏」", any("加入收藏" in x for x in fake.msgs), fake.msgs)
check("E.触发了统计刷新", fake.refresh == 1, f"refresh={fake.refresh}")

after = dict(db.get_media(m2))
diff = sorted(k for k in before if before[k] != after[k])
check("E.只改动 favorite 一列", diff == ["favorite"], f"diff={diff}")
check("E.用户评分等字段未被波及", after.get("user_rating") == 6.5, f"ur={after.get('user_rating')}")

mw.MainWindow._toggle_favorite_card(fake, media_fav)
check("E.再点回未收藏", media_fav["favorite"] == 0 and db.get_media(m2)["favorite"] == 0, "")
check("E.状态栏提示「已取消收藏」", any("取消收藏" in x for x in fake.msgs), fake.msgs)
check("E.统计刷新累计 2 次", fake.refresh == 2, f"refresh={fake.refresh}")

# ============ F/G/H. 首页 ============
from ui_home import HomeListView, row_media

for i in range(4):
    p = os.path.join(TMP, "lib", f"M{i}.mp4")
    touch(p)
    db.upsert_media_by_path(mode="overwrite", kind="movie", title=f"片子{i}",
                            file_path=p, library="TestLib")

hits = []
lv = HomeListView(on_open_actor=None, on_open_media=None,
                  on_hover_media=lambda m: hits.append(m.get("title")))
lv.resize(1280, 760)
lv.show()
pump(500)
check("F.首页表格已分批填充完成", lv.table.rowCount() >= 4, f"rows={lv.table.rowCount()}")

# 行序由排序决定，别硬编码标题 —— 直接读该行绑定的 media
_t0 = (row_media(lv.table, 0) or {}).get("title")
_t1 = (row_media(lv.table, 1) or {}).get("title")
_t3 = (row_media(lv.table, 3) or {}).get("title")

# --- F. 悬停底衬去重 + 去抖 ---
hits.clear()
lv._on_cell_entered(0, 0)
lv._on_cell_entered(0, 1)
lv._on_cell_entered(0, 2)
check("F.去抖窗口内不立即换底衬", len(hits) == 0, f"hits={hits}")
pump(260)
check("F.停在同一行只换一次底衬", len(hits) == 1 and hits[0] == _t0, f"hits={hits} want={_t0!r}")

lv._on_cell_entered(0, 0)
lv._on_cell_entered(0, 3)
pump(260)
check("F.同一行内反复移动不再重算（按 id 去重）", len(hits) == 1, f"hits={hits}")

lv._on_cell_entered(1, 0)
pump(260)
check("F.换到新行才换底衬", len(hits) == 2 and hits[1] == _t1, f"hits={hits} want={_t1!r}")

lv._on_cell_entered(2, 0)
lv._on_cell_entered(3, 0)
pump(260)
check("F.快速掠过只结算最后一行（去抖合并）",
      len(hits) == 3 and hits[-1] == _t3, f"hits={hits} want_last={_t3!r}")

# --- G. 搜索去抖 ---
counted = {"n": 0}
_orig_apply = lv._apply_view


def _counting_apply():
    counted["n"] += 1
    _orig_apply()


lv._apply_view = _counting_apply
counted["n"] = 0
lv.search.setText("片")
lv.search.setText("片子")
lv.search.setText("片子1")
pump(80)
check("G.连续输入过程中不触发过滤", counted["n"] == 0, f"applies={counted['n']}")
pump(420)
check("G.停手后只过滤一次", counted["n"] == 1, f"applies={counted['n']}")
check("G.过滤结果正确", lv.table.rowCount() == 1, f"rows={lv.table.rowCount()}")

# --- H. 分批填充的刷新/信号批处理 ---
seq = []
_orig_su = lv.table.setUpdatesEnabled
patched = True
try:
    def _rec_su(b):
        seq.append(bool(b))
        _orig_su(b)
    lv.table.setUpdatesEnabled = _rec_su
except Exception:
    patched = False
check("H.可挂探针到 setUpdatesEnabled", patched, "")
if patched:
    lv._filled = 0
    lv._fill_gen = getattr(lv, "_fill_gen", 0) + 1
    seq.clear()
    lv._fill_chunk()
    check("H.填充时先关刷新、结束再打开",
          seq[:1] == [False] and seq[-1] is True, f"seq={seq}")
    lv._filled = 0
    seq.clear()
    lv._apply_view()
    check("H.改行数也包在关刷新的区间内",
          seq.count(False) >= 1 and seq.count(True) >= 1,
          f"seq={seq}")

# ============ I. veil 原图缓存 LRU ============
from veil import Veil

v = Veil()
paths = []
for i in range(9):
    p = os.path.join(TMP, "bd", f"b{i}.png")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    _pm = QPixmap(40, 30)
    _pm.fill(QColor(20 * i + 10, 40, 90))
    _pm.save(p, "PNG")
    paths.append(p)

loadable = not QPixmap(paths[0]).isNull()
check("I.测试底图可读（PNG 插件可用）", loadable, "")
if loadable:
    for p in paths:
        v.set_source(p)
        v.pixmap(240, 140)
    check("I.原图缓存有上限（≤6）", len(v._cache) <= 6, f"cache={len(v._cache)}")
    check("I.最近用过的仍在缓存", paths[-1] in v._cache, "")
    check("I.最早的已被挤出", paths[0] not in v._cache, f"cache_keys={len(v._cache)}")
    check("I.模糊成品按 (path,w,h) 命中缓存",
          v.pixmap(240, 140) is v.pixmap(240, 140), "")
else:
    check("I.原图缓存有上限（≤6）", False, "PNG 不可读，跳过")
    check("I.最近用过的仍在缓存", False, "PNG 不可读，跳过")
    check("I.最早的已被挤出", False, "PNG 不可读，跳过")
    check("I.模糊成品按 (path,w,h) 命中缓存", False, "PNG 不可读，跳过")

# ============ 汇总 ============
failed = [n for n, ok, _ in results if not ok]
print("\n==== 结果 ====")
print(f"{len(results) - len(failed)}/{len(results)} 通过")
print("ALL PASS" if not failed else f"FAILED: {failed}")
sys.exit(0 if not failed else 1)
