# -*- coding: utf-8 -*-
"""v1.39.1 预览出图（离屏）：画像概览「高频榜 / 分布」修复后的排版。

要证明的一件事（用户反馈 4）：长 CJK 条目名不再把整行撑爆 ——
计数与 █ 条形不再被折到下一行、不再与相邻条目重叠；名字超预算时收尾加「…」
并可在悬停 tooltip 看全名。

同时把 v1.39.0 的两张关键图（演员检测复选框列、工具窗导航转圈）一并重出，
让本版交付的证据是完整的一套。

出图注意（铁律）：`QWidget.grab()` 是**透明底图**，直接 `convert("RGB")` 会把半透明
层显示成纯白，图会骗人。必须先 `alpha_composite` 到容器底色再存。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_preview_1391_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtGui import QFontDatabase, QImage, QPainter, QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import applog

db.db_path = lambda: os.path.join(TMP, "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

from main_window import load_style

load_style(app)

from ui_settings import SettingsDialog

OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)

# 页面底色（与 style.qss 的窗口底色一致），grab 是透明底图，必须垫这个色
BG = QColor("#12100e")


def save(widget, name, bg=BG):
    """把控件截图垫到容器底色后存盘（否则半透明层会被显示成纯白）。"""
    img = widget.grab().toImage()
    out = QImage(img.size(), QImage.Format_RGB32)
    out.fill(bg)
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    path = os.path.join(OUT, name)
    out.save(path)
    print(f"[出图] {name} {img.width()}x{img.height()}")
    return path


# 用户截图里的真实数据形态 —— 长 CJK 名集中在系列 / 片商 / 导演三列
LISTS = {
    "tags": [("有码", 314), ("单纯作品", 308), ("中出", 222), ("巨乳", 183),
             ("连环裸", 145), ("DMM独家", 132), ("女教师", 100), ("教师", 92),
             ("西装", 76), ("乱伦", 74), ("有码", 72), ("多P", 59)],
    "actors": [("柳ゆか", 18), ("花沢ゆき", 16), ("あいり菜", 12), ("白峰きろ", 12),
               ("飛山莉緒", 6), ("星田一花", 6), ("深川い suba", 6)],
    "directors": [("肉Translator", 74), ("ムKelly坂川", 21), ("三輪な志郎", 21),
                  ("星藤", 18), ("イノ purchasers", 15), ("Takuo Ohtani", 15),
                  ("aranata園", 14)],
    "studios": [("S1 NO.1 STYLE", 101), ("肉手列", 84), ("AV Boise", 76),
                (" Merit", 75), ("ムatrix", 61), ("SEX丽人", 60),
                ("Attackers", 59), ("Mature", 53)],
    "series": [("SEX依存症の女", 48), ("00の湿ったパirst", 37),
               ("女教師NTR 不良生徒に最愛の雲を奪う", 26),
               ("人妻秘書、汗と接吻に満ちた社長室中出", 24),
               ("上司のゴADOYENに何度もイカされるemas", 21),
               ("女体社員と絶対上司が出張先の相部屋", 16),
               ("脅迫スイートルーム", 14),
               ("取引先の激使社長に中出しされ続けた女", 14)],
}
DIST = {
    "画质": [("1080P", 211), ("720P", 205), ("未标注", 134)],
    "评分": [("4~6", 123), ("6~7", 21), ("7~7.5", 14), ("7.5~8", 11),
             ("8~9", 46), ("9~10", 19), ("无评分", 299)],
    "时长": [("30~60 分", 6), ("60~90 分", 10), ("90~120 分", 70),
             ("120~180 分", 441), ("≥180 分", 23)],
    "年份": [("2012~2016", 27), ("2017~2021", 102), ("2022~2026", 421)],
    "入库月": [("2025-05", 7), ("2025-06", 20), ("2025-07", 49),
              ("2025-08", 14), ("2025-09", 24), ("2025-10", 10),
              ("2025-11", 14), ("2025-12", 4), ("2026-01", 12),
              ("2026-02", 14), ("2026-03", 7), ("2026-04", 9),
              ("2026-05", 12), ("2026-06", 7), ("2026-07", 9),
              ("2026-08", 18)],
}

dlg = SettingsDialog(None)
dlg.resize(1000, 900)
dlg.show()
dlg._show("画像概览")
for _ in range(6):
    app.processEvents()

for k, body in dlg.ins_lists.items():
    body.setText(dlg._bar_lines(LISTS[k], body, show_bar=True))
for k, body in dlg.ins_dist.items():
    body.setText(dlg._bar_lines(DIST[k], body))
for _ in range(6):
    app.processEvents()

# ---- ① 整页 ----
save(dlg._pg_insight, "v1391_insight_full.png")

# ---- ② 高频榜 5 列特写（反馈截图对应的区域）----
hi = None
for w in dlg.findChildren(type(dlg.ins_lists["tags"])):
    p = w.parentWidget()
    gp = p.parentWidget() if p else None
    if gp is not None and gp.isAncestorOf(dlg.ins_lists["series"]):
        if gp.isAncestorOf(dlg.ins_lists["tags"]):
            hi = gp
            break
if hi is None:
    hi = dlg.ins_lists["series"].parentWidget().parentWidget()
save(hi, "v1391_insight_highfreq.png")

# ---- ③ 分布 5 列特写 ----
di = dlg.ins_dist["入库月"].parentWidget().parentWidget()
save(di, "v1391_insight_dist.png")

# ---- ④ 「系列」列 3 倍放大：看清长名截断 + 计数右对齐 + 条形右对齐 ----
src = dlg.ins_lists["series"].grab().toImage()
sc = src.scaled(src.width() * 3, src.height() * 3,
                Qt.KeepAspectRatio, Qt.FastTransformation)
out = QImage(sc.size(), QImage.Format_RGB32)
out.fill(BG)
p = QPainter(out)
p.drawImage(0, 0, sc)
p.end()
out.save(os.path.join(OUT, "v1391_insight_series_zoom.png"))
print(f"[出图] v1391_insight_series_zoom.png {sc.width()}x{sc.height()}")

# ---- ⑤ 导航转圈（v1.39.0 需求 3）重出：把某个导航项的 ring 置为运行中 ----
try:
    from scan_ring import ScanRing
    rings = getattr(dlg, "nav_rings", {}) or {}
    if rings:
        k = "演员检测" if "演员检测" in rings else list(rings)[0]
        rings[k].set_state(True)
        for _ in range(4):
            app.processEvents()
        nav = dlg.findChildren(type(rings[k]))
        row = rings[k].parentWidget()
        save(row, "v1391_nav_ring_zoom.png")
        save(dlg, "v1391_tools_dialog.png")
        rings[k].set_state(False)
    else:
        print("[跳过] 没有 nav_rings")
except Exception as e:
    print("[跳过] 转圈出图失败：%s: %s" % (type(e).__name__, e))

print("PREVIEW_1391_DONE")
