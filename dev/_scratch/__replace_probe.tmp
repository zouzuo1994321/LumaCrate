# -*- coding: utf-8 -*-
"""探针：截断的 JPEG / PNG 在 PIL / Qt / 纯结构检查下分别怎么判定（决定图像检测用哪种方案）。"""
import os

TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_imgprobe"
os.makedirs(TMP, exist_ok=True)

SRC_PNG = r"Z:/【01】自研软件/【26-19】本地影视中心/dev/screenshots/17_live_window.png"

from PIL import Image

jpg = os.path.join(TMP, "ok.jpg")
Image.open(SRC_PNG).convert("RGB").save(jpg, quality=88)


def structural_ok(p):
    try:
        with open(p, "rb") as f:
            data = f.read()
    except Exception as e:
        return False, "无法读取 %s" % e
    if len(data) < 1024:
        return False, "文件过小(%d)" % len(data)
    if data[:2] == b"\xff\xd8":
        tail = data.rstrip(b"\x00 \r\n")
        if not tail.endswith(b"\xff\xd9"):
            return False, "缺少 EOI 标记(截断)"
        return True, "ok"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if b"IEND" not in data[-32:]:
            return False, "缺少 IEND(截断)"
        return True, "ok"
    return True, "未知格式(不判)"


def pil_check(p):
    try:
        im = Image.open(p)
        im.load()
        return True, "ok"
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, str(e)[:70])


def qt_check(p):
    from PySide6.QtGui import QImageReader, QPixmap
    r = QImageReader(p)
    img = r.read()
    pm = QPixmap(p)
    return (not img.isNull()), "readNull=%s err=%s pixNull=%s size=%sx%s" % (
        img.isNull(), r.error(), pm.isNull(), pm.width(), pm.height())


def make(dst, src, ratio):
    raw = open(src, "rb").read()
    open(dst, "wb").write(raw[:max(1, int(len(raw) * ratio))])


cases = []
cases.append(("完整JPEG", jpg))
for ratio in (0.75, 0.45):
    p = os.path.join(TMP, "trunc_jpg_%d.jpg" % int(ratio * 100))
    make(p, jpg, ratio)
    cases.append(("截断JPEG %d%%" % int(ratio * 100), p))
p = os.path.join(TMP, "trunc_png_55.png")
make(p, SRC_PNG, 0.55)
cases.append(("截断PNG 55%", p))
p = os.path.join(TMP, "zero.jpg")
open(p, "wb").write(b"")
cases.append(("空文件", p))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
app = QApplication([])

for label, p in cases:
    print("---", label, os.path.getsize(p), "bytes")
    print("   结构:", structural_ok(p))
    print("   PIL :", pil_check(p))
    print("   Qt  :", qt_check(p))
