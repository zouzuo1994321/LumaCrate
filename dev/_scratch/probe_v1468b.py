# -*- coding: utf-8 -*-
"""v1.46.8 探针：状态栏进度条的「最短可见时长」与「滚动续载也点亮」。

四组判据：
  A 三态像素：空闲 0 / 不确定 >0 / 确定 >0
  B 快闪：set_busy(-1) 后立刻 set_busy(None)，30ms 内仍能看到朱红（旧版这里是 0）
  C 回落：B 之后等 >600ms，必须回到 0（不能卡住高亮）
  D 滚动：媒体墙滚到中段（发生换卡）→ 状态栏出现朱红
"""
import os
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1468b"
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


def spin(ms):
    """推进事件循环 ms 毫秒（QTimer 需要真实时间）。"""
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


def accent_pixels(im):
    n = 0
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            if r > 110 and r - g > 40 and r - b > 35:
                n += 1
    return n


bar = win._busy_bar
FAIL = []


def check(tag, cond, detail=""):
    print("  [%s] %-40s %s" % ("✓" if cond else "✗", tag, detail), flush=True)
    if not cond:
        FAIL.append(tag)


print("== A 三态 ==", flush=True)
for tag, v, want in (("空闲", None, 0), ("不确定(-1)", -1, 1), ("确定(45)", 45, 1)):
    mw.set_busy(v, "探针")
    settle(15)
    n = accent_pixels(img_of(bar))
    ok = (n == 0) if want == 0 else (n > 0)
    check("%s 朱红像素%s" % (tag, "=0" if want == 0 else ">0"), ok, "实测=%d" % n)

print("\n== B 快闪（核心修复点）==", flush=True)
mw.set_busy(None, "")
spin(600)
print("  前置：先回落干净 ->", accent_pixels(img_of(bar)), flush=True)
mw.set_busy(-1, "载入中")
mw.set_busy(None, "")          # 模拟「建一屏卡只要几毫秒」的真实时序
spin(30)
n_fast = accent_pixels(img_of(bar))
check("快闪后 30ms 仍可见朱红", n_fast > 0, "实测=%d（旧版这里是 0）" % n_fast)
img_of(bar).resize((880, 48), Image.NEAREST).save(os.path.join(TMP, "fast_30ms.png"))

print("\n== C 回落（不能卡住高亮）==", flush=True)
spin(700)
n_idle = accent_pixels(img_of(bar))
check("700ms 后回落为空槽", n_idle == 0, "实测=%d" % n_idle)
check("busy 属性已回 False", bool(bar.property("busy")) is False,
      "busy=%s" % bar.property("busy"))

print("\n== D 滚动续载也点亮 ==", flush=True)
wall = win._wall_page(None)
win.stack.addWidget(wall)
win.stack.setCurrentWidget(wall)
spin(400)
g = wall.findChildren(mw.LazyGrid)[0]
sb = g._scrollbar
sb.setValue(int(sb.maximum() * 0.3))
spin(40)                        # 刚换完卡
n_scroll = accent_pixels(img_of(bar))
check("滚动换卡后状态栏有朱红", n_scroll > 0, "实测=%d" % n_scroll)
spin(700)
check("滚动停顿 700ms 后回落", accent_pixels(img_of(bar)) == 0,
      "实测=%d" % accent_pixels(img_of(bar)))
img_of(win.statusBar()).save(os.path.join(TMP, "statusbar_scroll.png"))

print("\n失败项：%s" % (FAIL or "无"), flush=True)
print("PROBE_V1468B_DONE", flush=True)
