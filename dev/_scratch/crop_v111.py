# -*- coding: utf-8 -*-
"""放大裁切 dev/screenshots_v111 里的 PND 区域，用于核对字形是否被裁切。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt, QRect

app = QApplication(sys.argv)
SRC = os.path.join(_HERE, "screenshots_v111")

JOBS = [
    ("04_settings_scraper.png", QRect(170, 570, 300, 60), "z_btn_primary.png", 3),
    ("04_settings_scraper.png", QRect(170, 620, 810, 40), "z_btn_repair.png", 3),
    ("04_settings_scraper.png", QRect(0, 10, 150, 90), "z_sidebar.png", 3),
    ("04_settings_scraper.png", QRect(760, 120, 240, 120), "z_src_btns.png", 3),
    ("02_settings_nav.png", QRect(820, 222, 170, 210), "z_nav_updown.png", 3),
    ("01_topbar.png", QRect(0, 0, 120, 63), "z_topbar_arrows.png", 3),
]

for fn, rect, out, z in JOBS:
    img = QImage(os.path.join(SRC, fn))
    if img.isNull():
        print("缺文件", fn)
        continue
    crop = img.copy(rect)
    crop.scaled(crop.width() * z, crop.height() * z,
                Qt.IgnoreAspectRatio, Qt.FastTransformation
                ).save(os.path.join(SRC, out))
    print("%-26s <- %s %s" % (out, fn, rect))
print("ok")
