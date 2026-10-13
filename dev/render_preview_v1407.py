# -*- coding: utf-8 -*-
"""v1.40.7 预览出图：默认 1320×960，逐页抓图。

★ 假屏幕复刻真机（2560×1392）。
★ `QWidget.grab()` 是透明底图 → 必须 alpha_composite 到容器底色再存。
"""
import os
import sys

E = "E:/\u301001\u3011\u81ea\u7814\u8f6f\u4ef6/\u301026-19\u3011\u672c\u5730\u5f71\u89c6\u4e2d\u5fc3"
sys.path.insert(0, os.path.join(E, "src"))
os.chdir(E)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFontDatabase, QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QScrollArea

app = QApplication(sys.argv)
for fp in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    try:
        QFontDatabase.addApplicationFont(fp)
    except Exception:
        pass

import ui_settings
from main_window import load_style
print("MODULE:", ui_settings.__file__)
load_style(app)

class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)
    def geometry(self):
        return QRect(0, 0, 2560, 1440)

_fs = _FakeScr()
ui_settings.SettingsDialog.screen = lambda self: _fs

OUT = os.path.join(E, "dev", "screenshots")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

dlg = ui_settings.SettingsDialog()
dlg.show()
app.processEvents()

print("窗口尺寸: %dx%d" % (dlg.width(), dlg.height()))
print("最小尺寸: %dx%d" % (dlg.minimumWidth(), dlg.minimumHeight()))

# 容器底色（不垫底色的话 PNG 是透明的，转 RGB 会变纯白骗人）
BG = QColor(24, 22, 20)


def save_widget(w, path):
    pm = w.grab()                       # QPixmap
    img = pm.toImage()                  # -> QImage
    if img.isNull():
        print("  !! grab 失败", path)
        return
    out = QImage(img.size(), QImage.Format_RGB32)
    out.fill(BG)
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    out.save(path)
    print("  -> %s  %dx%d" % (os.path.basename(path), out.width(), out.height()))


PAGES = [("personal", "个性化设置"), ("manual", "手动修改"),
         ("scraper", "演员刮削"), ("actorcheck", "演员检测"),
         ("data", "数据与日志")]

for slug, key in PAGES:
    dlg._show(key)
    app.processEvents()
    save_widget(dlg, os.path.join(OUT, "v1407_win_%s.png" % slug))

# 拉宽到 1900×1100 → 验证内容冻结（两侧留白、组框宽度不变）
dlg.resize(1900, 1100)
app.processEvents()
dlg._show("演员刮削")
app.processEvents()
save_widget(dlg, os.path.join(OUT, "v1407_win_wide_scraper.png"))
print("拉伸后窗口: %dx%d" % (dlg.width(), dlg.height()))

print("DONE")
