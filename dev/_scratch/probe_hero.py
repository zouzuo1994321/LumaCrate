# -*- coding: utf-8 -*-
"""临时探针：离屏渲染 HeroView，定位「字体底部黑色底框」来源。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

import database as db
from ui_hero import HeroView
try:
    qss = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "style.qss")
    if os.path.exists(qss):
        app.setStyleSheet(open(qss, encoding="utf-8").read())
except Exception as e:
    print("qss:", e)

# 找一个有 fanart 的真实条目
cands = db.search_media(limit=100000)
pick = None
for m in cands:
    if (m.get("title") or "").upper().startswith("CEMD-880"):
        pick = m
        break
if pick is None:
    for m in cands:
        if m.get("fanart") and os.path.exists(m["fanart"]):
            pick = m
            break
if pick is None:
    print("no media found, total=", len(cands))
    sys.exit(1)

print("pick:", pick.get("title"))
print("  fanart:", pick.get("fanart"), os.path.exists(pick.get("fanart") or ""))
print("  poster:", pick.get("poster"), os.path.exists(pick.get("poster") or ""))

hv = HeroView(pick)
hv.resize(1900, 1000)
hv.show()
app.processEvents()
for _ in range(6):
    app.processEvents()

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots", "probe_hero.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
pm = hv.grab()
pm.save(out)
print("saved:", out, pm.width(), pm.height())
