# -*- coding: utf-8 -*-
"""调整 _render 内部顺序：先算 width/cols/x_off，再做窗口键判重。"""
import io
import ast

P = r"E:/【01】自研软件/【26-19】本地影视中心/src/main_window.py"
s = io.open(P, encoding="utf-8").read()

start = s.find("        # ⚠ v1.46.3：窗口键必须**包含列数**")
end = s.find("        want = []", start)
assert start > 0 and end > start

new = '''        # —— 先算宽度 / 自适应列数 / 水平偏移（这三者决定布局，必须在判重之前算出来）——
        # 宽度以**视口**为准（页面左右边距各 20）：body 与"摆卡片用的宽度"永远一致，
        # 不会出现卡片按旧宽度摆、右侧留一截；也不会比视口宽（不产生横向条）。
        vpw = int(vp.width()) if vp is not None else int(self.width())
        width = max(200, vpw - 40)
        # 卡片是**定宽**的，列数写死会在右侧留一大截（用户反馈"无论拉多宽右侧都有余量"）。
        # 这里按可用宽度挑一组列数：放得下、且右侧余量最小。
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
        cell_w = cw
        # 剩余宽度左右均分（否则余量全堆右侧，观感像"右边永远差一截"）
        _grid_w = cols * cw + (cols - 1) * 12
        self._x_off = max(0, (width - _grid_w) // 2)

        # 判重键必须包含「行窗口 + 列数 + 宽度 + 偏移」：任何一项变化都要重排，
        # 否则窗口拉宽后卡片还停在旧列位（这正是"右侧有余量"的另一半原因）。
        _key = (r0, r1, cols, width, self._x_off)
        if _key == getattr(self, "_win_key", None) and self._cards:
            return
        self._win_key = _key
        self._window = (r0, r1)

        try:
            self._body.setFixedSize(width, total_rows * rh)
        except RuntimeError:
            return

'''
s = s[:start] + new + s[end:]
io.open(P, "w", encoding="utf-8", newline="\n").write(s)
ast.parse(s)
print("reordered | single setFixedSize:", s.count("self._body.setFixedSize(width, total_rows * rh)"))
