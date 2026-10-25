# -*- coding: utf-8 -*-
"""v1.46.8 探针：状态栏 BusyBar 三态的朱红像素数（空闲应为 0，载入/缓存应 >0）。"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1468"
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

mw.load_style(app)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()


def settle(n=25):
    for _ in range(n):
        app.processEvents()


def img_of(w):
    im = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    iw, ih = im.width(), im.height()
    bg = Image.new("RGB", (iw, ih), (34, 29, 25))
    raw = Image.frombytes("RGBA", (iw, ih), bytes(im.constBits()))
    return Image.alpha_composite(bg.convert("RGBA"), raw).convert("RGB")


def accent_pixels(im):
    """统计「偏朱红」像素：红通道明显高于绿/蓝，且红通道够亮。"""
    n = 0
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            if r > 110 and r - g > 40 and r - b > 35:
                n += 1
    return n


bar = win._busy_bar
print("bar size:", bar.width(), "x", bar.height(), flush=True)
print("初始 busy 属性:", bar.property("busy"), "range:", bar.minimum(), bar.maximum(),
      "value:", bar.value(), flush=True)

cases = [("idle", None), ("indeterminate(-1)", -1), ("progress(45)", 45), ("idle again", None)]
for tag, v in cases:
    mw.set_busy(v, "探针")
    settle(20)
    im = img_of(bar)
    print("[%-18s] busy属性=%-5s range=%d..%d value=%-3d 朱红像素=%d"
          % (tag, bar.property("busy"), bar.minimum(), bar.maximum(), bar.value(),
             accent_pixels(im)), flush=True)
    im.resize((im.width * 4, im.height * 4), Image.NEAREST).save(
        os.path.join(TMP, "busybar_%s.png" % tag.split("(")[0].strip().replace(" ", "_")))

# 再量一次真实状态栏局部（保证不是单控件裁切问题）
mw.set_busy(-1, "探针")
settle(20)
sb = win.statusBar()
row = img_of(sb)
print("状态栏尺寸:", row.width(), "x", row.height(), "朱红像素=", accent_pixels(row), flush=True)
row.save(os.path.join(TMP, "statusbar_busy.png"))

print("PROBE_V1468_DONE", flush=True)
