# -*- coding: utf-8 -*-
"""v2.0.14 诊断六：`setText` 会显示清空按钮，**打字**会不会？

诊断五证明 `setText()` 之后按钮立刻可见（真窗口 `self.search` 也一样）。
真机上打字却要按回车才出现 → 怀疑 Qt 的清空按钮显隐只在 `setText` 一类路径里刷新，
**键盘输入这条路不刷新**。这里在进程内直接投 `QKeyEvent` 复现。
"""
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import Qt, QEvent                    # noqa: E402
from PySide6.QtGui import QKeyEvent                      # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit, QToolButton   # noqa: E402

app = QApplication(sys.argv)


def pump(n=8):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.02)


le = QLineEdit()
le.resize(300, 32)
le.setClearButtonEnabled(True)
le.show()
pump()
btn = le.findChildren(QToolButton)[0]
print("空:      visible=%s hidden=%s" % (btn.isVisible(), btn.isHidden()))

# 1) 键盘输入（真实路径：QKeyEvent → QWidgetLineControl::insert）
le.setFocus()
pump()
for ch in "abc":
    ev = QKeyEvent(QEvent.KeyPress, ord(ch.upper()), Qt.NoModifier, ch)
    app.sendEvent(le, ev)
    pump(2)
print("打字后:  text=%r visible=%s hidden=%s" % (le.text(), btn.isVisible(), btn.isHidden()))

# 2) 再 setText 一次同样的内容
le.setText(le.text())
pump()
print("setText: text=%r visible=%s hidden=%s  ← 同内容 setText 是否刷新" 
      % (le.text(), btn.isVisible(), btn.isHidden()))

# 3) 直接改文本（模拟粘贴）
le.clear()
pump()
print("clear:   text=%r visible=%s" % (le.text(), btn.isVisible()))
ev = QKeyEvent(QEvent.KeyPress, Qt.Key_V, Qt.ControlModifier, "\x16")
app.sendEvent(le, ev)
pump()
print("Ctrl+V:  text=%r visible=%s" % (le.text(), btn.isVisible()))

# 4) 手动 insert（粘贴等价）
le.insert("xy")
pump()
print("insert:  text=%r visible=%s" % (le.text(), btn.isVisible()))

print("\nDONE")
