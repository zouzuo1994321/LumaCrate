# -*- coding: utf-8 -*-
"""把 2026-10-23.md 里被 shell 反引号吃坏的 v1.46.7 段整段重写。

背景：上一步用 `python -c "...note..."` 传长文本，bash 把内容里的反引号当命令替换
执行了，反引号内的标识符全部变成空串。这里从 `## v1.46.7` 处截断后重新写入。
"""
import io
import os

P = r"E:/【01】自研软件/【26-19】本地影视中心/.workbuddy/memory/2026-10-23.md"

NOTE = '''

## v1.46.7（反馈：演员/导演「全部作品」还是卡在 48 部）

### 根因（v1.46.6 漏修的第二处）
- `_view_actor_detail()` 的写法是 `v.addWidget(self._grid(works))` 之后 `self._page(None, w)`
  —— 网格被**又套进一层普通 QWidget** 才交给页面。
- `_page()` 只认两种形态：`body_widget.lazy_grid` 属性、或 `body_widget` 自带 `attach_scroll`。
  这次**两者都不成立** → `attach_scroll()` 从未被调用 → `_scrollbar` / `_viewport` 都是 None。
- 虚拟网格 `_render()` 里 `y = sb.value()`（恒 0）、`vh` 退回 700 兜底 → `r1 = 700//rh + 3`
  ≈ 5~6 行 → **只建 40~48 张卡**，但 `_body` 仍按 total_rows 撑高（滚动条能拖）→
  用户滚下去看到的是空白，观感就是「只显示到 48 部」。
- 探针铁证：`未知演员 5143 部` → `_scrollbar=None`、`_cards` 索引 `[0..39]`；
  同时 `_body` 高 232766（说明 total_rows 算对了，**只是没跟着滚动换窗口**）。
  这一条把「数据没读出来」和「滚动没联动」区分开了 —— 前者会连滚动条一起没有。

### 修法（三层，缺一不可）
1. `_page()`：`target is None` 时 `body_widget.findChildren(LazyGrid)` 取第一个（递归兜底）。
2. `LazyGrid._adopt_scroll()`：`_scrollbar is None` 时沿父链找**最近的 QScrollArea** 自己认领；
   在 `_render()` 开头调用。→ 任何「把网格套进容器」的新写法都不会再复发。
3. `attach_scroll()` 幂等：同一个 scrollbar 重复挂直接 return；换 scrollbar 时先
   `disconnect` 旧的 `valueChanged`（否则显式挂 + 自愈各挂一次，换卡跑两遍、白查一次库）。

### 验证
- 全页面自检 `probe_v1467b.py`（8 页）：最近播放 60/60、我的收藏 984/984、
  媒体墙 48708/48707、合集（增量 144 张）、演员库 5937/5936、导演库 1221/1220、
  **演员全部作品 5143 → 末索引 5142**、**导演全部作品 1222 → 1221**，全 PASS。
  判据要区分虚拟/非虚拟：非虚拟（`virtual=False`，合集 `batch=48`）没有 `_viewport`、
  `_cards` 也恒空，只能查 `_scrollbar` + `_grid.count()`。
- 冒烟 **223/223**（新增 ⑱ 段 8 条：总数/挂滚动条/拿视口/列数>0/滚动范围>0/尾部可达/
  自愈生效/源码级 `_adopt_scroll()` 调用）；单测 **28/28**。
- 预览图：`v1467_works_top.png` / `v1467_works_mid.png` / `v1467_works_tail.png`
  （中段满屏、尾部最后 4 张，肉眼可证不再空白）。
- 真机：ALIVE_OK / `VER_OK（流明盒  v1.46.7 (Build 2610230109)）` / 未捕获异常 **0** /
  sysmon 单例 **1** / 零残留。
- 封存 `history/流明盒-v1.46.7-2610230109-*`（421 文件，SHA-256 前 16 位 `8882477a84164e70`）。

### 教训
- **「卡在 N 条」先分三路查**：① `_total`（数据层）；② `_body` 高度（几何层）；
  ③ `_scrollbar` / `_viewport`（联动层）。这次第一、二层都对，只有第三层坏 →
  「滚动条能拖但画面不动」，用户描述成「不显示了」。
- 上一版只修了「演员库/导演库」列表页，**没顺着 `_grid()` 的所有调用点（recent / 演员作品 /
  合集预览）各查一遍**，才让同一症状第二次被反馈。改公共组件要把**所有调用点**过一遍。
'''

with io.open(P, "r", encoding="utf-8") as fh:
    t = fh.read()
i = t.find("## v1.46.7")
if i < 0:
    raise SystemExit("未找到 v1.46.7 段，未做修改")
head = t[:i].rstrip() + "\n"
with io.open(P, "w", encoding="utf-8") as fh:
    fh.write(head + NOTE.lstrip("\n"))
print("重写完成；新长度", os.path.getsize(P), "字节")
with io.open(P, "r", encoding="utf-8") as fh:
    t2 = fh.read()
print(t2[t2.find("## v1.46.7"):][:600])
