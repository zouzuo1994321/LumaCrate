# -*- coding: utf-8 -*-
"""Emby 风格详情页：全宽 fanart 横幅 + 元数据 + 操作按钮 + 圆形演员行 + 文件信息。"""
import os

from PySide6.QtCore import (Qt, QRectF, QRect, QPoint, QPointF, QSize, QTimer, QEvent,
                            QObject)
from PySide6.QtGui import (QPixmap, QPainter, QColor, QPen, QLinearGradient, QFont,
                           QTextLayout, QFontMetrics, QPainterPath, QAction)
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea,
    QFrame, QMenu, QMessageBox, QApplication, QDialog, QDoubleSpinBox,
    QGridLayout, QLayout, QSizePolicy, QLineEdit, QListWidget,
    QListWidgetItem, QInputDialog, QAbstractSpinBox,
)

import database as db
import media_meta as mm
import player as player_mod
import nfo_parser as nfo_mod
import scanner as scanner_mod
import config as cfg            # v2.0.2：数值框最小宽度统一走 cfg.SPIN_MIN_W（叶子模块，不成环）


# ---------- 图像辅助 ----------
def cover_pixmap(path, w, h):
    """按 cover 方式缩放并居中裁剪到 w×h。"""
    if not path or not os.path.exists(path):
        return QPixmap()
    src = QPixmap(path)
    if src.isNull() or w <= 0 or h <= 0:
        return QPixmap()
    scaled = src.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (scaled.width() - w) // 2)
    y = max(0, (scaled.height() - h) // 2)
    return scaled.copy(x, y, w, h)


def _part_thumb_path(p):
    """选集片源同目录下的横版缩略图 `<番号>-thumb.jpg`（v1.18.0 反馈 95）。

    优先用它而非竖版海报：横版缩略图按 KeepAspectRatio 完整显示，更贴近片源内容。
    """
    fp = (p or {}).get("file_path")
    if not fp:
        return None
    d = os.path.dirname(fp)
    s = os.path.splitext(os.path.basename(fp))[0]
    cand = os.path.join(d, s + "-thumb.jpg")
    return cand if os.path.exists(cand) else None


#: v2.0.1（反馈 4）：性别流光向外扩出的像素（画布因此比头像大 2×GLOW_W）
GLOW_W = 6
#: 女 → 粉、男 → 蓝（与演员卡 ♀/♂ 同一套语义色）
#: v2.0.2（反馈 2）：粉色由 #ff7fa1 换成 #e4587c，流光跟着一起换（同一个「粉」）。
GLOW_FEMALE = "#e4587c"
GLOW_MALE = "#338ef7"

#: v2.0.3（反馈 8）：**演职员名字**按身份着色 —— 女演员粉 / 男演员蓝 / 导演黄 / 未知白。
#: 卡片小字（`main_window._crew_names_html`）与详情页演职人员（`CastAvatar`）共用这一处，
#: 两边永远同色。导演优先于性别判定（导演就是导演，不分男女）。
NAME_DIRECTOR = "#f5a524"
NAME_UNKNOWN = "#fafafa"

#: v2.0.4（反馈 9）：**默认**（未收藏）名字的颜色 —— 与卡片「演员：/导演：」标签、
#: 详情页角色小字（Actor / 导演）同色。身份色只在**收藏后**才亮起来。
#: v2.0.5：详情页也改走这套三档规则，所以常量挪到这里当**唯一真源**
#: （`main_window._CREW_NAME_DIM` 只是别名，别再各写一份）。
CREW_NAME_DIM = "#a1a1aa"


def is_director_role(role_text):
    """角色串是不是「导演」。数据里可能是 `Director`（大写）/ `导演` / 其它写法。"""
    t = str(role_text or "").strip().lower()
    return t in ("director", "导演") or "导演" in t or "director" in t


def crew_name_color(gender, is_director=False):
    """演职员名字的颜色：导演黄 > 女粉 > 男蓝 > 未知白。"""
    if is_director:
        return NAME_DIRECTOR
    g = str(gender or "").strip().lower()
    if g == "female":
        return GLOW_FEMALE
    if g == "male":
        return GLOW_MALE
    return NAME_UNKNOWN


def _paint_glow(p, cx, cy, r, color, w):
    """在半径 r 的圆外画一圈柔光（由外向内叠圆，越靠边越亮）＋ 一圈细亮环。

    - 柔光**必须**画在圆形照片之前、且画布比照片大 w 像素，否则会被照片裁掉；
    - 细环放在最外层 +1px：深色底上只有柔光会「发糊」，有环才像「流光」。
    """
    c = QColor(color)
    p.save()
    p.setPen(Qt.NoPen)
    for i in range(int(w), 0, -1):
        t = 1.0 - (i - 1) / float(w)          # i=w → 0（最外、最淡）；i=1 → 1（贴边、最亮）
        a = int(round(112 * (t ** 2.0)))
        if a <= 2:
            continue
        p.setBrush(QColor(c.red(), c.green(), c.blue(), min(255, a)))
        p.drawEllipse(QPointF(cx, cy), r + i - 0.35, r + i - 0.35)
    pen = QPen(QColor(c.red(), c.green(), c.blue(), 168))
    pen.setWidthF(1.4)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r + 1.0, r + 1.0)
    p.restore()


def circle_pixmap(path, size, bg="#27272a", glow=None, glow_w=0):
    """圆形头像；无图时返回占位圆。

    v2.0.1（反馈 4）：`glow` 给一个颜色时，在圆外画一圈柔光 —— 画布因此变成
    `size + 2×glow_w`，调用方要用 `pixmap.size()` 而不是原来的 size 来定控件尺寸。
    """
    g = int(glow_w) if glow else 0
    W = size + g * 2
    src = QPixmap(path) if (path and os.path.exists(path)) else QPixmap()
    out = QPixmap(W, W)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    if g > 0:
        _paint_glow(p, W / 2.0, W / 2.0, size / 2.0, glow, g)
    clip = QPainterPath()
    clip.addEllipse(QRectF(g, g, size, size))
    p.setClipPath(clip)
    if not src.isNull():
        s = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        p.drawPixmap(g + (size - s.width()) // 2, g + (size - s.height()) // 2, s)
    else:
        p.fillRect(g, g, size, size, QColor(bg))
        p.setPen(QColor("#a1a1aa"))
        f = QFont(); f.setPointSize(int(size / 3)); p.setFont(f)
        p.drawText(QRectF(g, g, size, size), Qt.AlignCenter, "人")
    p.end()
    return out


# ---------- 小控件辅助 ----------
def compact_button(text, width, height=26, tooltip="", ghost=True):
    """窄按钮（← → ↑ ↓ 测试 复制 …）：规避全局 QSS 的 `QPushButton{padding:7px 14px}`。

    坑（v1.11.0 已踩、v1.11.1 系统性收口）：全局内边距是按常规按钮给的 7px 14px，
    窄按钮宽度只有 28~48px，减掉 28px 横向内边距后内容区为负 → 字形被完全裁掉，
    界面上表现为「按钮框在，但里面什么都没有」（顶栏 ← →、设置里 ↑ ↓ 都是这个原因）。
    这里统一打 `compact` 属性，由 style.qss 的 `QPushButton[compact="1"]` 把内边距压成 0。
    """
    b = QPushButton(text)
    b.setObjectName("Ghost" if ghost else "Primary")
    b.setProperty("compact", "1")
    b.setFixedSize(width, height)
    if tooltip:
        b.setToolTip(tooltip)
    b.setCursor(Qt.PointingHandCursor)
    # 属性是在样式表已加载之后才设的，重新 polish 一次确保选择器立即生效
    b.style().unpolish(b)
    b.style().polish(b)
    return b


def placeholder_pixmap(w, h, text="影", bg="#27272a"):
    """无图时生成占位图：渐变底 + 首字，避免详情/卡片出现空白。"""
    pm = QPixmap(w, h)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0.0, QColor("#3f3f46"))
    g.setColorAt(1.0, QColor("#18181b"))
    p.fillRect(0, 0, w, h, g)
    p.setPen(QColor("#52525b"))
    p.drawRect(0, 0, w - 1, h - 1)
    p.setPen(QColor("#66a9ff"))
    f = QFont()
    f.setBold(True)
    f.setPointSize(max(12, int(min(w, h) / 4)))
    p.setFont(f)
    ch = (text or "影").strip()[:1].upper() or "影"
    p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, ch)
    p.end()
    return pm


