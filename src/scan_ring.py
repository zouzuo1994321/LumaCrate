# -*- coding: utf-8 -*-
"""「进行中」转圈（圆形进度环）—— v1.24.0 反馈 11 起供主页侧栏媒体库行使用，
v1.39.0（需求 3）抽出为独立模块，供工具窗左侧导航复用（运行中任务旁边的转圈）。

设计（与侧栏同款）：
- 自绘 paintEvent（QSS background 会盖掉自绘区 → 硬边色带，本项目铁律）；
- QTimer 45ms 驱动弧线旋转；pct=0 且 busy 时画一段 22% 的旋转弧（转圈观感），
  pct>0 时画进度弧；
- 绝不开 WA_StyledBackground；WA_TransparentForMouseEvents 保证不挡点击。
"""

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget


class ScanRing(QWidget):
    """侧边栏媒体库名 / 工具窗导航项旁边的**圆形进度环**。

    需求：正在进行的任务旁边显示一个像进度环一样的圆形，展示进度、并能一眼看出
    「该项正在进行中」。所以这里不只是显示百分比：进行中会**转圈**（QTimer 驱动
    弧线旋转），做完/空闲时整个环淡化消失。
    """

    RING = 18

    def __init__(self, parent=None, size=None):
        super().__init__(parent)
        if size:
            self.RING = int(size)
        self.setFixedSize(self.RING, self.RING)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._pct = 0
        self._busy = False
        self._phase = 0.0
        self._tip = ""
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def set_state(self, busy, pct=0, tip=""):
        """busy=False → 淡出隐藏。pct 为 0~100。"""
        changed = (busy != self._busy) or (int(pct) != self._pct)
        self._busy = bool(busy)
        self._pct = max(0, min(100, int(pct)))
        if tip:
            self._tip = tip
        if self._busy:
            if not self._timer.isActive():
                self._timer.start()
            self.show()
            self.raise_()
        else:
            self._timer.stop()
            self.hide()
        if changed:
            self.update()

    def is_busy(self):
        return self._busy

    def _tick(self):
        self._phase = (self._phase + 0.09) % 1.0
        self.update()

    def paintEvent(self, e):
        if not self._busy:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(1.5, 1.5, self.RING - 3.0, self.RING - 3.0)
        # 槽
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 38), 2.0))
        p.drawEllipse(r)
        # 进度弧（0% 时改为一段旋转的弧，做成「转圈」的观感）
        span = -int(360 * 16 * (self._pct / 100.0)) if self._pct else 0
        if not span:
            span = -int(360 * 16 * 0.22)
        start = int(-90 * 16 - (self._phase * 360 * 16 if not self._pct else 0))
        p.setPen(QPen(QColor("#5fb0ff"), 2.4))
        p.drawArc(r, start, span)
        p.end()
