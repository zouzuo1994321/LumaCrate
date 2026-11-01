# -*- coding: utf-8 -*-
"""v2.0.6（Build 2611010127）封存：给 archive_version.py 传本版摘要，并做「产物自洽」校验。

本版四条反馈（用户附 5 张截图）：
  ① 详细页评分配色 —— 没评过金色「评分」，评过了橙色加粗「用户评分 7.5」；
  ② 重复检测结果支持打开影片 / 打开影片路径 / 打开影片文件夹路径 + 删除影片文件 /
     删除影片文件夹，且**删前确认是否删源文件**；
  ③ 演职人员旁加「＋」/ 删，可增删本片的演员与导演；
  ④ 删除统一改成「芯片 / 头像右上角的 ×」。

封存额外断言：
  ① 根目录 exe 与 history/ 副本**逐字节一致**；
  ② zip 里有本版关键载体：`ui_hero.py`（评分配色 / ＋ / ×）、`ui_settings.py`
     （DupDeleteDialog、两条删除入口、就地重填树）、`duplicates.py`（回收站删除）、
     `style.qss`（Ghost 禁用态）、`dev/_scratch/live_v206b_exe.py`（本版真机脚本）；
  ③ zip 带上本版预览图 `docs/preview/v206_*.png` 与真机图 `v206b_*`；
  ④ 封存说明里四条反馈的关键词都在；
  ⑤ **语义顺序**没被写反：先「回收站删源文件」再「移索引」（否则会出现
     「索引没了、文件还在」的错位）；删除全程不能出现 `os.remove` / `shutil.rmtree`。
"""
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
    "v2.0.6 四条反馈（用户附 5 张截图）。"
    "**第 1 条 —— 详细页评分改配色**。原话：「详细页 评分改为金色。用用户评分的则改为 橙色加粗的用户评分」。"
    "做法：评分按钮的**文案 + 颜色**收进 `HeroView._rate_style()` 一处，"
    "没评过 → 文字金色（`RATE_GOLD = \"#f5a524\"`，与收藏标题同一个黄）；评过了 → "
    "「用户评分 7.5」橙色加粗（`RATE_USER = \"#ff8c3a\"`，`font-weight:bold`）—— 一眼分清「这是我打的」"
    "与「还没打分」。只 inline 覆盖 `color` / `font-weight`，按钮底色与鎏金描边仍走 QSS 的 `#HeroAct`"
    "（整条 QSS 写进去会把描边一起冲掉）；打完分直接调它重算，**不重建页面**。"
    "**第 2 条 —— 重复检测结果可打开 / 可删除**。原话：「重复影片的检查结果支持，打开影片和打开影片路径和"
    "打开影片文件夹路径，然后可以选择删除影片文件和删除影片文件夹的功能，但是删除前需要确认是否删除源文件。」"
    "做法：**两条入口做同一件事** —— 结果树的右键菜单（打开影片（播放）/ 打开影片路径（在资源管理器中定位）/ "
    "打开影片文件夹路径 / 删除影片文件… / 删除影片文件夹…）与树下方那排按钮（播放 / 定位文件 / 打开文件夹 / "
    "删除…），没选中行时四枚按钮全灰。删除走 `DupDeleteDialog`：一个勾选框问清「同时删除源文件（移入回收站）」，"
    "默认勾选，框里列出即将处理的**完整路径**与后果提示；不勾 = 只从媒体库移除索引、磁盘一个字节都不动"
    "（勾选状态就是 `DupDeleteDialog.delete_source`，默认 True，取消勾选后写 False）。"
    "源文件一律走**回收站**（`duplicates.recycle_paths` → `SHFileOperationW` + `FOF_ALLOWUNDO`），"
    "不用 `os.remove` / `shutil.rmtree`：一次可能连删几十项，误删的代价是一整部片子；`pFrom` 必须是"
    "「双 NUL 结尾」的路径串，逐个删才能精确定位失败项；再叠 `FOF_WANTNUKEWARNING` 保底（万一回收站不可用，"
    "系统先警告再毁，绝不静默永久删）。**删失败就整件事不做**（索引也不动），绝不留「索引没了、文件还在」的错位。"
    "删完 `_dd_removed` 记住本次删掉的路径 → 组行按**剩下的成员**重算份数 / 体积 / 目录，只剩一个目录的组"
    "不再列出（它已经不是「跨目录重复」），原始检测结论仍可导出。"
    "**第 3 条 —— 演职人员可增删**。原话：「演职员信息 和标签一样旁边加上 + 和 - 的按钮，可以添加/删除该影片的"
    "演员和导演」。做法：「＋」复用演员 / 导演库联想框（`PersonSearchDialog`，标题换成「添加演职人员」），"
    "点选即把该人**加进本片**、已在片里的人不会重复加；删除走 `db.unlink_media_person()` —— 只解除这一部作品"
    "的关联，人物本身仍留在演员库里、别的作品照样看得到。增删都会**回写该片的 nfo**"
    "（`nfo_parser.write_people` 写 `<actor>` / `<director>`）：`scanner._link_actors()` 每次扫描都先 "
    "`clear_media_people()` 再按 nfo 重建，不回写就会被下一次扫描整批抹掉。"
    "**第 4 条 —— 删除统一成右上角的「×」**。原话：「删除的话 都该为 标签和演员右上角出现一个 X 来删除」。"
    "做法：`CastAvatar` 构造时若给了 `on_remove`，就在头像**内部**放一枚 18×18 的「×」绝对定位到右上角"
    "（`_place_remove()`；不能用布局，否则会占掉一行、把整排头像顶高）；标签芯片同样在右上角放 16×16 的「×」。"
    "于是标签行与演职人员行都只剩一个「＋」，「清空全部标签」挪进芯片的右键菜单。"
    "**顺带修掉一个真缺陷（真机前探针量出来的）**：`style.qss` 缺 `QPushButton#Ghost:disabled` —— "
    "`QPushButton#Ghost`（ID，权重 0,1,0,1）压过通用的 `QPushButton:disabled`（0,0,1,1），于是重复检测结果树"
    "下那四枚按钮的**禁用态文字仍按 #d4d4d8 画**（实测最亮 211，与 enabled 一模一样）：看着能点、其实点不动。"
    "补上同 ID + 伪类那条后实测 211 → 84。"
    "验证：冒烟 **651/651**（v2.0.5 是 584，新增 ㉛ 段 63 条覆盖重复检测打开 / 删除 / 就地重填树，"
    "㉜ 段 4 条覆盖 Ghost 禁用态；㉛ 段的重复组改成**按路径认领**自己那组 —— 冒烟库里本就还有一组"
    "同大小的重复文件，按 `groups[0]` 取会删错对象）；"
    "真机 exe **28/28**：两态评分配色量暖色像素（金 197 / 中位 g/r 0.673、橙 494 / 0.549）、"
    "演职员 ×（media_people 3→2）、标签 ×（标签甲,标签乙 → 标签乙）、四枚按钮初始全灰 85 / 选中 213、"
    "结果进树、侧栏实色、关窗 rc=0、app.log 零未捕获异常；删除链路**从进程外读库 + 看磁盘**取证："
    "两份副本只剩一份（另一份进了回收站）、索引也只剩 1 条。"
    "预览图：`docs/preview/v206_detail.png`（详细页评分配色两态）、`v206_zoom_x.png`（头像 / 标签右上角的 × 放大）、"
    "`v206_dup_actions.png`（重复检测结果的菜单与四枚按钮）。"
    "真机图：`dev/screenshots/v206b_exe_rate_gold.png` / `v206b_exe_rate_orange.png` / "
    "`v206b_exe_cast_after_x.png` / `v206b_exe_tag_after_x.png` / `v206b_exe_dedupe_result.png` / "
    "`v206b_exe_dup_confirm.png` / `v206b_exe_dedupe_after_del.png`。"
    "**回退**：整版回退 `history/流明盒-v2.0.5-2611010126.exe`（或从其源码 zip 重打）。"
    "本版**没有碰** 卡片尺寸与列数、按钮几何、扫描逻辑、主题色板与数据库表结构"
    "（只用了既有的 `media_people` / `people` 关联，表结构未改）。"
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
    print("  exe 字节数:", os.path.getsize(EXE))

