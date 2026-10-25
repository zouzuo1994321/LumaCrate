# -*- coding: utf-8 -*-
"""把 app.log 里的「未捕获异常」按异常末行归类 + 时间分布（只读）。"""
import io
import os
import re
from collections import Counter

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
lp = os.path.join(ROOT, "index_data", "logs", "app.log")
lines = io.open(lp, encoding="utf-8", errors="replace").read().splitlines()

kinds = Counter()
first_seen, last_seen = {}, {}
days = Counter()
cur_ts = ""
for i, l in enumerate(lines):
    m = re.match(r"^(\d{4}-\d{2}-\d{2}) ", l)
    if m:
        cur_ts = m.group(1)
    if "未捕获异常" not in l:
        continue
    # 向后找第一条「XxxError: ...」作为归类键
    key = "(无堆栈)"
    for j in range(i + 1, min(i + 40, len(lines))):
        s = lines[j].strip()
        if not s:
            continue
        if re.match(r"^[A-Za-z_.]*(Error|Exception):", s) or s.startswith("RuntimeError"):
            key = s[:110]
            break
    kinds[key] += 1
    days[cur_ts] += 1
    first_seen.setdefault(key, cur_ts)
    last_seen[key] = cur_ts

print("== 未捕获异常归类 ==")
for k, n in kinds.most_common(12):
    print("  %5d × %s" % (n, k))
    print("         首次 %s / 最近 %s" % (first_seen.get(k), last_seen.get(k)))
print()
print("== 按天分布（最近 12 天）==")
for d, n in sorted(days.items())[-12:]:
    print("  %s  %d" % (d, n))
