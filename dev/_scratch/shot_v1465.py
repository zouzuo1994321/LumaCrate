# -*- coding: utf-8 -*-
"""v1.46.5 预览出图 + 像素自证。

两件事：
① 状态栏进度条三态（空白槽 / 不确定高亮 / 45% 高亮）—— 并**按像素**证明
   空闲态真的没有任何填充色（不是「看起来灰一点」）。
② 演员刮削页新增的「其他数据源」单选行。

⚠ 所有几何断言前必须 show()；grab() 出来的是透明底图，必须先 alpha_composite
   到底色再存（否则半透明层会被显示成纯白，图会骗人）。
"""
import os
import sys
import tempfile

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TMP = os.path.join(tempfile.gettempdir(), "lmc_shot_v1465")
os.makedirs(TMP, exist_ok=True)
os.makedirs(SHOTS, exist_ok=True)

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QFontDatabase, QColor, QPainter, QImage
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QProgressBar,
)

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import database as db
import applog

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP
db.init_db()

import main_window as mw

mw.load_style(app)
ACCENT = QColor(*mw.ACCENT_RGB)
STATUS_BG = QColor("#241f1b")


# ---------------------------------------------------------------- ① 进度条三态
class BarHost(QWidget):
    """模拟状态栏那一格：深色底 + 居中的 BusyBar。"""

    def __init__(self):
        super().__init__()
        self.setFixedSize(150, 24)
        self.setAutoFillBackground(False)
        self.bar = QProgressBar(self)
        self.bar.setObjectName("BusyBar")
        self.bar.setTextVisible(False)
        self.bar.setFixedSize(110, 6)
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.bar.setProperty("busy", False)
        self.bar.move(20, 9)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), STATUS_BG)


def set_state(host, progress):
    b = host.bar
    if progress is None:
        b.setRange(0, 1)
        b.setValue(0)
        active = False
    elif progress < 0:
        b.setRange(0, 0)
        active = True
    else:
        b.setRange(0, 100)
        b.setValue(progress)
        active = True
    b.setProperty("busy", active)
    b.style().unpolish(b)
    b.style().polish(b)
    app.processEvents()


def accent_pixels(widget):
    """把控件抓图合成到状态栏底色上，数「接近高亮朱红」的像素。"""
    img = widget.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    bg = Image.new("RGB", (w, h), (STATUS_BG.red(), STATUS_BG.green(), STATUS_BG.blue()))
    raw = Image.frombytes("RGBA", (w, h), bytes(img.constBits()))
    bg = Image.alpha_composite(bg.convert("RGBA"), raw).convert("RGB")
    n = 0
    for x in range(w):
        for y in range(h):
            r, g, b = bg.getpixel((x, y))
            if abs(r - ACCENT.red()) < 46 and abs(g - ACCENT.green()) < 46 \
                    and abs(b - ACCENT.blue()) < 46:
                n += 1
    return bg, n


hosts = []
for st in (None, -1, 45):
    h = BarHost()
    h.show()
    set_state(h, st)
    hosts.append((st, h))

print("== 进度条三态 ==")
idle_img, idle_accent = accent_pixels(hosts[0][1])
check1 = idle_accent == 0
print("  [%s] 空闲态零高亮像素（空槽）  高亮像素=%d" % ("✓" if check1 else "✗", idle_accent))
_, mid_accent = accent_pixels(hosts[1][1])
print("  [%s] 不确定态有高亮像素  %d" % ("✓" if mid_accent > 100 else "✗", mid_accent))
_, p45_accent = accent_pixels(hosts[2][1])
print("  [%s] 45%% 确定态有高亮像素  %d" % ("✓" if p45_accent > 100 else "✗", p45_accent))

# 拼三态对比图（纵向，2 倍放大）
ROW_H = 24
canvas = Image.new("RGB", (150, ROW_H * 3), (36, 31, 27))
for i, (st, h) in enumerate(hosts):
    app.processEvents()
    shot, _ = accent_pixels(h)
    canvas.paste(shot, (0, i * ROW_H))
canvas = canvas.resize((canvas.width * 4, canvas.height * 4), Image.NEAREST)
out1 = os.path.join(SHOTS, "v1465_busybar_states.png")
canvas.save(out1)
print("  → %s" % out1)

# ---------------------------------------------------------------- ② 设置页新行
import ui_settings as uis

win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
for _ in range(6):
    app.processEvents()

dlg = uis.SettingsDialog(win)
dlg.resize(1320, 960)
dlg.show()
for _ in range(8):
    app.processEvents()
dlg._show("演员刮削")
for _ in range(12):
    app.processEvents()

g0 = [g for g in dlg.findChildren(QGroupBox)
      if g.title().startswith("演员刮削数据源")]
assert g0, "找不到数据源组框"
box = g0[0]

# 选中「其他数据源」并填一个示例网址，让截图里能看清「选中态 + 可用」
dlg.sc_cf_other.setChecked(True)
dlg.sc_other_url.setText("https://example.com")
dlg._save_other_url()
for _ in range(6):
    app.processEvents()

print()
print("== 其他数据源行 ==")
print("  radio 文案：%r / %r" % (dlg.sc_cf_auto.text(), dlg.sc_cf_other.text()))
print("  输入框启用：%s  测试按钮启用：%s"
      % (dlg.sc_other_url.isEnabled(), dlg.sc_other_test.isEnabled()))
print("  Cookie 目标：%s" % (dlg._cookie_target(),))
widths = box.width() > 0 and dlg.sc_other_url.width()
print("  网址框宽：%d（组框宽 %d）" % (widths, box.width()))

img = box.grab()
w, h = img.width(), img.height()
bg = Image.new("RGB", (w, h), (27, 25, 23))
from PySide6.QtGui import QImage
raw = img.toImage().convertToFormat(QImage.Format_RGBA8888)
bg = Image.alpha_composite(bg.convert("RGBA"),
                           Image.frombytes("RGBA", (w, h), bytes(raw.constBits()))).convert("RGB")
out2 = os.path.join(SHOTS, "v1465_other_source.png")
bg.save(out2)
print("  → %s（%dx%d）" % (out2, w, h))

print("SHOT_V1465_DONE")
