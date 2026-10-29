# -*- coding: utf-8 -*-
"""把 v1.46.9 的长期经验追加到项目 MEMORY.md（避免 bash 吃反引号）。"""
P = r"E:/【01】自研软件/【26-19】本地影视中心/.workbuddy/memory/MEMORY.md"

ADD = """

## 工程真身位置（2026-10-28 差点改错盘）
- 真工程：`E:/【01】自研软件/【26-19】本地影视中心`（当前 v1.46.9）。
- `Z:/【01】自研软件/【26-19】本地影视中心` 是 **2026-09-21 的旧镜像**（v1.28.1、ui_hero.py 782 行、无 ElidedLabel、
  dev 里最新只有 smoke_v190.py）。会话 cwd 可能指向 Z 盘，**动手前先看 `src/version.py` 版本号与文件 mtime**。

## ElidedLabel：高度不能锁死 max_lines（v1.46.9）
- 详情页标题/简介用 `ElidedLabel`：`_shown(width)` 在 paintEvent 里按像素折行、只画前 N 行。
  原来高度 `setMinimumHeight(lineSpacing * max_lines + 6)` → 1 行标题的框里空一整行，
  视觉上就是「标题与简介之间多出一条空行」。
- 修法：`_apply_lines()` 用 `_count_lines()` 按**当前宽度**数真实行数后 `setFixedHeight`，
  挂在 `resizeEvent` / `showEvent` / `setText` 上。**构造时不能算**：那时控件还是默认宽度（640），算出来是假数。
- 量「间隙」要量**文字底边**（`top + lines * lineSpacing`）到下一个控件，不能量控件矩形：
  2 行高度里只画 1 行时空白在框**内部**，框与框之间的布局间距恒定 —— 量框会得出「两者一样」的假结论。

## 真机验证：一个进程内跑完整流程（v1.46.9）
- 父进程（bash 命令）结束时，它 `Popen` 的 exe 会被一起收走 → 日志里出现「启动后 1 分钟 退出 rc=0」，
  之后再按标题找窗口，找到的其实是别的实例。→ 真机脚本一律写成
  `launch → click 序列 → PrintWindow 抓图 → WM_CLOSE → 查 app.log` **一次跑完**
  （`dev/_scratch/exe_selfcheck_v1469.py`）。
- `PostMessage` 盲点按钮不可靠：详情页 `QScrollArea` 会继承上次滚动位置，同一个按钮的 y 坐标会漂 ~100px。
  → 先抓图再点，或把「点击 → 落库」链路放进冒烟里打桩（`QInputDialog.getText` 打桩 + 真 `btn.click()`）。

## 标签（media.tags）与 nfo `<tag>`
- `tags` 与 `genres` 是两回事：`tags` 逗号分隔存 `media.tags`；`genres` 是从 `<genre>` 解析的「类型」。
  详情页标签行的增删只动 `<tag>`（`nfo_parser._write_multi_nodes`），**绝不能连 `<genre>` 一起重写**。
- 真实库里两者数值常常相同 —— 这批 nfo 的 `<tag>` 与 `<genre>` 本来就写的一样，不是 bug。
"""

with open(P, "a", encoding="utf-8") as f:
    f.write(ADD)
print("MEMORY_APPENDED", len(ADD))
