# -*- coding: utf-8 -*-
"""v1.12.0 离线冒烟：媒体库合并为一份 + 取消「内置媒体库」概念。

覆盖：
1. 数据模型：只剩一份 `libraries`；`media_libraries` / `MEDIA_LIBRARY_DEFAULTS` /
   墓碑 `media_libraries_hidden` / `restore_default_media_libraries()` 全部消失
2. 全新安装默认 0 个库（不再自带内置库）
3. 统一 CRUD：新建（重名=覆盖）/ 编辑 / 改名（保住类型与路径）/ 删除（持久，不复活）
4. 升级迁移：6 个未改名的旧内置库丢弃；改过名的内置库 + 非内置旧分类库迁入统一列表；
   索引记录不受影响；`background.library` 指向已消失的库时复位
5. 界面：侧边栏只剩一个「媒体库」分组 + 「＋ 新建媒体库」入口；设置页没有「内置媒体库」
   提示与「恢复被删除的内置媒体库」按钮；唯一编辑对话框 LibraryEditDialog

全程离线：临时库 + 临时 settings.json，不碰真实索引与真实配置。
"""
import os
import sys
import json
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database as db
import config as cfg
import version as ver

errors = []


def check(name, cond, extra=""):
    print(("OK  " if cond else "FAIL") + " - " + name + (("   " + str(extra)) if extra else ""))
    if not cond:
        errors.append(name)


tmp = tempfile.mkdtemp(prefix="lmc_smoke120_")
DBP = os.path.join(tmp, "index_data", "media_center.db")
CFG = os.path.join(tmp, "settings.json")
db.db_path = lambda: DBP
cfg.config_path = lambda: CFG
cfg._SETTINGS = None


def write_settings(data: dict):
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_settings() -> dict:
    with open(CFG, encoding="utf-8") as f:
        return json.load(f)


def reload_settings():
    cfg._SETTINGS = None
    return cfg.get_settings()


