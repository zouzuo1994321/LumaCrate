# -*- coding: utf-8 -*-
"""v2.0.0：README 版本落点批量更新（徽章 / 下载名 / 目录树 / 迭代记录 / 冒烟表 / 强调色说明）。"""
import io

P = r"E:\【01】自研软件\【26-19】本地影视中心\README.md"
s = io.open(P, encoding="utf-8").read()
miss = []


def rep(old, new, tag):
    global s
    if old not in s:
        miss.append(tag)
        return
    s = s.replace(old, new, 1)
    print("OK   " + tag)


# 1) 徽章：版本号 + 颜色跟着新默认高亮色（朱红 c0392b → 极光蓝 006fee）
rep("![Version](https://img.shields.io/badge/version-v1.46.15%20(2610290118)-c0392b?style=flat-square)",
    "![Version](https://img.shields.io/badge/version-v2.0.0%20(2610290119)-006fee?style=flat-square)",
    "徽章 v2.0.0")

# 2) 下载名
rep("1. 到 [Releases](../../releases) 下载 `流明盒-v1.46.15-2610290118.exe`（约 57 MB，单文件）。",
    "1. 到 [Releases](../../releases) 下载 `流明盒-v2.0.0-2610290119.exe`（约 57 MB，单文件）。",
    "下载名")

# 3) 目录树里的 exe 名
rep("├── 流明盒-v1.46.15-2610290118.exe   # 单文件可执行",
    "├── 流明盒-v2.0.0-2610290119.exe    # 单文件可执行",
    "目录树 exe 名")

# 4) 「强调色派生」小节：12 色 → HeroUI 11 色
rep("### ② 强调色派生：12 色任选、全链路统一\n\n"
    "「外观」里 12 种高亮色可选。运行日志底色、进度环、选中流光、启动画面进度条全部由 `rgba(__ACCENT__, …)` "
    "派生（HLS 空间只调明暗 / 饱和度），改一处全链路跟着变，不会出现「某块颜色还是写死的旧色」。",
    "### ② 强调色派生：HeroUI 11 色任选、全链路统一（v2.0.0）\n\n"
    "「外观」里 **11 个圆形色点**可选（HeroUI 语义色板，默认「极光蓝 `#006fee`」）。运行日志底色、进度环、"
    "选中流光、启动画面进度条、A-Z 字母条、开关轨道、磨砂底衬柔光，全部由**同一份强调色**派生"
    "（`rgba(__ACCENT__, …)` + HLS 只调明暗 / 饱和度），改一处全链路跟着变。\n\n"
    "v2.0.0 的两条硬约束：① 旧版 12 色（朱红系）到新色板有 `config.LEGACY_ACCENT_MAP` **幂等迁移** —— "
    "老 `settings.json` 里的旧色值在「必须是色板之一」的归一闪之前先过映射，升级不会静默掉回默认色；"
    "② 自绘控件（字母条、开关、磨砂底衬）**懒读 `main_window.ACCENT_RGB`**、绝不自己 `import main_window`（会成环），"
    "与 QSS 令牌同源。",
    "强调色说明改 11 色")

# 5) 迭代记录：在 v1.46.15 那行之前插 v2.0.0
ROW = (
    "| v2.0.0 | 2610290119 | 2026-10-29 | **重大** | "
    "整代 UI 换血（用户原话：「UI 参考 heroui.com 给的风格，对 UI 组件套件进行全面升级，特别是配色方案。"
    "只保留那两条拖拽条。同步版本升级到 v2.0.0，做好回退的准备」）。产品代 1→**2**。"
    "① `style.qss` **整份重写**为 HeroUI 暗色语言：中性色阶 `#0a0a0b/111113/18181b/27272a/3f3f46`、"
    "前景三级 `#ecedee/a1a1aa/71717a`、大圆角（按钮·输入 12/10，卡片·分组 14/16，菜单·对话框 14/16，"
    "chip 与进度条全圆 `999px`）、弱边框 + 色块分层；选中态由「实心暗色」改成「强调色柔光底 `rgba(accent,0.22)`」。"
    "**选择器是 v1 的超集**（184 条全保留，新增 4 条）。"
    "② 三处 splitter handle（`ActorSplitV`/`ActorSplitH`/`ImageSplitH`）**原样保留** v1 的 "
    "`background: transparent; margin: 0px;` —— 把手是 `_GripHandle` 自绘的虚线 + 5 圆点，加底色就会盖住它；"
    "用户明确要求「只保留这两条拖拽条」。"
    "③ 色板 12 色朱红系 → HeroUI **11 色**（默认 `#006fee`）+ `LEGACY_ACCENT_MAP` 幂等迁移；"
    "`accent_shades()` 系数收窄；`_AccentSwatch` 由 30×24 扁平方形改成 **28×28 正圆 + 选中白环 + 手绘白勾**。"
    "④ Python 里约 **350 处**硬编码旧色值（内联 `setStyleSheet` + `QPainter` 画笔）一次性迁到中性色阶 / 语义色；"
    "`veil` 兜底底衬从「墨黑+朱红鎏金四团暖光」改成「`#0a0a0b` + 跟随高亮色的两团柔光」；"
    "字母条与开关轨道改为懒读 `ACCENT_RGB`。刻意保留：全局按钮横向内边距仍 **14px**（HeroUI 官网 16px）——"
    "改宽会让全站按钮各宽 4px、「评分」对话框从 240 顶到 250。"
    "验证：冒烟 **417/417**（新增 ㉗ 段 40 条，含「真造老配置跑 `load()` 验迁移」）、单测 ALL PASS、"
    "真机 exe **25/25**（点色卡 → settings.json 变 `#17c964` → 重抓图开关轨道 `mean=(27,198,101)` 证明真重绘；"
    "换色走 `_apply_settings()` 重建侧栏后进程存活；连切三页不崩；`app.log` 零异常）。"
    "回退：`docs/legacy/style_v1_46_15.qss` + `accent_v1_46_15.txt`（只退样式），"
    "或直接跑 `history/流明盒-v1.46.15-2610290118.exe`（整版回退）。 |\n"
)
rep("| v1.46.15 | 2610290118 | 2026-10-29         | 优化 |", ROW + "| v1.46.15 | 2610290118 | 2026-10-29         | 优化 |",
    "迭代记录新增 v2.0.0 行")

# 6) 冒烟表：条数 + ㉗ 段说明
rep("v1.43.0 起持续追加的**当前发布门槛**（最新 377/377，v1.46.15）。",
    "v1.43.0 起持续追加的**当前发布门槛**（最新 417/417，v2.0.0）。含 ㉗ 段（v2.0.0：11 色色板 / "
    "`ACCENT_DEFAULT==#006fee` / `LEGACY_ACCENT_MAP` 幂等且目标全在色板内 / 真造老配置跑 `load()` 验迁移 / "
    "四档派生亮度单调 / QSS 无残留令牌与旧墨金 / 三处 splitter handle 仍 `transparent` / 色卡 28×28 与 "
    "`R_DOT_ON<R_DOT<R_RING` / 开关 `_OFF`·`_ON` / `src/*.py` 无旧色残留 / veil 与 letter_index 取到当前高亮色）；含 ㉖ 段：",
    "冒烟条数与 ㉗ 段说明")

io.open(P, "w", encoding="utf-8").write(s)
print()
print("!! 未命中：%s" % miss if miss else "全部命中。")
