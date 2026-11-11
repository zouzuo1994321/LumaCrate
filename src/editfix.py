# -*- coding: utf-8 -*-
"""输入框的两件收尾（v2.0.14）
=================================

## 需求 1：右键菜单圆角外那一圈「黑色的小角」

v2.0.13 把 `QLineEdit` / `QTextEdit` 的标准右键菜单文本换成了中文，但那份菜单
是 **Qt 自己 `new` 的**，既没走 `uiwin.menu()`，也没加 `NoDropShadowWindowHint`
—— 于是圆角弧外还留着一圈比背景暗的直角，用户看图说「圆角外有黑色的小角」。

两层根因（真机 + 探针两轮实测）：

1. **窗口级投影**：类名是 `Qt6112QWindowPopupDropShadowSaveBits`，加
   `NoDropShadowWindowHint` 后变成 `QWindowPopupSaveBits`；
2. **Qt 还会把阴影画进菜单表面**：同一个菜单 `uiwin.bare()` 之后四角仍是
   `#0f0f11`。只加旗标**去不掉**这层，必须**不用标准菜单**。

所以这里在应用级拦 `QEvent.ContextMenu`：拿到
`createStandardContextMenu()` 的 actions（文本已由 qtlang 中文化、启用态也由
Qt 按当前选区算好），搬进 `uiwin.menu()` 再弹。**不重造 action** —— 重造就
丢了「撤消/重做是否可用」这类内部状态。

⚠ action 的父对象原本是那份临时菜单，必须 `setParent(我们的菜单)` 转交所有权，
否则临时菜单一析构就把 action 一起带走（弹出瞬间是好的、点下去没反应）。

## 需求 2：有内容时右侧出现小 ×

`setClearButtonEnabled(True)` 就够，但内建图标是
`style()->standardIcon(SP_LineEditClearButton)` 的**深色叉**，压在 `#18181b`
上几乎看不见（实测亮像素只有 16）。图标由 `style.qss` 的 `qproperty-icon`
换成 `glyphs.py` 画的圆头叉（换成 `image:` 无效，实测三张图逐字节相同）。

⚠ 那颗按钮是 `QLineEdit` 内部的**无名 `QToolButton`**（Qt 6.11 起连
`qt_clear_button` 这个 objectName 都没有了），只能靠 `QLineEdit QToolButton`
这种后代选择器命中，找不到它就别想用代码换图标。

⚠ **QSpinBox / QComboBox 内部也各有一个 `QLineEdit`**，给它们装清空按钮会
变成「数字框里塞了个叉」，所以按父控件排除。
"""
import os

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (QAbstractSpinBox, QComboBox, QLineEdit,
                               QPlainTextEdit, QTextEdit, QToolButton)

import applog
import uiwin

#: 会被接管右键菜单的输入类控件（QPlainTextEdit 的日志视图也走这套）
_MENU_TYPES = (QLineEdit, QPlainTextEdit, QTextEdit)

#: 装过清空按钮的标记（Python 侧属性，QWidget 允许挂）
_ARMED = "_lmc_clear_armed"

#: 诊断开关：`LMC_DEBUG_EDITFIX=1` 时把清空按钮的每次显隐判断写进 app.log
_DEBUG = os.environ.get("LMC_DEBUG_EDITFIX", "") == "1"

#: 进程级单例。**必须被持有引用**：QObject 被 GC 掉之后过滤器会静默失效。
_inst = None


def _has_clear_button(w) -> bool:
    """该不该给这个 QLineEdit 装清空按钮。"""
    if not isinstance(w, QLineEdit):
        return False
    if getattr(w, _ARMED, False):
        return False
    # 数字框 / 时间框 / 下拉框内部自带的那个 QLineEdit 不要（会变成「框里塞个叉」）
    p = w.parentWidget()
    if isinstance(p, (QAbstractSpinBox, QComboBox)):
        return False
    return True


