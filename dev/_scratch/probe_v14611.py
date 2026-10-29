# -*- coding: utf-8 -*-
"""v1.46.11 探针：①右键批量菜单 ②悬停不再叠加 ③回收站删除。"""
import os
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/probe_v14611"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import applog

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import database as db

DB = os.path.join(TMP, "index_data", "p.db")
os.makedirs(os.path.join(TMP, "index_data"), exist_ok=True)
if os.path.exists(DB):
    DB = os.path.join(TMP, "index_data", "p_%d.db" % time.time())
db.db_path = lambda: DB
db.init_db()

import main_window as mw
import ui_home

mw.load_style(app, cfg.DEFAULT_APPEARANCE)

ids = []
for i in range(5):
    fp = os.path.join(TMP, "v%02d.mp4" % i)
    open(fp, "wb").write(b"\x00" * 32)
    mid = db.upsert_media_by_path(mode="overwrite", kind="movie",
                                  title="PROBE-%02d 测试作品" % i, year=2026,
                                  runtime="01:00:00", file_path=fp,
                                  library="演示库", genres="剧情", studio="同人配信",
                                  premiere="2026-10-01", file_size=1024)
    ids.append(mid)

CALLS = []
lv = ui_home.HomeListView(on_bulk_action=lambda a, ms: CALLS.append((a, len(ms))))
lv.resize(1200, 800)
lv.show()
for _ in range(60):
    app.processEvents()
    time.sleep(0.01)

FAILS = []


def check(name, ok, detail=""):
    print(("[OK]   " if ok else "[FAIL] ") + name + ("  " + str(detail) if detail else ""),
          flush=True)
    if not ok:
        FAILS.append(name)


print("== ① 右键批量菜单 ==")
check("表格设置了自定义右键菜单", lv.table.contextMenuPolicy() == mw.Qt.CustomContextMenu,
      lv.table.contextMenuPolicy())
lv.table.clearSelection()
lv.table.selectRow(1)
one = lv.selected_medias()
check("单选：selected_medias 返回 1 项", len(one) == 1, len(one))
menu = lv._build_context_menu(one)
texts = [a.text() for a in menu.actions() if not a.isSeparator()]
check("单选菜单 5 项且顺序正确",
      texts == ["播放选中视频", "打开视频文件夹", "刷新数据", "删除数据", "删除源文件"],
      texts)
check("单选菜单文案不带数量后缀", all("项）" not in t for t in texts), texts)

# 全选
lv.table.selectAll()
many = lv.selected_medias()
check("全选：selected_medias 返回 5 项", len(many) == 5, len(many))
menu2 = lv._build_context_menu(many)
texts2 = [a.text() for a in menu2.actions() if not a.isSeparator()]
check("全选菜单每项都带（5 项）",
      all(t.endswith("（5 项）") for t in texts2), texts2)

# 触发一次（走 on_bulk_action 回调）
acts = getattr(menu2, "_actions_by_key", {})
check("按动作键能取到 5 个 action", set(acts) == {"play", "folder", "refresh",
                                                 "delete_index", "delete_files"},
      sorted(acts))
acts["delete_index"].trigger()
check("点菜单 → 回调拿到动作键与整批 5 项",
      CALLS and CALLS[-1] == ("delete_index", 5), CALLS)

print()
print("== ② 悬停不再叠加 ==")
import inspect
setrow = inspect.getsource(ui_home.HomeListView._set_row)
check("_set_row 不再给单元格挂 tooltip（叠层的另一个来源）",
      "item.setToolTip" not in setrow and "self.table.setItem" in setrow)
qss = open(os.path.join(ROOT, "src", "style.qss"), encoding="utf-8").read()
seg = qss.split("QFrame#HoverCard")[1][:200]
check("悬停卡底色改成不透明（rgba 半透明会让列表文字透出来）",
      "background: #17130f;" in seg and "__DLG__" not in seg, seg.split("}")[0])

# 悬停卡内容仍是完整信息
lv.table.selectRow(2)
m = lv.selected_medias()[0]
pv = lv._preview
pv.set_media(m)
check("悬停卡仍显示标题", m["title"] in pv.title.text(), pv.title.text())
check("悬停卡有副行（年份/时长）", "2026" in pv.sub.text(), pv.sub.text())
check("悬停卡有信息行（制片/上映）",
      "制片" in pv.info.text() and "上映" in pv.info.text(), pv.info.text().replace("\n", " | "))

print()
print("== ③ 删除数据 / 刷新 / 回收站 ==")
before = len(lv._view)
lv.drop_ids([ids[0]])
check("drop_ids 后 _view 少一条", len(lv._view) == before - 1, (before, len(lv._view)))
check("drop_ids 后表格也少一行", lv.table.rowCount() == before - 1, lv.table.rowCount())

db.update_media_fields(ids[1], title="PROBE-01 改过的标题")
hit = lv.refresh_ids([ids[1]])
_tc = lv._cols.index("title") if "title" in lv._cols else -1
_shown = lv.table.item(0, _tc).text() if _tc >= 0 else ""
check("refresh_ids 真读回新标题", hit == 1 and "改过的标题" in _shown, (_shown, hit))

# 回收站：造个临时文件，走真 SHFileOperationW
victim = os.path.join(TMP, "to_recycle.txt")
open(victim, "w", encoding="utf-8").write("probe")
ok, failed = mw.MainWindow._recycle_paths(None, [victim])
check("回收站删除：文件真的没了", ok == [victim] and not os.path.exists(victim),
      (ok, failed))
ok2, failed2 = mw.MainWindow._recycle_paths(None, [os.path.join(TMP, "nope.mp4")])
check("文件本就不存在 → 视为可清索引", ok2 and not failed2, (ok2, failed2))

print("FAILS:", FAILS, flush=True)
print("PROBE_V14611_DONE", flush=True)
