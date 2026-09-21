# -*- coding: utf-8 -*-
"""v1.26.0 定向渲染：三条界面反馈的「改前 / 改后」取证图。

产出 `dev/screenshots_v1260/`：
  01_brand_sub.png      侧栏品牌区特写（3×）—— 副标题不再裁掉末尾的 r
  02_statusbar.png      底部状态栏特写（2×）—— 已接上开源声明
  03_appearance.png     「个性化设置」整页（天青高亮色）
  04_toggles_zhu.png    「导航菜单」开关区特写（朱红）
  05_toggles_qing.png   「导航菜单」开关区特写（天青）
  06_toggles_compare.png 两张开关特写上下并排 —— 轨道色确实跟着高亮色变了

全部用临时库 + 临时 settings.json + 临时日志目录，不污染真实数据。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QGroupBox          # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase, QImage, QPainter, QColor, QLinearGradient  # noqa: E402
from PySide6.QtCore import QRect, Qt                            # noqa: E402

app = QApplication(sys.argv)

TMP = tempfile.mkdtemp(prefix="lmc_render_v1260_")
import database as db          # noqa: E402
import scanner as scanner_mod  # noqa: E402
import config as cfg           # noqa: E402

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import applog  # noqa: E402
_LOG = os.path.join(TMP, "logs")
os.makedirs(_LOG, exist_ok=True)
applog.log_dir = lambda: _LOG

from main_window import MainWindow, load_style  # noqa: E402

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

OUT = os.path.join(ROOT, "dev", "screenshots_v1260")
os.makedirs(OUT, exist_ok=True)


def poster(path, c1, c2, w=158, h=236):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(c1))
    g.setColorAt(1, QColor(c2))
    p.fillRect(QRect(0, 0, w, h), g)
    p.end()
    img.save(path)


LIB = os.path.join(TMP, "我的电影")
os.makedirs(LIB, exist_ok=True)
TITLES = ["乐来越爱你", "沙丘", "星际穿越", "寄生虫", "千与千寻", "海上钢琴师",
          "教父", "天堂电影院", "一一", "花样年华"]
COLORS = ["#2b3a55", "#5a4326", "#1b2a4a", "#26332b", "#3a2b4a",
          "#4a3a2b", "#3a2b2b", "#2b4a4a", "#4a4a2b", "#2b2b4a"]
for i, t in enumerate(TITLES):
    d = os.path.join(LIB, "%s.%d" % (t, 2000 + i))
    os.makedirs(d, exist_ok=True)
    poster(os.path.join(d, "poster.jpg"), COLORS[i], "#0f0d0c")
    with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
        f.write("<movie><title>%s</title><year>%d</year><rating>8.0</rating>"
                "<genre>剧情</genre><plot>预览用简介。</plot><thumb>poster.jpg</thumb>"
                "<actor><name>演员%d</name><role>主角</role></actor></movie>"
                % (t, 2000 + i, i))
    with open(os.path.join(d, "%s.mkv" % t), "w") as f:
        f.write("x" * 1000)

db.init_db()
scanner_mod.scan_library(LIB, library_name="我的电影")
s = cfg.get_settings()
s.add_library("我的电影", "电影", [LIB])
s.save()
cfg._SETTINGS = None

load_style(app)
win = MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
win.resize(1500, 940)
win.show()
app.processEvents()


def wait(ms=320):
    import time
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()
        time.sleep(0.01)


def save(pm, name):
    p = os.path.join(OUT, name)
    pm.save(p)
    print("saved", name, pm.width(), "x", pm.height())
    return p


def set_accent(hexv):
    """换高亮色：走设置对话框那条真实链路（落盘 → 刷新色板 → 刷新开关 → 重载样式表）。"""
    cfg.get_settings().set_accent(hexv)
    if getattr(win, "_settings_dlg", None) is not None:
        win._settings_dlg._paint_accent_btns()
        win._settings_dlg._refresh_toggles()
    win._apply_appearance()
    app.processEvents()


def crop_scale(src_png, box, scale, name):
    from PIL import Image
    im = Image.open(src_png)
    im = im.crop(box)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.NEAREST)
    p = os.path.join(OUT, name)
    im.convert("RGB").save(p, quality=92)
    print("saved", name, im.size)
    return p


wait(400)

# ---------- 1) 侧栏品牌区（3× 特写）
win.go(lambda: win._view_home())
wait(300)
side_png = save(win.sidebar.grab(), "00_sidebar_full.png")
crop_scale(side_png, (0, 0, 186, 74), 3.0, "01_brand_sub.png")

# ---------- 2) 底部状态栏（2× 特写）
sb = win.statusBar()
sb_png = save(sb.grab(), "02_statusbar.png")
crop_scale(sb_png, (0, 0, 700, max(1, sb.height())), 2.0, "02_statusbar_zoom.png")

# ---------- 3) 设置页：开关跟随高亮色
win._open_settings()
dlg = win._settings_dlg
dlg._show("个性化设置")
dlg.resize(1000, 900)
wait(400)

set_accent("#c0392b")
wait(250)
nav = None
# 「导航菜单」分组：按标题找（比按索引稳）
for g in dlg.findChildren(QGroupBox):
    if "导航菜单" in g.title():
        nav = g
        break
if nav is not None:
    zhu = save(nav.grab(), "04_toggles_zhu.png")
else:
    print("[警告] 没找到「导航菜单」分组")
    zhu = save(dlg.grab(), "04_toggles_zhu.png")

set_accent("#3fa9c9")
wait(250)
save(dlg.grab(), "03_appearance.png")
if nav is not None:
    qing = save(nav.grab(), "05_toggles_qing.png")
else:
    qing = save(dlg.grab(), "05_toggles_qing.png")

# ---------- 4) 两张开关特写并排
try:
    from PIL import Image, ImageDraw
    a = Image.open(zhu).convert("RGB")
    b = Image.open(qing).convert("RGB")
    w = max(a.width, b.width)
    pad, bar = 14, 26
    out = Image.new("RGB", (w + pad * 2, a.height + b.height + bar * 2 + pad * 3),
                    (23, 18, 15))
    d = ImageDraw.Draw(out)
    out.paste(a, (pad, bar + pad))
    out.paste(b, (pad, bar + pad + a.height + pad))
    d.text((pad + 2, 6), "ACCENT = #c0392b  (zhu hong / before-fix look)",
           fill=(200, 190, 175))
    d.text((pad + 2, bar + pad + a.height + 4),
           "ACCENT = #3fa9c9  (tian qing / track now follows)",
           fill=(160, 205, 225))
    out.save(os.path.join(OUT, "06_toggles_compare.png"), quality=92)
    print("saved 06_toggles_compare.png", out.size)
except Exception as e:                                  # noqa: BLE001
    print("[警告] 并排图失败：", e)

set_accent("#c0392b")
print("OUT:", OUT)
