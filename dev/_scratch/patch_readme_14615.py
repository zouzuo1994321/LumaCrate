# -*- coding: utf-8 -*-
"""把 v1.46.15 写进 README（迭代表 + 冒烟门槛说明）。跑一次即可。"""
import io

P = r"E:\【01】自研软件\【26-19】本地影视中心\README.md"
s = io.open(P, encoding="utf-8").read()

row = (
    "| v1.46.15 | 2610290118 | 2026-10-29         | 优化 | "
    "一条反馈（截图）：**「服务管理 → 已配置的媒体库」这块太高，把行距压紧**。根因不是 `LIB_ROW_H`(54) 一个人偏大，"
    "而是它与全局 `QListWidget::item{padding:5px 4px}` 叠加 —— `setSizeHint` 给 54，列表项自己再吃掉上下各 5px，"
    "真正交给 `setItemWidget` 的行控件只剩 44；而行内边距(4+4) + 28px 按钮只用到 36px，剩下 8px 被均分到上下 → "
    "每行看着像被拉开。改法两处联动：① `LIB_ROW_H` 54→**44**，列表容器余量从写死的 `+10` 抽成常量 `LIST_CHROME=6`"
    "（空库分支同样用它，否则会多出一条空白）；② 该列表单独 `objectName=\"LibList\"`，QSS 加 "
    "`QListWidget#LibList::item{padding:2px 4px}` 只作用于它（**只改 padding，绝不写 height/min-height**，"
    "否则会盖掉按条目数自适应的 `setFixedHeight`）。实测 3 行列表 **172 → 138**，每项 `visualRect` 54→44、"
    "行控件 44→40，按钮仍完整 28px、不出竖向滚动条。"
    "同版重打（Build 0118）补上真机暴露的第二个缺陷：**这三个按钮里的字上下被切** —— 与行高无关，是全局 "
    "`QPushButton{padding:7px 14px}` 让按钮 `sizeHint` 高 33px，而代码 `setFixedHeight(28)` 硬压，内容区只剩 12px"
    "（一行字要 17px）→ 改走 `ui_hero.compact_button()`（`compact` 属性 + `padding:0 4px`），字完整居中，"
    "尺寸仍 56×28、行高与列表高完全不变。\n"
)

old = "| v1.46.14 | 2610290116 | 2026-10-29"
assert old in s, "找不到 v1.46.14 那一行"
s = s.replace(old, row + old, 1)

smoke_old = "含 ㉕ 段：「我的评分」对话框"
assert smoke_old in s, "找不到冒烟门槛说明"
smoke_new = (
    "含 ㉖ 段：媒体库列表（`LIB_ROW_H==44`、`LIST_CHROME==6`、3 库列表高 138、每项 `visualRect` 44、"
    "行控件 40、按钮 28px 不越界且带 `compact` 属性、`sizeHint` 高不再超过实际高度、6 库封顶 182 出滚动条、"
    "空库分支走 `LIST_CHROME`、QSS `#LibList::item` 只改 padding 不写 height）。含 ㉕ 段：「我的评分」对话框"
)
s = s.replace(smoke_old, smoke_new, 1)

io.open(P, "w", encoding="utf-8").write(s)
print("README 已更新")
