# -*- coding: utf-8 -*-
"""验证 v1.33.1 联系图标：三张内联 logo 真能出图、形状与源图一致。

做法：把 `_contact_icon` 渲染到 96×96，逐像素比对它的 alpha 掩码与
**直接缩放的源 png alpha 掩码**是否一致（同形状判断）；再看四枚图标的
非透明像素数（确认非空）。
"""
import io
import os
import sys

sys.path.insert(0, r"C:\Users\zouzu\AppData\Local\Temp\lmc_v1310\src")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication, QImage, QColor  # noqa: E402

app = QGuiApplication.instance() or QGuiApplication([])

from PIL import Image  # noqa: E402
import main_window as mw  # noqa: E402

SRC = r"C:\Users\zouzu\Desktop\联系logo"
FILES = {"github": "github-1.png", "bilibili": "bilibili-1.png", "weibo": "weibo-1.png"}

SZ = 96
ok = True
print("=== 1) 四枚图标都非空 ===")
for kind in ("github", "bilibili", "weibo", "mail"):
    ic = mw.AboutDialog._contact_icon(kind, SZ, "#e8e0d4")
    pm = ic.pixmap(SZ, SZ)
    img = pm.toImage()
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 8:
                n += 1
    print("  %-9s opaque=%5d  size=%dx%d" % (kind, n, pm.width(), pm.height()))
    if n < 40:
        ok = False
        print("    !! 透明到几乎看不见")

print()
print("=== 2) 内联 logo 与源 png 的形状一致性（IoU） ===")
for kind, fn in FILES.items():
    # 源图 alpha 掩码（缩放到 96 再二值化）
    src_im = Image.open(os.path.join(SRC, fn)).convert("RGBA").resize((SZ, SZ), Image.LANCZOS)
    src_a = src_im.split()[3].point(lambda v: 255 if v > 128 else 0)

    qimg = mw.AboutDialog._contact_logo_pixmap(kind, SZ, "#e8e0d4").toImage()
    inter = union = 0
    for y in range(SZ):
        for x in range(SZ):
            a = 1 if qimg.pixelColor(x, y).alpha() > 128 else 0
            b = 1 if src_a.getpixel((x, y)) > 128 else 0
            if a and b:
                inter += 1
            if a or b:
                union += 1
    iou = inter / union if union else 0.0
    print("  %-9s IoU=%.3f  %s" % (kind, iou, "OK" if iou > 0.80 else "!! 形状可疑"))
    if iou <= 0.80:
        ok = False

print()
print("=== 3) 着色验证：tint 是否真的生效（取不透明像素的主色） ===")
for kind in ("github", "bilibili", "weibo"):
    qimg = mw.AboutDialog._contact_logo_pixmap(kind, SZ, "#ff0000").toImage()
    from collections import Counter
    c = Counter()
    for y in range(SZ):
        for x in range(SZ):
            col = qimg.pixelColor(x, y)
            if col.alpha() > 200:
                c[col.name()] += 1
    top = c.most_common(1)[0] if c else ("none", 0)
    print("  %-9s top color=%s (%d px)  %s"
          % (kind, top[0], top[1], "OK" if top[0] == "#ff0000" else "!! 着色未生效"))
    if top[0] != "#ff0000":
        ok = False

print()
print("ALL OK" if ok else "FAILED")
