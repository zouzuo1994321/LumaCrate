# -*- coding: utf-8 -*-
"""v1.38.0 预览出图：把新增的「演员检测多选批量确认关联」渲染成 PNG 便于肉眼校验。

使用临时数据库，不读写真实索引。产出：
  v1380_actorcheck.png   演员检测页：结果树最左「选择」复选框列 + 下方「全选/全不选/
                          批量确认关联（合并 N 簇）」工具栏；左侧勾选多簇、右侧显示某簇详情。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase

app = QApplication(sys.argv)

import database as db
import applog
import ui_actorcheck as ack_page
from main_window import load_style

TMP = tempfile.mkdtemp(prefix="lmc_prev_v1380_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)

load_style(app)

page = ack_page.ActorCheckPage()

# 造 4 个建议合并簇（不同艺名同一人），1 对存疑
page._res = {"merge_people": 5}
page._suspects = [
    {"a": {"id": 91, "name": "田中ゆか", "works": 3, "photo": "", "prof": {}, "romaji": "tanaka yuka"},
     "b": {"id": 92, "name": "田中由香", "works": 2, "photo": "", "prof": {}, "romaji": "tanaka yuka"},
     "score": 55, "tier": "存疑", "reasons": ["罗马音相近但生日不同，疑似同名不同人"]},
]
page._clusters = [
    {"ids": [10, 20], "keep_id": 10, "score": 95, "tier": "铁证",
     "reasons": ["罗马音完全一致", "生日与三围逐字相同"], "total_works": 7,
     "members": [{"id": 10, "name": "明里つくし", "works": 6, "photo": "", "prof": {}, "romaji": "akari tsukushi"},
                 {"id": 20, "name": "つくし明里", "works": 1, "photo": "", "prof": {}, "romaji": "tsukushi akari"}]},
    {"ids": [11, 21], "keep_id": 11, "score": 88, "tier": "很高",
     "reasons": ["别名互指", "出生日一致"], "total_works": 4,
     "members": [{"id": 11, "name": "佐藤れいな", "works": 3, "photo": "", "prof": {}, "romaji": "sato reina"},
                 {"id": 21, "name": "レイナ佐藤", "works": 1, "photo": "", "prof": {}, "romaji": "reina sato"}]},
    {"ids": [12, 22], "keep_id": 12, "score": 82, "tier": "高",
     "reasons": ["罗马音归并后同形"], "total_works": 5,
     "members": [{"id": 12, "name": "鈴木みお", "works": 4, "photo": "", "prof": {}, "romaji": "suzuki mio"},
                 {"id": 22, "name": "みお鈴木", "works": 1, "photo": "", "prof": {}, "romaji": "mio suzuki"}]},
    {"ids": [13, 23], "keep_id": 13, "score": 78, "tier": "高",
     "reasons": ["姓名规范化后相同"], "total_works": 3,
     "members": [{"id": 13, "name": "高橋しずく", "works": 2, "photo": "", "prof": {}, "romaji": "takahashi shizuku"},
                 {"id": 23, "name": "シズク高橋", "works": 1, "photo": "", "prof": {}, "romaji": "shizuku takahashi"}]},
]
page._fill_tree()

# 勾选后 3 簇（演示批量合并计数），并在右侧显示第 1 簇详情
def _cluster_items():
    out = []
    for i in range(page.tree.topLevelItemCount()):
        top = page.tree.topLevelItem(i)
        for j in range(top.childCount()):
            it = top.child(j)
            if it.data(0, page.ROLE_KIND) == "cluster":
                out.append(it)
    return out

items = _cluster_items()
for it in items[1:]:
    it.setCheckState(0, ack_page.Qt.Checked)
page.tree.setCurrentItem(items[0])   # 触发 _on_select → 右侧显示第 1 簇详情

page.resize(980, 760)
page.show()
for _ in range(5):
    app.processEvents()

page.grab().save(os.path.join(OUT, "v1380_actorcheck.png"))
print("saved v1380_actorcheck.png")
print("batch_btn text:", page.batch_merge_btn.text(), "enabled:", page.batch_merge_btn.isEnabled())

# ---- 真机尺寸下的「设置 → 演员检测」页（验证新增工具栏不会被裁掉）----
from ui_settings import SettingsDialog

dlg = SettingsDialog(None)
dlg.resize(1000, 900)          # 与真机同尺寸（SettingsDialog 的尺寸算法在 1920x1080 下的取值）
dlg.show()
app.processEvents()
dlg._show("演员检测")
app.processEvents()
pg = dlg._pg_actorcheck
pg._res = {"merge_people": 4}
pg._suspects = [
    {"a": {"id": 91, "name": "田中ゆか", "works": 3, "photo": "", "prof": {}, "romaji": "tanaka yuka"},
     "b": {"id": 92, "name": "田中由香", "works": 2, "photo": "", "prof": {}, "romaji": "tanaka yuka"},
     "score": 55, "tier": "存疑", "reasons": ["罗马音相近但生日不同，疑似同名不同人"]},
]
pg._clusters = [
    {"ids": [10, 20], "keep_id": 10, "score": 95, "tier": "铁证",
     "reasons": ["罗马音完全一致"], "total_works": 7,
     "members": [{"id": 10, "name": "明里つくし", "works": 6, "photo": "", "prof": {}, "romaji": "akari tsukushi"},
                 {"id": 20, "name": "つくし明里", "works": 1, "photo": "", "prof": {}, "romaji": "tsukushi akari"}]},
    {"ids": [11, 21], "keep_id": 11, "score": 88, "tier": "很高",
     "reasons": ["别名互指"], "total_works": 4,
     "members": [{"id": 11, "name": "佐藤れいな", "works": 3, "photo": "", "prof": {}, "romaji": "sato reina"},
                 {"id": 21, "name": "レイナ佐藤", "works": 1, "photo": "", "prof": {}, "romaji": "reina sato"}]},
    {"ids": [12, 22], "keep_id": 12, "score": 82, "tier": "高",
     "reasons": ["罗马音归并后同形"], "total_works": 5,
     "members": [{"id": 12, "name": "鈴木みお", "works": 4, "photo": "", "prof": {}, "romaji": "suzuki mio"},
                 {"id": 22, "name": "みお鈴木", "works": 1, "photo": "", "prof": {}, "romaji": "mio suzuki"}]},
    {"ids": [13, 23], "keep_id": 13, "score": 78, "tier": "高",
     "reasons": ["姓名规范化后相同"], "total_works": 3,
     "members": [{"id": 13, "name": "高橋しずく", "works": 2, "photo": "", "prof": {}, "romaji": "takahashi shizuku"},
                 {"id": 23, "name": "シズク高橋", "works": 1, "photo": "", "prof": {}, "romaji": "shizuku takahashi"}]},
]
pg._fill_tree()
_items = []
for _i in range(pg.tree.topLevelItemCount()):
    _top = pg.tree.topLevelItem(_i)
    for _j in range(_top.childCount()):
        _it = _top.child(_j)
        if _it.data(0, pg.ROLE_KIND) == "cluster":
            _items.append(_it)
for _it in _items[:2]:
    _it.setCheckState(0, ack_page.Qt.Checked)
pg.tree.setCurrentItem(_items[0])
for _ in range(6):
    app.processEvents()
_btn_geo = pg.batch_merge_btn.mapTo(dlg, pg.batch_merge_btn.rect().topLeft())
print("dialog batch_btn top-left in dlg:", _btn_geo.x(), _btn_geo.y(),
      "| visible:", pg.batch_merge_btn.isVisibleTo(dlg),
      "| dlg size:", dlg.width(), "x", dlg.height())
dlg.grab().save(os.path.join(OUT, "v1380_actorcheck_dialog.png"))
print("saved v1380_actorcheck_dialog.png")

print("OUT:", OUT)
