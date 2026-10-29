# -*- coding: utf-8 -*-
"""v1.46.10 封存：给 archive_version.py 传本版摘要。"""
import runpy
import sys

NOTE = (
    "详情页两条反馈：①「演职人员信息」并入「基本信息」右侧（海报 150 定宽 | 基本信息 230 定宽 | "
    "演职人员 stretch=1，三栏同排顶对齐，文件信息仍在底部；右键替换演员就地重建仍插回同一栏位；"
    "700px 窄栏无横向滚动条）。② 右键「替换「XX」」搜索框不能用中文输入法——根因是弹层用了 Qt.Popup，"
    "Windows 上 Popup 不被激活，输入法拿不到前台输入上下文；改为 Qt.Dialog + FramelessWindowHint 并补 "
    "WA_InputMethodEnabled / ImhNone / activateWindow + 输入框取焦；Popup 白送的「点外面关闭」用 "
    "ClickOutsideCloser（QApplication 事件过滤器 + geometry 命中）自己补回，done() 摘除。"
    "冒烟 276/276、单测 28/28；真机 A/B 实测：Popup 前台仍是主窗（不进输入法），新弹层前台 = 自身 HWND；"
    "真机 PrintWindow 三栏布局截图通过。"
)

sys.argv = ["archive_version.py", "--note", NOTE]
runpy.run_path(r"E:/【01】自研软件/【26-19】本地影视中心/dev/_scratch/archive_version.py",
               run_name="__main__")
