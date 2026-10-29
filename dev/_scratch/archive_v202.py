# -*- coding: utf-8 -*-
"""v2.0.2 封存：给 archive_version.py 传本版摘要，并额外做「产物自洽」校验。

本版（Build 2610290121）是 v2.0.0 换肤后的第二批真机反馈，全部落在**表现层 + 一条查询**，
所以封存额外断言：
  ① 根目录 exe 与 history/ 副本**逐字节一致**；
  ② 源码 zip 里有本版三个关键载体：`src/glyphs.py`（箭头/对勾 PNG）、
     `src/style.qss`（`#CardPlay` 已无背景声明）、`dev/_scratch/live_v202_exe.py`（真机验收脚本本身）；
  ③ zip 带上了本版预览图 `dev/screenshots/v202_*.png`；
  ④ 封存说明里 6 条反馈的**关键词**都在，防止「说明写漏一条」。
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

NOTE_TEXT = (
    "v2.0.0 换肤上线后的第二批真机反馈（用户附 10 张截图，共 6 条）。"
    "① **卡片右下「播放」改成圆形，与左下「收藏」大小一致，两钮都加阴影、整体强化显示**："
    "原先播放钮是 36×36 圆角方块（QSS `QPushButton#CardPlay` 给 border-radius），星标是 30×30 —— 一大一小、一方一圆。"
    "本版新增公共基类 `_CardRoundButton(QPushButton)`，`_PlayGlyphButton` / `_FavStarButton` 都继承它并只实现 `paint_glyph()`；"
    "**控件 34×34 = 圆本体 28 + 阴影环 3×2**，两钮都 34×34、一左一右、底边齐平（`_BTN_INSET=2`，圆离海报边 5px）。"
    "阴影**不用 `QGraphicsDropShadowEffect`** —— 每卡两个 effect，一屏 40+ 张卡就是 80+ 个离屏合成，滑动会掉帧；"
    "改成「由外向内递减 alpha 的同心圆」手绘（3 圈，a = 120×(1-(i-1)/3)²），再叠 1.3px 半透明白描边提亮边缘。"
    "悬停时圆底变当前高亮色（`ACCENT_RGB`，alpha 235），未悬停是 `rgba(12,12,14,176)`。"
    "⚠ QSS 里**刻意删掉** `#CardPlay` 的 background / border-radius / hover —— 自绘 `paintEvent` 不调 `super()` 时"
    "QSS 背景画不出来，留着只会双描边。"
    "② **色板粉色换值** `#ff7fa1` → `#e4587c`（用户指定的「更沉一档的粉」）；同步三处：色板、"
    "`config.LEGACY_ACCENT_MAP`（**没有这条迁移，v2.0.1 里选过粉色的用户升级后会静默掉回默认蓝**）、"
    "`ui_hero.GLOW_FEMALE`（女艺人头像流光）。"
    "③ **评分框恢复上下微调按钮**：v1.46.14 曾因「QSS 给了背景后 Qt 不再画原生箭头」而改成 `NoButtons`；"
    "v2.0.1 起箭头走 `src/glyphs.py` 的 PNG `image:`，真机可见 → 恢复 `UpDownArrows` 并给"
    "`setMinimumWidth(cfg.SPIN_MIN_W)`，避免「10.0 分」被箭头挤断。"
    "④ **搜索加上「标签」**：`database._media_where` 的 keyword 子句由 `title OR plot` 扩成 "
    "`title OR plot OR IFNULL(tags,'')`（`_media_where` 被 `search_media` / `count_media` 共用，"
    "口径自动一致）；搜索框占位语与 19 个语言块同步改词。"
    "⑤ **顶部标题跟主题色走**：`_h1()` 原先内联 `setStyleSheet('color:#66a9ff')` —— 只有重建页面才变色，"
    "改高亮色后仍是蓝的。改成 `setObjectName('PageTitle')` + QSS 令牌 `color: __ACCENT__`，`render_style()` 一重载立刻生效；"
    "同时补 `#PanelTitle` / `#PanelTitleSm`（工具窗各页小标题）两个选择器。"
    "⑥ **两处文字改白**：设置页「窗口透明度 100%」的值（`#PlainValue`）与手动修改页「检索并选择影片」"
    "（`#PlainTitle`）由写死的 `#66a9ff` 改成中性白 `#fafafa`。"
    "验证：冒烟 **504/504**（新增 ㉙ 段 49 条：常量/同基类/QSS 无 #CardPlay/两钮 34×34 等大·左右对称·底边齐平/"
    "**按钮自身 grab** 判角上透明·45° 实心·圆半径 13·圆下方有黑影/悬停底色 = #e4587c/已收藏金色星；"
    "粉色换值 + 迁移表 + **真造老配置跑 load()**；`RateDialog` 恢复 `UpDownArrows` + grab 出上下各 ≥8 个箭头亮像素；"
    "tags 搜索能搜到·count 同口径·标题简介没搜坏·不存在的词 0 条；三个标题 objectName 换翡翠就变绿）；"
    "`dev/test_v119_logic.py` ALL PASS。真机 exe **30/30**：色卡出现新粉 / 无旧粉、「100%」与「检索并选择影片」"
    "是中性白、「最近播放」页 20px 大标题 1051 个粉像素且**零蓝像素**（修前写死 #66a9ff）、"
    "点「翡翠」后**不重新导航**直接抓主窗该标题变 1244 个绿像素（证明令牌重载即时生效）、"
    "glyphs 三张 PNG 落盘、连切三页不崩、关窗 rc=0、app.log 零未捕获异常。"
    "预览图：`docs/preview/v202_card_buttons.png` / `v202_card_buttons_zoom.png`（2× 放大看阴影）/ "
    "`v202_rate_dialog.png` / `v202_titles.png`；真机图：`dev/screenshots/v202_exe_home_pink.png` / "
    "`v202_exe_title_pink.png`。"
    "**回退**：整个版本回退直接跑 `history/流明盒-v2.0.1-2610290120.exe`，"
    "或从 `history/流明盒-v2.0.1-2610290120-源码.zip` 重新 `build_exe.py`。"
    "本版**没有碰** 扫描、播放、刮削、数据库结构、卡片尺寸与列数。"
)

sys.argv = ["archive_version.py", "--note", NOTE_TEXT]
runpy.run_path(os.path.join(ROOT, "dev/_scratch/archive_version.py"), run_name="__main__")

# ---------------- 产物自洽校验 ----------------
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


check("工作副本 exe 存在", os.path.exists(EXE), STEM + ".exe")
check("留档副本 exe 存在", os.path.exists(EXE_H), "history/" + STEM + ".exe")
if os.path.exists(EXE) and os.path.exists(EXE_H):
    a, b = sha(EXE), sha(EXE_H)
    check("根目录 exe 与 history/ 副本逐字节一致（同一 SHA-256）", a == b, a[:16])
    print("  exe SHA-256:", a)

check("源码 zip 存在且非空", os.path.exists(ZIP) and os.path.getsize(ZIP) > 1 << 20,
      "%.1f MB" % (os.path.getsize(ZIP) / 1048576) if os.path.exists(ZIP) else "缺失")
if os.path.exists(ZIP):
    with zipfile.ZipFile(ZIP) as zf:
        names = zf.namelist()
        qss = zf.read(STEM + "/src/style.qss").decode("utf-8")
    tops = {n.split("/")[0] for n in names}
    check("zip 顶层目录 = %s" % STEM, tops == {STEM}, str(sorted(tops)))
    check("zip 内含 src/version.py（版本号真源）",
          any(n.endswith("src/version.py") for n in names), "%d 个文件" % len(names))
    check("zip 内含 src/glyphs.py（箭头/对勾 PNG 生成器）",
          any(n.endswith("src/glyphs.py") for n in names))
    check("zip 内含 dev/_scratch/live_v202_exe.py（本版真机验收脚本）",
          any(n.endswith("dev/_scratch/live_v202_exe.py") for n in names))
    check("zip 带本版预览图 dev/screenshots/v202_*.png",
          len([n for n in names if "/dev/screenshots/v202_" in n]) >= 2,
          len([n for n in names if "/dev/screenshots/v202_" in n]))
    # ① 的硬约束：QSS 里连 #CardPlay 选择器都不该再有（否则自绘 + QSS 双描边）。
    # ⚠ 必须先剥掉 /* */ 注释再查 —— 那条规则的位置留着一段说明，里面满是这两个词。
    import re as _re
    bare = _re.sub(r"/\*.*?\*/", "", qss, flags=_re.S)
    check("剥掉注释后 QSS 里已无 CardPlay 选择器（全自绘，无 QSS 背景）",
          "CardPlay" not in bare and "CardStar" not in bare,
          "注释里仍有 %d 处提及（说明用，允许）" % qss.count("CardPlay"))
    check("QSS 有 #PageTitle 且走 __ACCENT__ 令牌（反馈 5 的载体）",
          "QLabel#PageTitle" in qss and "color: __ACCENT__" in qss)
    check("QSS 有 #PlainTitle / #PlainValue 且是中性白",
          "QLabel#PlainTitle" in qss and "#fafafa" in qss)

check("封存说明已写", os.path.exists(NOTE), os.path.basename(NOTE))
if os.path.exists(NOTE):
    txt = open(NOTE, encoding="utf-8").read()
    for kw in ("SHA-256", "回退", "_CardRoundButton", "#e4587c", "UpDownArrows",
               "IFNULL(tags", "PageTitle", "#fafafa"):
        check("封存说明含关键词 %r" % kw, kw in txt)
    check("封存说明写了回退基线 v2.0.1 的 exe",
          "流明盒-v2.0.1-2610290120.exe" in txt)
check("回退基线 v2.0.1 的 exe 仍在 history/",
      os.path.exists(os.path.join(HIST, "流明盒-v2.0.1-2610290120.exe")))

print("ARCHIVE_V202_ALL_OK" if not FAILS else "ARCHIVE_V202_HAS_FAIL")
if FAILS:
    print("失败项:", FAILS)
