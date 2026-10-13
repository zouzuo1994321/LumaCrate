# -*- coding: utf-8 -*-
"""v1.40.5 预览出图 —— 刮削页全貌 + 两个合并后的专属特写（前/后对照）。

自证：打印 ui_settings.__file__。
出图注意：QWidget.grab() 是透明底图，必须 alpha_composite 到容器底色再存，
否则 PIL.convert("RGB") 会把半透明显示成纯白，图会骗人。
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

E = r"E:\【01】自研软件\【26-19】本地影视中心"
SRC = os.path.join(E, "src")
sys.path.insert(0, SRC)
os.chdir(E)

OUT = os.path.join(E, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)

from PySide6.QtWidgets import (QApplication, QGroupBox, QScrollArea, QLabel,
                               QHBoxLayout, QWidget)
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)
app.setStyle("Fusion")
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"):
    if os.path.isfile(fp):
        QFontDatabase.addApplicationFont(fp)
        break

from main_window import load_style
load_style(app)

import ui_settings
print("[自证] ui_settings:", ui_settings.__file__)

from PIL import Image


def save_widget(w, path, bg=(28, 26, 24)):
    """抓图 → 垫底色 → 存。透明底图必须先合成，否则半透明层会变纯白。"""
    pm = w.grab()
    img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    wpx, hpx = img.width(), img.height()
    ptr = img.constBits()
    raw = bytes(ptr).__bytes__() if not isinstance(ptr, (bytes, bytearray)) else ptr
    bpl = img.bytesPerLine()
    im = Image.frombytes("RGBA", (wpx, hpx), bytes(raw)[:bpl * hpx], "raw", "BGRA", bpl, 1)
    canvas = Image.new("RGBA", im.size, bg + (255,))
    canvas.alpha_composite(im)
    canvas.convert("RGB").save(path)
    print(f"  [出图] {os.path.basename(path)}  {canvas.width}x{canvas.height}")
    return canvas.width, canvas.height


dlg = ui_settings.SettingsDialog()
dlg.resize(1334, 960)
dlg.show()
app.processEvents()
dlg._show("演员刮削")
app.processEvents()
for _ in range(4):
    app.processEvents()

pg = dlg._pg_scraper
if isinstance(pg, QScrollArea):
    print("[体检⓪] 执行页被 QScrollArea 包裹（离屏 760 高装不下），取内层")
    pg = pg.widget()

lay = pg.layout()
print("\n[体检①] 刮削页 sizeHint=%d（v1.40.4 是 944，应更矮）" % pg.sizeHint().height())
print("[体检①] 逐组框：")
boxes = {}
for i in range(lay.count()):
    w = lay.itemAt(i).widget()
    if isinstance(w, QGroupBox):
        boxes[w.title()] = w
        print("   [%d] %-52s sizeHint=%d" % (i, w.title()[:50], w.sizeHint().height()))

# ---------- 图 1：刮削页全貌 ----------
w1, h1 = save_widget(pg, os.path.join(OUT, "v1405_scraper_full.png"))

# ---------- 图 2：「演员刮削」合并行特写 ----------
ge = boxes.get("演员刮削")
print("\n[体检②] 「演员刮削」合并行 sizeHint=%d（v1.40.4 两框合计 159）" % ge.sizeHint().height())
gl = ge.layout()
for j in range(gl.count()):
    it = gl.itemAt(j)
    c = it.widget()
    if c is None:
        print("   [%d] <弹性分隔 QSpacerItem>" % j)
    else:
        t = ""
        if isinstance(c, QLabel):
            t = " text=%r" % c.text()[:34]
        print("   [%d] %-14s sizeHint=%s%s" % (j, type(c).__name__, c.sizeHint().height(), t))
w2, h2 = save_widget(ge, os.path.join(OUT, "v1405_merged_row.png"))

# ---------- 图 3：数据源组框特写（按钮 + 提示同行） ----------
g0 = None
for k, w in boxes.items():
    if k.startswith("演员刮削数据源"):
        g0 = w
print("\n[体检③] 数据源组框 sizeHint=%d（v1.40.4 是 262）" % g0.sizeHint().height())
g0l = g0.layout()
for j in range(g0l.count()):
    c = g0l.itemAt(j).widget()
    name = type(c).__name__ if c is not None else "spacer"
    print("   [%d] %-14s sizeHint=%s" % (j, name, c.sizeHint().height() if c else "-"))
    if c is not None and isinstance(c, QWidget) and type(c).__name__ == "QWidget":
        cl = c.layout()
        for k in range(cl.count()):
            cc = cl.itemAt(k).widget()
            if cc is None:
                print("        (%d) <弹性分隔>" % k)
            else:
                t = ""
                if isinstance(cc, QLabel):
                    t = " text=%r" % cc.text()[:26]
                print("        (%d) %-14s sizeHint=%s%s" % (k, type(cc).__name__, cc.sizeHint().height(), t))
w3, h3 = save_widget(g0, os.path.join(OUT, "v1405_src_row.png"))

# ---------- 对照汇总 ----------
print("\n[对照] v1.40.4 → v1.40.5")
print("   演员刮削（总开关 + 统计） : 78 + 81 = 159  →  %d" % ge.sizeHint().height())
print("   数据源组框                : 262            →  %d" % g0.sizeHint().height())
print("   刮削页 sizeHint           : 944            →  %d" % pg.sizeHint().height())
print("   工具窗高度                : minH=%d maxH=%d（v1.40.4 硬锁未变）" % (dlg.minimumHeight(), dlg.maximumHeight()))

dlg.close()
print("\n[完成] 出图目录:", OUT)
