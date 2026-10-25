# -*- coding: utf-8 -*-
"""v1.45.0 工程化：把历史冒烟脚本收进 dev/history/（只留当前门槛 smoke_v1430.py）。

只移动文件，不删除；已存在同名文件时跳过。
"""
import os
import shutil

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
DEV = os.path.join(ROOT, "dev")
HIST = os.path.join(DEV, "history")
os.makedirs(HIST, exist_ok=True)
KEEP = {"smoke_v1430.py"}
moved = 0
for f in sorted(os.listdir(DEV)):
    if not (f.startswith("smoke_v") and f.endswith(".py")):
        continue
    if f in KEEP:
        continue
    src = os.path.join(DEV, f)
    dst = os.path.join(HIST, f)
    if os.path.exists(dst):
        print("跳过（已存在）:", f)
        continue
    shutil.move(src, dst)
    moved += 1
print("移动 %d 个历史冒烟到 dev/history/" % moved)
print("根目录剩余:", [x for x in os.listdir(DEV) if x.startswith("smoke_")])
print("MOVE_DONE")
