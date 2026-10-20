# -*- coding: utf-8 -*-
"""v1.42.1 UI 反馈冒烟（离屏 QT_QPA_PLATFORM=offscreen，不需要真实显示器）。

两则反馈：
  ① 工具→演员刮削页：数据源三行太高、组间与下方留白
     —— SRC_ROW_H 56→44、源行上下边距 4→2、组距 7→5，描述不裁、底部不留白；
  ② 演员检测页：结果树↔底部编辑区的竖向拖动条换主流「5 点 grabber」
     —— _GripSplitter/_GripHandle 自绘横向 5 圆点，QSS handle 背景透明 + margin 归零。

18 项断言全过才退出 0。
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication, QGroupBox, QSplitter
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint, QRect, QSize

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg
import applog

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1421_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
try:
    applog.log_dir = lambda: os.path.join(TMP, "logs")
except Exception:
    pass
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

from main_window import MainWindow, load_style
import version as VER
import ui_actorcheck as uac
from ui_settings import SettingsDialog, SRC_ROW_H

load_style(app)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "✓" if cond else "✗"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


class _FakeScr:
    def availableGeometry(self):
        return QRect(0, 0, 2560, 1392)

    def geometry(self):
        return QRect(0, 0, 2560, 1440)


SettingsDialog.screen = lambda self: _FakeScr()

# =====================================================================
# 版本
# =====================================================================
print("== 版本 ==")
check("VERSION == v1.42.1", VER.VERSION == "v1.42.1", VER.VERSION)
check("BUILD == 2610180084", VER.BUILD == "2610180084", VER.BUILD)

# =====================================================================
# Item ①：演员刮削页布局（离屏实测）
# =====================================================================
print("== Item① 刮削页数据源行高压紧 ==")
win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()

dlg = SettingsDialog(win)
dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
dlg.resize(1320, 960)
dlg.show()
app.processEvents()
for k, b in dlg.sub_btns.items():
    if "刮削" in k:
        b.click()
        break
app.processEvents()

pg = dlg._pg_scraper
seen = 0
while hasattr(pg, "widget") and seen < 4:        # 解包 freeze 滚动区/画布
    inner = pg.widget()
    if inner is None:
        break
    pg = inner
    seen += 1

groups = [g for g in pg.findChildren(QGroupBox)]
groups.sort(key=lambda g: g.mapTo(pg, QPoint(0, 0)).y())
gaps = []
prev_bottom = None
for g in groups:
    p = g.mapTo(pg, QPoint(0, 0))
    if prev_bottom is not None:
        gaps.append(p.y() - prev_bottom)
    prev_bottom = p.y() + g.height()
print("  组框:", [(g.title()[:10], g.height()) for g in groups], "上间距:", gaps)
check("SRC_ROW_H == 44", SRC_ROW_H == 44, str(SRC_ROW_H))
check("组间距均为 5（原 7）", len(gaps) >= 2 and all(x == 5 for x in gaps), str(gaps))

sl = dlg.src_list
check("src_list 固定高 == 44*3+8 == 140",
      sl.height() == SRC_ROW_H * 3 + 8, f"h={sl.height()} count={sl.count()}")
rows = [sl.itemWidget(sl.item(i)) for i in range(sl.count())]
check("三行 sizeHintForRow 全 == 44",
      sl.count() == 3 and all(sl.sizeHintForRow(i) == SRC_ROW_H for i in range(3)),
      str([sl.sizeHintForRow(i) for i in range(sl.count())]))

margins_ok, label_ok, texts, label_hs = True, True, [], []
for row in rows:
    h = row.layout()
    m = h.contentsMargins()
    if (m.left(), m.top(), m.right(), m.bottom()) != (6, 2, 6, 2):
        margins_ok = False
    from PySide6.QtWidgets import QLabel as _QL
    labs = [c for c in row.findChildren(_QL) if c.styleSheet() == ""]
    if labs:
        lab = labs[0]
        texts.append(lab.text())
        label_hs.append(lab.height())
        # 不裁切的精确判据：按当前宽度算出的所需高度 ≤ 实际拿到的行内可用高
        if lab.heightForWidth(lab.width()) > SRC_ROW_H - 4:
            label_ok = False
check("源行内边距 == (6,2,6,2)（原 4）", margins_ok)
check("三行描述 label 均不裁切（高 ≤ 40）", label_ok, f"label 高: {label_hs}")
joined = " ".join(texts)
check("label 文本含 avbase.net / minnano / IMDB 三源",
      all(s in joined for s in ("avbase.net", "minnano", "IMDB")), joined[:60])

# =====================================================================
# Item ②：演员检测页 5 点 grabber
# =====================================================================
print("== Item② 演员检测页 5 点 grabber ==")
page = uac.ActorCheckPage()
page.setAttribute(Qt.WA_DontShowOnScreen, True)
page.resize(1200, 860)
page.show()
app.processEvents()

grips = page.findChildren(uac._GripSplitter)
check("页面恰好 1 个 _GripSplitter 且为竖向",
      len(grips) == 1 and grips[0].orientation() == Qt.Vertical,
      f"n={len(grips)}")
sp = grips[0]
h = sp.handle(1)
check("handleWidth == 14 且 handle(1) 是 _GripHandle",
      sp.handleWidth() == 14 and isinstance(h, uac._GripHandle),
      f"hw={sp.handleWidth()} type={type(h).__name__}")
check("handle 实际高 == 14 且 sizeHint == 14x14（QSS margin 已归零）",
      h.height() == 14 and h.sizeHint() == QSize(14, 14),
      f"h={h.height()} sizeHint={h.sizeHint().width()}x{h.sizeHint().height()}")
check("光标为 SizeVerCursor", h.cursor().shape() == Qt.SizeVerCursor,
      str(h.cursor().shape()))

# ---- 圆点几何 / 颜色（像素级） ----
from PIL import Image

img = h.grab()
png_normal = os.path.join(TMP, "grip_normal.png")
img.save(png_normal)
im = Image.open(png_normal).convert("RGBA")
W, H = im.size
alpha = im.split()[3]
px = alpha.load()
cols = [x for x in range(W) if any(px[x, y] > 0 for y in range(H))]
grps = []
cur = [cols[0]]
for x in cols[1:]:
    if x - cur[-1] <= 1:
        cur.append(x)
    else:
        grps.append(cur)
        cur = [x]
grps.append(cur)
boxes = []
for g in grps:
    x0, x1 = g[0], g[-1]
    ys = [y for y in range(H) if any(px[x, y] > 0 for x in range(x0, x1 + 1))]
    boxes.append((x0, x1, ys[0], ys[-1]))

check("圆点几何：5 组、各 ≈5px（含抗锯齿 fringe 4~6）、间距 ≥3、总宽 39~43、水平居中 ±1",
      len(boxes) == 5
      and all(4 <= x1 - x0 + 1 <= 6 for x0, x1, _, _ in boxes)
      and all(4 <= y1 - y0 + 1 <= 6 for _, _, y0, y1 in boxes)
      and all(boxes[i + 1][0] - boxes[i][1] - 1 >= 3 for i in range(4))
      and 39 <= boxes[-1][1] - boxes[0][0] + 1 <= 43
      and abs((boxes[0][0] + boxes[-1][1]) / 2.0 - W / 2.0) <= 1,
      str([(b[0], b[2], b[1] - b[0] + 1) for b in boxes]))
mid_y = (boxes[2][2] + boxes[2][3]) / 2.0
check("圆点垂直居中 ±1", abs(mid_y - H / 2.0) <= 1, f"mid_y={mid_y} H={H}")

cx = int((boxes[2][0] + boxes[2][1]) / 2)
cy = int(mid_y)
a_normal = px[cx, cy]
check("normal 圆点 alpha == 140（强调色 55%）", a_normal == 140, str(a_normal))

h.setAttribute(Qt.WA_UnderMouse, True)
h._hover = True
png_hover = os.path.join(TMP, "grip_hover.png")
h.grab().save(png_hover)
a_hover = Image.open(png_hover).convert("RGBA").split()[3].load()[cx, cy]
h.setAttribute(Qt.WA_UnderMouse, False)
h._hover = False
check("hover 圆点 alpha == 238（提亮，且 > normal）",
      a_hover == 238 and a_hover > a_normal, str(a_hover))

far_clear = all(px[x, y] == 0 for x, y in
                [(10, 7), (W - 10, 7), (10, H - 2), (W - 10, H - 2),
                 (cx - 200, cy), (cx + 200, cy)])
check("handle 远离圆点处 alpha == 0（QSS 背景已透明、无长条）", far_clear)

plains = [s for s in page.findChildren(QSplitter)
          if not isinstance(s, uac._GripSplitter)]
check("横向 ActorSplitH 仍是普通 QSplitter（handleWidth=6，未牵连）",
      len(plains) == 1 and plains[0].objectName() == "ActorSplitH"
      and plains[0].handleWidth() == 6,
      str([(s.objectName(), s.handleWidth()) for s in plains]))

# createHandle 对横向也应返回 _GripHandle（代码路径覆盖）
from PySide6.QtWidgets import QWidget as _QW
tester = uac._GripSplitter(Qt.Horizontal)
tester.addWidget(_QW())
tester.addWidget(_QW())
check("_GripSplitter.createHandle 横向也返回 _GripHandle",
      isinstance(tester.handle(1), uac._GripHandle))

# =====================================================================
print(f"\n通过 {len(PASS)}/{len(PASS) + len(FAIL)}")
if FAIL:
    print("失败项:", FAIL)
    sys.exit(1)
print("SMOKE_V1421_ALL_OK")
