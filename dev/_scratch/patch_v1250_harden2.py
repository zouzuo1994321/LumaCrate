# -*- coding: utf-8 -*-
"""v1.25.0 加固补 2：把 `_selected_card` 的不变式收紧成「活的卡 或 None」。

起因：冒烟 J7 失败。查下来**不是应用 bug，而是我那条断言把一个没被维护的不变式
当成了已成立的事实**：
  1. `_select_card(victim)` 正常把 victim 记进 `_selected_card`；
  2. `shiboken6.delete(victim)` 把它析构；
  3. 再 `_select_card(victim)` → 命中 `if self._selected_card is card: return` **提前返回**
     —— 不崩（这半边是对的），但 `_selected_card` 里**留着一个悬空引用**。

目前所有取用点都包了 try/except RuntimeError 所以没有可见故障，但「悬空引用」是个
迟早要踩的坑（后面谁写一句 `self._selected_card.foo()` 不带守卫就崩）。
所以这里把不变式坐实：`_selected_card` 恒为「活的卡 或 None」。
"""
import os

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"


def patch(rel, label, old, new, count=1):
    p = os.path.join(ROOT, rel)
    with open(p, encoding="utf-8", newline="") as f:
        s = f.read()
    n = s.count(old)
    if n != count:
        print(f"[失败] {label}: 锚点命中 {n} 次（期望 {count}）")
        print("----- 锚点 -----")
        print(old[:400])
        raise SystemExit(1)
    s = s.replace(old, new, count)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print(f"[OK] {label}")


patch(
    r"src\main_window.py",
    "_select_card：命中同一张卡时顺手清掉悬空引用",
    '''    def _select_card(self, card):
        if self._selected_card is card:
            return
        old = self._selected_card''',
    '''    def _select_card(self, card):
        if self._selected_card is card:
            # 同一张卡被重复点：活着的直接返回（H33 就是钉这条）；
            # 但它可能**已经析构**（换页 / 扫描刷新后事件队列里残留的鼠标事件），
            # 那就把悬空引用清掉再往下走 —— 保证 `_selected_card` 不改「活的卡 或 None」。
            if card is not None and not _qt_alive(card):
                self._selected_card = None
            else:
                return
        old = self._selected_card''',
)

patch(
    r"src\main_window.py",
    "_select_card：目标已析构则不记入选中",
    '''        self._selected_card = card
        # 目标卡片也可能已被换页 / 刷新析构（事件队列里残留的鼠标事件），先判存活再碰它。
        if card and _qt_alive(card):
            card.set_selected(True)
            self._apply_card_glow(card)''',
    '''        # 目标卡片也可能已被换页 / 刷新析构（事件队列里残留的鼠标事件）——
        # **先判存活再记账**，否则 `_selected_card` 会留下悬空引用。
        if card is None or not _qt_alive(card):
            self._selected_card = None
            return
        self._selected_card = card
        card.set_selected(True)
        self._apply_card_glow(card)''',
)

print("\n加固补丁 2 完成。")
