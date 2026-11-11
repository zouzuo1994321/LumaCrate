# -*- coding: utf-8 -*-
"""v2.0.12 真机（同进程）取证：圆角外到底是黑的还是「露出后面的界面」。

为什么要开真窗口而不是离屏：`grab()` 只重放 paintEvent，拿不到「窗口表面是黑的」
这个真机现象；必须让窗口真的上屏，再 `QScreen.grabWindow(0)` 抓**合成之后**的像素。

判据（全部像素，不靠属性自证）：
  在一个**亮蓝**底的窗口上弹浮层 —— 半透明窗口时圆角外应当是蓝色（抗锯齿轻微压暗可接受），
  不透明窗口时是近黑（#000000 附近）。
"""
import os
import sys
import time

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import Qt, QPoint, QTimer          # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QFontDatabase, QPainter  # noqa: E402
from PySide6.QtWidgets import (QApplication, QDialog, QTableWidget,  # noqa: E402
                               QTableWidgetItem, QVBoxLayout, QWidget)

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw          # noqa: E402
import ui_home                    # noqa: E402
import ui_hero                    # noqa: E402

mw.load_style(app)

BG = "#1f7ae0"          # 亮蓝：黑角一眼就能看出来
BGRGB = (0x1f, 0x7a, 0xe0)
FAIL = []


def pump(ms=260):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot():
    return QGuiApplication.primaryScreen().grabWindow(0).toImage()


OUT = r"E:\【01】自研软件\【26-19】本地影视中心\dev\screenshots"


def save_crop(img, x, y, w, h, name, pad=14):
    """裁一块（含四周 pad 的背景）存盘 —— 出对照图用。

    ⚠ 必须存 `grabWindow(0)` 的**合成结果**，不能存 `widget.grab()`：
    后者只重放 paintEvent，半透明窗口在那上面全是 alpha=0，看不出「透出了什么」。
    """
    c = img.copy(max(0, x - pad), max(0, y - pad), w + 2 * pad, h + 2 * pad)
    c.save(os.path.join(OUT, "v2012_%s.png" % name))
    print("    图 v2012_%s.png %dx%d" % (name, c.width(), c.height()))
    return c


def px(img, gx, gy):
    if gx < 0 or gy < 0 or gx >= img.width() or gy >= img.height():
        return QColor(0, 0, 0)
    return img.pixelColor(gx, gy)


def is_black(c):
    # 只把「真黑」判成黑：软件自己的面板色是 #18181b（24,24,27），那是正常的深色，
    # 黑框伪影是圆角外**什么都没画**的窗口表面 —— 实测 #000000 ~ #060608。
    return max(c.red(), c.green(), c.blue()) <= 8


def bleeds_bg(c):
    # 半透明窗口的圆角外 = 后面那块界面（这里是亮蓝）+ 1px 边框的抗锯齿混合。
    # 判据：蓝通道明显高于红通道；纯黑或近黑不可能满足。
    return c.blue() > c.red() + 25


def is_bg(c, tol=14):
    return (abs(c.red() - BGRGB[0]) <= tol and abs(c.green() - BGRGB[1]) <= tol
            and abs(c.blue() - BGRGB[2]) <= tol)


def check(label, cond, detail=""):
    print(("  OK  " if cond else "  FAIL") + "  " + label + ("  | " + str(detail) if detail else ""))
    if not cond:
        FAIL.append(label)


class Host(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("v2012 probe host")
        self.resize(900, 620)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG))


host = Host()
host.move(60, 60)
host.show()
pump(500)
g = host.frameGeometry()
print("host geometry", g)

print("\n=== 1. 右键菜单（QSS 14px 圆角） ===")
menu = mw.uiwin.menu(host)
for t in ("播放选中视频", "打开视频文件夹", "刷新数据"):
    menu.addAction(t)
menu.popup(QPoint(g.x() + 340, g.y() + 330))
pump(400)
mg = menu.geometry()
img = shot()
c = px(img, mg.x() + 2, mg.y() + 2)
c_in = px(img, mg.x() + 20, mg.y() + 20)
print("    菜单 %dx%d @ (%d,%d)  角外=%s  内侧=%s" %
      (mg.width(), mg.height(), mg.x(), mg.y(), c.name(), c_in.name()))
check("菜单圆角外不是黑（露出蓝色底）", bleeds_bg(c) and not is_black(c), c.name())
check("菜单内侧仍是不透明深色", c_in.lightness() < 60 and c_in.alpha() == 255, c_in.name())
save_crop(img, mg.x(), mg.y(), mg.width(), mg.height(), "probe_menu")
menu.close()
pump(200)

print("\n=== 2. 表头筛选浮层（ColumnFilterPopup，8px 圆角） ===")
pop = ui_home.ColumnFilterPopup("favorite", "收藏", None, [("是", "1"), ("否", "0")], host)
pop.move(g.x() + 300, g.y() + 240)
pop.show()
pump(400)
pg = pop.geometry()
img = shot()
c = px(img, pg.x() + 2, pg.y() + 2)
c_in = px(img, pg.x() + pg.width() - 8, pg.y() + pg.height() - 8)
print("    浮层 %dx%d @ (%d,%d)  角外=%s  内侧=%s" %
      (pg.width(), pg.height(), pg.x(), pg.y(), c.name(), c_in.name()))
