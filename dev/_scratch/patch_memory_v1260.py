# -*- coding: utf-8 -*-
"""更新项目长期记忆 MEMORY.md：修正「不支持读图」+ 补排序索引规则。"""
import io
import os
import sys

P = r"Z:/【01】自研软件/【26-19】本地影视中心/.workbuddy/memory/MEMORY.md"
with io.open(P, encoding="utf-8", newline="") as f:
    s = f.read()

pairs = [
    # 1) 纠正「不支持读图」这条已经过时的约定（本会话实测可读）
    ("- 常贴截图反馈，但当前模型不支持读图 → 据文字 + 文件名推断意图，用数据探针/断言自证，不要假装「看过图」。",
     "- 常贴截图反馈。**截图可以直接 Read（本会话实测可读）** —— 用户贴的剪贴板图片在 "
     "`C:/Users/zouzu/.workbuddy/clipboard-images/clipboard-<日期>T<时分秒>-*.png`（按时间戳排序即得顺序）。\n"
     "  → **先把图读出来再动手**（v1.26.0 的 4 条反馈全靠读图才确认了「色板停在藕荷、开关却是朱红」这个关键事实），\n"
     "  然后用数据探针/断言自证结论，两者一起作为证据。"),

    # 2) 排序与索引逐列对齐（v1.26.0 基准测试的结论）
    ("- 5W+ 片靠 **SQL 下推 + 增量渲染**（不是加内存）：",
     "- **排序必须与索引逐列对齐**（v1.26.0 基准测试查出来的真缺陷）：`search_media` 恒定输出 "
     "`ORDER BY <expr> <dir>, m.year DESC, m.id ASC`，SQLite 要满足**全部** ORDER BY 项才用索引 —— "
     "所以单列索引、或 collation 不一致的索引（查询是 `COLLATE NOCASE`、索引是 BINARY）**全都用不上**，"
     "结果是每翻一页都 `SCAN m` + `USE TEMP B-TREE FOR ORDER BY`。修法是在 `_INDEXES` 里补**逐列、逐方向**对齐的复合索引："
     "`ON media(sort_title COLLATE NOCASE, year DESC, id ASC)` / `ON media(added_time DESC, year DESC, id ASC)`"
     "（实测深翻页 249ms→2.4ms、最近添加 152ms→0.7ms）。**以后改 ORDER BY 的 tie-breaker 必须同步改索引**，"
     "否则功能照常、性能静默退化。表达式排序（随机排序）无解，属设计取舍。\n"
     "- 5W+ 片靠 **SQL 下推 + 增量渲染**（不是加内存）："),
]
bad = []
for old, new in pairs:
    if s.count(old) != 1:
        bad.append(old[:40])
        continue
    s = s.replace(old, new, 1)
if bad:
    print("[FAIL] 锚点未命中：", bad)
    sys.exit(1)

with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(s)
with io.open(P, encoding="utf-8", newline="") as f:
    back = f.read()
for need in ("截图可以直接 Read", "排序必须与索引逐列对齐"):
    if need not in back:
        print("[FAIL] 回读缺", need)
        sys.exit(1)
with open(P, "rb") as f:
    raw = f.read()
print("[OK] MEMORY.md 已更新；%d B，CRLF=%d" % (len(raw), raw.count(b"\r\n")))
