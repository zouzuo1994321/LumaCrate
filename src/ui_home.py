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

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QPushButton,
    QDialog, QScrollArea, QListWidget, QListWidgetItem, QFrame,
    QAbstractItemView, QApplication,
)

import database as db
import media_meta as mm
import config as cfg
from ui_hero import HeroView, cover_pixmap, placeholder_pixmap


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
    """取某一行绑定的 media 字典（列顺序可变，故逐列查找 UserRole）。"""
    if row is None or row < 0:
        return None
    for c in range(table.columnCount()):
        it = table.item(row, c)
        if it is not None:
            m = it.data(Qt.UserRole)
            if isinstance(m, dict):
                return m
    return None


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
        self.img.setStyleSheet("background:#0d0b0a;border-radius:6px;")
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
                 on_changed=None):
        super().__init__()
        self.on_open_actor = on_open_actor
        self.on_open_media = on_open_media
        self.on_hover_media = on_hover_media     # 悬停/选中 → 通知主窗口换磨砂底衬
        self.on_changed = on_changed             # 详情页编辑（收藏/评分）→ 通知主窗口（刷统计/侧栏）
        self._detail_mid = None                  # 当前详情面板展示的作品 id（v1.21.1 反馈 4）
        self._media = []
        self._view = []
        self._sort_col = -1
        self._sort_asc = True
        self._cols = list(cfg.get_settings().home_columns)
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
        self.table.viewport().installEventFilter(self)
        self.table.verticalScrollBar().valueChanged.connect(self._hide_preview)
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

        # 右详情
        self.detail_host = QWidget()
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
        self._width_timer.start(150)

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

    # ---------- 数据 ----------
    def live_refresh(self):
        """扫描进行中就地刷新：重新拉取列表数据，让新索引的影片立刻出现在首页（v1.22.0 反馈 4）。

        由 MainWindow._on_scan_live 在扫描进度信号触发时调用（已做节流）。
        """
        if getattr(self, "_live_loading", False):
            return
        self._live_loading = True
        try:
            sb = self.table.verticalScrollBar()
            pos = sb.value() if sb is not None else 0
            self._load()
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
        self._media = db.search_media(limit=100000, light=True, top_only=True)
        self._view = list(self._media)
        self._set_active_chip(None)      # v1.25.0（反馈 6）：回到全量列表 → 取消选中态
        self._apply_view()

    _FILL_CHUNK = 200         # 每次往表格里填多少行，然后交还事件循环

    def _apply_view(self):
        """按当前 `_view` 重建表格 —— **分批填充**，避免一次填几万行把界面卡死。"""
        self._fill_gen = getattr(self, "_fill_gen", 0) + 1
        self._filled = 0
        self._backdrop_id = None          # 列表内容变了 → 允许下一行重新刷磨砂底衬
        # v1.21.0：改行数也会逐行触发布局/重绘，先关掉刷新一次性做完
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)
            self.table.setRowCount(len(self._view))
        finally:
            self.table.setUpdatesEnabled(True)
        self._schedule_fill()

    def _schedule_fill(self, delay=0):
        QTimer.singleShot(delay, self._fill_chunk)

    def _fill_chunk(self):
        gen = getattr(self, "_fill_gen", 0)
        n = len(self._view)
        if getattr(self, "_filled", 0) >= n:
            return
        end = min(self._filled + self._FILL_CHUNK, n)
        chunk = self._view[self._filled:end]
        try:
            amap = db.actors_map(ids=[m.get("id") for m in chunk if m.get("id")])
        except Exception:
            amap = {}
        tv = self.table
        # v1.21.0：一批 200 行 × 8 列 = 1600 次 setItem，若每次都重绘/发信号，
        # 滚动期间就是持续的卡顿源。这里关掉刷新与信号，一批只处理一次。
        tv.setUpdatesEnabled(False)
        tv.blockSignals(True)
        try:
            for i, m in enumerate(chunk, start=self._filled):
                if not m.get("actors_text"):
                    m["actors_text"] = amap.get(m.get("id"), "")
                self._set_row(i, m)
        finally:
            tv.blockSignals(False)
            tv.setUpdatesEnabled(True)
        self._filled = end
        if gen != getattr(self, "_fill_gen", 0):
            return                      # 期间视图已变，丢弃本轮
        if self._filled < n:
            self.status.setText(f"正在载入列表… {self._filled} / {n}")
            self._schedule_fill(1)
        else:
            self._on_select()

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
            item.setToolTip(self._col_value(m, key))
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
        text = self.search.text().strip().lower()
        if not text:
            self._view = list(self._media)
        else:
            self._view = [m for m in self._media
                          if text in (m.get("title") or "").lower()
                          or text in (m.get("actors_text") or "").lower()]
        self._apply_view()

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
                      on_changed=self._detail_changed)
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
        hint.setStyleSheet("color:#9b8a72;")
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
