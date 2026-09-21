# -*- coding: utf-8 -*-
"""临时探针2：定位详情页横幅中残留的 #14110f 平铺色带来源。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

import database as db
import ui_hero
from PySide6.QtCore import QPoint

qss = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "style.qss")
if os.path.exists(qss):
    app.setStyleSheet(open(qss, encoding="utf-8").read())

pick = None
for m in db.search_media(limit=100000):
    if (m.get("title") or "").upper().startswith("CEMD-880"):
        pick = m
        break
if not pick:
    sys.exit("no media")


def flat_report(tag):
    hv = ui_hero.HeroView(dict(pick))
    hv.resize(1900, 1000)
    hv.show()
    for _ in range(6):
        app.processEvents()
    b = hv.findChild(ui_hero.HeroBanner)
    if b is not None:
        print(f"[{tag}] banner size={b.width()}x{b.height()} "
              f"pixmap={b._pm.width()}x{b._pm.height()} src={b._src}")
    pm = hv.grab()
    im = pm.toImage()
    out = []
    for y in range(60, 460, 20):
        vals = [im.pixelColor(x, y).red() for x in range(60, 1900, 200)]
        flat = (max(vals) - min(vals)) <= 3 and vals[0] == 20
        out.append((y, vals[0], max(vals), "FLAT#14110f" if flat else ""))
    print("---", tag)
    for y, lo, hi, tag2 in out:
        print(f"  y={y:>3} min={lo:>3} max={hi:>3} {tag2}")
    hv.hide()


flat_report("原样（含文字投影）")

# 禁用文字投影
ui_hero._apply_text_shadow = lambda w, **k: w
flat_report("禁用文字投影")

# 恢复并改横幅底色
import importlib
importlib.reload(ui_hero)
_banner_bg = ui_hero.HeroBanner.setStyleSheet
ui_hero.HeroBanner.setStyleSheet = lambda self, *a: _banner_bg(self, "background:#ff00ff;")
flat_report("横幅底色改品红")
