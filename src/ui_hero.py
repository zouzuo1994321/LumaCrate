# -*- coding: utf-8 -*-
"""Emby 风格详情页：全宽 fanart 横幅 + 元数据 + 操作按钮 + 圆形演员行 + 文件信息。"""
import os

from PySide6.QtCore import Qt, QRectF, QRect, QPoint, QSize, QTimer
from PySide6.QtGui import (QPixmap, QPainter, QColor, QLinearGradient, QFont,
                           QPainterPath, QAction)
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea,
    QFrame, QMenu, QMessageBox, QApplication, QDialog, QDoubleSpinBox,
    QGridLayout, QLayout, QSizePolicy, QLineEdit, QListWidget,
    QListWidgetItem,
)

import database as db
import media_meta as mm
import player as player_mod
import nfo_parser as nfo_mod
import scanner as scanner_mod


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


def circle_pixmap(path, size, bg="#2a221c"):
    """圆形头像；无图时返回占位圆。"""
    src = QPixmap(path) if (path and os.path.exists(path)) else QPixmap()
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    clip = QPainterPath()
    clip.addEllipse(QRectF(0, 0, size, size))
    p.setClipPath(clip)
    if not src.isNull():
        s = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        p.drawPixmap((size - s.width()) // 2, (size - s.height()) // 2, s)
    else:
        p.fillRect(0, 0, size, size, QColor(bg))
        p.setPen(QColor("#9b8e7a"))
        f = QFont(); f.setPointSize(int(size / 3)); p.setFont(f)
        p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "人")
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


def placeholder_pixmap(w, h, text="影", bg="#241d18"):
    """无图时生成占位图：渐变底 + 首字，避免详情/卡片出现空白。"""
    pm = QPixmap(w, h)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0.0, QColor("#2e241c"))
    g.setColorAt(1.0, QColor("#15110e"))
    p.fillRect(0, 0, w, h, g)
    p.setPen(QColor("#8c6f2f"))
    p.drawRect(0, 0, w - 1, h - 1)
    p.setPen(QColor("#d4af37"))
    f = QFont()
    f.setBold(True)
    f.setPointSize(max(12, int(min(w, h) / 4)))
    p.setFont(f)
    ch = (text or "影").strip()[:1].upper() or "影"
    p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, ch)
    p.end()
    return pm


def _label(text, size=12, bold=False, color="#e8e0d4", wrap=False, shadow=False):
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
            p.fillRect(r, QColor("#1c1714"))
        # 底部柔和压暗：全程半透明（不再压成整块黑底），仅最后 6% 轻微过渡到页面底色以消除接缝
        h = max(r.height(), 1)
        g = QLinearGradient(0, h * 0.30, 0, h)
        g.setColorAt(0.00, QColor(12, 10, 9, 0))
        g.setColorAt(0.45, QColor(12, 10, 9, 52))
        g.setColorAt(0.70, QColor(12, 10, 9, 104))
        g.setColorAt(0.92, QColor(12, 10, 9, 150))
        g.setColorAt(1.00, QColor(15, 13, 12, 255))
        p.fillRect(r, g)
        # 左侧轻压暗（保证标题可读），比底部更弱
        g2 = QLinearGradient(0, 0, r.width() * 0.70, 0)
        g2.setColorAt(0.0, QColor(12, 10, 9, 120))
        g2.setColorAt(0.55, QColor(12, 10, 9, 34))
        g2.setColorAt(1.0, QColor(12, 10, 9, 0))
        p.fillRect(r, g2)
        p.end()


