# -*- coding: utf-8 -*-
"""v1.34.2 补丁：彻底消除「统计范围」组框下方留白（tip 被 QFormLayout 拉伸的真因）。"""
import io

p = "C:/lmc_build/src/ui_settings.py"
s = io.open(p, encoding="utf-8").read()
orig = s

# 1) 关闭 tip 换行（wordWrap=True 时 QLabel.sizeHint 按多行估算 → 被 QFormLayout 拉到 ~3 行高）
s = s.replace(
    "        self.lb_scope_tip.setWordWrap(True)\n",
    "        # v1.34.2（用户反馈 1）根因修复：wordWrap=True 时 QLabel 的 sizeHint 会按多行\n"
    "        # 估算高度，QFormLayout 把它拉伸到约 3 行高（实测 v1.34.1 tip 高 60px、v1.34.2 初版\n"
    "        # 仍 45px，而文本只有 1 行 ~17px）—— 这正是「统计范围组框下方留白太多」的真因。\n"
    "        # 关闭换行 + 定死 1 行高；三档文案已在 _refresh_est 压成单行，故不会裁字。\n"
    "        self.lb_scope_tip.setWordWrap(False)\n",
    1,
)

# 2) minimumHeight → fixedHeight（定死 1 行，QFormLayout 无法再拉伸它）
s = s.replace(
    "        self.lb_scope_tip.setMinimumHeight(\n"
    "            self.lb_scope_tip.fontMetrics().lineSpacing() + 2)\n",
    "        self.lb_scope_tip.setFixedHeight(\n"
    "            self.lb_scope_tip.fontMetrics().lineSpacing() + 3)\n",
    1,
)

# 3) 媒体库名过长时截断，保证 tip 恒为 1 行
s = s.replace(
    '        elif lib:\n'
    '            self.lb_scope_tip.setText(\n'
    '                f"只统计媒体库「{lib}」里的作品（适合这个库口味不一样时，权重不会串到其他库）。")\n',
    '        elif lib:\n'
    '            _ln = lib if len(lib) <= 12 else lib[:11] + "…"\n'
    '            self.lb_scope_tip.setText(\n'
    '                f"只统计媒体库「{_ln}」里的作品（适合这个库口味不一样时，权重不串库）。")\n',
    1,
)

assert s != orig, "no change applied!"
io.open(p, "w", encoding="utf-8").write(s)
print("patched:", p, "delta bytes", len(s) - len(orig))
print("wordWrap False count:", s.count("self.lb_scope_tip.setWordWrap(False)"))
print("fixedHeight count:", s.count("self.lb_scope_tip.setFixedHeight("))
print("_ln elide count:", s.count('_ln = lib if len(lib) <= 12'))
