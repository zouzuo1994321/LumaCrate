# -*- coding: utf-8 -*-
"""v1.46.1：切页时收起残留 tooltip + 虚拟化渲染加失效保护。"""
import io, ast

P = r"E:/【01】自研软件/【26-19】本地影视中心/src/main_window.py"
s = io.open(P, encoding="utf-8").read()

# 1) go() / _replace_current() 切页时收起 tooltip（用户口中的「弹窗」多为悬停提示残留）
s = s.replace('''    def go(self, builder, push=True):
        widget = builder()''',
'''    def go(self, builder, push=True):
        # v1.46.1：切页时收起残留的悬停提示（tooltip 是独立顶层窗口，
        # 页面被替换后它不会自己消失，看起来就像"切页弹了个窗"）
        try:
            from PySide6.QtWidgets import QToolTip
            QToolTip.hideText()
        except Exception:
            pass
        widget = builder()''')

# 2) 渲染入口加失效保护（滚动条/视口可能随旧页一起销毁）
s = s.replace('''        if not self._virtual or not _qt_alive(self, self._body):
            return
        cols = max(1, int(self._cols))''',
'''        if not self._virtual or not _qt_alive(self, self._body):
            return
        sb, vp = self._scrollbar, self._viewport
        if sb is not None and not _qt_alive(self, sb):
            return
        if vp is not None and not _qt_alive(self, vp):
            return
        cols = max(1, int(self._cols))''')
s = s.replace('''        total_rows = max(1, (self._total + cols - 1) // cols)
        sb, vp = self._scrollbar, self._viewport
        vh''', '''        total_rows = max(1, (self._total + cols - 1) // cols)
        vh''')

# 3) 容器尺寸/定位都包一层 RuntimeError 兜底
s = s.replace('''        self._body.setFixedSize(width, total_rows * rh)''',
'''        try:
            self._body.setFixedSize(width, total_rows * rh)
        except RuntimeError:
            return''')

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
ast.parse(s)
print("patched | QToolTip:", "QToolTip.hideText" in s, "| guards:", s.count("_qt_alive(self, vp)"))
