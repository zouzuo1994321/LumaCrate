# -*- coding: utf-8 -*-
"""
首页：列表 + 详情 模式（Emby 风格）
===================================
左侧可排序 / 可搜索的表格，列由设置「首页显示列」动态决定（参考 tinyMediaManager 的列选择器），
支持按住表头拖动调整列顺序（顺序持久化到 settings.json）。
鼠标悬停在某一行上会弹出该作品的缩略图预览卡片。
右侧详情面板：fanart 横幅 + 海报 + 基本信息 + 画质徽章 + 简介 + 文件路径。
底部状态栏：已选 N 项 · 总大小。
"""
import os
import time

from PySide6.QtCore import Qt, QTimer, QEvent, Signal, QPoint
from PySide6.QtGui import (QCursor, QGuiApplication, QPainter, QColor, QPen,
                           QPainterPath)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QPushButton,
    QDialog, QScrollArea, QListWidget, QListWidgetItem, QFrame,
    QAbstractItemView, QApplication, QMenu,
)

import database as db
import media_meta as mm
import config as cfg
from ui_hero import HeroView, cover_pixmap, placeholder_pixmap


def _busy(progress=None, text=""):
    """v1.46.8（反馈）：把首页列表的载入进度上报给状态栏进度条。

    为什么必须补：首页一次性读 **4.8 万条**（`search_media(limit=100000)`）再分 244 批
    填表，全程只更新自己的 `self.status` 文字，**从来没调用过 `set_busy`** →
    用户看到「正在载入列表… 16200 / 48708」在跑，右边那个进度条却一直是空槽，
    就会认为「载入 / 缓存中切朱红的高亮没了」。
    延迟 import 是为了避开与 `main_window` 的循环依赖（ui_home 被 main_window 导入）。
    """
    try:
        import main_window as _mw
        _mw.set_busy(progress, text)
    except Exception:
        pass


# 列 -> 排序键
_SORT_KEYS = {
    "title":       lambda m: (m.get("title") or ""),
    "actors":      lambda m: (m.get("actors_text") or ""),
    "year":        lambda m: m.get("year") or 0,
    "premiere":    lambda m: m.get("premiere") or "",
    "added_date":  lambda m: m.get("added_date") or "",
    "rating":      lambda m: m.get("rating") if isinstance(m.get("rating"), (int, float)) else -1,
    "user_rating": lambda m: m.get("user_rating") if isinstance(m.get("user_rating"), (int, float)) else -1,
    "certification": lambda m: m.get("certification") or "",
    "kind":        lambda m: mm.kind_cn(m.get("kind")) or "",
    "collection":  lambda m: m.get("collection") or "",
    "runtime_min": lambda m: int(mm.runtime_minutes(m.get("runtime")) or 0),
    "runtime":     lambda m: m.get("runtime") or "",
    "quality":     lambda m: m.get("quality") or "",
    "file_size":   lambda m: m.get("file_size") or 0,
    "studio":      lambda m: m.get("studio") or "",
    "language":    lambda m: m.get("country") or "",
    "filename":    lambda m: os.path.basename(m.get("file_path") or "") or "",
    "path":        lambda m: m.get("file_path") or "",
    "library":     lambda m: m.get("library") or "",
    "play_count":  lambda m: m.get("play_count") or 0,
    "favorite":    lambda m: m.get("favorite") or 0,
    "plot":        lambda m: m.get("plot") or "",
}

# 各列默认宽度（用户可拖动表头分隔线再调，也可拖动表头整体换位）
_COL_WIDTH = {
    "title": 360, "actors": 180, "year": 70, "premiere": 100, "added_date": 100,
    "rating": 70, "user_rating": 82, "certification": 130, "kind": 70,
    "collection": 130, "runtime_min": 92, "runtime": 92, "quality": 140,
    "file_size": 110, "studio": 140, "language": 100, "filename": 220,
    "path": 320, "library": 110, "play_count": 80, "favorite": 80, "plot": 260,
}


def row_media(table, row):
    """取某一行绑定的 media 字典（列顺序可变，故逐列查找 UserRole）。

    v2.0.8：表格改成**视口懒填**后，屏幕外的行没有 QTableWidgetItem ——
    这时按行号回退到表格持有的 `_media_view`（与 `_view` 同一份列表）。
    没有这层回退，Ctrl+A 全选 / 批量导出 / 批量删除 会拿到一堆 None。
    """
    if row is None or row < 0:
        return None
    for c in range(table.columnCount()):
        it = table.item(row, c)
        if it is not None:
            m = it.data(Qt.UserRole)
            if isinstance(m, dict):
                return m
    view = getattr(table, "_media_view", None)
    if view is not None and 0 <= row < len(view):
        return view[row]
    return None


# ---------- v2.0.7（反馈 3）：表头「左漏斗（筛选）+ 右三角（排序）」 ----------
#: 能按「数值比较」筛的列（其余列一律按「包含文本」筛）
_NUM_COLS = frozenset(("rating", "user_rating", "play_count", "year",
                       "file_size", "runtime_min"))


def _draw_funnel(p, cx, cy, size, color, filled):
    """画一枚漏斗（宽口 → 收腰 → 细颈）。

    ⚠ 形状得**一眼能认出是漏斗**，否则会和右边的排序三角混成「两个小三角」：
    上沿保持满宽走前 1/3 高度，再陡收到 22% 宽的颈，颈占下半段。
    """
    w, h = size * 0.94, size
    x0, y0 = cx - w / 2.0, cy - h / 2.0
    neck_w = w * 0.11          # 半宽
    mouth_h = h * 0.58         # 收腰止于这个高度
    path = QPainterPath()
    path.moveTo(x0, y0)
    path.lineTo(x0 + w, y0)
    path.lineTo(cx + neck_w, y0 + mouth_h)
    path.lineTo(cx + neck_w, y0 + h)
    path.lineTo(cx - neck_w, y0 + h)
    path.lineTo(cx - neck_w, y0 + mouth_h)
    path.closeSubpath()
    if filled:
        p.fillPath(path, QColor(color))
    else:
        p.setPen(QPen(QColor(color), 1.35))
        p.drawPath(path)


def _draw_tri(p, cx, cy, size, color, up=True, filled=False):
    """画一枚排序三角：升序朝上、降序朝下。"""
    s = size * 0.46
    path = QPainterPath()
    if up:
        path.moveTo(cx - s, cy + s * 0.80)
        path.lineTo(cx + s, cy + s * 0.80)
        path.lineTo(cx, cy - s * 0.86)
    else:
        path.moveTo(cx - s, cy - s * 0.80)
        path.lineTo(cx + s, cy - s * 0.80)
        path.lineTo(cx, cy + s * 0.86)
    path.closeSubpath()
    if filled:
        p.fillPath(path, QColor(color))
    else:
        p.setPen(QPen(QColor(color), 1.35))
        p.drawPath(path)


