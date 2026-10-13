# -*- coding: utf-8 -*-
"""v1.40.8 离屏预览出图
========================
对「手动修改（选片后）」与「画像概览（分析后）」各出**顶部 + 底部**两张整窗图，
用于肉眼确认「内容已完整」：

  · 手动修改：顶部能看到 nfo 字段表头，**滚动到底部**能看到「简介 / 概要 / 演员」
    与「保存到 nfo 与索引 / 重新载入 / 打开影片目录」三个按钮。
  · 画像概览：顶部能看到雷达 + 概览，**滚动到底部**能看到「标签共现」全段。

并在图上打印「画布最小高 vs 内容需求」对照（v1.40.8 关键判据）。

跑法：
    C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u \
        "E:/【01】自研软件/【26-19】本地影视中心/dev/render_preview_v1408.py"
"""
import os
import sys
import time

ROOT = "E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication, QScrollArea
from PySide6.QtCore import QRect
from PySide6.QtGui import QFontDatabase, QImage, QPainter, QColor

app = QApplication([])
try:
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
except Exception:
    pass

import main_window as mw
import ui_settings as uis

print("ui_settings:", uis.__file__)
print("main_window:", mw.__file__)


class _FakeScr:
    """复刻真机 2560×1440（offscreen 平台的 availableGeometry 只有 800×800）。"""

    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


uis.SettingsDialog.screen = lambda self: _FakeScr()
mw.load_style(app)

OUT = os.path.join(ROOT, "dev", "screenshots")
BG = QColor(14, 12, 10)          # 与 style.qss 的窗口底色一致
SAVED = []


def save(w, name):
    """`grab()` 是透明底图 —— 必须先垫一层容器底色再存，否则半透明层会显示成纯白。"""
    pm = w.grab()
    img = pm.toImage()
    canvas = QImage(img.width(), img.height(), QImage.Format_RGB32)
    canvas.fill(BG)
    p = QPainter(canvas)
    p.drawImage(0, 0, img)
    p.end()
    fp = os.path.join(OUT, name)
    canvas.save(fp)
    SAVED.append(fp)
    print("  [saved] %-34s %dx%d" % (name, canvas.width(), canvas.height()))


def scroll_bottom(sc):
    sb = sc.verticalScrollBar()
    sb.setValue(sb.maximum())
    for _ in range(8):
        app.processEvents()


d = uis.SettingsDialog()
d.show()
for _ in range(12):
    app.processEvents()
print("dialog:", d.width(), d.height())


def canvas_of(sc):
    return sc.widget() if isinstance(sc, QScrollArea) else sc


def page_of(sc):
    cv = canvas_of(sc)
    if cv is None or cv.layout() is None or cv.layout().count() == 0:
        return cv
    return cv.layout().itemAt(0).widget()


# ---------- 手动修改 ----------
print()
print("== 手动修改（选片后） ==")
d._show("手动修改")
for _ in range(10):
    app.processEvents()
mp = d._manual_page
print("  列表条目:", mp.list.count())
if mp.list.count():
    mp.list.setCurrentRow(0)
    for _ in range(20):
        app.processEvents()
sc = d._pg_manual
pg = page_of(sc)
print("  画布最小高 = %d | 内容需求 = %d | 页面 %dx%d | 视口高 %d" % (
    canvas_of(sc).minimumHeight(), uis.SettingsDialog._content_need_height(pg),
    pg.width(), pg.height(), sc.viewport().height()))
host = mp.scroll.widget()
if host is not None:
    vb = mp.scroll.verticalScrollBar()
    print("  右栏 host 高 = %d | 右栏视口高 = %d | 滚动范围 = %d" % (
        host.height(), mp.scroll.viewport().height(), vb.maximum()))
save(d, "v1408_win_manual.png")
scroll_bottom(mp.scroll)
save(d, "v1408_win_manual_bottom.png")

# ---------- 画像概览 ----------
print()
print("== 画像概览（分析后） ==")
d._show("画像概览")
for _ in range(10):
    app.processEvents()
t0 = time.time()
while not d._insight_data and time.time() - t0 < 60:
    app.processEvents()
    time.sleep(0.03)
# 等「内容高重试到稳定」的循环跑完
for _ in range(40):
    app.processEvents()
    time.sleep(0.01)
sc = d._pg_insight
pg = page_of(sc)
print("  分析数据键 = %s" % sorted((d._insight_data or {}).keys()))
print("  画布最小高 = %d | 内容需求 = %d | 页面 %dx%d | 视口高 %d" % (
    canvas_of(sc).minimumHeight(), uis.SettingsDialog._content_need_height(pg),
    pg.width(), pg.height(), sc.viewport().height()))
save(d, "v1408_win_insight.png")
scroll_bottom(sc)
save(d, "v1408_win_insight_bottom.png")

print()
print("共出图 %d 张：" % len(SAVED))
for fp in SAVED:
    print("  " + fp)
