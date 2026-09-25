# -*- coding: utf-8 -*-
"""启动动画 / 启动画面（v1.24.0 新增）

需求（反馈 4）：参考给定样式的启动动画 —— logo + 软件名，**主色调为蓝色**。
v1.27.0（反馈 1）：软件更名「流明盒 / LumaCrate」，英文名下面新增一行 **Slogan**，
画布因此从 440×320 长到 440×344，logo 从 100 收到 96。

设计要点
--------
- 全**自绘** `QSplashScreen`（`drawContents`）：圆角深蓝底 + 蓝色渐晕 + 蓝色进度条，
  不依赖任何图片资源，logo 缺省时自动降级为自绘的圆角「影」字标。
- 进度是**真实进度**：`setProgress(pct, tip)` 由启动流程逐步驱动（打开数据库 →
  载入索引统计 → 建主界面），不是假动画。`pct=None` 时切换为**不确定态**（蓝色滑块来回跑）。
- 淡入 / 淡出用 `QPropertyAnimation(windowOpacity)`，动画对象由自身持有（否则被 GC 冻结）。
- 环境变量 `LMC_NO_SPLASH=1` 可完全关闭（离屏冒烟 / 自动化测试用）。

用法::

    sp = SplashScreen(logo_path, ver.APP_NAME, ver.FULL_VERSION)
    sp.fade_in()
    sp.setProgress(15, "正在打开媒体索引…")
    ...
    sp.fade_out(win)
"""
import os
import sys

from PySide6.QtCore import Qt, QRectF, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import (QPixmap, QPainter, QColor, QPen, QFont, QLinearGradient,
                           QPainterPath, QRadialGradient)
from PySide6.QtWidgets import QSplashScreen, QApplication

import version as ver
import i18n      # v1.32.0：Slogan 与启动提示语跟随界面语言（叶子模块）

# —— 蓝色主题（主色调）——————————————————————————————————————
_BG_TOP = QColor("#101b2e")        # 深蓝（上）
_BG_BOT = QColor("#0a1220")        # 更深蓝（下）
_GLOW = QColor(61, 139, 253, 60)    # 顶部蓝色渐晕
_ACCENT_A = QColor("#4f9dff")      # 进度条起点（亮蓝）
_ACCENT_B = QColor("#1f6fe0")      # 进度条终点（深蓝）
_TRACK = QColor(255, 255, 255, 30)  # 进度槽
_TEXT = QColor("#e9f2ff")          # 主文字
_DIM = QColor("#8ea6c8")           # 次要文字
_SLOGAN = QColor("#a9c8ff")        # Slogan 行（v1.27.0，比副标题亮一档的蓝）
_FAINT = QColor("#5d7a9c")         # 版本 / 版权行（更暗的蓝灰）


