# -*- coding: utf-8 -*-
"""v2.0.4 封存：给 archive_version.py 传本版摘要，并额外做「产物自洽」校验。

本版是配色逻辑的纠正（默认灰 / 收藏才高亮 / 置顶加粗），改动集中在
`main_window._crew_names_html` 与 `ui_hero.CastAvatar`，封存额外断言：
  ① 根目录 exe 与 history/ 副本**逐字节一致**；
  ② zip 里有本版三个关键载体：`src/main_window.py`（三档语义）、`src/ui_hero.py`（身份色真源）、
     `dev/_scratch/live_v204_exe.py`；
  ③ zip 带上了本版预览图 `docs/preview/v204_*.png` 与真机图 `dev/screenshots/v204_*.png`；
  ④ 封存说明里 9 条反馈的关键词都在；
  ⑤ 代码里没有「未收藏也上色」或「下划线」的残留。
"""
import hashlib
import os
import re
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
    "第 9 条反馈（用户看了 0123 的卡片截图后纠正配色逻辑，原话：「卡片的颜色逻辑不太对："
    "① 默认就是这个灰色 ② 如果收藏 则高亮 女演员粉色，男演员蓝色，导演黄色 ③ 如果置顶 则字体加粗」）。"
    "上一版把身份色铺成了**常驻色**（未收藏也彩色），用户的真实意图是把它当成「收藏」这个状态的奖励色。"
    "改法（`main_window._crew_names_html`）：三档语义互不重叠 ——"
    "**未收藏（默认）= 弱化灰 `#a1a1aa`**（新增常量 `_CREW_NAME_DIM`，与卡片上「演员：」/「导演：」"
    "标签同色，冒烟有「与 PosterCard 内联灰一致」的断言）；"
    "**收藏 = 身份色**（`ui_hero.crew_name_color`：女 `#e4587c` / 男 `#338ef7` / 导演 `#f5a524` / "
    "未知 `#fafafa`，导演优先于性别）；**置顶 = 仅加粗、不换颜色**；收藏 + 置顶 = 彩色 + 加粗。"
    "同时删掉 v2.0.3 里我自己发明的「收藏 = 加粗 + 下划线」——用户没要下划线，而且它会与"
    "「置顶 = 加粗」抢同一个通道（`CastAvatar` 里的 `QFont.setUnderline` 一并删掉）。"
    "详情页那排演职人员**保持身份常驻色**（看人的地方按身份区分才有意义，与卡片规则不同），"
    "收藏 / 置顶统一走加粗。"
    "验证：冒烟 **542/542**（v2.0.3 是 534，本版补 8 条：默认三名字全灰且不加粗、收藏后三色齐现"
    "且灰色一个不剩、未收藏的导演不预先上色、置顶只加粗仍灰、收藏+置顶彩+粗、下划线彻底消失、"
    "`_CREW_NAME_DIM` 与 PosterCard 内联灰一致、详情页收藏态无下划线）；"
    "`dev/test_v119_logic.py` ALL PASS。真机 exe **30/30**（v2.0.2 六条全量复验，零回退："
    "色卡新粉 110 像素 / 无旧粉、「100%」96 个中性白、「最近播放」页 20px 大标题 1051 粉像素 + "
    "零蓝像素、点翡翠后不重新导航直接抓图变 1244 绿像素、glyphs 三张 PNG 落盘、连切三页不崩、"
    "关窗 rc=0、app.log 零未捕获异常）。"
    "预览图：`docs/preview/v204_crew_states.png`（四张卡并排：默认 / 收藏 / 置顶 / 收藏+置顶）。"
    "**回退**：整版回退 `history/流明盒-v2.0.3-2610290123.exe`（或从其源码 zip 重打）。"
    "本版**没有碰** 扫描、播放、刮削、数据库结构、卡片尺寸与列数、按钮几何。"
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
        main = zf.read(STEM + "/src/main_window.py").decode("utf-8")
        hero = zf.read(STEM + "/src/ui_hero.py").decode("utf-8")
    tops = {n.split("/")[0] for n in names}
    check("zip 顶层目录 = %s" % STEM, tops == {STEM}, str(sorted(tops)))
    check("zip 内含 src/version.py（版本号真源）",
          any(n.endswith("src/version.py") for n in names), "%d 个文件" % len(names))
    check("zip 内含 dev/_scratch/live_v204_exe.py（本版真机验收脚本）",
          any(n.endswith("dev/_scratch/live_v204_exe.py") for n in names))
    check("zip 带本版预览图 docs/preview/v204_*.png",
          len([n for n in names if "/docs/preview/v204_" in n]) >= 1,
          len([n for n in names if "/docs/preview/v204_" in n]))
    check("zip 带本版真机图 dev/screenshots/v204_*.png",
          len([n for n in names if "/dev/screenshots/v204_" in n]) >= 1,
          len([n for n in names if "/dev/screenshots/v204_" in n]))

    # 三档语义的源码痕迹
    check("存在默认灰常量 _CREW_NAME_DIM = #a1a1aa",
          re.search(r'_CREW_NAME_DIM = "#a1a1aa"', main) is not None)
    _seg = main[main.find("def _crew_names_html"):main.find("def _build_crew_lines")]
    check("名字颜色按 fav 分支（未收藏走灰色常量）",
          "_CREW_NAME_DIM" in _seg and "if fav" in _seg)
    check("置顶走加粗、颜色不参与", "if pin:" in _seg and "font-weight:bold" in _seg)
    check("卡片小字里没有下划线残留", "underline" not in _seg)
    check("详情页 CastAvatar 不再 setUnderline", "setUnderline" not in hero)
    check("身份色真源仍在（crew_name_color / is_director_role）",
          "def crew_name_color" in hero and "def is_director_role" in hero)

check("封存说明已写", os.path.exists(NOTE), os.path.basename(NOTE))
if os.path.exists(NOTE):
    txt = open(NOTE, encoding="utf-8").read()
    for kw in ("SHA-256", "回退", "_CREW_NAME_DIM", "#a1a1aa", "#e4587c",
               "置顶", "下划线", "542/542"):
        check("封存说明含关键词 %r" % kw, kw in txt)
    check("封存说明写了回退基线 v2.0.3 的 exe",
          "流明盒-v2.0.3-2610290123.exe" in txt)
check("回退基线 v2.0.3 的 exe 仍在 history/",
      os.path.exists(os.path.join(HIST, "流明盒-v2.0.3-2610290123.exe")))

print("ARCHIVE_V204_ALL_OK" if not FAILS else "ARCHIVE_V204_HAS_FAIL")
if FAILS:
    print("失败项:", FAILS)
