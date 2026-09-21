# -*- coding: utf-8 -*-
"""README v1.25.0 迭代记录收尾：构建号 0035 + 补两处「发布前加固」。

0034 打好之后在真机 `app.log` 里捡到一条 v1.24.1 起就存在的崩溃（QTimer 已析构），
外加真机验收脚本自身在「破坏性按钮的模态确认框」上翻车 —— 两件事都并进本版，
故构建号顺延到 0035 重打。
"""
import os

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"


def patch(rel, label, old, new, count=1):
    p = os.path.join(ROOT, rel)
    with open(p, encoding="utf-8", newline="") as f:
        s = f.read()
    n = s.count(old)
    if n != count:
        print(f"[失败] {label}: 锚点命中 {n} 次（期望 {count}）")
        print("----- 锚点 -----")
        print(old[:400])
        raise SystemExit(1)
    s = s.replace(old, new, count)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print(f"[OK] {label}")


patch(
    r"README.md",
    "README：标题构建号 -> 0035",
    "### v1.25.0 (Build 2609210034) — 2026-09-21",
    "### v1.25.0 (Build 2609210035) — 2026-09-21",
)

patch(
    r"README.md",
    "README：主题行 3 处 -> 4 处",
    "另有 3 处**只在写断言时才暴露的静默失效**，一并修掉。",
    "另有 4 处**只在写断言 / 读运行日志时才暴露的静默失效**，一并修掉。",
)

patch(
    r"README.md",
    "README：小标题 3 处 -> 4 处",
    "- **写断言时才暴露的 3 处静默失效（均已修 + 补断言）**：",
    "- **写断言 / 读运行日志时才暴露的 4 处静默失效（均已修 + 补断言）**：",
)

patch(
    r"README.md",
    "README：补第 4 条静默失效（QTimer 已析构）",
    """  3. **「补全标签」会悄悄删掉技术标签**""",
    """  3. **选中卡片的流光定时器会「已析构」崩溃**（**这条不在反馈里，是打包后顺手 grep 真机 `index_data/logs/app.log` 捡到的**）——
     日志里 `2026-09-21 09:25:33`（`v1.24.1 Build 2609210033` 的一次真实会话，刚做过媒体库扫描）留了一条
     `main_window.py, in mousePressEvent → _select_card → set_selected`：
     `RuntimeError: libshiboken: Internal C++ object (PySide6.QtCore.QTimer) already deleted.`
     根因是新旧写法都有的：`set_selected(True)` **每次都新建一个 QTimer 并覆盖旧引用**，旧的那个虽然还挂在卡片下不泄漏，
     但一旦被析构，`self._timer` 就成了「已析构的 C++ 对象」，下一次进来在 `self._timer.stop()` 处直接抛异常
     —— 而扫描 / 换页会批量 `deleteLater()` 上一批卡片，此时事件队列里恰好还压着投给卡片的鼠标事件。
     现改为**定时器只建一次、之后复用**，`stop()` 再包一层 `RuntimeError` 兜底（真析构了就丢引用按需重建）；
     同时把 `MainWindow._selected_card` 的不变式坐实为「**活的卡 或 None**」（重复点同一张已析构的卡时清掉悬空引用，
     目标卡已析构则不记入）。以后**每版打包后都 grep 一遍 `未捕获异常`**，这类只在真机复现的漏洞只能这么捡。
  4. **「补全标签」会悄悄删掉技术标签**""",
)

patch(
    r"README.md",
    "README：冒烟条数 284 -> 292",
    "- 新增 `dev/smoke_v1250.py`，**284 条断言全过 / 0 失败**",
    "- 新增 `dev/smoke_v1250.py`，**292 条断言全过 / 0 失败**",
)

patch(
    r"README.md",
    "README：冒烟条数处的 J 段说明",
    "**渲染结果里没有 `xxx-color: 192, 57, 43;` 这种非法声明**；外发光的 blur / offset / 颜色 / 透明度，以及「换选中会摘掉旧 effect」「已析构的卡安静退出」；`#Seg` 选择器与三个 chip 的 checkable / 单选 / 再点取消。",
    "**渲染结果里没有 `xxx-color: 192, 57, 43;` 这种非法声明**；外发光的 blur / offset / 颜色 / 透明度，以及「换选中会摘掉旧 effect」「已析构的卡安静退出」；`#Seg` 选择器与三个 chip 的 checkable / 单选 / 再点取消。\n  - **J 段（Build 0035 新增 8 条）专钉上面第 3 条崩溃**：定时器「只建一次、复用」；把它用 `shiboken6.delete()` 真析构后再切选中态**不抛异常**并能重建；`_select_card` 对已析构卡片安静跳过且不记入 `_selected_card`；源码里旧写法已消失。",
)

patch(
    r"README.md",
    "README：验证段补 build_exe 归档与真机脚本加固",
    "- **影响面**：`src/tagopt.py`（新增）",
    """- **顺带修掉的两个「工具链」问题（都不影响 exe 内容，但都会让人白跑一轮）**：
  1. **`build_exe.py` 让根目录每构建一次就多攒一个 48MB 旧包** —— 原归档逻辑遇到 `history/` 已有同名留档就打印 `[保留]` 并**原地不动**（本意是防止成品被重复搬进 `dev/`，但副作用是根目录永远留着上一个版本）。构建 0035 之前根目录同时躺着 `0033` 与 `0034`。现改为 `os.replace` **覆盖**那份字节相同的留档（原子操作，失败则退回 `[保留]`）；本次构建日志已打出两条 `[归档] … （覆盖字节相同的同名留档）`，**根目录现在只剩最新那一个 exe**。
  2. **`dev/live_verify.py` 点「破坏性按钮」时会被模态确认框整段废掉验收** —— 「执行写入」会弹 `QMessageBox`，**主窗与工具窗同时被置 `disabled`**，之后所有 `PostMessage` 点击**全部静默失效**：日志一路写「抓取成功」、截图与上一张逐字节相同、目标文件一个字节没变。更坑的是该确认框的**默认按钮被刻意设成 `No`**（破坏性动作的安全默认），所以「按回车确认」等于取消。现新增 `find_modal()`（门槛放到 `w>150 and h>80`，否则漏掉 ~420×180 的确认框）+ `bottom_button_centers()`（扫截图底部亮像素聚类定位按钮，**不写死坐标**）+ `confirm_modal_yes()`（点**最左**那个按钮 = Qt 的 Yes）。
- **影响面**：`src/tagopt.py`（新增）""",
)

print("\nREADME 收尾补丁完成。")