check("源码 zip 存在且非空", os.path.exists(ZIP) and os.path.getsize(ZIP) > 1 << 20,
      "%.1f MB" % (os.path.getsize(ZIP) / 1048576) if os.path.exists(ZIP) else "缺失")
if os.path.exists(ZIP):
    with zipfile.ZipFile(ZIP) as zf:
        names = zf.namelist()

        def rd(rel):
            return zf.read(STEM + "/" + rel).decode("utf-8", "replace")

        hero = rd("src/ui_hero.py")
        sett = rd("src/ui_settings.py")
        dup = rd("src/duplicates.py")
        qss = rd("src/style.qss")
        main = rd("src/main_window.py")

    tops = {n.split("/")[0] for n in names}
    check("zip 顶层目录 = %s" % STEM, tops == {STEM}, str(sorted(tops)))
    check("zip 内含 src/version.py（版本号真源）",
          any(n.endswith("src/version.py") for n in names), "%d 个文件" % len(names))
    check("zip 内含 dev/_scratch/live_v206b_exe.py（本版真机验收脚本）",
          any(n.endswith("dev/_scratch/live_v206b_exe.py") for n in names))
    check("zip 内含 dev/_scratch/archive_v206.py（本封存脚本）",
          any(n.endswith("dev/_scratch/archive_v206.py") for n in names))
    _prev = [n for n in names if "/docs/preview/v206_" in n]
    check("zip 带本版预览图 docs/preview/v206_*.png（≥2）", len(_prev) >= 2,
          [n.split("/")[-1] for n in _prev])
    _shots = [n for n in names if "/dev/screenshots/" in n and "v206b_" in n]
    check("zip 带本版真机图（v206b_*，≥4）", len(_shots) >= 4,
          "%d 张：%s" % (len(_shots), [n.split("/")[-1] for n in _shots][:4]))

    # ① 评分配色
    check("评分金色真源 RATE_GOLD = #f5a524", 'RATE_GOLD = "#f5a524"' in hero)
    check("用户评分橙色 RATE_USER = #ff8c3a", 'RATE_USER = "#ff8c3a"' in hero)
    check("文案 + 颜色收在一处（_rate_style）", "def _rate_style" in hero)
    check("用户评分加粗（font-weight:bold 与 RATE_USER 同处）",
          "font-weight:bold" in hero and "RATE_USER" in hero)

    # ② 重复检测：打开 / 删除 / 确认
    check("确认框类 DupDeleteDialog 存在", "class DupDeleteDialog" in sett)
    check("确认框有「删除源文件」勾选项",
          "同时删除源文件" in sett and "delete_source" in sett)
    check("右键菜单五项齐全",
          all(k in sett for k in ("打开影片（播放）", "打开影片路径（在资源管理器中定位）",
                                  "打开影片文件夹路径", "删除影片文件…", "删除影片文件夹…")))
    check("树下四枚按钮入口（播放 / 定位文件 / 打开文件夹 / 删除）",
          all(k in sett for k in ("dd_play", "dd_reveal", "dd_open_dir", "dd_del")))
    check("删除走回收站（duplicates.recycle_paths）",
          "def recycle_paths" in dup and "recycle_paths" in sett)
    check("回收站标志 FOF_ALLOWUNDO + FOF_WANTNUKEWARNING",
          "_FOF_ALLOWUNDO" in dup and "_FOF_WANTNUKEWARNING" in dup)
    check("pFrom 是双 NUL 结尾的路径串", '"\\x00\\x00"' in dup)
    check("recycle_paths 里没有 os.remove( / shutil.rmtree( 调用（注释里提到不算）",
          "os.remove(" not in dup.split("def recycle_paths")[1].split("__all__")[0]
          and "shutil.rmtree(" not in dup.split("def recycle_paths")[1].split("__all__")[0])
    check("**先删源文件、再从索引移除**（顺序不能反）",
          sett.index("if dlg.delete_source:") < sett.index("db.delete_media(mid)"))
    check("删失败就整件事不做（failed 分支 return）",
          'res.get("failed")' in sett and "本次没有做任何改动" in sett)
    check("删完就地重填结果树（_dd_removed）",
          "_dd_removed" in sett and "_fill_dedupe_tree" in sett)

    # ③ 演职人员 ＋ / 删除
    check("演职人员「＋」入口（_add_person）", "def _add_person" in hero)
    check("加人复用 PersonSearchDialog", "PersonSearchDialog" in hero)
    check("只解关联不断人（unlink_media_person）", "unlink_media_person" in hero)
    check("增删回写 nfo（write_people）", "write_people" in hero)

    # ④ × 删除
    check("标签芯片有「×」按钮", 'QPushButton("×")' in hero)
    check("头像内部放 ×（绝对定位 _place_remove）",
          "def _place_remove" in hero and "setFixedSize(18, 18)" in hero)

    # 顺带修的缺陷
    check("style.qss 补了 QPushButton#Ghost:disabled（CSS 权重那条）",
          "QPushButton#Ghost:disabled" in qss)
    check("主窗没被本版改动波及（卡片尺寸仍按类属性）",
          "ACTOR_CARD_W" in main)

check("封存说明已写", os.path.exists(NOTE), os.path.basename(NOTE))
if os.path.exists(NOTE):
    txt = open(NOTE, encoding="utf-8").read()
    for kw in ("SHA-256", "回退", "RATE_GOLD", "#f5a524", "#ff8c3a", "加粗",
               "回收站", "FOF_ALLOWUNDO", "双 NUL", "DupDeleteDialog", "delete_source",
               "索引没了、文件还在", "unlink_media_person", "write_people",
               "18×18", "651/651", "28/28", "Ghost:disabled"):
        check("封存说明含关键词 %r" % kw, kw in txt)
    check("封存说明写了回退基线 v2.0.5(0126) 的 exe",
          "流明盒-v2.0.5-2611010126.exe" in txt)
check("回退基线 v2.0.5(0126) 的 exe 仍在 history/",
      os.path.exists(os.path.join(HIST, "流明盒-v2.0.5-2611010126.exe")))

print()
if FAILS:
    print("ARCHIVE_V206_FAIL:", FAILS)
else:
    print("ARCHIVE_V206_ALL_OK")
