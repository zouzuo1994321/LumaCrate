# -*- coding: utf-8 -*-
"""v2.0.8 外观探针：量标签芯片的「圆角是否真画出来」「× 是否在圆心」。

判定方法（都在离屏 grab 出来的像素上做）：
· 圆角：胶囊左上角 (x0, y0) 与 (x0+3, y0+3) 若与**容器底色**同色 → 角被切掉了（有圆角）；
        若等于胶囊内的边框色 → 直角。
  另外沿「胶囊中线那一行」往左扫，找出第一枚非底色像素的 x，与理论圆弧起点比对。
· 叉号居中：在 14×14 的徽章里取墨迹（亮度 > 110）的 bbox，中心应 ≈ (7, 7)。
"""
import os, sys
os.environ.setdefault('LMC_NO_SYSMON', '1')
ROOT = r'E:/【01】自研软件/【26-19】本地影视中心'
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt
from PIL import Image

app = QApplication.instance() or QApplication(sys.argv)
for f in [r'C:/Windows/Fonts/msyh.ttc', r'C:/Windows/Fonts/msyhbd.ttc']:
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)
import main_window
main_window.load_style(app)
import ui_hero

OUT = r'C:/Users/zouzu/AppData/Local/Temp/v208'
os.makedirs(OUT, exist_ok=True)


def shot(w, name):
    w.show()
    for _ in range(4):
        app.processEvents()
    pm = w.grab()
    p = os.path.join(OUT, name)
    pm.save(p)
    return pm, p


def rgb(img, x, y):
    c = img.pixelColor(int(x), int(y))
    return (c.red(), c.green(), c.blue())


# ---------- 1. 标签芯片 ----------
host = QWidget()
host.setStyleSheet("background:#1c1c1f;")
lay = QVBoxLayout(host)
lay.setContentsMargins(24, 24, 24, 24)
lay.setSpacing(10)
row = QHBoxLayout()
row.setSpacing(8)
chips = [ui_hero.TagChip(t) for t in ("業餘", "第一人稱攝影", "苗條")]
for c in chips:
    row.addWidget(c)
row.addStretch(1)
lay.addLayout(row)
host.resize(560, 110)
pm, path = shot(host, 'probe_tags.png')
img = pm.toImage()
BG = rgb(img, 2, 2)
print('容器底色', BG)

for c in chips:
    x0, y0 = c.x() + 24 - 24, c.y()      # chip 坐标是相对 host 的（在 row 布局里）
    x0, y0 = c.mapTo(host, c.rect().topLeft()).x(), c.mapTo(host, c.rect().topLeft()).y()
    w, h = c.width(), c.height()
    pill_top = y0 + ui_hero.TagChip.OVER
    print('\n[%s] chip=(%d,%d) %dx%d 胶囊顶=%d' % (c._text, x0, y0, w, h, pill_top))
    corner = rgb(img, x0 + 1, pill_top + 1)
    edge_mid = None
    for xx in range(x0, x0 + w // 2):
        if rgb(img, xx, pill_top + 8) != BG:
            edge_mid = xx
            break
    print('  左上角(1,1) =', corner, ' 中线左起首个非底色 x =', edge_mid, '(chip x0=%d)' % x0)
    print('  圆角判定:', 'OK（角上是底色，圆弧收进去了）'
          if sum(abs(a - b) for a, b in zip(corner, BG)) < 24 else 'FAIL（角上是边框色=直角）')
    # 徽章
    d = c._dot
    bx, by = d.mapTo(host, d.rect().topLeft()).x(), d.mapTo(host, d.rect().topLeft()).y()
    bright = []
    for yy in range(by, by + d.height()):
        for xx in range(bx, bx + d.width()):
            r, g, b = rgb(img, xx, yy)
            if (r + g + b) / 3 > 110:
                bright.append((xx - bx, yy - by))
    if bright:
        xs = [p[0] for p in bright]
        ys = [p[1] for p in bright]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        print('  徽章中心 (%.2f, %.2f)  理论 (%.1f, %.1f)  偏移 (%.2f, %.2f)'
              % (cx, cy, d.width() / 2.0, d.height() / 2.0,
                 cx - d.width() / 2.0, cy - d.height() / 2.0))
    else:
        print('  徽章里没量到墨迹！')

# ---------- 2. 悬停态徽章（红底白叉）----------
host2 = QWidget()
host2.setStyleSheet("background:#1c1c1f;")
v2 = QVBoxLayout(host2)
v2.setContentsMargins(24, 24, 24, 24)
c2 = ui_hero.TagChip("第一人稱攝影")
v2.addWidget(c2)
host2.resize(300, 90)
c2._dot._hover = True
c2._hover = True
pm2, _ = shot(host2, 'probe_tags_hover.png')
img2 = pm2.toImage()
bx = c2._dot.mapTo(host2, c2._dot.rect().topLeft()).x()
by = c2._dot.mapTo(host2, c2._dot.rect().topLeft()).y()
print('\n悬停徽章底色', rgb(img2, bx + 2, by + 7), '（应为偏红 ~(248,113,113)）')
bright = []
for yy in range(by, by + 14):
    for xx in range(bx, bx + 14):
        r, g, b = rgb(img2, xx, yy)
        if r > 230 and g > 230 and b > 230:
            bright.append((xx - bx, yy - by))
if bright:
    xs = [p[0] for p in bright]
    ys = [p[1] for p in bright]
    print('  白叉中心 (%.2f, %.2f) 理论 (7.0, 7.0)'
          % ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0))