# ---------- 演员头像 ----------
class CastAvatar(QFrame):
    def __init__(self, person, on_click, on_context=None, size=96):
        super().__init__()
        self.person = person
        self.on_click = on_click
        self.on_context = on_context
        self.setFixedWidth(size + 16)
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)
        img = QLabel()
        img.setPixmap(circle_pixmap(person.get("photo_path") or person.get("thumb"), size))
        img.setFixedSize(size, size)
        v.addWidget(img, alignment=Qt.AlignHCenter)
        # v1.37.0（反馈 1）：收藏 → 金色；置顶 → 加粗；收藏+置顶 → 金色加粗。
        fav = person.get("favorite")
        pin = person.get("pinned")
        if fav and pin:
            _nc, _nw = "#d4af37", "bold"
        elif fav:
            _nc, _nw = "#d4af37", "normal"
        elif pin:
            _nc, _nw = "#e8e0d4", "bold"
        else:
            _nc, _nw = "#e8e0d4", "normal"
        name = QLabel(person.get("name", ""))
        name.setAlignment(Qt.AlignHCenter)
        name.setStyleSheet(f"font-size:12px;color:{_nc};font-weight:{_nw};")
        name.setToolTip(person.get("name", ""))
        v.addWidget(name)
        role = QLabel(person.get("char_role") or person.get("role_type") or "")
        role.setAlignment(Qt.AlignHCenter)
        role.setStyleSheet("font-size:11px;color:#9b8e7a;")
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
        dlg = PersonSearchDialog(initial=_name, old_name=_name,
                                  on_pick=lambda p: self.on_context(self.person, p))
        dlg.move_to(e.globalPos())
        dlg.exec()
        e.accept()


