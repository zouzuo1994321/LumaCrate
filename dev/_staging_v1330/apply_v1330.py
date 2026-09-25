# -*- coding: utf-8 -*-
"""v1.32.0 → v1.33.0 一键落地（幂等）。

用法（在**权限正常**的环境里执行，项目根即本仓库根）：
    python dev\\_staging_v1330\\apply_v1330.py           # 真正落地
    python dev\\_staging_v1330\\apply_v1330.py --dry-run  # 只体检，不写盘
    python apply_v1330.py --root D:\\path\\to\\repo      # 脚本被挪到别处时显式指定项目根

它把 `dev/_staging_v1330/` 里的文件按相对路径覆盖到项目里，并在覆盖前：
  1. 把原文件备份到 `dev/_backup_v1330/<相对路径>`（只备份一次，不覆盖已存在的备份）；
  2. 逐个校验 sha256（写后回读，不一致就报错并停下）；
  3. 对 `.py` 做语法检查（`compile()`，不落 `.pyc`）：写盘前先验暂存版，写盘后再验一次。

为什么需要这个脚本：Z: 盘上**已存在**的文件是 OS 级只读
（`open('w')` / `DeleteFileW` / `MoveFileW` 全都 `err=5`），只有**新建**的文件可写。
所以源码只能先暂存到 `dev/_staging_v1330/`，再由你在权限正常时执行本脚本落盘。

覆盖清单 = v1.33.0 的四条反馈：
  反馈 1（扫描结果可导入/导出）
      src/duplicates.py     —— export_json 加信封 + 顶层标量平铺；新增 import_json 与重建函数
      src/imagedetect.py    —— 新增 export_json / import_json / EXPORT_FORMAT
      src/actorcheck.py     —— 新增递归 _plain + export_json / import_json（`_occ` 的元组键）
      src/tagopt.py         —— 新增递归 _plain + export_json / import_json（translated 嵌套二元组）
      src/ui_settings.py    —— 重复检测页 + 标签优化页各加一对按钮与两个方法
      src/ui_imagedetect.py —— 图像检测页同上
      src/ui_actorcheck.py  —— 演员检测页同上
  反馈 2（四页「白条」根因修复）
      src/main_window.py    —— LazyGrid 的 head / bar 默认隐藏；_update_head 主动 hide
  反馈 3（删除「悬停时显示预告片（预留）」）
      src/config.py         —— DEFAULT_CONTENT_CARDS 删 hover_trailer
      src/ui_settings.py    —— card_map 删条目、头注释同步
  反馈 4（「关于」加入作者联系图标）
      src/version.py        —— CONTACTS / CONTACT_MAIL 真源
      src/main_window.py    —— AboutDialog._contact_icon / _contact_bar / _open_contact
                               + _body() 的「### 联系作者」段
      src/style.qss         —— QPushButton#ContactIcon（必须 padding: 0）
  文档与脚本
      README.md / README_EN.md（徽章 + v1.33.0 迭代记录）
      dev/{smoke_v1330,render_v1330,live_verify_v1330}.py
      dev/_scratch/{ui_coords_v1330,probe_tagopt_rt}.py
      dev/screenshots_v1330/*.png

**不动** `settings.json`（那是你自己的配置，不该被版本覆盖）。

跑完别忘了：把 `流明盒-v1.33.0-2609240044.exe` 放到项目根，并手工删掉根目录里
上一版的 `流明盒-v1.32.0-2609240043.exe`（本脚本不动 exe）。
"""
import hashlib
import os
import shutil
import sys

STAGE_NAME = "_staging_v1330"
BACKUP_NAME = "_backup_v1330"
WANT_VERSION = "v1.33.0"
WANT_BUILD = "2609240044"


def syntax_ok(path):
    """纯语法检查：不落任何 .pyc（`py_compile` 会往源码旁写缓存，不适合这里）。"""
    try:
        with open(path, encoding="utf-8") as f:
            compile(f.read(), path, "exec")
        return True, ""
    except Exception as e:
        return False, str(e)