def _label(text, size=12, bold=False, color="#ecedee", wrap=False, shadow=False):
    l = QLabel(text)
    l.setStyleSheet(f"font-size:{size}px;color:{color};" + ("font-weight:bold;" if bold else ""))
    l.setWordWrap(wrap)
    if shadow:
        _apply_text_shadow(l)
    return l


def _apply_text_shadow(widget, blur=18, dy=2, alpha=200):
    """给压在图上的文字加投影，替代整块黑色底框，保证可读性。"""
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)
    return widget


class ElidedLabel(QLabel):
    """最多显示 N 行，超出部分用「 ...」结尾（v1.45.3）。

    为什么不用按**字数**截断（原 220 字）：详情面板宽度随窗口变化，同样 220 字
    在宽屏 2 行、在窄屏能折成 6 行。QLabel 自己也不会多行省略。

    实现：**paintEvent 里按当前像素宽度折行**（`_shown(width)`），只画前 N 行、
    末行补「 ...」；高度固定 N 行。不在 resize 时改 text —— 首次布局控件还是默认
    宽度，算出的省略结果会偏短（真机会只显示半行）。
    """

    def __init__(self, text="", max_lines=2, parent=None, px=12):
        super().__init__(parent)
        self._max_lines = max(1, int(max_lines))
        #: v1.45.5：**逻辑像素**字号。QSS 的 `px` 会按 devicePixelRatio 放大，而
        #: `QFont.setPixelSize()` **不随 DPI 缩放** —— 上一版直接 setPixelSize(34)，
        #: 在 125%/150% 缩放的屏幕上标题明显变小。这里存逻辑值，绘制/度量时乘 dpr。
        self._px = max(1, int(px))
        self._full = (text or "").replace(chr(10), " ")
        self.setTextFormat(Qt.PlainText)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setToolTip(self._full)          # 悬停看全文
        # v1.46.9（反馈 1）：高度 = **实际占用的行数**，不是恒定的 N 行。
        # 1 行标题就只占 1 行 —— 否则标题与简介之间会多出一整行空白。
        self._lines = self._max_lines
        self.setFixedHeight(self._height_for(self._max_lines))

    # ---------- 高度（按实际行数，v1.46.9 反馈 1） ----------
    def _height_for(self, n):
        return int(self._eff_font_metrics().lineSpacing() * max(1, int(n)) + 6)

    def _apply_lines(self):
        """按当前宽度重算「实际几行」，把高度收到 n 行。

        为什么不在 `__init__` 里算：构造时控件还是默认宽度（QScrollArea 里通常是 640），
        算出来的行数和真实布局无关 —— 与 `_shown()` 文档里记的是同一个坑；
        真实宽度只有在 resize / show 之后才确定，所以两处都挂上重算。
        """
        self.ensurePolished()          # QSS 字体在 polish 阶段才写进控件，先确认真实字体
        w = max(60, self.width() - 2)
        n = self._count_lines(self._full, w) if self._full else 1
        n = max(1, min(self._max_lines, n))
        if n == self._lines and self.height() == self._height_for(n):
            return
        self._lines = n
        self.setFixedHeight(self._height_for(n))    # setFixedHeight 同时设 min/max，避免布局再拉伸

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_lines()

    def showEvent(self, e):
        super().showEvent(e)
        self._apply_lines()

    # ---------- 字号（随 DPI） ----------
    def _eff_font(self):
        f = QFont(self.font())
        dpr = float(self.devicePixelRatioF() or 1.0)
        f.setPixelSize(max(1, int(round(self._px * dpr))))
        return f

    def _eff_font_metrics(self):
        return QFontMetrics(self._eff_font())

    def setText(self, text):
        self._full = (text or "").replace(chr(10), " ")
        self.setToolTip(self._full)
        self._apply_lines()
        self.update()

    def full_text(self):
        return self._full

    def _shown(self, width):
        """按给定像素宽度返回「最多 N 行 + 省略号」的字符串（纯函数，便于断言）。

        先 `ensurePolished()`：QSS 的 `font-size` 是在 polish 阶段才写进控件字体的，
        不调用的话 `font()` 还是默认字号，折行算出来会短一半（实测 454px 只排 20 字）。
        """
        fm = self._eff_font_metrics()
        width = max(60, int(width) - 2)
        text = self._full
        if not text:
            return ""
        tl = QTextLayout(text, self.font())
        tl.beginLayout()
        lines = []
        while True:
            ln = tl.createLine()
            if not ln.isValid():
                break
            ln.setLineWidth(width)
            lines.append(ln)
        tl.endLayout()
        if len(lines) <= self._max_lines:
            return text
        last = lines[self._max_lines - 1]
        keep = text[: last.textStart() + last.textLength()]
        suffix = " ..."
        cand = keep.rstrip() + suffix
        # 只在「加省略号后**行数**仍超 N」时才丢字：不能按单行宽度判，
        # 否则两行文本会被当成一行、砍掉一半（实测 454px 只剩 37 字）。
        while keep and self._count_lines(cand, width) > self._max_lines:
            keep = keep[:-1]
            cand = keep.rstrip() + suffix
        return cand

    def _count_lines(self, text, width):
        tl = QTextLayout(text, self._eff_font())
        tl.beginLayout()
        n = 0
        while True:
            ln = tl.createLine()
            if not ln.isValid():
                break
            ln.setLineWidth(width)
            n += 1
        tl.endLayout()
        return n

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setFont(self._eff_font())
            p.setPen(self.palette().color(self.foregroundRole()))
            p.drawText(self.rect(), int(Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap),
                       self._shown(self.width()))
        finally:
            p.end()


# ---------- 流式布局（v1.19.1 反馈 1/2：详情面板随窗口宽度自适应，避免横向滚动条） ----------
class FlowLayout(QLayout):
    """子项按可用宽度自动换行（超一行自动折到下一行）。

    用途：详情面板里的「元数据行」「选集缩略卡网格」原先用固定横向布局，
    内容宽度会撑出一个**最小宽度**，在首页右侧较窄的详情栏里撑出横向滚动条
    （用户必须拖动底部滚轴才能看全信息）。改用流式布局后，元素会随容器宽度换行，
    面板宽度完全跟随窗口，不再需要横向滚动。`addStretch` 提供为 no-op，
    以兼容既有按「横向布局」写的调用点。
    """

    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def addStretch(self, *args):      # 横向布局的占位调用，流式布局下无意义 → no-op
        return None

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations()          # 不主动扩张

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        eff = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = eff.x(), eff.y()
        line_h = 0
        for it in self._items:
            hint = it.sizeHint()
            if x + hint.width() > eff.right() + 1 and line_h > 0:
                x = eff.x()
                y += line_h + self.spacing()
                line_h = 0
            if not test_only:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self.spacing()
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.bottom()


# ---------- 剧照（extrafanart） ----------
#: 剧照目录名（Emby / Kodi 约定，全部按小写比较）
_STILL_DIRS = ("extrafanart", "extrafanarts", "extrafanarts2", "extrathumbs", "thumbs")
_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
#: 剧照缩略图尺寸（16:9，横向条里一屏约 5~6 张，窄窗口也能划）
_STILL_W, _STILL_H = 240, 135


def _natural_key(name):
    """自然排序：`fanart10` 排在 `fanart9` 之后（而不是字典序的 `fanart10` < `fanart9`）。"""
    import re as _re
    return [int(t) if t.isdigit() else t.lower() for t in _re.split(r"(\d+)", str(name))]


def find_extrafanart(media):
    """扫描片源目录下的 `extrafanart` 剧照目录，返回图片绝对路径列表（v1.46.9 反馈 2）。

    从 `file_path` 与 `nfo_path` 所在目录分别找一层子目录（大小写不敏感），
    命中 `extrafanart` / `extrafanarts` / `extrathumbs` / `thumbs` 即收集其中的图片。
    不去递归更深层：Emby 的约定就是「同目录下 extrafanart/ 平铺一堆 jpg」，
    深挖既慢又容易把别的影片的图卷进来。
    """
    roots = []
    for key in ("file_path", "nfo_path"):
        p = (media or {}).get(key)
        if not p:
            continue
        d = p if os.path.isdir(p) else os.path.dirname(p)
        if d and d not in roots:
            roots.append(d)
    out = []
    for d in roots:
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in sorted(names, key=_natural_key):
            sub = os.path.join(d, name)
            if name.lower() not in _STILL_DIRS or not os.path.isdir(sub):
                continue
            try:
                files = os.listdir(sub)
            except OSError:
                continue
            for f in sorted(files, key=_natural_key):
                if not f.lower().endswith(_IMG_EXT):
                    continue
                fp = os.path.join(sub, f)
                if fp not in out:
                    out.append(fp)
    return out


