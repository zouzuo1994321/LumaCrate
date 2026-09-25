# -*- coding: utf-8 -*-
"""v1.34.1 预览出图：三条修复的「修前 / 修后」对照图。

出图（存到 dev/shots_v1341/）：
  01_autofill_scope_all.png      自动填充面板 · 统计范围=全部媒体库
  02_autofill_scope_fav.png      自动填充面板 · 统计范围=我的收藏（验证高度一致）
  03_autofill_zoom.png           SpinBox 区域放大（验证数字不再贴边）
  04_smart_toolbar.png           智能推荐工具行（验证权重框与「加强」不再挤）
  05_smart_toolbar_zoom.png      工具行右侧放大

关键：grab() 出来的是**透明底**图，必须 alpha_composite 到容器底色再存，
否则半透明层会被 PIL 显示成纯白（图会骗人）。
"""
import io
import os
import sys

LOG = r"C:/Users/zouzu/AppData/Local/Temp/lmc_render_v1341.log"
sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")

ROOT = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1310"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["LMC_NO_SYSMON"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUT = os.path.join(ROOT, "dev", "shots_v1341")
os.makedirs(OUT, exist_ok=True)

from PySide6.QtCore import Qt                                    # noqa: E402
from PySide6.QtGui import QFontDatabase, QFont, QColor, QImage   # noqa: E402
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout,  # noqa: E402
                               QHBoxLayout, QLabel, QPushButton)

app = QApplication(sys.argv)
for f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.isfile(f):
        QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei UI", 9))

import main_window as mw                                         # noqa: E402
mw.load_style(app)
import ui_settings as uis                                        # noqa: E402

BG = QColor(24, 20, 18)          # 与视觉稿一致的容器底色


def save(widget, name, bg=BG):
    """grab → 把透明底压到 bg 上再存（不做这步会在看图时变成纯白）。"""
    from PIL import Image
    img = widget.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    raw = bytes(ptr) if ptr is not None else b""
    if len(raw) < w * h * 4:
        raw = img.bits().tobytes()
    pil = Image.frombytes("RGBA", (w, h), raw[:w * h * 4], "raw", "RGBA")
    canvas = Image.new("RGB", (w, h), (bg.red(), bg.green(), bg.blue()))
    canvas.paste(pil, (0, 0), pil)
    p = os.path.join(OUT, name)
    canvas.save(p)
    print("  出图 %-32s %dx%d" % (name, w, h), flush=True)
    return p


def zoom(src_name, box, out_name, scale=3):
    from PIL import Image
    im = Image.open(os.path.join(OUT, src_name))
    c = im.crop(box)
    c = c.resize((c.width * scale, c.height * scale), Image.LANCZOS)
    c.save(os.path.join(OUT, out_name))
    print("  放大 %-32s %dx%d" % (out_name, c.width, c.height), flush=True)


def pump(n=6):
    for _ in range(n):
        app.processEvents()


print("== ① ② AutoFillDialog ==")
dlg = uis.AutoFillDialog()
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.show()
pump()
dlg.cb_scope.setCurrentIndex(0)
pump()
print("  scope=全部媒体库  dlg=%dx%d" % (dlg.width(), dlg.height()))
save(dlg, "01_autofill_scope_all.png")

# SpinBox 区域：从「维度」表头到最后一行的字体框下方
p_top = dlg.dim_rows["tag"][1]
r0 = p_top.mapTo(dlg, p_top.rect().topLeft())
zoom("01_autofill_scope_all.png",
     (max(0, r0.x() - 90), max(0, r0.y() - 26),
      min(dlg.width(), r0.x() + 420), r0.y() + 210),
     "03_autofill_zoom.png", scale=3)

dlg.cb_scope.setCurrentIndex(1)
pump()
print("  scope=我的收藏    dlg=%dx%d" % (dlg.width(), dlg.height()))
save(dlg, "02_autofill_scope_fav.png")
dlg.close()
pump()

print()
print("== ③ 智能推荐工具行 ==")
win = mw.MainWindow()
win.resize(1920, 1080)
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.show()
pump()

w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
ph = QLabel("（网格占位）"); ph.setFixedHeight(120); v.addWidget(ph)
tb = QWidget(); tbl = QHBoxLayout(tb)
tbl.setContentsMargins(0, 0, 0, 0); tbl.setSpacing(8)
info = QLabel("<b>AI 智能算法（本地 Ollama 扩词）</b> · 依据 381 部收藏影片"
              "（23038 部高分） + 143 位收藏的演员/导演 · 候选 47,571 部")
info.setStyleSheet("color:#c9bda7;font-size:12px;")
info.setMinimumWidth(0)
tbl.addWidget(info, 1)
win._smart_guides = []
win._guide_bar(tbl)
win._refresh_guides()
again = QPushButton("换一批"); again.setObjectName("Ghost")
tbl.addWidget(again)
v.insertWidget(0, tb)

page = win._page("智能推荐（24 部）", w)
page.resize(1734, 220)
page.setAttribute(Qt.WA_DontShowOnScreen, True)
page.show()
pump(8)
print("  工具行 tb=%dx%d" % (tb.width(), tb.height()))
save(page, "04_smart_toolbar.png")

# 工具行右侧放大（含权重框 + 加强/清空 + 换一批）
gw = win.guide_w
gr = gw.mapTo(tb, gw.rect().topLeft())
x0 = max(0, gr.x() - 300)
zoom("04_smart_toolbar.png",
     (x0, max(0, gr.y() - 22), tb.width(), gr.y() + 62),
     "05_smart_toolbar_zoom.png", scale=3)

# 再加一条引导，看 chip 状态（顺带验证 chips 不挤压输入框）
win._smart_guides = [{"token": "a:さつき芽衣", "dim": "actor",
                      "key": "さつき芽衣", "weight": 2.0}]
win._refresh_guides()
pump()
save(page, "06_smart_toolbar_with_chip.png")

page.close(); win.close()

print()
print("完成 →", OUT)
