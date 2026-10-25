# -*- coding: utf-8 -*-
"""v1.46.7 预览出图：演员「全部作品」滚到中段与底部仍有卡片（修「卡在 48 部」）。

对比点：修复前 `_scrollbar=None`，卡片只建 0~39/0~47，滚下去整片空白。
现在滚到 2500/中段、拉到底，都应该是满屏海报。
"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
SHOTS = os.path.join(ROOT, "dev", "screenshots")
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_shot_v1467"
os.makedirs(SHOTS, exist_ok=True)
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
import database as db

mw.load_style(app)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()


def settle(n=30):
    for _ in range(n):
        app.processEvents()


def grab(w, path):
    """grab() 是透明底 PNG —— 必须合成到底色，否则半透明层会显示成纯白。"""
    img = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    iw, ih = img.width(), img.height()
    bg = Image.new("RGB", (iw, ih), (22, 19, 16))
    raw = Image.frombytes("RGBA", (iw, ih), bytes(img.constBits()))
    out = Image.alpha_composite(bg.convert("RGBA"), raw).convert("RGB")
    out.save(path)
    print("  → %s (%dx%d)" % (path, iw, ih), flush=True)


conn = db.get_conn()
pid = conn.execute(
    "SELECT p.id, p.name, COUNT(mp.media_id) c FROM people p "
    "JOIN media_people mp ON mp.person_id=p.id WHERE p.role_type='Actor' "
    "GROUP BY p.id ORDER BY c DESC LIMIT 1").fetchone()
print("演员：%s（%d 部）" % (pid[1], pid[2]), flush=True)

page = win._view_actor_detail(pid[0])
win.stack.addWidget(page)
win.stack.setCurrentWidget(page)
settle(45)

g = page.findChildren(mw.LazyGrid)[0]
sb = g._scrollbar
print("grid：total=%d cols=%d sb=%s max=%s"
      % (g._total, g._cols_now, sb is not None, sb.maximum() if sb else "-"), flush=True)

grab(page, os.path.join(SHOTS, "v1467_works_top.png"))

if sb is not None:
    sb.setValue(int(sb.maximum() * 0.5))
    settle(25)
    grab(page, os.path.join(SHOTS, "v1467_works_mid.png"))
    sb.setValue(sb.maximum())
    settle(25)
    grab(page, os.path.join(SHOTS, "v1467_works_tail.png"))
    idx = sorted(g._cards.keys())
    print("尾部：value=%d/%d 末索引=%s/%d"
          % (sb.value(), sb.maximum(), idx[-1] if idx else -1, g._total - 1), flush=True)

print("SHOT_V1467_DONE", flush=True)