class StillStrip(QScrollArea):
    """横向剧照条：滚轮 = 左右滑（v1.46.9 反馈 2）。

    竖向滚动区里塞一个横向 `QScrollArea`，滚轮事件会被它自己吃掉 —— 用户以为「划不动」。
    这里把竖向滚轮转成横向位移，触摸板横向滑动也照常可用。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                           "QScrollArea>QWidget>QWidget{background:transparent;}")

    def wheelEvent(self, e):
        d = e.angleDelta().x() or e.angleDelta().y()
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - d)
        e.accept()

    def page(self, direction):
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() + direction * max(160, int(bar.pageStep() * 0.9)))


class StillViewer(QDialog):
    """剧照大图查看（点剧照打开；← → 或按钮翻页，Esc 关闭）。"""

    def __init__(self, paths, index=0, parent=None):
        super().__init__(parent)
        self._paths = list(paths or [])
        self._i = max(0, min(len(self._paths) - 1, int(index)))
        self.setWindowTitle("剧照")
        self.setStyleSheet("QDialog{background:#0a0a0b;}")
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignCenter)
        v.addWidget(self._img, 1)
        row = QHBoxLayout()
        self._prev = compact_button("‹", 32, 28, "上一张")
        self._next = compact_button("›", 32, 28, "下一张")
        self._prev.clicked.connect(lambda: self._step(-1))
        self._next.clicked.connect(lambda: self._step(1))
        self._cap = _label("", 12, False, "#d4d4d8")
        row.addWidget(self._prev)
        row.addWidget(self._next)
        row.addSpacing(8)
        row.addWidget(self._cap, 1)
        v.addLayout(row)
        scr = QApplication.primaryScreen()
        g = scr.availableGeometry() if scr is not None else None
        self.resize(int(g.width() * 0.72) if g else 1100,
                    int(g.height() * 0.78) if g else 700)
        self._show_current()

    def _show_current(self):
        if not self._paths:
            return
        path = self._paths[self._i]
        pm = QPixmap(path)
        if not pm.isNull():
            pm = pm.scaled(max(320, self.width() - 40), max(240, self.height() - 90),
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._img.setPixmap(pm)
        else:
            self._img.setText("（图片无法读取）")
        self._cap.setText(f"{self._i + 1} / {len(self._paths)}  ·  {os.path.basename(path)}")
        self._prev.setEnabled(self._i > 0)
        self._next.setEnabled(self._i < len(self._paths) - 1)

    def _step(self, d):
        self._i = max(0, min(len(self._paths) - 1, self._i + d))
        self._show_current()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Left:
            self._step(-1)
        elif e.key() == Qt.Key_Right:
            self._step(1)
        elif e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


# ---------- 横幅(带渐变遮罩) ----------
class HeroBanner(QWidget):
    def __init__(self, height=430):
        super().__init__()
        self._src = None
        self._pm = QPixmap()
        self.setMinimumHeight(height)
        # 注意：此处不可用 setStyleSheet 设背景色 —— 带 WA_StyledBackground 的父控件在子控件
        # 区域会被样式背景覆盖，导致标题/简介位置出现一块硬边黑底（即用户反馈的「黑色底框」）。
        # 底色由 paintEvent 自行绘制。
        self.setAttribute(Qt.WA_StyledBackground, False)

    def set_image(self, path):
        self._src = path
        self._reload()

    def _reload(self):
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        if self._src and os.path.exists(self._src):
            self._pm = cover_pixmap(self._src, w, h)
        else:
            # 无 fanart 时显示鎏金占位图，避免详情页空白
            self._pm = placeholder_pixmap(w, h, text="影视")

    def resizeEvent(self, e):
        self._reload()
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        if not self._pm.isNull():
            p.drawPixmap(0, 0, self._pm)
        else:
            p.fillRect(r, QColor("#18181b"))
        # 底部柔和压暗：全程半透明（不再压成整块黑底），仅最后 6% 轻微过渡到页面底色以消除接缝
        h = max(r.height(), 1)
        g = QLinearGradient(0, h * 0.30, 0, h)
        g.setColorAt(0.00, QColor(10, 10, 11, 0))
        g.setColorAt(0.45, QColor(10, 10, 11, 52))
        g.setColorAt(0.70, QColor(10, 10, 11, 104))
        g.setColorAt(0.92, QColor(10, 10, 11, 150))
        g.setColorAt(1.00, QColor(17, 17, 19, 255))
        p.fillRect(r, g)
        # 左侧轻压暗（保证标题可读），比底部更弱
        g2 = QLinearGradient(0, 0, r.width() * 0.70, 0)
        g2.setColorAt(0.0, QColor(10, 10, 11, 120))
        g2.setColorAt(0.55, QColor(10, 10, 11, 34))
        g2.setColorAt(1.0, QColor(10, 10, 11, 0))
        p.fillRect(r, g2)
        p.end()


# ---------- 演员头像 ----------
class CastAvatar(QFrame):
    def __init__(self, person, on_click, on_context=None, size=96):
        super().__init__()
        self.person = person
        self.on_click = on_click
        self.on_context = on_context
        # v2.0.1（反馈 4）：卡片宽度按「头像 + 两侧流光」定，有无流光都一样宽，
        # 一排头像的姓名才对得齐。8 = 布局左右各 4px 内边距。
        self.setFixedWidth(size + 2 * GLOW_W + 8)
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)
        img = QLabel()
        # 演职人员头像按性别加流光：女 → 粉、男 → 蓝、未知 → 不显示（保持干净）
        _g = str(person.get("gender") or "").strip().lower()
        _glow = GLOW_FEMALE if _g == "female" else (GLOW_MALE if _g == "male" else None)
        pm = circle_pixmap(person.get("photo_path") or person.get("thumb"), size,
                           glow=_glow, glow_w=GLOW_W if _glow else 0)
        img.setPixmap(pm)
        # ⚠ 控件尺寸**恒按外扩后的画布**定（108），不随有无流光变 —— 否则同一排里
        # 「有流光的头像」比「未知性别」高 12px，姓名/角色会上下错位（第一版就是这样）。
        # 没流光的头像在框内居中，照片直径仍是 size，视觉大小一致。
        img.setAlignment(Qt.AlignCenter)
        img.setFixedSize(size + 2 * GLOW_W, size + 2 * GLOW_W)
        v.addWidget(img, alignment=Qt.AlignHCenter)
        # v2.0.3（反馈 8）：名字按身份着色 —— 女演员粉 / 男演员蓝 / 导演黄 / 未知白。
        # v2.0.5（反馈 10）：用户要求「详细页中演职人员信息也沿用这套逻辑」→ 与卡片完全一致：
        #   **默认灰（CREW_NAME_DIM）→ 收藏才上身份色 → 置顶只加粗**。
        fav = person.get("favorite")
        pin = person.get("pinned")
        _is_dir = is_director_role(person.get("char_role") or person.get("role_type"))
        _nc = crew_name_color(person.get("gender"), _is_dir) if fav else CREW_NAME_DIM
        _nw = "bold" if pin else "normal"
        name = QLabel(person.get("name", ""))
        name.setAlignment(Qt.AlignHCenter)
        name.setStyleSheet(f"font-size:12px;color:{_nc};font-weight:{_nw};")
        name.setToolTip(person.get("name", ""))
        v.addWidget(name)
        role = QLabel(person.get("char_role") or person.get("role_type") or "")
        role.setAlignment(Qt.AlignHCenter)
        role.setStyleSheet("font-size:11px;color:%s;" % CREW_NAME_DIM)
        v.addWidget(role)
        # v1.40.12：让子控件（圆形头像/姓名/角色）上的右键也归到本框的 contextMenuEvent
        # （否则 QLabel 默认 DefaultContextMenu 会把事件吃在自己身上，父框收不到）。
        for _c in self.findChildren(QWidget):
            _c.setContextMenuPolicy(Qt.NoContextMenu)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def mousePressEvent(self, e):
        # 左键单击 → 进入详情（与双击同一动作）
        if e.button() == Qt.LeftButton and self.on_click:
            self.on_click(self.person)

    def mouseDoubleClickEvent(self, e):
        # 双击也进入详情（用户需求：左键单击与双击都进入演员/导演）
        if e.button() == Qt.LeftButton and self.on_click:
            self.on_click(self.person)

    def contextMenuEvent(self, e):
        # 右键 → 弹「输入框 + 演员/导演库实时联想」搜索框；点选/回车即把**本片该位**替换为该人
        # （v1.40.14：不再跳工具界面，而是改变影片内演员/导演信息）。
        if not self.on_context:
            e.ignore()
            return
        _name = (self.person or {}).get("name")
        # v1.46.10：给 parent（主窗）—— 无边框 Dialog 有了属主才不会在任务栏多出一个条目，
        # 也才能稳定地被激活（输入法需要前台窗口）。
        dlg = PersonSearchDialog(initial=_name, old_name=_name,
                                 on_pick=lambda p: self.on_context(self.person, p),
                                 parent=self.window())
        dlg.move_to(e.globalPos())
        dlg.exec()
        e.accept()


# ---------- 右键搜索框（输入框 + 演员/导演库联想，v1.40.13/14） ----------
class ClickOutsideCloser(QObject):
    """无边框对话框「点外面就关」（v1.46.10 反馈 2）。

    原来这个弹层用 `Qt.Popup`：它能自动「点外面关闭」，但 **Popup 窗口在 Windows 上
    不会被激活** —— 输入法要靠前台窗口的输入上下文才能挂上，于是弹层里根本切不了中文
    （只能打英文）。改成真正的 `Qt.Dialog`（可激活、能挂输入法）后，
    「点外面关闭」就得自己实现：在 QApplication 上装事件过滤器，点到面板外就 reject。
    """

    def __init__(self, dlg):
        super().__init__(dlg)
        self._dlg = dlg

    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QEvent.MouseButtonPress and self._dlg.isVisible():
                if not self._dlg.geometry().contains(ev.globalPosition().toPoint()):
                    self._dlg.reject()
        except (RuntimeError, AttributeError):
            return False
        return False


class PersonSearchDialog(QDialog):
    """右键演员/导演头像弹出：输入框 + 跨「演员库 / 导演库」实时联想。

    外观（v1.40.15）：面板无边框、无系统标题栏；标题「替换「XX」」位于正文首行，
    右侧是明确的「放弃修改」按钮（= 取消，不改动本片，等同 Esc / 点击面板外）。

    交互：
    - 顶部输入框每键入即在两库按 name / alias / romaji 子串联想，列表实时刷新；
    - 空输入 → 默认推荐两库作品数最高的若干位；
    - 单击列表项，或在输入框按回车（自动选中当前顶部项）→ 选中该人并回调 on_pick(person_dict)；
    - 列表为空时回车无动作（必须点选联想结果）。

    v1.40.14：点选结果即把**当前影片该位**演员/导演替换为所选人（`on_context(old, new)` →
    HeroView._apply_person_replace → db.replace_media_person + 就地刷新演职人员信息），
    不再跳到「工具」界面。
    """

    def __init__(self, initial=None, old_name=None, on_pick=None, parent=None):
        super().__init__(parent)
        self._on_pick = on_pick
        self._old_name = old_name or ""
        # v1.46.10（反馈 2）：**不能再用 Qt.Popup** —— Popup 窗口在 Windows 上不激活，
        # 输入法挂不上，弹层里切不了中文（用户截图里的「输入框打不出中文」就是这个）。
        # 改成一个**能激活的无边框对话框**：输入法正常、Esc 照旧关闭；
        # 「点面板外面关闭」由 `ClickOutsideCloser` 补回来（原来 Popup 是白送的）。
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self._outside = None
        # 输入法相关：显式打开输入法事件，别让自绘/无边框链路把它关掉
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setWindowTitle(f"替换「{self._old_name}」" if self._old_name else "搜索演员 / 导演")
        self.setMinimumWidth(380)
        self.setMaximumHeight(470)
        # 弹层自身不透明底色（避免离屏/真机透明），不走全局 QWidget 背景规则
        self.setStyleSheet(
            "PersonSearchDialog{background:#18181b;border:1px solid #3f3f46;"
            "border-radius:10px;}"
        )
        self.setAutoFillBackground(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)

        # —— 原顶部关闭栏「融入下方」：标题贴着正文放，右侧是明确的「放弃修改」按钮 ——
        head = QHBoxLayout()
        head.setContentsMargins(1, 0, 1, 0)
        head.setSpacing(8)
        self._title = QLabel(
            f"替换「{self._old_name}」" if self._old_name else "搜索演员 / 导演")
        self._title.setStyleSheet(
            "font-size:13px;font-weight:bold;color:#ecedee;background:transparent;")
        head.addWidget(self._title)
        head.addStretch(1)
        self._cancel_btn = QPushButton("放弃修改")
        self._cancel_btn.setObjectName("Ghost")      # 复用全局次级按钮样式
        self._cancel_btn.setProperty("compact", "1")  # 窄按钮去 padding（见 style.qss）
        self._cancel_btn.setFixedHeight(26)
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setToolTip("不改动本片，直接关闭（Esc）")
        self._cancel_btn.clicked.connect(self.reject)
        head.addWidget(self._cancel_btn)
        lay.addLayout(head)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("输入姓名 / 别名 / 罗马音，自动联想…")
        self._edit.setClearButtonEnabled(True)
        # v1.46.10：确保输入框本身接收输入法事件（中文/日文均可直接输入）
        self._edit.setAttribute(Qt.WA_InputMethodEnabled, True)
        self._edit.setFocusPolicy(Qt.StrongFocus)
        self._edit.setInputMethodHints(Qt.ImhNone)
        lay.addWidget(self._edit)
        self._hint = QLabel("点选即替换本片该位 · 演员库 + 导演库 联想")
        self._hint.setStyleSheet("font-size:11px;color:#a1a1aa;background:transparent;")
        lay.addWidget(self._hint)
        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        lay.addWidget(self._list, 1)
        self._edit.textChanged.connect(self._on_text)
        self._edit.returnPressed.connect(self._on_return)
        self._list.itemClicked.connect(self._on_item_clicked)
        if initial:
            self._edit.setText(initial)
        else:
            self._refresh("")
        # 弹层显示后立即抢焦点，方便直接键入
        QTimer.singleShot(0, self._edit.setFocus)

    # ---------- 显示/关闭：保证能激活（输入法） + 点外面关闭 ----------
    def showEvent(self, e):
        super().showEvent(e)
        # 无边框对话框必须自己抢前台，否则 Windows 不把输入法上下文交给它
        self.raise_()
        self.activateWindow()
        self._edit.setFocus(Qt.OtherFocusReason)
        app = QApplication.instance()
        if app is not None and self._outside is None:
            self._outside = ClickOutsideCloser(self)
            app.installEventFilter(self._outside)

    def done(self, r):
        app = QApplication.instance()
        if app is not None and self._outside is not None:
            app.removeEventFilter(self._outside)
            self._outside = None
        super().done(r)

    def keyPressEvent(self, e):
        # Esc 关闭（Qt.Dialog 默认也支持，这里显式兜住无边框场景）
        if e.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(e)

    @staticmethod
    def _role_label(p):
        return "导演" if (p.get("role_type") or "") == "Director" else "演员"

    def _format(self, p):
        return f"{p.get('name', '')}　（{self._role_label(p)}）· {p.get('works') or 0} 部作品"

    def _refresh(self, kw):
        rows = db.search_people(kw, limit=60)
        self._list.blockSignals(True)
        self._list.clear()
        for p in rows:
            it = QListWidgetItem(self._format(p))
            it.setData(Qt.UserRole, p)
            self._list.addItem(it)
        self._list.blockSignals(False)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._hint.setText(f"联想结果：{self._list.count()} 位（演员库 + 导演库）")

    def _on_text(self, text):
        self._refresh(text)

    def _on_return(self):
        it = self._list.currentItem() or (self._list.item(0) if self._list.count() else None)
        if it is not None:
            self._pick(it.data(Qt.UserRole))

    def _on_item_clicked(self, item):
        self._pick(item.data(Qt.UserRole))

    def _pick(self, person):
        cb = self._on_pick
        self.accept()
        if cb and person:
            cb(person)

    def move_to(self, global_pos):
        """按光标位置放置弹层，并夹紧到屏幕可视区内。"""
        self.adjustSize()
        r = self.rect()
        r.moveTopLeft(global_pos)
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect()
        if avail.isNull():
            self.move(r.topLeft())
            return
        if r.right() > avail.right():
            r.moveRight(avail.right())
        if r.bottom() > avail.bottom():
            r.moveTop(max(avail.top(), global_pos.y() - r.height()))
        if r.left() < avail.left():
            r.moveLeft(avail.left())
        if r.top() < avail.top():
            r.moveTop(avail.top())
        self.setGeometry(r)


# ---------- 详情页 ----------
class HeroView(QScrollArea):
    def __init__(self, media, on_open_actor=None, on_back=None, on_changed=None,
                 on_person_replaced=None, on_open_actors=None):
        super().__init__()
        self.media = media
        self.on_open_actor = on_open_actor
        self.on_back = on_back
        self.on_changed = on_changed
        self.on_person_replaced = on_person_replaced   # (old_person, new_person) → 通知主窗
        # v1.43.0（反馈 6）：「更多 → 查看演员库」。此前该菜单项是空占位
        # （`lambda: self.on_back and None`），点了没有任何反应。
        self.on_open_actors = on_open_actors
        self._cast_box = None
        self._cast_layout = None      # v1.46.10：演职人员信息所在的横向布局（就地重建用）
        self._body_layout = None
        self.setWidgetResizable(True)
        self._build()

    def _build(self):
        m = self.media
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部返回行（v1.37.0 反馈 3）：仅在确实需要返回按钮时才建这一行。
        # 首页右侧详情 on_back=None，原本仍建一个空 topbar（上边距 10px）会露出一条
        # 顶部空白带，看起来像「少了几个像素」。on_back 为 None 时直接不建，让横幅顶到顶端。
        if self.on_back is not None:
            topbar = QWidget()
            tl = QHBoxLayout(topbar)
            tl.setContentsMargins(18, 10, 18, 0)
            back = QPushButton("← 返回")
            back.setObjectName("Ghost")
            back.clicked.connect(self.on_back)
            tl.addWidget(back)
            tl.addStretch(1)
            root.addWidget(topbar)

        # 横幅
        banner = HeroBanner(430)
        fanart = m.get("fanart") or m.get("poster")
        banner.set_image(fanart)
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(28, 0, 28, 22)
        bl.addStretch(1)

        # 操作按钮（v1.19.1 反馈 2：播放 / 收藏 / 评分 / 更多 统一移到「标题上方」）
        bl.addLayout(self._action_row(m))
        # 标题（v1.45.4 反馈 1）：与简介同规则 —— **最多 2 行**，放不下「 ...」，高度锁 2 行。
        # 长番号标题在窄面板会折 3~4 行，把下面的元数据挤走，所以这里也用 ElidedLabel。
        _t = ElidedLabel(m.get("title", ""), max_lines=2, px=34)
        _t.setStyleSheet("color:#ecedee;font-weight:bold;")
        _apply_text_shadow(_t)
        bl.addWidget(_t)
        # 元数据行（流式：窄面板自动换行 —— v1.19.1 反馈 1）
        meta = FlowLayout(spacing=12)
        self._meta = meta          # v1.18.0 反馈 97：评分写回后即时刷新此行
        rating = f"★ {m.get('rating')}" if m.get("rating") else "★ —"
        year = m.get("year") or "—"
        country = f"({m.get('country')})" if m.get("country") else ""
        kind_cn = {"movie": "电影", "tvshow": "剧集", "episode": "分集"}.get(m.get("kind"), "")
        parts = [rating, f"{year}{country}", m.get("genres") or "—"]
        if m.get("runtime"):
            parts.append(m["runtime"])
        if m.get("certification"):
            parts.append(m["certification"])
        if isinstance(m.get("user_rating"), (int, float)):
            parts.append(f"我评 {m['user_rating']:.1f}★")
        for i, t in enumerate(parts):
            meta.addWidget(_label(str(t), 12, False, "#d4d4d8" if i else "#66a9ff", shadow=True))
        meta.addWidget(_label(kind_cn, 12, False, "#d4d4d8", shadow=True))
        meta.addStretch(1)
        bl.addLayout(meta)
        # 简介（v1.45.3 反馈 1）：**最多 2 行**，放不下用「 ...」收尾。
        # 之前按**字数**截断（>220 字才截），窄面板照样折成 6 行 —— 用户截图就是这种情况；
        # 现在按像素折行取前 2 行，且高度固定 2 行，面板不再抖动。
        plot = (m.get("plot") or "（无简介）").strip()
        _pl = ElidedLabel(plot, max_lines=2, px=12)
        _pl.setStyleSheet("color:#d4d4d8;")
        _apply_text_shadow(_pl)
        bl.addWidget(_pl)
        # 徽章
        badges = [b for b in (m.get("quality") or "").split(",") if b]
        if badges:
            bl.addLayout(self._badge_row(badges))

        root.addWidget(banner)

        # 主体
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(28, 18, 28, 24)
        bv.setSpacing(14)
        self._body_layout = bv
        bv.addWidget(self._intro_section(m))
        # v1.46.9 反馈 3：标签行（紧挨「基本信息」，方便一起改）
        bv.addWidget(self._tag_section(m))
        # v1.46.9 反馈 2：extrafanart 剧照横条（没有这个目录时整块不建）
        still_box = self._extrafanart_section(m)
        if still_box is not None:
            bv.addWidget(still_box)
        # v1.46.10（反馈 1）：演职人员信息已并入 `_intro_section`（贴「基本信息」右侧），
        # 这里不再整块独占一行；文件信息仍在底部。
        bv.addWidget(self._file_section(m))
        parts_box = self._parts_section(m)
        if parts_box is not None:
            bv.addWidget(parts_box)
        bv.addWidget(self._links_section(m))
        bv.addStretch(1)
        root.addWidget(body, 1)

        self.setWidget(content)

    def _intro_section(self, m):
        """海报 + 基本信息 + 演职人员信息（v1.46.10 反馈 1：三栏并排，左图右文）。

        此前「演职人员信息」独占一整行（海报/基本信息的**右侧**大片空白没人用），
        用户要求把它挪到「基本信息」旁边。现在：
            [海报 150] [基本信息 230] [演职人员信息 —— 占满剩余宽度]
        演员行本来就是横向可滚的 `QScrollArea`，放进窄栏后自动按需出横向滚动条，
        窄面板（首页右侧详情栏）下也不会撑出页面级横向滚动条。
        文件信息仍留在主体底部（`_build` 里单独一行）。
        """
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)
        # v1.46.10：右键替换演员后要**就地重建**这一块，故记住它所在的布局
        self._cast_layout = h

        poster = QLabel()
        pm = cover_pixmap(m.get("poster") or m.get("fanart"), 150, 225)
        if pm.isNull():
            pm = placeholder_pixmap(150, 225, text=(m.get("title") or "影")[:1] or "影")
        poster.setPixmap(pm)
        poster.setFixedSize(150, 225)
        poster.setStyleSheet("border-radius:4px;background:#18181b;")
        h.addWidget(poster)

        # 基本信息：**定宽**容器。不能像原来那样给 stretch —— 它有 stretch 时会把
        # 右侧全部宽度吃掉，演员栏就没地方站了；而定宽后 `_kv` 的值列本身是
        # `QSizePolicy.Ignored`（可取用剩余宽度），不会因为收窄而塌成 0。
        facts_host = QWidget()
        facts_host.setFixedWidth(230)
        facts = QVBoxLayout(facts_host)
        facts.setContentsMargins(0, 0, 0, 0)
        facts.setSpacing(4)
        facts.addWidget(_label("基本信息", 15, True))
        rows = [
            ("类型", mm.kind_cn(m.get("kind")) or "—"),
            ("年份", str(m.get("year")) if m.get("year") else "—"),
            ("分级", m.get("certification") or "—"),
            ("时长", m.get("runtime") or "—"),
            ("画质", m.get("quality") or "—"),
            ("制片", m.get("studio") or "—"),
            ("媒体库", m.get("library") or "—"),
            ("系列", m.get("collection") or "—"),
        ]
        for k, v in rows:
            facts.addWidget(self._kv(k, v))
        facts.addStretch(1)
        h.addWidget(facts_host)

        # 演职人员信息（原 `_build` 里的独立一行）：占满右侧剩余宽度，顶部对齐
        self._cast_box = self._cast_section(m)
        h.addWidget(self._cast_box, 1, Qt.AlignTop)
        return box

    # ---------- 标签行（v1.46.9 反馈 3） ----------
    def _tag_values(self, m=None):
        raw = (m or self.media).get("tags") or ""
        return [t.strip() for t in str(raw).split(",") if t.strip()]

    def _tag_section(self, m):
        """标签行：现有标签（芯片） + 「＋」（添加）/「－」（删除）两个按钮。"""
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(_label("标签", 15, True))
        add = compact_button("＋", 28, 24, "添加标签")
        rm = compact_button("－", 28, 24, "删除标签")
        add.clicked.connect(self._add_tag)
        rm.clicked.connect(lambda: self._remove_tag_menu(rm))
        head.addWidget(add)
        head.addWidget(rm)
        head.addStretch(1)
        v.addLayout(head)

        tags = self._tag_values(m)
        host = QWidget()
        flow = FlowLayout(host, spacing=8)
        if tags:
            for t in tags:
                flow.addWidget(self._tag_chip(t))
        else:
            flow.addWidget(_label("（还没有标签，点「＋」添加）", 12, False, "#71717a"))
        v.addWidget(host)
        return box

    def _tag_chip(self, text):
        chip = QLabel(text)
        chip.setStyleSheet(
            "background:#27272a;color:#d4d4d8;border:1px solid #3f3f46;"
            "border-radius:10px;padding:2px 10px;font-size:12px;")
        chip.setToolTip(f"标签：{text}")
        return chip

    @staticmethod
    def _split_tags(text):
        """用户输入的标签串 → 列表。逗号 / 中文逗号 / 顿号 / 分号 / 空白都当分隔符。"""
        import re as _re
        return [t for t in _re.split(r"[,，、;；\s]+", str(text or "")) if t.strip()]

    def _add_tag(self):
        cur = self._tag_values()
        text, ok = QInputDialog.getText(
            self, "添加标签", "标签（多个用逗号分隔）：", QLineEdit.Normal, "")
        if not ok or not str(text).strip():
            return
        new = [t for t in self._split_tags(text) if t not in cur]
        if not new:
            return
        self._apply_tags(cur + new)

    def _remove_tag_menu(self, anchor):
        cur = self._tag_values()
        menu = QMenu(self)
        if not cur:
            a = QAction("（暂无标签）", self)
            a.setEnabled(False)
            menu.addAction(a)
        for t in cur:
            act = menu.addAction(f"删除「{t}」")
            act.triggered.connect(lambda _=False, tag=t: self._apply_tags(
                [x for x in self._tag_values() if x != tag]))
        if cur:
            menu.addSeparator()
            clr = menu.addAction("清空全部标签")
            clr.triggered.connect(lambda: self._apply_tags([]))
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _apply_tags(self, tags):
        """落库 + 写回 nfo（`<tag>`），然后重建本页让标签行立刻反映结果。"""
        tags = [str(t).strip() for t in (tags or []) if str(t).strip()]
        mid = self.media.get("id")
        if mid is not None:
            self.media["tags"] = db.set_media_tags(mid, tags)     # 归一化后的真值
        else:
            self.media["tags"] = ",".join(tags)
        # 写回 nfo：失败不弹框（有的影片本来就没 nfo），库里已经生效，界面照常刷新
        try:
            nfo_mod.write_tags(self.media.get("nfo_path"), tags)
        except Exception:
            pass
        self._rebuild_page()
        if self.on_changed:
            self.on_changed()

    def _rebuild_page(self):
        """就地重建详情页（保留竖向滚动位置）。`_reload` 与标签增删共用。"""
        bar = self.verticalScrollBar()
        pos = bar.value()
        old = self.takeWidget()      # 先摘掉旧内容，避免 setWidget 时残留
        if old is not None:
            old.deleteLater()
        self._build()
        bar.setValue(pos)

    # ---------- 剧照（extrafanart，v1.46.9 反馈 2） ----------
    def _extrafanart_section(self, m):
        """片源目录 `extrafanart/` 里的剧照，做成可左右滑动的横条。"""
        stills = find_extrafanart(m)
        if not stills:
            return None
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(_label(f"剧照（{len(stills)}）", 15, True))
        head.addStretch(1)
        prev = compact_button("‹", 28, 24, "向左翻")
        nxt = compact_button("›", 28, 24, "向右翻")
        head.addWidget(prev)
        head.addWidget(nxt)
        v.addLayout(head)

        host = QWidget()
        hl = QHBoxLayout(host)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        for i, p in enumerate(stills):
            hl.addWidget(self._still_cell(p, i, stills))
        hl.addStretch(1)

        strip = StillStrip()
        strip.setWidget(host)
        strip.setFixedHeight(_STILL_H + 18)      # 图高 + 横向滚动条
        prev.clicked.connect(lambda: strip.page(-1))
        nxt.clicked.connect(lambda: strip.page(1))
        v.addWidget(strip)
        return box

    def _still_cell(self, path, idx, paths):
        lab = QLabel()
        pm = cover_pixmap(path, _STILL_W, _STILL_H)
        if pm.isNull():
            pm = placeholder_pixmap(_STILL_W, _STILL_H, text="剧")
        lab.setPixmap(pm)
        lab.setFixedSize(_STILL_W, _STILL_H)
        lab.setCursor(Qt.PointingHandCursor)
        lab.setToolTip(os.path.basename(path))
        lab.setStyleSheet("border-radius:4px;background:#18181b;")
        lab.mousePressEvent = lambda e, i=idx: self._open_still(paths, i)
        return lab

    def _open_still(self, paths, idx):
        dlg = StillViewer(paths, idx, self)
        dlg.exec()

    def _badge_row(self, badges):
        row = QHBoxLayout()
        row.setSpacing(6)
        order = ["4K", "1080P", "720P", "HDR10", "杜比视界", "Atmos", "DTS:X", "TrueHD"]
        # v2.0.0：改 HeroUI 亮色 chip —— 底用中高亮度色 + 深字，暗色面板上才读得清
        color = {"4K": "#66a9ff", "HDR10": "#f5a524", "杜比视界": "#9353d3",
                 "Atmos": "#338ef7", "DTS:X": "#17c964", "TrueHD": "#17c964"}
        for b in order:
            if b in badges:
                lab = QLabel(b)
                c = color.get(b, "#71717a")
                lab.setStyleSheet(
                    f"background:{c};color:#0a0a0b;font-weight:bold;font-size:11px;"
                    "border-radius:6px;padding:2px 8px;")
                row.addWidget(lab)
        row.addStretch(1)
        return row

    def _action_row(self, m):
        # v1.19.1 反馈 1：改用流式布局 —— 窄面板下按钮自动换行，不再撑出横向滚动条
        row = FlowLayout(spacing=10)
        play = QPushButton("播放")
        play.setObjectName("Primary")
        play.setMinimumWidth(120)
        play.clicked.connect(self._play)
        row.addWidget(play)

        # v1.20.0：收藏 / 评分 / 刷新 / 更多 改用 #HeroAct（深底 + 鎏金描边 + 亮字）。
        # 原先复用 #Ghost，叠在明亮的 fanart 剧照上几乎看不见（用户反馈「融入背景」）。
        fav = QPushButton("已收藏" if m.get("favorite") else "收藏")
        fav.setObjectName("HeroAct")
        fav.clicked.connect(self._toggle_fav)
        self._fav_btn = fav
        row.addWidget(fav)

        rate = QPushButton(self._rate_label(m))
        rate.setObjectName("HeroAct")
        rate.clicked.connect(self._rate)
        self._rate_btn = rate
        row.addWidget(rate)

        # v1.20.0 新增：只针对本片重读 nfo 并刷新（不重扫整个媒体库）
        refresh = QPushButton("刷新")
        refresh.setObjectName("HeroAct")
        refresh.setToolTip("重新读取本片对应的 nfo 文件，并刷新此页信息（保留收藏 / 评分 / 播放次数）")
        refresh.clicked.connect(self._refresh)
        self._refresh_btn = refresh
        row.addWidget(refresh)

        more = QPushButton("更多")
        more.setObjectName("HeroAct")
        more.clicked.connect(lambda: self._more_menu(more))
        row.addWidget(more)
        row.addStretch(1)
        return row

    def _more_menu(self, anchor):
        menu = QMenu(self)
        a1 = QAction("在资源管理器中显示", self)
        a1.triggered.connect(lambda: player_mod.reveal_in_explorer(self.media.get("file_path", "")))
        a2 = QAction("复制文件路径", self)
        a2.triggered.connect(self._copy_path)
        a3 = QAction("查看演员库", self)
        # v1.43.0（反馈 6）：这里原来是 `lambda: self.on_back and None` —— **纯占位**，
        # 点了什么都不会发生（用户截图反馈「没有反应」）。现在接到主窗的演员库页。
        a3.triggered.connect(self._open_actor_lib)
        menu.addAction(a1); menu.addAction(a2); menu.addAction(a3)
        # v1.43.4（真机 app.log 抓到）：**先抓住顶层窗口再 exec**。
        # 点「查看演员库」会 `go()` 重建页面 → 本 HeroView 在 menu.exec() 收尾前就被
        # deleteLater 销毁，之后再 `self.window()` 就是 libshiboken 的
        # 「Internal C++ object already deleted」RuntimeError。
        _win = self.window()
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        # 用**类**访问（不用 self）：此时 self 可能已被 go() 销毁，走实例访问有风险
        HeroView._repaint_after_menu(_win)

    @staticmethod
    def _repaint_after_menu(win=None):
        """菜单关闭后强制整窗重绘（v1.43.1 反馈 3；v1.43.4 加空值/失效兜底）。"""
        try:
            if win is None:
                return
            if hasattr(win, "_repaint_shell"):
                win._repaint_shell()
            else:
                win.update()
            win.repaint()
        except Exception:
            # 顶层窗口若也已被销毁，忽略即可 —— 不该为了一次重绘把异常抛给主循环
            pass

    def _open_actor_lib(self):
        """v1.43.0（反馈 6）：「查看演员库」—— 导航到主窗的演员库页。"""
        if self.on_open_actors:
            self.on_open_actors()

    def _copy_path(self):
        QApplication.clipboard().setText(self.media.get("file_path") or "")

    def _play(self):
        res = player_mod.launch(self.media.get("file_path", ""))
        if res["ok"] and self.media.get("id") is not None:
            db.mark_played(self.media["id"])
            self.media["play_count"] = (self.media.get("play_count") or 0) + 1
        elif not res["ok"]:
            QMessageBox.warning(self, "播放失败", res["msg"])

    def _toggle_fav(self):
        if self.media.get("id") is None:
            return
        new = db.toggle_favorite(self.media["id"])
        self.media["favorite"] = new
        self._fav_btn.setText("已收藏" if new else "收藏")
        if self.on_changed:
            self.on_changed()

    # ---------- 用户评分（写库 + 回写 nfo） ----------
    def _rate_label(self, m):
        v = m.get("user_rating")
        return f"评分 {v:.1f}" if isinstance(v, (int, float)) else "评分"

    def _rate(self):
        if self.media.get("id") is None:
            return
        dlg = RateDialog(self, self.media.get("user_rating"))
        if dlg.exec() != QDialog.Accepted:
            return
        val = dlg.value
        db.set_user_rating(self.media["id"], val)
        self.media["user_rating"] = val
        nfo_mod.write_user_rating(self.media.get("nfo_path"), val)
        self._rate_btn.setText(self._rate_label(self.media))
        self._refresh_meta()       # v1.18.0 反馈 97：即时刷新顶部「我评 X.X★」
        if self.on_changed:
            self.on_changed()

    def _refresh_meta(self):
        """v1.18.0（反馈 97）：用户评分写回后即时刷新详情页顶部元数据行（含「我评 X.X★」）。"""
        meta = getattr(self, "_meta", None)
        if meta is None:
            return
        while meta.count():
            item = meta.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        m = self.media
        rating = f"★ {m.get('rating')}" if m.get("rating") else "★ —"
        year = m.get("year") or "—"
        country = f"({m.get('country')})" if m.get("country") else ""
        kind_cn = {"movie": "电影", "tvshow": "剧集", "episode": "分集"}.get(m.get("kind"), "")
        parts = [rating, f"{year}{country}", m.get("genres") or "—"]
        if m.get("runtime"):
            parts.append(m["runtime"])
        if m.get("certification"):
            parts.append(m["certification"])
        if isinstance(m.get("user_rating"), (int, float)):
            parts.append(f"我评 {m['user_rating']:.1f}★")
        for i, t in enumerate(parts):
            meta.addWidget(_label(str(t), 12, False, "#d4d4d8" if i else "#66a9ff", shadow=True))
        meta.addWidget(_label(kind_cn, 12, False, "#d4d4d8", shadow=True))
        meta.addStretch(1)

    # ---------- 单片 nfo 重扫 / 刷新（v1.20.0） ----------
    def _reload(self):
        """按 id 重新从数据库读取本片数据，并重建整个详情界面（不重新解析 nfo）。"""
        mid = self.media.get("id")
        if mid is None:
            return
        row = db.get_media(mid)
        if not row:
            return
        self.media = row
        self._rebuild_page()

    def _refresh(self):
        """「刷新」：只重新读取本片对应的 nfo 并回写数据库，然后重建本页。

        不重扫整个媒体库（数万部时整库重扫很慢）；用户态字段（收藏 / 播放次数）不受影响，
        nfo 未写 `<userrating>` 时库中已有的评分也会保留（见 `scanner.rescan_one`）。
        """
        if self.media.get("id") is None:
            return
        res = scanner_mod.rescan_one(self.media["id"])
        if not res.get("ok"):
            QMessageBox.warning(self, "刷新失败", res.get("msg") or "未知错误")
            return
        self._reload()
        if self.on_changed:
            self.on_changed()

    def _cast_section(self, m):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_label("演职人员信息", 15, True))
        cast = db.get_cast(m["id"]) if m.get("id") else []
        if not cast:
            v.addWidget(_label("（无演员信息，nfo 中未包含 actor 节点）", 12, False, "#a1a1aa"))
            return box
        row_host = QWidget()
        rl = QHBoxLayout(row_host)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        for p in cast:
            rl.addWidget(CastAvatar(p, self.on_open_actor, on_context=self._apply_person_replace))
        rl.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(row_host)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(170)
        scroll.setStyleSheet("background:transparent;")
        v.addWidget(scroll)
        return box

    def _apply_person_replace(self, old_person, new_person):
        """右键搜索框点选某人 → 把**本片**该位演员/导演替换为该人（v1.40.14）。

        只改这一部作品的关联（media_people），不动 people 表、也不动该人的其它作品；
        改完整块「演职人员信息」就地重建，随后通知主窗（状态栏提示 + 刷统计）。
        """
        mid = (self.media or {}).get("id")
        old_id = (old_person or {}).get("id")
        new_id = (new_person or {}).get("id")
        if not mid or old_id is None or new_id is None or old_id == new_id:
            return
        res = db.replace_media_person(mid, old_id, new_id)
        if not res.get("ok"):
            return
        # 延迟一拍再重建 UI：本函数由右键搜索框（嵌套事件循环）内的点选触发，此刻若同步销毁
        # 含该头像的旧块，会在「控件自身的事件处理尚未返回」时析构它 → 用 singleShot(0) 等
        # 对话框 exec 返回、控制权回到主事件循环后再刷新，避免在自身事件里删除自身。
        QTimer.singleShot(0, self._refresh_cast)
        if self.on_person_replaced:
            try:
                self.on_person_replaced(old_person, new_person)
            except Exception:
                pass
        if self.on_changed:
            try:
                self.on_changed()          # 刷统计/侧栏计数（与收藏/评分同一口径）
            except Exception:
                pass

    def _refresh_cast(self):
        """就地重建「演职人员信息」区（右键替换后即时刷新，不整页重建）。

        v1.46.10：这一块从「主体竖向布局里的独立一行」挪进了 `_intro_section` 的横向布局，
        所以优先用 `_cast_layout`，取不到再退回 `_body_layout`（防止旧引用/异常路径）。
        """
        try:
            lay = self._cast_layout or self._body_layout
            old = self._cast_box
            if lay is None or old is None:
                return
            idx = lay.indexOf(old)
            new_box = self._cast_section(self.media)
            if idx < 0:
                lay.addWidget(new_box)
            else:
                lay.insertWidget(idx, new_box)
            lay.removeWidget(old)
            old.setParent(None)
            old.deleteLater()
            self._cast_box = new_box
        except RuntimeError:
            # 页面已被切走/销毁（延迟刷新时 C++ 侧可能已析构）——忽略即可
            pass

    def _file_section(self, m):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addWidget(_label("文件信息", 15, True))
        fp = m.get("file_path") or "—"
        v.addWidget(self._kv("文件路径", fp, copyable=True))
        v.addWidget(self._kv("文件大小", mm.human_size(m.get("file_size"))))
        v.addWidget(self._kv("添加日期", m.get("added_date") or "—"))
        if m.get("studio"):
            v.addWidget(self._kv("制片公司", m["studio"]))
        return box

    def _kv(self, k, val, copyable=False):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        kl = _label(k, 12, False, "#a1a1aa")
        kl.setFixedWidth(72)
        h.addWidget(kl)
        vl = _label(str(val), 12, False, "#d4d4d8", wrap=True)
        # v1.19.1 反馈 1：值可能是不含空格的长串（文件路径 / 长片商名），wordWrap 无法折行，
        # 会把自身最小宽度撑得很大、逼出横向滚动条。允许被压缩（配合 wrap 对含空格文本换行），
        # 超长路径由右侧「复制」按钮完整取用。
        vl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        vl.setMinimumWidth(0)
        h.addWidget(vl, 1)
        if copyable:
            cp = compact_button("复制", 52, 24, "复制该字段到剪贴板")
            cp.clicked.connect(lambda: QApplication.clipboard().setText(str(val)))
            h.addWidget(cp)
        return w

    def _links_section(self, m):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        if not m.get("tmdb_id"):
            return box
        v.addWidget(_label("相关链接", 15, True))
        link = QLabel(f'<a style="color:#66a9ff;" href="https://www.themoviedb.org/movie/{m["tmdb_id"]}">TMDB</a>')
        link.setOpenExternalLinks(True)
        v.addWidget(link)
        return box

    def _parts_section(self, m):
        """选集（CD 连续序号归组后的分片）：可点击播放其中任意一片。

        顶层影片（parent_id 为空）的选集 = 自己 + 其分片；从分片点进来的
        （parent_id 非空）也能看到同属一个选集的全部片源，并可单独播放。
        """
        mid = m.get("id")
        if mid is None:
            return None
        parent_id = m.get("parent_id")
        if parent_id is not None:
            rep = db.get_media(parent_id)
            children = db.children_of(parent_id)
            parts = ([rep] if rep else []) + children
        else:
            children = db.children_of(mid)
            parts = [m] + children
        if len(parts) < 2:
            return None
        parts.sort(key=lambda x: (x.get("episode") or 0, x.get("id") or 0))
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(_label("选集", 15, True))
        # v1.19.1 反馈 1：改用流式布局，缩略卡随面板宽度自动换行（原先固定 4 列会撑出横向滚动条）
        grid_host = QWidget()
        grid = FlowLayout(grid_host, spacing=10)
        for i, p in enumerate(parts):
            grid.addWidget(self._part_cell(p, i + 1))
        v.addWidget(grid_host)
        return box

    def _part_cell(self, p, idx):
        """选集里的一个片源缩略卡（点击播放该文件）。"""
        w = QFrame()
        w.setCursor(Qt.PointingHandCursor)
        w.setFixedSize(140, 178)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        img = QLabel()
        img.setAlignment(Qt.AlignCenter)
        thumb = _part_thumb_path(p)          # v1.18.0 反馈 95：同目录 <番号>-thumb.jpg 横版缩略图
        if thumb:
            pm = QPixmap(thumb)
            if not pm.isNull():
                pm = pm.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            pm = cover_pixmap(p.get("poster") or p.get("fanart"), 140, 140)
        if pm.isNull():
            pm = placeholder_pixmap(140, 140, text="CD")
        img.setPixmap(pm)
        img.setFixedSize(140, 140)
        img.setStyleSheet("border-radius:4px;background:#18181b;")
        v.addWidget(img)
        cd = p.get("episode") or idx
        lab = _label(f"CD{cd}", 12, True, "#ecedee")
        lab.setAlignment(Qt.AlignCenter)
        v.addWidget(lab)
        w.mousePressEvent = lambda e, pp=p: self._play_part(pp)
        return w

    def _play_part(self, p):
        """播放选集里的某一片（按文件定位，不依赖详情页主文件）。"""
        res = player_mod.launch(p.get("file_path", ""))
        if res["ok"] and p.get("id") is not None:
            db.mark_played(p["id"])
            cur = db.get_media(self.media.get("id") or -1)
            if cur:
                self.media = cur
        elif not res["ok"]:
            QMessageBox.warning(self, "播放失败", res["msg"])


# ---------- 打分对话框（保留 1 位小数） ----------
class RateDialog(QDialog):
    """给当前影片打分（0–10，1 位小数）。

    v1.46.14（用户截图反馈两条）：
      ① 「窗口有点错位」—— 数值框右侧那块**上下微调按钮**在暗色主题下只有一条竖分隔线、
         **一个箭头都画不出来**（QSS 里 `::up-arrow/::down-arrow` 的着色彩根本没生效），
         看着就像一块贴歪了的深色面板把圆角盖住了。当时只能 `NoButtons` 把整块去掉。
      ② 「左右都留空，压缩窗口宽度」—— 原来数值框 `setFixedWidth(140)`、按钮行前面
         又塞了 `addStretch(1)`，而窗口宽度是被那行最长提示文字撑开的（实测 302px），
         于是数值框右边空 130px、按钮左边空 82px。现在：数值框**撑满整行**、
         「清除」贴左（它是次要/破坏性动作，与「取消/确定」分开更安全），
         提示文字去掉「「清除」可去掉已有评分」这半句（挪进按钮 tooltip），
         宽度由内容收紧到 ~216px。

    v2.0.2（反馈 3）：箭头**回来了**。v2.0.1 用 `glyphs.py` 把 chevron 画成 PNG、QSS 走
    `image:` 之后，`::up-arrow/::down-arrow` 在真机上已经能正常显示（其它数值框实测可见），
    所以这里恢复 `UpDownArrows` —— 用户要求「上下按钮改为和请求间隔那个数值框一样的样式」，
    那个就是同一套 QSS，恢复默认即可对上。顺带把 `valueChanged` 到 `_ok` 的路径也保持
    原样（键盘 ↑↓ / 滚轮 / 点按钮三者等价，都只改 0.1）。
    """

    def __init__(self, parent, current):
        super().__init__(parent)
        self.setWindowTitle("我的评分")
        self.value = current
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 12)
        v.setSpacing(10)

        self.spin = QDoubleSpinBox()
        self.spin.setRange(0.0, 10.0)
        self.spin.setSingleStep(0.1)
        self.spin.setDecimals(1)
        self.spin.setValue(float(current) if isinstance(current, (int, float)) else 0.0)
        self.spin.setSuffix(" 分")
        # v2.0.2（反馈 3）：恢复上下微调按钮（v2.0.1 起箭头走 PNG `image:`，真机可见）。
        # ⚠ 这里**必须**显式写成 UpDownArrows：老代码留的是 NoButtons，改 QSS 也救不回来。
        self.spin.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
        # v2.0.2：按钮区宽 18px + 输入框 padding 11px，默认 minimumSizeHint 会把
        # 「10.0 分」压成「10.0 …」→ 给足最小宽度（其它数值框走 cfg.SPIN_MIN_W 同一口径）。
        self.spin.setMinimumWidth(cfg.SPIN_MIN_W)
        self.spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.spin.setFocus()                 # 打开即聚焦，直接键入分数
        self.spin.selectAll()
        v.addWidget(self.spin)
        hint = QLabel("范围 0–10，保留 1 位小数。")
        hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        v.addWidget(hint)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        clear = QPushButton("清除")
        clear.setObjectName("Ghost")
        clear.setToolTip("清除已有评分（等于不给分）")
        clear.clicked.connect(self._clear)
        ok = QPushButton("确定")
        ok.setObjectName("Primary")
        ok.clicked.connect(self._ok)          # v1.19.0 反馈 100：回写当前分值再 accept
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        btns.addWidget(clear)
        btns.addSpacing(24)                  # 「清除」与「取消/确定」之间留一段，避免误点
        btns.addStretch(1)                   # 空白只留在这两段按钮之间（左右都不留空）
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)
        self.adjustSize()

    def _ok(self):
        """v1.19.0 反馈 100：点「确定」必须把 spinbox 当前值回写 self.value，
        否则 HeroView._rate 取到的还是原值（原空时写成 None 即清除），评分永远不显示。"""
        self.value = self.spin.value()
        self.accept()

    def _clear(self):
        self.value = None
        self.accept()
