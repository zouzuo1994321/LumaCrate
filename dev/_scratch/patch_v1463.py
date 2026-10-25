# -*- coding: utf-8 -*-
"""v1.46.3：① 去掉底部多余横向滚动条（容器不写死宽度）② 窗口默认 1920×1080、最小 1680×960。"""
import io
import ast

P = r"E:/【01】自研软件/【26-19】本地影视中心/src/main_window.py"
s = io.open(P, encoding="utf-8").read()

# ---------- ① 容器宽度交给布局，只固定高度 ----------
old = '''        try:
            self._body.setFixedSize(width, total_rows * rh)
        except RuntimeError:
            return'''
new = '''        # ⚠ v1.46.3：**不能给 _body 写死宽度**。
        #   写死成旧视口宽（或某次 resize 前的宽）会让内容比视口宽 → 底部多出一条横向
        #   滚动条，而且右侧永远"差一点"。宽度交给布局（QScrollArea 会把 host 拉到视口宽），
        #   这里只固定**高度**（撑出竖向滚动条）。
        try:
            self._body.setFixedHeight(total_rows * rh)
            self._body.setMinimumWidth(0)
        except RuntimeError:
            return'''
assert old in s
s = s.replace(old, new)

# width 计算：优先用 body 实际宽度（布局已按视口给），退化到视口宽 - 页面左右边距
s = s.replace('''        width = max(120, int(self._body_w or self.width()))
        cell_w = max(60, (width - 12 * (cols - 1)) // cols)''',
'''        width = int(self._body.width() or 0)
        if width < 200:
            vpw = int(vp.width()) if vp is not None else int(self.width())
            width = max(200, vpw - 40)      # 页面左右边距各 20
        cell_w = max(60, (width - 12 * (cols - 1)) // cols)''')

# ---------- ② 带虚拟网格的页面：关掉横向滚动条（内容必定按视口宽排布） ----------
s = s.replace('''        target = getattr(body_widget, "lazy_grid", None)
        if target is None and hasattr(body_widget, "attach_scroll"):
            target = body_widget
        if target is not None:
            target.attach_scroll(scroll.verticalScrollBar(), scroll.viewport())''',
'''        target = getattr(body_widget, "lazy_grid", None)
        if target is None and hasattr(body_widget, "attach_scroll"):
            target = body_widget
        if target is not None:
            # v1.46.3：网格页一律不要横向滚动条 —— 卡片按视口宽重排即可，
            # 出现横向条只会让底部多一条、右侧留白（用户截图）。
            try:
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            except Exception:
                pass
            target.attach_scroll(scroll.verticalScrollBar(), scroll.viewport())''')

# ---------- ③ 最小窗口尺寸 1680×960（按屏幕钳制） ----------
s = s.replace('''            self.resize(w, h)
            self.move(avail.x() + max(0, (avail.width() - w) // 2),
                      avail.y() + max(0, (avail.height() - h) // 2))
        else:
            self.resize(w, h)''',
'''            self.resize(w, h)
            # v1.46.3（需求 2）：默认 1920×1080，最小 1680×960；
            # 屏幕装不下时按可用区域钳制，避免窗口大于桌面。
            self.setMinimumSize(min(1680, avail.width()), min(960, avail.height()))
            self.move(avail.x() + max(0, (avail.width() - w) // 2),
                      avail.y() + max(0, (avail.height() - h) // 2))
        else:
            self.resize(w, h)
            self.setMinimumSize(1680, 960)''')

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
ast.parse(s)
print("patched v1.46.3 | fixedSize removed:", "setFixedSize(width, total_rows" not in s,
      "| hbar off:", "ScrollBarAlwaysOff" in s,
      "| min size:", "min(1680, avail.width())" in s)