class FilterHeaderView(QHeaderView):
    """带「左漏斗 / 右三角」的表头（v2.0.7 反馈 3）。

    为什么自绘而不是往上叠 QToolButton：表头会随**列宽拖动 / 列换位 / 横向滚动**
    一直在动位置，叠上去的按钮得手工同步几何，任何一处跟不上就错位；自绘 + 自己
    判点击位置最稳，也不额外占控件。

    点击分区（`_zone_at`）：
      · 距列左边 ≤ PAD+ICON+HIT → 漏斗 → `filterClicked`
      · 距列右边 ≤ PAD+ICON+HIT → 三角 → `sortClicked`（正序 / 逆序）
      · 其它 → 交回默认实现（原来的「点表头整列排序」和「拖动换位」都还在）
    列窄于 `MIN_W` 时**不画也不响应**（画上去只会压住列名）。
    """

    ICON = 13
    PAD = 7
    HIT = 6
    MIN_W = 68

    filterClicked = Signal(int)      # logical index
    sortClicked = Signal(int)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self._hover = (-1, "")       # (logicalIndex, "funnel"/"tri")
        self._hover_section = -1     # 鼠标所在的整列（v2.0.8 反馈 3：图标只在悬停列显示）
        self.sort_col = -1           # 当前排序列（logical），-1 = 未排序
        self.sort_asc = True
        # 由 HomeListView 注入：logical -> 列 key / 列 key -> 是否已筛选
        self.key_of = None
        self.has_filter = None

    # ---------- 几何 ----------
    def _zones(self, idx):
        """返回 ((漏斗 x0, x1), (三角 x0, x1))；列太窄或不在可视区返回 None。"""
        if idx < 0 or idx >= self.count():
            return None
        left = self.sectionViewportPosition(idx)
        w = self.sectionSize(idx)
        if w < self.MIN_W or left + w <= 0:
            return None
        f1 = left + self.PAD + self.ICON + self.HIT
        t0 = left + w - self.PAD - self.ICON - self.HIT
        return ((left, f1), (t0, left + w))

    def _zone_at(self, pos):
        idx = self.logicalIndexAt(pos)
        z = self._zones(idx)
        if z is None:
            return (-1, "")
        (f0, f1), (t0, t1) = z
        x = pos.x()
        if f0 <= x <= f1:
            return (idx, "funnel")
        if t0 <= x <= t1:
            return (idx, "tri")
        return (-1, "")

    @staticmethod
    def _accent():
        try:
            a = (cfg.get_settings().appearance or {}).get("accent")
            return str(a) if a else "#e4587c"
        except Exception:
            return "#e4587c"

    def _filter_active(self, idx):
        try:
            key = self.key_of(idx) if self.key_of else None
            return bool(key and self.has_filter and self.has_filter(key))
        except Exception:
            return False

    # ---------- 绘制 ----------
    def paintSection(self, painter, rect, logicalIndex):
        super().paintSection(painter, rect, logicalIndex)
        z = self._zones(logicalIndex)
        if z is None:
            return
        # v2.0.8（反馈 3）：图标**只在鼠标停在这一列时**才画。
        # 用户原话：「列表顶部 筛选和排序 图标，只有鼠标到了列表顶部的那一列才显示」——
        # 满屏都是漏斗和三角太吵。唯一例外：**这一列确实有筛选**时，漏斗常驻
        # （否则用户完全看不出「现在列表是筛过的」，会以为数据丢了）。
        hov = logicalIndex == self._hover_section
        active = self._filter_active(logicalIndex)
        if not hov and not active:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        cy = rect.center().y()
        # 漏斗：已筛选 → 实心强调色（常驻）；否则悬停时描边亮白
        hov_f = self._hover == (logicalIndex, "funnel")
        fcol = self._accent() if active else ("#ecedee" if hov_f else "#a1a1aa")
        _draw_funnel(painter, rect.left() + self.PAD + self.ICON / 2.0, cy,
                     self.ICON, fcol, filled=active)
        # 三角：只随悬停出现；当前排序列 → 强调色实心且朝上/朝下
        if hov:
            here = logicalIndex == self.sort_col
            hov_t = self._hover == (logicalIndex, "tri")
            tcol = self._accent() if here else ("#ecedee" if hov_t else "#a1a1aa")
            _draw_tri(painter, rect.right() - self.PAD - self.ICON / 2.0 - 1, cy,
                      self.ICON, tcol, up=self.sort_asc, filled=here)
        painter.restore()

    # ---------- 交互 ----------
    def _repaint_section(self, idx):
        if 0 <= idx < self.count():
            try:
                self.updateSection(idx)
            except RuntimeError:
                pass

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        zone = self._zone_at(pos)
        sec = self.logicalIndexAt(pos)
        if sec != self._hover_section:
            old = self._hover_section
            self._hover_section = sec
            self._repaint_section(old)
            self._repaint_section(sec)
        if zone != self._hover:
            old_idx = self._hover[0]
            self._hover = zone
            self._repaint_section(old_idx)
            on_icon = bool(zone[1])
            self.setCursor(Qt.PointingHandCursor if on_icon else Qt.ArrowCursor)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self._hover != (-1, "") or self._hover_section != -1:
            idx = self._hover[0]
            old = self._hover_section
            self._hover = (-1, "")
            self._hover_section = -1
            self._repaint_section(idx)
            self._repaint_section(old)
            self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            idx, zone = self._zone_at(e.position().toPoint())
            if zone == "funnel":
                self.filterClicked.emit(idx)
                return                       # 不调 super：别触发「整列排序」
            if zone == "tri":
                self.sortClicked.emit(idx)
                return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        # 图标区按下后松手不能落回默认实现（否则会额外发一次 sectionClicked）
        if e.button() == Qt.LeftButton:
            idx, zone = self._zone_at(e.position().toPoint())
            if zone:
                return
        super().mouseReleaseEvent(e)


