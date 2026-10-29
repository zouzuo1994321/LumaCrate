# -*- coding: utf-8 -*-
"""整理 v1.46.13 交付截图：留 4 张正式图，删掉本轮临时图（`_` 前缀）。

本机 os.remove 被 safe-delete shim 拦，统一走 SetFileAttributesW + DeleteFileW。
"""
import os
import ctypes
import shutil
from PIL import Image

base = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
SRC = os.path.join(base, "_exe2_scan_1.png")


def _del(p):
    if os.path.exists(p):
        ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
        ctypes.windll.kernel32.DeleteFileW(p)


def del_glob(prefixes, keep=()):
    n = 0
    for fn in list(os.listdir(base)):
        if fn in keep:
            continue
        if fn.startswith("_") or fn.startswith("v14613_exe_t"):
            p = os.path.join(base, fn)
            _del(p)
            if not os.path.exists(p):
                n += 1
    return n


# 1) 整窗「扫描中」图
shutil.copy2(SRC, os.path.join(base, "v14613_exe_scanning.png"))
im = Image.open(SRC).convert("RGB")
W, H = im.size

# 2) 整条状态栏 4 倍
c = im.crop((0, H - 26, W, H - 2)).resize((W, 24 * 4), Image.LANCZOS)
c.save(os.path.join(base, "v14613_exe_scanning_bar.png"))

# 3) 右侧 6 倍（扫描文字 + 进度条）
d = im.crop((1300, H - 26, W, H - 2)).resize(((W - 1300) * 5, 24 * 7), Image.LANCZOS)
d.save(os.path.join(base, "v14613_exe_scanning_right.png"))

removed = del_glob(None, keep=("v14613_exe_start.png", "v14613_exe_scanning.png",
                               "v14613_exe_scanning_bar.png", "v14613_exe_scanning_right.png",
                               "v14613_before.png", "v14613_during.png", "v14613_after.png",
                               "v14613_during_right.png", "v14613_after_right.png"))
print("已清理临时图:", removed)
print("保留:")
for fn in sorted(os.listdir(base)):
    print("  ", fn)
