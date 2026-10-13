# -*- coding: utf-8 -*-
"""v1.40.6 预览出图 —— 四页的「按页自适应高度」对照图。

自证：打印 ui_settings.__file__。
出图注意：QWidget.grab() 是透明底图，必须 alpha_composite 到容器底色再存，
否则 PIL.convert("RGB") 会把半透明显示成纯白，图会骗人。
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

E = r"E:\【01】自研软件\【26-19】本地影视中心"
SRC = os.path.join(E, "src")
sys.path.insert(0, SRC)
os.chdir(E)

OUT = os.path.join(E, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QImage

app = QApplication.instance() or QApplication(sys.argv)
app.setStyle("Fusion")
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"):
    if os.path.isfile(fp):
        QFontDatabase.addApplicationFont(fp)
        break

from main_window import load_style
load_style(app)

import ui_settings
print("[自证] ui_settings:", ui_settings.__file__)

from PIL import Image


def save_widget(w, path, bg=(28, 26, 24)):
    """抓图 → 垫底色 → 存。透明底图必须先合成，否则半透明层会变纯白。"""
    pm = w.grab()
    img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    wpx, hpx = img.width(), img.height()
    ptr = img.constBits()
    raw = bytes(ptr).__bytes__() if not isinstance(ptr, (bytes, bytearray)) else ptr
    bpl = img.bytesPerLine()
    im = Image.frombytes("RGBA", (wpx, hpx), bytes(raw)[:bpl * hpx], "raw", "BGRA", bpl, 1)
    canvas = Image.new("RGBA", im.size, bg + (255,))
    canvas.alpha_composite(im)
    canvas.convert("RGB").save(path)
    print(f"  [出图] {os.path.basename(path)}  {canvas.width}x{canvas.height}")
    return canvas.width, canvas.height


dlg = ui_settings.SettingsDialog()
dlg.show()
app.processEvents()

# ★★★ v1.40.6 第二轮：**离屏平台的「屏幕可用高」只有 800**（`availableGeometry`），
#   于是 `h = min(MAX_H, 800-40) = 760` —— `MAX_H=960` 这条封顶分支**根本走不到**，
#   出图会显示「个性化设置 → 760」（假象）。真机是 2560×1440（可用高 1392），
#   上限 = min(960, 1352) = 960，才是用户看到的真实效果。
#   所以这里把 `screen()` 换成复刻真机的假屏幕，让预览图 == 真机。
from PySide6.QtCore import QRect as _QRect


class _FakeScr:
    def availableGeometry(self):
        return _QRect(0, 0, 2560, 1392)

    def geometry(self):
        return _QRect(0, 0, 2560, 1440)


_fs = _FakeScr()
ui_settings.SettingsDialog.screen = lambda self: _fs
dlg.resize(dlg.width(), dlg.MAX_H)
dlg._program_resize = True
dlg._auto_h = dlg.MAX_H
dlg._user_resized_h = None
dlg._program_resize = False
app.processEvents()
print(f"\n[体检⓪] MIN_H={dlg.MIN_H} MAX_H={dlg.MAX_H} "
      f"minH={dlg.minimumHeight()} maxH={dlg.maximumHeight()} "
      f"（ceil/floor 不等 → 可拉伸）")
print(f"[体检⓪] 已切到「真机口径」假屏幕 2560x1440（可用高 1392）→ 上限 = MAX_H = {dlg.MAX_H}")

# ---------- 四页各出一张 ----------
plan = [
    ("手动修改", "v1406_page_manual.png"),
    ("AI引擎设置", "v1406_page_aiengine.png"),
    ("演员刮削", "v1406_page_scraper.png"),
    ("个性化设置", "v1406_page_personal.png"),
]
rows = []
for key, fname in plan:
    dlg._show(key)
    for _ in range(4):
        app.processEvents()
    pg = dlg.stack.currentWidget()
    inner = pg
    d = 0
    while hasattr(inner, "widget") and inner.widget() is not None and d < 4:
        inner = inner.widget()
        d += 1
    need = dlg._content_height(inner)
    h = dlg.height()
    scrolled = type(dlg.stack.currentWidget()).__name__ == "QScrollArea"
    rows.append((key, need, h, scrolled))
    save_widget(dlg, os.path.join(OUT, fname))

# ---------- 对照表 ----------
print("\n[对照表] 页面 / 内容高 / 切换后窗口高 / 是否页内滚动")
for key, need, h, sc in rows:
    print("   %-12s content=%5d  窗口高=%4d  %s" % (
        key, need, h, "滚动" if sc else "一屏"))
print(f"\n[结论] v1.40.4 的窗口高恒为 min(960, 可用高-40)；本轮改为"
      f" max({dlg.MIN_H}, min({dlg.MAX_H}, content+chrome)) —— "
      f"矮页自动变矮、高页封顶滚动。")

dlg.close()
print("\n[完成] 出图目录:", OUT)