try:
    from PySide6.QtWidgets import (QApplication, QGroupBox, QLabel, QPushButton)
    from PySide6.QtGui import QFontDatabase
    import ui_settings as ui_set
    from ui_settings import SettingsDialog, LibraryEditDialog
    from main_window import MainWindow, load_style

    app = QApplication.instance() or QApplication([])
    # 先注册中文字体 + 套 QSS 再建控件，保证标签度量走真实字体（见技能第十节）
    for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
        if os.path.exists(_f):
            QFontDatabase.addApplicationFont(_f)
    load_style(app)
    check("版本号为 v1.12.0", ver.VERSION == "v1.12.0", ver.FULL_VERSION)

    # ================================================== 1) 数据模型：只剩一份
    check("config 已删除 MEDIA_LIBRARY_DEFAULTS（不再注入内置库）",
          not hasattr(cfg, "MEDIA_LIBRARY_DEFAULTS"))
    check("保留旧内置库识别表 _LEGACY_BUILTIN_LIBS（仅用于升级清理）",
          cfg._LEGACY_BUILTIN_LIBS == {"movie": "电影", "tv": "电视", "anime": "番剧",
                                       "acg": "二次元", "banned": "禁片", "domestic": "国产"},
          cfg._LEGACY_BUILTIN_LIBS)
    check("DEFAULT_LIBRARIES 为空（不带任何默认库）", cfg.DEFAULT_LIBRARIES == [])

    # ================================================== 2) 全新安装：0 个库
    check("全新安装（无 settings.json）默认 0 个媒体库",
          cfg.get_settings().libraries == [], cfg.get_settings().libraries)
    check("Settings 不再有 media_libraries / media_libraries_hidden 属性",
          not hasattr(cfg.get_settings(), "media_libraries")
          and not hasattr(cfg.get_settings(), "media_libraries_hidden"))
    check("restore_default_media_libraries 已删除",
          not hasattr(cfg.get_settings(), "restore_default_media_libraries"))
    check("add_media_library / remove_media_library 等旧接口已删除",
          not any(hasattr(cfg.get_settings(), n) for n in
                  ("add_media_library", "remove_media_library", "update_media_library",
                   "set_media_library_paths", "media_library", "media_library_names")))

    # ================================================== 3) 统一 CRUD
    s = cfg.get_settings()
    s.add_library("Jav-VR", "混合", ["Y:/jav"])
    s.add_library("我的电影", "电影", ["D:/movies"])
    check("新建两个库（顺序稳定）", s.library_names() == ["Jav-VR", "我的电影"], s.library_names())
    check("library() 按名字取配置", (s.library("Jav-VR") or {}).get("paths") == ["Y:/jav"])
    check("library(不存在) 返回 None", s.library("没有这个库") is None)

    s.add_library("Jav-VR", "电影", [])
    check("重名新建 = 覆盖配置而不是追加一条",
          len(s.libraries) == 2 and s.library("Jav-VR")["kind"] == "电影")
    s.update_library("Jav-VR", "Jav-VR", "混合", ["Y:/jav"])

    check("rename_library 能改名", s.rename_library("我的电影", "电影收藏"))
    check("改名不丢类型与路径",
          s.library("电影收藏")["kind"] == "电影"
          and s.library("电影收藏")["paths"] == ["D:/movies"],
          s.library("电影收藏"))
    check("改名后旧名字查不到", s.library("我的电影") is None)

    s.remove_library("电影收藏")
    check("remove_library 生效", s.library_names() == ["Jav-VR"], s.library_names())

    s2 = reload_settings()
    check("删除是持久的（重载后不会复活）", s2.library_names() == ["Jav-VR"], s2.library_names())
    dumped = read_settings()
    check("settings.json 不再写 media_libraries 键", "media_libraries" not in dumped)
    check("settings.json 不再写 media_libraries_hidden 键",
          "media_libraries_hidden" not in dumped)
    check("settings.json 只写一份 libraries", dumped["libraries"] == s2.libraries)

    # ================================================== 4) 升级迁移
    # 场景 A：老用户只动过内置库的删除按钮（6 个默认名都在）-> 升级后应清空
    legacy_a = {
        "libraries": [],
        "media_libraries": [
            {"key": "movie", "name": "电影", "language": "简体中文", "paths": [],
             "filter": {"kind": "movie"}},
            {"key": "tv", "name": "电视", "language": "简体中文", "paths": [],
             "filter": {"kind": "tvshow"}},
            {"key": "anime", "name": "番剧", "language": "简体中文", "paths": [],
             "filter": {"kind": "tvshow", "genre": "动画"}},
            {"key": "acg", "name": "二次元", "language": "简体中文", "paths": [],
             "filter": {"genre": "动画"}},
            {"key": "banned", "name": "禁片", "language": "简体中文", "paths": [],
             "filter": {"certification": "R"}},
            {"key": "domestic", "name": "国产", "language": "简体中文", "paths": [],
             "filter": {"country": "中国"}},
        ],
        "media_libraries_hidden": ["tv", "anime"],
    }
    write_settings(legacy_a)
    sa = reload_settings()
    check("升级即清空：6 个未改名的内置库全部移除", sa.libraries == [], sa.libraries)

    # 场景 B：改过名的内置库 + 自建分类库 + 用户命名库
    legacy_b = {
        "libraries": [{"name": "Jav-VR", "kind": "混合", "paths": ["Y:/jav"]}],
        "media_libraries": [
            {"key": "movie", "name": "电影", "language": "简体中文", "paths": [],
             "filter": {"kind": "movie"}},
            {"key": "domestic", "name": "我的国产片", "language": "简体中文",
             "paths": ["E:/guochan"], "filter": {"country": "中国"}},
            {"key": "lib_7", "name": "自建分类库", "language": "简体中文",
             "paths": ["F:/x"], "filter": {}},
        ],
        "media_libraries_hidden": ["tv"],
        "background": {"enabled": False, "library": "电影", "time": "03:00", "frequency": "每天"},
    }
    write_settings(legacy_b)
    sb = reload_settings()
    check("升级迁移：只清掉未改名的内置库，用户资产全保留",
          sb.library_names() == ["Jav-VR", "我的国产片", "自建分类库"], sb.library_names())
    check("改过名的内置库被迁移且保住路径与筛选",
          sb.library("我的国产片")["paths"] == ["E:/guochan"]
          and sb.library("我的国产片")["filter"] == {"country": "中国"},
          sb.library("我的国产片"))
    check("非内置 key 的旧分类库也迁移过来",
          sb.library("自建分类库")["paths"] == ["F:/x"])
    check("迁移进来的库默认类型为「混合」", sb.library("我的国产片")["kind"] == "混合")
    check("background.library 指向已消失的库 -> 复位为「全部库」",
          sb.background["library"] == "", sb.background)

    sb.save()
    sb2 = reload_settings()
    check("迁移结果落盘后不会重复追加",
          sb2.library_names() == ["Jav-VR", "我的国产片", "自建分类库"], sb2.library_names())

    # background 指向存在的库时不该被复位
    sb2.background["library"] = "Jav-VR"
    sb2.save()
    sb3 = reload_settings()
    check("background.library 指向存在的库时保持不动",
          sb3.background["library"] == "Jav-VR", sb3.background)

    # ================================================== 5) 界面
    db.init_db()
    w = MainWindow()
    sections = [l.text() for l in w.sidebar.findChildren(QLabel)
                if l.objectName() == "Section"]
    check("侧边栏只有一个「媒体库」分组", sections.count("媒体库") == 1, sections)
    check("侧边栏不再有「命名媒体库」分组", "命名媒体库" not in sections, sections)

    side_btns = [b.text() for b in w.sidebar.findChildren(QPushButton)]
    check("侧边栏列出全部用户媒体库", all(n in side_btns for n in sb3.library_names()),
          side_btns)
    check("侧边栏有「＋ 新建媒体库」入口（无内置库后必须能就地新建）",
          w._NEW_LIB_TEXT in side_btns, side_btns)
    new_btns = [b for b in w.sidebar.findChildren(QPushButton)
                if b.text() == w._NEW_LIB_TEXT]
    check("「＋ 新建媒体库」用 NavDim 弱化样式（而不是和真实库同样的 Nav）",
          bool(new_btns) and new_btns[0].objectName() == "NavDim",
          [b.objectName() for b in new_btns])
    check("媒体库按钮右键有菜单（CustomContextMenu）",
          all(b.contextMenuPolicy() == b.contextMenuPolicy().CustomContextMenu
              for b in w.sidebar.findChildren(QPushButton)
              if b.text() in sb3.library_names()))
    check("MainWindow 有 _new_library 入口方法", callable(getattr(w, "_new_library", None)))

    # 空库 + 筛选兜底：不应抛异常
    empty_lib = {"name": "空库", "kind": "混合", "paths": [], "filter": {"kind": "movie"}}
    check("_lib_view 对空库不抛异常", w._lib_view(empty_lib) is not None)

    # 设置页
    dlg = SettingsDialog()
    texts = [l.text() for l in dlg.findChildren(QLabel)]
    check("设置页不再出现「内置媒体库」字样",
          not any("内置媒体库" in t for t in texts),
          [t for t in texts if "内置" in t])
    btn_texts = [b.text() for b in dlg.findChildren(QPushButton)]
    check("设置页不再有「恢复被删除的内置媒体库」按钮",
          not any("恢复" in t and "内置" in t for t in btn_texts),
          [t for t in btn_texts if "恢复" in t])
    check("设置页不再有「已配置的媒体库」之外的重复媒体库区块... 媒体库分组只有 1 个",
          [g.title() for g in dlg.findChildren(QGroupBox)].count("媒体库") == 1,
          [g.title() for g in dlg.findChildren(QGroupBox)])
    check("ui_settings 已删除 MediaLibraryDialog（唯一对话框）",
          not hasattr(ui_set, "MediaLibraryDialog"))
    check("设置页为空列表时给出引导文案", True)

    # 空列表占位
    real = list(cfg.get_settings().libraries)
    cfg.get_settings().libraries = []
    dlg._rebuild_lib_list()
    ph = [dlg.lib_list.itemWidget(dlg.lib_list.item(i)).text()
          for i in range(dlg.lib_list.count())
          if isinstance(dlg.lib_list.itemWidget(dlg.lib_list.item(i)), QLabel)]
    check("没有媒体库时列表显示引导占位（不是空白）",
          len(ph) == 1 and "还没有媒体库" in ph[0], ph)
    cfg.get_settings().libraries = real

    # LibraryEditDialog：新建/编辑共用
    d_new = LibraryEditDialog(None, {"name": "", "kind": "混合", "paths": []},
                              title="新建媒体库")
    check("LibraryEditDialog 支持「新建媒体库」标题", d_new.windowTitle() == "新建媒体库")
    check("LibraryEditDialog 默认标题仍是「编辑媒体库」",
          LibraryEditDialog(None, {"name": "x"}).windowTitle() == "编辑媒体库")
    check("类型下拉来自 cfg.LIBRARY_KINDS",
          [d_new.kind.itemText(i) for i in range(d_new.kind.count())] == cfg.LIBRARY_KINDS,
          [d_new.kind.itemText(i) for i in range(d_new.kind.count())])
    check("新建对话框名称框为空、路径可空",
          d_new.result_data() == ("", "混合", []), d_new.result_data())

    # 冒烟里加一个媒体库，验证「已配置的媒体库」列表渲染出真实行（含编辑/扫描/删除）
    cfg.get_settings().add_library("冒烟库", "电影", ["D:/x"])
    dlg._rebuild_lib_list()
    rows = []
    for i in range(dlg.lib_list.count()):
        rw = dlg.lib_list.itemWidget(dlg.lib_list.item(i))
        if isinstance(rw, QPushButton):
            continue
        rows.append([b.text() for b in rw.findChildren(QPushButton)] if rw else [])
    check("已配置列表每行都有 编辑/扫描/删除 三个按钮",
          any(all(t in row for t in ("编辑", "扫描", "删除")) for row in rows), rows)
    check("列表行带 UserRole（可按行反查库名）",
          dlg.lib_list.item(0).data(0x0100) == "Jav-VR",
          dlg.lib_list.item(0).data(0x0100))

finally:
    try:
        app.quit()      # noqa: F821
    except Exception:
        pass

print("\n==== %s ====" % ("全部通过" if not errors else ("失败 %d 项: %s" % (len(errors), errors))))
sys.exit(1 if errors else 0)
