# -*- coding: utf-8 -*-
"""v2.0.8 探针：表头图标只在「鼠标所在的那一列」显示。

量法：抓表头图像，按 `_zones()` 算出的每个图标区，数「明显比底色亮」的像素个数。
  · 未悬停时，普通列的图标区应该是 0（没有墨迹）；
  · 悬停第 N 列后，第 N 列两个区都 > 0，其它列仍为 0；
  · 有筛选的那一列，即使没悬停，漏斗区也要 > 0（常驻提示）。
"""
import os, sys, tempfile
os.environ.setdefault('LMC_NO_SYSMON', '1')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = r'E:/【01】自研软件/【26-19】本地影视中心'
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix='lmc_v208hdr_')
os.makedirs(os.path.join(TMP, 'index_data', 'logs'), exist_ok=True)
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, QPoint
app = QApplication(sys.argv)
for f in [r'C:/Windows/Fonts/msyh.ttc']:
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import database as db
import config as cfg
import applog
db.db_path = lambda: os.path.join(TMP, 'index_data', 'media_center.db')
cfg.config_path = lambda: os.path.join(TMP, 'settings.json')
cfg._SETTINGS = None
applog.base_dir = lambda: TMP
db.init_db()
try:
    cfg.get_settings().home_columns = ['title', 'favorite', 'year', 'user_rating']
    cfg.get_settings().save()
except Exception as e:
    print('set cols fail', e)

import main_window
main_window.load_style(app)
import ui_home

rows = [{'kind': 'movie', 'title': 'P%d' % i, 'year': 2020 + i % 5,
         'file_path': 'E:/m/%d.mp4' % i, 'favorite': i % 2} for i in range(30)]
conn = db.get_conn()
conn.executemany(
    'INSERT INTO media (kind,title,year,file_path,favorite,added_time) VALUES (?,?,?,?,?,?)',
    [(r['kind'], r['title'], r['year'], r['file_path'], r['favorite'], 1700000000 + i)
     for i, r in enumerate(rows)])
conn.commit()

lv = ui_home.HomeListView()
lv.resize(1300, 700)
lv.show()
for _ in range(8):
    app.processEvents()

hdr = lv._header
img = hdr.grab().toImage()
# 表头底色：取标题列中部的空白处（离图标很远），之后的墨迹判定一律相对它，
# 这样深色/浅色主题都成立（离屏默认样式是白底，硬编码「比底色亮」会全量命中）。
_c = img.pixelColor(200, 8)
BG = (_c.red(), _c.green(), _c.blue())
print('表头底色', BG)


def ink(x0, x1, y0=6, y1=None):
    """数一块区域里「明显不同于表头底色」的像素。"""
    y1 = y1 if y1 is not None else hdr.height() - 6
    n = 0
    for y in range(int(y0), int(y1)):
        for x in range(int(x0), int(x1)):
            c = img.pixelColor(x, y)
            if (abs(c.red() - BG[0]) + abs(c.green() - BG[1]) + abs(c.blue() - BG[2])) > 40:
                n += 1
    return n


def zones():
    out = {}
    for i in range(hdr.count()):
        z = hdr._zones(i)
        if z is None:
            continue
        (f0, f1), (t0, t1) = z
        out[i] = (f0, f1, t0, t1)
    return out


print('列数', hdr.count(), '列宽', [hdr.sectionSize(i) for i in range(hdr.count())])
Z = zones()
print('hdr.size =', hdr.size(), ' viewport =', hdr.viewport().size())
print('zones =', Z)
print('grab size =', img.size())

print('\n--- A. 未悬停（应只有 0 个图标）---')
for i, (f0, f1, t0, t1) in Z.items():
    print('  列%d 漏斗墨迹=%3d  三角墨迹=%3d' % (i, ink(f0, f1), ink(t0, t1)))

print('\n--- B. 悬停第 1 列 ---')
hdr._hover_section = 1
hdr.viewport().update()
for _ in range(4):
    app.processEvents()
img = hdr.grab().toImage()
for i, (f0, f1, t0, t1) in Z.items():
    print('  列%d 漏斗墨迹=%3d  三角墨迹=%3d' % (i, ink(f0, f1), ink(t0, t1)))

print('\n--- C. 第 3 列有筛选（未悬停）---')
lv._filters = {'user_rating': {'mode': 'num', 'op': '>=', 'value': '7'}}
hdr._hover_section = -1
hdr.viewport().update()
for _ in range(4):
    app.processEvents()
img = hdr.grab().toImage()
for i, (f0, f1, t0, t1) in Z.items():
    print('  列%d 漏斗墨迹=%3d  三角墨迹=%3d' % (i, ink(f0, f1), ink(t0, t1)))

hdr.grab().save(r'C:/Users/zouzu/AppData/Local/Temp/v208/hdr_filtered.png')
lv._filters = {}
hdr._hover_section = 2
hdr.viewport().update()
for _ in range(4):
    app.processEvents()
hdr.grab().save(r'C:/Users/zouzu/AppData/Local/Temp/v208/hdr_hover.png')
print('\n图已存: hdr_filtered.png / hdr_hover.png')
