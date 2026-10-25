# -*- coding: utf-8 -*-
"""v1.46.2：修「切页弹出空白小窗」与「滚动出现间隙」。

空白小窗根因：
  `go()` 里 `stack.removeWidget(old)` **只把页面从栈里摘掉、不删除也不隐藏**，
  被摘下的 QScrollArea（以及停留在里面等待 deleteLater 的子卡）会变成
  **无父顶层窗口**（标题沿用「流明盒」、内容空白）—— 正是用户截到的那个窗。
  ⇒ 摘掉后 `hide() + deleteLater()`，并让 LazyGrid 的渲染在「已不可见 / 已脱离父」时直接退出。

间隙根因：
  1) 卡片高度被硬写成 `rh-12`，而真实卡片高度取整后可能差 1~2px，行与行之间会漏出底色；
  2) 窗口换页时只删旧卡不补齐新卡（`_make` 抛错直接 skip）→ 留下孔洞；
  3) overscan 只有 2 行，快速滚动时新卡来不及补。
  ⇒ 行高用**实测卡片高度**；每张卡按自身 height 摆放（不再强改）；overscan 提到 3 行；
     建卡失败时补一个等高占位块，保证不留洞。
"""
import io
import ast

P = r"E:/【01】自研软件/【26-19】本地影视中心/src/main_window.py"
s = io.open(P, encoding="utf-8").read()

# ---------- 1) 切页：摘下的页面必须隐藏并销毁 ----------
s = s.replace('''        if old:
            self.stack.removeWidget(old)''',
'''        if old:
            # v1.46.2：removeWidget 只是"摘出栈"，不会隐藏也不会销毁 ——
            # 被摘下的页面会变成**无父顶层窗口**（用户截到的那个空白「流明盒」小窗）。
            self.stack.removeWidget(old)
            try:
                old.hide()
                old.setParent(None)
                old.deleteLater()
            except RuntimeError:
                pass''')

# ---------- 2) 渲染：不可见 / 已脱离父 → 直接退出，绝不 show() 无父控件 ----------
s = s.replace('''        if not self._virtual or not _qt_alive(self, self._body):
            return
        sb, vp = self._scrollbar, self._viewport''',
'''        if not self._virtual or not _qt_alive(self, self._body):
            return
        # v1.46.2：页面已切走（不可见 / body 不再是自己的孩子）时**绝不建卡**，
        # 否则 setParent 失败会让卡片变成顶层窗口（空白小窗的第二个来源）。
        try:
            if not self.isVisible():
                return
            if self._body.parent() is not self:
                return
        except RuntimeError:
            return
        sb, vp = self._scrollbar, self._viewport''')

# ---------- 3) overscan 3 行 ----------
s = s.replace('        self._overscan = 2', '        self._overscan = 3')

# ---------- 4) 摆位：用卡片自身高度，失败补占位（不留洞） ----------
old_fill = '''        made = {}
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
                        pass'''
new_fill = '''        made = {}
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
                        # v1.46.2：建卡失败也要留下**等高占位**，否则该格子是一个洞
                        # （用户截图里行与行之间那道"间隙"就是这种洞 + 被裁的高度）
                        applog.log(f"建卡失败 idx={idx}: {e}", "error")
                        w = QFrame()
                        w.setObjectName("CardPlaceholder")
                    w.setParent(self._body)
                    made[idx] = w
                i += 1
        for row, base, n in want:
            for c in range(n):
                idx = base + c
                w = made.get(idx)
                if w is not None:
                    try:
                        h = w.height() or (rh - 12)
                        # 高度用于实测行高时可能偏小（还没应用固定尺寸），兜底取 rh-12
                        if h < 20:
                            h = rh - 12
                        w.setGeometry(c * (cell_w + 12), (row - r0) * rh, cell_w, h)
                        w.show()
                    except RuntimeError:
                        pass'''
assert old_fill in s
s = s.replace(old_fill, new_fill)

# ---------- 5) 行高按实测卡片（含 12 间距），并用最大高度兜底 ----------
s = s.replace('''            self._row_h = max(1, probe.height() + 12)''',
'''            self._row_h = max(1, probe.height() + 12)
            self._card_h = max(1, probe.height())''')
s = s.replace('''        self._body_w = 0''','''        self._body_w = 0
        self._card_h = 0''')

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
ast.parse(s)
print("patched v1.46.2 | goto-delete:", "old.setParent(None)" in s,
      "| guard:", "self._body.parent() is not self" in s,
      "| overscan3:", "_overscan = 3" in s,
      "| placeholder:", "CardPlaceholder" in s)
