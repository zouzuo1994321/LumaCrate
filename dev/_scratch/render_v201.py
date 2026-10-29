# -*- coding: utf-8 -*-
"""v2.0.1 七条反馈的离屏出图（QT_QPA_PLATFORM=windows，force Fusion —— 与真机同路径）。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout,
                               QSpinBox, QDoubleSpinBox, QCheckBox, QLabel,
                               QStyleFactory)
from PySide6.QtGui import QImage, QPainter, QPixmap, QColor, QFontDatabase
from PySide6.QtCore import Qt

OUT = os.path.join(ROOT, "docs", "preview")
os.makedirs(OUT, exist_ok=True)

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setStyle(QStyleFactory.create("Fusion"))

import main_window as mw
mw.load_style(app)


def save(w, name, bg="#18181b", pad=0):
    """抓图并按底色合成（QWidget.grab 是透明底，直接存会变白底骗人）。"""
    pm = w.grab()
    im = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    canvas = QImage(im.width() + pad * 2, im.height() + pad * 2, QImage.Format_ARGB32)
    canvas.fill(QColor(bg))
    p = QPainter(canvas)
    p.drawImage(pad, pad, im)
    p.end()
    path = os.path.join(OUT, name)
    canvas.save(path)
    print("saved", path, canvas.width(), "x", canvas.height())
    return path


# ---------- ① 「窗口透明度」那一行 ----------
import ui_settings as uis
dlg = uis.SettingsDialog(None)
dlg.resize(uis.SettingsDialog.DEF_W, uis.SettingsDialog.DEF_H)
dlg.show()
app.processEvents()
dlg._show("外观")
app.processEvents()
row = dlg.op_slider.parentWidget()
save(row, "v201_slider_row.png", bg="#18181b", pad=6)
print("  op_slider:", dlg.op_slider.size(), "row:", row.size())

# ---------- ⑤ 色卡一排（12 个） ----------
acrow = dlg.lb_accent.parentWidget()
save(acrow, "v201_swatches.png", bg="#18181b", pad=6)
print("  acrow:", acrow.size(), "swatches:", len(dlg._accent_btns))

# ---------- ②③ 数值框箭头 + 勾选框对勾 ----------
box = QWidget()
box.setObjectName("Host")
box.setStyleSheet("QWidget#Host{background:#18181b;}")
box.setAttribute(Qt.WA_StyledBackground, True)
v = QVBoxLayout(box)
v.setContentsMargins(16, 14, 16, 14)
v.setSpacing(10)
h1 = QHBoxLayout()
sp1 = QSpinBox(); sp1.setRange(0, 999); sp1.setValue(15)
sp1.setSuffix(" 秒"); sp1.setFixedWidth(120)
sp2 = QDoubleSpinBox(); sp2.setRange(0, 10); sp2.setValue(6.5)
sp2.setDecimals(1); sp2.setFixedWidth(120)
h1.addWidget(QLabel("请求超时")); h1.addWidget(sp1)
h1.addSpacing(14)
h1.addWidget(QLabel("评分")); h1.addWidget(sp2)
h1.addStretch(1)
v.addLayout(h1)
c1 = QCheckBox("极速模式：只复核普通算法拿不准的"); c1.setChecked(True)
c2 = QCheckBox("未选中状态")
c3 = QCheckBox("结合收藏影片的标签 / 片商 / 系列"); c3.setChecked(True)
v.addWidget(c1); v.addWidget(c3); v.addWidget(c2)
box.resize(430, 170)
box.show()
app.processEvents()
save(box, "v201_spin_check.png", bg="#18181b", pad=6)

# ---------- ④ 演职人员头像按性别流光 ----------
import ui_hero as uhero
face = os.path.join(ROOT, "index_data", "_probe_face.png")
src = QPixmap(os.path.join(ROOT, "logo-4.png"))
if not src.isNull():
    src.scaled(160, 160, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation).save(face)
else:
    pm0 = QPixmap(120, 120); pm0.fill(QColor("#b9c6d2")); pm0.save(face)

host = QWidget()
host.setObjectName("CastHost")
host.setStyleSheet("QWidget#CastHost{background:#141416;}")
host.setAttribute(Qt.WA_StyledBackground, True)
hl = QHBoxLayout(host)
hl.setContentsMargins(14, 10, 14, 10)
hl.setSpacing(8)
for who, g in (("天馬ゆい", "female"), ("ぶーてゃん", "male"), ("BuddhaD", "")):
    hl.addWidget(uhero.CastAvatar({"name": who, "gender": g, "photo_path": face,
                                   "char_role": "Actor"}, None))
hl.addStretch(1)
host.resize(470, 168)
host.show()
app.processEvents()
save(host, "v201_cast_glow.png", bg="#141416", pad=0)

# ---------- ⑦ 详情面板：直角 vs 圆角 ----------
box2 = QWidget()
box2.setObjectName("Host2")
box2.setStyleSheet("QWidget#Host2{background:#0a0a0b;}")
box2.setAttribute(Qt.WA_StyledBackground, True)
h2 = QHBoxLayout(box2)
h2.setContentsMargins(10, 10, 10, 10)
for nm in ("DetailHost",):
    d = QWidget(); d.setObjectName(nm)
    d.setAttribute(Qt.WA_StyledBackground, True)
    d.setFixedSize(300, 150)
    h2.addWidget(d)
box2.resize(340, 176)
box2.show()
app.processEvents()
save(box2, "v201_detailhost.png", bg="#0a0a0b", pad=0)

print("DONE")