# ---------- 右键搜索框（输入框 + 演员/导演库联想，v1.40.13/14） ----------
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
        # v1.40.15：无边框统一面板 —— 干掉原生标题栏（那条「替换「XX」 … ×」），
        # 标题融入面板正文首行，并把「关闭」做成正文里明确的「放弃修改」按钮。
        # （仅 Qt.Popup 在本机仍会带一条系统标题栏，故显式再叠 FramelessWindowHint。）
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowTitle(f"替换「{self._old_name}」" if self._old_name else "搜索演员 / 导演")
        self.setMinimumWidth(380)
        self.setMaximumHeight(470)
        # 弹层自身不透明底色（避免离屏/真机透明），不走全局 QWidget 背景规则
        self.setStyleSheet(
            "PersonSearchDialog{background:#1e1a16;border:1px solid #3a332b;"
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
            "font-size:13px;font-weight:bold;color:#e8e0d4;background:transparent;")
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
        lay.addWidget(self._edit)
        self._hint = QLabel("点选即替换本片该位 · 演员库 + 导演库 联想")
        self._hint.setStyleSheet("font-size:11px;color:#9b8e7a;background:transparent;")
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
                 on_person_replaced=None):
        super().__init__()
        self.media = media
        self.on_open_actor = on_open_actor
        self.on_back = on_back
        self.on_changed = on_changed
        self.on_person_replaced = on_person_replaced   # (old_person, new_person) → 通知主窗
        self._cast_box = None
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
        # 标题（v1.19.1 反馈 1：改为自动换行，窄面板不再撑出横向滚动条）
        bl.addWidget(_label(m.get("title", ""), 34, True, "#f3d9a0", wrap=True, shadow=True))
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
            meta.addWidget(_label(str(t), 12, False, "#d9cfbf" if i else "#d4af37", shadow=True))
        meta.addWidget(_label(kind_cn, 12, False, "#d9cfbf", shadow=True))
        meta.addStretch(1)
        bl.addLayout(meta)
        # 简介
        plot = (m.get("plot") or "（无简介）").strip().replace("\n", " ")
        if len(plot) > 220:
            plot = plot[:220] + " ..."
        bl.addWidget(_label(plot, 12, False, "#c9bdaa", wrap=True, shadow=True))
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
        self._cast_box = self._cast_section(m)   # v1.40.14：右键替换后就地重建这一块
        bv.addWidget(self._cast_box)
        bv.addWidget(self._file_section(m))
        parts_box = self._parts_section(m)
        if parts_box is not None:
            bv.addWidget(parts_box)
        bv.addWidget(self._links_section(m))
        bv.addStretch(1)
        root.addWidget(body, 1)

        self.setWidget(content)

    def _intro_section(self, m):
        """海报 + 基本信息快速概览（左图右文，Emby 风格）。"""
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)

        poster = QLabel()
        pm = cover_pixmap(m.get("poster") or m.get("fanart"), 150, 225)
        if pm.isNull():
            pm = placeholder_pixmap(150, 225, text=(m.get("title") or "影")[:1] or "影")
        poster.setPixmap(pm)
        poster.setFixedSize(150, 225)
        poster.setStyleSheet("border-radius:4px;background:#15110e;")
        h.addWidget(poster)

        facts = QVBoxLayout()
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
        h.addLayout(facts, 1)
        return box

    def _badge_row(self, badges):
        row = QHBoxLayout()
        row.setSpacing(6)
        order = ["4K", "1080P", "720P", "HDR10", "杜比视界", "Atmos", "DTS:X", "TrueHD"]
        color = {"4K": "#d4af37", "HDR10": "#c0392b", "杜比视界": "#8e44ad",
                 "Atmos": "#2980b9", "DTS:X": "#16a085", "TrueHD": "#16a085"}
        for b in order:
            if b in badges:
                lab = QLabel(b)
                c = color.get(b, "#7f8c8d")
                lab.setStyleSheet(
                    f"background:{c};color:#14110f;font-weight:bold;font-size:11px;"
                    "border-radius:3px;padding:2px 8px;")
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
        a3.triggered.connect(lambda: self.on_back and None)
        menu.addAction(a1); menu.addAction(a2); menu.addAction(a3)
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

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
            meta.addWidget(_label(str(t), 12, False, "#d9cfbf" if i else "#d4af37", shadow=True))
        meta.addWidget(_label(kind_cn, 12, False, "#d9cfbf", shadow=True))
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
        bar = self.verticalScrollBar()
        pos = bar.value()
        old = self.takeWidget()      # 先摘掉旧内容，避免 setWidget 时残留
        if old is not None:
            old.deleteLater()
        self._build()
        bar.setValue(pos)

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
            v.addWidget(_label("（无演员信息，nfo 中未包含 actor 节点）", 12, False, "#9b8e7a"))
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
        """就地重建「演职人员信息」区（右键替换后即时刷新，不整页重建）。"""
        try:
            lay = self._body_layout
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
        kl = _label(k, 12, False, "#9b8e7a")
        kl.setFixedWidth(72)
        h.addWidget(kl)
        vl = _label(str(val), 12, False, "#d9cfbf", wrap=True)
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
        link = QLabel(f'<a style="color:#d4af37;" href="https://www.themoviedb.org/movie/{m["tmdb_id"]}">TMDB</a>')
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
        img.setStyleSheet("border-radius:4px;background:#15110e;")
        v.addWidget(img)
        cd = p.get("episode") or idx
        lab = _label(f"CD{cd}", 12, True, "#e8e0d4")
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
        self.spin.setFixedWidth(140)
        self.spin.setFocus()                 # 打开即聚焦，直接键入分数
        self.spin.selectAll()
        v.addWidget(self.spin)
        hint = QLabel("范围 0–10，保留 1 位小数；「清除」可去掉已有评分。")
        hint.setStyleSheet("color:#9b8e7a;font-size:11px;")
        v.addWidget(hint)

        btns = QHBoxLayout()
        clear = QPushButton("清除")
        clear.setObjectName("Ghost")
        clear.clicked.connect(self._clear)
        ok = QPushButton("确定")
        ok.setObjectName("Primary")
        ok.clicked.connect(self._ok)          # v1.19.0 反馈 100：回写当前分值再 accept
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(clear)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)

    def _ok(self):
        """v1.19.0 反馈 100：点「确定」必须把 spinbox 当前值回写 self.value，
        否则 HeroView._rate 取到的还是原值（原空时写成 None 即清除），评分永远不显示。"""
        self.value = self.spin.value()
        self.accept()

    def _clear(self):
        self.value = None
        self.accept()
