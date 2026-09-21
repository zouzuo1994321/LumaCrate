# -*- coding: utf-8 -*-
"""给 local-media-center-release 技能补第十七节：影片墙排序必须与索引逐列对齐。

顺带把「性能基准测试」的产物与跑法写进去（这是本项目新增的常设动作）。
"""
import io
import os
import sys

P = os.path.join(os.path.expanduser("~"), ".workbuddy", "skills",
                 "local-media-center-release", "SKILL.md")
with io.open(P, encoding="utf-8", newline="") as f:
    s = f.read()

if "## 十七、影片墙的排序必须与索引「逐列对齐」" in s:
    print("[跳过] 第十七节已存在")
    sys.exit(0)

SEC = """
## 十七、影片墙的排序必须与索引「逐列对齐」（v1.26.0 基准测试查出来的）

### 17.1 症状：不报错、单页也不慢，只有「深翻页」才露馅

`dev/benchmark.py` 第一轮跑出来三条超阈值：深层翻页 **249ms**、随机排序 211ms、最近添加 152ms。
`EXPLAIN QUERY PLAN` 一看就明白 —— 排序相关的查询**全是**：

```
SCAN m
USE TEMP B-TREE FOR ORDER BY
```

即 **全表扫描 + 全表排序**，每翻一页都重来一遍。

### 17.2 根因：索引跟 ORDER BY 对不上，不是 SQL 写得差

1. `search_media` 的排序键**永远带附加项** —— `ORDER BY {expr} {direction}, m.year DESC, m.id ASC`。
   SQLite 要满足**全部** ORDER BY 项才会用索引，多出来的两个 tie-breaker 直接把索引废掉。
2. 已有的 `idx_media_sort_title` 是**单列 + BINARY collation**，而查询写的是
   `m.sort_title COLLATE NOCASE` —— collation 不一致同样用不上。
3. 只把附加项去掉也不够（实测：去掉后仍 `USE TEMP B-TREE`，因为 `COLLATE NOCASE` 仍对不上）。
4. 只有**单键**排序（`ORDER BY m.added_time DESC`）才走 `COVERING INDEX idx_media_added_time`。

### 17.3 修法：按 ORDER BY 逐列、逐方向建复合索引

```python
"CREATE INDEX IF NOT EXISTS idx_wall_title ON media(sort_title COLLATE NOCASE, year DESC, id ASC)",
"CREATE INDEX IF NOT EXISTS idx_wall_time  ON media(added_time DESC, year DESC, id ASC)",
```

SQLite **支持**索引列上的 `DESC`，也**支持**把 `COLLATE` 写进索引定义 —— 两样都必须写全，
少一样就退回全表排序。实测（4.8 万条）：

| 用例 | 修复前 | 修复后 | 提速 |
|---|---:|---:|---:|
| 深层翻页 60 条（offset 47963） | 249.26 ms | 2.43 ms | 103× |
| 最近添加 60 条（倒序） | 151.54 ms | 0.66 ms | 231× |
| 首屏分页 60 条 | 14.88 ms | 0.70 ms | 21× |
| 关键词列表 60 条 | 31.42 ms | 0.68 ms | 46× |

- 代价：数据库 **121.0 → 128.9 MB**（+7.9MB）；`init_db()` 首次补索引 **约 4s**（只一次）。
- **新库/老库都会自动补**（`CREATE INDEX IF NOT EXISTS` 在 `_INDEXES` 里），无需手写迁移。
- **改了 `search_media` 的 ORDER BY 就必须同步改这两条索引** —— 它们是逐列绑定的，
  加一个 tie-breaker 就会让索引静默失效（而功能完全正常，只有性能悄悄退化）。

### 17.4 无法索引的一类：表达式排序（随机排序）

`sort="random"` 用 `((m.id * 2654435761 + SEED) % 2147483647)` 做会话种子置换。
**表达式排序永远无索引可用**，每页 ~215ms 且 offset 越深越慢（浅 offset 靠 top-N 排序器侥幸快）。
这是「分页稳定、不重不漏、点一下重新洗牌」的**设计取舍**，写进《性能基线》即可，不要试图加索引。
真要优化只有一条路：物化一列 `shuffle` + 索引，`reshuffle()` 时整表 UPDATE（≈ 一次全表扫的代价）。

### 17.5 顺带记住两条实测口径

- **全表聚合**（`count_media(keyword)` / `library_counts()` / `stats()` / `count_people()`）
  是 **15~50ms** 量级，属于「进页面算一次 + 缓存」，**不要挂到输入框每次改动上**。
- **卡片渲染才是卡片墙的真瓶颈**：`PosterCard` 每张 ≈ 0.8ms（热缓存）/ ≈ 6.5ms（冷封面解码），
  一屏 60 张 = 50ms / 390ms。所以「增量渲染」不是优化选项而是必需项。

## 十八、性能基准测试（`dev/benchmark.py`，每版或每次动数据层后跑一次）

- **它在真实索引上跑**（4.8 万条那个），因此必须**严格只读**：
  · 不调 `init_db()`（会写 WAL）；冷启动那一条用「`db.close_conn()` 后重跑一次查询」等价测建连代价；
  · 不碰任何 `insert_* / update_* / delete_* / clear_media()`；
  · 必须 `applog.log_dir = lambda: <TEMP>/...`，否则会往真实 `index_data/logs/app.log` 里写；
  · **不要** patch `db.db_path`（那正是被测对象）。
- 产出**项目根目录 `性能基线.md`**：环境 / 数据规模 / 逐项（中位·最小·最大·n·阈值·判定）/ 结论 / 复现命令。
- Qt 部分用 `QT_QPA_PLATFORM=offscreen` + `LMC_NO_BACKDROP=1`；建 `PosterCard` 要 `deleteLater()` 回收。
- **报告里的「修复前」数字要硬编码在脚本的 `OPT_BEFORE_AFTER` 里**、「修复后」从本次 `RESULTS` 里现取 ——
  这样文档永远不会出现「写的 XX ms 跟实际跑出来的对不上」。
- 写 f-string / `%` 格式化时注意正文里的 `%`：`"… % 2147483647)"` 会被当成格式符，写成 `%%`。
"""

s = s.rstrip() + "\n" + SEC
with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(s)
with io.open(P, encoding="utf-8", newline="") as f:
    back = f.read()
for need in ("## 十七、影片墙的排序必须与索引", "## 十八、性能基准测试", "idx_wall_title"):
    if need not in back:
        print("[FAIL] 回读缺", need)
        sys.exit(1)
with open(P, "rb") as f:
    raw = f.read()
print("[OK] SKILL.md 已补第十七 / 十八节；大小 %d B，CRLF=%d" % (len(raw), raw.count(b"\r\n")))
