# -*- coding: utf-8 -*-
"""给项目 MEMORY.md 追加 v1.46.15 的两条通用硬规则。"""
import io
import os

P = r"E:\【01】自研软件\【26-19】本地影视中心\.workbuddy\memory\MEMORY.md"
ADD = """
## `QListWidget` + `setItemWidget` 的行高有两个来源（v1.46.15 定的，务必遵守）
- 行高 = `item.setSizeHint(h)` **减去** QSS `::item` 的上下 padding。只改其中一个，
  行内控件会被**静默压扁**（`visualItemRect().height()` 是 h，而 `itemWidget.height()`
  只有 `h - 上下padding之和`）。
- 判据：打印 `visualItemRect().height()` 与 `itemWidget.height()` 的**差值**，它必须等于
  QSS 里那条 `::item` 的上下 padding 之和。本项目全局是 `QListWidget::item{padding:5px 4px}`
  → 差值 10；`服务管理 → 已配置的媒体库` 这个列表单独命名 `#LibList` 压到 2px → 差值 4。
- 容器总高要跟着算：`min(条目数, 可见行数) * ROW_H + 边框 + 首末项 padding`。
  本项目把后两项抽成常量 `ui_settings.LIST_CHROME = 6`；**别写死 `+10`**（那是给 5px padding 留的，
  跟着 44 的行高会多出一条空白）。
- 想单独调某一个列表，用 **objectName + `QListWidget#Xxx::item`** 命名作用域，别动全局那条。
  **只改 padding，绝不写 height/min-height** —— 会盖掉按条目数自适应的 `setFixedHeight`。

## 「按钮里的字被切」的判据不是 height，是 `sizeHint > height`（v1.46.15 定的）
- 全局 `QPushButton{padding:7px 14px}`：28px 高的按钮，内容区只剩 `28-2-14 = 12px`，
  而一行中文要 17px → Qt **把字形上下各切约 3px**，用户报「按钮显示不全」。
- **`setFixedHeight(28)` 挡不住这个**：按钮外框仍是 28、`geometry` 也合规、不越界，
  所以「高度对不对 / 有没有越界」这类断言永远全绿 —— 必须断言
  `b.sizeHint().height() <= b.height()`，或在真机 `QT_QPA_PLATFORM=windows` 下看截图。
- 修法统一走 `ui_hero.compact_button(text, w, h, tooltip)`：它打 `compact` 属性，
  QSS `QPushButton[compact="1"]{padding:0 4px;}` 把内边距压成 0。**宽 56px 的正常按钮一样中招**，
  不是只有 28~48px 的窄按钮才需要它。
- 同版重打要顺延 `BUILD_SEQ`（0117 → 0118），并把旧的同版 exe 从根目录与 `history/` **都删掉**，
  否则交付物里会并排出现两个同版本号 exe。

## 真机点开工具窗后至少等 2.0s 再点导航（v1.46.15 白查半小时）
- 1.2s 时工具窗还没建完：`grabWindow(dlg)` 拿到 **0×0**，随后发 `WM_CLOSE` 给那个半成品窗口，
  **整个程序被关掉**，`app.log` 末尾只有一行 `退出 rc=0` —— 极像崩溃/abort，会把排查方向带偏
  （会去怀疑 QThread 生命周期）。
- 判定方法：先 `dump_windows` 看窗口还在不在，再 `grab`；`grab` 返回 0×0 一律先怀疑
  「窗口没了 / 还没建好」，不要先怀疑渲染。
- 顺带：`find_window_ex` 的门槛是 `w>300 and h>200`，所以它不会误抓到 tooltip；
  但 `dump_windows` 只按传入 pid 过滤，**PyInstaller onefile 的真身是子进程、pid 不同**，
  必须用 `pids_of_exe(name)` 而不是 `[proc.pid]`。

## 长文本别塞进 bash 的 `python -c "..."`（2026-10-29 把记忆文件写脏）
- 双引号里的**反引号会触发命令替换**：`\`LIB_ROW_H\`` 被当成命令执行 → 文本被吞掉/替换成
  `command not found` 之类的脏字符串，文件照样「写入成功」，但内容已毁。
- 写长文本、改 README/记忆一律：先用 Write 落一个 `.py`，再
  `python -u -c "import runpy; runpy.run_path(r'<绝对路径>', run_name='__main__')"`。
"""
s = io.open(P, encoding="utf-8").read()
if "## `QListWidget` + `setItemWidget` 的行高有两个来源" in s:
    print("已存在，跳过")
else:
    io.open(P, "w", encoding="utf-8").write(s.rstrip() + "\n" + ADD)
    print("MEMORY.md 已追加，长度", os.path.getsize(P))
