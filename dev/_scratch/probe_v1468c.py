# -*- coding: utf-8 -*-
"""v1.46.8 定位：滚动时 set_busy / _render 到底有没有被调用（调用时间线）。"""
import os
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1468c"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import applog

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import main_window as mw

T0 = time.monotonic()
EVENTS = []

_orig_set_busy = mw.set_busy


def traced_set_busy(progress=None, text=""):
    EVENTS.append((round((time.monotonic() - T0) * 1000, 1), "set_busy", progress, text))
    return _orig_set_busy(progress, text)


mw.set_busy = traced_set_busy

_orig_render = mw.LazyGrid._render


def traced_render(self):
    before = (self._win_key, len(self._cards))
    r = _orig_render(self)
    after = (self._win_key, len(self._cards))
    EVENTS.append((round((time.monotonic() - T0) * 1000, 1), "render",
                   "key_changed" if before[0] != after[0] else "same_key",
                   "cards %d->%d" % (before[1], after[1])))
    return r


mw.LazyGrid._render = traced_render

mw.load_style(app)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()


def settle(n=25):
    for _ in range(n):
        app.processEvents()


def spin(ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.004)


def img_of(w):
    im = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    iw, ih = im.width(), im.height()
    bg = Image.new("RGB", (iw, ih), (34, 29, 25))
    raw = Image.frombytes("RGBA", (iw, ih), bytes(im.constBits()))
    return Image.alpha_composite(bg.convert("RGBA"), raw).convert("RGB")


def accent_n(im):
    n = 0
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            if r > 110 and r - g > 40 and r - b > 35:
                n += 1
    return n


bar = win._busy_bar
print("== 建墙页 ==", flush=True)
EVENTS.clear()
wall = win._wall_page(None)
win.stack.addWidget(wall)
win.stack.setCurrentWidget(wall)
for i in range(10):
    spin(100)
    print("  t=%4dms busy=%s range=%d..%d value=%d 朱红=%d"
          % ((i + 1) * 100, bar.property("busy"), bar.minimum(), bar.maximum(),
             bar.value(), accent_n(img_of(bar))), flush=True)

g = wall.findChildren(mw.LazyGrid)[0]
sb = g._scrollbar
print("  scrollbar max=%d  当前=%d" % (sb.maximum(), sb.value()), flush=True)

print("\n== 滚动到 30% ==", flush=True)
EVENTS.clear()
t_mark = round((time.monotonic() - T0) * 1000, 1)
sb.setValue(int(sb.maximum() * 0.3))
for i in range(1, 9):
    spin(25)
    print("  +%3dms busy=%s range=%d..%d 朱红=%d"
          % (i * 25, bar.property("busy"), bar.minimum(), bar.maximum(),
             accent_n(img_of(bar))), flush=True)

print("\n== 事件时间线（相对 t_mark=%s） ==" % t_mark, flush=True)
for e in EVENTS[:40]:
    print("  %.1fms %s %s" % (e[0], e[1], e[2:]), flush=True)

print("\n== 网格状态 ==", flush=True)
print("  _cards=%d  _win_key=%s  _virtual=%s"
      % (len(g._cards), g._win_key, g._virtual), flush=True)
print("PROBE_V1468C_DONE", flush=True)
