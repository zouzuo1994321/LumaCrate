# -*- coding: utf-8 -*-
"""v2.0.0：把 Python 里散落的旧「墨金」色值映射到 HeroUI 暗色中性色阶。

为什么不用运行时取色：这些颜色大量出现在**内联 setStyleSheet** 与自绘画笔里，
改成「运行时再查表」要动几百处调用签名，风险远大于收益。这里做一次性的
字面量迁移 —— 语义一一对应（主文字 / 次文字 / 弱文字 / 面板底 / 分割线 /
语义色），换完观感统一，且以后新代码直接写新色值即可。

映射原则：
  主文字   → #ecedee（HeroUI foreground）
  次文字   → #a1a1aa / #d4d4d8
  弱文字   → #71717a / #52525b
  深面板   → #18181b / #111113 / #0a0a0b
  更高一层 → #27272a / #3f3f46
  强调金   → #66a9ff（HeroUI primary 的浅色档，作固定强调文本）
  成功     → #45d483   警告 → #f5a524   危险 → #f87171
"""
import io
import os

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"

MAP = {
    # ---- 主文字 ----
    "#ece5d8": "#ecedee",
    "#f0e8da": "#fafafa",
    "#f2e8d6": "#fafafa",
    "#f6ecd8": "#fafafa",
    "#e8ddc8": "#ecedee",
    "#e8e0d4": "#ecedee",
    "#f7e3b4": "#fafafa",
    "#e7c86a": "#d4d4d8",
    # ---- 次文字 ----
    "#d9cfbf": "#d4d4d8",
    "#c9bda7": "#d4d4d8",
    "#c9bda9": "#d4d4d8",
    "#c9bdaa": "#d4d4d8",
    "#c9bda6": "#d4d4d8",
    "#d3cabb": "#d4d4d8",
    "#cfc4b0": "#d4d4d8",
    "#a2967f": "#a1a1aa",
    "#9b8e7a": "#a1a1aa",
    "#9b8a72": "#a1a1aa",
    "#9a8f7d": "#a1a1aa",
    "#8c8071": "#71717a",
    "#8b8071": "#71717a",
    "#8f8574": "#71717a",
    "#7b7160": "#71717a",
    "#6a6256": "#52525b",
    "#cbb17a": "#a1a1aa",
    # ---- 深底 ----
    "#0d0b0a": "#0a0a0b",
    "#0f0d0b": "#18181b",
    "#15110e": "#18181b",
    "#17130f": "#18181b",
    "#1b1613": "#18181b",
    "#1c1815": "#111113",
    "#2a221c": "#27272a",
    "#241f1b": "#27272a",
    "#2a241c": "#27272a",
    "#2a241f": "#27272a",
    "#362e23": "#3f3f46",
    "#3a3129": "#3f3f46",
    "#3a332c": "#3f3f46",
    # ---- 强调（固定金 → HeroUI primary 浅色）----
    "#d4af37": "#66a9ff",
    "#e8d27a": "#8fc0ff",
    "#5fb0ff": "#338ef7",
    "#1f6feb": "#006fee",
    # ---- 语义色 ----
    "#e8b76a": "#f5a524",
    "#d8a04a": "#f5a524",
    "#9ecf8a": "#45d483",
    "#7fdca0": "#45d483",
    "#8fd18f": "#45d483",
    "#6fae6f": "#45d483",
    "#6fbf73": "#45d483",
    "#7fc08a": "#45d483",
    "#16a085": "#17c964",
    "#e08a7a": "#f87171",
    "#e07a6a": "#f87171",
    "#eef3fb": "#fafafa",
}

# config.py 里的 ACCENT_COLORS 是**新**色值，不在 MAP 的键里，天然安全；
# 但 LEGACY_ACCENT_MAP 的键就是旧色值 —— 绝不能替换，否则迁移表会被改坏。
SKIP_FILES = {"config.py"}

total = 0
for fn in sorted(os.listdir(SRC)):
    if not fn.endswith(".py") or fn in SKIP_FILES:
        continue
    p = os.path.join(SRC, fn)
    s = io.open(p, encoding="utf-8").read()
    n, out = 0, s
    for old, new in MAP.items():
        # 大小写不敏感地替换（源码里既有 #ECE5D8 也有 #ece5d8）
        cnt = out.lower().count(old)
        if cnt:
            # 逐段替换，保留原来的大小写风格不追究（颜色值大小写无意义）
            import re
            out = re.sub(re.escape(old), new, out, flags=re.IGNORECASE)
            n += cnt
    if n:
        io.open(p, "w", encoding="utf-8").write(out)
        print("%-22s 替换 %d 处" % (fn, n))
        total += n
print("合计替换", total, "处")
