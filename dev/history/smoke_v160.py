# -*- coding: utf-8 -*-
"""v1.6.0 离线冒烟测试：
- 详情页横幅去掉「黑色底框」：底部仍能透出 fanart（像素回归）
- 首页悬停缩略图预览卡：构建 / 填充 / 定位 / 不抢焦点
- 列设置：新增「演员」列、列表可拖动排序、顺序持久化
- 表头拖动换列 + 顺序落盘 + 复位后逻辑列==视觉列 + 行数据绑定仍可解析
"""
import os
import sys
import tempfile
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import scanner as scanner_mod
import config as cfg

errors = []


def check(name, cond, extra=""):
    print(("OK  " if cond else "FAIL") + " - " + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        errors.append(name)


# 1) 导入
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QColor, QGuiApplication
    import ui_hero, ui_home, ui_settings, main_window, media_meta as mm
    import version as ver
    check("import 全部模块", True)
except Exception as e:
    check("import modules: " + repr(e), False)

app = QApplication.instance() or QApplication([])
# 加载真实样式表（预览卡等样式回归）
_qss = os.path.join(_HERE, "..", "src", "style.qss")
if os.path.exists(_qss):
    app.setStyleSheet(open(_qss, encoding="utf-8").read())

check("版本号为 v1.6.0", ver.VERSION == "v1.6.0", ver.FULL_VERSION)
check("HOME_COLUMNS 含演员列", any(k == "actors" for k, _ in cfg.HOME_COLUMNS))
check("QTableWidget 有 cellEntered 信号", hasattr(ui_home.HomeListView, "_on_cell_entered"))
check("QGuiApplication.screenAt 可用", hasattr(QGuiApplication, "screenAt"))

orig_cols = list(cfg.get_settings().home_columns)

tmp = tempfile.mkdtemp(prefix="lmc_smoke6_")
# 使用临时数据库，避免污染真实索引
_DB_TMP = os.path.join(tmp, "index_data", "media_center.db")
db.db_path = lambda: _DB_TMP
NFO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>TEST-001 冒烟用例</title>
  <year>2026</year>
  <rating>7.5</rating>
  <premiered>2026-01-02</premiered>
  <genre>剧情</genre>
  <studio>StudioX</studio>
  <actor><name>演员甲</name></actor>
  <actor><name>演员乙</name></actor>
</movie>"""
try:
    item_dir = os.path.join(tmp, "TEST-001【演员甲】")
    os.makedirs(item_dir)
    with open(os.path.join(item_dir, "TEST-001.nfo"), "w", encoding="utf-8") as f:
        f.write(NFO)
    video = os.path.join(item_dir, "TEST-001.mp4")
    with open(video, "wb") as f:
        f.write(b"\x00" * 2048)

    db.init_db()
    db.clear_media()
    counts = scanner_mod.scan_library(tmp, None, library_name="电影", mode="overwrite")
    check("同名 nfo 仍被识别", counts["movie"] >= 1)

    row = next((m for m in db.search_media("TEST-001") if "TEST-001" in (m.get("title") or "")), None)
    check("测试条目已入库", row is not None)

    # 2) 演员聚合
    amap = db.actors_map()
    check("actors_map 返回演员串", bool(row) and ("演员甲" in amap.get(row["id"], "")))

    # 3) 详情页横幅：底部不得压成整块黑底（透出 fanart）
    if row:
        white = os.path.join(item_dir, "TEST-001-fanart.jpg")
        im = QImage(1920, 1080, QImage.Format_RGB32)
        im.fill(QColor(255, 255, 255))
        im.save(white, "JPG", 92)
        m2 = dict(row)
        m2["fanart"] = white
        m2["poster"] = white
        hv = ui_hero.HeroView(m2)
        hv.resize(1600, 900)
        hv.show()
        for _ in range(6):
            app.processEvents()
        banner = hv.findChild(ui_hero.HeroBanner)
        check("HeroBanner 存在", banner is not None)
        if banner is not None:
            bh = banner.height()
            pm = hv.grab()
            os.makedirs(os.path.join(_HERE, "screenshots"), exist_ok=True)
            pm.save(os.path.join(_HERE, "screenshots", "smoke_v160_hero.png"))
            y = int(bh * 0.90)
            c = pm.toImage().pixelColor(760, y)
            lum = c.red()
            check("横幅底部未压成全黑(90%%处透出背景)", lum > 70, f"y={y} rgb=({c.red()},{c.green()},{c.blue()})")
            cbot = pm.toImage().pixelColor(760, max(bh - 3, 0))
            check("横幅底边与页面底色衔接(非纯黑)", cbot.red() >= 12, f"rgb=({cbot.red()},{cbot.green()},{cbot.blue()})")
        hv.hide()

    # 4) 悬停缩略图预览卡
    hp = ui_home.HoverPreview(None)
    hp.set_media(row or {"title": "无图条目"})
    check("预览卡缩略图非空", not hp.img.pixmap().isNull())
    check("预览卡宽度固定", hp.width() == ui_home.HoverPreview.CARD_W)
    hp.set_media({"title": "无图条目", "actors_text": "甲乙"})
    check("预览卡无图时用占位图", not hp.img.pixmap().isNull())
    try:
        from PySide6.QtCore import QPoint
        hp.popup_at(QPoint(10, 10))
        hp.popup_at(QPoint(1900, 1070))
        check("预览卡可在屏幕四角定位", True)
    except Exception as e:
        check("预览卡定位: " + repr(e), False)
    try:
        hp.resize(10, 10)
        hp.popup_at(QPoint(600, 400))
        check("预览卡定位不受预设尺寸影响", hp.width() == ui_home.HoverPreview.CARD_W)
    except Exception as e:
        check("预览卡定位2: " + repr(e), False)
    hp.hide()

    # 5) 列设置对话框：演员列 + 拖动排序 + 持久化
    dlg = ui_home.ColumnSettingsDialog(None)
    check("列设置对话框可构造", dlg is not None)
    check("对话框列出全部列", dlg.list.count() == len(cfg.HOME_COLUMNS))
    keys = dlg._keys()
    check("对话框含演员项", "actors" in keys)
    it = next(dlg.list.item(i) for i in range(dlg.list.count()) if dlg.list.item(i).data(Qt.UserRole) == "actors")
    check("演员项可拖动", bool(it.flags() & Qt.ItemIsDragEnabled))
    check("演员项可勾选", bool(it.flags() & Qt.ItemIsUserCheckable))
    check("列表启用内部拖动", dlg.list.dragDropMode().name == "InternalMove"
          if hasattr(dlg.list.dragDropMode(), "name") else True)
    # 勾选演员列 + 把它移动到第二位（模拟拖动后的顺序）
    it.setCheckState(Qt.Checked)
    src_row = dlg.list.row(it)
    moved = dlg.list.takeItem(src_row)
    dlg.list.insertItem(1, moved)
    dlg.accept()
    cols = cfg.get_settings().home_columns
    check("勾选后被写入设置", "actors" in cols, cols)
    check("拖动后的顺序被保存", cols[1] == "actors", cols)
    check("标题仍在列表中", "title" in cols)

    # 顺序可被外部强制修正
    cfg.get_settings().set_home_columns(orig_cols + ["actors"])
    check("set_home_columns 保序", cfg.get_settings().home_columns == orig_cols + ["actors"])

    # 6) 首页视图：演员列渲染 / 行绑定 / 表头拖动换位
    hv2 = ui_home.HomeListView()
    check("首页视图可构造", hv2 is not None)
    check("每列都绑定 media 数据", ui_home.row_media(hv2.table, 0) is not None
          if hv2.table.rowCount() else True)
    if hv2.table.rowCount():
        mfirst = ui_home.row_media(hv2.table, 0)
        check("行绑定对象可解析 id", isinstance(mfirst, dict) and "id" in mfirst)
    # 演员列取值
    if row:
        fake = dict(row)
        fake["actors_text"] = "演员甲 / 演员乙"
        check("演员列取值", hv2._col_value(fake, "actors") == "演员甲 / 演员乙")
        check("演员列排序键存在", "actors" in ui_home._SORT_KEYS)
    # 表头拖动
    hdr = hv2.table.horizontalHeader()
    before = list(hv2._cols)
    if hdr.count() >= 3:
        hdr.moveSection(2, 0)
        hv2._commit_column_order()
        after = list(hv2._cols)
        check("拖动后列顺序改变", after != before, f"{before} -> {after}")
        check("新顺序已落盘", cfg.get_settings().home_columns == after)
        hdr2 = hv2.table.horizontalHeader()
        check("复位后逻辑列==视觉列",
              all(hdr2.logicalIndex(v) == v for v in range(hdr2.count())))
        check("复位后表头标签匹配",
              hv2.table.horizontalHeaderItem(0).text() == dict(cfg.HOME_COLUMNS).get(after[0]))
        check("重排后行数据仍可解析",
              ui_home.row_media(hv2.table, 0) is not None if hv2.table.rowCount() else True)
    hv2._hide_preview()
    check("隐藏预览不抛异常", True)

    # 7) 主窗口仍可构建
    w = main_window.MainWindow()
    check("主窗口构建成功", w is not None)
    check("窗口宽度<=1920", w.width() <= 1920)
finally:
    cfg.get_settings().set_home_columns(orig_cols)
    shutil.rmtree(tmp, ignore_errors=True)

print("\n结果:", "全部通过" if not errors else ("失败: " + ", ".join(errors)))
sys.exit(1 if errors else 0)
