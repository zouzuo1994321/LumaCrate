# -*- coding: utf-8 -*-
"""v1.42.1 Item 2 实测：5 点 grip 把手的几何 / QSS 干扰 / 渲染离屏核对。

关键疑点：style.qss 通用规则 `QSplitter::handle { width: 1px }` 会不会把
自绘把手压成 1px（导致圆点被裁）。这里量 handle 实际几何并出图。"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QImage, QPainter
from PySide6.QtCore import Qt, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_grip_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import load_style
import ui_actorcheck as uac

load_style(app)
print("accent =", cfg.accent_rgb(cfg.get_settings().accent()))

page = uac.ActorCheckPage()
page.setAttribute(Qt.WA_DontShowOnScreen, True)
page.resize(1200, 860)
page.show()
app.processEvents()

splits = page.findChildren(uac._GripSplitter)
print("grip splitters:", len(splits))
ok = True
for sp in splits:
    print(f"splitter orient={'V' if sp.orientation() == Qt.Vertical else 'H'} "
          f"handleWidth={sp.handleWidth()} sizes={sp.sizes()} count={sp.count()}")
    for i in range(1, sp.count()):
        h = sp.handle(i)
        print(f"  handle({i}): w={h.width()} h={h.height()} "
              f"sizeHint={h.sizeHint().width()}x{h.sizeHint().height()} "
              f"type={type(h).__name__}")
        if h.height() < 6:
            ok = False
            print("  !! handle 高度不足 6px —— 通用 QSS width:1px 疑似生效")

# 渲染竖向把手本体（hover 前 / 强制 hover 后各一张）
sp = splits[0]
h = sp.handle(1)
img = h.grab()
img.save(os.path.join(TMP, "grip_normal.png"))
print("grip_normal:", img.width(), "x", img.height())

h.setAttribute(Qt.WA_UnderMouse, True)
h._hover = True
img2 = h.grab()
img2.save(os.path.join(TMP, "grip_hover.png"))
h.setAttribute(Qt.WA_UnderMouse, False)
h._hover = False

# 整页抓一张，看把手在两个组框之间的位置
full = page.grab()
full.save(os.path.join(TMP, "grip_page.png"))
print("grip_page:", full.width(), "x", full.height())
print("TMP:", TMP)
print("HANDLE_OK" if ok else "HANDLE_BAD")
