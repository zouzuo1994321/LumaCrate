# -*- coding: utf-8 -*-
"""v2.0.0 封存：给 archive_version.py 传本版摘要，并额外做「回滚可执行性」校验。

用户要求「做好回退的准备」，所以本版封存额外断言：
  ① 根目录 exe 与 history/ 副本**逐字节一致**（同一份 SHA-256）；
  ② 源码 zip 存在且能列出顶层目录 / 含 src/style.qss；
  ③ 封存说明里写了 SHA-256、「回退」字样，以及**两条回退路径**；
  ④ `docs/legacy/` 里那两份 v1 留档真的在（只回退样式就靠它们）。
"""
import ctypes
import hashlib
import os
import runpy
import sys
import zipfile

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
import version as ver   # noqa: E402

STEM = f"{ver.APP_NAME}-{ver.VERSION}-{ver.BUILD}"
HIST = os.path.join(ROOT, "history")
ZIP = os.path.join(HIST, f"{STEM}-源码.zip")
NOTE = os.path.join(HIST, f"{STEM}-封存说明.txt")
EXE = os.path.join(ROOT, STEM + ".exe")
EXE_H = os.path.join(HIST, STEM + ".exe")
LEGACY_QSS = os.path.join(ROOT, "docs", "legacy", "style_v1_46_15.qss")
LEGACY_ACC = os.path.join(ROOT, "docs", "legacy", "accent_v1_46_15.txt")

NOTE_TEXT = (
    "整代 UI 换血（用户原话：「UI 参考 heroui.com 这个网页给的风格，对软件 UI 组件套件进行全面的升级，"
    "特别是配色方案。只保留那两条拖拽条。同步版本升级到 v2.0.0，做好回退的准备」）。"
    "产品代 1 → **2**，外部版本号 v1.46.15 → **v2.0.0**。"
    "① `src/style.qss` **整份重写**为 HeroUI 暗色语言：中性色阶 #0a0a0b / 111113 / 18181b / 27272a / 3f3f46、"
    "前景三级 #ecedee / a1a1aa / 71717a、大圆角（按钮·输入 12/10，卡片·分组 14/16，菜单·对话框 14/16，"
    "chip 与进度条全圆 999px）、弱边框 + 色块分层；选中态由「实心暗色」改成「强调色柔光底 rgba(accent,0.22)」。"
    "**选择器是 v1 的超集**（v1 184 条全部保留，新增 4 条），所以不存在「某块样式被写丢」。"
    "② 三处 splitter handle（ActorSplitV / ActorSplitH / ImageSplitH）**原样保留** v1 的 "
    "`background: transparent; margin: 0px;` —— 把手本体是 `ui_actorcheck._GripHandle` 自绘的虚线 + 5 个圆点，"
    "QSS 一旦加底色/圆角就会把圆点盖掉；用户明确说「只保留这两条拖拽条」。"
    "③ 色板 12 色朱红系 → HeroUI 语义 **11 色**（默认 极光蓝 #006fee）；新增 `config.LEGACY_ACCENT_MAP` "
    "**幂等迁移**：老 settings.json 里的旧色值在「必须是色板之一」的归一闪**之前**先过映射，"
    "否则升级后会静默掉回默认蓝。`accent_shades()` 系数收窄（dark -0.120/+0.060、deep -0.070/+0.040、"
    "light +0.100/+0.060）。`_AccentSwatch` 从 30×24 扁平方形重做为 **28×28 正圆 + 选中白环 + 手绘白勾**。"
    "④ Python 里约 **350 处**硬编码旧色值一次性迁移（内联 setStyleSheet + QPainter 画笔，三轮脚本共 316+34+41 处），"
    "语义一一对应：主文字→ecedee、次文字→a1a1aa/d4d4d8、弱文字→71717a/52525b、深面板→0a0a0b/111113/18181b、"
    "更高一层→27272a/3f3f46、语义色→45d483(成功)/f5a524(警告)/f87171(危险)。`config.py` 例外（迁移表的键就是旧值）、"
    "`version.py` 例外（历史注释保留原色值，否则注释会自相矛盾）。"
    "同时把 `veil.default_backdrop()` 的「墨黑 + 朱红/鎏金四团暖光」改成「#0a0a0b + 跟随高亮色的两团低透明柔光 + "
    "两团中性提亮」；A-Z 字母条与开关轨道改为**懒读 `main_window.ACCENT_RGB`**（与 QSS 令牌同源）。"
    "一处刻意不改：全局按钮横向内边距**保持 v1 的 14px**（HeroUI 官网 16px）—— 按钮 sizeHint 宽度直接决定紧凑行"
    "最小宽，改 16px 会让全站按钮各宽 4px、「评分」对话框从 240 顶到 250。"
    "验证：冒烟 **417/417**（v1.46.15 是 377，新增 ㉗ 段 40 条：11 色色板、ACCENT_DEFAULT、迁移表幂等且目标全在色板内、"
    "**真造老配置跑 load() 验迁移生效**、四档派生亮度单调、QSS 无残留令牌/无旧墨金、三处 handle 仍 transparent、"
    "把手类仍在、色卡 28×28 与 R_DOT_ON<R_DOT<R_RING、开关_OFF/_ON、src 无旧色残留、veil/letter 取到当前高亮色）；"
    "`dev/test_v119_logic.py` ALL PASS。真机 exe 验收 **25/25**：老配置 #c0392b 载入即迁成 #f31260；"
    "按导航**高亮行反查**确认「个性化设置」真切过去了（不再「点完就当成了」）；真点「翡翠」色卡 → "
    "settings.json 变 #17c964 → 2.2s 后重抓图，开关轨道实测 mean=(27,198,101)，**界面确实重绘**；"
    "换色走 `_apply_settings()`（会重建侧栏，v1.27.0 崩过的路径）后进程存活；连切三页不崩；关窗 rc=0；"
    "app.log 8 行零未捕获异常、零 QThread 销毁警告。"
    "预览图：`docs/preview/v200_components_compare.png`（同一套控件 左 v1 / 右 v2）、"
    "`v200_swatches_compare.png`（色卡 v1 方形 vs v2 正圆）、`v200_main.png`、`v200_settings_appearance.png`、"
    "`v200_actorcheck.png`、`v200_grip_band.png`（拖拽条放大，证明没被 QSS 盖掉）；"
    "真机图：`dev/screenshots/v200_exe_main.png` / `v200_exe_appearance.png` / `v200_exe_accent_jade.png` / "
    "`v200_exe_service.png`。"
    "★ **两条回退路径**（都在仓库里，不需要重写代码）："
    "A. 只回退样式 —— `docs/legacy/style_v1_46_15.qss` 覆盖回 `src/style.qss` + "
    "按 `docs/legacy/accent_v1_46_15.txt` 把 12 色色板与四档派生系数粘回 `src/config.py`"
    "（该文件里还写了旧默认色 #c0392b 与三步操作）；"
    "B. 整个版本回退 —— 直接跑 `history/流明盒-v1.46.15-2610290118.exe`（v1 的最后一版 = 本次大改的回滚基线），"
    "或从 `history/流明盒-v1.46.15-2610290118-源码.zip` 重新 `build_exe.py`。"
    "本版改动集中在**表现层**：`src/style.qss`（重写）、`src/config.py`（色板 + 迁移 + 派生系数）、"
    "`src/ui_settings.py`（色卡 + 开关轨道 + 少量内联色）、`src/veil.py`（兜底底衬）、`src/letter_index.py`（字母条配色）、"
    "以及其余模块的内联色值；**没有碰** 扫描、播放、刮削、数据库、卡片的布局与尺寸。"
)