class ColumnFilterPopup(QFrame):
    """点表头漏斗弹出的小面板（v2.0.7 反馈 3）。

    只做一件事：问清「这一列要留下哪些行」。三种形态按列自动选：
      · 文本列 → 一个输入框（包含匹配，不区分大小写）；
      · 数值列（评分 / 年份 / 观看次数 / 体积 / 时长）→ 比较符「= ≥ ≤」+ 数值；
      · 枚举列（收藏、类型）→ 一排可点的胶囊，点哪个选哪个。
    用 `Qt.Popup` 而不是普通对话框：点面板外面 / 按 Esc 自动关，和系统菜单一致。
    """

    applied = Signal(str, object)     # (列 key, spec dict 或 None=清除)

    def __init__(self, key, label, spec=None, options=None, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("ColFilter")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._key = key
        self._mode = ("eq" if options is not None
                      else ("num" if key in _NUM_COLS else "text"))
        spec = dict(spec or {})
        self._chips = []
        self._op = str(spec.get("op") or ">=")
        self._eq = str(spec.get("value") or "")
        self.setStyleSheet(
            "QFrame#ColFilter{background:#18181b;border:1px solid #3f3f46;"
            "border-radius:8px;}"
            "QLabel{background:transparent;color:#ecedee;font-size:12px;}"
            "QLabel#ColFilterHint{color:#8b8b93;font-size:11px;}"
            "QPushButton#Chip{background:transparent;border:1px solid #3f3f46;"
            "border-radius:11px;padding:3px 10px;color:#d4d4d8;font-size:12px;}"
            "QPushButton#Chip:hover{border-color:#71717a;color:#fafafa;}"
            "QPushButton#Chip:checked{background:rgba(228,88,124,0.22);"
            "border-color:#e4587c;color:#ffffff;}"
            "QPushButton#Mini{background:rgba(255,255,255,0.06);"
            "border:1px solid #3f3f46;border-radius:6px;padding:4px 12px;"
            "color:#ecedee;font-size:12px;}"
            "QPushButton#Mini:hover{background:rgba(255,255,255,0.12);}"
            "QPushButton#MiniGo{background:#e4587c;border:1px solid #e4587c;"
            "border-radius:6px;padding:4px 12px;color:#ffffff;font-size:12px;"
            "font-weight:bold;}"
            "QPushButton#MiniGo:hover{background:#ef6f92;}")
        self.setMinimumWidth(248)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(7)
        head = QLabel("筛选 · %s" % label)
        head.setStyleSheet("font-size:12px;font-weight:bold;color:#fafafa;")
        v.addWidget(head)

        self.edit = None
        if self._mode == "eq":
            row = QHBoxLayout()
            row.setSpacing(6)
            for text, val in (options or []):
                b = QPushButton(text)
                b.setObjectName("Chip")
                b.setCheckable(True)
                b.setCursor(Qt.PointingHandCursor)
                b.setChecked(str(val) == self._eq)
                b.clicked.connect(lambda _c, vv=str(val): self._set_eq(vv))
                row.addWidget(b)
                self._chips.append((b, str(val)))
            row.addStretch(1)
            v.addLayout(row)
        else:
            if self._mode == "num":
                row = QHBoxLayout()
                row.setSpacing(6)
                for text, val in (("=", "="), ("≥", ">="), ("≤", "<=")):
                    b = QPushButton(text)
                    b.setObjectName("Chip")
                    b.setCheckable(True)
                    b.setCursor(Qt.PointingHandCursor)
                    b.setFixedWidth(34)
                    b.setChecked(val == self._op)
                    b.clicked.connect(lambda _c, vv=val: self._set_op(vv))
                    row.addWidget(b)
                    self._chips.append((b, val))
                row.addStretch(1)
                v.addLayout(row)
            self.edit = QLineEdit()
            self.edit.setText(str(spec.get("value") or ""))
            self.edit.setPlaceholderText("数值，例如 2020 / 7.5" if self._mode == "num"
                                         else "包含这个文字即可（留空 = 不筛选）")
            self.edit.returnPressed.connect(self._apply)
            v.addWidget(self.edit)

        btns = QHBoxLayout()
        btns.setSpacing(6)
        btns.addStretch(1)
        clear = QPushButton("清除")
        clear.setObjectName("Mini")
        clear.setCursor(Qt.PointingHandCursor)
        clear.clicked.connect(lambda: self._emit(None))
        btns.addWidget(clear)
        ok = QPushButton("确定")
        ok.setObjectName("MiniGo")
        ok.setCursor(Qt.PointingHandCursor)
        ok.clicked.connect(self._apply)
        btns.addWidget(ok)
        v.addLayout(btns)
        self.adjustSize()

    # ---------- 选择 ----------
    def _set_op(self, val):
        self._op = val
        for b, vv in self._chips:
            if vv in ("=", ">=", "<="):
                b.setChecked(vv == val)

    def _set_eq(self, val):
        self._eq = val
        for b, vv in self._chips:
            b.setChecked(vv == val)

    def spec(self):
        """把面板上的选择折成一条筛选条件；空值返回 None（= 清除）。"""
        if self._mode == "eq":
            return {"mode": "eq", "value": self._eq} if self._eq != "" else None
        text = self.edit.text().strip() if self.edit is not None else ""
        if not text:
            return None
        if self._mode == "num":
            try:
                float(text)
            except ValueError:
                return None
            return {"mode": "num", "op": self._op, "value": text}
        return {"mode": "text", "value": text}

    def _apply(self):
        self._emit(self.spec())

    def _emit(self, spec):
        try:
            self.applied.emit(self._key, spec)
        finally:
            self.close()
            self.deleteLater()

    def showEvent(self, e):
        super().showEvent(e)
        if self.edit is not None:
            self.edit.setFocus()
            self.edit.selectAll()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(e)


class HoverPreview(QFrame):
    """鼠标悬停在列表行上时弹出的缩略图预览卡片（不抢焦点、不接收鼠标事件）。"""

    CARD_W = 248
    IMG_H = 306

    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setObjectName("HoverCard")
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedWidth(self.CARD_W)

        v = QVBoxLayout(self)
        v.setContentsMargins(9, 9, 9, 9)
        v.setSpacing(6)
        self.img = QLabel()
        self.img.setFixedSize(self.CARD_W - 18, self.IMG_H)
        self.img.setAlignment(Qt.AlignCenter)
        self.img.setStyleSheet("background:#0a0a0b;border-radius:6px;")
        v.addWidget(self.img, alignment=Qt.AlignHCenter)

        self.title = QLabel()
        self.title.setObjectName("HoverTitle")
        self.title.setWordWrap(True)
        v.addWidget(self.title)

        self.sub = QLabel()
        self.sub.setObjectName("HoverSub")
        self.sub.setWordWrap(True)
        v.addWidget(self.sub)

        self.info = QLabel()
        self.info.setObjectName("HoverInfo")
        self.info.setWordWrap(True)
        v.addWidget(self.info)

    def set_media(self, m):
        w, h = self.CARD_W - 18, self.IMG_H
        pm = cover_pixmap(m.get("poster") or m.get("thumb") or m.get("fanart"), w, h)
        if pm.isNull():
            pm = placeholder_pixmap(w, h, text=(m.get("title") or "影")[:1] or "影")
        self.img.setPixmap(pm)
        self.title.setText(m.get("title") or "（无标题）")

        parts = []
        r = m.get("rating")
        if isinstance(r, (int, float)):
            parts.append(f"★ {r:.1f}")
        if m.get("year"):
            parts.append(str(m["year"]))
        if m.get("runtime"):
            parts.append(str(m["runtime"]))
        if m.get("quality"):
            parts.append(str(m["quality"]))
        self.sub.setText("   ·   ".join(parts))

        rows = []
        if m.get("actors_text"):
            rows.append("演员：" + m["actors_text"])
        if m.get("genres"):
            rows.append("类型：" + str(m["genres"]))
        if m.get("studio"):
            rows.append("制片：" + str(m["studio"]))
        if m.get("premiere"):
            rows.append("上映：" + str(m["premiere"]))
        self.info.setText("\n".join(rows))
        self.info.setVisible(bool(rows))
        self.adjustSize()

    def popup_at(self, pos):
        """在光标附近弹出，自动避让屏幕边缘。"""
        self.adjustSize()
        w, h = self.width(), self.height()
        x, y = pos.x() + 18, pos.y() + 20
        screen = None
        try:
            screen = QGuiApplication.screenAt(pos)
        except Exception:
            screen = None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is not None:
            av = screen.availableGeometry()
            if x + w > av.right():
                x = pos.x() - w - 18
            if y + h > av.bottom():
                y = max(av.top() + 6, av.bottom() - h - 6)
            x = max(av.left() + 6, min(x, max(av.left() + 6, av.right() - w - 6)))
            y = max(av.top() + 6, y)
        self.move(x, y)
        self.show()
        self.raise_()


class HomeListView(QWidget):
    def __init__(self, on_open_actor=None, on_open_media=None, on_hover_media=None,
                 on_changed=None, on_person_replaced=None, on_open_actors=None,
                 on_bulk_action=None):
        super().__init__()
        self.on_open_actor = on_open_actor
        self.on_open_media = on_open_media
        self.on_hover_media = on_hover_media     # 悬停/选中 → 通知主窗口换磨砂底衬
        self.on_changed = on_changed             # 详情页编辑（收藏/评分）→ 通知主窗口（刷统计/侧栏）
        self.on_person_replaced = on_person_replaced   # v1.40.14：右键搜索点选 → 替换本片演员/导演
        # v1.43.1（反馈 4）：「更多 → 查看演员库」。**首页右侧详情也是 HeroView**，
        # v1.43.0 只给详情页那处传了回调，首页这处漏了 → 用户点菜单仍然没反应。
        self.on_open_actors = on_open_actors
        # v1.46.11（反馈 1）：列表右键批量操作。真正的动作（播放 / 打开文件夹 /
        # 刷新 / 删索引 / 删文件）都在主窗口里做 —— 那里有 _toast、统计刷新与
        # 确认框，页面本身只管「哪几行被选中」与「把菜单画出来」。
        self.on_bulk_action = on_bulk_action
        self._detail_mid = None                  # 当前详情面板展示的作品 id（v1.21.1 反馈 4）
        self._media = []
        self._view = []
        self._sort_col = -1
        self._sort_asc = True
        self._cols = list(cfg.get_settings().home_columns)
        # v2.0.7（反馈 3）：每列筛选条件 {列 key: {"mode":…, "value":…}}，与排序一样落盘
        self._filters = dict(cfg.get_settings().home_filters or {})
        self._filter_popup = None
        self._reordering = False
        self._width_user = False        # 用户是否手动拖过列宽（未拖过则不落盘，避免把默认/拉伸值当用户设置）
        self._split_restored = False
        self._build()

    # ---------- 构建 ----------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 8)
        root.setSpacing(8)

        # 顶部：首页模块快捷筛选 chips（受设置控制）+ 列设置按钮
        s = cfg.get_settings()
        top = QWidget()
        tl = QHBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)
        self._chip_defs = [("recent", "最近添加"), ("favorites", "我的收藏"), ("collections", "合集")]
        # v1.25.0（反馈 6）：这三个按钮原来复用 #Ghost，点下去只有一点点极淡的描边，
        # 用户反馈「不知道是不是点了这个」。改成 checkable + 独立的 #Seg 样式，
        # 选中就是实心强调底 + 亮描边 + 加粗白字；再点一次同一项 = 取消筛选。
        self._chip_btns = {}
        self._active_chip = None
        for key, label in self._chip_defs:
            if s.home_modules.get(key):
                b = QPushButton(label)
                b.setObjectName("Seg")
                b.setCheckable(True)
                b.setToolTip(f"只看「{label}」的作品（再点一次取消）")
                b.clicked.connect(lambda _c, k=key: self._click_chip(k))
                tl.addWidget(b)
                self._chip_btns[key] = b
        tl.addStretch(1)
        col_btn = QPushButton("列设置")
        col_btn.setObjectName("Ghost")
        col_btn.setToolTip("勾选显示列，并可拖动列表调整列顺序（也可直接拖动表头换位）")
        col_btn.clicked.connect(self._open_col_settings)
        tl.addWidget(col_btn)
        root.addWidget(top)

        # 分栏：左表 / 右详情
        self.split = QSplitter(Qt.Horizontal)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)

        self.search = QLineEdit()
        self.search.setPlaceholderText("在列表中搜索片名…")
        # v1.21.0：搜索**去抖** —— textChanged 每敲一个字符就整表过滤 + 重填，
        # 几万行时表现为「打字一顿一顿」；改为停手 250ms 后才真正过滤。
        self.search.textChanged.connect(self._on_search_changed)
        lv.addWidget(self.search)

        self.table = QTableWidget(0, max(len(self._cols), 1))
        # v2.0.7（反馈 3）：换成自绘表头（左漏斗 / 右三角）。**必须先装表头再
        # `_rebuild_headers()`** —— 后者是按 `horizontalHeader()` 现取现配的
        # （可拖动、可点、sectionMoved 连接），装晚了这些设置会落在被丢弃的旧表头上。
        hdr = FilterHeaderView(Qt.Horizontal, self.table)
        hdr.key_of = self._col_key
        hdr.has_filter = lambda k: k in self._filters
        hdr.setDefaultAlignment(Qt.AlignCenter)
        hdr.filterClicked.connect(self._open_column_filter)
        hdr.sortClicked.connect(self._sort)
        self.table.setHorizontalHeader(hdr)
        self._header = hdr
        self._rebuild_headers()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.table.horizontalHeader().sectionClicked.connect(self._sort)
        self.table.horizontalHeader().sectionResized.connect(self._on_section_resized)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.table.itemDoubleClicked.connect(self._on_open)
        self.table.cellEntered.connect(self._on_cell_entered)
        # v1.46.11（反馈 1）：列表右键菜单（单选 / 多选都走同一个构建器）
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.viewport().installEventFilter(self)
        self.table.verticalScrollBar().valueChanged.connect(self._hide_preview)
        # v2.0.8（反馈 4）：滚动就补填新露出的一段（`_fill_window` 自己判重，没变化直接返回）
        self.table.verticalScrollBar().valueChanged.connect(lambda *_: self._fill_window())
        self.table.horizontalScrollBar().valueChanged.connect(self._hide_preview)
        lv.addWidget(self.table, 1)

        # 悬停缩略图预览
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._show_preview)
        self._preview = HoverPreview(self)
        self._preview.hide()

        # 列顺序变更去抖（拖动结束后落盘）
        self._order_timer = QTimer(self)
        self._order_timer.setSingleShot(True)
        self._order_timer.timeout.connect(self._commit_column_order)

        # 列宽变更去抖（拖动分隔线结束后落盘）
        self._width_timer = QTimer(self)
        self._width_timer.setSingleShot(True)
        self._width_timer.timeout.connect(self._commit_width)

        # 分栏位置变更去抖（拖动结束后落盘）
        self._split_timer = QTimer(self)
        self._split_timer.setSingleShot(True)
        self._split_timer.timeout.connect(self._commit_split)

        # 搜索去抖（v1.21.0，见 self.search 处说明）
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_filter_now)

        # 磨砂底衬去抖（v1.21.0）：换一次底衬要整窗重算模糊，鼠标快速扫过列表时
        # 逐行触发就会一路卡；停在同一行 130ms 才真正换。
        self._backdrop_timer = QTimer(self)
        self._backdrop_timer.setSingleShot(True)
        self._backdrop_timer.timeout.connect(self._apply_backdrop)

        # 右详情（v1.37.0 反馈 4）：加高亮色边框。普通 QWidget 不画 QSS 边框，
        # 故开 WA_StyledBackground；背景保持透明，不要盖掉磨砂玻璃。
        self.detail_host = QWidget()
        self.detail_host.setObjectName("DetailHost")
        self.detail_host.setAttribute(Qt.WA_StyledBackground, True)
        dv = QVBoxLayout(self.detail_host)
        dv.setContentsMargins(0, 0, 0, 0)
        dv.addWidget(QLabel("（在左侧选择一项查看详情）"))

        self.split.addWidget(left)
        self.split.addWidget(self.detail_host)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        # 恢复上次的分栏位置（列表 / 详情）；新建时为默认比例
        sizes = cfg.get_settings().home_split
        if len(sizes) == 2 and sizes[0] > 0 and sizes[1] > 0:
            self.split.setSizes([int(sizes[0]), int(sizes[1])])
        self.split.splitterMoved.connect(self._on_split_moved)
        root.addWidget(self.split, 1)

        # 底部状态
        self.status = QLabel("已选 0 项")
        self.status.setObjectName("HomeStatus")
        root.addWidget(self.status)

        self._load()
        self._restore_sort()      # 启动时恢复上次排序

    def _rebuild_headers(self):
        label_map = dict(cfg.HOME_COLUMNS)
        labels = [label_map.get(k, k) for k in self._cols]
        self.table.setColumnCount(len(self._cols))
        self.table.setHorizontalHeaderLabels(labels)
        hdr = self.table.horizontalHeader()
        hdr.setSectionsMovable(True)
        hdr.setSectionsClickable(True)
        try:
            hdr.sectionMoved.disconnect()
        except Exception:
            pass
        hdr.sectionMoved.connect(self._on_section_moved)
        widths = cfg.get_settings().home_column_widths or {}
        has_custom = bool(widths)
        for c, key in enumerate(self._cols):
            saved_w = widths.get(key)
            self.table.setColumnWidth(c, int(saved_w) if saved_w else _COL_WIDTH.get(key, 120))
        # 用户未自定义列宽：最后一列拉伸填满，默认美观；
        # 一旦用户拖过列宽（home_column_widths 非空），改用精确宽度、关闭拉伸，避免污染列宽
        hdr.setStretchLastSection(not has_custom)
        # v2.0.7（反馈 3）：换列 / 改列宽后，把「当前排序列 + 升降」再喂给表头，
        # 否则三角会停在旧列上（排序没变、箭头却指错列）。
        if isinstance(hdr, FilterHeaderView):
            hdr.sort_col = self._sort_col
            hdr.sort_asc = self._sort_asc
            hdr.viewport().update()

    def _col_key(self, logical):
        """表头回调用：logical 列号 → 列 key（越界 / 换列途中一律 None）。"""
        try:
            if 0 <= logical < len(self._cols):
                return self._cols[logical]
        except Exception:
            pass
        return None

    # ---------- 列拖动排序 ----------
    def _on_section_moved(self, logical, old_visual, new_visual):
        if self._reordering:
            return
        self._order_timer.start(120)

    def _commit_column_order(self):
        hdr = self.table.horizontalHeader()
        n = min(hdr.count(), len(self._cols))
        try:
            order = [self._cols[hdr.logicalIndex(v)] for v in range(n)]
        except Exception:
            return
        if order == self._cols:
            return
        self._cols = order
        self._sort_col = -1
        cfg.get_settings().set_home_columns(order)
        # 复位表头（使逻辑列 == 视觉列），再按新顺序重排数据
        self._reordering = True
        try:
            self.table.setColumnCount(0)
            self._rebuild_headers()
        finally:
            self._reordering = False
        self._apply_view()
        self._restore_sort()      # 换列后若排序列仍在，保持排序

    # ---------- 列宽变更 ----------
    def _on_section_resized(self, logical, old, new):
        if self._reordering:
            return
        self._width_user = True
        # v2.0.8：构造期 `table` 一进布局，最后一列的「拉伸」就会触发一次
        # sectionResized —— 那一刻 `_width_timer` 还没建（它建在 `_build` 更后面），
        # 直接 `.start()` 就是未捕获的 AttributeError（只影响「列宽去抖落盘」，
        # 所以从前一直没被发现，但 app.log 里会留一条）。用 getattr 兜住。
        _t = getattr(self, "_width_timer", None)
        if _t is not None:
            _t.start(150)

    def _commit_width(self):
        hdr = self.table.horizontalHeader()
        widths = {}
        n = hdr.count()
        for c in range(n):
            li = hdr.logicalIndex(c)
            if 0 <= li < len(self._cols):
                widths[self._cols[li]] = hdr.sectionSize(c)
        if widths:
            cfg.get_settings().set_home_column_widths(widths)

    # ---------- 分栏位置持久化 ----------
    def _on_split_moved(self, pos, index):
        self._split_timer.start(120)

    def _commit_split(self):
        sizes = self.split.sizes()
        if len(sizes) == 2 and sizes[0] > 0 and sizes[1] > 0:
            cfg.get_settings().set_home_split(sizes)

    # ---------- 排序持久化 ----------
    def _restore_sort(self):
        sort = cfg.get_settings().home_sort or {}
        key = sort.get("key")
        if not key or key not in self._cols:
            return
        idx = self._cols.index(key)
        self._sort_col = idx
        self._sort_asc = bool(sort.get("asc", True))
        keyf = _SORT_KEYS.get(key, lambda m: (m.get("title") or ""))
        try:
            self._view = sorted(self._view, key=keyf, reverse=not self._sort_asc)
        except TypeError:
            self._view = sorted(self._view, key=lambda m: str(keyf(m)), reverse=not self._sort_asc)
        self._apply_view()
        if getattr(self, "_header", None) is not None:
            self._header.sort_col = self._sort_col
            self._header.sort_asc = self._sort_asc
            self._header.viewport().update()

    # ---------- 数据 ----------
    def live_refresh(self):
        """扫描进行中就地刷新：重新拉取列表数据，让新索引的影片立刻出现在首页（v1.22.0 反馈 4）。

        由 MainWindow._on_scan_live 在扫描进度信号触发时调用（已做节流）。

        v1.46.13（反馈 2）：**按实测耗时自适应节流**。`_load()` 是同步读全库
        （`search_media(limit=100000)`，4.8 万片实测 1~2 秒），如果固定 1.2s 就触发，
        GUI 线程会被这条重载一直占满 —— 用户看到的反而是「扫描期间界面卡着不动」。
        现在记下这次耗时，下次至少等 `max(1.2, 耗时×3)` 秒（上限 8s）才允许再刷。
        """
        if getattr(self, "_live_loading", False):
            return
        now = time.monotonic()
        if now < getattr(self, "_live_next_at", 0.0):
            return
        self._live_loading = True
        try:
            sb = self.table.verticalScrollBar()
            pos = sb.value() if sb is not None else 0
            t0 = time.monotonic()
            self._load()
            cost = time.monotonic() - t0
            self._live_next_at = time.monotonic() + max(1.2, min(8.0, cost * 3.0))
            # 填表是分批异步的，稍后把滚动位置还原，尽量不打断用户视线
            QTimer.singleShot(60, lambda: (self.table.verticalScrollBar().setValue(pos)
                                           if self.table.verticalScrollBar() is not None else None))
        finally:
            self._live_loading = False

    def _load(self):
        """读取列表数据。

        v1.14.0 海量数据优化：
        · `light=True` —— 列表**不取 plot 等大字段**（详情面板要用时再按 id 单行取回），
          5 万条时这是几百 MB 级的差别；
        · 演员列改**懒加载** —— 只为真正填进表格的那一段查关联（`actors_map(ids=…)`），
          不再每次把整张 media_people 拉进内存。
        """
        # v1.46.8：这条查询是**同步**取全库（4.8 万条约数秒），先点亮状态栏
        # （不确定态），配合 `_on_busy` 里的同步 repaint，朱红在阻塞开始前就画上去。
        _busy(-1, "载入列表")
        self._media = db.search_media(limit=100000, light=True, top_only=True)
        # v2.0.7（反馈 3）：重载后仍要套用「搜索框 + 每列筛选」，否则扫描刷新一次筛选就没了
        self._view = self._filter_view(list(self._media))
        self._set_active_chip(None)      # v1.25.0（反馈 6）：回到全量列表 → 取消选中态
        self._apply_view()

    _FILL_PAD = 14            # 视口上下各多填几行 —— 滚动时不会先看到一片空白
    _FILL_FALLBACK = 60       # 视口还没布局出来时（构造期）先填这么多行

    def _apply_view(self):
        """按当前 `_view` 重建表格 —— **只填视口里看得见的那几十行**（v2.0.8 反馈 4）。

        原来的做法是「`setRowCount(全量)` → 每 200 行一批把整表填满」，离屏实测 4 万条：
          · `setRowCount(0)+setRowCount(40000)` 一次阻塞 **738ms**（纯建行，不含内容）；
          · 全量填表 200 批合计 **3.5s**，每批 17ms —— 用户感觉就是「一直在顿」；
          · 于是「点一次表头排序」= 再填一遍 = **4.1s 卡顿**，也就是反馈里的「有点卡」。
        关键事实：QTableWidget 只有**可见行**真的需要 QTableWidgetItem。行数照旧设成全量
        （滚动条长度才对），内容按视口懒填、滚到哪儿填哪儿 —— 排序 / 筛选 / 换列
        立刻降到毫秒级，内存也少了几十万个 item。
        """
        n = len(self._view)
        self._backdrop_id = None          # 列表内容变了 → 允许下一行重新刷磨砂底衬
        # 行没填时 `row_media()` 按行号回退到这里（导出 / 全选 / 批量删都靠它）
        self.table._media_view = self._view
        tv = self.table
        if tv.rowCount() != n:
            # 只有行数变了才动它 —— 排序时行数不变，这一步 0 开销
            tv.setUpdatesEnabled(False)
            try:
                tv.setRowCount(n)
            finally:
                tv.setUpdatesEnabled(True)
        self._filled_range = None
        _busy(None)
        self._fill_window(force=True)      # 填视口
        self._on_select()                  # 底部「已选 N 项」跟着刷新

    def _viewport_rows(self):
        """当前视口覆盖的行区间 (first, last)；几何还没算出来时给安全默认值。"""
        tv = self.table
        h = tv.viewport().height()
        first = tv.rowAt(0)
        if first < 0:
            vsb = tv.verticalScrollBar()
            first = max(0, vsb.value()) if vsb is not None else 0
        last = tv.rowAt(max(0, h - 1)) if h > 0 else -1
        if last < 0:
            row_h = tv.verticalHeader().defaultSectionSize() or 24
            cnt = max(1, h // row_h) if h > 0 else self._FILL_FALLBACK
            last = first + cnt - 1
        return first, last

    def _fill_window(self, force=False):
        """把「视口 + 上下各 `_FILL_PAD` 行」需要的那一段写进表格。"""
        n = len(self._view)
        if n == 0:
            self._filled_range = None
            return
        first, last = self._viewport_rows()
        a = max(0, first - self._FILL_PAD)
        b = min(n - 1, last + self._FILL_PAD)
        if not force and (a, b) == getattr(self, "_filled_range", None):
            return                      # 视口没动 → 什么都不用做
        chunk = self._view[a:b + 1]
        # 演员列仍然懒加载，但只查这一段（原先是整批 200 行查一次）
        need = [m.get("id") for m in chunk
                if m.get("id") and not m.get("_cast_loaded")]
        amap, ok = {}, False
        if need:
            try:
                amap = db.actors_map(ids=need)
                ok = True
            except Exception:
                amap = {}
        tv = self.table
        tv.setUpdatesEnabled(False)
        tv.blockSignals(True)
        try:
            for i, m in enumerate(chunk, start=a):
                if not m.get("_cast_loaded"):
                    m["actors_text"] = amap.get(m.get("id"), "")
                    if ok:
                        # 查成功才记号：查失败（库忙）时下一步还会再试，不会永久显示「—」
                        m["_cast_loaded"] = True
                self._set_row(i, m)
        finally:
            tv.blockSignals(False)
            tv.setUpdatesEnabled(True)
        self._filled_range = (a, b)

    # ---- 兼容旧探针（dev/test_v121_cards.py 等还在调这两个名字）----
    def _schedule_fill(self, delay=0):
        QTimer.singleShot(delay, self._fill_window)

    def _fill_chunk(self):
        """旧名：语义等同「把当前视口填满」。"""
        self._fill_window(force=True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if getattr(self, "_view", None) is not None:
            self._fill_window()

    def showEvent(self, e):
        super().showEvent(e)
        # 首次显示时视口几何才是真的 → 下一帧补一次（构造期算出来的是默认高度）
        QTimer.singleShot(0, self._fill_window)

    def _col_value(self, m, key):
        if key == "title":
            return m.get("title") or ""
        if key == "actors":
            return m.get("actors_text") or "—"
        if key == "rating":
            r = m.get("rating")
            return f"{r:.1f}" if isinstance(r, (int, float)) else "—"
        if key == "user_rating":
            r = m.get("user_rating")
            return f"{r:.1f}" if isinstance(r, (int, float)) else "—"
        if key == "kind":
            return mm.kind_cn(m.get("kind")) or "—"
        if key == "runtime_min":
            return mm.runtime_minutes(m.get("runtime")) or "—"
        if key == "file_size":
            return mm.human_size(m.get("file_size"))
        if key == "favorite":
            return "★ 收藏" if m.get("favorite") else "—"
        if key == "play_count":
            return str(m.get("play_count") or 0)
        if key == "language":
            return m.get("country") or "—"
        if key == "filename":
            fp = m.get("file_path") or ""
            return os.path.basename(fp) if fp else "—"
        if key == "path":
            return m.get("file_path") or "—"
        if key == "year":
            return str(m.get("year")) if m.get("year") else "—"
        v = m.get(key)
        return str(v) if v is not None else "—"

    def _set_row(self, i, m):
        for c, key in enumerate(self._cols):
            item = QTableWidgetItem(self._col_value(m, key))
            item.setData(Qt.UserRole, m)          # 每列都挂上，列换位后仍可取到
            # v1.46.11（反馈 2）：这里**故意不再 setToolTip**。
            # 原来看每个单元格都挂了 tooltip，鼠标在一行上停够 ~1s 后系统 tooltip
            # 就会弹出来 —— 它和下面的自定义悬停卡**同时存在、互相压着**
            # （用户截图里的「叠加显示」就是这两层：一行标题的 tooltip + 整张信息卡）。
            # 悬停卡已经给了标题 / 评分年份时长 / 演员 / 类型 / 制片 / 上映，
            # 其余字段在右侧详情里都有，所以直接去掉，只留一张卡。
            self.table.setItem(i, c, item)

    # ---------- 悬停缩略图 ----------
    def _on_cell_entered(self, row, col):
        if row < 0:
            self._hide_preview()
            return
        m = row_media(self.table, row)
        if not m:
            self._hide_preview()
            return
        if m is getattr(self, "_hover_media", None):
            # 同一行内换列：预览已弹出就保持不动，否则重新计时 —— 都**不重刷底衬**
            if not self._preview.isVisible():
                self._hover_timer.start(320)
            return
        self._hide_preview()
        self._hover_media = m
        self._notify_backdrop(m)
        self._hover_timer.start(320)

    def _notify_backdrop(self, m):
        """请求换磨砂底衬 —— **去抖 + 按 id 去重**（v1.21.0）。

        底衬换一次要把剧照缩放到整窗再模糊（1920×1080），是这个页面最重的一步。
        原先鼠标在同一行内换列、或快速滑过快十几行时会被逐行触发，表现出来就是
        「鼠标一移动就卡」。
        """
        mid = (m or {}).get("id")
        if mid is None or mid == getattr(self, "_backdrop_id", None):
            return
        self._backdrop_pending = m
        self._backdrop_timer.start(130)

    def _apply_backdrop(self):
        m = getattr(self, "_backdrop_pending", None)
        mid = (m or {}).get("id")
        if mid is None or mid == getattr(self, "_backdrop_id", None):
            return
        self._backdrop_id = mid
        if self.on_hover_media:
            try:
                self.on_hover_media(m)
            except Exception:
                pass

    def _show_preview(self):
        m = getattr(self, "_hover_media", None)
        if not m or not self.isVisible():
            return
        try:
            self._preview.set_media(m)
            self._preview.popup_at(QCursor.pos())
        except Exception:
            self._hide_preview()

    def _hide_preview(self, *args):
        self._hover_timer.stop()
        self._hover_media = None
        if self._preview.isVisible():
            self._preview.hide()

    def eventFilter(self, obj, ev):
        if obj is self.table.viewport():
            t = ev.type()
            if t in (QEvent.Leave, QEvent.Wheel, QEvent.MouseButtonPress,
                     QEvent.MouseButtonDblClick, QEvent.Hide, QEvent.FocusOut):
                self._hide_preview()
        return super().eventFilter(obj, ev)

    def hideEvent(self, e):
        self._hide_preview()
        # 切页前把未提交的去抖写入落盘，保证布局/列宽不丢
        if self._search_timer.isActive():
            self._search_timer.stop(); self._apply_filter_now()
        self._backdrop_timer.stop()       # 已离开首页，不必再换底衬
        if self._split_timer.isActive():
            self._split_timer.stop(); self._commit_split()
        if self._width_timer.isActive():
            self._width_timer.stop(); self._commit_width()
        if self._order_timer.isActive():
            self._order_timer.stop(); self._commit_column_order()
        super().hideEvent(e)

    # ---------- 交互 ----------
    def _on_search_changed(self, text):
        """搜索框每次变动都回调 —— 这里只重起去抖计时器，真正过滤交给 `_apply_filter_now`。"""
        self._hide_preview()
        self._search_timer.start(250)

    def _apply_filter_now(self):
        """搜索框去抖后 + 每列筛选统一在这里落地（v2.0.7：多了一层列筛选）。"""
        self._hide_preview()
        self._view = self._filter_view(list(self._media))
        self._apply_view()

    def _filter_view(self, seq):
        """把「搜索框 + 每列筛选」一起套上去，返回新列表（不改入参）。

        筛选与排序是两件事：这里只筛，排序仍由 `_sort` / `_restore_sort` 负责，
        所以「先筛后排」与「先排后筛」结果一致。
        """
        text = self.search.text().strip().lower()
        out = []
        for m in seq:
            if text:
                if (text not in (m.get("title") or "").lower()
                        and text not in (m.get("actors_text") or "").lower()):
                    continue
            ok = True
            for key, spec in self._filters.items():
                if not self._match_filter(m, key, spec):
                    ok = False
                    break
            if ok:
                out.append(m)
        return out

    def _num_value(self, m, key):
        """取一列的**数值**（筛选用）；取不到返回 None（这类行在数值筛选下一律不显示）。"""
        if key == "runtime_min":
            v = mm.runtime_minutes(m.get("runtime"))
        else:
            v = m.get(key)
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(str(v).strip())
        except (TypeError, ValueError):
            return None

    def _match_filter(self, m, key, spec):
        """单行是否通过某一列的筛选条件。"""
        spec = spec or {}
        mode = str(spec.get("mode") or "text")
        val = spec.get("value")
        if mode == "eq":
            if val in (None, ""):
                return True
            if key == "favorite":
                return bool(m.get("favorite")) == (str(val) == "1")
            return str(self._col_value(m, key) or "") == str(val)
        if mode == "num":
            try:
                target = float(val)
            except (TypeError, ValueError):
                return True
            cur = self._num_value(m, key)
            if cur is None:
                return False
            op = str(spec.get("op") or ">=")
            if op == "=":
                return abs(cur - target) < 1e-6
            if op == "<=":
                return cur <= target
            return cur >= target
        q = str(val or "").strip().lower()
        if not q:
            return True
        return q in str(self._col_value(m, key) or "").lower()

    # ---------- 每列筛选（v2.0.7 反馈 3） ----------
    def _eq_options(self, key):
        """枚举型列的候选值；返回 None 表示「不是枚举列」（走输入框 / 数值）。"""
        if key == "favorite":
            return [("全部", ""), ("已收藏", "1"), ("未收藏", "0")]
        if key == "kind":
            seen = []
            for m in self._media or []:
                v = self._col_value(m, "kind")
                if v and v != "—" and v not in seen:
                    seen.append(v)
            return [("全部", "")] + [(v, v) for v in sorted(seen)[:12]]
        return None

    def _open_column_filter(self, logical):
        """表头漏斗被点 → 在该列正下方弹出筛选面板。"""
        key = self._col_key(logical)
        if not key:
            return
        self._hide_preview()
        label = dict(cfg.HOME_COLUMNS).get(key, key)
        pop = ColumnFilterPopup(key, label, self._filters.get(key),
                                self._eq_options(key), self)
        pop.applied.connect(self._on_filter_applied)
        self._filter_popup = pop
        hdr = self.table.horizontalHeader()
        left = hdr.sectionViewportPosition(logical)
        gp = hdr.mapToGlobal(QPoint(max(0, left), hdr.height()))
        pop.adjustSize()
        scr = QGuiApplication.screenAt(gp) or QGuiApplication.primaryScreen()
        x, y = gp.x(), gp.y() + 2
        if scr is not None:
            geo = scr.availableGeometry()
            x = max(geo.left() + 6, min(x, geo.right() - pop.width() - 6))
            y = max(geo.top() + 6, min(y, geo.bottom() - pop.height() - 6))
        pop.move(x, y)
        pop.show()

    def _on_filter_applied(self, key, spec):
        """面板点「确定 / 清除」→ 改状态 → 落盘 → 重筛 → 刷新漏斗高亮。"""
        if spec:
            self._filters[key] = spec
        else:
            self._filters.pop(key, None)
        try:
            cfg.get_settings().set_home_filters(self._filters)
        except Exception:
            pass
        hdr = getattr(self, "_header", None)
        if hdr is not None:
            try:
                hdr.viewport().update()
            except RuntimeError:
                pass
        self._apply_filter_now()

    def clear_column_filters(self):
        """一键清掉所有列筛选（右键菜单「清除列筛选」用）。"""
        if not self._filters:
            return
        self._filters = {}
        try:
            cfg.get_settings().set_home_filters({})
        except Exception:
            pass
        hdr = getattr(self, "_header", None)
        if hdr is not None:
            try:
                hdr.viewport().update()
            except RuntimeError:
                pass
        self._apply_filter_now()

    def _click_chip(self, key):
        """点同一个快捷筛选第二次 = 取消筛选，回到全部作品（v1.25.0 反馈 6）。

        用 `_media` 这份缓存列表还原，不重新查库 —— 47k 条重查一次要好几秒。
        """
        if self._active_chip == key:
            self._set_active_chip(None)
            if self._media:
                self._view = list(self._media)
                self._apply_view()
            else:
                self._load()
            return
        self._apply_chip(key)

    def _set_active_chip(self, key):
        """维护「同一时刻只有一个亮着」，并同步按钮的 checked 态。"""
        self._active_chip = key
        for k, b in (getattr(self, "_chip_btns", None) or {}).items():
            try:
                b.setChecked(k == key)
            except RuntimeError:
                pass                          # 控件已随页面销毁

    def _apply_chip(self, key):
        self._set_active_chip(key)
        if key == "recent":
            self._view = db.recent(200)
        elif key == "favorites":
            self._view = db.favorites()
        elif key == "collections":
            cols = db.collections()
            names = [n for n, _ in cols]
            self._view = []
            for n in names:
                self._view.extend(db.search_media(collection=n, limit=100000, light=True, top_only=True))
        # 演员列交给 _fill_chunk 懒加载（此处不再预填空串，否则会绕过按段查询）
        # v1.21.0：清空搜索框时**屏蔽信号**，否则刚设好的 _view 会被搜索回调覆盖成全量
        self._search_timer.stop()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        # v2.0.7（反馈 3）：快捷筛选（最近添加 / 我的收藏 / 合集）之上仍叠每列筛选
        self._view = self._filter_view(self._view)
        self._apply_view()

    def _sort(self, col):
        if col < 0 or col >= len(self._cols):
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        key = self._cols[col]
        keyf = _SORT_KEYS.get(key, lambda m: (m.get("title") or ""))
        try:
            self._view = sorted(self._view, key=keyf, reverse=not self._sort_asc)
        except TypeError:
            self._view = sorted(self._view, key=lambda m: str(keyf(m)),
                                reverse=not self._sort_asc)
        self._apply_view()
        cfg.get_settings().set_home_sort(self._cols[col], self._sort_asc)
        # v2.0.7（反馈 3）：把排序列/方向告诉表头，好把对应的三角点亮
        if getattr(self, "_header", None) is not None:
            self._header.sort_col = self._sort_col
            self._header.sort_asc = self._sort_asc
            self._header.viewport().update()

    def _on_select(self):
        rows = self.table.selectionModel().selectedRows()
        sel = []
        last_m = None
        for r in rows:
            m = row_media(self.table, r.row())
            if m:
                sel.append(m)
                last_m = m
        self._show_detail(last_m)
        total = sum((m.get("file_size") or 0) for m in sel)
        self.status.setText(f"已选 {len(sel)} 项   ·   总大小 {mm.human_size(total)}")

    def _show_detail(self, m):
        self._hide_preview()
        # 列表数据是「轻投影」（不含 plot 等大字段）→ 详情面板按 id 取回完整行。
        # 单行走主键，代价极小，换来列表内存占用大幅下降（v1.14.0）。
        if m and m.get("id"):
            try:
                full = db.get_media(m["id"])
                if full:
                    m = {**m, **full}
            except Exception:
                pass
        self._detail_mid = (m or {}).get("id")     # v1.21.1 反馈 4：记下当前作品 id
        layout = self.detail_host.layout()
        while layout.count():
            w = layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not m:
            layout.addWidget(QLabel("（在左侧选择一项查看详情）"))
            return
        # v1.21.1 反馈 4：详情页改收藏/用户评分后，左侧表格对应行要**就地**刷新，
        # 不用整页重建（那样会丢选中/滚动位置），也不用手动点顶栏「刷新」。
        hv = HeroView(m, on_open_actor=self.on_open_actor, on_back=None,
                      on_changed=self._detail_changed,
                      on_open_actors=self.on_open_actors,
                      on_person_replaced=self.on_person_replaced)
        layout.addWidget(hv)

    def _detail_changed(self):
        """详情页编辑（收藏 / 用户评分）回调：先就地刷新本行，再上抛给主窗口刷统计。"""
        self._refresh_detail_row()
        if self.on_changed:
            try:
                self.on_changed()
            except Exception:
                pass

    def _refresh_detail_row(self):
        """v1.21.1 反馈 4：只重画当前作品那一行（favorite / user_rating 等列）。

        不重建整表，因此选中行、滚动位置、已展开的详情面板都保持不动；
        数据按 id 回查完整行，保证与数据库一致。
        """
        mid = self._detail_mid
        if mid is None:
            return
        try:
            full = db.get_media(mid)
        except Exception:
            return
        if not full:
            return
        for i, m in enumerate(self._view):
            if m.get("id") == mid:
                m.update(full)              # 回写最新字段（favorite / user_rating …）
                self._set_row(i, m)
                break

    def _on_open(self, item):
        m = row_media(self.table, item.row())
        if m and self.on_open_media:
            self.on_open_media(m)

    # ---------- 右键批量操作（v1.46.11 反馈 1） ----------
    #: (动作键, 菜单文字)。None 表示分隔线。菜单顺序就是这里的顺序。
    BULK_ITEMS = (
        ("play",         "播放选中视频"),
        ("folder",       "打开视频文件夹"),
        None,
        ("refresh",      "刷新数据"),
        None,
        ("delete_index", "删除数据"),
        ("delete_files", "删除源文件"),
    )

    def selected_medias(self):
        """当前选中的作品（按行号顺序、按 id 去重）。单选 / Ctrl 多选 / Shift 全选都走这里。"""
        try:
            rows = sorted(r.row() for r in self.table.selectionModel().selectedRows())
        except (RuntimeError, AttributeError):
            return []
        out, seen = [], set()
        for r in rows:
            m = row_media(self.table, r)
            if not m:
                continue
            mid = m.get("id")
            if mid in seen:
                continue
            seen.add(mid)
            out.append(m)
        return out

    def _on_context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid():
            return
        # 右键落在「已选中的行」上 → 保留整片选择（多选批量操作）；
        # 落在别处 → 先把选择切到这一行（跟资源管理器一致）。
        sel_rows = {r.row() for r in self.table.selectionModel().selectedRows()}
        if idx.row() not in sel_rows:
            self.table.clearSelection()
            self.table.selectRow(idx.row())
        medias = self.selected_medias()
        if not medias:
            return
        self._hide_preview()        # 菜单和悬停卡别叠在一起
        menu = self._build_context_menu(medias)
        try:
            menu.exec(self.table.viewport().mapToGlobal(pos))
        finally:
            menu.deleteLater()

    def _build_context_menu(self, medias):
        """按选中数量构建菜单。**独立成方法**，离屏冒烟可直接断言条目与文案。"""
        n = len(medias or [])
        suffix = "" if n <= 1 else f"（{n} 项）"
        menu = QMenu(self)
        menu.setObjectName("BulkMenu")
        actions = {}
        for spec in self.BULK_ITEMS:
            if spec is None:
                menu.addSeparator()
                continue
            key, label = spec
            act = menu.addAction(label + suffix)
            if key == "delete_files":
                act.setObjectName("DangerAction")
            actions[key] = act
        menu._actions_by_key = actions        # 便于测试/自动化取用
        for key, act in actions.items():
            # 默认参数固定住 key，否则闭包在循环结束后全指向最后一个
            act.triggered.connect(lambda _c=False, k=key, ms=medias: self._run_bulk(k, ms))
        return menu

    def _run_bulk(self, action, medias):
        if not self.on_bulk_action:
            return
        try:
            self.on_bulk_action(action, list(medias or []))
        except Exception:
            import traceback
            import applog
            applog.log("列表批量操作失败：%s\n%s" % (action, traceback.format_exc()), "error")

    # ---------- 批量结果回写（供主窗口调用） ----------
    def drop_ids(self, ids):
        """从列表里移除若干作品（删除索引 / 删除源文件之后调用）。

        只删这几行 + 同步 `_media` / `_view` 两个缓存，**不整表重建** ——
        4.8 万行重建一次要好几秒，删 3 项却卡半天不值。
        """
        ids = {i for i in (ids or []) if i is not None}
        if not ids:
            return
        self._media = [m for m in self._media if m.get("id") not in ids]
        self._view = [m for m in self._view if m.get("id") not in ids]
        self.table.setUpdatesEnabled(False)
        try:
            for r in range(self.table.rowCount() - 1, -1, -1):
                m = row_media(self.table, r)
                if m and m.get("id") in ids:
                    self.table.removeRow(r)
        finally:
            self.table.setUpdatesEnabled(True)
        if self._detail_mid in ids:
            self._detail_mid = None
            self._show_detail(None)
        else:
            self._on_select()

    def refresh_ids(self, ids):
        """重新从库里读回这几行并就地重画（右键「刷新数据」）。返回真正刷到的条数。"""
        ids = {i for i in (ids or []) if i is not None}
        if not ids:
            return 0
        hit = 0
        for i, m in enumerate(self._view):
            if m.get("id") not in ids:
                continue
            try:
                full = db.get_media(m["id"])
            except Exception:
                full = None
            if full:
                m.update(full)          # dict 是共享的 → _media 里那份也一起更新
                self._set_row(i, m)
                hit += 1
        self._on_select()
        return hit

    # ---------- 列设置 ----------
    def _open_col_settings(self):
        self._hide_preview()
        dlg = ColumnSettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._cols = list(cfg.get_settings().home_columns)
            self._reordering = True
            try:
                self.table.setColumnCount(0)
                self._rebuild_headers()
            finally:
                self._reordering = False
            if "actors" in self._cols and not any("actors_text" in m for m in self._media):
                self._load()
                return
            self._apply_view()


class ColumnSettingsDialog(QDialog):
    """首页显示列设置：勾选可见列 + 按住鼠标左键拖动排序（参考 tinyMediaManager 列选择器）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("首页显示列设置")
        self.resize(400, 560)
        self._labels = dict(cfg.HOME_COLUMNS)
        self._key_by_label = {v: k for k, v in self._labels.items()}
        s = cfg.get_settings()

        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 10)
        v.setSpacing(8)
        v.addWidget(QLabel("勾选需要在首页表格中显示的列（「标题」始终显示）。"))
        hint = QLabel("按住鼠标左键拖动条目即可调整列的排列顺序，确定后立即生效。")
        hint.setStyleSheet("color:#a1a1aa;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setDragEnabled(True)
        self.list.setAcceptDrops(True)
        self.list.viewport().setAcceptDrops(True)
        self.list.setDropIndicatorShown(True)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setUniformItemSizes(True)
        v.addWidget(self.list, 1)

        cur = [k for k in s.home_columns if k in self._labels]
        rest = [k for k, _ in cfg.HOME_COLUMNS if k not in cur]
        self._populate(cur + rest, {k: (k in s.home_columns) for k, _ in cfg.HOME_COLUMNS})

        btns = QHBoxLayout()
        reset = QPushButton("恢复默认")
        reset.setObjectName("Ghost")
        reset.clicked.connect(self._reset)
        ok = QPushButton("确定")
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        up = QPushButton("上移")
        up.setObjectName("Ghost")
        up.clicked.connect(lambda: self._nudge(-1))
        down = QPushButton("下移")
        down.setObjectName("Ghost")
        down.clicked.connect(lambda: self._nudge(1))
        btns.addWidget(up)
        btns.addWidget(down)
        btns.addStretch(1)
        btns.addWidget(reset)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)

    # ---------- 列表构建 / 操作 ----------
    def _populate(self, keys, checked_map):
        self.list.clear()
        for key in keys:
            it = QListWidgetItem(self._labels.get(key, key))
            it.setData(Qt.UserRole, key)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable |
                        Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            it.setCheckState(Qt.Checked if checked_map.get(key) else Qt.Unchecked)
            self.list.addItem(it)

    def _checked_map(self):
        out = {}
        for i in range(self.list.count()):
            it = self.list.item(i)
            key = it.data(Qt.UserRole) or self._key_by_label.get(it.text())
            if key:
                out[key] = (it.checkState() == Qt.Checked)
        return out

    def _keys(self):
        keys = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            key = it.data(Qt.UserRole) or self._key_by_label.get(it.text())
            if key:
                keys.append(key)
        return keys

    def _nudge(self, delta):
        row = self.list.currentRow()
        if row < 0:
            return
        j = row + delta
        if not (0 <= j < self.list.count()):
            return
        it = self.list.takeItem(row)
        self.list.insertItem(j, it)
        self.list.setCurrentRow(j)

    def _reset(self):
        order = [k for k, _ in cfg.HOME_COLUMNS if k in cfg.DEFAULT_HOME_COLUMNS]
        order += [k for k, _ in cfg.HOME_COLUMNS if k not in cfg.DEFAULT_HOME_COLUMNS]
        self._populate(order, {k: (k in cfg.DEFAULT_HOME_COLUMNS) for k, _ in cfg.HOME_COLUMNS})

    def accept(self):
        keys, checked = [], self._checked_map()
        for k in self._keys():
            if checked.get(k):
                keys.append(k)
        if "title" not in keys:
            keys.insert(0, "title")
        if not keys:
            return
        cfg.get_settings().set_home_columns(keys)
        super().accept()
