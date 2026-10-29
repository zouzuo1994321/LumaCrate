# -*- coding: utf-8 -*-
"""v1.46.15 封存：给 archive_version.py 传本版摘要，并额外做「回滚基线」校验。

用户明确说「下一个版本将对 UI 进行一次完整的迭代，做好回滚的准备」，
所以本版封存除了常规的「源码 zip + 封存说明 + SHA-256」，还额外断言：
  ① 工程根目录与 history/ 下的 exe **逐字节一致**（同一份 SHA-256）；
  ② 源码 zip 存在且能列出顶层目录（不是 0 字节坏包）；
  ③ 封存说明里写了 SHA-256 与「回滚基线」字样。
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
    "一条反馈（截图）：「**服务管理 → 已配置的媒体库**这块太高，把行距压紧」。"
    "根因不是 `LIB_ROW_H`(54) 一个人偏大，而是它与全局 `QListWidget::item{padding:5px 4px}` **叠加** —— "
    "`setSizeHint` 给 54，列表项自己再吃掉上下各 5px，真正交给 `setItemWidget` 的行控件只剩 44；"
    "而行内边距(4+4) + 28px 按钮只用到 36px，剩下 8px 被均分到上下 → 每行看着像「被拉开」。"
    "改法两处联动：① `LIB_ROW_H` 54→**44**、列表容器余量从写死的 `+10` 抽成常量 `LIST_CHROME=6`"
    "（空库分支也改用它，否则会多出一条空白）；② 该列表单独 `objectName=\"LibList\"`，QSS 加 "
    "`QListWidget#LibList::item{padding:2px 4px}` 只作用于它（命名作用域，不动全站；"
    "**只改 padding，绝不写 height/min-height**，否则会盖掉按条目数自适应的 `setFixedHeight`）。"
    "实测（离屏 1320×960，3 个库）3 行列表 **172 → 138**，每项 `visualRect` 高 54 → 44、行控件 44 → 40，"
    "按钮仍是完整 28px，竖向滚动条不出现（max=0）；组框图 1134×576 → 1134×542。"
    "同版重打（Build **0118**）补上真机截图暴露的第二个缺陷："
    "「压缩后这些按钮显示不全了」——**与行高无关**，是按钮自身的内边距：全局 "
    "`QPushButton{padding:7px 14px}` 让「编辑/扫描/删除」的 `sizeHint` 高 33px（7+7 内边距 + 17 字高 + 2 边），"
    "而代码 `setFixedHeight(28)` 把它硬压到 28 → 内容区只剩 12px，字上下各被切约 3px。"
    "改走 `ui_hero.compact_button()`（打 `compact` 属性，`QPushButton[compact=\"1\"]{padding:0 4px;}` "
    "把内边距压成 0），尺寸仍锁 56×28 → 内容区 26px，字完整居中，**行高与列表高完全不变**。"
    "验证：冒烟 **377/377**（新增 ㉖ 段 17 条：`LIB_ROW_H==44`、`LIST_CHROME==6`、列表 `objectName==LibList`、"
    "3 库列表高 138、每项 sizeHint/visualRect 均 44、行控件 40、按钮 28px 不越界、按钮带 `compact` 属性且 "
    "`sizeHint().height()<=height()`、按钮 56×28、无滚动条、6 库封顶 182 且出滚动条、空库分支 50、"
    "QSS `#LibList::item` 存在且只改 padding 不写 height）；`dev/test_v119_logic.py` ALL PASS。"
    "真机（`QT_QPA_PLATFORM=windows`，dpr=1.0）实测行控件 40 / 按钮 56×28 位于 y=6 且不越界；"
    "打包 exe `流明盒-v1.46.15-2610290118.exe`（约 57 MB）真机验收 **13/13**："
    "标题 `流明盒  v1.46.15 (Build 2610290118)` / 不 Hung / 主窗可抓图 1920×1080 / 工具窗打开 1336×999 / "
    "点进「服务管理」后进程存活且页面可抓图 1320×960 / 关窗 rc=0 / app.log 8 行零未捕获异常。"
    "预览图：`dev/screenshots/v14615_buttons_before_after.png`（按钮改前/改后）、"
    "`v14615_exe_service.png`（真机工具窗）、`_liblist_before.png` ↔ `_liblist_after.png`（行距改前/改后）。"
    "★ **回滚基线**：按用户要求，下一版将对 UI 做一次完整迭代 —— 本版即是「大改 UI 之前的最后一版」，"
    "回滚只需把根目录 exe 换回本版、或从本源码 zip 重新 `build_exe.py`（两者 SHA-256 一致）。"
    "本版只动了两个文件：`src/ui_settings.py`（LIB_ROW_H / LIST_CHROME / setObjectName / compact_button 四处）、"
    "`src/style.qss`（一条 `#LibList::item`），**没有碰** 扫描、播放、刮削、数据库与主窗结构。"
)

sys.argv = ["archive_version.py", "--note", NOTE_TEXT]
runpy.run_path(os.path.join(ROOT, "dev/_scratch/archive_version.py"), run_name="__main__")

# ---------------- 回滚基线校验 ----------------
FAILS = []


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def check(label, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + label + (("  → " + str(detail)) if detail else ""))
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
check("封存说明已写", os.path.exists(NOTE), NOTE)
if os.path.exists(NOTE):
    txt = open(NOTE, encoding="utf-8").read()
    check("封存说明含 SHA-256", "SHA-256" in txt)
    check("封存说明含「回滚基线」", "回滚基线" in txt)

print("ARCHIVE_V14615_ALL_OK" if not FAILS else "ARCHIVE_V14615_HAS_FAIL")
if FAILS:
    print("失败项:", FAILS)
