# -*- coding: utf-8 -*-
"""v1.46.2 验证：① 切页后是否还有空白顶层小窗 ② 滚动后是否还有大片空白间隙。"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"   # 需要 grab，离屏即可
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt
from PIL import Image

app = QApplication(sys.argv)
QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")

import database as db
import config as cfg

db.db_path = lambda: os.path.join(ROOT, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(tempfile.mkdtemp(), "s.json")
cfg._SETTINGS = None
db.init_db()

import main_window as mw

mw.load_style(app)
w = mw.MainWindow()
w.setAttribute(Qt.WA_DontShowOnScreen, True)
w.resize(1920, 1080)
w.show()
for _ in range(10):
    app.processEvents()


def tops():
    return ["%s(%r %dx%d)" % (type(t).__name__, t.windowTitle()[:12], t.width(), t.height())
            for t in app.topLevelWidgets() if t is not w and t.isVisible()]


lib = (cfg.get_settings().libraries or [{}])[0].get("name") or "Javlibrary"
print("== 切页 ==")
for i in range(3):
    for tag, fn in (("全部", lambda: w._wall_page("全部")),
                    ("媒体库", lambda: w._wall_page(lib, {"library": lib})),
                    ("演员", w._view_actors),
                    ("导演", w._view_directors)):
        w.go(fn)
        for _ in range(8):
            app.processEvents()
    print(" 第%d轮 → 额外顶层: %s" % (i + 1, tops() or "无"))

print("== 滚动后空白间隙 ==")
w.go(lambda: w._wall_page("全部"))
for _ in range(12):
    app.processEvents()
pg = w.stack.currentWidget()
lg = pg.widget().findChildren(mw.LazyGrid)[0]
sb = pg.verticalScrollBar()
sb.setValue(int(sb.maximum() * 0.4))
for _ in range(10):
    app.processEvents()
lg._render()
for _ in range(6):
    app.processEvents()

p = os.path.join(tempfile.mkdtemp(), "page.png")
pg.grab().save(p)
im = Image.open(p).convert("L")
wpx, hpx = im.size
# 只看内容区（跳过顶部工具行/标题）
blank_runs = []
run = 0
for y in range(90, hpx):
    row = [im.getpixel((x, y)) for x in range(40, wpx - 60, 20)]
    var = max(row) - min(row)
    if var <= 6:
        run += 1
    else:
        if run >= 60:
            blank_runs.append((y - run, run))
        run = 0
if run >= 60:
    blank_runs.append((hpx - run, run))
print(" 图 %dx%d | 连续空白带(≥60px): %s" % (wpx, hpx,
      ["y=%d h=%d" % r for r in blank_runs] or "无"))
print(" 卡片数=%d 窗口=%s" % (len(lg._cards), lg._window))
w.close()
print("PROBE2_DONE")
