# -*- coding: utf-8 -*-
"""生成 logo 资源：src/logo.png（打包用）+ logo.ico（exe / 窗口图标，多分辨率）。"""
import os, shutil, builtins
from PIL import Image

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
_OUT = open(r"C:\Users\zouzu\AppData\Local\Temp\lmc_logo.txt", "w", encoding="utf-8")
def print(*a, **k):
    k["file"] = _OUT
    builtins.print(*a, **k)

src_png = os.path.join(ROOT, "logo.png")
im = Image.open(src_png).convert("RGBA")
print("src", im.size, im.mode)

# 1) src/logo.png（运行时窗口图标 / 关于页 logo；与 style.qss 同目录，打包 add-data）
dst_png = os.path.join(SRC, "logo.png")
shutil.copyfile(src_png, dst_png)
print("copy ->", dst_png, os.path.getsize(dst_png), "bytes")

# 2) logo.ico（多分辨率，供 PyInstaller --icon）
ico = os.path.join(ROOT, "logo.ico")
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
im.save(ico, format="ICO", sizes=sizes)
print("ico ->", ico, os.path.getsize(ico), "bytes", sizes)

_OUT.flush(); _OUT.close()
