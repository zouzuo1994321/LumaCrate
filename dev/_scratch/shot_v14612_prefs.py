# -*- coding: utf-8 -*-
"""v1.46.12 预览图：偏好导入 / 导出的进度（数据管理页 + 偏好评组特写）。"""
import os
import sys
import tempfile

from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QGroupBox, QMessageBox   # noqa: E402
from PySide6.QtGui import QFontDatabase                              # noqa: E402
from PySide6.QtCore import Qt, QRect                                 # noqa: E402

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db          # noqa: E402
import config as cfg           # noqa: E402

TMP = tempfile.mkdtemp(prefix="lmc_shot_v14612_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

import main_window as mw       # noqa: E402
from ui_settings import SettingsDialog   # noqa: E402

mw.load_style(app)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
OUT = os.path.join(ROOT, "dev", "screenshots")


def on_dark(pix, out_path, bg=(23, 19, 15)):
    tmp = os.path.join(TMP, "x.png")
    pix.save(tmp)
    im = Image.open(tmp).convert("RGBA")
    cv = Image.new("RGBA", im.size, bg + (255,))
    cv.alpha_composite(im)
    cv.convert("RGB").save(out_path)
    return cv.convert("RGB")


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


SettingsDialog.screen = lambda self: _FakeScr()

win = mw.MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
for _ in range(8):
    app.processEvents()

dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1360, 980)
dlg.show()
for _ in range(10):
    app.processEvents()
dlg._show("数据管理")
for _ in range(16):
    app.processEvents()

# ---- 造「正在导入」的样子（真控件、真 QSS，只喂状态） ----
dlg.pref_ex.setEnabled(False)
dlg.pref_im.setEnabled(False)
dlg.pref_stop.setVisible(True)
dlg.pref_stop.setEnabled(True)
dlg.pref_prog_row.setVisible(True)
dlg.pref_bar.setRange(0, 3006)
dlg.pref_bar.setValue(1875)
dlg.pref_status.setText("正在合并影片偏好 1875/3006（已回写 nfo 268）")
dlg.pref_hint.setText("导入中：D:/Backup/流明盒-偏好-20261028-120000.json")
for _ in range(12):
    app.processEvents()

full = on_dark(dlg.grab(), os.path.join(OUT, "v14612_偏好进度.png"))
print("saved v14612_偏好进度.png", full.size)

# ---- 偏好管理组特写 ----
gp = None
for g in dlg.findChildren(QGroupBox):
    t = g.title()
    if t.startswith("偏好管理"):
        gp = g
        break
print("group:", gp.title() if gp else None)
if gp is not None:
    tl = gp.mapTo(dlg, gp.rect().topLeft())
    box = (max(0, tl.x() - 14), max(0, tl.y() - 12),
           min(full.width, tl.x() + gp.width() + 14),
           min(full.height, tl.y() + gp.height() + 14))
    crop = full.crop(box)
    crop = crop.resize((int(crop.width * 1.35), int(crop.height * 1.35)),
                       Image.LANCZOS)
    out = os.path.join(OUT, "v14612_偏好进度_特写.png")
    crop.save(out)
    print("saved v14612_偏好进度_特写.png", crop.size)

# ---- 第二种状态：导入完成 ----
dlg.pref_ex.setEnabled(True)
dlg.pref_im.setEnabled(True)
dlg.pref_stop.setVisible(False)
dlg.pref_prog_row.setVisible(False)
dlg.pref_hint.setText("最近导入：D:/Backup/流明盒-偏好-20261028-120000.json"
                      "（影片命中 3006 · 未匹配 0 · 人物 340 · nfo 写回 415）")
for _ in range(10):
    app.processEvents()
if gp is not None:
    tl = gp.mapTo(dlg, gp.rect().topLeft())
    pix2 = on_dark(dlg.grab(), os.path.join(OUT, "_tmp_done.png"))
    box = (max(0, tl.x() - 14), max(0, tl.y() - 12),
           min(pix2.width, tl.x() + gp.width() + 14),
           min(pix2.height, tl.y() + gp.height() + 14))
    crop = pix2.crop(box)
    crop = crop.resize((int(crop.width * 1.35), int(crop.height * 1.35)),
                       Image.LANCZOS)
    crop.save(os.path.join(OUT, "v14612_偏好完成_特写.png"))
    print("saved v14612_偏好完成_特写.png", crop.size)
print("OK")
