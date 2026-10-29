# -*- coding: utf-8 -*-
"""出「我的评分」改前 / 改后对比图（2 倍，横向并列，带标注），并清理临时图。

改前：`_rate_before.png`（本次改动**前**用同一套 QSS 离屏渲染，302×128）
改后：`v14614_rate_body.png`（真机 windows 平台渲染，240×129）
"""
import os
import ctypes
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"
BEFORE = os.path.join(BASE, "_rate_before.png")
AFTER = os.path.join(BASE, "v14614_rate_body.png")
OUT = os.path.join(BASE, "v14614_rate_before_after.png")

SCALE = 2
PAD = 16
GAP = 14
LABEL_H = 26
FONT = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 15)

im_b = Image.open(BEFORE).convert("RGB")
im_a = Image.open(AFTER).convert("RGB")
im_b = im_b.resize((im_b.width * SCALE, im_b.height * SCALE), Image.LANCZOS)
im_a = im_a.resize((im_a.width * SCALE, im_a.height * SCALE), Image.LANCZOS)

W = PAD * 2 + im_b.width + GAP + im_a.width
H = PAD * 2 + LABEL_H + max(im_b.height, im_a.height)
canvas = Image.new("RGB", (W, H), (18, 15, 12))
d = ImageDraw.Draw(canvas)
board = (28, 24, 20)

# 改前
canvas.paste(im_b, (PAD, PAD + LABEL_H - 8))
d.rectangle([PAD, PAD + LABEL_H - 8, PAD + im_b.width - 1,
             PAD + LABEL_H - 8 + im_b.height - 1], outline=(150, 60, 50), width=2)
d.text((PAD + 2, PAD + 2), "改前  302×128（右侧空 130px、左下空 82px、微调按钮区无箭头）",
       font=FONT, fill=(226, 150, 140))

x2 = PAD + im_b.width + GAP
canvas.paste(im_a, (x2, PAD + LABEL_H - 8))
d.rectangle([x2, PAD + LABEL_H - 8, x2 + im_a.width - 1,
             PAD + LABEL_H - 8 + im_a.height - 1], outline=(90, 150, 90), width=2)
d.text((x2 + 2, PAD + 2), "改后  240×129（四周无死白、按钮分组）",
       font=FONT, fill=(150, 210, 150))

canvas.save(OUT, "PNG")
print("对比图:", OUT, canvas.size)


def _del(p):
    if os.path.exists(p):
        ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
        ctypes.windll.kernel32.DeleteFileW(p)


keep = {"v14614_rate_body.png", "v14614_rate_before_after.png", "v14614_rate_dialog.png",
        "v14614_exe_start.png"}
n = 0
for fn in os.listdir(BASE):
    if fn.startswith("_rate") and fn not in keep:
        p = os.path.join(BASE, fn)
        _del(p)
        n += not os.path.exists(p)
print("清理临时图:", n)
print([f for f in sorted(os.listdir(BASE)) if f.startswith("v14614") or f.startswith("_rate")])
