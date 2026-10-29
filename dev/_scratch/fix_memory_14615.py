# -*- coding: utf-8 -*-
"""修正 2026-10-29.md：删掉被 bash 反引号污染的 v1.46.15 段，重新写一份干净的。"""
import io
import os

P = r"E:\【01】自研软件\【26-19】本地影视中心\.workbuddy\memory\2026-10-29.md"
MARK = "# v1.46.15（2610290118）"

s = io.open(P, encoding="utf-8").read()
i = s.find(MARK)
if i > 0:
    s = s[:i].rstrip() + "\n"
    print("已截断到 v1.46.14 段末尾，长度", len(s))
else:
    print("没找到 v1.46.15 段，保持原样，长度", len(s))

ADD = """
# v1.46.15（2610290118）「服务管理 → 已配置的媒体库」行距压紧 + 按钮里的字被压

## 用户反馈（两条，第二条是同版重打的原因）
1. 截图：「**压缩 已配置的媒体库 的高度**」；并要求「对软件进行测试和封存。下一个版本将对 UI
   进行一次完整的迭代。**做好回滚的准备**」。
2. 截图：「**压缩后这些按钮显示不全了**」（三个「编辑 / 扫描 / 删除」）。

## 根因（两条，成因完全不同，别混在一起）
- **行距松 ≠ LIB_ROW_H 一个人偏大**：`setSizeHint(54)` 之外，全局
  `QListWidget::item{padding:5px 4px}` 还会再吃掉上下各 5px → 真正交给 `setItemWidget` 的行控件
  只有 **44**；而行内 `setContentsMargins(6,4,6,4)` + 28px 按钮只用 36px，**剩 8px 被均分到上下**。
  空库分支还硬写 `+10`（那是给 5px padding 留的），跟着 44 走会多出一条空白。
- **按钮字被切与行高无关**：全局 `QPushButton{padding:7px 14px}` 让「编辑」的 `sizeHint` 高
  **33px**（7+7 内边距 + 17 字高 + 2 边框），代码 `setFixedHeight(28)` 硬压 → 内容区只剩 **12px**，
  字形上下各被切约 3px。**离屏冒烟量「按钮 height==28、不越界」永远全绿，量不出这个问题。**

## 改法
- `ui_settings`：`LIB_ROW_H` 54→**44**；新增常量 `LIST_CHROME = 6`（上下边框 2 + 首末项 2px 内边距），
  空库分支与按条目数自适应分支都用它；列表 `setObjectName("LibList")`。
- `style.qss`：新增 `QListWidget#LibList::item { padding: 2px 4px; }`（命名作用域，只影响这一个列表；
  **只改 padding，绝不写 height/min-height** —— 会盖掉按条目数自适应的 `setFixedHeight`）。
- 三个按钮改走 `ui_hero.compact_button("编辑", 56, 28, tooltip)`（打 `compact` 属性 →
  `QPushButton[compact="1"]{padding:0 4px;}`），**尺寸仍 56×28，行高与列表高完全不变**。

## 实测
- 3 行列表 **172 → 138**；每项 `visualItemRect` 高 54→44、行控件 44→40（h 差 10→4）；
  按钮仍完整 28px、`verticalScrollBar().maximum()==0`；组框图 1134×576 → **1134×542**。
- 6 个库封顶 **182**（4×44+6）并出滚动条；空库 **50**（44+6）。
- 真机（`QT_QPA_PLATFORM=windows`，dpr=1.0）：行控件 40、按钮 56×28 位于 y=6，`bottom+?` 不越界。

## 验证
- 冒烟 **377/377**。新增 ㉖ 段 17 条，其中两条是真正能钉住「字被切」的判据：
  按钮带 `compact` 属性、`sizeHint().height() <= height()`（33→19）。只量 28px 不越界是量不出来的。
- `dev/test_v119_logic.py` ALL PASS。
- 真机验收 **13/13**：标题 `流明盒  v1.46.15 (Build 2610290118)` / 不 Hung / 主窗 1920×1080 /
  工具窗 1336×999 / 点进服务管理后进程存活且可抓图 1320×960 / 关窗 rc=0 /
  app.log 8 行零未捕获异常。

## 踩坑 / 复用
- **`QListWidget` + `setItemWidget` 的行高有两个来源**：`setSizeHint` 与 QSS `::item` 的 padding。
  只调其中一个，行内控件会被静默压扁 —— 判据是打印 `visualItemRect().height()` 与
  `itemWidget.height()` 的**差值**（应等于上下 padding 之和）。
- **「按钮里的字被切」不要只看按钮 height**：要看 `sizeHint().height()` 是否大于 `height()`；
  大于就说明 QSS 内边距把内容区压负、Qt 会裁字。**56px 宽的正常按钮一样中招**（不是只有 28~48px 的窄按钮）。
- **同版重打要顺延 BUILD_SEQ**（0117 → 0118），并把旧的同版 exe 从根目录与 `history/` 都删掉，
  否则交付物里会并排出现两个同版本号 exe。
- **真机点开工具窗后至少等 2.0s 再点导航**：1.2s 时窗口还没建完，`grabWindow` 拿到 0×0，
  随后的 `WM_CLOSE` 会把整个程序关掉（日志里只有一行 `退出 rc=0`，极像崩溃，排查方向会被带偏）。
- `_nav_*.png` / `_liblist_*` 这类下划线前缀是临时图，**封存前要复制成正名前缀**（`v14615_*`），
  否则会被 `archive_version.py` 的截图过滤规则漏掉、进不了 zip。
- **别在 bash 的 `python -c \"...\"` 里写反引号**：会触发命令替换，把整段文本吞掉/替换成脏数据
  （本轮就把记忆文件写脏了一次）。写长文本一律先落成 `.py` 再用 `runpy` 跑。

## 交付 + 回滚
- `流明盒-v1.46.15-2610290118.exe`（57 MB，root + `history/` 各一份，
  SHA-256 `84fc32e3fbb619c6e4f37ec143160aa2b33e54b8c12de6a4f9d1857d5a6ac8b8`）
- `history/流明盒-v1.46.15-2610290118-源码.zip`（495 文件，6.0→3.0 MB）
- `history/流明盒-v1.46.15-2610290118-封存说明.txt`（含 SHA-256 与「回滚基线」说明）
- 图：`v14615_buttons_before_after.png`（按钮改前/改后）、`v14615_exe_service.png`、
  `v14615_exe_service_full.png`、`v14615_liblist_before.png` ↔ `v14615_liblist_after.png`、
  `v14615_exe_start.png`
- ★ 本版即「下一版 UI 大改之前的**回滚基线**」：只动了 `src/ui_settings.py` 与 `src/style.qss` 两处，
  回滚 = 换回本版 exe，或从本源码 zip 重新 `python build_exe.py`（两者 SHA-256 一致）。
"""

with io.open(P, "w", encoding="utf-8") as f:
    f.write(s + ADD)
print("最终长度", os.path.getsize(P))
