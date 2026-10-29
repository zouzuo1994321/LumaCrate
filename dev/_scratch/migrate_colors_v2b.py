# -*- coding: utf-8 -*-
"""v2.0.0 第二轮：清掉第一轮 MAP 没覆盖到的旧金色系 / 旧强调红。

这些色值只在个别位置出现，且语义各不相同（收藏标记 / 性别符号 / 开关滑块 /
徽标底 / 占位图渐变），所以不做全局字面量替换，而是**逐处带上下文**替换 ——
每一条的 old 串都包含足够长度，保证唯一命中。找不到就报出来，不静默跳过。
"""
import io
import os

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"

# (文件, 旧串, 新串, 说明)
JOBS = [
    # ---- main_window ----
    ("main_window.py", '"color:#c8b892;font-size:12px;"',
     '"color:#a1a1aa;font-size:12px;"', "计数标签 旧金→次文字"),
    ("main_window.py", '"background:#66a9ff;color:#14110f;font-size:10px;font-weight:bold;"',
     '"background:#66a9ff;color:#0a0a0b;font-size:10px;font-weight:bold;"', "角标 深字→中性黑"),
    ("main_window.py", 'p.fillRect(0, 0, w, h, QColor("#1d1813"))',
     'p.fillRect(0, 0, w, h, QColor("#18181b"))', "自绘底 旧墨→卡片底"),
    ("main_window.py", '"color:#e2685a;font-size:12px;font-weight:600;"',
     '"color:#f87171;font-size:12px;font-weight:600;"', "警示标题 → danger"),
    ("main_window.py", '"background:#a32a20;color:#ffffff;',
     '"background:#b91c1c;color:#ffffff;', "警示块底 → 深 danger"),
    ("main_window.py", '"font-size:15px;font-weight:700;color:#f3e8d6;"',
     '"font-size:15px;font-weight:700;color:#ecedee;"', "详情名 → 主文字"),
    ("main_window.py", '("♂", "#5aa9e6") if _g == "male"',
     '("♂", "#338ef7") if _g == "male"', "男性符号 → 天青"),
    ("main_window.py", '("♀", "#e6739f") if _g == "female"',
     '("♀", "#f31260") if _g == "female"', "女性符号 → 玫红"),
    ("main_window.py", '<span style="color:#e8d7ab;">',
     '<span style="color:#ecedee;">', "富文本加粗名 → 主文字"),
    ("main_window.py", '% ("#f3d9a0" if p.get("favorite") else "#a1a1aa"))',
     '% ("#f5a524" if p.get("favorite") else "#a1a1aa"))', "收藏星 → 琥珀"),
    ("main_window.py", '% ("#f3d9a0" if p.get("pinned") else "#a1a1aa"))',
     '% ("#f5a524" if p.get("pinned") else "#a1a1aa"))', "置顶钉 → 琥珀"),
    ("main_window.py", 'tb.setStyleSheet("background:#1c1714;color:#ecedee;',
     'tb.setStyleSheet("background:#18181b;color:#ecedee;', "悬浮条底 → 卡片底"),
    ("main_window.py", 'pen = QPen(QColor("#1c1714"))',
     'pen = QPen(QColor("#18181b"))', "自绘描边 → 卡片底"),
    ("main_window.py", 't.setStyleSheet("font-size:16px;font-weight:bold;color:#f3d9a0;")',
     't.setStyleSheet("font-size:16px;font-weight:bold;color:#ecedee;")', "区块标题 → 主文字"),
    # ---- ui_actorcheck ----
    ("ui_actorcheck.py", '"很高": "#9fd6b0"', '"很高": "#17c964"', "档位色 旧浅绿→翡翠"),
    # ---- ui_hero ----
    ("ui_hero.py", 'bg="#241d18"', 'bg="#27272a"', "占位图底 → 中性 800"),
    ("ui_hero.py", 'g.setColorAt(0.0, QColor("#2e241c"))',
     'g.setColorAt(0.0, QColor("#3f3f46"))', "占位图渐变上端 → 中性 700"),
    ("ui_hero.py", 'p.setPen(QColor("#8c6f2f"))',
     'p.setPen(QColor("#52525b"))', "占位图笔画 → 中性 600"),
    ("ui_hero.py", 'QDialog{background:#0f0d0c;}',
     'QDialog{background:#0a0a0b;}', "对话框底 → 页面底"),
    ("ui_hero.py", 'p.fillRect(r, QColor("#1c1714"))',
     'p.fillRect(r, QColor("#18181b"))', "自绘底 → 卡片底"),
    ("ui_hero.py", 'PersonSearchDialog{background:#1e1a16;border:1px solid #3a332b;',
     'PersonSearchDialog{background:#18181b;border:1px solid #3f3f46;', "检索框底/边框 → 中性"),
    ("ui_hero.py", '_t.setStyleSheet("color:#f3d9a0;font-weight:bold;")',
     '_t.setStyleSheet("color:#ecedee;font-weight:bold;")', "分组标题 → 主文字"),
    # ---- ui_imagedetect ----
    ("ui_imagedetect.py", '("#f0c674" if adv == "需人工核对" else "#45d483")',
     '("#f5a524" if adv == "需人工核对" else "#45d483")', "需核对 → 琥珀"),
    # ---- ui_settings ----
    ("ui_settings.py", 'p.setBrush(QColor("#f3d9a0"))',
     'p.setBrush(QColor("#fafafa"))', "开关滑块 旧米→纯白"),
    ("ui_settings.py", 'head.setStyleSheet("color:#e8d9b6;font-size:12px;")',
     'head.setStyleSheet("color:#d4d4d8;font-size:12px;")', "小标题 → 次文字亮"),
    ("ui_settings.py", 'self.ins_line.setStyleSheet("color:#e8d9b6;font-size:13px;")',
     'self.ins_line.setStyleSheet("color:#d4d4d8;font-size:13px;")', "提示行 → 次文字亮"),
    ("ui_settings.py", 'self.ins_cooc.setStyleSheet("color:#b9ad97;font-size:11px;")',
     'self.ins_cooc.setStyleSheet("color:#a1a1aa;font-size:11px;")', "共现提示 → 次文字"),
    ("ui_settings.py", 'lb.setStyleSheet("color:#b9ad97;font-size:12px;"',
     'lb.setStyleSheet("color:#a1a1aa;font-size:12px;"', "说明标签 → 次文字"),
    ("ui_settings.py", '<span style="color:#b9ad97">',
     '<span style="color:#a1a1aa">', "富文本弱字 → 次文字"),
    ("ui_settings.py", 'top.setForeground(0, QBrush(QColor("#f0c674")))',
     'top.setForeground(0, QBrush(QColor("#f5a524")))', "AI 建议列 → 琥珀"),
    ("ui_settings.py", '"#45d483" if (g.ai.get("advice") or "") == "全部保留" else "#f0c674"',
     '"#45d483" if (g.ai.get("advice") or "") == "全部保留" else "#f5a524"', "建议色 → 琥珀"),
    ("ui_settings.py", 'child.setForeground(1, QBrush(QColor("#e2685a")))',
     'child.setForeground(1, QBrush(QColor("#f87171")))', "冲突列 → danger"),
]

