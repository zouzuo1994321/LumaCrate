# -*- coding: utf-8 -*-
"""v1.39.0 预览出图：三条反馈的可视化验收。

产出（dev/screenshots/）：
  v1390_actorcheck.png        演员检测页：复选框列修复后可见（多簇勾选态）
  v1390_actorcheck_zoom.png   同上，复选框列 2 倍放大（17×17 方块清晰可验）
  v1390_settings_nav_ring.png 工具窗：左侧导航「演员检测」项旁转圈（需求 3）
  v1390_settings_nav_zoom.png 工具窗左侧导航区放大（转圈与按钮的相对位置）

使用临时数据库，不读写真实索引。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = tempfile.mkdtemp(prefix="lmc_prev_v1390_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

import database as db
import applog
import ui_actorcheck as ack_page
from main_window import load_style

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)

load_style(app)


def _clusters_data():
    """4 个建议合并簇 + 1 对存疑（与 v1.38.0 出图同规格，便于对比）。"""
    return {
        "merge_people": 5,
        "suspects": [
            {"a": {"id": 91, "name": "田中ゆか", "works": 3, "photo": "", "prof": {}, "romaji": "tanaka yuka"},
             "b": {"id": 92, "name": "田中由香", "works": 2, "photo": "", "prof": {}, "romaji": "tanaka yuka"},
             "score": 55, "tier": "存疑", "reasons": ["罗马音相近但生日不同，疑似同名不同人"]},
        ],
        "clusters": [
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
        ],
    }


def _cluster_items(pg):
    out = []
    for i in range(pg.tree.topLevelItemCount()):
        top = pg.tree.topLevelItem(i)
        for j in range(top.childCount()):
            it = top.child(j)
            if it.data(0, pg.ROLE_KIND) == "cluster":
                out.append(it)
    return out


def _fill(pg):
    d = _clusters_data()
    pg._res = {"merge_people": d["merge_people"]}
    pg._suspects = d["suspects"]
    pg._clusters = d["clusters"]
    pg._fill_tree()


# ================================================================ ① 演员检测页（复选框列）
print("---- ① 演员检测页：复选框列修复后可见 ----")
page = ack_page.ActorCheckPage()
_fill(page)
items = _cluster_items(page)
# 前 3 簇勾选（演示批量合并计数 = 3），第 4 簇不勾；右侧显示第 1 簇详情
for it in items[:3]:
    it.setCheckState(0, Qt.Checked)
page.tree.setCurrentItem(items[0])
page.resize(980, 760)
page.show()
for _ in range(6):
    app.processEvents()
page.grab().save(os.path.join(OUT, "v1390_actorcheck.png"))
print("saved v1390_actorcheck.png | batch_btn:", page.batch_merge_btn.text(),
      "enabled:", page.batch_merge_btn.isEnabled())

# 复选框列 2 倍放大（列 0 宽 62 → 裁前 ~90px，覆盖两行簇行）
tree_img = page.tree.grab().toImage()
print("tree grab size:", tree_img.width(), "x", tree_img.height())

# ================================================================ ② 工具窗：导航转圈
print("---- ② 工具窗：左侧导航「进行中」转圈 ----")
from ui_settings import SettingsDialog

dlg = SettingsDialog(None)
dlg.resize(1000, 900)
dlg.show()
app.processEvents()
dlg._show("演员检测")
app.processEvents()

# 让「演员检测」页处于忙碌态（转圈的触发条件），再走一遍轮询刷新
_img_page = dlg._pg_imagedetect.widget() if hasattr(dlg._pg_imagedetect, "widget") else None
dlg._pg_actorcheck.is_busy = lambda: True
dlg._refresh_nav_rings()
for _ in range(8):        # 让转圈动画转过几帧（QTimer 45ms/帧）
    app.processEvents()

ring = dlg.nav_rings["演员检测"]
print("nav ring busy:", ring.is_busy(), "visible:", ring.isVisible(),
      "pos in dialog:", ring.mapTo(dlg, ring.rect().topLeft()).x(),
      ring.mapTo(dlg, ring.rect().topLeft()).y())

dlg.grab().save(os.path.join(OUT, "v1390_settings_nav_ring.png"))
print("saved v1390_settings_nav_ring.png")

# 左侧导航区放大（nav_frame 宽 150，整条裁出来即可看清转圈与按钮的相对位置）
nav_img = dlg.nav_frame.grab().toImage()
print("nav_frame grab size:", nav_img.width(), "x", nav_img.height())
dlg.nav_frame.grab().save(os.path.join(OUT, "v1390_settings_nav_zoom.png"))
print("saved v1390_settings_nav_zoom.png")

# 还原（不影响后续可能的其它截图）
dlg._pg_actorcheck.is_busy = lambda: False
dlg._refresh_nav_rings()

print("OUT:", OUT)
