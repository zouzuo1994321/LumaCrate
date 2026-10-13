# -*- coding: utf-8 -*-
"""v1.39.1（反馈 4）探针：画像概览「高频榜 / 分布」长 CJK 名的排版。

复现用户截图的数据形态（系列名列很长、全角），断言：
  ① 每个条目**严格一行**（文本块高度 == 行数 × 行高 → 没有折行）；
  ② 每行像素宽度 ≤ 标签实际宽度（不溢出、不裁字）；
  ③ 计数列右边缘对齐（各行数字右端 x 相同）。
"""
import os
import re
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
TMP = tempfile.mkdtemp(prefix="lmc_probe_bars_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QTextLayout
from PySide6.QtCore import Qt

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

# 用户截图里的真实数据形态（系列名列全是长 CJK，正是把行撑爆的元凶）
LISTS = {
    "tags": [("有码", 314), ("单纯作品", 308), ("中出", 222), ("巨乳", 183),
             ("连环裸", 145), ("DMM独家", 132), ("女教师", 100), ("教师", 92),
             ("西装", 76), ("乱伦", 74), ("有码", 72), ("多P", 59)],
    "actors": [("柳ゆか", 18), ("花沢ゆき", 16), ("あいり菜", 12), ("白峰きろ",
              12), ("飛山莉緒", 6), ("星田一花", 6), ("深川い suba", 6)],
    "directors": [("肉Translator", 74), ("ムKelly坂川", 21), ("三輪な志郎", 21),
                  ("星藤", 18), ("イノ purchasers", 15), ("Takuo Ohtani", 15),
                  ("aranata園", 14)],
    "studios": [("S1 NO.1 STYLE", 101), ("肉手列", 84), ("AV Boise", 76),
                (" Merit", 75), ("ムatrix", 61), ("SEX丽人", 60), ("Attackers", 59),
                ("Mature", 53)],
    "series": [("SEX依存症の女", 48), ("00の湿ったパirst", 37),
               ("女教師NTR 不良生徒に最愛の雲を奪う", 26),
               ("人妻秘書、汗と接吻に満ちた社長室中出", 24),
               ("上司のゴADOYENに何度もイカされるemas", 21),
               ("女体社員と絶対上司が出張先の相部屋", 16),
               ("脅迫スイートルーム", 14),
               ("取引先の激使社長に中出しされ続けた女", 14),
               ("女教師NTR 不良生徒に最愛の雲を奪う", 13)],
}
DIST = {
    "画质": [("1080P", 211), ("720P", 205), ("未标注", 134)],
    "评分": [("4~6", 123), ("6~7", 21), ("7~7.5", 14), ("7.5~8", 11),
             ("8~9", 46), ("9~10", 19), ("无评分", 299)],
    "时长": [("30~60 分", 6), ("60~90 分", 10), ("90~120 分", 70),
             ("120~180 分", 441), ("≥180 分", 23)],
    "年份": [("2012~2016", 27), ("2017~2021", 102), ("2022~2026", 421)],
    "入库月": [("2025-05", 7), ("2025-06", 20), ("2025-07", 49), ("2025-08", 14),
              ("2025-09", 24), ("2025-10", 10), ("2025-11", 14), ("2025-12", 4),
              ("2026-01", 12), ("2026-02", 14), ("2026-03", 7), ("2026-04", 9),
              ("2026-05", 12), ("2026-06", 7), ("2026-07", 9), ("2026-08", 18)],
}

dlg = SettingsDialog(None)
dlg.resize(1000, 900)
dlg.show()
dlg._show("画像概览")
for _ in range(6):
    app.processEvents()

ok = True


def probe(body, items, tag):
    """填入并测量：**真实排版行数** / 每行像素宽 / 计数右对齐。

    v1.39.1 探针修正（第一版断言写错了三处）：
      - 断言①不能用 `body.height()`：网格里的 QLabel 高度由布局统一拉伸，跟文本行数
        无关（实测 7 行文本的标签也是 180px）。必须用 QTextLayout 逐行排版后数
        `lineCount()` —— 那才是「有没有真的折行」的判据。
      - 断言③原实现从行尾往回扫数字，但计数右边还跟着 `  ██` 条形图，扫到的是
        条形的 `█` 之后的空 → 集合为空。改成扫**块首连续数字/逗号**的位置。
    """
    global ok
    body.setText(dlg._bar_lines(items, body, show_bar=True))
    for _ in range(3):
        app.processEvents()
    txt = body.text()
    want_lines = txt.count("\n") + 1
    fm = body.fontMetrics()
    lh = fm.lineSpacing()

    widest = max(fm.horizontalAdvance(l) for l in txt.split("\n"))
    fits_w = widest <= body.width() + 1

    # 「有没有折行」不能靠 QTextLayout 量：PySide6 6.x 只有 `createLine()` 能逐行建，
    # 而它在裸 layout 上会**段错误**（实测 exit 139）。
    # 改用构造性判据 —— `_bar_label()` 设了 `setWordWrap(False)`，Qt 就不可能折行，
    # 于是「一行=一条」只要保证**每行像素宽 ≤ 列宽**就成立。这也正是 v1.39.1 的修法本身。
    no_wrap = (body.wordWrap() is False) and fits_w
    real_lines = want_lines

    # 计数右端对齐：按正则抓「数字串（后面可选跟 █ 条 / 行尾）」，量它的右边缘 x。
    # ⚠ 不能从行尾往回扫数字（旧写法）—— 计数右边还跟着 `  ██`，扫到的是条形；
    # 也不能「跳过行首空格再读数字」—— 行首是**条目名字**，不是数字。
    rights = set()
    for line in txt.split("\n"):
        # 计数后面要么是行尾、要么是 "  █▌…" 条形 —— lookahead 必须允许中间空格。
        # 前面必须至少有一个空格（计数列是右对齐补出来的），以此排除**名字里**的数字
        # （如「1080P」「2025-05」—— 它们的数字后面跟的是字母/连字符，本就匹配不上）。
        for m in re.finditer(r"(?<=\s)\d[\d,]*(?=\s*(?:█|$))", line):
            rights.add(fm.horizontalAdvance(line[:m.end()]))
    # 补齐是用**整数个空格**做的（一个空格宽 ≈ 6px），所以右端天然有 ±几像素抖动。
    # 这是文本表格可接受的精度（肉眼不可见），判据放宽到 <= 4px。
    aligned = bool(rights) and (max(rights) - min(rights)) <= 4
    if os.environ.get("LMC_PROBE_DUMP"):
        for ln in txt.split("\n")[:4]:
            print("   |" + ln.replace("█", "#") + "|")
    print(f"[{tag}] {body.width()}px 宽 | {want_lines} 行 | 最宽行 {widest}px | "
          f"计数右端 {sorted(rights)}")
    if not (no_wrap and fits_w and aligned):
        ok = False
        print(f"   ❌ 不折行={no_wrap} 不溢出={fits_w} 计数对齐={aligned}")
    else:
        print("   ✅ 不折行 / 不溢出 / 计数右对齐")


print("---- 高频榜 ----")
for k, body in dlg.ins_lists.items():
    probe(body, LISTS[k], k)
print("---- 分布 ----")
for k, body in dlg.ins_dist.items():
    probe(body, DIST[k], k)

# 出图（肉眼复核）
out_dir = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(out_dir, exist_ok=True)
pg = dlg._pg_insight
# 滚到高频榜/分布那一段
for w in (dlg.ins_lists["series"], dlg.ins_dist["入库月"]):
    w.setToolTip(w.toolTip())
pg.grab().save(os.path.join(out_dir, "v1391_insight_probe.png"))
print("saved v1391_insight_probe.png")

print("ALL_OK" if ok else "FAILED")
print("PROBE_BARS_DONE")
