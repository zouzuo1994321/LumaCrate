# -*- coding: utf-8 -*-
"""v1.42.2 UI 反馈冒烟（离屏 QT_QPA_PLATFORM=offscreen，不需要真实显示器）。

两则反馈：
  ① 演员检测页「树↔右侧详情之间的**横向**拖动条」（ActorSplitH）也要同款
     5 点 grabber —— _GripHandle 增加方向感知（横向把手时 5 点**竖排**一列）、
     handleWidth 6→14、QSS 背景透明 + margin 归零；
  ② 演员刮削页「IMDB 行下方凭空多一条 44px 空槽」—— 真机截图实证是列表里
     多出一个没有挂 widget 的幻影项（根因未复现）：rebuild 后兜底清掉幻影项；
     另修 Qt 已知行为 clear() 不删 setItemWidget 旧行 widget（控件泄漏）。

含 v1.42.1 回归项。全过才退出 0。
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import (QApplication, QGroupBox, QSplitter, QListWidget,
                               QLabel, QListWidgetItem)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint, QRect, QSize

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import config as cfg
import applog

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1422_")
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
check("VERSION == v1.42.2", VER.VERSION == "v1.42.2", VER.VERSION)
check("BUILD == 2610180085", VER.BUILD == "2610180085", VER.BUILD)

# =====================================================================
# Item ①：演员检测页横向 ActorSplitH 也换 5 点 grip
# =====================================================================
print("== Item① 横向 ActorSplitH 5 点 grip ==")
page = uac.ActorCheckPage()
page.setAttribute(Qt.WA_DontShowOnScreen, True)
page.resize(1200, 860)
page.show()
app.processEvents()

grips = page.findChildren(uac._GripSplitter)
by_name = {g.objectName(): g for g in grips}
check("页面有 2 个 _GripSplitter（ActorSplitV 竖向 + ActorSplitH 横向）",
      set(by_name) == {"ActorSplitV", "ActorSplitH"},
      str([(g.objectName(), g.orientation()) for g in grips]))

sv, sh = by_name.get("ActorSplitV"), by_name.get("ActorSplitH")
if sv is not None and sh is not None:
    check("ActorSplitH orientation == Horizontal",
          sh.orientation() == Qt.Horizontal)
    check("ActorSplitH handleWidth == 14（原 6）", sh.handleWidth() == 14,
          str(sh.handleWidth()))
    hh = sh.handle(1)
    check("ActorSplitH handle(1) 是 _GripHandle", isinstance(hh, uac._GripHandle),
          type(hh).__name__)
    check("ActorSplitH 把手宽 == 14", hh.width() == 14, str(hh.width()))
    check("横向把手光标为 SizeHorCursor",
          hh.cursor().shape() == Qt.SizeHorCursor, str(hh.cursor().shape()))
    check("竖向把手光标仍为 SizeVerCursor（回归）",
          sv.handle(1).cursor().shape() == Qt.SizeVerCursor)

    # ---- 圆点几何：横向把手应为**竖排一列** ----
    from PIL import Image
    img = hh.grab()
    png_h = os.path.join(TMP, "grip_h_normal.png")
    img.save(png_h)
    im = Image.open(png_h).convert("RGBA")
    W, H = im.size
    alpha = im.split()[3]
    px = alpha.load()
    ys = [y for y in range(H) if any(px[x, y] > 0 for x in range(W))]
    grps = []
    cur = [ys[0]]
    for y in ys[1:]:
        if y - cur[-1] <= 1:
            cur.append(y)
        else:
            grps.append(cur)
            cur = [y]
    grps.append(cur)
    boxes = []
    for g in grps:
        y0, y1 = g[0], g[-1]
        xs = [x for x in range(W) if any(px[x, y] > 0 for y in range(y0, y1 + 1))]
        boxes.append((y0, y1, xs[0], xs[-1]))

    check("圆点几何：5 组、各 ≈5px（含抗锯齿 fringe 4~6）、间距 ≥3、总高 39~43、横向居中 ±1",
          len(boxes) == 5
          and all(4 <= y1 - y0 + 1 <= 6 for y0, y1, _, _ in boxes)
          and all(4 <= x1 - x0 + 1 <= 6 for _, _, x0, x1 in boxes)
          and all(boxes[i + 1][0] - boxes[i][1] - 1 >= 3 for i in range(4))
          and 39 <= boxes[-1][1] - boxes[0][0] + 1 <= 43
          and abs((boxes[0][2] + boxes[0][3]) / 2.0 - W / 2.0) <= 1,
          str([(b[0], b[2], b[1] - b[0] + 1) for b in boxes]))
    # 竖排判据：5 组的 x 范围基本重合、y 依次递进
    same_col = all(abs(b[2] - boxes[0][2]) <= 1 and abs(b[3] - boxes[0][3]) <= 1
                   for b in boxes)
    check("5 点确为竖排一列（x 重合、y 递进）", same_col,
          str([(b[2], b[3]) for b in boxes]))

    cx = int((boxes[2][2] + boxes[2][3]) / 2)
    cy = int((boxes[2][0] + boxes[2][1]) / 2)
    a_normal = px[cx, cy]
    check("normal 圆点 alpha == 140", a_normal == 140, str(a_normal))
    hh.setAttribute(Qt.WA_UnderMouse, True)
    hh._hover = True
    png_hh = os.path.join(TMP, "grip_h_hover.png")
    hh.grab().save(png_hh)
    a_hover = Image.open(png_hh).convert("RGBA").split()[3].load()[cx, cy]
    hh.setAttribute(Qt.WA_UnderMouse, False)
    hh._hover = False
    check("hover 圆点 alpha == 238（提亮）",
          a_hover == 238 and a_hover > a_normal, str(a_hover))
    far = all(px[x, y] == 0 for x, y in
              [(1, 2), (W - 2, 2), (1, H - 2), (W - 2, H - 2), (cx, 2), (cx, H - 2)])
    check("横向把手远离圆点处 alpha == 0（QSS 背景透明）", far)

# =====================================================================
# Item ②：刮削页数据源列表 —— 幻影项兜底 + 控件泄漏收尸
# =====================================================================
print("== Item② 数据源列表幻影项/泄漏 ==")
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

sl = dlg.src_list
check("正常 3 源：count == 3 且每行都有 widget",
      sl.count() == 3 and all(sl.itemWidget(sl.item(i)) is not None
                              for i in range(sl.count())),
      f"count={sl.count()}")
check("列表高 == 44*3+8 == 140", sl.height() == SRC_ROW_H * 3 + 8,
      f"h={sl.height()}")

# ---- 控件泄漏收尸：反复重建后 viewport 子对象不再增长 ----
# v1.42.2 修复前：clear() 不清 setItemWidget 行控件，deleteLater 又要等
# 事件轮次冲 DeferredDelete（processEvents 不冲！实测重建 x3 后 viewport
# 子对象 3→6→9→12 线性堆积）。修复后旧行 hide+脱父即时脱落，只剩当前 3 行。
for _ in range(3):
    dlg._rebuild_source_list()
    app.processEvents()
n_widgets = len(sl.viewport().children())
check("重建 x3 后 viewport 子对象 == 3（旧行即时脱落，无泄漏）",
      n_widgets == 3, f"n={n_widgets}")
check("重建 x3 后仍 count == 3 / 高 == 140",
      sl.count() == 3 and sl.height() == 140, f"count={sl.count()} h={sl.height()}")

# ---- 幻影项兜底：模拟「item 进列但 widget 没挂上」（真机 bug 形态） ----
# 用户截图实证：列表 184px 高 = 44×4+8 → count 被算成 4，第 4 条是无 widget
# 的幻影空槽。所以模拟方式必须是**多插一条无 widget 的项**（3→4），
# 而不是「跳过挂载某条真实行」（那会 3→2，不是 bug 形态）。
orig_sw = sl.setItemWidget
_state = {"phantom": True}


def _patched(item, widget):
    orig_sw(item, widget)
    if _state["phantom"]:
        _state["phantom"] = False
        sl.addItem(QListWidgetItem("幻影空槽"))   # 多一条没挂 widget 的项


sl.setItemWidget = _patched
try:
    dlg._rebuild_source_list()
    app.processEvents()
finally:
    try:
        del sl.setItemWidget
    except Exception:
        pass
check("幻影项被兜底清掉：count 回 3、无 widget-less 项、高回 140",
      sl.count() == 3
      and all(sl.itemWidget(sl.item(i)) is not None for i in range(sl.count()))
      and sl.height() == 140,
      f"count={sl.count()} h={sl.height()}")

# ---- 4 源场景不误伤：每行都有 widget，count=4、高 184 ----
st = cfg.get_settings()
st.scraper["sources"] = ["avbase", "minnano", "imdb", "javdb"]
dlg._rebuild_source_list()
app.processEvents()
check("4 源（含未知键）不误伤：count == 4、4 行全有 widget、高 == 184",
      sl.count() == 4
      and all(sl.itemWidget(sl.item(i)) is not None for i in range(sl.count()))
      and sl.height() == SRC_ROW_H * 4 + 8,
      f"count={sl.count()} h={sl.height()}")
st.scraper["sources"] = ["avbase", "minnano", "imdb"]
dlg._rebuild_source_list()
app.processEvents()

# =====================================================================
# v1.42.1 回归：刮削页布局 + 竖向 grabber
# =====================================================================
print("== 回归 v1.42.1 ==")
pg = dlg._pg_scraper
seen = 0
while hasattr(pg, "widget") and seen < 4:
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
check("SRC_ROW_H == 44", SRC_ROW_H == 44, str(SRC_ROW_H))
check("组间距均为 5", len(gaps) >= 2 and all(x == 5 for x in gaps), str(gaps))

rows = [sl.itemWidget(sl.item(i)) for i in range(sl.count())]
margins_ok, label_ok, texts, label_hs = True, True, [], []
for row in rows:
    m = row.layout().contentsMargins()
    if (m.left(), m.top(), m.right(), m.bottom()) != (6, 2, 6, 2):
        margins_ok = False
    labs = [c for c in row.findChildren(QLabel) if c.styleSheet() == ""]
    if labs:
        lab = labs[0]
        texts.append(lab.text())
        label_hs.append(lab.height())
        if lab.heightForWidth(lab.width()) > SRC_ROW_H - 4:
            label_ok = False
check("源行内边距 == (6,2,6,2)", margins_ok)
check("三行描述 label 均不裁切", label_ok, f"label 高: {label_hs}")
joined = " ".join(texts)
check("label 文本含 avbase.net / minnano / IMDB 三源",
      all(s in joined for s in ("avbase.net", "minnano", "IMDB")), joined[:60])

vh = sv.handle(1)
check("竖向把手 14px 且 sizeHint 14x14（QSS margin 归零）",
      vh.height() == 14 and vh.sizeHint() == QSize(14, 14),
      f"h={vh.height()} sizeHint={vh.sizeHint().width()}x{vh.sizeHint().height()}")
img = vh.grab()
png_v = os.path.join(TMP, "grip_v_normal.png")
img.save(png_v)
im = Image.open(png_v).convert("RGBA")
W, H = im.size
px = im.split()[3].load()
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
check("竖向把手 5 点横排几何（4~6px、间距≥3、总宽 39~43、居中）",
      len(boxes) == 5
      and all(4 <= x1 - x0 + 1 <= 6 for x0, x1, _, _ in boxes)
      and all(4 <= y1 - y0 + 1 <= 6 for _, _, y0, y1 in boxes)
      and all(boxes[i + 1][0] - boxes[i][1] - 1 >= 3 for i in range(4))
      and 39 <= boxes[-1][1] - boxes[0][0] + 1 <= 43
      and abs((boxes[0][0] + boxes[-1][1]) / 2.0 - W / 2.0) <= 1,
      str([(b[0], b[1] - b[0] + 1) for b in boxes]))

# =====================================================================
print(f"\n通过 {len(PASS)}/{len(PASS) + len(FAIL)}")
if FAIL:
    print("失败项:", FAIL)
    sys.exit(1)
print("SMOKE_V1422_ALL_OK")
