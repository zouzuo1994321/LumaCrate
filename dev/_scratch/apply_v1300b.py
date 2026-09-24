# -*- coding: utf-8 -*-
"""v1.30.0 第二批落地：把 dev/_staging_v1300b/ 里的文件覆盖到正式位置。

**先跑过 `dev/_scratch/apply_v1300.py` 再跑本脚本。**

用法（在项目根目录执行）：

    python dev/_scratch/apply_v1300.py
    python dev/_scratch/apply_v1300b.py

这批只做一件事：修掉 A-Z 字母跳转的卡顿（真机 5909 位演员跳到 'Z' 由 59 秒降到 9 秒），
外加把构建号日期段从 260923 改成打包当天 260924（末四位仍是 0041）。

流程与上一批一致：py_compile → 关键锚点校验 → 备份原件到 _backup/ → 覆盖 → 逐字节校验。
"""
import hashlib
import os
import py_compile
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAGE = os.path.join(ROOT, "dev", "_staging_v1300b")
BACKUP = os.path.join(STAGE, "_backup")

FILES = ['src/main_window.py', 'src/version.py', 'README.md', 'README_EN.md', 'dev/smoke_v1300.py', 'dev/live_verify_v1300.py', 'dev/_scratch/probe_jump_cost.py', 'dev/_scratch/probe_lazy_avatar.py', 'dev/_scratch/probe_avatar_cost.py', 'dev/_scratch/probe_batch_size.py', 'dev/_scratch/probe_jump_parts.py', 'dev/_scratch/inspect_live_png.py', 'dev/_scratch/diff_png2.py']

ANCHORS = {
    "src/main_window.py": ["def _ensure_avatar", "self._avatar_pending",
                           "正在跳转… 已载入", "max(self.batch, 600)",
                           "def _show_jump_progress"],
    "src/version.py": ['BUILD_DATE = "260924"', 'BUILD_SEQ = "0041"',
                       "MAJOR_ITER = 30", "MINOR_ITER = 0"],
    "README.md": ["v1.30.0 (Build 2609240041)", "A-Z 跳转从 59 秒降到 26 秒",
                  "77 PASS / 0 FAIL"],
    "README_EN.md": ["59s → 26s"],
    "dev/smoke_v1300.py": ["I. 头像按需加载", "I1 未绘制的卡头像处于 pending",
                           "I3 绘制后头像 pixmap 非空且尺寸正确"],
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
        done.append((rel, "覆盖" if old_hash != "(新建)" else "新建",
                     "校验通过" if ok else "校验失败"))
        if not ok:
            print("!! 校验失败：%s" % rel)
            return 3
    print("%-38s %-6s %s" % ("文件", "动作", "校验"))
    for rel, act, v in done:
        print("%-38s %-6s %s" % (rel, act, v))
    print("\n共 %d 个文件已落地。" % len(done))
    print("回滚：把 %s 里的同名文件复制回去即可。" % BACKUP)
    print("下一步：python build_exe.py 重打（会得到 流明盒-v1.30.0-2609240041.exe）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
