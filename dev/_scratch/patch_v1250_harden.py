# -*- coding: utf-8 -*-
"""v1.25.0 发布前加固：修掉 app.log 里捡到的 QTimer 已析构崩溃。

证据（真机 `index_data/logs/app.log`，2026-09-21 09:25:33，`v1.24.1 (Build 2609210033)`
的一次真实会话，09:24:49 刚做过媒体库扫描）：
    File "main_window.py", line 1553, in mousePressEvent
    File "main_window.py", line 3021, in _select_card
    File "main_window.py", line 1928, in set_selected
    RuntimeError: libshiboken: Internal C++ object (PySide6.QtCore.QTimer) already deleted.

根因：`set_selected(True)` 每次都**新建**一个 QTimer 并覆盖旧引用。旧定时器虽然还挂在
卡片下（父对象是卡片）不会泄漏，但当它被析构之后，`self._timer` 就指向一个「已析构的
C++ 对象」，下一次 `set_selected` 走到 `self._timer.stop()` 直接抛 RuntimeError。
扫描/换页会批量 `deleteLater()` 上一批卡片，而此时事件队列里还压着投给卡片的鼠标事件
—— 就是这条路径。

修法：定时器**只建一次、之后复用**，并且 `.stop()` 包一层 RuntimeError 兜底（真析构了就
丢掉引用按需重建）。同时给 `_select_card` 的目标卡片补 `_qt_alive` 判定。

顺带把构建号推到 0035 —— 源码变了，已打好的 0034 包必须重打。
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


OLD_SET = '''    def set_selected(self, on):
        if self._selected == on:
            return
        self._selected = on
        if on:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(40)
        elif self._timer:
            self._timer.stop()
            self._timer = None
        self.update()
'''

NEW_SET = '''    def set_selected(self, on):
        if self._selected == on:
            return
        self._selected = on
        # v1.25.0 加固：定时器「只建一次、之后复用」。
        # 原来每次选中都新建一个 QTimer 并覆盖旧引用 —— 旧的那个虽然还挂在卡片下（父对象
        # 是卡片）不泄漏，但只要它被析构，`self._timer` 就成了「已析构的 C++ 对象」，
        # 下一次进来在 `self._timer.stop()` 处抛：
        #   RuntimeError: libshiboken: Internal C++ object (PySide6.QtCore.QTimer) already deleted.
        # 真机 app.log 抓到过（2026-09-21 09:25:33，扫描后 mousePressEvent → _select_card
        # → set_selected）。所以这里 stop 要兜底，真析构了就丢引用、下面按需重建。
        t = self._timer
        if t is not None:
            try:
                t.stop()
            except RuntimeError:
                t = None
                self._timer = None
        if on:
            if self._timer is None:
                self._timer = QTimer(self)
                self._timer.timeout.connect(self._tick)
            self._timer.start(40)
        self.update()
'''

# PosterCard 与 ActorCard 各一份，正文逐字节相同 → 一次替换两处
patch(r"src\main_window.py", "set_selected 加固（PosterCard + ActorCard）",
      OLD_SET, NEW_SET, count=2)

patch(
    r"src\main_window.py",
    "_select_card：目标卡片补存活判定",
    '''        self._selected_card = card
        if card:
            card.set_selected(True)
            self._apply_card_glow(card)''',
    '''        self._selected_card = card
        # 目标卡片也可能已被换页 / 刷新析构（事件队列里残留的鼠标事件），先判存活再碰它。
        if card and _qt_alive(card):
            card.set_selected(True)
            self._apply_card_glow(card)''',
)

# ---------------- 构建号 0034 -> 0035
patch(
    r"src\version.py",
    "version.py 构建号 -> 0035",
    '''# 内部构建号 YYMMDDNNNN (2026-09-21 第三十四次构建，末四位按「每次打包自增」连续计数)
# 0034：v1.25.0 六条反馈（标签优化页为新增模块）
BUILD_DATE = "260921"
BUILD_SEQ = "0034"''',
    '''# 内部构建号 YYMMDDNNNN (2026-09-21 第三十五次构建，末四位按「每次打包自增」连续计数)
# 0034：v1.25.0 六条反馈（标签优化页为新增模块）
# 0035：0034 打包后从 app.log 捡到 QTimer 已析构崩溃（v1.24.1 起就存在），修复后重打
BUILD_DATE = "260921"
BUILD_SEQ = "0035"''',
)

print("\n加固补丁完成。")
