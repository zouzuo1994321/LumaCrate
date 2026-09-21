# -*- coding: utf-8 -*-
"""v1.10.0 离线冒烟测试：
- 修复0 单实例启动不再自尽（_kill_other_instances 排除父进程 ppid）
- 需求1 演员库卡片平铺 + 额外字段（状态/出生/出身地/身高/三围/胸围）
- 需求2 五角星收藏 + ▲置顶 + 排序(置顶>收藏>其余)
- 需求3 现役绿 / 退役黄 / 选中粉色流光高亮（自绘 paintEvent 不崩）
- 需求4 影片卡重构：图片与标题不重叠 + 小字演员/导演 + 单击选中双击进入
"""
import os
import sys
import json
import tempfile
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import scanner as scanner_mod
import config as cfg
import nfo_parser as nfo_mod
import version as ver

errors = []


def check(name, cond, extra=""):
    print(("OK  " if cond else "FAIL") + " - " + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        errors.append(name)


tmp = tempfile.mkdtemp(prefix="lmc_smoke10_")
db.db_path = lambda: os.path.join(tmp, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(tmp, "settings.json")
cfg._SETTINGS = None

try:
    from PySide6.QtWidgets import QApplication
    from main_window import (_parse_size, _parse_meta, ActorCard, PosterCard,
                             MainWindow)
    import main as app_main
    check("import 全部模块", True)

    app = QApplication.instance() or QApplication([])
    check("版本号为 v1.10.0", ver.VERSION == "v1.10.0", ver.FULL_VERSION)

    # ------------------------------------------------------------ 修复0 单实例
    src = open(os.path.join(_HERE, "..", "src", "main.py"), encoding="utf-8").read()
    check("单实例排除父进程 ppid（不再自尽）",
          "os.getppid()" in src and "my_ppid" in src)

    # ------------------------------------------------------------ 需求4 导演抓取 + 影片卡
    NFO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <movie><title>DIRTEST 导演用例</title><year>2023</year>
    <actor><name>演员甲</name></actor>
    <actor><name>演员乙</name></actor>
    <director>导演一</director>
    <director>导演二</director>
    </movie>"""
    d = os.path.join(tmp, "DIRTEST")
    os.makedirs(d)
    with open(os.path.join(d, "DIRTEST.nfo"), "w", encoding="utf-8") as f:
        f.write(NFO)
    video = os.path.join(d, "DIRTEST.mp4")
    with open(video, "wb") as f:
        f.write(b"\x00" * 2048)
    db.init_db()
    counts = scanner_mod.scan_library(tmp, None, library_name="测试库", mode="overwrite")
    check("测试媒体已入库", counts["movie"] >= 1)
    mid = db.media_id_by_path(video)
    crew = db.cast_crew_map().get(mid, {})
    check("导演被抓取并关联", "导演一" in crew.get("directors", "") and "导演二" in crew.get("directors", ""), crew)
    check("演员被抓取并关联", "演员甲" in crew.get("actors", "") and "演员乙" in crew.get("actors", ""), crew)

    media = db.get_media(mid)
    card = PosterCard(media, lambda m: None, crew.get("actors", ""), crew.get("directors", ""))
    card.show()
    app.processEvents()
    check("影片卡渲染不崩(offscreen)", True)
    check("影片卡小字显示导演", "导演：" in card._facts.text(), card._facts.text())
    check("影片卡小字显示演员", "演员：" in card._facts.text())
    card.set_selected(True)
    app.processEvents()
    check("影片卡选中态(粉色流光)不崩", card._selected is True)
    card.close()

    # ------------------------------------------------------------ 需求2/3 演员卡 + 排序 + 配色
    pids = [db.upsert_person(nm, "Actor", None) for nm in ("绿现役", "黄退役", "灰未知")]
    db.update_person(pids[0], only_missing=False, birthday="1999-01-01", status="现役",
                     meta=json.dumps({"出身地": "东京", "身高": "163cm", "尺寸": "T163/B85/W58/H83"}))
    db.update_person(pids[1], only_missing=False, birthday="1990-05-05", status="退役",
                     meta=json.dumps({"出身地": "大阪", "身高": "158cm", "尺寸": "T158/B80/W55/H80"}))
    db.toggle_person_favorite(pids[2])
    db.toggle_person_pinned(pids[1])
    ordered = db.all_people_ordered("Actor")
    idx = {p["id"]: i for i, p in enumerate(ordered)}
    check("排序：置顶在第一", ordered[0]["id"] == pids[1], [p["name"] for p in ordered])
    check("排序：收藏在其次", ordered[1]["id"] == pids[2])
    check("排序：置顶>收藏>其余(三者相对序正确)",
          idx[pids[1]] < idx[pids[2]] < idx[pids[0]], idx)

    ac0 = ActorCard(db.get_person(pids[0]), on_open=lambda p: None, on_fav=lambda p: None,
                    on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
    ac0.show(); app.processEvents()
    check("演员卡(现役)渲染不崩", True)
    check("演员卡显示 出生/出身地/身高/三围/胸围",
          all(k in ac0._facts.text() for k in ("出生", "出身地", "身高", "三围", "胸围")),
          ac0._facts.text())
    ac1 = ActorCard(db.get_person(pids[1]), on_open=lambda p: None, on_fav=lambda p: None,
                    on_pin=lambda p: None, on_select=lambda c: None, main_win=None)
    ac1.show(); app.processEvents()
    check("演员卡(退役)渲染不崩", True)
    ac1.set_selected(True); app.processEvents()
    check("演员卡选中(粉色流光)不崩", ac1._selected is True)
    ac0.close(); ac1.close()

    # ------------------------------------------------------------ 主窗口可用
    w = MainWindow()
    check("主窗口构造成功", w is not None)
    actors_page = w._view_actors()
    check("演员库页面可构造(卡片网格)", actors_page is not None)
    w._select_card(None)
    w.close()
    check("closeEvent 执行无异常", True)

except Exception as e:
    check("运行期异常: " + repr(e), False)
    import traceback
    traceback.print_exc()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n结果:", "全部通过" if not errors else ("失败: " + ", ".join(errors)))
sys.exit(1 if errors else 0)
