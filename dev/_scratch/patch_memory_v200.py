# -*- coding: utf-8 -*-
"""v2.0.0：给项目长期记忆 MEMORY.md 追加一节硬规则（控制在 ~2.5k 字符）。"""
import io

P = r"E:\【01】自研软件\【26-19】本地影视中心\.workbuddy\memory\MEMORY.md"
s = io.open(P, encoding="utf-8").read()
assert "v2.0.0 起的组件套件口径" not in s

BLOCK = """

## 组件套件口径 = HeroUI 暗色语言（v2.0.0 起的硬规则）
- 唯一真源仍是 `src/style.qss` + `render_style()` 的令牌替换。**中性色阶**：`#0a0a0b`(页面底) /
  `#111113`(面板·状态栏) / `#18181b`(卡片·对话框) / `#27272a` / `#3f3f46`(分割线·轨道)；
  **前景三级**：`#ecedee` / `#a1a1aa` / `#71717a`。**圆角**：按钮·输入 12/10、卡片·分组 14/16、
  菜单·对话框 14/16、chip 与进度条 `999px`。选中态一律「强调色柔光底 `rgba(accent,0.22)`」，
  不再用实心暗色。新写内联样式/自绘画笔时**直接用这套色值**，别再造墨金色。
- **改 QSS 后用「选择器差集」自证没写丢**：把旧文件与新文件的选择器集合求差，v1 的必须全在新文件里。
  逐行读 600 行 QSS 一定会漏，差集是机械判据。
- **全局按钮横向内边距锁 14px**（HeroUI 官网是 16px）：按钮 sizeHint 宽决定紧凑行最小宽，改 16px
  会让全站按钮各宽 4px、「评分」对话框从 240 顶到 250（冒烟会红）。

## 色板迁移必须幂等，且只能放在「归一闪」之前
- `config.ACCENT_COLORS` / `ACCENT_DEFAULT` 换版时，必须同步 `LEGACY_ACCENT_MAP`（旧色 → 新色），
  并在 `load()` 里**先过映射、再做「必须是色板之一」的归一**。顺序反了 = 老用户升级静默掉回默认色。
- 映射表要满足「目标不再出现在键里」（`all(v not in MAP for v in MAP.values())`），否则每存一次配置漂一格。
- **`config.py` 永远不参与批量色值替换**：迁移表的键就是旧色值，替换会毁表。
  `version.py` 的历史注释同理（保留原色值，否则注释自相矛盾）。

## 三处拖拽条 = 用户点名保留，别碰
`QSplitter#ActorSplitV / #ActorSplitH / #ImageSplitH::handle` 必须保持
`background: transparent; margin: 0px;`。把手本体是 `ui_actorcheck._GripHandle` 自绘的虚线 + 5 个圆点，
QSS 只要给 handle 加底色/圆角/边框，圆点就被盖住。冒烟 ㉗ 段对三处逐条断言，改 QSS 时别删。
自绘控件跟高亮色的正确姿势：**懒读 `main_window.ACCENT_RGB`**（`sys.modules.get("main_window")`），
绝不在这些模块里 `import main_window`（会成环）。

## 出图 / 真机断言的四个新坑（v2.0.0 一次踩齐）
- **页面级 `grab()` 必须强制底色**：页面根控件 `background: transparent`，整张图透明时
  「按最多数不透明像素取样当底色」会被某块彩色控件带偏（演员检测页整张变按钮蓝，看着像产品缺陷）。
- **离屏 `ToggleSwitch` 动画不跑完**：`setChecked(True)` 后 `_pos` 仍 0，出图两个开关都画成「关」。
  出图要终态就手动 `_anim.stop(); _pos = 1.0 if on else 0.0`。
- **「判红」的像素断言换色后恒为 0**：改成按 `ACCENT_RGB` 算通道距离（任一通道差 ≤46），换任何色都成立。
- **真机点击「点完就当成了」不成立**：页面切换有动画、改色还会触发 `_apply_settings()` 重建；
  必须**回读导航高亮行**确认页面真切过去了（`nav_rows()` 找 x∈[12,130] 里比中位亮度高的连续行），并留重试。
  换色后**至少等 2s 再抓图**（settings.json 先落盘、重绘在后），且要挑一个「和当前色不同」的色卡去点。
"""

io.open(P, "a", encoding="utf-8").write(BLOCK)
print("appended", len(BLOCK), "chars")
