# -*- coding: utf-8 -*-
"""v1.26.0：README 迭代记录 + 目录结构补《性能基线》。"""
import io
import os
import sys

P = r"Z:/【01】自研软件/【26-19】本地影视中心/README.md"
with io.open(P, encoding="utf-8", newline="") as f:
    s = f.read()

SEC = """### v1.26.0 (Build 2609210036) — 2026-09-21
> 主题：**4 条反馈 —— 滑动开关跟随高亮色 / 底部开源声明 / 侧栏副标题防裁字 / 性能基准测试**。
> 「性能基准测试」这一条在跑第一轮时就**当场查出一条真实缺陷**：影片墙的每一条查询都是「全表扫描 + 全表排序」，
> 补两条索引后深层翻页 **249ms → 2.4ms**（详见根目录《性能基线》与下文）。

- **反馈 1 · 换了高亮色之后，所有「滑动按钮」的颜色没跟着变**：
  - **根因**：设置页那个自绘开关 `ToggleSwitch` 的轨道色是**写死的** —— `_ON = (0xc0, 0x39, 0x2b)`（朱红），
    与 `render_style()` 那条「QSS 令牌 + 模块级 `ACCENT_RGB`」的链路**完全没有关系**。
    所以 v1.25.0 的 12 色高亮只覆盖了 QSS 能表达的东西（卡片描边 / 按钮 / chip / 滑块 / 进度条 / 勾选框），
    **自绘控件里漏了开关的轨道**。用截图取证：色板高亮停在「藕荷」，而设置页里 20 多个开关全是朱红。
  - **修法**：`paintEvent` 改成**每次绘制时现取**高亮色（`ToggleSwitch.accent_on()`），与 QSS 同源、不会串色。
    `_ON` 保留为兜底值（`ACCENT_DEFAULT`）。
  - **不能模块级 `import main_window`**：`main_window` 顶部就有 `from ui_settings import SettingsDialog, …`，
    反向 import 会成环（导入期类还没定义 → 窗口直接建不起来）。所以走 `sys.modules.get("main_window")`
    取「已加载完的那个模块对象」，拿不到时回落到 `settings.json` 里的 accent。
  - **还差一步「刷新」**：Qt 不会因为某个模块级变量变了就自动重绘，不显式 `update()` 的话要等鼠标划过才变色
    —— 用户会以为「这个开关还是没跟着变」。新增 `SettingsDialog._refresh_toggles()`，在换色时统一 `update()`。
  - **圆点保持中性色 `#f3d9a0` 不变**（iOS 式设计：轨道跟随主题色、圆点是中性色），默认朱红下的观感逐像素零回退。
  - 代价实测：**0.033 ms / 帧**（现取不缓存也毫无负担），已写成断言 `B17`。
- **反馈 2 · 底部加上开源声明**：状态栏原来只有 `版本 | Copyright`，现在接成
  `v1.26.0 (Build 2609210036)  |  Copyright  2026 肆月Aperture  |  本软件为开源软件，没有授权禁止用于商业用途。`
  —— 位置严格按反馈原话「添加在…后面」（有一条断言 `C5` 专门比较两者的先后下标，防止以后被人挪到前面去）。
- **反馈 3 · 侧栏标题 `LocalMediaCenter` 的 r 显示不全**：
  - **先量再改**（不靠眼估）：侧栏固定 `186px`，减两侧内边距 24px、减 logo 28px 与间距 8px 后，
    **文字列只有 122px**；而 `11px + letter-spacing 2px` 下的 `LocalMediaCenter` 量出来 **127px** ——
    正好超出 5px，于是末尾的 r 被裁掉。超出的量恰好是「16 个字符 × 0.5px 字距 = 8px」再加基础字宽。
  - **修法**：字号降到 **10px**（反馈原话「改小一档」），并把字距从 2px 收到 1.5px 留出余量 →
    实测 **113px / 可用 122px，余 9px**。
  - **取证不止于算数**：把品牌区真的渲染出来逐像素扫文字右边缘 —— 文字右缘 `x=152`、标签右边界 `x=163`，
    **右边实打实空出 11px**，不是「算了觉得够」。
- **反馈 4 · 性能基准测试（根目录新增 `dev/benchmark.py` + `性能基线.md`）**：
  - 在**真实索引**上跑（4.8 万部 / 121MB / 7127 位演员 / 92590 条关联），**全程只读** ——
    不调 `init_db()`、不碰任何 `insert/update/delete`，日志也重定向到 `%TEMP%`；覆盖 27 个用例，
    分「数据层」与「Qt 层」两张表：分页 / 深翻页 / 随机排序 / 多维筛选 / 关键词 / 批量关系查询 /
    详情页回查 / 全库画像 / 标签统计 / nfo 解析 / 样式表重载 / 建 60 张卡（冷热封面缓存）。
  - **第一轮就查出一条真缺陷**：`EXPLAIN QUERY PLAN` 显示排序相关的查询**全是**
    `SCAN m` + `USE TEMP B-TREE FOR ORDER BY`（全表扫 + 全表排序）。根因不是 SQL 写得差，而是**索引与 ORDER BY 对不上**：
    ① `search_media` 的排序键永远带附加项 —— `ORDER BY <字段> <方向>, m.year DESC, m.id ASC`；
    ② 已有的 `idx_media_sort_title` 是**单列 + BINARY collation**，而查询写的是 `m.sort_title COLLATE NOCASE`。
    于是任何一条影片墙查询都无法命中索引。
  - **修法**：补两条与 ORDER BY **逐列对齐**的复合索引 `idx_wall_title` / `idx_wall_time`。实测：

    | 用例 | 修复前 | 修复后 | 提速 |
    |---|---:|---:|---:|
    | 深层翻页 60 条（名称升序，offset 47963） | 249.26 ms | 2.43 ms | **103×** |
    | 最近添加 60 条（按时间倒序） | 151.54 ms | 0.66 ms | **231×** |
    | 首屏分页 60 条 | 14.88 ms | 0.70 ms | **21×** |
    | 关键词列表 60 条 | 31.42 ms | 0.68 ms | **46×** |

    代价：数据库体积 121.0 → 128.9 MB（+7.9MB），`init_db()` 首次补索引约 4s（仅一次，之后启动无感）。
  - **如实记录一条已知边界（不粉饰）**：`sort="random"`（随机排序）走会话种子置换
    `((id * 2654435761 + SEED) % 2147483647)`，是个**表达式**，任何索引都排不了它 →
    每页 ~215ms，且 offset 越深越慢。这是「分页稳定、不重不漏、点一下重新洗牌」的**设计取舍**，
    《性能基线》里写明了将来要优化时的最低成本路径（物化一列 `shuffle` + 索引）。
  - 《性能基线》里同时给出**环境 / 数据规模 / 逐项耗时（中位·最小·最大·次数·阈值·判定）/ 结论 / 复现命令**，
    并在结论里点名「**必须放后台线程**」的两项：`insight.Portrait().build()`（~1.2s）与
    `tagopt.library_tag_stats()`（~2.3s）—— 它们是全库全表扫描，落在 GUI 线程里就是一次肉眼可见的卡死。
- **验证**：
  - 新增 `dev/smoke_v1260.py`，**61 条断言全过 / 0 失败**：版本号；`accent_on()` 在 12 色下逐一等于该色 RGB；
    **像素级**证明开关轨道真的跟着换（朱红 `(192,57,43)` / 天青 `(63,169,201)`，两色差异 158，
    而圆点仍是 `(243,217,160)`、关态轨道仍是 `(74,64,56)`）—— 这一条就是反馈 1 的原始症状本身；
    设置页 26 个开关能被 `_refresh_toggles()` 覆盖；状态栏三段的**先后顺序**；
    `#Sub` 的 10px/1.5px 与「旧组合 127px > 122px、新组合 113px ≤ 122px」的**正反两向**证据；
    **像素级**证明文字右边留白 11px；索引存在性 + `EXPLAIN QUERY PLAN` 不再出现 `TEMP B-TREE`；
    基准脚本「不含 `db.clear_media(` / `db.init_db(` 调用」的只读约束；《性能基线》的章节与对照表齐备。
  - 回归跑 `dev/smoke_v1250.py`：**只有 3 条失败，全是它自己的版本号断言**（`v1.25.0` / `2609210035` / 大版本 25），
    版本号已按规则升到 `v1.26.0` / `2609210036`，属预期；v1.25.0 的 6 条反馈行为断言**全部仍过**。
  - 定向渲染 `dev/render_v1260.py` → `dev/screenshots_v1260/`：品牌区特写（3×）、状态栏特写（2×）、
    「导航菜单」开关区在**朱红 / 天青两种高亮色**下的特写各一张 + 上下并排对照图。
  - 源码体检（`lint_check`）：23 个文件 **0 编译错误 / 0 个 CRLF**。

"""