sys.argv = ["archive_version.py", "--note", NOTE_TEXT]
runpy.run_path(os.path.join(ROOT, "dev/_scratch/archive_version.py"), run_name="__main__")

# ---------------- 回滚可执行性校验 ----------------
FAILS = []


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def check(label, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + label + (("  -> " + str(detail)) if detail else ""))
    if not cond:
        FAILS.append(label)


check("工作副本 exe 存在", os.path.exists(EXE), EXE)
check("留档副本 exe 存在", os.path.exists(EXE_H), EXE_H)
if os.path.exists(EXE) and os.path.exists(EXE_H):
    a, b = sha(EXE), sha(EXE_H)
    check("根目录 exe 与 history/ 副本逐字节一致（同一 SHA-256）", a == b, a[:16])
    print("  exe SHA-256:", a)
check("源码 zip 存在且非空", os.path.exists(ZIP) and os.path.getsize(ZIP) > 1 << 20,
      "%.1f MB" % (os.path.getsize(ZIP) / 1048576) if os.path.exists(ZIP) else "缺失")
if os.path.exists(ZIP):
    with zipfile.ZipFile(ZIP) as zf:
        names = zf.namelist()
    tops = {n.split("/")[0] for n in names}
    check("zip 顶层目录 = %s" % STEM, tops == {STEM}, str(sorted(tops)))
    check("zip 内含 src/version.py", any(n.endswith("src/version.py") for n in names),
          "%d 个文件" % len(names))
    check("zip 内含 src/style.qss（新组件套件本体）",
          any(n.endswith("src/style.qss") for n in names))
    check("zip 内含 docs/legacy/ 的 v1 样式留档（回退路径 A 的载体）",
          any("docs/legacy/style_v1_46_15.qss" in n for n in names))
check("封存说明已写", os.path.exists(NOTE), NOTE)
if os.path.exists(NOTE):
    txt = open(NOTE, encoding="utf-8").read()
    check("封存说明含 SHA-256", "SHA-256" in txt)
    check("封存说明含「回退」", "回退" in txt)
    check("封存说明写了路径 A（docs/legacy）", "docs/legacy/style_v1_46_15.qss" in txt)
    check("封存说明写了路径 B（v1.46.15 的 exe）", "流明盒-v1.46.15-2610290118.exe" in txt)

check("docs/legacy/style_v1_46_15.qss 存在且非空",
      os.path.exists(LEGACY_QSS) and os.path.getsize(LEGACY_QSS) > 20000,
      os.path.getsize(LEGACY_QSS) if os.path.exists(LEGACY_QSS) else "缺失")
check("docs/legacy/accent_v1_46_15.txt 存在且含 12 色原文",
      os.path.exists(LEGACY_ACC) and "#c0392b" in open(LEGACY_ACC, encoding="utf-8").read(),
      os.path.getsize(LEGACY_ACC) if os.path.exists(LEGACY_ACC) else "缺失")
check("v1.46.15 的 exe 仍在 history/（回退路径 B 的载体）",
      os.path.exists(os.path.join(HIST, "流明盒-v1.46.15-2610290118.exe")))

print("ARCHIVE_V200_ALL_OK" if not FAILS else "ARCHIVE_V200_HAS_FAIL")
if FAILS:
    print("失败项:", FAILS)
