# -*- coding: utf-8 -*-
"""v1.28.0 定向出图 —— 「外观」里的两个开关 / 侧栏开与关对比 / 两处可点热区

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1280.py', run_name='__main__')"

产物：dev/screenshots_v1280/
安全：db / config / 日志全部指向临时目录，不动真实索引与配置。
"""
import io
import os
import sys
import time
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1280")
INDEX = os.path.join(TMP, "index_data")
OUT = os.path.join(ROOT, "dev", "screenshots_v1280")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(OUT, exist_ok=True)
for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    try:
        os.remove(_f)
    except OSError:
        pass

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ.pop("LMC_NO_SYSMON", None)      # 侧栏那张要真采样

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import version as ver
import sysmon

db.init_db()

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import QApplication, QGroupBox, QWidget

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw
from ui_settings import SettingsDialog

mw.load_style(app)


def pump(n=8):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


SIDE_BG = (12, 10, 9)          # QFrame#Sidebar 底色，透明底抓图要垫它


def _flatten(p, bg):
    im = Image.open(p).convert("RGBA")
    if bg is not None:
        base = Image.new("RGBA", im.size, tuple(bg) + (255,))
        im = Image.alpha_composite(base, im)
    return im.convert("RGB")


def save(pm, name, scale=1.0, bg=None):
    p = os.path.join(OUT, name)
    pm.save(p)
    im = _flatten(p, bg)
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im.save(p)
    print("  %-32s %dx%d  %d B" % (name, im.width, im.height, os.path.getsize(p)))
    return p


def hover(w, on=True):
    """强制控件进入 :hover —— QStyleSheetStyle 的 State_MouseOver 直接读 WA_UnderMouse。"""
    w.setAttribute(Qt.WA_UnderMouse, bool(on))
    w.update()
    pump(4)


def mean_lum(pm, bg=SIDE_BG):
    """平均亮度。**必须先垫底色再算** —— 抓图是透明底，直接读像素拿到的是
    (0,0,0,0)，算出来的数没有意义（第一版就是这么误报的）。"""
    _tmp = os.path.join(TMP, "_lum_probe.png")
    pm.save(_tmp)
    im = _flatten(_tmp, bg)
    px = im.load()
    tot = n = 0
    for y in range(0, im.height, 3):
        for x in range(0, im.width, 3):
            r, g, b = px[x, y]
            tot += r + g + b
            n += 1
    return tot / max(1, n * 3)


def _flatten(src, bg):
    """src 可以是路径或文件对象。"""
    im = Image.open(src).convert("RGBA")
    if bg is not None:
        base = Image.new("RGBA", im.size, tuple(bg) + (255,))
        im = Image.alpha_composite(base, im)
    return im.convert("RGB")


print("== 出图 v1.28.0 ==")

# ------------------------------------------------- 00 / 01 侧栏：两块开 vs 关
s = cfg.get_settings()
s.set_appearance(show_stats=True, show_sysmon=True)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(14)
win.stat_label.setText("电影 48083 · 剧集 0\n分集 0 · 演员 7127")
m = sysmon.SysMetrics()
m.sample()
time.sleep(0.45)
live = m.sample()
live.update(sysmon.probe_ai())
win.sysmon.apply(live)
pump(8)
print("     实时采样：cpu=%.1f mem=%.1f gpu=%s ollama=%s model=%s"
      % (live["cpu"], live["mem"], live["gpu"], live["ollama_on"], live.get("model")))
side_on = win.sidebar.grab()
save(side_on, "00_sidebar_on.png", bg=SIDE_BG)

s.set_appearance(show_stats=False, show_sysmon=False)
win._apply_settings()
pump(14)
side_off = win.sidebar.grab()
save(side_off, "01_sidebar_off.png", bg=SIDE_BG)

# 并排对比
a = _flatten(os.path.join(OUT, "00_sidebar_on.png"), SIDE_BG)
b = _flatten(os.path.join(OUT, "01_sidebar_off.png"), SIDE_BG)
gap = 16
cmp_im = Image.new("RGB", (a.width + gap + b.width, max(a.height, b.height)), (18, 15, 13))
cmp_im.paste(a, (0, 0))
cmp_im.paste(b, (a.width + gap, 0))
cmp_im.save(os.path.join(OUT, "02_sidebar_compare.png"))
print("  %-32s %dx%d  %d B" % ("02_sidebar_compare.png", cmp_im.width, cmp_im.height,
                               os.path.getsize(os.path.join(OUT, "02_sidebar_compare.png"))))

# 恢复两块并重建
s.set_appearance(show_stats=True, show_sysmon=True)
win._apply_settings()
pump(16)
win.stat_label.setText("电影 48083 · 剧集 0\n分集 0 · 演员 7127")
win.sysmon.apply(live)
pump(8)

# ------------------------------------------------- 03 「外观」设置页（两个开关）
dlg = SettingsDialog(win)
dlg.show()
pump(16)
box = None
for g in dlg.findChildren(QGroupBox):
    if g.title() == "外观":
        box = g
        break
if box is not None:
    # 「外观」组本身是半透明面板 —— 离屏没有底衬，直接 convert("RGB") 会是一片惨白，
    # 跟真机完全不像。垫侧栏同款深底（真机是模糊剧照底衬，这里取最接近的深色）。
    save(box.grab(), "03_settings_appearance_2x.png", 2.0, bg=SIDE_BG)
    c = box.findChild(QWidget)
    print("     「外观」组尺寸 %dx%d" % (box.width(), box.height()))
else:
    print("     !! 没找到「外观」组")
dlg.close()

# ------------------------------------------------- 04 品牌区（含悬停提亮）
brand = win.sidebar.findChild(QWidget, "BrandBox")
hover(brand, False)
plain = brand.grab()
save(plain, "04_brand_normal_3x.png", 3.0, bg=SIDE_BG)
hover(brand, True)
lit = brand.grab()
save(lit, "05_brand_hover_3x.png", 3.0, bg=SIDE_BG)
l0, l1 = mean_lum(plain), mean_lum(lit)
print("     品牌区悬停前后平均亮度：%.3f → %.3f（差 %+.3f）" % (l0, l1, l1 - l0))
hover(brand, False)

# ------------------------------------------------- 06 底部状态栏（含悬停提亮）
sb = win.statusBar()
FOOT_W = 700          # 底部文案只占左边一小段，整条 1920 缩出来字太小
hover(sb, False)
f0 = sb.grab().copy(0, 0, FOOT_W, sb.height())
save(f0, "06_footer_normal_3x.png", 3.0, bg=SIDE_BG)
l0 = mean_lum(f0)
hover(sb, True)
f1 = sb.grab().copy(0, 0, FOOT_W, sb.height())
save(f1, "07_footer_hover_3x.png", 3.0, bg=SIDE_BG)
l1 = mean_lum(f1)
print("     底部状态栏悬停前后平均亮度：%.3f → %.3f（差 %+.3f）" % (l0, l1, l1 - l0))
hover(sb, False)

# ------------------------------------------------- 08 整窗
pump(8)
save(win.grab(), "08_window_1600.png", bg=None)

win.close()
pump(6)
print("输出目录：", OUT)
