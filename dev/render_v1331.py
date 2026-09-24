# -*- coding: utf-8 -*-
"""v1.33.1 三条反馈的效果图（离屏）。

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1331.py', run_name='__main__')"

产物 → dev/screenshots_v1331/
    01_tagopt_row.png     标签优化：五枚按钮同排（反馈 1）
    02_dedupe_buttons.png 重复检测：已无导出 CSV/JSON（反馈 2）
    03_about_logos.png    「关于」真实平台 logo（反馈 3）
    04_about_logos_zoom.png  联系图标 4 倍放大（看形状细节）

安全：db / config / 日志全指向临时目录，绝不碰真实索引。
"""
import os
import sys
import time
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(ROOT, "dev"))

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1331")
INDEX = os.path.join(TMP, "index_data")
AVATARS = os.path.join(TMP, "people_photos")
OUT = os.path.join(ROOT, "dev", "screenshots_v1331")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(AVATARS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def _wipe(p):
    if not os.path.exists(p):
        return
    import ctypes
    ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
    ctypes.windll.kernel32.DeleteFileW(p)


for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    _wipe(_f)

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

db.init_db()
_s0 = cfg.get_settings()
_s0.scraper["photo_dir"] = AVATARS
_s0.save()

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw

mw.load_style(app)

import shots_lib as SL

MADE = []


def pump(n=8):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


def save(pm, name, scale=1.0, bg=None, crop=None, corner="br"):
    p = os.path.join(OUT, name)
    pm.save(p)
    im = Image.open(p).convert("RGBA")
    if bg is not None:
        base = Image.new("RGBA", im.size, tuple(bg) + (255,))
        im = Image.alpha_composite(base, im)
    im = im.convert("RGB")
    if crop:
        im = im.crop(crop)
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im = SL.watermark(im, corner=corner)
    im.save(p)
    MADE.append(name)
    print("  %-30s %dx%d" % (name, im.width, im.height))


# ============================================================ 工具窗
print("== 工具窗（反馈 1 / 2） ==")
import ui_settings

dlg = ui_settings.SettingsDialog()
dlg.resize(1180, 900)
dlg.show()
pump(16)

# --- 反馈 1：标签优化按钮行 ---
try:
    dlg._show("标签优化")
    pump(24)
    _five = (dlg.btn_to_scan, dlg.btn_to_run, dlg.btn_to_clear,
             dlg.btn_to_exp, dlg.btn_to_imp)
    rows = set()
    xs = []
    ys = []
    for b in _five:
        tl = b.mapTo(dlg, b.rect().topLeft())
        xs.append((b.text(), tl.x()))
        ys.append(tl.y())
    same_row = len(set(ys)) == 1
    print("     五枚按钮 y 坐标：%s → 同排=%s" % (sorted(set(ys)), same_row))
    for t, x in sorted(xs, key=lambda v: v[1]):
        print("       %-14s x=%d" % (t, x))
    # 裁剪整行（含上方分组标题）
    y0 = min(ys) - 52
    y1 = max(ys) + 44
    x0 = min(x for _, x in xs) - 26
    x1 = max(x for _, x in xs) + 260
    save(dlg.grab(), "01_tagopt_row.png", bg=None,
         crop=(max(0, x0), max(0, y0),
               min(dlg.width(), x1), min(dlg.height(), y1)))
except Exception as e:
    import traceback
    print("     标签优化抓图失败：%s" % e)
    traceback.print_exc()

# --- 反馈 2：重复检测按钮区（应只剩「导出/导入结果文件…」） ---
try:
    dlg._show("重复检测")
    pump(24)
    got = [b.text() for b in dlg.findChildren(QPushButton)]
    legacy = [t for t in got if t in ("导出 CSV", "导出 JSON")]
    print("     重复检测页按钮总数 %d；残留 CSV/JSON = %s" % (len(got), legacy))
    anchor = getattr(dlg, "dd_exp_result", None)
    if anchor is not None:
        tr = anchor.parentWidget()
        tl = tr.mapTo(dlg, tr.rect().topLeft())
        save(dlg.grab(), "02_dedupe_buttons.png", bg=None,
             crop=(max(0, tl.x() - 34), max(0, tl.y() - 26),
                   min(dlg.width(), tl.x() + tr.width() + 400),
                   min(dlg.height(), tl.y() + tr.height() + 24)))
except Exception as e:
    import traceback
    print("     重复检测抓图失败：%s" % e)
    traceback.print_exc()

dlg.close()
pump(6)

# ============================================================ 关于（反馈 3）
print("\n== 「关于」真实平台 logo（反馈 3） ==")
ab = mw.AboutDialog()
ab.resize(760, 820)
ab.show()
pump(26)
try:
    cbs = [b for b in ab.findChildren(QPushButton) if b.objectName() == "ContactIcon"]
    print("     联系图标 %d 枚：%s" % (len(cbs), [b.width() for b in cbs]))
    if cbs:
        tr = cbs[0].parentWidget()
        tl = tr.mapTo(ab, tr.rect().topLeft())
        box = (max(0, tl.x() - 250), max(0, tl.y() - 26),
               min(ab.width(), tl.x() + tr.width() + 250),
               min(ab.height(), tl.y() + tr.height() + 26))
        save(ab.grab(), "03_about_logos.png", bg=None, crop=box)
        # 4 倍放大：只看图标条本身，逼出形状细节
        _cbs_geo = []
        for b in cbs:
            p = b.mapTo(ab, b.rect().topLeft())
            _cbs_geo.append((p.x(), p.y(), b.width(), b.height()))
        gx0 = min(g[0] for g in _cbs_geo)
        gy0 = min(g[1] for g in _cbs_geo)
        gx1 = max(g[0] + g[2] for g in _cbs_geo)
        gy1 = max(g[1] + g[3] for g in _cbs_geo)
        save(ab.grab(), "04_about_logos_zoom.png", 4.0,
             crop=(max(0, gx0 - 8), max(0, gy0 - 6),
                   min(ab.width(), gx1 + 8), min(ab.height(), gy1 + 6)),
             corner="tl")
    else:
        save(ab.grab(), "03_about_logos.png", bg=None)
except Exception as e:
    import traceback
    print("     关于抓图失败：%s" % e)
    traceback.print_exc()

ab.close()
pump(6)

print("\n共 %d 张 → %s" % (len(MADE), OUT))
print("版本：%s (Build %s)" % (ver.VERSION, ver.BUILD))
