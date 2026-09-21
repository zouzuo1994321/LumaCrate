# -*- coding: utf-8 -*-
"""追加 v1.26.0 到今日工作日志（append-only）。"""
import io
import os
import sys

P = r"Z:/【01】自研软件/【26-19】本地影视中心/.workbuddy/memory/2026-09-21.md"
SECTION = """
---

## v1.26.0 / Build 2609210036 —— 4 条反馈 + 性能基准测试

**反馈 → 根因 → 修法**

1. **换了高亮色后所有「滑动按钮」颜色没跟着变**
   - 根因：设置页那个自绘开关 `ToggleSwitch` 的轨道色是**写死的** `_ON = (0xc0,0x39,0x2b)`，
     与 v1.25.0 那套「QSS 令牌 + `ACCENT_RGB`」链路**完全脱钩** → 12 色高亮只覆盖了 QSS 能表达的部分。
   - 修法：`paintEvent` 改成现取（`ToggleSwitch.accent_on()`，懒读 `sys.modules["main_window"].ACCENT_RGB`，
     **不能模块级 import main_window** —— 会与 `from ui_settings import …` 成环）+ 换色时 `_refresh_toggles()` 统一 `update()`
     （Qt 不会因为模块级变量变了就重绘，不刷新要等鼠标划过才变色）。圆点保持中性 `#f3d9a0`（iOS 式），朱红下逐像素零回退。
   - 开销：0.033ms/帧。
2. **底部加开源声明** → 状态栏文案接成 `版本 | Copyright | LICENSE_NOTE`（断言 C5 钉死先后顺序）。
3. **侧栏副标题 `LocalMediaCenter` 的 r 被裁** → 先量：侧栏 186 − 内边距 24 − logo 28 − 间距 8 = **文字列 122px**，
   而 `11px + letter-spacing 2px` 量出 **127px** → 超 5px。改成 `10px + 1.5px` → **113px / 余 9px**。
   并用像素扫描取证：文字右缘 x=152、标签右边界 x=163，**右边真空出 11px**。
4. **性能基准测试** → 根目录新增 `dev/benchmark.py` + `性能基线.md`（27 个用例，真实索引只读）。
   **第一轮就查出真缺陷**（见下）。

**性能基准测出来的真缺陷（本轮最大收获）**

- 现象：`EXPLAIN QUERY PLAN` 显示排序相关查询**全是** `SCAN m` + `USE TEMP B-TREE FOR ORDER BY`（全表扫 + 全表排序）。
- 根因：**索引与 ORDER BY 对不上** —— ① `search_media` 恒定输出 `ORDER BY <expr> <dir>, m.year DESC, m.id ASC`，
  SQLite 要满足全部项才用索引；② 旧 `idx_media_sort_title` 是单列 + BINARY，查询却是 `COLLATE NOCASE`。
- 修法：`_INDEXES` 补两条**逐列逐方向对齐**的复合索引 `idx_wall_title` / `idx_wall_time`。
- 实测：深翻页 **249.26 → 2.43ms（103×）**、最近添加 **151.54 → 0.66ms（231×）**、首屏 14.88 → 0.70ms、关键词 31.42 → 0.68ms。
  代价：库 121.0 → 128.9MB，`init_db()` 首次补索引 ~4s（一次性）。
- **已知边界（如实写进报告，不粉饰）**：`sort="random"` 是表达式排序，任何索引都排不了 → ~215ms，
  属「分页稳定 + 一点重洗」的设计取舍；报告里给了将来优化路径（物化 `shuffle` 列 + 索引）。
- 另一条结论：**必须放后台线程**的是 `insight.Portrait().build()`（~1.2s）与 `tagopt.library_tag_stats()`（~2.3s）。

**验证**

- `dev/smoke_v1260.py` **61 断言 / 0 失败**（A 版本号 / B 反馈1 含像素级 / C 反馈2 / D 反馈3 含像素级与正反两向量测 /
  E 索引 + 查询计划 / F 基准产物与只读约束 / G 12 色令牌回归）。
  其中 **B8** 就是反馈 1 的原始症状本身：朱红 `(192,57,43)` vs 天青 `(63,169,201)`，两色像素差异 **158**。
- 回归 `dev/smoke_v1250.py`：**只有 3 条失败，全是它自己的版本号断言**（v1.25.0 / 2609210035 / 大版本 25），属预期。
- 定向渲染 `dev/render_v1260.py` → `dev/screenshots_v1260/`：品牌区特写 3×、状态栏特写 2×、
  「导航菜单」开关区在朱红 / 天青下的特写各一张 + 上下并排对照图（红轨 vs 蓝轨，一眼可辨）。
- `lint_check`：23 文件 0 错误 / 0 CRLF。
- 打包 `本地影视中心-v1.26.0-2609210036.exe`（根目录 + history/ 双份，`Copying icon to EXE` 已出现）。

**新增交付物**

- 根目录 `性能基线.md`（环境 / 数据规模 / 27 项耗时表 / 结论 / 复现命令）
- 根目录 `命名建议.md`（发布推广用中英文名 + 雷区 + 配套文案）
- `dev/benchmark.py`（常设；以后每次动数据层都该跑一次）
- 技能 `local-media-center-release` 补第十七节（排序与索引逐列对齐）、第十八节（基准测试约定）

**顺带纠正一条过时的项目约定**

- 旧记忆写「当前模型不支持读图，只能靠文字推断」—— **本会话实测可以 Read 截图**。
  用户的剪贴板图在 `C:/Users/zouzu/.workbuddy/clipboard-images/clipboard-<日期>T<时分秒>-*.png`。
  本次 4 条反馈全靠读图才确认了「色板停在藕荷、开关却全是朱红」这个关键事实 → 已改写进 `MEMORY.md`。

**仍待用户确认（上一轮遗留，未重复追问）**

- `dev/` 里 26 个与 `history/` 同名的重复 exe（合计 1,179.0 MB）是否可删。
"""

with io.open(P, encoding="utf-8", newline="") as f:
    s = f.read()
if "## v1.26.0 / Build 2609210036" in s:
    print("[跳过] 今日日志已有 v1.26.0 段")
    sys.exit(0)
s = s.rstrip() + "\n" + SECTION
with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(s)
with io.open(P, encoding="utf-8", newline="") as f:
    back = f.read()
assert "## v1.26.0 / Build 2609210036" in back
with open(P, "rb") as f:
    raw = f.read()
print("[OK] 2026-09-21.md 已追加 v1.26.0；%d B，CRLF=%d" % (len(raw), raw.count(b"\r\n")))
