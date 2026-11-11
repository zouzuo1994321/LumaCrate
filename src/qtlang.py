# -*- coding: utf-8 -*-
"""Qt **内建控件**的标准文本翻译（v2.0.13）。
==============================================

用户原话：「修复输入框右键为英文的问题」（截图：Undo / Redo / Cut / Copy / Paste /
Delete / Select All）。

根因
----
输入框右键弹出的是 `QLineEdit` 的**标准上下文菜单**，它的文字不是我们写的中文，
而是 Qt 自己 `QCoreApplication::translate("QLineEdit", "&Undo")` 出来的 ——
**只有装了 QTranslator 才有中文**，否则回退英文源串。本软件从来没有装过
（`i18n.py` 那套「词典 + 回退」只管我们自己的文案，管不到 Qt 内建控件）。

同一条链路一起变中文的还有：`QTextEdit` / `QPlainTextEdit` 右键、`QMessageBox`
的标准按钮（是/否/确定/取消）、`QFileDialog`（打开/保存/取消）、`QComboBox`、
字体与颜色对话框里的标准项 —— 都属于「用户会直接读到的系统文案」。

为什么不是 `apply/translate/py` 里加词条
----------------------------------------
那些是**我们的**字符串，Qt 内建控件的字符串在 Qt 的 .qm 里。两份表分开放，
职责不重叠：`i18n.py` 管业务文案，本模块管 Qt 自带控件。

能覆盖多少语言
--------------
PySide6 只随包发了部分语种的 `qtbase_*.qm`（实测 19 种界面语言里 15 种有：
zh_CN / en / ja / ko / es / ar / pt_BR / ru / de / fr / it / tr / nl / pl / sv；
**hi / th / vi / id 没有**）。拿不到就**静默回退英文**，不报错、不影响界面。
`en` 是 Qt 的源语言，压根不用装。

打包注意（onefile）
-------------------
PyInstaller **不会**自动收 `PySide6/translations/*.qm`，必须 `build_exe.py` 用
`--add-data` 显式带进去（落在 `_MEIPASS/PySide6/translations`）。
所以 `translations_dirs()` 同时找**四种**位置：`QLibraryInfo` 报的路径、
PySide6 包目录、`_MEIPASS` 下两个可能位置、exe 同级的 `translations/` ——
任一处命中即可，全都找不到也只会退回英文，不会崩。
"""
import os
import sys

#: 已安装的翻译器。**必须持有引用** —— QTranslator 被 GC 掉，翻译会静默失效。
_installed = []

#: 我们 `i18n.py` 的语言码 → Qt 的 locale 名（只有对不上的才需要写）
_ALIAS = {
    "pt": "pt_BR",       # PySide6 只有 qtbase_pt_BR.qm，没有 pt / pt_PT
    "zh": "zh_CN",
    "zh_TW": "zh_TW",
}


def translations_dirs():
    """`qtbase_*.qm` 可能在的所有目录（按可信度排序，去重）。"""
    out = []

    def add(p):
        if p and os.path.isdir(p) and p not in out:
            out.append(p)

    try:
        from PySide6.QtCore import QLibraryInfo
        add(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    except Exception:
        pass
    try:
        import PySide6
        add(os.path.join(os.path.dirname(PySide6.__file__), "translations"))
    except Exception:
        pass
    # onefile 解包目录：--add-data 写的是 `;PySide6/translations`，落在 _MEIPASS/PySide6/…
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        add(os.path.join(meipass, "PySide6", "translations"))
        add(os.path.join(meipass, "translations"))
    # 绿色版兜底：exe 旁边放一个 translations/ 也能生效
    try:
        add(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "translations"))
    except Exception:
        pass
    return out


def locale_for(code):
    """语言码 → `QLocale`；`en`（Qt 的源语言）返回 None（不该装翻译）。"""
    c = (code or "").strip()
    if not c or c.split("_")[0] == "en":
        return None
    c = _ALIAS.get(c, c)
    try:
        from PySide6.QtCore import QLocale
        return QLocale(c)
    except Exception:
        return None


def install(app, code):
    """按界面语言重装 Qt 标准文本翻译。返回 `(是否装上, qm 路径)`。

    幂等，可以随时再调（切换界面语言时）。**必须传 `QApplication` 实例**：
    `installTranslator` 是它的方法；翻译器也要挂到它名下，避免被回收。
    """
    global _installed
    if app is None:
        return False, ""
    for t in _installed:
        try:
            app.removeTranslator(t)
        except Exception:
            pass
    _installed = []

    loc = locale_for(code)
    if loc is None:
        return False, ""

    from PySide6.QtCore import QTranslator
    for d in translations_dirs():
        tr = QTranslator(app)
        try:
            ok = tr.load(loc, "qtbase", "_", d)
        except Exception:
            ok = False
        if ok:
            app.installTranslator(tr)
            _installed.append(tr)
            return True, tr.filePath()
    return False, ""


def sample_texts(n=3):
    """取 `QLineEdit` 标准右键菜单的前 n 项，作为「翻译真的生效」的现场证据。

    为什么要在**产品日志**里留这一行：用户以后再反馈「某处还是英文」，看一眼
    `app.log` 就知道是 qm 没打进 exe、还是某个控件压根不走标准菜单 —— 不用猜。
    调用方必须已经建好 `QApplication`；本函数全程吞异常，拿不到就返回空列表。
    """
    out = []
    try:
        from PySide6.QtWidgets import QLineEdit
        le = QLineEdit()
        menu = le.createStandardContextMenu()
        for a in menu.actions():
            if a.isSeparator():
                continue
            # 去掉 `\tCtrl+Z` 与 `&` 加速键标记 —— Qt 把 `撤消(&U)` 渲染成「撤消(U)」，
            # 日志里照渲染后的样子写，人一眼能对上。
            out.append(a.text().split("\t")[0].replace("&", ""))
            if len(out) >= n:
                break
        menu.deleteLater()
        le.deleteLater()
    except Exception:
        return []
    return out
