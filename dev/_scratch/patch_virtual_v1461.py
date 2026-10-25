# -*- coding: utf-8 -*-
"""把 LazyGrid 的虚拟化渲染改成「绝对定位 + 增量换卡」，消除滚动闪烁。"""
import io, ast

P = r"E:/【01】自研软件/【26-19】本地影视中心/src/main_window.py"
s = io.open(P, encoding="utf-8").read()

start = s.find("    def _render(self):")
end = s.find("    def eventFilter(self, obj, ev):", start)
assert start > 0 and end > start, (start, end)

new = '''    def _render(self):
        """只渲染「可视区 ± overscan 行」——**绝对定位 + 增量换卡**（v1.46.1）。

        为什么不用 QGridLayout / 先清后建：那样每次换窗口都要**删掉全部卡片再重建**，
        真实显示上会闪一下（用户反馈的「滚轴时页面一闪闪 / 消失」）；高频滚动时
        每 tick 清一次，观感更差。

        现在的做法（通用，任何 `virtual=True` 的网格都适用）：
          1. `_body` 高度 = 总行数 × 行高 → 滚动条由它撑开，不再用上下占位；
          2. 每张卡 `setGeometry(...)` 绝对定位，**不走布局**；
          3. 新进入窗口的卡**先建出来**，再删离开窗口的卡 —— 任何一帧都有内容。
        """
        if not self._virtual or not _qt_alive(self, self._body):
            return
        cols = max(1, int(self._cols))
        total_rows = max(1, (self._total + cols - 1) // cols)
        sb, vp = self._scrollbar, self._viewport
        vh = max(120, int(getattr(vp, "height", lambda: 700)()) if vp is not None else 700)
        y = int(sb.value()) if sb is not None else 0
        if self._row_h <= 0:
            rows = self._safe_fetch(0, 1)
            if not rows:
                return
            probe = self._make(rows[0])
            probe.setParent(self._body)
            probe.hide()
            self._row_h = max(1, probe.height() + 12)
            probe.deleteLater()
            self._window = (-1, -1)
        rh = self._row_h
        r0 = max(0, y // rh - self._overscan)
        r1 = min(total_rows - 1, (y + vh) // rh + self._overscan)
        if (r0, r1) == self._window and self._cards:
            return
        self._window = (r0, r1)

        width = max(120, int(self._body_w or self.width()))
        cell_w = max(60, (width - 12 * (cols - 1)) // cols)
        self._body.setFixedSize(width, total_rows * rh)

        want = []
        for row in range(r0, r1 + 1):
            base = row * cols
            if base >= self._total:
                break
            want.append((row, base, min(cols, self._total - base)))

        rows = self._safe_fetch(r0 * cols, (r1 - r0 + 1) * cols)
        made = {}
        i = 0
        for row, base, n in want:
            for c in range(n):
                if i >= len(rows):
                    break
                idx = base + c
                if idx in self._cards:
                    made[idx] = self._cards[idx]
                else:
                    try:
                        w = self._make(rows[i])
                    except Exception as e:
                        applog.log(f"建卡失败 idx={idx}: {e}", "error")
                        i += 1
                        continue
                    w.setParent(self._body)
                    made[idx] = w
                i += 1
        for row, base, n in want:
            for c in range(n):
                idx = base + c
                w = made.get(idx)
                if w is not None:
                    try:
                        w.setGeometry(c * (cell_w + 12), (row - r0) * rh, cell_w, rh - 12)
                        w.show()
                    except RuntimeError:
                        pass
        for idx, w in list(self._cards.items()):
            if idx not in made:
                try:
                    w.hide()
                    w.deleteLater()
                except RuntimeError:
                    pass
        self._cards = made
        self._built = list(made.values())
        self._loaded = min(self._total, (r1 + 1) * cols)
        self._update_head()

'''
s = s[:start] + new + s[end:]

# 字段
s = s.replace('''        self._viewport = None
        self._built = []''',
'''        self._viewport = None
        self._built = []
        self._cards = {}      # 虚拟化：index -> 卡片控件（绝对定位）
        self._body_w = 0''')

# 视口宽度变化 → 重算列宽
s = s.replace('''    def eventFilter(self, obj, ev):
        if self._virtual and ev.type() == QEvent.Resize:
            try:
                self._window = (-1, -1)      # 视口尺寸变了 → 重算窗口（可能换列数）
                if not self._scroll_timer.isActive():
                    self._scroll_timer.start(0)
            except Exception:
                pass
        return super().eventFilter(obj, ev)''',
'''    def eventFilter(self, obj, ev):
        if self._virtual and ev.type() == QEvent.Resize:
            try:
                self._body_w = max(120, obj.width())   # 视口宽度变了 → 重算列宽
                self._window = (-1, -1)
                if not self._scroll_timer.isActive():
                    self._scroll_timer.start(0)
            except Exception:
                pass
        return super().eventFilter(obj, ev)''')

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
ast.parse(s)
print("REWRITTEN ok | _cards:", s.count("self._cards"))
