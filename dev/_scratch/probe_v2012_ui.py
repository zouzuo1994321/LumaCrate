# -*- coding: utf-8 -*-
"""v2.0.12 取证：**圆角外黑框** 到底在哪、修完还在不在。

用户反馈：「不少圆角外有黑框尝试修复」+ 3 张截图（右键菜单 / 替换弹层 / 表头单元格）。

结论（本脚本要自证的）：
  A. 顶层浮层（QMenu / 无边框 QDialog / 悬停卡）必须开 WA_TranslucentBackground，
     否则圆角外是**窗口表面的纯黑**；同时必须带 NoDropShadowWindowHint（系统阴影按矩形画）。
  B. 表格自己有 14px 圆角，表头是方形半透明子控件 → 圆角缺口里只剩「页面色 + 4.5% 白」，
     比表头正文暗一截，看着就是黑框。表头首/末列补 13px 顶部圆角后，缺口 = 页面色。
     **这一条用像素量**：垫一层已知底色，量缺口里那一格的颜色。

用法（必须用 runpy 走绝对路径）：
  python -u -c "import runpy; runpy.run_path(r'<本文件>', run_name='__main__')"
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("LMC_NO_SYSMON", "1")

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtCore import Qt                                   # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QTableWidget,      # noqa: E402
                               QTableWidgetItem, QVBoxLayout, QWidget)

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw          # noqa: E402
import ui_home                    # noqa: E402
import ui_hero                    # noqa: E402
import uiwin                      # noqa: E402

mw.load_style(app)

FAIL = []


def check(label, cond, detail=""):
    print(("  OK  " if cond else "  FAIL") + "  " + label + ("  | " + str(detail) if detail else ""))
    if not cond:
        FAIL.append(label)


PAGE = QColor(16, 16, 20)          # 故意用一个跟表头/表格都不一样的底色，好把「谁画的」区分开


def grab_on(widget, page=PAGE, pad=4):
    """把 widget 画到一张已知底色的图上（grab() 出来的透明区不能直接判 RGB）。"""
    pm = widget.grab()
    out = QPixmap(pm.width() + pad * 2, pm.height() + pad * 2)
    out.fill(page)
    p = QPainter(out)
    p.drawPixmap(pad, pad, pm)
    p.end()
    return out, pad


print("\n=== A. 顶层浮层的窗口属性 ===")

m = uiwin.menu()
flags = int(m.windowFlags())
check("menu 有 WA_TranslucentBackground", m.testAttribute(Qt.WA_TranslucentBackground))
check("menu 有 FramelessWindowHint", bool(flags & int(Qt.FramelessWindowHint)))
check("menu 有 NoDropShadowWindowHint", bool(flags & int(Qt.NoDropShadowWindowHint)))
check("menu 没有 autoFillBackground", not m.autoFillBackground())
check("menu 仍是 Popup（点外面能关）", bool(flags & int(Qt.Popup)))

dlg = ui_hero.PersonSearchDialog(initial="")
check("PersonSearchDialog 半透明", dlg.testAttribute(Qt.WA_TranslucentBackground))
check("PersonSearchDialog 无 autoFillBackground", not dlg.autoFillBackground())
df = int(dlg.windowFlags())
check("PersonSearchDialog 无边框", bool(df & int(Qt.FramelessWindowHint)))
check("PersonSearchDialog 无系统阴影", bool(df & int(Qt.NoDropShadowWindowHint)))
# 弹层自身的 QSS 圆角必须还在（背景不透明 + 圆角，靠的就是窗口半透明）
check("PersonSearchDialog 仍是圆角 10px", "border-radius:10px" in dlg.styleSheet())

pop = ui_home.ColumnFilterPopup("favorite", "收藏", None, [("是", "1"), ("否", "0")])
check("ColumnFilterPopup 半透明", pop.testAttribute(Qt.WA_TranslucentBackground))
check("ColumnFilterPopup 仍是圆角 8px", "border-radius:8px" in pop.styleSheet())

hov = ui_home.HoverPreview()
check("HoverPreview 半透明", hov.testAttribute(Qt.WA_TranslucentBackground))

print("\n=== A2. 源码级：别再有人裸建 QMenu ===")
for f in ("main_window.py", "ui_hero.py", "ui_home.py", "ui_settings.py"):
    src = open(os.path.join(SRC, f), encoding="utf-8").read()
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    check("%s 里没有裸 QMenu(" % f, "QMenu(" not in body,
          body.count("QMenu("))

print("\n=== B. 表头圆角缺口（像素） ===")


def build_table():
    host = QWidget()
    host.setStyleSheet("background: #%02x%02x%02x;" % (PAGE.red(), PAGE.green(), PAGE.blue()))
    v = QVBoxLayout(host)
    v.setContentsMargins(0, 0, 0, 0)
    t = QTableWidget(3, 4)
    t.setHorizontalHeaderLabels(["A", "B", "C", "D"])
    for r in range(3):
        for c in range(4):
            t.setItem(r, c, QTableWidgetItem("r%dc%d" % (r, c)))
    t.setShowGrid(False)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(26)
    t.horizontalHeader().setFixedHeight(32)
    v.addWidget(t)
    host.resize(420, 160)
    host.show()
    return host, t


host, tbl = build_table()
app.processEvents()
pm, pad = grab_on(host, page=QColor(0, 0, 0))
img = pm.toImage()
hdr = tbl.horizontalHeader()
# 缺口采样点：表头左上角靠里 3~4px 的三角区（半径 13，所以 (3,3) 一定还在弧外）
pos = hdr.mapTo(host, hdr.rect().topLeft())
cx, cy = pos.x() + pad + 3, pos.y() + pad + 3
c_gap = img.pixelColor(cx, cy)
c_body = img.pixelColor(pos.x() + pad + 30, pos.y() + pad + 12)
print("    缺口色 = %s   表头正文色 = %s   (取样点 %d,%d)" %
      (c_gap.name(), c_body.name(), cx, cy))
# 判定：缺口应该 = 页面底色（视频里给 host 铺的 #101014），而不是「底色 + 4.5% 白」
check("缺口不再被表头压暗（≈页面色）",
      abs(c_gap.red() - PAGE.red()) <= 2 and abs(c_gap.blue() - PAGE.blue()) <= 2,
      c_gap.name())
check("表头正文比缺口亮（说明取样点确实一个里一个外）",
      c_body.lightness() > c_gap.lightness() + 3,
      "%d > %d" % (c_body.lightness(), c_gap.lightness()))

print("\n=== C. QSS 生效性（Qt 会静默丢掉非法声明） ===")
qss = mw.render_style()
from PySide6.QtWidgets import QHeaderView  # noqa: E402
tbl.setStyleSheet("")                        # 只吃全局表
app.processEvents()
for sel in ("QHeaderView::section:first", "QHeaderView::section:last"):
    check("QSS 有 " + sel, sel in qss)
check("全局 QDialog 不再有 border-radius", "QDialog {" in qss and
      "border-radius" not in qss.split("QDialog {")[1].split("}")[0],
      qss.split("QDialog {")[1].split("}")[0].replace("\n", " ")[:90])

print("\n失败项 = %d" % len(FAIL))
for f in FAIL:
    print("  · " + f)