# ---------- 3. 详情页：评分按钮 + 元数据行颜色 ----------
media = {"id": None, "title": "T", "rating": 5.0, "year": 2026, "genres": "剧情",
         "runtime": "01:10:00", "certification": "JP-18+", "kind": "movie",
         "tags": "業餘,第一人稱攝影", "plot": "x", "file_path": "E:/a.mp4",
         "favorite": 0, "user_rating": None}
hv = ui_hero.HeroView(dict(media))
hv.resize(1200, 1000)
hv.show()
for _ in range(6):
    app.processEvents()
pm3 = hv.grab()
pm3.save(os.path.join(OUT, 'probe_detail.png'))
img3 = pm3.toImage()


def text_color_in(img, x, y, w, h, thr=120):
    """取一块区域里最亮的 20% 像素的平均色 —— 即「字是什么颜色」。"""
    pts = []
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            r, g, b = rgb(img, xx, yy)
            pts.append((r + g + b, (r, g, b)))
    pts.sort(reverse=True)
    top = pts[:max(3, len(pts) // 5)]
    n = len(top)
    return tuple(sum(p[1][i] for p in top) // n for i in range(3))


btn = hv._rate_btn
bx, by = btn.mapTo(hv, btn.rect().topLeft()).x(), btn.mapTo(hv, btn.rect().topLeft()).y()
print('\n「评分」按钮 几何 (%d,%d) %dx%d' % (bx, by, btn.width(), btn.height()))
print('  按钮文字色 ≈', text_color_in(img3, bx + 4, by + 4, btn.width() - 8, btn.height() - 8),
      '（白字应三通道接近且都很亮）')

meta = hv._meta
item = meta.itemAt(0)
w0 = item.widget()
mx = w0.mapTo(hv, w0.rect().topLeft()).x()
my = w0.mapTo(hv, w0.rect().topLeft()).y()
print('  元数据第 1 项 = %r  几何 (%d,%d)' % (w0.text(), mx, my))
print('  元数据评分色 ≈',
      text_color_in(img3, mx, my, w0.width(), w0.height()),
      '（金色应 r 高、g 中、b 低）')
item1 = meta.itemAt(1).widget()
m1x = item1.mapTo(hv, item1.rect().topLeft()).x()
print('  元数据第 2 项色 ≈',
      text_color_in(img3, m1x, my, item1.width(), item1.height()), '（应仍是灰白）')
