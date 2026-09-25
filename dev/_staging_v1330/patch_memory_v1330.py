# -*- coding: utf-8 -*-
"""把 v1.33.0 对项目 `MEMORY.md` 的**增量补丁**写进暂存（Z: 上已存在的文件是只读）。

用法：在权限正常的环境里执行
    python dev\\_staging_v1330\\patch_memory_v1330.py            # 真正改
    python dev\\_staging_v1330\\patch_memory_v1330.py --dry-run  # 只看
它把 `dev/_staging_v1330/_memory/MEMORY.md.patch.json` 里的「锚点 → 插入内容」
按顺序应用到 `.workbuddy/memory/MEMORY.md`，改前备份到
`dev/_backup_v1330/_memory/MEMORY.md`。

补丁是**插入式**的（在指定锚点行前插入新段），不重写整份文件 ——
这样即便 MEMORY.md 在别处被手工改过，也不会被覆盖掉。
"""
import json
import os
import shutil
import sys


def find_root():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        base = os.path.basename(d)
        if (os.path.isfile(os.path.join(d, "src", "version.py"))
                and not base.startswith("_staging")):
            return d
        d = os.path.dirname(d)
    return None


def main():
    dry = "--dry-run" in sys.argv
    root = find_root()
    if not root:
        print("!! 找不到项目根")
        return 2
    stage = os.path.join(root, "dev", "_staging_v1330")
    pf = os.path.join(stage, "_memory", "MEMORY.md.patch.json")
    if not os.path.isfile(pf):
        print("!! 找不到补丁文件：%s" % pf)
        return 2
    with open(pf, encoding="utf-8") as f:
        patches = json.load(f)

    target = os.path.join(root, ".workbuddy", "memory", "MEMORY.md")
    if not os.path.isfile(target):
        print("!! 找不到目标：%s" % target)
        return 2
    with open(target, encoding="utf-8") as f:
        txt = f.read()
    orig = txt

    for p in patches:
        anchor = p["anchor"]
        body = p["insert_before"]
        if body.strip() in txt:
            print("  [跳过] 已存在：%s" % p.get("name", anchor[:24]))
            continue
        if anchor not in txt:
            print("  !! 锚点找不到：%r" % anchor[:60])
            return 1
        if dry:
            print("  [插入] %-30s ← %r" % (p.get("name", "?"), anchor[:44]))
            continue
        txt = txt.replace(anchor, body + anchor, 1)
        print("  [插入] %-30s ← %r" % (p.get("name", "?"), anchor[:44]))

    if dry:
        print("\n(dry-run，未写盘)")
        return 0
    if txt == orig:
        print("\n无需改动。")
        return 0

    b = os.path.join(root, "dev", "_backup_v1330", "_memory", "MEMORY.md")
    os.makedirs(os.path.dirname(b), exist_ok=True)
    if not os.path.isfile(b):
        shutil.copyfile(target, b)
        print("  已备份原文件 → %s" % b)
    with open(target, "w", encoding="utf-8") as f:
        f.write(txt)
    # 回读校验
    with open(target, encoding="utf-8") as f:
        back = f.read()
    if back != txt:
        print("  !! 写后校验失败")
        return 1
    print("  MEMORY.md 已更新（%d → %d 字符）" % (len(orig), len(txt)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