def _sync_clear_btn(w, btn) -> None:
    """按当前（**已提交**的）文本自己定清空按钮的显隐。

    判据与 Qt 自己那条一致：有字 + 不是只读。**故意不看 echoMode** —— 密码框
    恰恰最需要这颗叉（Qt 也是这么做的），多一条 `echoMode == Normal` 反而会在
    将来加密码框时把 Qt 想显示的按钮藏起来。

    为什么要自己管：显隐本来由 Qt 内部负责，但真机验收时出现过「框里明明有字、
    叉却不在」。**后来查明那次是输入法的组字串（preedit，带点线下划线）而不是
    已提交文本** —— `text()` 确实是空的、`textChanged` 也确实不该响，行为本来就对。
    即便如此仍保留这条自管：它让显隐只需认「text() 有没有字」这一个事实，
    不依赖 Qt 在 IME 提交 / 拖放 / 程序 setText 各条通道上的刷新时机。
    """
    try:
        want = bool(w.text()) and not w.isReadOnly()
        btn.setVisible(want)
        w.update()
        if _DEBUG:
            applog.log("清空按钮同步：text=%r（%d 字）→ visible=%s"
                       % (w.text(), len(w.text()), want))
    except RuntimeError:            # C++ 侧已析构
        pass


def _arm(w) -> None:
    """开清空按钮，并把它的显隐交给 `textChanged` 自己管。"""
    try:
        w.setClearButtonEnabled(True)
        btns = w.findChildren(QToolButton)
        btn = btns[0] if btns else None
        if btn is not None:
            w._lmc_clear_btn = btn          # 持有引用，避免每次都 findChildren
            w.textChanged.connect(lambda *_a, _w=w, _b=btn: _sync_clear_btn(_w, _b))
            _sync_clear_btn(w, btn)
        setattr(w, _ARMED, True)
    except Exception as e:                      # 单点失败不该拖垮整窗
        applog.log("输入框清空按钮安装失败：%s" % e, "warning")


def _install_clear_button(w) -> None:
    if _has_clear_button(w):
        _arm(w)


def popup_edit_menu(widget, pos) -> bool:
    """把「标准菜单的内容」放进「圆角外真透明的菜单壳」里弹出。

    `pos` 是全局坐标。成功接管返回 True（调用方因此吞掉这次 ContextMenu 事件）。
    """
    try:
        src = widget.createStandardContextMenu()
    except Exception as e:
        applog.log("生成标准编辑菜单失败：%s" % e, "warning")
        return False
    if src is None:
        return False

    try:
        menu = uiwin.menu(widget)
        menu.setAttribute(Qt.WA_DeleteOnClose, True)
        acts = src.actions()
        for act in acts:
            act.setParent(menu)     # ★ 所有权转交：临时菜单析构时不会带走它们
            menu.addAction(act)
        src.deleteLater()
        if not acts:
            menu.deleteLater()
            return False
        menu.popup(pos)
        return True
    except Exception as e:
        applog.log("输入框右键菜单接管失败：%s" % e, "warning")
        return False


class _EditFix(QObject):
    """应用级过滤器：一处安装，全工程所有输入框都吃到。"""

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.ContextMenu and isinstance(obj, _MENU_TYPES):
            if popup_edit_menu(obj, ev.globalPos()):
                return True
            return False
        if t == QEvent.Show and isinstance(obj, QLineEdit):
            _install_clear_button(obj)
        return False


def install(app) -> object:
    """幂等安装。`load_style()` 里调一次就够（所有入口都会经过它）。"""
    global _inst
    if _inst is not None:
        return _inst
    if app is None:
        return None
    _inst = _EditFix(app)
    app.installEventFilter(_inst)
    # 安装之前就已经建好的输入框不会再收到 Show，这里补一遍
    try:
        for w in app.allWidgets():
            _install_clear_button(w)
    except Exception as e:
        applog.log("清空按钮补齐失败：%s" % e, "warning")
    applog.log("输入框收尾：右键菜单改走圆角壳、清空按钮已开启")
    return _inst
