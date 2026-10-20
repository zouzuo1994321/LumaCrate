# -*- coding: utf-8 -*-
"""v1.42.1 预览出图：① 刮削页数据源三行紧凑；② 演员检测页 5 点 grabber（整页 + 把手带放大）。
离屏。grab 是透明底图 → 先 alpha_composite 到采样出的容器底色再存 RGB。"""
import os
import sys
import tempfile
from collections import Counter

from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QGroupBox
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtCore import Qt, QPoint, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_render_v1421_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow, load_style
import ui_actorcheck as uac
from ui_settings import SettingsDialog

load_style(app)
OUT = os.path.join(ROOT, "dev", "_scratch")


def to_rgb(pix, out_path, fallback=(32, 29, 27)):
    """grab → 贴底色 → 直接存到 out_path（不跨盘 move）。"""
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
    out = Image.alpha_composite(base, im).convert("RGB")
    out.save(out_path)
    return out_path


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


SettingsDialog.screen = lambda self: _FakeScr()

# ---------- ① 刮削页 ----------
win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
app.processEvents()
for k, b in dlg.sub_btns.items():
    if "刮削" in k:
        b.click()
        break
app.processEvents()
pg = dlg._pg_scraper
seen = 0
while hasattr(pg, "widget") and seen < 4:
    inner = pg.widget()
    if inner is None:
        break
    pg = inner
    seen += 1
to_rgb(pg.grab(), os.path.join(OUT, "v1421_scraper_page.png"))
print("saved v1421_scraper_page.png", pg.width(), "x", pg.height())

# ---------- ② 演员检测页 ----------
page = uac.ActorCheckPage()
page.setAttribute(Qt.WA_DontShowOnScreen, True)
page.resize(1200, 860)
page.show()
app.processEvents()
to_rgb(page.grab(), os.path.join(OUT, "v1421_actorcheck_page.png"))
print("saved v1421_actorcheck_page.png")

# 把手带放大（splitter 布局 y=12+sizes[0]，handle 高 14）
sp = page.findChildren(uac._GripSplitter)[0]
y0 = 12 + sp.sizes()[0]
band = page.grab(QRect(0, y0, page.width(), 14))
to_rgb(band, os.path.join(TMP, "band.png"))
im = Image.open(os.path.join(TMP, "band.png"))
im = im.crop((im.width // 2 - 260, 0, im.width // 2 + 260, 14))
im = im.resize((im.width * 4, im.height * 8), Image.NEAREST)
im.save(os.path.join(OUT, "v1421_grip_band.png"))
print("saved v1421_grip_band.png")
print("RENDER_DONE")
