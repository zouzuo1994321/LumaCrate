# -*- coding: utf-8 -*-
"""v2.0.3 封存：给 archive_version.py 传本版摘要，并额外做「产物自洽」校验。

本版两条反馈（① 收藏钮去掉圆底 ② 演职员名字按身份着色）都落在表现层 + 一处查询字段，
封存额外断言：
  ① 根目录 exe 与 history/ 副本**逐字节一致**；
  ② zip 里有本版三个关键载体：`src/ui_hero.py`（名字配色唯一真源）、
     `src/database.py`（cast_crew_map_ex 带 gender）、`dev/_scratch/live_v203_exe.py`；
  ③ zip 带上了本版预览图 `dev/screenshots/v203_*.png` 与 `docs/preview/v203_*.png`；
  ④ 封存说明里两条反馈的关键词都在；
  ⑤ 代码里**没有残留**「收藏 → 金色 #66a9ff」的旧写法（颜色已让位给身份）。
"""
import ctypes
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
    "v2.0.2 交付后追加的两条真机反馈（v2.0.3，同一天重打成 Build 2610290123）。"
    "① **「收藏外不需要圆形」**（用户附截图，红框圈的是卡片左下星标）：v2.0.2 把收藏钮也做成了"
    "「深色圆底 + 阴影」，用户看真机后要**只留星**。做法：基类 `_CardRoundButton` 加类属性 "
    "`HAS_CIRCLE`（播放钮 True / 收藏钮 False），`paintEvent` 在 False 时**不画**圆本体、圆阴影、"
    "圆描边；阴影改由子类**沿星形轮廓**描两层递减 alpha 的黑边（画成圆影等于又给了个圆底）。"
    "星顺势放大到 `r*0.80`（≈22px 见方，v2.0.2 内接只有 16px，去掉圆后按老尺寸会又小又空）。"
    "控件仍 34×34、位置常量与播放钮共用，「等大 / 底边齐平 / 左右对称」三条几何不变式照旧成立；"
    "悬停时未收藏的星描边换 `ACCENT_RGB`、已收藏的星提亮一档，两种状态都不许渗出圆底。"
    "② **「女演员的名字用粉色，男演员用蓝色，导演用黄色，未知为白色」**（追加一条："
    "「包括卡片内名字」）：色值是 女 `#e4587c` / 男 `#338ef7` / 导演 `#f5a524` / 未知 `#fafafa`。"
    "新增 `ui_hero.crew_name_color()` 与 `is_director_role()` 作为"
    "**唯一色源**（导演优先于性别，大小写/空格容错），卡片小字 `main_window._crew_names_html` "
    "与详情页演职人员 `CastAvatar` 都调它 → 两边永远同色。`db.cast_crew_map_ex` 的元组由 3 项"
    "扩到 4 项（多带 `p.gender`），消费方按 `len(t)` 兼容旧三元组；`cast_crew_map` 里写死的 "
    "`for n, _, _ in` 必须改成 `t[0]`，否则第 4 项没处放直接 ValueError。"
    "v1.37.0 的「收藏 → 金色」让位给身份配色（颜色已被占满），改走**非颜色**通道："
    "收藏 = 加粗 + 下划线、置顶 = 加粗。"
    "验证：冒烟 **534/534**（v2.0.2 是 504，本版新增 ㉙ 段 30 条：`HAS_CIRCLE` 两值、收藏钮"
    "不透明像素 < 播放钮 55%、圆内左/右/下三点基本透明、星形本体 ≥60 像素、沿轮廓柔影 "
    "25<alpha<140 ≥30 像素、悬停染色 ≥20 粉像素且仍无圆底；四色映射 + 大小写容错 + 卡片 HTML "
    "三色 span + 导演压性别 + 旧三元组兼容 + 收藏/置顶走字重与下划线 + `cast_crew_map_ex` 带 "
    "gender + 真建 `CastAvatar` 逐个核对名字颜色与下划线）；`dev/test_v119_logic.py` ALL PASS。"
    "真机 exe **30/30**（v2.0.2 的六条反馈全数复验：色卡新粉 110 像素 / 无旧粉、「100%」96 个中性白、"
    "「最近播放」页 20px 大标题 1051 粉像素 + **零蓝像素**、点翡翠后**不重新导航**直接抓图变 1244 绿像素、"
    "glyphs 三张 PNG 落盘、连切三页不崩、关窗 rc=0、app.log 零未捕获异常）。"
    "⚠ 真机验收的副本名改成 `LMC-probe-<build>.exe`：程序启动会 `_kill_other_instances()` 杀掉"
    "**同名**进程，用原版名字跑验收会把用户正在用的那份一起关掉（实测就撞上了，主窗抓图 0x0）。"
    "预览图：`docs/preview/v203_card_buttons.png`、`v203_card_buttons_zoom.png`、"
    "`v203_btn_strip.png`（4× 特写：播放 / 收藏 / 已收藏 / 收藏悬停）、"
    "`v203_crew_colors_cards.png`、`v203_crew_colors_cast.png`；"
    "真机图：`dev/screenshots/v203_exe_home_pink.png` / `v203_exe_title_pink.png` / "
    "`v203_exe_title_jade.png` / `v203_exe_appearance.png` / `v203_exe_manual_title.png`。"
    "**回退**：整版回退 `history/流明盒-v2.0.2-2610290121.exe`（或从其源码 zip 重打）。"
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
        hero = zf.read(STEM + "/src/ui_hero.py").decode("utf-8")
        main = zf.read(STEM + "/src/main_window.py").decode("utf-8")
        dbx = zf.read(STEM + "/src/database.py").decode("utf-8")
    tops = {n.split("/")[0] for n in names}
    check("zip 顶层目录 = %s" % STEM, tops == {STEM}, str(sorted(tops)))
    check("zip 内含 src/version.py（版本号真源）",
          any(n.endswith("src/version.py") for n in names), "%d 个文件" % len(names))
    check("zip 内含 dev/_scratch/live_v203_exe.py（本版真机验收脚本）",
          any(n.endswith("dev/_scratch/live_v203_exe.py") for n in names))
    check("zip 带本版真机图 dev/screenshots/v203_*.png",
          len([n for n in names if "/dev/screenshots/v203_" in n]) >= 2,
          len([n for n in names if "/dev/screenshots/v203_" in n]))
    check("zip 带本版预览图 docs/preview/v203_*.png",
          len([n for n in names if "/docs/preview/v203_" in n]) >= 3,
          len([n for n in names if "/docs/preview/v203_" in n]))

    # ① 收藏钮不再画圆
    check("ui_hero 有名字配色唯一真源 crew_name_color / is_director_role",
          "def crew_name_color" in hero and "def is_director_role" in hero)
    check("main_window 的收藏钮 HAS_CIRCLE = False",
          re.search(r"class _FavStarButton[\s\S]{0,1400}HAS_CIRCLE = False", main) is not None)
    check("main_window 的播放钮仍是圆（HAS_CIRCLE 默认 True）",
          "HAS_CIRCLE = True" in main)
    check("main_window 卡片小字已改用 crew_name_color 上色",
          "crew_name_color" in main and "is_director_role" in main)
    check("database 的 cast_crew_map_ex 查询带了 p.gender",
          "IFNULL(p.gender,'') AS gender" in dbx)
    # ⚠ 只查**非注释行**：database.py 里那段「写死 `for n, _, _ in` 会 ValueError」是说明文字，
    #   直接 `in dbx` 会被自己的注释判红（上一版就这么假红过）。
    _code_db = "\n".join(ln for ln in dbx.splitlines() if not ln.strip().startswith("#"))
    check("database 的 cast_crew_map 不再写死三元组解包",
          "t[0] for t in" in _code_db and "for n, _, _ in" not in _code_db)
    # ⑤ 旧的金色写法不再出现在这两处
    check("卡片小字里没有残留「收藏 → #66a9ff」",
          "#66a9ff" not in main[main.find("def _crew_names_html"):main.find("def _build_crew_lines")])
    check("详情页 CastAvatar 里没有残留「收藏 → #66a9ff」",
          "#66a9ff" not in hero[hero.find("class CastAvatar"):hero.find("class CastAvatar") + 4000])

check("封存说明已写", os.path.exists(NOTE), os.path.basename(NOTE))
if os.path.exists(NOTE):
    txt = open(NOTE, encoding="utf-8").read()
    for kw in ("SHA-256", "回退", "HAS_CIRCLE", "crew_name_color", "#e4587c",
               "#f5a524", "cast_crew_map_ex", "LMC-probe"):
        check("封存说明含关键词 %r" % kw, kw in txt)
    check("封存说明写了回退基线 v2.0.2 的 exe",
          "流明盒-v2.0.2-2610290121.exe" in txt)
check("回退基线 v2.0.2 的 exe 仍在 history/",
      os.path.exists(os.path.join(HIST, "流明盒-v2.0.2-2610290121.exe")))

print("ARCHIVE_V203_ALL_OK" if not FAILS else "ARCHIVE_V203_HAS_FAIL")
if FAILS:
    print("失败项:", FAILS)
