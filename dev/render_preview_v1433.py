# -*- coding: utf-8 -*-
"""v1.43.3 预览出图：① 图像检测页（同款虚线+5 点把手）② 把手放大（横/竖各一条）。"""
import os
import sys
import tempfile
from collections import Counter

from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QRect, QPoint

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_render_v1433_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

import main_window as mw
import ui_imagedetect as uid
import ui_actorcheck as uac

mw.load_style(app)
OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)


def to_rgb(pix, out_path, fallback=(24, 21, 19)):
    tmp = os.path.join(TMP, "raw.png")
    pix.save(tmp)
    im = Image.open(tmp).convert("RGBA")
    cnt = Counter()
    for y in range(0, im.height, 5):
        for x in range(0, im.width, 7):
            p = im.getpixel((x, y))
            if p[3] > 200:
                cnt[p[:3]] += 1
    bg = cnt.most_common(1)[0][0] if cnt else fallback
    base = Image.new("RGBA", im.size, bg + (255,))
    Image.alpha_composite(base, im).convert("RGB").save(out_path)
    return out_path


# ① 图像检测页
pg = uid.ImageDetectPage()
pg.setAttribute(Qt.WA_DontShowOnScreen, True)
pg.resize(1200, 800)
pg.show()
for _ in range(12):
    app.processEvents()
to_rgb(pg.grab(), os.path.join(OUT, "v1433_imagedetect_page.png"))
print("saved v1433_imagedetect_page.png")

# ② 图像检测页把手放大（横向把手 → 竖虚线 + 竖排 5 点）
sp = pg.findChildren(uac._GripSplitter)[0]
h = sp.handle(1)
pos = h.mapTo(pg, QPoint(0, 0))
band = pg.grab(QRect(pos.x() - 40, pos.y() + sp.height() // 2 - 90, 94, 180))
to_rgb(band, os.path.join(TMP, "band.png"))
im = Image.open(os.path.join(TMP, "band.png"))
im = im.resize((im.width * 5, im.height * 2), Image.LANCZOS)
im.save(os.path.join(OUT, "v1433_grip_band_h.png"))
print("saved v1433_grip_band_h.png  handle=%dx%d" % (h.width(), h.height()))

# ③ 演员检测页竖向把手放大（横虚线 + 横排 5 点）
ap = uac.ActorCheckPage()
ap.setAttribute(Qt.WA_DontShowOnScreen, True)
ap.resize(1200, 900)
ap.show()
for _ in range(12):
    app.processEvents()
spv = [s for s in ap.findChildren(uac._GripSplitter)
       if s.orientation() == Qt.Vertical][0]
y0 = 12 + spv.sizes()[0]
to_rgb(ap.grab(QRect(0, y0, ap.width(), 14)), os.path.join(TMP, "bandv.png"))
im2 = Image.open(os.path.join(TMP, "bandv.png"))
im2 = im2.crop((im2.width // 2 - 260, 0, im2.width // 2 + 260, 14))
im2 = im2.resize((im2.width * 4, im2.height * 8), Image.NEAREST)
im2.save(os.path.join(OUT, "v1433_grip_band_v.png"))
print("saved v1433_grip_band_v.png")
# ④ 把手单独渲染到中性深底（14px 宽，放大 3×2 看虚线 + 描边）
# ⚠ 不能用 to_rgb()：把手几乎全透明，自动取底会把「点的颜色」当底色涂满整条。
_tmp = os.path.join(TMP, "handle.png")
h.grab().save(_tmp)
hm = Image.open(_tmp).convert("RGBA")
canvas = Image.new("RGBA", (120, hm.height + 40), (23, 19, 15, 255))
canvas.alpha_composite(hm, (53, 20))
canvas = canvas.convert("RGB").resize(((120) * 3, (hm.height + 40) * 2), Image.LANCZOS)
canvas.save(os.path.join(OUT, "v1433_handle_only.png"))
print("saved v1433_handle_only.png")
print("RENDER_DONE")