check("筛选浮层圆角外不是黑", bleeds_bg(c) and not is_black(c), c.name())
check("筛选浮层内侧是不透明深色", c_in.lightness() < 70, c_in.name())
pop.close()
pump(200)

print("\n=== 3. 替换弹层（PersonSearchDialog，10px 圆角） ===")
dlg = ui_hero.PersonSearchDialog(initial="", old_name="月野江すい", parent=host)
dlg.move(g.x() + 260, g.y() + 150)
dlg.show()
pump(450)
dg = dlg.geometry()
img = shot()
c = px(img, dg.x() + 2, dg.y() + 2)
c_in = px(img, dg.x() + dg.width() - 10, dg.y() + dg.height() - 10)
print("    弹层 %dx%d @ (%d,%d)  角外=%s  内侧=%s" %
      (dg.width(), dg.height(), dg.x(), dg.y(), c.name(), c_in.name()))
check("替换弹层圆角外不是黑", bleeds_bg(c) and not is_black(c), c.name())
check("替换弹层内侧是不透明深色", c_in.lightness() < 70 and c_in.alpha() == 255, c_in.name())
save_crop(img, dg.x(), dg.y(), dg.width(), dg.height(), "probe_psd")
# 文字可读性：弹层里必须真有一块深色面板（不是全透）
dark_ratio = sum(1 for x in range(dg.x() + 20, dg.x() + dg.width() - 20, 6)
                 for y in range(dg.y() + 20, dg.y() + dg.height() - 20, 6)
                 if px(img, x, y).lightness() < 70)
total = len(range(dg.x() + 20, dg.x() + dg.width() - 20, 6)) * \
        len(range(dg.y() + 20, dg.y() + dg.height() - 20, 6))
print("    弹层内深色像素占比 %.0f%%" % (100.0 * dark_ratio / max(total, 1)))
check("弹层内深色占比 > 60%（面板真的画出来了）", dark_ratio / max(total, 1) > 0.6,
      "%.2f" % (dark_ratio / max(total, 1)))
dlg.close()
pump(200)

print("\n=== 4. 原生边框对话框（全局 QDialog 规则，已去掉圆角） ===")
nd = QDialog(host)
nd.setWindowTitle("列设置")
nd.resize(420, 240)
nd.move(g.x() + 120, g.y() + 120)
nd.show()
pump(450)
cg = nd.geometry()
img = shot()
c_tl = px(img, cg.x() + 2, cg.y() + 2)
c_tr = px(img, cg.x() + cg.width() - 3, cg.y() + 2)
print("    客户区 %dx%d @ (%d,%d)  左上=%s 右上=%s" %
      (cg.width(), cg.height(), cg.x(), cg.y(), c_tl.name(), c_tr.name()))
check("原生对话框客户区四角不是纯黑（是面板色）", (not is_black(c_tl)) and (not is_black(c_tr)) and c_tl.lightness() > 10,
      "%s / %s" % (c_tl.name(), c_tr.name()))
nd.close()
pump(200)

print("\n=== 5. 表格顶部圆角（表头首列） ===")
tv = QWidget(host)
lay = QVBoxLayout(tv)
lay.setContentsMargins(120, 60, 120, 60)
tbl = QTableWidget(4, 3)
tbl.setHorizontalHeaderLabels(["片名", "评分", "年份"])
for r in range(4):
    for cc in range(3):
        tbl.setItem(r, cc, QTableWidgetItem("X-%d" % r))
tbl.setShowGrid(False)
tbl.verticalHeader().setVisible(False)
lay.addWidget(tbl)

tv2 = QWidget(host)
tv2.setStyleSheet("background:%s;" % BG)
tv2.setAttribute(Qt.WA_StyledBackground, True)
tv2.resize(880, 520)
tv2.move(g.x() + 10, g.y() + 10)
lay2 = QVBoxLayout(tv2)
lay2.setContentsMargins(0, 0, 0, 0)
lay2.addWidget(tv)
tv2.show()
pump(450)
hdr = tbl.horizontalHeader()
tl = hdr.mapToGlobal(hdr.rect().topLeft())
img = shot()
c_gap = px(img, tl.x() + 3, tl.y() + 3)
c_hdr = px(img, tl.x() + 40, tl.y() + 12)
print("    表头左上 global=(%d,%d)  缺口=%s  表头=%s" % (tl.x(), tl.y(), c_gap.name(), c_hdr.name()))
check("表头圆角缺口 = 页面底色（没被表头压暗）", is_bg(c_gap, 20) and not is_black(c_gap),
      c_gap.name())
check("表头正文比缺口亮（一个里一个外）", c_hdr.lightness() > c_gap.lightness() + 2,
      "%d > %d" % (c_hdr.lightness(), c_gap.lightness()))
save_crop(img, tl.x(), tl.y(), 180, 90, "probe_header", pad=0)
tv2.close()

print("\n失败项 = %d" % len(FAIL))
for f in FAIL:
    print("  · " + f)
QTimer.singleShot(0, app.quit)
app.exec()
