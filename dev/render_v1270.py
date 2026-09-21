# -*- coding: utf-8 -*-
"""v1.27.0 定向出图 —— 启动画面 / 关于 / 侧栏底部（数据统计 + 实时状态）

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1270.py', run_name='__main__')"

产物：dev/screenshots_v1270/
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

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1270")
INDEX = os.path.join(TMP, "index_data")
OUT = os.path.join(ROOT, "dev", "screenshots_v1270")
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
os.environ["LMC_NO_SYSMON"] = "1"

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
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw
import splash as splash_mod

mw.load_style(app)


def pump(n=8):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


SIDE_BG = (12, 10, 9)          # QFrame#Sidebar 的底色，给透明底的面板抓图垫底用


def _flatten(p, bg):
    """面板是透明底抓的图 —— 直接 convert('RGB') 会把 10% 白的轨道显示成纯白。
    必须按 alpha 合成到侧栏底色上，才和真机上看到的一致。"""
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
    print("  %-30s %dx%d  %d B" % (name, im.width, im.height, os.path.getsize(p)))
    return p


def crop_scale(src_png, box, name, scale=3.0):
    im = Image.open(src_png).convert("RGB")
    c = im.crop(box)
    c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
    p = os.path.join(OUT, name)
    c.save(p)
    print("  %-30s %dx%d  %d B" % (name, c.width, c.height, os.path.getsize(p)))
    return p


print("== 出图 v1.27.0 ==")

# ---------------------------------------------------------------- 00 启动画面
sp = splash_mod.SplashScreen()
sp.setProgress(100, "准备就绪")
pm = QPixmap(sp.W, sp.H)
pm.fill(Qt.transparent)
sp.render(pm)
p00 = save(pm, "00_splash.png")
save(pm, "00_splash_2x.png", 2.0)

sp2 = splash_mod.SplashScreen()
sp2.setProgress(46, "正在载入界面样式…")
pm2 = QPixmap(sp2.W, sp2.H)
pm2.fill(Qt.transparent)
sp2.render(pm2)
save(pm2, "01_splash_mid.png")

# ---------------------------------------------------------------- 02 关于框
dlg = mw.AboutDialog()
dlg.resize(560, dlg.minimumHeight())
dlg.show()
pump(6)
save(dlg.grab(), "02_about.png", 1.6)
dlg.close()

# ---------------------------------------------------------------- 03 侧栏底部
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(12)
side = win.sidebar
panel = win.sysmon

# 真实采样灌进去（临时库没有影片，统计数字手动摆成真机的样子，好看出真实排版）
m = sysmon.SysMetrics()
m.sample()
time.sleep(0.45)
live = m.sample()
live.update(sysmon.probe_ai())
panel.apply(live)
win.stat_label.setText("电影 48083 · 剧集 0\n分集 0 · 演员 7127")
pump(6)
print("     实时采样：cpu=%.1f mem=%.1f gpu=%s ollama=%s model=%s"
      % (live.get("cpu") or -1, live.get("mem") or -1, live.get("gpu"),
         live.get("ollama_on"), live.get("model")))

sb_png = save(side.grab(), "03_sidebar_full.png")
# 侧栏底部 262px（数据统计 + 实时状态）
box = (0, max(0, side.height() - 262), side.width(), side.height())
crop_scale(sb_png, box, "04_sidebar_bottom_3x.png", 3.0)
crop_scale(sb_png, (0, 0, side.width(), 60), "05_brand_3x.png", 3.0)
save(panel.grab(), "06_sysmon_live_3x.png", 3.0, bg=SIDE_BG)

# ---------------------------------------------------------------- 07 两种高亮色对照
FAKE = {"cpu": 42.0, "mem": 71.0, "gpu": 88.0,
        "gpu_name": "NVIDIA GeForce RTX 4070 SUPER", "gpu_mem": (2435.0, 12282.0),
        "net_on": True, "net_up": 153.0, "net_down": 12.5,
        "ollama_on": True, "model": "qwen3.5:4b", "model_ok": True}
old = mw.ACCENT_RGB
for tag, rgb in (("zhu", (192, 57, 43)), ("qing", (63, 169, 201))):
    mw.ACCENT_RGB = rgb
    panel.apply(dict(FAKE))
    pump(3)
    save(panel.grab(), "07_sysmon_%s_3x.png" % tag, 3.0, bg=SIDE_BG)
mw.ACCENT_RGB = old

# 并排对照
a = Image.open(os.path.join(OUT, "07_sysmon_zhu_3x.png")).convert("RGB")
b = Image.open(os.path.join(OUT, "07_sysmon_qing_3x.png")).convert("RGB")
gap = 24
canvas = Image.new("RGB", (a.width + b.width + gap * 3, max(a.height, b.height) + gap * 2),
                   SIDE_BG)
canvas.paste(a, (gap, gap))
canvas.paste(b, (gap * 2 + a.width, gap))
cp = os.path.join(OUT, "08_sysmon_compare.png")
canvas.save(cp)
print("  %-30s %dx%d  %d B" % ("08_sysmon_compare.png", canvas.width, canvas.height,
                               os.path.getsize(cp)))

# ---------------------------------------------------------------- 09 整窗
win.resize(1600, 900)
pump(10)
save(win.grab(), "09_window_1600.png")
win.close()
pump(6)

print("输出目录：", OUT)
