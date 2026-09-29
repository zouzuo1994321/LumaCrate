# -*- coding: utf-8 -*-
"""演员库 / 导演库右侧的 A-Z 字母索引导航条（v1.30.0，反馈 4）
===============================================================
用户原话：「演员库和导演库 滚轴旁加入 字母索引导航，类似于 A-Z index 控件 方便加速跳转」。

为什么不用 27 个 QPushButton
----------------------------
· 每个按钮都得按 compact 规则订制（全局 QSS `QPushButton{padding:7px 14px}`
  会把内容区压成负数 → 字形被裁，见 ui_hero.compact_button 的注释）；
· 更要命的是高度必须随可用高度均分 —— 固定高度的按钮在窗口变矮时会溢出、
  变高时底部留一条空白。自绘可以按 `height()/27` 精确分摊，还能画 hover 高亮。

所以这里整块自绘（`paintEvent`）+ 自己算命中（`mousePressEvent`）：
对外只暴露一个 `picked(str)` 信号，点到一个「有数据」的字母才发。

字母的来源由 `database.people_letter_index()` 给出：优先罗马音 romaji 首字母，
没有 romaji 就用姓名首字符；非 A-Z 的统统归到 "#"。
**映射里没有这个字母 = 库里没有 = 画成暗色且点了不发信号。**
"""
from PySide6.QtCore import Qt, Signal, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import QWidget

#: 展示顺序：A..Z 之后是「#」（非拉丁字母 / 数字 / 空）
LETTERS = [chr(c) for c in range(ord("A"), ord("Z") + 1)] + ["#"]

BAR_W = 30
_MIN_ROW_H = 17

_COLOR_TEXT = QColor(201, 189, 167)     # #c9bda7，与卡片信息值同色
_COLOR_DIM = QColor(107, 97, 82)        # 无数据的字母（不可点）
_COLOR_HOVER_BG = QColor(192, 57, 43, 60)
_COLOR_ACTIVE = QColor(212, 175, 55)    # #d4af37 金色
_COLOR_ACTIVE_BG = QColor(212, 175, 55, 38)


class LetterIndexBar(QWidget):
    """竖排 A-Z（+ #）索引条。宽度固定 `BAR_W`，高度由外层布局撑满。"""

    picked = Signal(str)      # 点到有数据的字母时发出该字母

    def __init__(self, index=None, parent=None):
        """
        :param index: dict {字母: 该字母第一个人的下标}，来自 `db.people_letter_index()`。
                      缺失的字母画成暗色且不可点。
        """
        super().__init__(parent)
        self.setObjectName("LetterIndexBar")
        self.setFixedWidth(BAR_W)
        self.setMinimumHeight(len(LETTERS) * _MIN_ROW_H)
        # 自绘控件：关掉 QSS 背景，否则父控件样式会盖住 paintEvent 画的东西
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._index = dict(index or {})
        self._hover = None
        self._active = None

    # ---------- 对外 API ----------
    def set_index(self, index: dict):
        self._index = dict(index or {})
        self.update()

    def index(self) -> dict:
        return dict(self._index)

    def row_height(self) -> float:
        return max(_MIN_ROW_H, self.height() / max(1, len(LETTERS)))

    def rect_of(self, letter: str) -> QRect:
        """某个字母的矩形（离屏冒烟用它算点击坐标）。"""
        try:
            i = LETTERS.index(letter)
        except ValueError:
            return QRect()
        h = self.row_height()
        return QRect(0, int(i * h), self.width(), int(h))

    def letter_at(self, y) -> str:
        n = len(LETTERS)
        h = self.row_height()
        i = int(y // h)
        if 0 <= i < n:
            return LETTERS[i]
        return ""

    def is_enabled(self, letter: str) -> bool:
        return letter in self._index

    def position_of(self, letter: str):
        """该字母第一个人在列表中的下标；没有则返回 None。"""
        v = self._index.get(letter)
        return int(v) if v is not None else None

    def set_active(self, letter):
        """高亮当前所在字母（滚动时由页面刷新，目前界面只做静态标记预留）。"""
        if self._active != letter:
            self._active = letter
            self.update()

    def click_letter(self, letter: str) -> bool:
        """以编程方式触发一次点击（离屏冒烟 / 键盘可达性用）。返回是否真的发出信号。"""
        if not self.is_enabled(letter):
            return False
        if letter != "#" and letter not in LETTERS:
            return False
        self.picked.emit(letter)
        return True

    # ---------- 交互 ----------
    def mouseMoveEvent(self, e):
        lt = self.letter_at(e.position().y())
        if lt != self._hover:
            self._hover = lt if self.is_enabled(lt) else None
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self._hover:
            self._hover = None
            self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            lt = self.letter_at(e.position().y())
            if lt and self.is_enabled(lt):
                self.picked.emit(lt)
                return
        super().mousePressEvent(e)

    # ---------- 绘制 ----------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), Qt.transparent)
        h = self.row_height()
        y = 0.0
        for lt in LETTERS:
            r = QRect(0, int(y), self.width(), int(y + h) - int(y))
            on = self.is_enabled(lt)
            if on and lt == self._hover:
                p.fillRect(r, _COLOR_HOVER_BG)
            elif on and lt == self._active:
                p.fillRect(r, _COLOR_ACTIVE_BG)
            f = QFont()
            f.setPixelSize(11)
            f.setBold(bool(on and (lt == self._hover or lt == self._active)))
            p.setFont(f)
            p.setPen(_COLOR_ACTIVE if (on and lt == self._active) else
                     (_COLOR_TEXT if on else _COLOR_DIM))
            p.drawText(r, Qt.AlignHCenter | Qt.AlignVCenter, lt)
            y += h
        p.end()

    def sizeHint(self):
        return QSize(BAR_W, len(LETTERS) * _MIN_ROW_H)