miss = []
for fn, old, new, why in JOBS:
    p = os.path.join(SRC, fn)
    s = io.open(p, encoding="utf-8").read()
    if old not in s:
        miss.append("%s  << %s  (%s)" % (fn, old[:60], why))
        continue
    s = s.replace(old, new, 1)
    io.open(p, "w", encoding="utf-8").write(s)
    print("OK   %-20s %s" % (fn, why))

# ---- 徽标配色整块重写（旧饱和底色 + 深字，在暗色下读不出来）----
p = os.path.join(SRC, "ui_hero.py")
s = io.open(p, encoding="utf-8").read()
old_blk = '''        color = {"4K": "#66a9ff", "HDR10": "#c0392b", "杜比视界": "#8e44ad",
                 "Atmos": "#2980b9", "DTS:X": "#17c964", "TrueHD": "#17c964"}'''
new_blk = '''        # v2.0.0：改 HeroUI 亮色 chip —— 底用中高亮度色 + 深字，暗色面板上才读得清
        color = {"4K": "#66a9ff", "HDR10": "#f5a524", "杜比视界": "#9353d3",
                 "Atmos": "#338ef7", "DTS:X": "#17c964", "TrueHD": "#17c964"}'''
if old_blk in s:
    s = s.replace(old_blk, new_blk, 1)
    print("OK   %-20s 徽标配色表" % "ui_hero.py")
else:
    miss.append("ui_hero.py  << 徽标 color 表未命中")
old_tx = 'f"background:{c};color:#14110f;font-weight:bold;font-size:11px;"\n                    "border-radius:3px;padding:2px 8px;")'
new_tx = 'f"background:{c};color:#0a0a0b;font-weight:bold;font-size:11px;"\n                    "border-radius:6px;padding:2px 8px;")'
if old_tx in s:
    s = s.replace(old_tx, new_tx, 1)
    print("OK   %-20s 徽标文字/圆角" % "ui_hero.py")
else:
    miss.append("ui_hero.py  << 徽标 setStyleSheet 未命中")
s = s.replace('c = color.get(b, "#7f8c8d")', 'c = color.get(b, "#71717a")', 1)
io.open(p, "w", encoding="utf-8").write(s)

print()
if miss:
    print("!! 未命中 %d 条：" % len(miss))
    for m in miss:
        print("   ", m)
else:
    print("全部命中，无遗漏。")