class SplashScreen(QSplashScreen):
    """蓝色启动画面。宽 440 / 高 320。

    纵向排布**全部走下面的常量**，不要在各处再写魔法数字 —— v1.24.0 第一次出图时
    「64%」和进度槽正好压在英文副标题上，就是因为 logo 高 116 + 固定偏移算出来的
    行高互相吃掉了空间。v1.27.0 又加了一行 Slogan，所以画布长到 344、logo 收到 96。
    """

    W = 440
    H = 344                            # v1.27.0：320 → 344，给 Slogan 行腾位置
    LOGO = 96                          # logo 显示边长（等比缩放后的外框）

    # —— 纵向节奏（自上而下）——
    _LOGO_Y = 24.0                     # logo 框顶端
    _TITLE_GAP = 15.0                  # logo 底 → 标题框顶
    _TITLE_H = 34.0
    _SUB_H = 17.0
    _SUB_GAP = 2.0                     # 标题框底 → 副标题框顶
    _SLOGAN_H = 20.0                   # v1.27.0：Slogan 行高
    _SLOGAN_GAP = 7.0                  # 副标题框底 → Slogan 框顶
    _PCT_H = 14.0
    _PCT_GAP = 12.0                    # Slogan 框底 → 百分比文字顶
    _BAR_GAP = 4.0                     # 百分比底 → 进度槽顶
    _BAR_H = 6.0
    _FOOT_H = 14.0                     # 版本 / 版权每行高
    _FOOT_BOTTOM = 5.0                 # 版权行距底边

    def __init__(self, logo_path=None, title=None, version_text=None,
                 copyright_text=None):
        # 第一个参数必须是 pixmap（QSplashScreen 的签名是 (splash_pixmap, flags)）；
        # 传一个 **W×H 的全透明** pixmap，圆角外的区域才能透出去。
        pm = QPixmap(self.W, self.H)
        pm.fill(Qt.transparent)
        super().__init__(pm, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
                         | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.resize(self.W, self.H)

        self.title = title or ver.APP_NAME
        self.version_text = version_text or ver.FULL_VERSION
        self.copyright_text = copyright_text or ver.COPYRIGHT

        self._pct = 0
        self._tip = "正在启动…"
        self._indeterminate = False
        self._phase = 0.0
        self._fade = None                 # 持有动画引用，防 GC

        self._logo = self._load_logo(logo_path)

        # 不确定态用的小滑块相位定时器（按需启动）
        self._marquee = QTimer(self)
        self._marquee.setInterval(16)
        self._marquee.timeout.connect(self._tick)
        self._center()

    # ---------- 资源 ----------
    def _load_logo(self, path):
        for p in (path, _default_logo_path()):
            if not p or not os.path.exists(p):
                continue
            pm = QPixmap(p)
            if pm.isNull():
                continue
            return pm.scaled(self.LOGO, self.LOGO, Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
        return None                       # 交给 _draw_logo_fallback 自绘

    def _center(self):
        scr = QApplication.primaryScreen()
        if scr is None:
            return
        g = scr.availableGeometry()
        self.move(g.center().x() - self.W // 2, g.center().y() - self.H // 2)

    # ---------- 进度 ----------
    def setProgress(self, pct, tip=None):
        """pct 为 0~100；传 None 进入不确定态。每次刷新都会立刻重绘并放行事件循环。"""
        if pct is None:
            if not self._indeterminate:
                self._indeterminate = True
                self._marquee.start()
        else:
            if self._indeterminate:
                self._indeterminate = False
                self._marquee.stop()
            self._pct = max(0, min(100, int(pct)))
        if tip:
            self._tip = tip
        self.repaint()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()           # 让启动画面真的动起来（否则整段黑屏）

    def progress(self):
        return self._pct

    def _tick(self):
        self._phase += 0.055
        if self._phase > 1.0:
            self._phase -= 1.0
        self.repaint()

    # ---------- 淡入 / 淡出 ----------
    def fade_in(self, ms=620):
        self.setWindowOpacity(0.0)
        self.show()
        self._animate(0.0, 1.0, ms, QEasingCurve.OutCubic)

    def fade_out(self, win=None, ms=380):
        anim = self._animate(1.0, 0.0, ms, QEasingCurve.InCubic)
        if anim is not None:
            anim.finished.connect(lambda: self._finish(win))

    def _animate(self, start, end, ms, curve):
        a = QPropertyAnimation(self, b"windowOpacity", self)   # self 为父 → 不被 GC
        a.setDuration(int(ms))
        a.setStartValue(float(start))
        a.setEndValue(float(end))
        a.setEasingCurve(curve)
        self._fade = a
        a.start()
        return a

    def _finish(self, win):
        try:
            self.close()
        finally:
            if win is not None:
                win.show()
                win.raise_()
                win.activateWindow()

    # ---------- 自绘 ----------
    def _rows(self):
        """算出各行的 y（头部块自上而下、页脚块自下而上），避免两处各算一套。"""
        ly = self._LOGO_Y
        title = ly + self.LOGO + self._TITLE_GAP
        sub = title + self._TITLE_H + self._SUB_GAP
        slogan = sub + self._SUB_H + self._SLOGAN_GAP
        pct = slogan + self._SLOGAN_H + self._PCT_GAP
        bar = pct + self._PCT_H + self._BAR_GAP
        copy_y = self.H - self._FOOT_BOTTOM - self._FOOT_H
        ver_y = copy_y - self._FOOT_H
        tip = ver_y - 18.0 - 14.0
        return {"logo": ly, "title": title, "sub": sub, "slogan": slogan,
                "pct": pct, "bar": bar, "tip": tip, "ver": ver_y, "copy": copy_y}

    def drawContents(self, p):
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        W, H = self.W, self.H
        body = QRectF(1.0, 1.0, W - 2.0, H - 2.0)

        # 1) 圆角深蓝底
        path = QPainterPath()
        path.addRoundedRect(body, 16, 16)
        p.setClipPath(path)
        g = QLinearGradient(0, 0, 0, H)
        g.setColorAt(0.0, _BG_TOP)
        g.setColorAt(1.0, _BG_BOT)
        p.fillPath(path, g)

        # 2) 顶部蓝色渐晕（把主色调压出来）
        rg = QRadialGradient(W / 2.0, -H * 0.15, H * 1.05)
        rg.setColorAt(0.0, _GLOW)
        rg.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillPath(path, rg)

        # 3) 蓝色描边 + 顶部高光
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(79, 157, 255, 120), 1.2))
        p.drawRoundedRect(body.adjusted(0.6, 0.6, -0.6, -0.6), 15, 15)
        hi = QLinearGradient(0, 0, 0, 60)
        hi.setColorAt(0.0, QColor(255, 255, 255, 26))
        hi.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(16, 1, W - 32, 60), hi)

        # 4) logo（居中偏上）
        R = self._rows()
        lx = (W - self.LOGO) / 2.0
        self._draw_logo(p, lx, R["logo"])

        # 5) 标题 + 英文名
        p.setPen(_TEXT)
        f = QFont(); f.setFamily("Microsoft YaHei UI"); f.setPixelSize(24); f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, R["title"], W, self._TITLE_H),
                   Qt.AlignHCenter | Qt.AlignVCenter, self.title)
        p.setPen(_DIM)
        f2 = QFont(); f2.setFamily("Microsoft YaHei UI"); f2.setPixelSize(11)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 2.2)
        p.setFont(f2)
        p.drawText(QRectF(0, R["sub"], W, self._SUB_H),
                   Qt.AlignHCenter | Qt.AlignVCenter, ver.APP_NAME_EN)

        # 5.5) Slogan（v1.27.0 反馈 1）：比副标题亮一档的蓝，字距略收，更像一句标语
        p.setPen(_SLOGAN)
        fs = QFont(); fs.setFamily("Microsoft YaHei UI"); fs.setPixelSize(12)
        fs.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        p.setFont(fs)
        p.drawText(QRectF(24, R["slogan"], W - 48, self._SLOGAN_H),
                   Qt.AlignHCenter | Qt.AlignVCenter, i18n.tr_slogan())

        # 6) 进度条（含百分比）
        self._draw_bar(p, W)

        # 7) 提示语
        p.setPen(_DIM)
        f3 = QFont(); f3.setFamily("Microsoft YaHei UI"); f3.setPixelSize(11)
        p.setFont(f3)
        p.drawText(QRectF(30, R["tip"], W - 60, 18), Qt.AlignHCenter | Qt.AlignVCenter,
                   self._tip)

        # 8) 版本 / 版权
        p.setPen(_FAINT)
        f4 = QFont(); f4.setFamily("Microsoft YaHei UI"); f4.setPixelSize(9)
        p.setFont(f4)
        p.drawText(QRectF(20, R["ver"], W - 40, self._FOOT_H),
                   Qt.AlignHCenter | Qt.AlignVCenter, f"{self.version_text}")
        p.drawText(QRectF(20, R["copy"], W - 40, self._FOOT_H),
                   Qt.AlignHCenter | Qt.AlignVCenter, self.copyright_text)
        p.setClipping(False)

    def _draw_logo(self, p, x, y):
        if self._logo is not None:
            p.drawPixmap(int(x), int(y), self._logo)
            return
        # 兜底：自绘圆角蓝色方块 + 「影」
        r = QRectF(x, y, self.LOGO, self.LOGO)
        lg = QLinearGradient(r.topLeft(), r.bottomRight())
        lg.setColorAt(0.0, _ACCENT_A)
        lg.setColorAt(1.0, _ACCENT_B)
        p.setPen(Qt.NoPen)
        p.setBrush(lg)
        p.drawRoundedRect(r, 26, 26)
        p.setPen(QColor(255, 255, 255, 235))
        f = QFont(); f.setFamily("Microsoft YaHei UI")
        f.setPixelSize(int(self.LOGO * 0.5)); f.setBold(True)
        p.setFont(f)
        p.drawText(r, Qt.AlignCenter, "影")

    def _draw_bar(self, p, W):
        R = self._rows()
        bw, bh = 260.0, self._BAR_H
        bx = (W - bw) / 2.0
        by = R["bar"]
        # 槽
        p.setPen(Qt.NoPen)
        p.setBrush(_TRACK)
        p.drawRoundedRect(QRectF(bx, by, bw, bh), bh / 2, bh / 2)
        # 填充
        lg = QLinearGradient(bx, 0, bx + bw, 0)
        lg.setColorAt(0.0, _ACCENT_A)
        lg.setColorAt(1.0, _ACCENT_B)
        if not self._indeterminate:
            fill = bw * (self._pct / 100.0)
            if fill > 0.5:
                p.setBrush(lg)
                p.drawRoundedRect(QRectF(bx, by, max(fill, bh), bh), bh / 2, bh / 2)
        # 百分比：**右对齐到进度槽右端**、比槽高一行。
        # 居中的话会和副标题在同一水平带上打架（v1.24.0 踩过），靠右还能顺手让
        # 「已走完多少」和槽的右端对齐，读起来更直观。
        p.setPen(_DIM)
        f = QFont(); f.setFamily("Microsoft YaHei UI"); f.setPixelSize(10)
        p.setFont(f)
        p.drawText(QRectF(bx, R["pct"], bw, self._PCT_H),
                   Qt.AlignRight | Qt.AlignVCenter, f"{self._pct}%")
        # 不确定态：另外跑一条来回滑动的亮段（画在槽里，不影响上面的百分比）
        if self._indeterminate:
            seg = bw * 0.28
            x = bx + (bw - seg) * self._phase
            p.setBrush(lg)
            p.drawRoundedRect(QRectF(x, by, seg, bh), bh / 2, bh / 2)


def _default_logo_path():
    """开发期 / 打包期都能找到 logo.png（与 main.py::_app_resource 同一套候选）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = []
    if getattr(sys, "frozen", False):
        cands.append(getattr(sys, "_MEIPASS", ""))
        cands.append(os.path.dirname(sys.executable))
    else:
        cands.append(here)
        cands.append(os.path.dirname(here))
    for c in cands:
        if c:
            path = os.path.join(c, "logo.png")
            if os.path.exists(path):
                return path
    return None


def splash_disabled():
    return str(os.environ.get("LMC_NO_SPLASH", "")).strip() in ("1", "true", "True", "yes")


def make_splash(logo_path=None):
    """按需创建启动画面：被关闭或创建失败时返回 None（**绝不能影响启动**）。"""
    if splash_disabled():
        return None
    try:
        sp = SplashScreen(logo_path)
        sp.show()
        return sp
    except Exception:
        return None


__all__ = ["SplashScreen", "make_splash", "splash_disabled"]
