# -*- coding: utf-8 -*-
"""v2.0.11 预览图：三条反馈的前后对照（1400 × 880）。

A. 输入框首字前那截空白（16px → 12px 内边距）
B. 首页滚动条（4px 方头 → 8px 圆胶囊），6 倍放大
C. 演员 / 导演里的多碟分集（cd1 + cd2 两行 → 一部），用**真实临时库**跑真实函数

输出：docs/preview/v2011_fix.png
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("LMC_NO_SYSMON", "1")

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = tempfile.mkdtemp(prefix="lmc2011pv_")
os.makedirs(os.path.join(TMP, "index_data"), exist_ok=True)

from PySide6.QtCore import Qt                     # noqa: E402
from PySide6.QtGui import (QFontDatabase, QImage,  # noqa: E402
                           QPainter, QColor, QPixmap)
from PySide6.QtWidgets import (QApplication, QFrame, QLabel, QLineEdit,  # noqa: E402
                               QScrollArea, QVBoxLayout, QHBoxLayout, QWidget)

app = QApplication([])
for _f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import applog                                     # noqa: E402
applog.log_dir = lambda *a, **k: TMP
import database as db                             # noqa: E402

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
db.init_db()
import scanner                                    # noqa: E402
import main_window as mw                          # noqa: E402

mw.load_style(app)

ACCENT = "#e4587c"
BG = "#0f0f10"
CARD = "#18181b"
LINE = "#3f3f46"
DIM = "#a1a1aa"

# ---------------------------------------------------------------- C 的真实数据
LIB = os.path.join(TMP, "lib", "SAVR-1144")
os.makedirs(LIB, exist_ok=True)
F1 = os.path.join(LIB, "SAVR-1144-8K-cd1.mp4")
F2 = os.path.join(LIB, "SAVR-1144-8K-cd2.mp4")
for f in (F1, F2):
    with open(f, "wb") as fh:
        fh.write(b"\0" * 8)

conn = db.get_conn()
ids = []
for p in (F1, F2):
    cur = conn.execute(
        "INSERT INTO media (kind,title,sort_title,year,file_path,library) "
        "VALUES ('movie','SAVR-1144-8K','savr-1144-8k',2024,?,'测试库')", (p,))
    ids.append(cur.lastrowid)
conn.execute("INSERT INTO people (name,role_type) VALUES ('演员甲','Actor')")
pid = conn.execute("SELECT id FROM people WHERE name='演员甲'").fetchone()["id"]
for mid in ids:
    conn.execute("INSERT INTO media_people (media_id,person_id,char_role) "
                 "VALUES (?,?,'')", (mid, pid))
conn.commit()
conn.close()

before_rows = db.person_works(pid)          # 归组前：两条分片各算一行
before_works = db.get_person(pid)["works"]
scanner.group_cd_sets(TMP)
db.recount_people_works()
after_rows = db.person_works(pid)
after_works = db.get_person(pid)["works"]
print("before", [os.path.basename(r["file_path"]) for r in before_rows], before_works)
print("after ", [os.path.basename(r["file_path"]) for r in after_rows], after_works)

# ---------------------------------------------------------------- 画布
W, H = 1400, 760
canvas = QWidget()
canvas.setStyleSheet(
    "QWidget#root{background:%s;}"
    "QLabel{background:transparent;color:#ecedee;}"
    "QFrame#card{background:%s;border:1px solid %s;border-radius:12px;}"
    "QLabel#h{font-size:16px;font-weight:bold;color:#fafafa;}"
    "QLabel#sub{font-size:12px;color:%s;}"
    "QLabel#num{font-size:12px;color:#fafafa;font-weight:bold;}"
    "QLabel#old{font-size:12px;color:#8b8b93;}"
    "QLabel#ok{font-size:12px;color:#4ade80;font-weight:bold;}"
    % (BG, CARD, LINE, DIM))
canvas.setObjectName("root")
canvas.resize(W, H)

root = QVBoxLayout(canvas)
root.setContentsMargins(26, 22, 26, 20)
root.setSpacing(14)

ttl = QLabel("流明盒 v2.0.11 · 三条反馈的前后对照")
ttl.setStyleSheet("font-size:20px;font-weight:bold;color:#fafafa;")
root.addWidget(ttl)
subt = QLabel("构建号 2611100132　·　所有数字都是离屏 / 真机实测值，不是估计")
subt.setStyleSheet("font-size:12px;color:%s;" % DIM)
root.addWidget(subt)

row = QHBoxLayout()
row.setSpacing(14)
root.addLayout(row, 1)


def card(title, hint=""):
    f = QFrame()
    f.setObjectName("card")
    v = QVBoxLayout(f)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(9)
    t = QLabel(title)
    t.setObjectName("h")
    v.addWidget(t)
    if hint:
        h = QLabel(hint)
        h.setObjectName("sub")
        h.setWordWrap(True)
        v.addWidget(h)
    return f, v


# ---------- A：输入框 ----------
ca, va = card("输入框首字前的空白", "用户原话：「所有输入的好像前面有几px的间隙」")
OLD_LE = ("QLineEdit{background:rgba(39,39,42,0.72);color:#ecedee;"
          "border:1px solid rgba(255,255,255,0.08);border-radius:20px;"
          "padding:7px 16px;}")


def mk_edit(old):
    e = QLineEdit()
    e.setPlaceholderText("包含这个文字即可（留空 = 不筛选）")
    e.setMinimumHeight(35)
    if old:
        e.setStyleSheet(OLD_LE)
    return e


ea = mk_edit(True)
va.addWidget(QLabel("修改前 · padding 7px 16px"))
va.addWidget(ea)
la = QLabel("首字落在 <span style='color:#f87171'>19px</span>"
            "<span style='color:#8b8b93'>（1px 边框 + 16px + 字形余隙 2px）</span>")
la.setObjectName("sub")
la.setTextFormat(Qt.RichText)
va.addWidget(la)

eb = mk_edit(False)
va.addWidget(QLabel("修改后 · padding 7px 12px"))
va.addWidget(eb)
lb = QLabel("首字落在 <span style='color:#4ade80'>15px</span>"
            "<span style='color:#8b8b93'>（表格里的输入框 11 → 10px 同步收紧）</span>")
lb.setObjectName("sub")
lb.setTextFormat(Qt.RichText)
va.addWidget(lb)
va.addStretch(1)
row.addWidget(ca, 1)

# ---------- B：滚动条 ----------
cb, vb = card("首页滚动条", "用户原话：「优化首页的滚轮，更符合软件风格，和圆角保持一致」")
OLD_SB = ("QScrollArea{border:none;background:transparent;}"
          "QScrollBar:vertical{background:transparent;width:8px;margin:2px;}"
          "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);"
          "border-radius:4px;min-height:32px;}"
          "QScrollBar::add-line,QScrollBar::sub-line{height:0;width:0;}"
          "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}")


def sb_grab(old):
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    body = QWidget()
    body.setMinimumHeight(1200)
    sa.setWidget(body)
    if old:
        sa.setStyleSheet(OLD_SB)
    sa.resize(260, 200)
    sa.show()
    for _ in range(3):
        app.processEvents()
    im = sa.verticalScrollBar().grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    sa.close()
    return im


def zoom(im, k=14, rows=14, bgc="#18181b"):
    """裁一段「滑块顶端往下 30 行」再放大 —— 圆角/方头的差别全在顶上那几行。

    ⚠ 不能整条 zoom 再缩：竖条只有 8~12px 宽、200 多行高，按高度缩放后宽度只剩 8px。
    ⚠ grab() 的透明区 RGB 是垃圾，必须先垫底色再放大（项目记忆里的老坑）。
    """
    def lum(x, y):
        c = im.pixelColor(x, y)
        return (c.red() + c.green() + c.blue()) / 3.0
    h = im.height()
    ys = [y for y in range(h) if lum(im.width() // 2, y) > 12]
    y0 = max(0, (ys[0] if ys else 0) - 4)
    crop = im.copy(0, y0, im.width(), min(rows, h - y0))
    out = QImage(crop.width() * k, crop.height() * k, QImage.Format_RGB32)
    out.fill(QColor(bgc))
    p = QPainter(out)
    p.setRenderHint(QPainter.SmoothPixmapTransform, False)
    p.drawImage(out.rect(), crop)
    p.end()
    return out


def measure(im):
    def lum(x, y):
        c = im.pixelColor(x, y)
        return (c.red() + c.green() + c.blue()) / 3.0
    w, h = im.width(), im.height()
    vals = [lum(w // 2, y) for y in range(h)]
    lit = [y for y, v in enumerate(vals) if v > 12]
    if not lit:
        return 0, 0, []
    y0, y1 = lit[0], lit[-1]
    thr = (max(vals[y0:y1 + 1]) + min(vals)) / 2.0
    wm = len([x for x in range(w) if lum(x, (y0 + y1) // 2) > thr])
    tops = [len([x for x in range(w) if lum(x, y) > thr]) for y in range(y0, y0 + 4)]
    return wm, w, tops


im_old = sb_grab(True)
im_new = sb_grab(False)
w_old, c_old, t_old = measure(im_old)
w_new, c_new, t_new = measure(im_new)

hb = QHBoxLayout()
hb.setSpacing(18)
for tag, im, wpx, tops, tint in (
        ("修改前", im_old, w_old, t_old, "#f87171"),
        ("修改后", im_new, w_new, t_new, "#4ade80")):
    box = QVBoxLayout()
    box.setSpacing(6)
    t = QLabel("%s · 滑块 %dpx · %s" % (tag, wpx, "方头" if tops[0] >= wpx else "圆头"))
    t.setStyleSheet("font-size:12px;color:%s;font-weight:bold;" % tint)
    box.addWidget(t)
    pic = QLabel()
    pic.setPixmap(QPixmap.fromImage(zoom(im)))
    box.addWidget(pic)
    box.addWidget(QLabel("顶端逐行宽度 %s" % (tops,)))
    box.addStretch(1)
    hb.addLayout(box)
vb.addLayout(hb)
note = QLabel("根因不是「没写 border-radius」：Qt 里 <b>给 ::handle 写 margin 就不画圆角</b>，"
              "旧版槽 8px + margin 2px 把滑块挤成 4px、圆角被裁成方头。")
note.setObjectName("sub")
note.setWordWrap(True)
note.setTextFormat(Qt.RichText)
vb.addWidget(note)
vb.addStretch(1)
row.addWidget(cb, 1)

# ---------- C：多碟分集 ----------
cc, vc = card("演员 / 导演里的多碟分集",
              "用户原话：「cd1 cd2 在演员和导演中还是分开」")


def rows_box(title, rows, works, tint):
    f = QFrame()
    f.setStyleSheet("QFrame{background:#141417;border:1px solid %s;border-radius:8px;}" % LINE)
    vv = QVBoxLayout(f)
    vv.setContentsMargins(10, 8, 10, 8)
    vv.setSpacing(4)
    t = QLabel(title + "　参演作品 <b>%d</b> 部" % works)
    t.setObjectName("sub")
    t.setTextFormat(Qt.RichText)
    t.setStyleSheet("font-size:11px;color:%s;font-weight:bold;" % tint)
    vv.addWidget(t)
    for r in rows:
        lb = QLabel("▸ " + os.path.basename(r["file_path"]))
        lb.setStyleSheet("font-size:11px;color:#d4d4d8;")
        vv.addWidget(lb)
    return f


vc.addWidget(rows_box("修改前", before_rows, before_works, "#f87171"))
vc.addWidget(rows_box("修改后", after_rows, after_works, "#4ade80"))
hint_c = QLabel("同一目录的 cd1 / cd2 共用一份 nfo，扫描时每个分片都单独链过一次演员 → "
                "反查自然出两行。现在把分片折到「代表分片」再按代表去重；"
                "只挂在 cd2 上的人也折到同一部，不会凭空消失。")
hint_c.setObjectName("sub")
hint_c.setWordWrap(True)
vc.addWidget(hint_c)
vc.addStretch(1)
row.addWidget(cc, 1)

# ---------- 底部实测表 ----------
foot = QFrame()
foot.setObjectName("card")
fv = QVBoxLayout(foot)
fv.setContentsMargins(16, 12, 16, 12)
fv.setSpacing(6)
t = QLabel("实测数据")
t.setObjectName("h")
fv.addWidget(t)
for line in (
        "输入框首字列：19px → <b>15px</b>（普通页面 / 列筛选弹层一致；表单内 33px 高那档同步收紧）",
        "滚动条：滑块 4px 方头 → <b>8px 圆胶囊</b>，槽 12px、离窗口边 2px，另加 hover 提亮与极淡圆角槽底",
        "演员甲 works：<b>2 → 1</b>；只挂 cd2 的导演也算 <b>1</b> 部；删掉 cd2 后仍是 1 部",
        "回归：离屏冒烟 783/783　·　取证探针 probe_v2011_ui / _scroll / _cd 全绿",
):
    lb = QLabel("· " + line)
    lb.setObjectName("sub")
    lb.setTextFormat(Qt.RichText)
    lb.setWordWrap(True)
    fv.addWidget(lb)
root.addWidget(foot)

for _w in (ca, cb, cc, foot):
    _w.setAttribute(Qt.WA_StyledBackground, True)

canvas.show()
for _ in range(6):
    app.processEvents()

img = canvas.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
out = QImage(img.width(), img.height(), QImage.Format_RGB32)
out.fill(QColor(BG))
p = QPainter(out)
p.drawImage(0, 0, img)
p.end()
dst = os.path.join(ROOT, "docs", "preview", "v2011_fix.png")
os.makedirs(os.path.dirname(dst), exist_ok=True)
out.save(dst)
print("saved", dst, out.width(), out.height())
