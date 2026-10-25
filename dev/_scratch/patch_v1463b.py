# -*- coding: utf-8 -*-
"""v1.46.3：虚拟网格按可用宽度自适应列数，消除右侧余量；card_at/jump_to 同口径。"""
import io
import ast

P = r"E:/【01】自研软件/【26-19】本地影视中心/src/main_window.py"
s = io.open(P, encoding="utf-8").read()

# 1) 记录卡片实测宽度
s = s.replace('''            self._row_h = max(1, probe.height() + 12)
            self._card_h = max(1, probe.height())''',
'''            self._row_h = max(1, probe.height() + 12)
            self._card_h = max(1, probe.height())
            self._card_w = max(1, probe.width())''')
s = s.replace('''        self._card_h = 0''', '''        self._card_h = 0
        self._card_w = 0
        self._cols_now = 0     # 当前生效列数（虚拟模式按宽度自适应）''')

# 2) 渲染里：按宽度选列数（取余量最小、且至少放得下的那组）
old = '''        width = int(self._body.width() or 0)
        if width < 200:
            vpw = int(vp.width()) if vp is not None else int(self.width())
            width = max(200, vpw - 40)      # 页面左右边距各 20
        cell_w = max(60, (width - 12 * (cols - 1)) // cols)'''
new = '''        width = int(self._body.width() or 0)
        if width < 200:
            vpw = int(vp.width()) if vp is not None else int(self.width())
            width = max(200, vpw - 40)      # 页面左右边距各 20
        # v1.46.3：**卡片是定宽的**，列数写死会在右侧留一大截空（用户反馈"无论拉多宽
        # 右侧都有余量"）。这里按可用宽度挑一组列数：能放下、且右侧余量最小。
        cw = self._card_w or 217
        nominal = max(1, int(self._cols))
        best_c, best_slack = nominal, None
        for c in range(max(2, nominal - 3), nominal + 6):
            slack = width - (c * cw + (c - 1) * 12)
            if slack < 0:
                continue
            if best_slack is None or slack < best_slack:
                best_c, best_slack = c, slack
        cols = best_c
        self._cols_now = cols
        cell_w = cw'''
assert old in s
s = s.replace(old, new)

# 3) card_at / jump_to 用生效列数
s = s.replace('''        if self._virtual:
            # v1.46.1：卡片已改为绝对定位（`_cards` 字典），不再挂在 QGridLayout 里
            w = self._cards.get(int(index))''',
'''        if self._virtual:
            # v1.46.1：卡片已改为绝对定位（`_cards` 字典），不再挂在 QGridLayout 里
            w = self._cards.get(int(index))''')
s = s.replace('''                row = max(0, int(index)) // max(1, int(self._cols))''',
'''                row = max(0, int(index)) // max(1, int(self._cols_now or self._cols))''')

# 4) 窗口失焦/尺寸变化时清空列数缓存，强制重排
s = s.replace('''                self._body_w = max(120, obj.width())   # 视口宽度变了 → 重算列宽''',
'''                self._body_w = max(120, obj.width())   # 视口宽度变了 → 重算列宽
                self._cols_now = 0''')

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
ast.parse(s)
print("patched | adaptive cols:", "_cols_now" in s, "| card_w:", "_card_w" in s)
