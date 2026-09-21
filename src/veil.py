# -*- coding: utf-8 -*-
"""应用内磨砂玻璃底衬（v1.7.0）。

为什么不用 Windows 系统级 Acrylic / Mica
--------------------------------------------------
本机实测（Windows 11 build 26200 + PySide6 6.11），用「纯白背景板 + Win32
GetWindowRect 定位 + 窗口内部平均亮度」做二值判定，结果：

    方案组合                                   窗口内部平均亮度   结论
    有边框 + DWM 系统背景材质                        12.8        不透明
    无边框 + DWM 系统背景材质（Mica/Acrylic/Tabbed） 19~29        不透明
    无边框 + SetWindowCompositionAttribute 亚克力     26~29        不透明
    无边框 + 不开任何系统模糊                        62.7        ★ 半透明

即：所有系统级模糊 API 在把窗口顶成不透明的同时，模糊本身也透不出来；
唯一能透出桌面的组合（无边框 + WA_TranslucentBackground）**没有模糊**，
文字压在桌面内容上可读性很差。

因此改为**应用内磨砂**：把一张背景图（当前作品剧照 / 兜底程序化底图）强模糊 +
压暗后铺满窗口，再在其上叠加半透明玻璃面板。视觉上就是磨砂玻璃，且：
  · 不受桌面内容干扰，可读性可控；
  · 与主题的墨黑 / 朱红 / 鎏金基调统一。
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import (QPixmap, QPainter, QColor, QLinearGradient,
                           QRadialGradient)
from PySide6.QtWidgets import QWidget

# 模糊核：先把图缩到 1/BLUR_FACTOR 再升采样，等效超大半径高斯，速度快几个数量级
BLUR_FACTOR = 42


def blur_pixmap(pm: QPixmap, factor: int = BLUR_FACTOR) -> QPixmap:
    """降采样 → 升采样 的快速强模糊（磨砂感来源）。"""
    if pm is None or pm.isNull():
        return pm
    w = max(8, pm.width() // max(2, factor))
    h = max(8, pm.height() // max(2, factor))
    small = pm.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return small.scaled(pm.width(), pm.height(), Qt.IgnoreAspectRatio,
                        Qt.SmoothTransformation)


def cover(pm: QPixmap, w: int, h: int) -> QPixmap:
    """按「填满并裁切」缩放（不拉伸变形）。"""
    if pm is None or pm.isNull() or w <= 0 or h <= 0:
        return pm
    if pm.width() <= 0 or pm.height() <= 0:
        return pm
    sw = max(w, int(pm.width() * h / pm.height()))
    sh = max(h, int(pm.height() * w / pm.width()))
    return pm.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def default_backdrop(w: int, h: int) -> QPixmap:
    """没有剧照时的兜底底图：墨黑底 + 朱红/鎏金柔光，模糊后天然是磨砂质感。"""
    w, h = max(64, w), max(64, h)
    small = QPixmap(max(64, w // BLUR_FACTOR), max(64, h // BLUR_FACTOR))
    small.fill(QColor(11, 9, 8))
    p = QPainter(small)
    p.setRenderHint(QPainter.Antialiasing, True)
    sw, sh = small.width(), small.height()
    for (cx, cy, rad, color) in ((0.16, 0.10, 1.05, QColor(139, 43, 33, 210)),
                                 (0.92, 0.14, 0.85, QColor(201, 162, 74, 150)),
                                 (0.70, 0.98, 1.15, QColor(74, 32, 28, 200)),
                                 (0.05, 0.90, 0.75, QColor(120, 96, 42, 110))):
        g = QRadialGradient(sw * cx, sh * cy, max(sw, sh) * rad)
        c0 = QColor(color); c1 = QColor(color); c1.setAlpha(0)
        g.setColorAt(0.0, c0); g.setColorAt(1.0, c1)
        p.fillRect(0, 0, sw, sh, g)
    p.end()
    return small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


class Veil:
    """底衬的绘制逻辑（与 QWidget 解耦，方便离屏测试）。"""

    # v1.21.0：原图缓存上限。首页悬停会连续换很多张剧照，缓存无上限时
    # 每张原图（可能 1920×1080 级）都常驻，滚一会儿内存就涨上去、开始发卡。
    _CACHE_MAX = 6

    def __init__(self):
        self._src_path = None
        self._cache = {}          # path -> 原图 QPixmap（LRU，最多 _CACHE_MAX 张）
        self._cache_order = []    # 最近使用的 path，队首最旧
        self._blurred = None      # 已按当前尺寸模糊好的成品
        self._blurred_for = None  # (path, w, h)
        self._scrim = 150
        self._enabled = True

    def _remember(self, path, pm):
        self._cache[path] = pm
        if path in self._cache_order:
            self._cache_order.remove(path)
        self._cache_order.append(path)
        while len(self._cache_order) > self._CACHE_MAX:
            self._cache.pop(self._cache_order.pop(0), None)

    # ---- 配置 ----
    def set_enabled(self, on: bool):
        if bool(on) != self._enabled:
            self._enabled = bool(on)
            self._blurred = None

    def set_scrim(self, alpha: int):
        """压暗程度：越大越实（0~255）。"""
        self._scrim = max(0, min(255, int(alpha)))
        self._blurred = None

    def set_source(self, path):
        """背景图路径；None / 不存在 → 用兜底底图。"""
        path = path if (path and str(path).strip()) else None
        if path != self._src_path:
            self._src_path = path
            self._blurred = None

    @property
    def source(self):
        return self._src_path

    # ---- 绘制 ----
    def pixmap(self, w: int, h: int):
        key = (self._src_path, w, h)
        if self._blurred is not None and self._blurred_for == key:
            return self._blurred
        src = None
        if self._src_path:
            pm = self._cache.get(self._src_path)
            if pm is None:
                pm = QPixmap(str(self._src_path))
                if pm.isNull():
                    pm = None
                else:
                    self._remember(self._src_path, pm)
            if pm is not None:
                # 先模糊再裁切：避免把大图放大后再模糊导致细节残留
                src = blur_pixmap(cover(pm, w, h))
        if src is None or src.isNull():
            src = default_backdrop(w, h)
        self._blurred = src
        self._blurred_for = key
        return src

    def paint(self, painter: QPainter, w: int, h: int):
        if w <= 0 or h <= 0:
            return
        if not self._enabled:
            painter.fillRect(0, 0, w, h, QColor(15, 13, 12))
            return
        pm = self.pixmap(w, h)
        if pm is not None and not pm.isNull():
            painter.drawPixmap(0, 0, pm)
        # 压暗（保证面板上的文字可读）
        painter.fillRect(0, 0, w, h, QColor(13, 11, 10, self._scrim))
        # 四角再压一点，形成玻璃的纵深
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor(0, 0, 0, 46))
        g.setColorAt(0.45, QColor(0, 0, 0, 0))
        g.setColorAt(1.0, QColor(0, 0, 0, 66))
        painter.fillRect(0, 0, w, h, g)


class VeilWidget(QWidget):
    """主窗口的中央容器：自绘磨砂底衬，其余子控件叠在它上面。

    注意：必须关掉 WA_StyledBackground，否则样式表里的背景会在**子控件区域**
    再刷一层，把自绘的磨砂底衬盖掉（v1.6.0 详情页黑底就是这个坑）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CentralVeil")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.veil = Veil()

    def paintEvent(self, e):
        p = QPainter(self)
        self.veil.paint(p, self.width(), self.height())
        p.end()

    def set_source(self, path):
        self.veil.set_source(path)
        self.update()
