# -*- coding: utf-8 -*-
"""v1.43.0 预览出图：① 元数据管理页（含偏好管理）② 演员刮削页（6 源 + gfriends +
ThePornDB Key + 演员库清理）③ 演员库清理对话框。
grab 是透明底图 → 先 alpha_composite 到采样出的容器底色再存 RGB。"""
import os
import sys
import tempfile
from collections import Counter

from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QRect

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg

TMP = tempfile.mkdtemp(prefix="lmc_render_v1430_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow, load_style
from ui_settings import SettingsDialog
import ui_cleanup as uic

load_style(app)
OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)


def to_rgb(pix, out_path, fallback=(32, 29, 27)):
    tmp = os.path.join(TMP, "raw.png")
    pix.save(tmp)
    im = Image.open(tmp).convert("RGBA")
    cnt = Counter()
    for y in range(0, im.height, 5):
        for x in range(0, im.width, 7):
            p = im.getpixel((x, y))
            if p[3] > 200:
                cnt[p[:3]] += 1
    bg = cnt.most_common(1)[0][0] if cnt else fallback
    base = Image.new("RGBA", im.size, bg + (255,))
    Image.alpha_composite(base, im).convert("RGB").save(out_path)
    return out_path


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


SettingsDialog.screen = lambda self: _FakeScr()

# 造几条数据让清理对话框有内容、偏好统计有数
conn = db.get_conn()
for i, t in enumerate(("MIDE-823 テスト", "SSIS-001 サンプル")):
    conn.execute("INSERT INTO media (kind,title,file_path,favorite,play_count,user_rating,library)"
                 " VALUES ('movie',?,?,?,?,?,'测试库')",
                 (t, os.path.join(TMP, "lib", f"{t.split()[0]}.mp4"),
                  1 if i == 0 else 0, 3 if i == 0 else 0, 9.0 if i == 0 else 0))
for n, r in (("三上悠亜", "Actor"), ("宮下玲奈", "Actor"), ("監督テスト", "Director")):
    conn.execute("INSERT INTO people (name, role_type, favorite) VALUES (?,?,?)",
                 (n, r, 1 if n == "三上悠亜" else 0))
for n in ("无作品演员A", "无作品演员B", "无作品导演C"):
    conn.execute("INSERT INTO people (name, role_type) VALUES (?,?)",
                 (n, "Director" if n.endswith("导演C") else "Actor"))
conn.commit()

win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
for _ in range(10):
    app.processEvents()

# ① 元数据管理
dlg._show("数据与日志")
for _ in range(14):
    app.processEvents()
to_rgb(dlg._pg_data.grab() if not hasattr(dlg._pg_data, "widget") else dlg.grab(),
       os.path.join(OUT, "v1430_data_page.png"))
print("saved v1430_data_page.png")

# ② 演员刮削
dlg._show("演员刮削")
for _ in range(14):
    app.processEvents()
to_rgb(dlg.grab(), os.path.join(OUT, "v1430_scraper_page.png"))
print("saved v1430_scraper_page.png  sources=%d h=%d"
      % (dlg.src_list.count(), dlg.src_list.height()))

# ③ 演员库清理对话框
clean = uic.PeopleCleanDialog(dlg)
clean.setAttribute(Qt.WA_DontShowOnScreen, True)
clean.resize(760, 560)
clean.show()
for _ in range(10):
    app.processEvents()
clean._set_all(True)
app.processEvents()
to_rgb(clean.grab(), os.path.join(OUT, "v1430_people_clean.png"))
print("saved v1430_people_clean.png  rows=%d" % clean.list.count())
clean.close()
print("RENDER_DONE")
