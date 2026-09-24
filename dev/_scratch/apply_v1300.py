# -*- coding: utf-8 -*-
"""v1.30.0 一键落地：把 dev/_staging_v1300/ 里的文件覆盖到项目正式位置。

用法（在项目根目录执行；用你本机任意 Python 3.8+ 均可）：

    python dev/_scratch/apply_v1300.py

它做的事（**幂等**，可以重复跑）：
  1. 逐个校验暂存文件（.py 先 py_compile，README 校验关键锚点）；
  2. 覆盖前把现有文件另存到 dev/_staging_v1300/_backup/ 下（首次跑才算）；
  3. 复制到目标位置，并**逐字节校验**结果；
  4. 打印一张 文件 / 状态 / 校验 的表；任何一步失败会立刻停止并保留现场。

跑完就可以：
    python dev/smoke_v1300.py        # 或 runpy 方式（视你的环境）
    python build_exe.py              # 重新打包 v1.30.0

v1.30.0 相对 v1.28.1 的改动范围（共 14 个文件）：
  新增  src/letter_index.py  src/ui_imagedetect.py  src/ui_manualedit.py
        dev/smoke_v1300.py   dev/render_v1300.py
  改动  src/database.py（首字母排序 + _people_clauses 收拢 + people_letter_index
        + media_for_imagescan）、src/main_window.py（演员卡作品数 + LazyGrid.jump_to
        + _people_rail）、src/ui_settings.py（两页接入 + 导航顺序）、src/version.py
        （v1.30.0 / 2609230041）、src/imagedetect.py（候选路径不再跨槽位兜底）、
        src/nfo_editor.py、build_exe.py（5 个 hidden-import）、README.md、README_EN.md。
"""
import hashlib
import os
import py_compile
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAGE = os.path.join(ROOT, "dev", "_staging_v1300")
BACKUP = os.path.join(STAGE, "_backup")

FILES = ['src/letter_index.py', 'src/ui_imagedetect.py', 'src/ui_manualedit.py', 'dev/smoke_v1300.py', 'dev/render_v1300.py', 'dev/live_verify_v1300.py', 'dev/_scratch/ui_coords_v1300.py', 'src/database.py', 'src/main_window.py', 'src/ui_settings.py', 'src/version.py', 'src/imagedetect.py', 'src/nfo_editor.py', 'build_exe.py', 'README.md', 'README_EN.md']

#: 覆盖后必须能在文件里找到的锚点（防「复制成功但内容不对」）
ANCHORS = {
    "src/database.py": ["_ACTOR_LETTER_EXPR", "def _people_clauses", "def people_letter_index",
                        "def media_for_imagescan", '("letter",    "首字母"'],
    "src/main_window.py": ['("作品", 1, 1, 1)', "def _people_rail", "def jump_to",
                           "self._people_rail(page,", "from letter_index import LetterIndexBar"],
    "src/ui_settings.py": ['"手动修改"', '"图像检测"', "ui_manualedit.ManualEditPage()",
                           "ui_imagedetect.ImageDetectPage()"],
    "src/version.py": ['MAJOR_ITER = 30', 'MINOR_ITER = 0', 'BUILD_DATE = "260923"',
                       'BUILD_SEQ = "0041"'],
    "src/imagedetect.py": ["刻意不做跨槽位兜底"],
    "build_exe.py": ['"ui_imagedetect"', '"ui_manualedit"', '"letter_index"'],
    "README.md": ["v1.30.0 (Build 2609230041)", "A-Z 字母索引", "工具箱新增「图像检测」"],
    "README_EN.md": ["A–Z letter index", "Image check"],
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    if not os.path.isdir(STAGE):
        print("找不到暂存目录：%s" % STAGE)
        return 2
    plan = []
    for rel in FILES:
        src = os.path.join(STAGE, rel.replace("/", os.sep))
        dst = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(src):
            print("[缺失] 暂存文件不存在：%s" % rel)
            return 2
        if rel.endswith(".py"):
            try:
                py_compile.compile(src, doraise=True, cfile=src + ".compilecheck")
            except Exception as e:
                print("[语法] %s 编译失败：%s" % (rel, e))
                return 2
            finally:
                try:
                    os.remove(src + ".compilecheck")
                except OSError:
                    pass
        with open(src, encoding="utf-8") as f:
            txt = f.read()
        miss = [a for a in ANCHORS.get(rel, []) if a not in txt]
        if miss:
            print("[锚点] %s 缺少关键内容：%s" % (rel, miss))
            return 2
        plan.append((rel, src, dst))

    print("== 准备就绪，开始覆盖（原件镜像到 %s）==" % BACKUP)
    done = []
    for rel, src, dst in plan:
        old_hash = sha(dst) if os.path.exists(dst) else "(新建)"
        bak = os.path.join(BACKUP, rel.replace("/", os.sep))
        if os.path.exists(dst):
            os.makedirs(os.path.dirname(bak), exist_ok=True)
            if not os.path.exists(bak):
                shutil.copyfile(dst, bak)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        ok = (os.path.getsize(src) == os.path.getsize(dst)) and (sha(src) == sha(dst))
        done.append((rel, "覆盖" if old_hash != "(新建)" else "新建", "校验通过" if ok else "校验失败"))
        if not ok:
            print("!! 校验失败：%s" % rel)
            return 3
    print("%-26s %-6s %s" % ("文件", "动作", "校验"))
    for rel, act, v in done:
        print("%-26s %-6s %s" % (rel, act, v))
    print("\n共 %d 个文件已落地。" % len(done))
    print("回滚：把 %s 里的同名文件复制回去即可。" % BACKUP)
    print("下一步：python dev/smoke_v1300.py  →  python build_exe.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