OLD_ANCHOR = "### v1.25.0 (Build 2609210035) — 2026-09-21"
if s.count(OLD_ANCHOR) != 1:
    print("[FAIL] 迭代记录锚点命中 %d 次" % s.count(OLD_ANCHOR))
    sys.exit(1)
s = s.replace(OLD_ANCHOR, SEC + OLD_ANCHOR, 1)

# 目录结构：补上根目录的《性能基线.md》与 dev 里的基准脚本
OLD_TREE = """├── build_exe.py          # 打包脚本
├── requirements.txt
└── README.md"""
NEW_TREE = """├── build_exe.py          # 打包脚本
├── 性能基线.md            # 性能基准测试报告(由 dev/benchmark.py 在真实索引上生成)
├── requirements.txt
└── README.md"""
if s.count(OLD_TREE) != 1:
    print("[FAIL] 目录结构锚点命中 %d 次" % s.count(OLD_TREE))
    sys.exit(1)
s = s.replace(OLD_TREE, NEW_TREE, 1)

with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(s)
with io.open(P, encoding="utf-8", newline="") as f:
    back = f.read()
for need in ("### v1.26.0 (Build 2609210036) — 2026-09-21", "性能基线.md",
             "103×", "0.033 ms / 帧"):
    if need not in back:
        print("[FAIL] 回读缺 %r" % need)
        sys.exit(1)
with open(P, "rb") as f:
    raw = f.read()
print("[OK] README 已更新；大小 %d B，CRLF=%d" % (len(raw), raw.count(b"\r\n")))
