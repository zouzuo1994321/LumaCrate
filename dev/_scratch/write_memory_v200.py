# -*- coding: utf-8 -*-
"""v2.0.0：往今日记忆追加一节（append-only）。"""
import io

P = r"E:\【01】自研软件\【26-19】本地影视中心\.workbuddy\memory\2026-10-29.md"
s = io.open(P, encoding="utf-8").read()
assert "v2.0.0" not in s, "今日记忆里已经有 v2.0.0 段，别重复追加"

BLOCK = """

---

# v2.0.0 — 整代 UI 换血（HeroUI 暗色语言）

## 需求
用户原话：「UI 参考 https://heroui.com/ 这个网页给的风格对软件 UI 组件套件 进行全面的升级，特别是
配色方案等。**只保留**那两条拖拽条。同步版本升级到 v2.0.0，做好回退的准备。」
给了四张图：① HeroUI 的配色切换器（一排正圆色点，选中的套白环打勾）②③ 暗色组件观感
④ 两处 5 点拖拽条（演员检测 / 图像检测）—— 明确**只保留拖拽条**，其余全重做。

## 做了什么
1. **回退留档先行**：`docs/legacy/style_v1_46_15.qss`（31388 B）+ `accent_v1_46_15.txt`（旧 12 色原文、
   旧四档派生系数、三步回退步骤、整版回退路径）。
2. `src/style.qss` **整份重写**为 HeroUI 暗色语言：中性色阶 `#0a0a0b/111113/18181b/27272a/3f3f46`、
   前景三级 `#ecedee/a1a1aa/71717a`、大圆角（按钮·输入 12/10、卡片·分组 14/16、菜单·对话框 14/16、
   chip 与进度条全圆 999px）、弱边框 + 色块分层、选中态 = 强调色柔光底 `rgba(accent,0.22)`。
   **用选择器差集验证没写丢**：v1 有 184 条，v2 是它的**超集**（+4 条），差集为空 —— 这条检查比逐行读 QSS 可靠。
3. **拖拽条原样保留**：三处 `QSplitter#ActorSplitV / #ActorSplitH / #ImageSplitH::handle` 仍是
   `background: transparent; margin: 0px;`，QSS 里还写了「不要加底色/圆角，否则会盖掉自绘圆点」的注释，
   冒烟 ㉗ 段对三处逐条断言。真机放大抓图 `v200_grip_band.png` 确认虚线与 5 个蓝点都在。
4. 色板 12 色（朱红系）→ HeroUI **11 色**（默认 `#006fee` 极光蓝）+ `LEGACY_ACCENT_MAP` **幂等迁移**
   （插在「必须是色板之一」的归一闪**之前**，否则老用户升级掉回默认色）。
   `accent_shades()` 系数收窄为 dark `-0.120/+0.060`、deep `-0.070/+0.040`、light `+0.100/+0.060`。
   `_AccentSwatch` 由 30×24 扁平方形重做为 **28×28 正圆**（`R_DOT=10 / R_DOT_ON=9 / R_RING=13 / RING_W=2`，
   选中 = 白环 + 手绘白勾）。
5. **Python 内联色一次性迁移 ~350 处**（hex 扫描 + 整数元组扫描，三轮脚本：316 + 34 + 41）。
   例外两个文件：`config.py`（`LEGACY_ACCENT_MAP` 的**键**就是旧色值，替换会毁掉迁移表）、
   `version.py`（历史注释里的色值要保留原样，否则「RGB=(15,13,11) 正是 #18181b」会自相矛盾 —— 第一轮就踩了，已还原 4 行）。
6. 视觉地基：`veil.default_backdrop()` 从「墨黑 + 朱红/鎏金四团暖光」改成「`#0a0a0b` + 跟随高亮色的两团
   低透明柔光（54/26）+ 两团中性提亮」；`letter_index` 与 `ToggleSwitch` 改为**懒读 `main_window.ACCENT_RGB`**。
7. **刻意不迁的一处**：全局按钮横向内边距保持 v1 的 **14px**（HeroUI 官网 16px）。改 16px 会让所有按钮
   sizeHint 宽 +4px，「评分」对话框从 240 顶到 250（冒烟里那条 `200 <= sizeHint <= 248` 立刻红）。

## 验证
- 冒烟 **417/417**（v1.46.15 是 377，新增 ㉗ 段 40 条）。
  其中「迁移是否生效」不再用文本序判（`ACCENT_COLORS` 在文件顶部还有定义处，`find()` 到的是那一处，
  第一版断言假红），改成**真造一份 `accent=#c0392b` 的 settings.json 跑 load()** 看是否落到 `#f31260`。
- `dev/test_v119_logic.py` ALL PASS。
- 真机 exe 验收 **25/25**：老配置 `#c0392b` 载入即迁；按**导航高亮行反查**确认「个性化设置」真切过去；
  真点「翡翠」色卡 → settings.json 变 `#17c964` → 等 2.2s 重抓图，开关轨道 `mean=(27,198,101)`（真重绘）；
  换色走 `_apply_settings()`（重建侧栏，v1.27.0 崩过的路径）后进程存活；连切三页不崩；`rc=0`；`app.log` 8 行零异常。
- 预览图 6 张在 `docs/preview/`，真机图 4 张在 `dev/screenshots/`。

## 本轮踩的新坑（已写进 MEMORY.md）
- **出图脚本「按最多数不透明像素取样当底色」会把透明页面染成按钮色**：演员检测页整张变蓝，
  看着像产品缺陷，其实是页面根控件 `background: transparent` + 取样被蓝色按钮带偏 —— 页面级 grab 必须**强制底色**。
- **离屏 `ToggleSwitch` 动画不跑完**：`setChecked(True)` 后 `_pos` 还停在 0，出图两个开关都是「关」。
  出图要终态 → 手动 `_anim.stop(); _pos = 1.0`。
- **`_accent_n()` 这类「判红」的像素断言换色后恒为 0**：改成按 `ACCENT_RGB` 算通道距离（任一通道差 ≤46）。
- **真机点击「点完就当成了」不成立**：页面切换有动画，且设置里改色会触发 `_apply_settings()` 重建，
  立刻点下一处会落到旧页面 → 每次点完都要**回读导航高亮行**确认，并留重试。
- **真机换色后立刻抓图会抓到旧色那一帧**（settings.json 先落盘、重绘在后）→ 断言前至少等 2s。
- **真机点色卡要挑「和当前色不同」的那个**：老配置迁移后本来就是玫红，点玫红等于没测。
- **会话记录里能捞回被批量替换改坏的历史注释原文**（`version.py` 那 4 行就是从 jsonl 里 grep 回来的）。

## 交付 + 回退
- `流明盒-v2.0.0-2610290119.exe`（56.9 MB，root + `history/` 各一份，
  SHA-256 `40b98f580263f1b8846c626e7789879b0f55c7ae43f238133df2d435fb4a5ccf`）
- `history/流明盒-v2.0.0-2610290119-源码.zip`（518 文件，6.4→3.2 MB，含 `docs/legacy/`）
- `history/流明盒-v2.0.0-2610290119-封存说明.txt`（含 SHA-256 与两条回退路径）
- 图：`docs/preview/v200_components_compare.png`（同一套控件 左 v1 / 右 v2）、`v200_swatches_compare.png`、
  `v200_main.png`、`v200_settings_appearance.png`、`v200_actorcheck.png`、`v200_grip_band.png`；
  真机 `v200_exe_main.png`、`v200_exe_appearance.png`、`v200_exe_accent_jade.png`、`v200_exe_service.png`
- ★ 两条回退路径：A 只退样式（`docs/legacy/` 两份 + `config.py` 三步操作）；
  B 整版回退（`history/流明盒-v1.46.15-2610290118.exe`，即上一版的回滚基线）。
"""

io.open(P, "a", encoding="utf-8").write(BLOCK)
print("appended", len(BLOCK), "chars ->", P)