def find_root():
    """从脚本位置向上找带 `src/version.py` 的目录。

    注意要**跳过暂存目录自己** —— 暂存里也有一份 `src/version.py`，不排除的话
    会把 `dev/_staging_v1330/` 当成项目根。
    """
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        base = os.path.basename(d)
        if (os.path.isfile(os.path.join(d, "src", "version.py"))
                and not base.startswith("_staging")):
            return d
        d = os.path.dirname(d)
    return None


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    dry = "--dry-run" in sys.argv
    root = None
    if "--root" in sys.argv:
        try:
            root = sys.argv[sys.argv.index("--root") + 1]
        except IndexError:
            print("!! --root 后面要跟项目根路径")
            return 2
    root = root or find_root()
    if not root:
        print("!! 找不到项目根（向上找 src/version.py 失败）—— 请把本脚本放在项目内的 dev/_staging_v1330/ 下")
        return 2
    stage = os.path.join(root, "dev", STAGE_NAME)
    if not os.path.isdir(stage):
        print("!! 找不到暂存目录：%s" % stage)
        return 2

    rels = []
    for r, _ds, fs in os.walk(stage):
        for f in fs:
            if f == os.path.basename(__file__):
                continue                      # 自己不用拷回去
            rels.append(os.path.relpath(os.path.join(r, f), stage).replace("\\", "/"))
    rels.sort()

    print("项目根  : %s" % root)
    print("暂存目录: %s" % stage)
    print("共 %d 个文件%s\n" % (len(rels), "（dry-run，不写盘）" if dry else ""))

    backup = os.path.join(root, "dev", BACKUP_NAME)
    added, updated, same, failed = [], [], [], []

    for rel in rels:
        s = os.path.join(stage, rel.replace("/", os.sep))
        t = os.path.join(root, rel.replace("/", os.sep))

        # 1) 语法校验暂存版
        if rel.endswith(".py"):
            good, err = syntax_ok(s)
            if not good:
                print("  [语法] %-34s FAIL  %s" % (rel, err))
                failed.append(rel)
                continue

        exists = os.path.isfile(t)
        if exists and sha(t) == sha(s):
            same.append(rel)
            print("  [跳过] %-38s 内容已一致" % rel)
            continue

        if dry:
            print("  [%s] %-38s %s" % ("覆盖" if exists else "新增", rel,
                                       "%d B" % os.path.getsize(s)))
            (updated if exists else added).append(rel)
            continue

        # 2) 备份（只备份一次，绝不覆盖旧备份）
        if exists:
            b = os.path.join(backup, rel.replace("/", os.sep))
            if not os.path.isfile(b):
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copyfile(t, b)
        # 3) 落盘
        os.makedirs(os.path.dirname(t), exist_ok=True)
        shutil.copyfile(s, t)
        # 4) 回读校验
        if sha(t) != sha(s):
            print("  [%s] %-38s **写后校验失败**" % ("覆盖" if exists else "新增", rel))
            failed.append(rel)
            continue
        if rel.endswith(".py"):
            good, err = syntax_ok(t)
            if not good:
                print("  [%s] %-38s 写后语法检查失败：%s"
                      % ("覆盖" if exists else "新增", rel, err))
                failed.append(rel)
                continue
        print("  [%s] %-38s %8d B  sha 校验通过"
              % ("覆盖" if exists else "新增", rel, os.path.getsize(t)))
        (updated if exists else added).append(rel)

    print("\n---- 汇总 ----")
    print("  新增 %d / 覆盖 %d / 已一致 %d / 失败 %d"
          % (len(added), len(updated), len(same), len(failed)))
    if updated or added:
        print("  原文件已备份到：%s" % backup)
    if failed:
        print("  !! 失败：%s" % failed)
        return 1

    # 5) 版本自检
    if not dry:
        vp = os.path.join(root, "src", "version.py")
        ns = {}
        try:
            with open(vp, encoding="utf-8") as f:
                exec(compile(f.read(), vp, "exec"), ns)
            print("  版本自检：%s (Build %s)" % (ns.get("VERSION"), ns.get("BUILD")))
            if ns.get("VERSION") != WANT_VERSION or ns.get("BUILD") != WANT_BUILD:
                print("  !! 版本号不是 %s / %s，请检查落地结果" % (WANT_VERSION, WANT_BUILD))
                return 1
        except Exception as e:
            print("  !! 版本自检失败：%s" % e)
            return 1
        print("\n  落地完成。下一步：")
        print("     · 确认根目录有 流明盒-%s-%s.exe" % (WANT_VERSION, WANT_BUILD))
        print("     · 删掉根目录里旧的 流明盒-v1.32.0-2609240043.exe")
        print("     · 双击新 exe 验收：演员库/导演库/最近播放/合集 四页右上角白条应已消失")
    return 0


if __name__ == "__main__":
    sys.exit(main())
