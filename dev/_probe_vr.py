# -*- coding: utf-8 -*-
"""只读探查：VR 选集源文件夹内容（有无 nfo / poster / thumb，命名规则）。不动数据。"""
import os

DIRS = [
    r"X:\【30】VR视频\SAVR-1144-8K【弥生みづき】",
    r"X:\【30】VR视频\SAVR-1156-8K【逢月ひまり】",
    r"X:\【30】VR视频\SAVR-1172-8K【未知演员】",
]


def dump(d):
    print("DIR:", d, "| exists =", os.path.isdir(d))
    if not os.path.isdir(d):
        return
    try:
        names = sorted(os.listdir(d))
    except OSError as e:
        print("   [无法列出]", e)
        return
    for n in names:
        p = os.path.join(d, n)
        try:
            sz = os.path.getsize(p) if os.path.isfile(p) else 0
        except OSError:
            sz = 0
        print(f"   {'D' if os.path.isdir(p) else 'F'}  {n}   ({sz} B)")


for d in DIRS:
    dump(d)
    print()

# 顺带看父目录里有没有 .nfo（比如 movie.nfo / 目录级 nfo）
parent = r"X:\【30】VR视频"
print("PARENT:", parent, "exists =", os.path.isdir(parent))
if os.path.isdir(parent):
    nfos = [n for n in os.listdir(parent) if n.lower().endswith(".nfo")]
    print("   父目录下 .nfo:", nfos[:20])
