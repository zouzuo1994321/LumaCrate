# -*- coding: utf-8 -*-
"""
设置界面（参考截图 2–7）
========================
- 个性化设置：导航菜单(开关 + 上下排序) / 首页管理(模块开关) / 内容卡片(显示评分·分辨率·演员·导演)
- 服务管理：媒体库(新建 / 列表 / 扫描全部 —— 全部由用户自己命名，无内置库) / 后台任务管理(启用 / 库 / 时间 / 频率)
自绘 ToggleSwitch（无额外图片依赖）。
"""
import os
import math
import re
import subprocess
import sys
import zipfile

from PySide6.QtCore import (Qt, QThread, Signal, QPropertyAnimation, Property, QTime,
                            QEasingCurve, QSize, QTimer, QRectF, QPointF)
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QFont, QBrush
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QStackedWidget, QFrame, QLineEdit, QComboBox, QTimeEdit,
    QFileDialog, QWidget, QAbstractButton, QAbstractItemView, QGroupBox,
    QFormLayout, QGridLayout, QMessageBox, QCheckBox, QRadioButton,
    QSpinBox, QProgressBar, QPlainTextEdit, QApplication, QSlider, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QDoubleSpinBox,
)

import config as cfg
import database as db
import duplicates as dup_mod
import insight as insight_mod
import recommend as rec_mod
import scraper as scraper_mod
import applog
import backup as backup_mod
import tagopt as tagopt_mod
import ui_imagedetect              # v1.30.0 反馈 2：图像检测
import ui_manualedit               # v1.30.0 反馈 3：手动修改
import ui_actorcheck               # v1.31.0 反馈 3：演员检测
import i18n                        # v1.32.0 反馈 3：界面语言（19 种）
from ui_hero import compact_button

# v1.13.0：拉大行距，避免列表里内容被裁（反馈 1/2）；导航菜单列表高度改为按条目数自适应（反馈 7）
# v1.22.0：再整体加大一档 —— 用户反馈「提高行距以保证按钮完整显示」，行内 28~30px 的
# ↑/↓/测试 等窄按钮原来贴边（行高 = 按钮高 + 上下边距刚好相等），字体降级/DPI 缩放时
# 底部会被裁掉一截。这里把每行高度提到「按钮高 + 16px 呼吸」。
NAV_ROW_H = 52          # 导航菜单每行高度（含 ↑/↓ + 开关）
SRC_ROW_H = 56          # 数据源每行高度（描述允许换到第 2 行 + ↑/↓/测试）
# v1.14.0 反馈 6：媒体库列表每行也要留足高度 —— 原来用 row.sizeHint()，
# 行内的「编辑/扫描/删除」按钮被压得底部缺一截（截图为证）。
LIB_ROW_H = 54          # 媒体库每行高度（按此定 sizeHint，按钮完整可见）


def html_esc(text):
    """转义 `& < >`，用于把用户/数据里的文本安全地塞进富文本标签。"""
    return (str(text if text is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def rich(text):
    """把 `**强调**` 转成 `<b>强调</b>`。

    QLabel / QMessageBox / tooltip **都不认 Markdown**：直接写 `**` 会原样显示成星号
    （v1.24.0 出图时才发现一堆提示文案带着 `**`）。带星号的字符串一律过一遍这个函数，
    Qt 见到 `<b>` 会自动切到富文本模式 —— 所以换行要一并换成 `<br>`，并且要把 `& < >`
    先转义（文案里有「**< 0 = 软排斥**」这种裸小于号，不转义会被当成标签）。
    不含星号的原样返回，保持纯文本（纯文本才不会把 `\\n` 当空白吞掉）。
    """
    if "**" not in text:
        return text
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html_esc(text)).replace("\n", "<br>")


def _human_bytes(n):
    """字节数转人类可读字符串（用于实时运行状态面板的数据库大小）。"""
    n = int(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n} {unit}" if unit == "B" else f"{n / 1024:.1f} {unit}"
        n /= 1024


# ---------- 自绘开关 ----------
class ToggleSwitch(QAbstractButton):
    """自绘开关。

    v1.11.1 修复「设置里的动画不能正常显示」：原实现每次 `toggled` 都
    `a = QPropertyAnimation(self, b"pos_f")` —— 该对象**没有父对象、也没人持有引用**，
    Python 侧立刻被 GC 回收，动画只跑了一两帧就冻结：轨道还是关闭色、
    圆点卡在中位（截图里就是这样），状态与实际值不符。
    现在：动画 parent 设成 self 复用一份；颜色随进度插值；finished 再兜底对齐终值。
    """

    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"pos_f", self)   # parent=self，避免被回收
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._settle)
        self.toggled.connect(self._animate)

    # 轨道底色：关 #4a4038 → 开 <当前高亮色>。
    # v1.26.0（反馈 1）：原来这里写死朱红 —— 用户在「外观 → 高亮色」里换成藕荷/天青后，
    # 设置页里所有自绘开关的轨道**仍然是红的**（截图：色板高亮停在藕荷，开关全是朱红）。
    # 现在改成每次绘制时现取高亮色（与 QSS 令牌同源）。_ON 保留为兜底值 = ACCENT_DEFAULT。
    _OFF = (0x4a, 0x40, 0x38)
    _ON = (0xc0, 0x39, 0x2b)

    @staticmethod
    def accent_on():
        """当前高亮色的 RGB（跟随「外观 → 高亮色」）。

        为什么懒读 `main_window.ACCENT_RGB` 而不是模块级 `import main_window`：
        `main_window` 顶部就有 `from ui_settings import SettingsDialog, LibraryEditDialog`，
        这里反向 import 会成环（导入期类还没定义 → 窗口直接建不起来）。
        所以走 `sys.modules` 取「已加载完的那个模块对象」；拿不到时回落到 settings.json 的 accent。
        `render_style()` 每次重载样式表都会刷新 `ACCENT_RGB`，两边取到的必然是同一个值。
        """
        mw = sys.modules.get("main_window")
        rgb = getattr(mw, "ACCENT_RGB", None) if mw is not None else None
        try:
            if rgb is not None:
                r, g, b = (int(v) for v in tuple(rgb)[:3])
                return (r, g, b)
        except (TypeError, ValueError):
            pass
        try:
            return tuple(cfg.accent_rgb(cfg.get_settings().accent()))
        except Exception:
            return ToggleSwitch._ON

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        h = r.height()
        pad = 3
        tr = h / 2
        t = max(0.0, min(1.0, self._pos))
        p.setPen(Qt.NoPen)
        on = self.accent_on()
        p.setBrush(QColor(*[int(a + (b - a) * t) for a, b in zip(self._OFF, on)]))
        p.drawRoundedRect(r, tr, tr)
        kx = pad + t * (r.width() - 2 * pad - (h - 2 * pad))
        p.setBrush(QColor("#f3d9a0"))
        p.drawEllipse(int(kx), pad, h - 2 * pad, h - 2 * pad)

    def _animate(self, checked):
        end = 1.0 if checked else 0.0
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(end)
        self._anim.start()

    def _settle(self):
        """动画结束后把位置精确对齐到勾选状态（防止中途被打断留下半格）。"""
        self.set_pos(1.0 if self.isChecked() else 0.0)

    def get_pos(self):
        return self._pos

    def set_pos(self, v):
        self._pos = v
        self.update()

    pos_f = Property(float, get_pos, set_pos)


# ---------- 扫描线程 ----------
class ScanNamedWorker(QThread):
    done = Signal(dict, str)

    def __init__(self, lib):
        super().__init__()
        self.lib = lib

    def run(self):
        import scanner as scanner_mod
        counts = {"movie": 0, "tvshow": 0, "episode": 0}
        for p in self.lib.get("paths", []):
            if os.path.isdir(p):
                c = scanner_mod.scan_library(p, None, library_name=self.lib["name"])
                for k in counts:
                    counts[k] += c.get(k, 0)
        self.done.emit(counts, self.lib["name"])


# ---------- 演员刮削线程 ----------
class ScrapeWorker(QThread):
    progress = Signal(int, int, str, str)      # 当前序号 / 总数 / 姓名 / 状态
    done = Signal(dict)

    def __init__(self, people, opts):
        super().__init__()
        self.people = list(people)
        self.opts = dict(opts)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        def writer(pid, fields, only_missing):
            db.update_person(pid, only_missing=only_missing, **fields)

        def rep(i, total, name, status):
            self.progress.emit(i, total, name, status)

        try:
            stats = scraper_mod.scrape_many(
                self.people, self.opts, progress=rep,
                should_stop=lambda: self._stop, writer=writer)
        except Exception as e:
            stats = {"total": len(self.people), "ok": 0, "notfound": 0, "failed": 1,
                     "photo": 0, "fields": 0, "errors": [f"{type(e).__name__}: {e}"]}
        self.done.emit(stats)


class TestSourceWorker(QThread):
    """数据源连接自检（不阻塞界面）。"""
    done = Signal(str, dict)

    def __init__(self, source, proxy, timeout):
        super().__init__()
        self.source, self.proxy, self.timeout = source, proxy, timeout

    def run(self):
        r = scraper_mod.test_source(self.source, self.proxy, self.timeout)
        self.done.emit(self.source, r)


# ---------- 重复检测线程（v1.23.0） ----------
class DedupeWorker(QThread):
    """跨目录重复影片检测（在后台线程跑，避免 5 万片规模下卡界面）。

    v1.32.0（反馈 1）：接入「普通算法 / AI 算法」双模式 —— 普通算法跑完
    `find_duplicates()` 后，若选的是 AI 算法且本机 Ollama 可用，再让本地模型
    逐组复核（**只加一列建议，不动任何文件**）。
    """
    progress = Signal(int, int, str)
    done = Signal(object)          # DupReport 或 None（失败）

    def __init__(self, library, min_confidence, exclude_multipart=True,
                 verify_exists=True, algo="normal", model="", fast=True):
        super().__init__()
        self.library = library or None
        self.min_confidence = min_confidence
        # v1.24.0（反馈 1/2）：分片排除开关 + 磁盘存在性校验
        self.exclude_multipart = bool(exclude_multipart)
        self.verify_exists = bool(verify_exists)
        # v1.32.0（反馈 1）：算法与 AI 复核参数
        self.algo = "ai" if algo == "ai" else "normal"
        self.model = model or ""
        self.fast = bool(fast)

    def run(self):
        try:
            rep = dup_mod.find_duplicates(
                library=self.library, min_confidence=self.min_confidence,
                exclude_multipart=self.exclude_multipart,
                verify_exists=self.verify_exists,
                progress=lambda a, b, m: self.progress.emit(a, b, m))
        except Exception as e:
            applog.log(f"[重复检测] 失败：{type(e).__name__}: {e}")
            self.done.emit(None)
            return
        if self.algo == "ai" and rep is not None:
            try:
                dup_mod.review_with_ai(
                    rep, model=self.model or None, fast=self.fast,
                    progress=lambda a, b, m: self.progress.emit(a, b, m),
                    stop=self.isInterruptionRequested)
            except Exception as e:
                # 复核失败**绝不能吞掉普通算法的结果** —— 报告照发，只补一条说明
                applog.log(f"[重复检测] AI 复核异常：{type(e).__name__}: {e}")
                rep.ai = {"ai": False, "done": 0, "failed": 0, "skipped": 0,
                          "jobs": 0, "fast": self.fast,
                          "note": "AI 复核出错（%s），以下为普通算法结果。" % e}
        self.done.emit(rep)


# ---------- 玻璃对话框基类 ----------
# ---------- 八维偏好雷达（v1.24.0 反馈 6） ----------
class RadarChart(QWidget):
    """八维雷达图：**纯自绘**，无第三方图表依赖。

    之所以不用 QPainterPath 之外的任何东西：项目要求单文件 exe 不带 matplotlib
    （打包体积 + 首次启动都要付出代价），而八轴闭环多边形只要 20 行 `drawPolygon`。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 300)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._dims = []             # [(label, 0~1, detail)]

    def set_data(self, dims):
        self._dims = list(dims or [])
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        dims = self._dims
        if not dims:
            p.setPen(QColor("#8c8071"))
            p.drawText(self.rect(), Qt.AlignCenter, "暂无数据")
            p.end()
            return
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0 + 4
        r = min(w, h - 46) / 2.0 - 34
        n = len(dims)
        # 1) 同心网格 + 轴线
        grid_pen = QPen(QColor(255, 255, 255, 34), 1.0)
        for k in (0.25, 0.5, 0.75, 1.0):
            poly = QPolygonF()
            for i in range(n):
                a = -math.pi / 2 + 2 * math.pi * i / n
                poly.append(QPointF(cx + r * k * math.cos(a), cy + r * k * math.sin(a)))
            p.setPen(grid_pen)
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(poly)
        p.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
        for i in range(n):
            a = -math.pi / 2 + 2 * math.pi * i / n
            p.drawLine(QPointF(cx, cy), QPointF(cx + r * math.cos(a), cy + r * math.sin(a)))
        # 2) 数据多边形
        poly = QPolygonF()
        for i, (_label, v, _d) in enumerate(dims):
            a = -math.pi / 2 + 2 * math.pi * i / n
            rr = r * max(0.015, min(1.0, float(v)))
            poly.append(QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a)))
        p.setPen(QPen(QColor("#5fb0ff"), 2.0))
        p.setBrush(QBrush(QColor(95, 176, 255, 62)))
        p.drawPolygon(poly)
        # 3) 顶点小圆点
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#8fd0ff"))
        for pt in poly:
            p.drawEllipse(pt, 2.6, 2.6)
        # 4) 轴标签
        f = QFont(); f.setFamily("Microsoft YaHei UI"); f.setPixelSize(11)
        p.setFont(f)
        for i, (label, v, _d) in enumerate(dims):
            a = -math.pi / 2 + 2 * math.pi * i / n
            lx = cx + (r + 18) * math.cos(a)
            ly = cy + (r + 16) * math.sin(a)
            box = QRectF(lx - 46, ly - 16, 92, 32)
            p.setPen(QColor("#e2d7c3"))
            p.drawText(box, Qt.AlignCenter, f"{label}\n{int(round(v * 100))}%")
        p.end()


class PortraitWorker(QThread):
    """画像概览的后台计算（4.8 万条约 1.5 秒，不能占主线程）。"""

    done = Signal(object)
    progress = Signal(int, int, str)

    def __init__(self, library=None, favorites_only=False, parent=None):
        super().__init__(parent)
        self.library = library
        # v1.24.1（反馈 4）：统计范围 = 全部 / 我的收藏 / 指定媒体库
        self.favorites_only = bool(favorites_only)

    def run(self):
        try:
            data = insight_mod.Portrait(self.library,
                                        favorites_only=self.favorites_only).build(
                progress=lambda i, n, m: self.progress.emit(i, n, m))
        except Exception as e:
            applog.log(f"画像概览失败：{type(e).__name__}: {e}", "error")
            data = {"error": f"{type(e).__name__}: {e}"}
        self.done.emit(data)


class AiProbeWorker(QThread):
    """探测本机 Ollama（v1.24.1 反馈 2）。

    原来是直接在按钮回调里同步 `probe_ollama()`：0.5 秒的超时加上「结果和进页面时
    自动探测的一模一样」，点下去界面毫无变化 —— 用户看到的就是「点了没反应」。
    这里丢到线程里跑，配合页面的「正在检测…」忙碌态，点下去立刻有反馈。
    """

    done = Signal(object)

    def run(self):
        try:
            st = rec_mod.ai_status()
        except Exception as e:
            st = {"engine": "error", "label": "检测失败",
                  "detail": f"{type(e).__name__}: {e}"}
        self.done.emit(st)


class AiModelsWorker(QThread):
    """读取本机 Ollama 已安装的模型列表（v1.25.0 反馈 1）。

    `ollama list` 的图形等价物：丢线程里跑，避免 0.5 秒超时把设置窗口卡住。
    """

    done = Signal(object)

    def run(self):
        try:
            names = rec_mod.list_models()
        except Exception as e:
            applog.log(f"读取本机模型失败：{type(e).__name__}: {e}", "error")
            names = []
        self.done.emit(list(names or []))


class TagOptScanWorker(QThread):
    """标签优化：扫描 + 出计划（**只读盘、只算，绝不写盘**）（v1.25.0 反馈 4）。

    真正落盘在用户看到预览并确认之后的 TagOptRunWorker 里 —— 两段拆开是为了
    「先看会改成什么样，再决定要不要改」。
    """

    done = Signal(object, str)
    progress = Signal(int, int, str)

    def __init__(self, opt, scope, value, kw):
        super().__init__()
        self.opt = opt
        self.scope = scope
        self.value = value
        self.kw = dict(kw or {})

    def run(self):
        try:
            nfos = self.opt.collect(
                self.scope, self.value,
                progress=lambda i, n, m: self.progress.emit(i, n, m))
            if not nfos:
                self.done.emit([], "没有找到任何 .nfo —— 检查路径是否正确，"
                                   "或这个媒体库下是否已经有刮削好的 nfo。")
                return
            plans = self.opt.plan(
                nfos, progress=lambda i, n, m: self.progress.emit(i, n, m),
                **self.kw)
            self.done.emit(plans, "")
        except Exception as e:
            applog.log(f"标签优化扫描失败：{type(e).__name__}: {e}", "error")
            self.done.emit([], f"{type(e).__name__}: {e}")


class TagOptRunWorker(QThread):
    """标签优化：把计划写回 nfo 并同步数据库（v1.25.0 反馈 4）。"""

    done = Signal(object)
    progress = Signal(int, int, str)

    def __init__(self, opt, plans, backup):
        super().__init__()
        self.opt = opt
        self.plans = list(plans or [])
        self.backup = bool(backup)

    def run(self):
        try:
            st = self.opt.apply(
                self.plans, backup=self.backup,
                progress=lambda i, n, m: self.progress.emit(i, n, m))
        except Exception as e:
            applog.log(f"标签优化写入失败：{type(e).__name__}: {e}", "error")
            st = {"written": 0, "skipped": 0, "failed": 0, "db_synced": 0,
                  "backups": [], "errors": [f"{type(e).__name__}: {e}"]}
        self.done.emit(st)


class VectorEditorDialog(QDialog):
    """向量编辑（v1.24.0 反馈 8，借鉴 nfo_profiler 的同名功能）。

    偏好向量 = 「收藏影片的标签 / 片商 / 系列 + 收藏的演员 / 导演」，
    这里可以逐项改权重：>1 加强、0~1 减弱、**0 = 屏蔽**、< 0 = 软排斥（出现就减分）。
    改完立刻生效（智能推荐缓存会被作废，下次进「智能推荐」重新算）。
    """

    DIMS = [("tag", "标签"), ("actor", "演员"), ("director", "导演"),
            ("studio", "片商"), ("series", "系列")]

    def __init__(self, parent=None, on_saved=None):
        super().__init__(parent)
        self.setWindowTitle("向量编辑 · 智能推荐偏好权重")
        self.resize(760, 620)
        self.s = cfg.get_settings()
        self.on_saved = on_saved
        self._build()
        self.reload()

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(10)
        hint = QLabel(rich(
            "偏好向量来自「我的收藏」的影片（标签 / 片商 / 系列）与「演员库 / 导演库」里收藏的人。\n"
            "权重含义：**>1 加强**、1 = 默认、0~1 减弱、**0 = 屏蔽**、**< 0 = 软排斥**（命中就减分）。\n"
            "权重存在数据库 `vector_overrides` 表里，并在 settings.json 留一份快照随配置一起导出。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a2967f;font-size:11px;")
        v.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("维度"))
        self.cb_dim = QComboBox()
        for key, cn in self.DIMS:
            self.cb_dim.addItem(cn, key)
        row.addWidget(self.cb_dim)
        row.addWidget(QLabel("关键词"))
        self.ed_key = QLineEdit()
        self.ed_key.setPlaceholderText("例如：巨乳 / MOODYZ / さつき芽衣")
        row.addWidget(self.ed_key, 1)
        row.addWidget(QLabel("权重"))
        self.sp_w = QDoubleSpinBox()
        self.sp_w.setRange(-5.0, 5.0)
        self.sp_w.setSingleStep(0.1)
        self.sp_w.setDecimals(2)
        self.sp_w.setValue(1.0)
        row.addWidget(self.sp_w)
        add = QPushButton("添加 / 更新")
        add.setObjectName("Primary")
        add.clicked.connect(self._upsert)
        row.addWidget(add)
        v.addLayout(row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["维度", "关键词", "权重", "说明"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._pick)
        v.addWidget(self.table, 1)

        btns = QHBoxLayout()
        b_fill = QPushButton("从画像自动填充…")
        b_fill.setObjectName("Ghost")
        b_fill.setToolTip("按「画像概览」里权重最高的标签 / 片商 / 演员自动生成一批权重")
        b_fill.clicked.connect(self._autofill)
        b_del = QPushButton("删除选中")
        b_del.setObjectName("Ghost")
        b_del.clicked.connect(self._delete)
        b_clr = QPushButton("全部清空")
        b_clr.setObjectName("Ghost")
        b_clr.clicked.connect(self._clear)
        btns.addWidget(b_fill)
        btns.addWidget(b_del)
        btns.addStretch(1)
        btns.addWidget(b_clr)
        v.addLayout(btns)

        self.status = QLabel("—")
        self.status.setStyleSheet("color:#8c8071;font-size:11px;")
        self.status.setWordWrap(True)
        v.addWidget(self.status)

        foot = QHBoxLayout()
        foot.addStretch(1)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        foot.addWidget(close)
        v.addLayout(foot)

    # ---------- 数据 ----------
    def reload(self):
        rows = db.vector_overrides()
        self.table.setRowCount(len(rows))
        cn = {k: c for k, c in self.DIMS}
        for r, (dim, key, w, note, _u) in enumerate(rows):
            vals = [cn.get(dim, dim), key, f"{w:g}", note or ""]
            for c, val in enumerate(vals):
                it = QTableWidgetItem(str(val))
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(r, c, it)
        self.table.resizeColumnsToContents()
        self.status.setText(
            f"共 {len(rows)} 条手动权重。"
            + ("（空 = 完全按收藏自动推导）" if not rows else ""))

    def _current(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        return (self.table.item(r, 0).text(), self.table.item(r, 1).text())

    def _pick(self):
        r = self.table.currentRow()
        if r < 0:
            return
        dim_cn, key = self.table.item(r, 0).text(), self.table.item(r, 1).text()
        for i, (k, c) in enumerate(self.DIMS):
            if c == dim_cn:
                self.cb_dim.setCurrentIndex(i)
                break
        self.ed_key.setText(key)
        try:
            self.sp_w.setValue(float(self.table.item(r, 2).text()))
        except Exception:
            pass

    def _upsert(self):
        dim = self.cb_dim.currentData()
        key = self.ed_key.text().strip()
        if not key:
            QMessageBox.information(self, "提示", "请填写关键词。")
            return
        w = float(self.sp_w.value())
        db.set_vector_override(dim, key, w)
        # settings.json 留一份快照（随「数据导出 → 配置」一起走）
        self.s.set_vector_weight(dim, key, w)
        applog.log(f"[向量编辑] {dim}:{key} = {w:g}")
        self.reload()
        if self.on_saved:
            self.on_saved()

    def _delete(self):
        cur = self._current()
        if not cur:
            return
        dim_cn, key = cur
        dim = next((k for k, c in self.DIMS if c == dim_cn), dim_cn)
        db.set_vector_override(dim, key, None)
        self.s.set_vector_weight(dim, key, None)
        applog.log(f"[向量编辑] 删除 {dim}:{key}")
        self.reload()
        if self.on_saved:
            self.on_saved()

    def _clear(self):
        if QMessageBox.question(self, "确认", "清空全部手动权重？"
                                "（只影响推荐，不动任何影片数据）") != QMessageBox.Yes:
            return
        db.clear_vector_overrides()
        self.s.clear_vector()
        self.reload()
        if self.on_saved:
            self.on_saved()

    def _autofill(self):
        """按画像的高频项生成一批权重（标签 / 片商 / 系列 / 演员 / 导演 各取前几名）。"""
        if QMessageBox.question(
                self, "自动填充",
                "会按「画像概览」统计出的高频项写入一批权重（标签前 30、片商前 10、"
                "系列前 10、演员前 10、导演前 10，权重 1.5 / 1.3 / 1.2）。\n"
                "已有的同名条目会被覆盖。继续？") != QMessageBox.Yes:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            data = insight_mod.Portrait().build()
        finally:
            QApplication.restoreOverrideCursor()
        plan = (("tag", data.get("tags", [])[:30], 1.5),
                ("studio", data.get("studios", [])[:10], 1.3),
                ("series", data.get("series", [])[:10], 1.2),
                ("actor", data.get("actors", [])[:10], 1.3),
                ("director", data.get("directors", [])[:10], 1.2))
        n = 0
        for dim, items, w in plan:
            for key, _c in items:
                if not str(key).strip():
                    continue
                db.set_vector_override(dim, key, w)
                self.s.set_vector_weight(dim, key, w)
                n += 1
        applog.log(f"[向量编辑] 自动填充 {n} 条")
        self.reload()
        self.status.setText(f"已自动填充 {n} 条（标签 / 片商 / 系列 / 演员 / 导演）。")
        if self.on_saved:
            self.on_saved()


class GlassDialog(QDialog):
    """按当前外观设置给对话框套用系统模糊（磨砂玻璃）。"""

    def showEvent(self, e):
        super().showEvent(e)
        try:
            import backdrop
            self._backdrop = backdrop.auto_apply(self)
        except Exception:
            pass


# ---------- 媒体库编辑 / 新建对话框：名称 / 类型 / 媒体文件夹 ----------
class LibraryEditDialog(GlassDialog):
    """唯一的媒体库编辑对话框（v1.12.0 起「新建」与「编辑」共用，只差标题）。

    旧版还有第二个 `MediaLibraryDialog`（名称/语言/文件夹）只服务于「内置媒体库」那套
    分类库 —— 两套并存正是「两个媒体库」的来源，已随统一模型一起删掉。
    """

    def __init__(self, parent, lib, title="编辑媒体库"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(480, 360)      # v1.22.0：路径区多了 ↑/↓/移除 一行 + 更高列表
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 12)
        v.setSpacing(10)

        form = QFormLayout()
        self.name = QLineEdit(lib.get("name", ""))
        self.kind = QComboBox()
        self.kind.addItems(cfg.LIBRARY_KINDS)
        self.kind.setCurrentText(lib.get("kind", "混合") or "混合")
        form.addRow("名称", self.name)
        form.addRow("媒体类型", self.kind)
        v.addLayout(form)

        # v1.22.0（反馈 2）：路径可**上下排序**，顺序即扫描优先级 —— 扫描时按这个顺序
        # 依次遍历各目录，靠前的目录先入索引。↑/↓ 就地调整，保存后写入 settings.json。
        v.addWidget(QLabel("路径（可添加多个目录；顺序即扫描优先级，自上而下依次扫描）："))
        self.paths = QListWidget()
        self.paths.setFixedHeight(122)
        for p in lib.get("paths", []):
            self.paths.addItem(p)
        self.paths.currentRowChanged.connect(lambda _r: self._sync_path_btns())
        v.addWidget(self.paths)
        pa = QWidget()
        pah = QHBoxLayout(pa)
        pah.setContentsMargins(0, 0, 0, 0)
        pah.setSpacing(6)
        addp = QPushButton("添加路径")
        addp.setObjectName("Ghost")
        addp.clicked.connect(self._add)
        self.up_p = compact_button("↑", 30, 30, "上移（提高扫描优先级）")
        self.up_p.clicked.connect(lambda: self._move_path(-1))
        self.down_p = compact_button("↓", 30, 30, "下移（降低扫描优先级）")
        self.down_p.clicked.connect(lambda: self._move_path(1))
        self.del_p = QPushButton("移除")
        self.del_p.setObjectName("Ghost")
        self.del_p.clicked.connect(self._remove_path)
        pah.addWidget(addp)
        pah.addWidget(self.up_p)
        pah.addWidget(self.down_p)
        pah.addWidget(self.del_p)
        pah.addStretch(1)
        v.addWidget(pa)
        self._sync_path_btns()

        btns = QHBoxLayout()
        ok = QPushButton("保存")
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)

    def _add(self):
        d = QFileDialog.getExistingDirectory(self, "选择媒体库目录")
        if d:
            self.paths.addItem(d)
            self.paths.setCurrentRow(self.paths.count() - 1)

    def _move_path(self, delta):
        """把当前路径上/下移一位（顺序即扫描优先级）。"""
        r = self.paths.currentRow()
        t = r + delta
        if r < 0 or t < 0 or t >= self.paths.count():
            return
        it = self.paths.takeItem(r)
        self.paths.insertItem(t, it)
        self.paths.setCurrentRow(t)

    def _remove_path(self):
        r = self.paths.currentRow()
        if r < 0:
            return
        self.paths.takeItem(r)
        self._sync_path_btns()

    def _sync_path_btns(self):
        """没有选中行时，↑/↓/移除 置灰。"""
        has = self.paths.currentRow() >= 0
        for b in (getattr(self, "up_p", None), getattr(self, "down_p", None),
                  getattr(self, "del_p", None)):
            if b is not None:
                b.setEnabled(has)

    def result_data(self):
        return (self.name.text().strip(), self.kind.currentText(),
                [self.paths.item(i).text() for i in range(self.paths.count())])


# ---------- 设置对话框 ----------
class SettingsDialog(QDialog):
    def __init__(self, parent=None, on_changed=None):
        super().__init__(parent)
        # v1.24.0（反馈 5）：入口与标题由「设置」改为「工具」
        self.setWindowTitle("工具")
        # 放大对话框，确保「演员刮削」整页一屏显示、无需滚动
        sw = self.screen()
        avail = sw.availableGeometry() if sw is not None else None
        w = min(1000, (avail.width() if avail else 1280) - 40)
        h = min(900, (avail.height() if avail else 1040) - 40)
        self.resize(w, h)
        self.s = cfg.get_settings()
        self.on_changed = on_changed
        self._src_rows = {}        # 数据源 key -> 行内测试结果标签
        self._insight_data = {}    # 画像概览结果（懒计算，首次进页面时算）
        self._insight_worker = None
        self._insight_pending = False   # 分析中又换了统计范围 → 跑完补算一次
        self._vector_dlg = None
        self._build()

    # ---------- 框架 ----------
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.nav_frame = QFrame()
        self.nav_frame.setObjectName("Sidebar")
        self.nav_frame.setFixedWidth(150)
        root.addWidget(self.nav_frame)
        self._rebuild_nav_buttons(build=True)

        self.stack = QStackedWidget()
        self._pg_personal = self._page_scroll(self._build_personal())
        # v1.24.0：画像概览内容很高（雷达 + 概览 + 高频榜 + 分布 + 共现），**必须套滚动** ——
        # 不套的话它会把整窗最小高度顶到 1733px（真机 1080p 屏幕上底部够不着，live_verify 抓到过）。
        # v1.30.0：手动修改（左列表 + 右表单，自带滚动）／图像检测（结果树，必须套滚动）
        self._pg_manual = self._page_scroll(ui_manualedit.ManualEditPage())
        self._pg_insight = self._page_scroll(self._build_insight())
        self._pg_scraper = self._build_scraper()      # 紧凑布局，整页一屏、不套滚动
        self._pg_smart = self._page_scroll(self._build_smart())     # v1.24.0：智能推荐
        self._pg_tagopt = self._page_scroll(self._build_tagopt())   # v1.25.0：标签优化
        self._pg_service = self._page_scroll(self._build_service())
        self._pg_dedupe = self._page_scroll(self._build_dedupe())   # v1.23.0：重复检测
        # v1.31.0（反馈 3）：演员检测自带上下两块 + 内外滚动，**不再套 _page_scroll**
        # （外面再包一层滚动区会让两个分隔条的高度互相打架）。
        self._pg_actorcheck = ui_actorcheck.ActorCheckPage()
        self._pg_imagedetect = self._page_scroll(ui_imagedetect.ImageDetectPage())
        self._pg_data = self._page_scroll(self._build_data())   # v1.13.0：数据 / 日志导出
        for pg in (self._pg_personal, self._pg_manual, self._pg_insight, self._pg_scraper,
                   self._pg_smart, self._pg_tagopt, self._pg_service, self._pg_dedupe,
                   self._pg_actorcheck, self._pg_imagedetect, self._pg_data):
            self.stack.addWidget(pg)
        root.addWidget(self.stack, 1)

        self._show("个性化设置")

    def showEvent(self, e):
        super().showEvent(e)
        # 让设置窗口也享受磨砂玻璃
        import backdrop
        self._backdrop = backdrop.auto_apply(self)
        # v1.18.0 反馈 98：打开即开始刷新「实时运行状态」
        if getattr(self, "_rt_timer", None) is not None:
            self._rt_timer.start()

    def _page_scroll(self, widget):
        from PySide6.QtWidgets import QScrollArea
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(widget)
        return sc

    @staticmethod
    def _section(text):
        """导航分组小标题。样式来自 `QLabel#Section`（与主页侧栏的「分类 / 媒体库」同一套）。"""
        l = QLabel(i18n.tr(text))
        l.setObjectName("Section")
        return l

    #: 导航分组（v1.31.0 反馈 4 定的四组）。**键是中文**，因为它是页面的身份
    #: （`self.sub_btns` 的 key、`ORDER` 的元素、dev 脚本遍历的依据），
    #: 翻译只发生在**显示**这一层 —— 换语言绝不能改身份，否则 `_show()` 会找不到页。
    NAV_GROUPS = [
        ("基础工具", ["个性化设置", "服务管理", "手动修改"]),
        ("数据优化", ["演员刮削", "智能推荐", "标签优化"]),
        ("智能检测", ["重复检测", "演员检测", "图像检测"]),
        ("数据分析", ["画像概览", "数据与日志"]),
    ]

    def _rebuild_nav_buttons(self, build=False):
        """(重)建左侧导航按钮。换语言时会再调一次（`build=False`）。

        v1.31.0（反馈 4）：导航按**用途分成四组**，与主页侧栏「分类 + 媒体库」同一套
        分组写法（`QLabel#Section` 小标题）。10 来个平铺页签已经不好找了，分组后
        「检测类工具在哪」一眼可见。

        v1.32.0（反馈 3）：按钮文字走 `i18n.tr()`；`self.sub_btns` 的**键仍是中文**，
        页面映射（`_show`）因此不受语言影响。
        """
        old = self.nav_frame.layout()
        if old is None:
            old = QVBoxLayout(self.nav_frame)
        else:
            # ⚠ 清空布局必须 `setParent(None)` —— 只 `takeAt()` + `deleteLater()`
            # 不会立刻脱离父对象，旧按钮会在新按钮之前继续显示（v1.31.0 踩过。
            # 见 skill 第 27.2 节）。
            while old.count():
                it = old.takeAt(0)
                w = it.widget()
                if w is not None:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
        old.setContentsMargins(8, 12, 8, 10)
        old.setSpacing(4)
        self.sub_btns = {}
        # `ORDER` 保持「扁平、按可见顺序」—— dev/ 下的 live_verify 与 render 脚本
        # 都按它遍历页面，分组只是显示层的包装。
        self.ORDER = [k for _g, keys in self.NAV_GROUPS for k in keys]
        for group, keys in self.NAV_GROUPS:
            old.addWidget(self._section(group))
            for key in keys:
                b = QPushButton(i18n.tr(key))
                b.setObjectName("Nav")
                b.setToolTip("%s · %s" % (i18n.tr(key), key))   # 悬停能看回原名，排查方便
                b.clicked.connect(lambda _c, k=key: self._show(k))
                old.addWidget(b)
                self.sub_btns[key] = b
        old.addStretch(1)
        if build:
            self._rebuild_nav_highlight()

    def _rebuild_nav_highlight(self):
        """把当前页的高亮重新画一遍（换语言重建按钮后必须补这一步）。

        ⚠ 必须容忍 `self.stack` 还不存在 —— 首次 `_build()` 里是**先**建导航
        （`_rebuild_nav_buttons(build=True)`）**后**建 `self.stack`（页面要按
        `NAV_GROUPS` 的顺序逐个建，价格不菲，所以放在按钮之后）。这里若直接
        `_show()` 就会 `AttributeError: no attribute 'stack'`，设置窗**完全打不开**。
        `_show()` 是换页的**唯一**入口（`_current_key` 的写入点也在它里面），
        所以这里只做「有能力就补画高亮」，真正的首次 `_show("个性化设置")` 由
        `_build()` 末尾负责 —— 那时 stack 已经就绪。
        """
        if getattr(self, "stack", None) is None:
            return
        self._show(getattr(self, "_current_key", None) or self.ORDER[0])

    def _show(self, key):
        self._current_key = key
        for k, b in self.sub_btns.items():
            b.setStyleSheet(
                "background:rgba(255,255,255,0.12);color:#f7e3b4;" if k == key else "")
        self.stack.setCurrentWidget({
            "个性化设置": self._pg_personal,
            "手动修改": self._pg_manual,
            "画像概览": self._pg_insight,
            "演员刮削": self._pg_scraper,
            "智能推荐": self._pg_smart,
            "标签优化": self._pg_tagopt,
            "服务管理": self._pg_service,
            "重复检测": self._pg_dedupe,
            "演员检测": self._pg_actorcheck,
            "图像检测": self._pg_imagedetect,
            "数据与日志": self._pg_data,
        }.get(key, self._pg_personal))
        # v1.24.0：画像概览第一次打开时自动分析一次（后续手动点「重新分析」）
        if key == "画像概览" and not self._insight_data:
            self._run_insight()

    # ---------- 通用行 ----------
    def _row(self, label_text, switch):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(2, 2, 2, 2)
        h.addWidget(QLabel(label_text))
        h.addStretch(1)
        h.addWidget(switch)
        return w

    # ---------- 个性化设置 ----------
    def _build_personal(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(14)

        # 外观（磨砂玻璃 / 经典暗色）
        g0 = QGroupBox("外观")
        g0v = QVBoxLayout(g0)
        self.ap_mode = QComboBox()
        self.ap_mode.addItems(cfg.APPEARANCE_MODES)
        self.ap_mode.setCurrentText(self.s.appearance.get("mode", "磨砂玻璃"))
        self.ap_mode.currentTextChanged.connect(self._apply_appearance)
        self.ap_level = QComboBox()
        self.ap_level.addItems(cfg.GLASS_LEVELS)
        self.ap_level.setCurrentText(self.s.appearance.get("level", "中"))
        self.ap_level.currentTextChanged.connect(self._apply_appearance)
        af = QFormLayout()
        af.addRow("主题模式", self.ap_mode)
        af.addRow("玻璃浓度", self.ap_level)
        # v1.32.0（反馈 3）：界面语言（19 种）。下拉里显示**自称**
        # （`English` / `日本語` / `العربية`）—— 用户认自己的字，不认别人的字母。
        self.ap_lang = QComboBox()
        for _code, _native in i18n.lang_names():
            self.ap_lang.addItem("%s  ·  %s" % (_native, i18n.cn_name(_code)), _code)
        _cur = self.s.language()
        _idx = self.ap_lang.findData(_cur)
        self.ap_lang.setCurrentIndex(_idx if _idx >= 0 else 0)
        self.ap_lang.setMinimumWidth(240)
        self.ap_lang.currentIndexChanged.connect(self._apply_language)
        af.addRow("界面语言", self.ap_lang)
        g0v.addLayout(af)
        # 语言说明（切到非基准语言时会写明「哪些已译、哪些仍是中文」）
        self.ap_lang_hint = QLabel("")
        self.ap_lang_hint.setStyleSheet("color:#a2967f;font-size:11px;")
        self.ap_lang_hint.setWordWrap(True)
        g0v.addWidget(self.ap_lang_hint)
        self._refresh_lang_hint()
        self.ap_hint = QLabel("")
        self.ap_hint.setStyleSheet("color:#a2967f;font-size:11px;")
        self.ap_hint.setWordWrap(True)
        g0v.addWidget(self.ap_hint)
        # 窗口透明度（整窗半透明透出桌面）
        oph = QWidget()
        ophl = QHBoxLayout(oph)
        ophl.setContentsMargins(0, 0, 0, 0)
        ophl.addWidget(QLabel("窗口透明度"))
        self.op_slider = QSlider(Qt.Horizontal)
        self.op_slider.setRange(30, 100)
        self.op_slider.setValue(int(round(float(self.s.window_opacity) * 100)))
        self.op_slider.valueChanged.connect(self._preview_opacity)
        self.op_slider.sliderReleased.connect(self._commit_opacity)
        ophl.addWidget(self.op_slider, 1)
        self.op_val = QLabel(f"{int(round(float(self.s.window_opacity) * 100))}%")
        self.op_val.setFixedWidth(48)
        self.op_val.setStyleSheet("color:#d4af37;")
        ophl.addWidget(self.op_val)
        g0v.addWidget(oph)
        # v1.25.0（反馈 5）：12 种基础「高亮色」。
        # 卡片选中的描边 + 外发光、按钮 / chip / 滑块 / 勾选框的强调色，
        # 全部由它派生（QSS 走令牌替换，自绘控件走 main_window.ACCENT_RGB），
        # 所以换一个色，整套界面一起变。
        acrow = QWidget()
        ach = QHBoxLayout(acrow)
        ach.setContentsMargins(0, 2, 0, 0)
        ach.setSpacing(6)
        ach.addWidget(QLabel("高亮色"))
        self._accent_btns = {}
        for _nm, _hex in cfg.ACCENT_COLORS:
            b = QPushButton()
            b.setFixedSize(26, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c, h=_hex: self._apply_accent(h))
            ach.addWidget(b)
            self._accent_btns[_hex] = b
        ach.addSpacing(10)
        self.lb_accent = QLabel("—")
        self.lb_accent.setStyleSheet("color:#d4af37;font-size:11px;")
        ach.addWidget(self.lb_accent)
        ach.addStretch(1)
        g0v.addWidget(acrow)
        # v1.28.0（反馈 1）：侧栏底部「数据统计」/「实时状态」的显隐开关。
        # 这两块在**侧栏**里（所有页面共用，首页自然也跟着变），关掉后侧栏竖向空间自动收回。
        srow = QWidget()
        srl = QVBoxLayout(srow)
        srl.setContentsMargins(0, 4, 0, 0)
        srl.setSpacing(6)
        self.sw_side_stats = ToggleSwitch(
            checked=bool(self.s.appearance.get("show_stats", True)))
        self.sw_side_stats.toggled.connect(self._apply_side_panels)
        self.sw_side_sysmon = ToggleSwitch(
            checked=bool(self.s.appearance.get("show_sysmon", True)))
        self.sw_side_sysmon.toggled.connect(self._apply_side_panels)
        srl.addWidget(self._row("侧栏「数据统计」", self.sw_side_stats))
        srl.addWidget(self._row("侧栏「实时状态」", self.sw_side_sysmon))
        side_hint = QLabel("控制侧栏底部这两块的显隐（侧栏各页面共用）；"
                           "关掉「实时状态」后采集线程也不会启动。")
        side_hint.setStyleSheet("color:#a2967f;font-size:11px;")
        side_hint.setWordWrap(True)
        srl.addWidget(side_hint)
        g0v.addWidget(srow)
        self._paint_accent_btns()
        self._refresh_backdrop_hint()
        v.addWidget(g0)

        # 导航菜单
        g1 = QGroupBox("导航菜单")
        g1v = QVBoxLayout(g1)
        self.nav_list = QListWidget()
        # 高度由 _rebuild_nav_list 按条目数自适应：原来写死 360，7 行只占一半，
        # 下方留了一大片空白（v1.13.0 反馈 7）。
        g1v.addWidget(self.nav_list)
        g1v.addWidget(QLabel("开关控制侧边栏是否显示；↑/↓ 调整顺序。"))
        self._rebuild_nav_list()
        v.addWidget(g1)

        # 首页管理
        g2 = QGroupBox("首页管理")
        g2v = QVBoxLayout(g2)
        module_map = [("recent", "最近添加 快捷筛选"),
                      ("favorites", "我的收藏 快捷筛选"),
                      ("collections", "合集 快捷筛选")]
        for key, label in module_map:
            sw = ToggleSwitch(checked=self.s.home_modules.get(key, True))
            sw.toggled.connect(lambda c, k=key: (self.s.home_modules.__setitem__(k, c), self.s.save()))
            g2v.addWidget(self._row(label, sw))
        v.addWidget(g2)

        # 内容卡片
        g3 = QGroupBox("内容卡片")
        g3v = QVBoxLayout(g3)
        # v1.11.1：年份 / 演员 / 导演 也做成开关（此前只有评分与画质可关）
        card_map = [("show_rating", "显示评分"),
                    ("show_year", "显示年份"),
                    ("show_quality", "显示分辨率 / 画质"),
                    ("show_actors", "显示演员"),
                    ("show_directors", "显示导演")]
        for key, label in card_map:
            sw = ToggleSwitch(checked=self.s.content_cards.get(key, True))
            sw.toggled.connect(lambda c, k=key: (self.s.content_cards.__setitem__(k, c), self.s.save()))
            g3v.addWidget(self._row(label, sw))
        hint = QLabel("改动立即生效：卡片会按开关自动调整高度，不会留下空白或被裁。")
        hint.setStyleSheet("color:#a2967f;font-size:11px;")
        hint.setWordWrap(True)
        g3v.addWidget(hint)
        v.addWidget(g3)

        v.addStretch(1)
        return page

    def _rebuild_nav_list(self):
        self.nav_list.clear()
        for item in self.s.nav:
            li = QListWidgetItem(self.nav_list)
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(6, 6, 6, 6)
            h.addWidget(QLabel(item["label"]))
            h.addStretch(1)
            # ↑/↓ 用 compact_button：全局 QSS 的 padding:7px 14px 会把 30px 宽按钮的
            # 内容区压成负数 → 箭头看不见（v1.11.1 修复「按钮不显示」）
            up = compact_button("↑", 32, 28, "上移")
            up.clicked.connect(lambda _c, k=item["key"]: self._move_nav(k, -1))
            down = compact_button("↓", 32, 28, "下移")
            down.clicked.connect(lambda _c, k=item["key"]: self._move_nav(k, 1))
            sw = ToggleSwitch(checked=item.get("visible", True))
            sw.toggled.connect(lambda c, k=item["key"]: self.s.set_nav_visible(k, c))
            h.addWidget(up)
            h.addWidget(down)
            h.addWidget(sw)
            # v1.13.0：行高加大到 NAV_ROW_H，避免行内控件挤在一起显得「显示不全」
            li.setSizeHint(QSize(row.sizeHint().width(), NAV_ROW_H))
            self.nav_list.addItem(li)
            self.nav_list.setItemWidget(li, row)
        # 列表高度贴合条目数（不留下方空白）
        self.nav_list.setFixedHeight(len(self.s.nav) * NAV_ROW_H + 14)

    def _move_nav(self, key, delta):
        self.s.move_nav(key, delta)
        self._rebuild_nav_list()
        if self.on_changed:
            self.on_changed()

    # ---------- 外观 ----------
    GLASS_HINT = ("磨砂玻璃：应用内磨砂 —— 当前作品的剧照会被强模糊后作为整窗底衬，"
                  "上面再叠半透明玻璃面板。浓度越低底衬越明显，切换后立即生效。")
    DARK_HINT = "经典暗色：不透明纯色，兼容性最好。"

    # ---------- 侧栏「数据统计」/「实时状态」显隐（v1.28.0 反馈 1） ----------
    def _apply_side_panels(self, *_):
        """两个开关落盘 → 通知主窗重建侧栏（`_apply_settings` 会走 `_build_sidebar`）。"""
        self.s.set_appearance(show_stats=self.sw_side_stats.isChecked(),
                              show_sysmon=self.sw_side_sysmon.isChecked())
        if self.on_changed:
            self.on_changed()

    # ---------- 高亮色（v1.25.0 反馈 5） ----------
    def _apply_accent(self, hexv):
        """选中一个高亮色：落盘 → 刷新色板 → 走一遍 `_apply_appearance`
        （它会重载样式表，main_window.render_style 顺手把 ACCENT_RGB 一起换掉，
        自绘卡片的描边和外发光因此立刻跟着变）。"""
        self.s.set_accent(hexv)
        self._paint_accent_btns()
        self._refresh_toggles()
        self._apply_appearance()

    def _paint_accent_btns(self):
        """把 12 个色块画成「本色填充 + 选中白边 + 勾」；未选中用暗描边。

        注意：这里用**控件级**样式表，它会盖掉全局 QSS 的 padding —— 26px 的小方块
        必须显式写 padding:0，否则全局 `QPushButton{padding:7px 14px}` 会把内容区
        压成负数，勾号与底色都会画不出来（本项目复发过多次的老坑）。
        """
        cur = self.s.accent()
        for hexv, b in getattr(self, "_accent_btns", {}).items():
            on = str(hexv).lower() == str(cur).lower()
            b.setStyleSheet(
                "QPushButton{background:%s;border:2px solid %s;border-radius:13px;"
                "padding:0;font-weight:700;color:#ffffff;}"
                "QPushButton:hover{border-color:#ffffff;}"
                % (hexv, "#ffffff" if on else "rgba(255,255,255,0.20)"))
            b.setText("✓" if on else "")
            b.setToolTip(f"{cfg.accent_name(hexv)} {hexv}"
                         + ("（当前使用）" if on else "点击切换"))
        lb = getattr(self, "lb_accent", None)
        if lb is not None:
            lb.setText(f"当前：{cfg.accent_name(cur)} {cur}")

    def _refresh_toggles(self):
        """换高亮色后让设置页里所有自绘开关**立刻**重画。

        轨道色是 paintEvent 里现取的，但 Qt 不会因为「某个模块级变量变了」就自动重绘 ——
        不显式 update() 的话要等鼠标划过才变色，用户会以为「这个开关没跟着变」。
        """
        for sw in self.findChildren(ToggleSwitch):
            sw.update()

    def _refresh_backdrop_hint(self):
        mode = self.s.appearance.get("mode")
        self.ap_hint.setText(self.DARK_HINT if mode != "磨砂玻璃" else self.GLASS_HINT)

    def _preview_opacity(self, val):
        """拖动时实时预览窗口透明度（不立即写盘，避免频繁 IO）。"""
        self.op_val.setText(f"{val}%")
        mw = self.parent()
        if mw is not None and hasattr(mw, "setWindowOpacity"):
            try:
                mw.setWindowOpacity(val / 100.0)
            except Exception:
                pass

    def _commit_opacity(self):
        """松手时落到设置并持久化。"""
        self.s.set_window_opacity(self.op_slider.value() / 100.0)

    def _apply_appearance(self, *_):
        self.s.set_appearance(self.ap_mode.currentText(), self.ap_level.currentText())
        # 系统级模糊在 Qt 窗口上无法透出（实测见 veil.py 顶部），这里只作能力探测记录
        import backdrop
        self._backdrop_probe = backdrop.auto_apply(self)
        if self.on_changed:
            self.on_changed()
        self._refresh_backdrop_hint()

    # ---------- 界面语言（v1.32.0 反馈 3） ----------
    def _apply_language(self, *_):
        """换界面语言：落盘 → 换 i18n 当前语言 → 让主窗重建界面。

        ⚠ 两件事必须按这个顺序做，且**只在这里做**：
        1. 先 `i18n.set_lang()`，再 `on_changed()` —— 主窗重建时会读 `i18n.tr()`，
           顺序反了就会用旧语言重建一遍、再也没人触发第二次刷新。
        2. 重建走的是主窗那一个入口（`_apply_settings`）。本项目 v1.27.0 踩过
           「面板被 deleteLater 时把运行中的 QThread 一起销毁 → 进程 abort」的坑，
           刷新界面**绝不能**在设置页里自己再写一套重建逻辑。
        """
        code = self.ap_lang.currentData() or i18n.DEFAULT_LANG
        self.s.set_appearance(language=code)
        i18n.set_lang(code)
        applog.log("[设置] 界面语言切换为 %s（%s）" % (code, i18n.cn_name(code)))
        if self.on_changed:
            self.on_changed()
        # 设置窗自己也要跟着重建导航（否则左侧还是旧语言的页名）
        self._rebuild_nav_buttons()
        self._show(self._current_key)
        self._refresh_lang_hint()

    def _refresh_lang_hint(self):
        lb = getattr(self, "ap_lang_hint", None)
        if lb is None:
            return
        code = i18n.get_lang()
        if code == i18n.BASE_LANG:
            lb.setText("界面语言：简体中文（基准语言）。切换后立即生效，无需重启。")
            lb.setStyleSheet("color:#a2967f;font-size:11px;")
            return
        note = ("界面语言已切到 %s（%s）。导航与常用动作已本地化；"
                "算法说明、免责声明等业务细节仍保留中文原文 —— "
                "本项目界面文案量很大，逐条机器翻译反而会误导。" % (i18n.cn_name(code), code))
        if i18n.is_rtl(code):
            note += "　⚠ 该语言从右往左书写，但本软件版面仍是左起 —— 只译文字、未做镜像。"
        lb.setText(note)
        lb.setStyleSheet("color:#8c8071;font-size:11px;")

    # ---------- 演员刮削 ----------
    def _build_scraper(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        sc = self.s.scraper

        # 总开关 + 数据源（合并为一组，压缩竖向高度）
        g0 = QGroupBox("演员刮削数据源（自上而下依次尝试，命中后补其缺失字段）")
        g0v = QVBoxLayout(g0)
        g0v.setSpacing(8)
        self.sc_enabled = ToggleSwitch(checked=bool(sc.get("enabled")))
        self.sc_enabled.toggled.connect(lambda c: self.s.set_scraper(enabled=c))
        g0v.addWidget(self._row("启用演员刮削（补齐演员头像 / 别名 / 生日 / 简介）", self.sc_enabled))
        rf = QWidget()
        rfh = QHBoxLayout(rf)
        rfh.setContentsMargins(0, 0, 0, 0)
        self.sc_stats = QLabel("—")
        self.sc_stats.setStyleSheet("color:#a2967f;font-size:11px;")
        self.sc_stats.setWordWrap(True)
        rfh.addWidget(self.sc_stats, 1)
        refresh = QPushButton("刷新统计")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self._refresh_scraper_stats)
        rfh.addWidget(refresh)
        g0v.addWidget(rf)
        self.src_list = QListWidget()
        self.src_list.setSelectionMode(QAbstractItemView.NoSelection)   # 点「测试」不再整行变红
        self.src_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.src_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.src_list.setSpacing(2)
        g0v.addWidget(self.src_list)
        self._rebuild_source_list()
        srcbtns = QWidget()
        sbh = QHBoxLayout(srcbtns)
        sbh.setContentsMargins(0, 0, 0, 0)
        test_all = QPushButton("测试全部数据源")
        test_all.setObjectName("Ghost")
        test_all.clicked.connect(self._test_all_sources)
        sbh.addWidget(test_all)
        sbh.addStretch(1)
        g0v.addWidget(srcbtns)
        self.src_hint = QLabel("提示：minnano-av 面向日本 AV 女优（日文名检索）；IMDB 面向普通影视演员（英文名检索）；"
                              "无法直连 minnano-av 时在下方填写代理。")
        self.src_hint.setStyleSheet("color:#a2967f;font-size:11px;")
        self.src_hint.setWordWrap(True)
        g0v.addWidget(self.src_hint)
        v.addWidget(g0)

        # 策略
        g2 = QGroupBox("刮削策略")
        g2v = QVBoxLayout(g2)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(3)
        # v1.22.0（反馈 1）：`overwrite` / `only_no_photo` 两个开关从「策略」里移除 ——
        # 二者由下方「刮削模式」统一决定（全量 / 增量 / 补齐），避免两处语义打架。
        # 这里只保留「补齐哪些字段」「是否下载头像」这类与模式正交的选项。
        for i, (key, label, default) in enumerate((
                ("fill_alias", "补齐 别名 / 爱称", True),
                ("fill_birthday", "补齐 生日（数据源不提供时留空）", True),
                ("fill_bio", "补齐 简介（尺寸 / 出身地 / 事务所等）", True),
                ("download_photo", "下载演员头像到本地", True))):
            sw = ToggleSwitch(checked=bool(sc.get(key, default)))
            sw.toggled.connect(lambda c, k=key: self.s.set_scraper(**{k: c}))
            grid.addWidget(self._row(label, sw), i // 2, i % 2)
        g2v.addLayout(grid)

        nf = QGridLayout()
        nf.setHorizontalSpacing(14)
        nf.setVerticalSpacing(4)
        self.sc_delay = QSpinBox()
        self.sc_delay.setRange(0, 10000)
        self.sc_delay.setSingleStep(100)
        self.sc_delay.setSuffix(" 毫秒")
        self.sc_delay.setValue(int(sc.get("delay_ms", 900)))
        self.sc_delay.valueChanged.connect(lambda x: self.s.set_scraper(delay_ms=x))
        self.sc_timeout = QSpinBox()
        self.sc_timeout.setRange(5, 120)
        self.sc_timeout.setSuffix(" 秒")
        self.sc_timeout.setValue(int(sc.get("timeout", 15)))
        self.sc_timeout.valueChanged.connect(lambda x: self.s.set_scraper(timeout=x))
        self.sc_retry = QSpinBox()
        self.sc_retry.setRange(0, 3)
        self.sc_retry.setSuffix(" 次")
        self.sc_retry.setValue(int(sc.get("retry", 1)))
        self.sc_retry.valueChanged.connect(lambda x: self.s.set_scraper(retry=x))
        self.sc_limit = QSpinBox()
        self.sc_limit.setRange(0, 9999)
        self.sc_limit.setSuffix(" 人（0 = 不限）")
        self.sc_limit.setValue(int(sc.get("limit", 0)))
        self.sc_limit.valueChanged.connect(lambda x: self.s.set_scraper(limit=x))
        self.sc_proxy = QLineEdit(sc.get("proxy") or "")
        self.sc_proxy.setPlaceholderText("可留空；例如 http://127.0.0.1:7890")
        self.sc_proxy.editingFinished.connect(
            lambda: self.s.set_scraper(proxy=self.sc_proxy.text().strip()))
        self.sc_dir = QLineEdit(sc.get("photo_dir") or "")
        self.sc_dir.setPlaceholderText(self.s.scraper_photo_dir())
        self.sc_dir.editingFinished.connect(
            lambda: self.s.set_scraper(photo_dir=self.sc_dir.text().strip()))
        dirbtn = QPushButton("选择目录")
        dirbtn.setObjectName("Ghost")
        dirbtn.clicked.connect(self._pick_photo_dir)
        dirw = QWidget()
        dirh = QHBoxLayout(dirw)
        dirh.setContentsMargins(0, 0, 0, 0)
        dirh.addWidget(self.sc_dir, 1)
        dirh.addWidget(dirbtn)
        # 6 项参数排成 2 列网格（3 行），显著压缩竖向高度
        for i, (lab, wid) in enumerate((
                ("请求间隔", self.sc_delay), ("请求超时", self.sc_timeout),
                ("失败重试", self.sc_retry), ("单次上限", self.sc_limit),
                ("代理", self.sc_proxy), ("头像缓存目录", dirw))):
            r, c = i // 2, (i % 2) * 2
            nf.addWidget(QLabel(lab), r, c)
            nf.addWidget(wid, r, c + 1)
        g2v.addLayout(nf)
        v.addWidget(g2)

        # 执行：四种刮削模式（v1.22.0 反馈 1 —— 全量 / 增量 / 补齐 / 修复）
        g3 = QGroupBox("执行")
        g3v = QVBoxLayout(g3)
        self._mode_specs = (
            ("full", "全量刮削",
             "全部重新刮削：对**所有**演员强制覆盖已有信息（耗时最久，会覆盖既有资料）"),
            ("incremental", "增量刮削",
             "增量刮削：只处理**还没刮削过**（无头像）的演员，已有资料不动"),
            ("fill", "补齐信息",
             "补齐信息：对**资料不全**（缺头像 / 别名 / 简介）的演员补齐缺失字段，不覆盖已有"),
            ("repair", "修复历史资料",
             "修复历史资料：只对旧版本写坏的垃圾记录强制覆盖重刮"),
        )
        modehint = QLabel("刮削模式（点哪个执行哪个）：")
        modehint.setStyleSheet("color:#a2967f;font-size:11px;")
        g3v.addWidget(modehint)
        moderow = QWidget()
        mh = QHBoxLayout(moderow)
        mh.setContentsMargins(0, 0, 0, 0)
        mh.setSpacing(8)
        self.mode_btns = {}
        for key, label, tip in self._mode_specs:
            b = QPushButton(label)
            b.setObjectName("Primary" if key in ("full", "repair") else "Ghost")
            b.setToolTip(rich(tip))
            b.clicked.connect(lambda _c, k=key: self._run_mode(k))
            mh.addWidget(b)
            self.mode_btns[key] = b
        mh.addStretch(1)
        self.sc_stop = QPushButton("停止")
        self.sc_stop.setObjectName("Ghost")
        self.sc_stop.setEnabled(False)
        self.sc_stop.clicked.connect(self._stop_scrape)
        mh.addWidget(self.sc_stop)
        g3v.addWidget(moderow)
        self.sc_mode_hint = QLabel("")
        self.sc_mode_hint.setStyleSheet("color:#a2967f;font-size:11px;")
        self.sc_mode_hint.setWordWrap(True)
        g3v.addWidget(self.sc_mode_hint)
        self.sc_prog = QProgressBar()
        self.sc_prog.setRange(0, 100)
        self.sc_prog.setValue(0)
        g3v.addWidget(self.sc_prog)
        self.sc_log = QPlainTextEdit()
        self.sc_log.setReadOnly(True)
        self.sc_log.setFixedHeight(48)
        self.sc_log.setPlaceholderText("刮削日志…")
        g3v.addWidget(self.sc_log)
        note = QLabel("说明：仅补齐演员资料并下载头像，不修改任何媒体文件；遵守目标站点 robots / 使用条款，"
                      "间隔过小可能被限流。")
        note.setStyleSheet("color:#a2967f;font-size:11px;")
        note.setWordWrap(True)
        g3v.addWidget(note)
        v.addWidget(g3)

        self._refresh_scraper_stats()
        v.addStretch(1)
        return page

    def _rebuild_source_list(self):
        self.src_list.clear()
        sc = self.s.scraper
        info = {x["key"]: x for x in cfg.SCRAPER_SOURCES}
        for key in sc.get("sources", []):
            it = info.get(key, {"key": key, "name": key, "desc": ""})
            li = QListWidgetItem(self.src_list)
            li.setData(Qt.UserRole, key)          # 便于按行反查数据源 key
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(6, 4, 6, 4)
            lab = QLabel(f"{it['name']}　{it.get('desc', '')}")
            # v1.13.0（反馈 2）：描述原来是单行且被限宽裁掉尾巴（「…专属头」）。
            # 改为允许换行到第 2 行 + Ignored 水平策略（长描述只占剩余宽度，不挤右侧按钮）。
            lab.setWordWrap(True)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            lab.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            h.addWidget(lab, 1)
            up = compact_button("↑", 28, 28, "上移")
            up.clicked.connect(lambda _c, k=key: self._move_source(k, -1))
            down = compact_button("↓", 28, 28, "下移")
            down.clicked.connect(lambda _c, k=key: self._move_source(k, 1))
            tst = compact_button("测试", 52, 28, "测试该数据源连通性")
            tst.clicked.connect(lambda _c, k=key: self._test_source(k))
            res = QLabel("—")
            res.setObjectName("SrcTestResult")
            res.setFixedWidth(56)
            res.setStyleSheet("color:#9b8e7a;font-size:11px;")
            sw = ToggleSwitch(checked=bool((sc.get("sources_enabled") or {}).get(key, True)))
            sw.toggled.connect(lambda c, k=key: self._toggle_source(k, c))
            h.addWidget(up)
            h.addWidget(down)
            h.addWidget(tst)
            h.addWidget(res)
            h.addWidget(sw)
            li.setSizeHint(QSize(row.sizeHint().width(), SRC_ROW_H))
            self.src_list.addItem(li)
            self.src_list.setItemWidget(li, row)
            self._src_rows[key] = res
        n = self.src_list.count()
        self.src_list.setFixedHeight(max(64, SRC_ROW_H * n + 8))

    def _move_source(self, key, delta):
        self.s.move_scraper_source(key, delta)
        self._rebuild_source_list()

    def _toggle_source(self, key, checked):
        en = dict(self.s.scraper.get("sources_enabled") or {})
        en[key] = bool(checked)
        self.s.set_scraper(sources_enabled=en)

    def _pick_photo_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择演员头像缓存目录")
        if d:
            self.sc_dir.setText(d)
            self.s.set_scraper(photo_dir=d)

    def _refresh_scraper_stats(self):
        try:
            st = db.scraper_stats()
        except Exception as e:
            self.sc_stats.setText(f"统计失败：{e}")
            return
        self._scraper_stats = st
        self.sc_stats.setText(
            f"演员 {st['total']} 人　·　已有头像 {st['photo']}　·　已有生日 {st['birthday']}　·　"
            f"已有别名 {st['alias']}　·　已刮削 {st['scraped']}　·　"
            f"待修复 {st.get('repair', 0)}")
        n = int(st.get("repair", 0) or 0)
        if hasattr(self, "sc_repair"):
            self.sc_repair.setEnabled(n > 0)
            self.sc_repair.setText(f"修复历史资料（重新刮削 {n} 人）")
            self.sc_repair_hint.setText(rich(
                "这些演员的资料被旧版本误写入了站点样板/HTML 残片乱码（meta/bio 命中特征词），"
                "需强制覆盖重刮清掉。注：数据源本就不提供生日/三围的演员属正常缺失，不算待修复。"
                "点上面的按钮会**强制覆盖**重刮这批人（需联网 / 代理）。"
                if n else "没有需要修复的历史资料。"))

    def _log(self, text):
        self.sc_log.appendPlainText(text)

    def _test_source(self, key):
        self._log(f"[测试] {scraper_mod.SOURCE_NAMES.get(key, key)} …")
        lbl = self._src_rows.get(key)
        if lbl is not None:
            lbl.setText("测试中…")
            lbl.setStyleSheet("color:#d4af37;font-size:11px;")
        w = TestSourceWorker(key, self.sc_proxy.text().strip(), int(self.sc_timeout.value()))
        w.done.connect(self._on_test_done)
        w.start()
        if not hasattr(self, "_test_workers"):
            self._test_workers = []
        self._test_workers.append(w)

    def _test_all_sources(self):
        for key in self.s.scraper.get("sources", []):
            self._test_source(key)

    def _on_test_done(self, key, res):
        name = scraper_mod.SOURCE_NAMES.get(key, key)
        self._log(f"[测试] {name}：{'可用' if res.get('ok') else '不可用'} — "
                  f"{res.get('msg')} （{res.get('ms')} ms）")
        lbl = self._src_rows.get(key)
        if lbl is not None:
            ok = bool(res.get("ok"))
            lbl.setText("可用" if ok else "不可用")
            lbl.setStyleSheet("color:#6fae6f;font-size:11px;" if ok
                              else "color:#e07a6a;font-size:11px;")

    def _scrape_opts(self):
        """当前配置好的刮削参数（含数据源、头像目录）。"""
        sc = dict(self.s.scraper)
        sources = self.s.scraper_sources()
        if not sources:
            return None
        sc["sources"] = sources
        sc["photo_dir"] = self.s.scraper_photo_dir()
        return sc

    def _run_mode(self, mode):
        """四种刮削模式统一入口（v1.22.0 反馈 1）。

        full       全量刮削：所有人强制覆盖（会覆盖既有资料，耗时最久）
        incremental 增量刮削：仅「还没刮削（无头像）」的演员，已有资料不动
        fill        补齐信息：缺头像/别名/简介的演员，只补缺失字段、不覆盖已有
        repair      修复历史资料：只强制覆盖重刮旧版写坏的样板/HTML 垃圾记录
        """
        if getattr(self, "_scrape_worker", None) and self._scrape_worker.isRunning():
            QMessageBox.information(self, "提示", "刮削正在进行中。")
            return
        sc = self._scrape_opts()
        if sc is None:
            QMessageBox.warning(self, "提示", "请至少启用一个数据源。")
            return

        if mode == "full":
            people = db.people_for_scrape(only_no_photo=False, limit=0)
            if not people:
                QMessageBox.information(self, "提示", "没有可刮削的演员。")
                return
            if QMessageBox.question(
                self, "全量刮削",
                rich(f"将**强制覆盖重刮全部 {len(people)} 位演员**的资料（含头像）。\n"
                     f"会联网请求数据源，间隔 {sc.get('delay_ms')}ms，"
                     + (f"代理 {sc.get('proxy')}。" if sc.get('proxy') else "当前未配置代理。")
                     + "\n\n会覆盖既有资料，只改演员、不动媒体文件。是否继续？")
            ) != QMessageBox.Yes:
                return
            sc["overwrite"] = True
            sc["only_no_photo"] = False
            sc["only_missing"] = False
            title = f"开始全量刮削：共 {len(people)} 人（强制覆盖）"

        elif mode == "incremental":
            people = db.people_for_scrape(only_no_photo=True, limit=0)
            if not people:
                QMessageBox.information(self, "提示", "没有「还没刮削（无头像）」的演员。")
                return
            sc["overwrite"] = False
            sc["only_no_photo"] = True
            sc["only_missing"] = True
            title = f"开始增量刮削：共 {len(people)} 人（仅未刮削）"

        elif mode == "fill":
            people = db.people_needing_fill()
            if not people:
                QMessageBox.information(self, "提示", "没有需要补齐信息的演员。")
                return
            sc["overwrite"] = False
            sc["only_no_photo"] = False
            sc["only_missing"] = True
            title = f"开始补齐信息：共 {len(people)} 人（只补缺失字段）"

        elif mode == "repair":
            people = db.people_needing_repair()
            if not people:
                QMessageBox.information(self, "提示", "没有需要修复的历史资料。")
                return
            if QMessageBox.question(
                self, "修复历史资料",
                f"将强制覆盖重刮 {len(people)} 位演员的资料（含头像）。\n"
                f"会联网请求数据源，间隔 {sc.get('delay_ms')}ms，"
                + (f"代理 {sc.get('proxy')}。" if sc.get('proxy') else "当前未配置代理。")
                + "\n\n只改演员资料，不动任何媒体文件。是否继续？"
            ) != QMessageBox.Yes:
                return
            sc["overwrite"] = True
            sc["only_no_photo"] = False
            sc["only_missing"] = False
            title = f"开始修复：共 {len(people)} 人（强制覆盖）"
        else:
            return

        self._run_scrape(people, sc, title)

    def _start_scrape(self):
        if getattr(self, "_scrape_worker", None) and self._scrape_worker.isRunning():
            QMessageBox.information(self, "提示", "刮削正在进行中。")
            return
        sc = self._scrape_opts()
        if sc is None:
            QMessageBox.warning(self, "提示", "请至少启用一个数据源。")
            return
        people = db.people_for_scrape(only_no_photo=bool(sc.get("only_no_photo", True)),
                                      limit=0)
        limit = int(sc.get("limit", 0) or 0)
        if limit > 0:
            people = people[:limit]
        if not people:
            QMessageBox.information(self, "提示", "没有需要刮削的演员（可关闭「只处理还没有头像的演员」再试）。")
            return
        self._run_scrape(people, sc,
                         f"开始刮削：共 {len(people)} 人，数据源 {' → '.join(sc['sources'])}，"
                         f"间隔 {sc.get('delay_ms')}ms，超时 {sc.get('timeout')}s"
                         + (f"，代理 {sc.get('proxy')}" if sc.get("proxy") else ""))

    def _start_repair_dead(self):  # 废弃：统一入口见 _run_mode（v1.22.0）
        """修复历史资料：强制覆盖、不限「只处理无头像」，专治旧版写坏的 meta。

        v1.11.1 背景：v1.10.0 的解析器把 `<head>` 里 og:description 的站点样板文案
        写进了 meta/bio（真机 72/108 条），并漏了生日 → 演员卡「出生/身高/三围/胸围」
        全是「—」。解析器修好后，这批历史记录只能重刮才能补回；又因为
        「覆盖已有信息」「只处理无头像」默认是关/开的，走普通刮削永远碰不到他们，
        所以这里单独给一个强制覆盖的入口。
        """
        if getattr(self, "_scrape_worker", None) and self._scrape_worker.isRunning():
            QMessageBox.information(self, "提示", "刮削正在进行中。")
            return
        sc = self._scrape_opts()
        if sc is None:
            QMessageBox.warning(self, "提示", "请至少启用一个数据源。")
            return
        people = db.people_needing_repair()
        if not people:
            QMessageBox.information(self, "提示", "没有需要修复的历史资料。")
            return
        if QMessageBox.question(
                self, "修复历史资料",
                f"将强制覆盖重刮 {len(people)} 位演员的资料（含头像）。\n"
                f"会联网请求数据源，间隔 {sc.get('delay_ms')}ms，"
                + (f"代理 {sc.get('proxy')}。" if sc.get("proxy") else "当前未配置代理。")
                + "\n\n只改演员资料，不动任何媒体文件。是否继续？"
        ) != QMessageBox.Yes:
            return
        sc["overwrite"] = True          # 关键：否则 meta 与旧字段不会被刷新
        sc["only_no_photo"] = False
        self._run_scrape(people, sc, f"开始修复：共 {len(people)} 人（强制覆盖）")

    def _run_scrape(self, people, sc, title):
        self.sc_log.clear()
        self._log(title)
        applog.log(f"刮削开始：{title} 人数={len(people)} 源={sc.get('sources')} "
                   f"覆盖={sc.get('overwrite')}")
        self.sc_prog.setRange(0, len(people))
        self.sc_prog.setValue(0)
        for _b in self.mode_btns.values():
            _b.setEnabled(False)
        self.sc_stop.setEnabled(True)
        self._scrape_worker = ScrapeWorker(people, sc)
        self._scrape_worker.progress.connect(self._on_scrape_progress)
        self._scrape_worker.done.connect(self._on_scrape_done)
        self._scrape_worker.start()

    def _stop_scrape(self):
        w = getattr(self, "_scrape_worker", None)
        if w and w.isRunning():
            w.stop()
            self._log("[停止] 已请求停止，等待当前请求结束…")
            self.sc_stop.setEnabled(False)

    def _on_scrape_progress(self, i, total, name, status):
        self.sc_prog.setValue(i)
        self._log(f"[{i}/{total}] {name} — {status}")

    def _on_scrape_done(self, stats):
        for _b in self.mode_btns.values():
            _b.setEnabled(True)
        self.sc_stop.setEnabled(False)
        self.sc_prog.setValue(self.sc_prog.maximum())
        self._log(f"完成：成功 {stats.get('ok', 0)} · 未找到 {stats.get('notfound', 0)} · "
                  f"失败 {stats.get('failed', 0)} · 下载头像 {stats.get('photo', 0)} · "
                  f"补齐字段 {stats.get('fields', 0)}")
        applog.log(f"刮削完成：成功 {stats.get('ok', 0)} / 未找到 {stats.get('notfound', 0)} / "
                   f"失败 {stats.get('failed', 0)} / 头像 {stats.get('photo', 0)} / "
                   f"字段 {stats.get('fields', 0)}")
        for e in (stats.get("errors") or [])[:12]:
            self._log("  ! " + e)
            applog.log(f"刮削错误：{e}", "error")
        self._refresh_scraper_stats()
        if self.on_changed:
            self.on_changed()

    def closeEvent(self, e):
        w = getattr(self, "_scrape_worker", None)
        if w and w.isRunning():
            w.stop()
            w.wait(4000)
        for t in getattr(self, "_test_workers", []):
            if t.isRunning():
                t.wait(3000)
        # v1.18.0 反馈 98：关闭即停止刷新定时器
        if getattr(self, "_rt_timer", None) is not None:
            self._rt_timer.stop()
        super().closeEvent(e)

    def _build_service(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(14)

        # 媒体库（v1.12.0：只有这一份列表，全部由用户自己命名；无内置库、无「恢复」按钮）
        g1 = QGroupBox("媒体库")
        g1v = QVBoxLayout(g1)

        hint = QLabel("媒体库全部由你自己创建和命名 —— 软件不再自带任何内置库，"
                      "删除后也不会自动恢复。删除只影响库的配置与（可选的）索引记录，"
                      "磁盘上的视频文件不会动。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a2967f;font-size:11px;")
        g1v.addWidget(hint)

        form = QFormLayout()
        self.lib_name = QLineEdit()
        self.lib_name.setPlaceholderText("例如：我的电影 / Jav-VR")
        self.lib_kind = QComboBox()
        self.lib_kind.addItems(cfg.LIBRARY_KINDS)
        form.addRow("名称", self.lib_name)
        form.addRow("媒体类型", self.lib_kind)
        g1v.addLayout(form)

        self.path_list = QListWidget()
        self.path_list.setFixedHeight(110)
        self.path_list.currentRowChanged.connect(lambda _r: self._sync_default_path_btns())
        g1v.addWidget(QLabel("默认路径（可添加多个目录；顺序即扫描优先级，自上而下依次扫描）："))
        g1v.addWidget(self.path_list)
        pa = QWidget()
        pah = QHBoxLayout(pa)
        pah.setContentsMargins(0, 0, 0, 0)
        pah.setSpacing(6)
        add_path = QPushButton("添加路径")
        add_path.setObjectName("Ghost")
        add_path.clicked.connect(self._add_path)
        self.dp_up = compact_button("↑", 30, 30, "上移（提高扫描优先级）")
        self.dp_up.clicked.connect(lambda: self._move_default_path(-1))
        self.dp_down = compact_button("↓", 30, 30, "下移（降低扫描优先级）")
        self.dp_down.clicked.connect(lambda: self._move_default_path(1))
        add_lib = QPushButton("添加媒体库")
        add_lib.setObjectName("Primary")
        add_lib.clicked.connect(self._add_library)
        pah.addWidget(add_path)
        pah.addWidget(self.dp_up)
        pah.addWidget(self.dp_down)
        pah.addWidget(add_lib)
        pah.addStretch(1)
        g1v.addWidget(pa)
        self._sync_default_path_btns()

        self.lib_list = QListWidget()
        g1v.addWidget(QLabel("已配置的媒体库："))
        g1v.addWidget(self.lib_list)
        self._rebuild_lib_list()

        scan_all = QPushButton("扫描全部媒体库")
        scan_all.setObjectName("Primary")
        scan_all.clicked.connect(self._scan_all)
        g1v.addWidget(scan_all)
        # v1.14.0 反馈 7：扫描进度就地显示，**不再弹模态对话框** ——
        # 原来每扫完一个库就弹一个「扫描完成」窗口，设置窗口与主界面都被挡住不能操作。
        self.lib_status = QLabel("未在扫描。")
        self.lib_status.setStyleSheet("color:#a2967f;font-size:11px;")
        self.lib_status.setWordWrap(True)
        g1v.addWidget(self.lib_status)
        v.addWidget(g1)

        # 后台任务管理
        g2 = QGroupBox("后台任务管理")
        g2v = QVBoxLayout(g2)
        self.bg_switch = ToggleSwitch(checked=self.s.background.get("enabled", False))
        self.bg_switch.toggled.connect(lambda c: (self.s.background.__setitem__("enabled", c), self.s.save()))
        g2v.addWidget(self._row("启用后台任务（应用运行期间按计划自动扫描）", self.bg_switch))

        bf = QFormLayout()
        self.bg_lib = QComboBox()
        self.bg_lib.addItems(["（全部库）"] + self.s.library_names())
        if self.s.background.get("library"):
            idx = self.bg_lib.findText(self.s.background["library"])
            if idx >= 0:
                self.bg_lib.setCurrentIndex(idx)
        self.bg_lib.currentTextChanged.connect(
            lambda t: (self.s.background.__setitem__("library", "" if t == "（全部库）" else t), self.s.save()))
        self.bg_time = QTimeEdit()
        hh, mm_ = (self.s.background.get("time", "03:00") + ":00").split(":")[:2]
        self.bg_time.setTime(QTime(int(hh), int(mm_)))
        self.bg_time.timeChanged.connect(
            lambda t: (self.s.background.__setitem__("time", t.toString("HH:mm")), self.s.save()))
        self.bg_freq = QComboBox()
        self.bg_freq.addItems(["每天", "每周", "每月"])
        self.bg_freq.setCurrentText(self.s.background.get("frequency", "每天"))
        self.bg_freq.currentTextChanged.connect(
            lambda t: (self.s.background.__setitem__("frequency", t), self.s.save()))
        bf.addRow("媒体库", self.bg_lib)
        bf.addRow("扫描时间", self.bg_time)
        bf.addRow("扫描频率", self.bg_freq)
        g2v.addLayout(bf)
        v.addWidget(g2)

        v.addStretch(1)
        return page

    # ---------- 重复检测（v1.23.0，借鉴 NFO 画像矿工 nfo_profiler 的 dedupe 思路） ----------
    # ---------- 画像概览（v1.24.0 反馈 6） ----------
    def _build_insight(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(QLabel("统计范围"))
        self.ins_lib = QComboBox()
        self.ins_lib.setToolTip("决定这份画像统计哪一批作品：整个索引、只有收藏的，或某个媒体库")
        # v1.24.1（反馈 4）：itemData 统一为 (库名 or None, 是否只看收藏)
        self.ins_lib.addItem("（全部媒体库）", (None, False))
        self.ins_lib.addItem("★ 我的收藏", (None, True))
        self.ins_lib.setItemData(1, "只统计点过 ☆ 的作品 —— 看自己的口味画像更准",
                                 Qt.ToolTipRole)
        for n in self.s.library_names():
            self.ins_lib.addItem(n, (n, False))
        # v1.24.1：恢复上次选的统计范围（**在 connect 之前 setCurrentIndex**，否则会立刻触发重算）
        _ins = getattr(self.s, "insight", None) or {}
        _want = (str(_ins.get("scope") or "") or None, bool(_ins.get("favorites_only")))
        for _i in range(self.ins_lib.count()):
            if self._insight_scope(_i) == _want:
                self.ins_lib.setCurrentIndex(_i)
                break
        self.ins_lib.currentIndexChanged.connect(self._on_insight_scope)
        top.addWidget(self.ins_lib)
        self.ins_run = QPushButton("重新分析")
        self.ins_run.setObjectName("Primary")
        self.ins_run.clicked.connect(self._run_insight)
        top.addWidget(self.ins_run)
        self.ins_bar = QProgressBar()
        self.ins_bar.setRange(0, 100)
        self.ins_bar.setValue(0)
        self.ins_bar.setFixedWidth(180)
        top.addWidget(self.ins_bar)
        self.ins_status = QLabel("尚未分析。进页面会自动算一次（4.8 万条约 1.5 秒）。")
        self.ins_status.setStyleSheet("color:#a2967f;font-size:11px;")
        top.addWidget(self.ins_status, 1)
        v.addLayout(top)

        # 一句话画像
        g0 = QGroupBox("一句话画像")
        g0v = QVBoxLayout(g0)
        self.ins_line = QLabel("—")
        self.ins_line.setWordWrap(True)
        self.ins_line.setStyleSheet("color:#e8d9b6;font-size:13px;")
        g0v.addWidget(self.ins_line)
        v.addWidget(g0)

        # 雷达 + 概览数字
        mid = QHBoxLayout()
        mid.setSpacing(12)
        g1 = QGroupBox("八维偏好雷达")
        g1v = QVBoxLayout(g1)
        self.ins_radar = RadarChart()
        g1v.addWidget(self.ins_radar, 1)
        self.ins_radar_tip = QLabel("—")
        self.ins_radar_tip.setWordWrap(True)
        self.ins_radar_tip.setStyleSheet("color:#8c8071;font-size:11px;")
        g1v.addWidget(self.ins_radar_tip)
        mid.addWidget(g1, 3)

        g2 = QGroupBox("概览")
        g2v = QVBoxLayout(g2)
        self.ins_ov = QLabel("—")
        self.ins_ov.setWordWrap(True)
        self.ins_ov.setTextFormat(Qt.RichText)
        self.ins_ov.setStyleSheet("color:#c9bda7;font-size:12px;")
        g2v.addWidget(self.ins_ov)
        g2v.addStretch(1)
        mid.addWidget(g2, 2)
        v.addLayout(mid)

        # 高频榜
        g3 = QGroupBox("高频榜")
        g3v = QGridLayout(g3)
        g3v.setHorizontalSpacing(18)
        self.ins_lists = {}
        for col, key in enumerate(("tags", "actors", "directors", "studios", "series")):
            lb = QLabel({"tags": "标签", "actors": "演员", "directors": "导演",
                         "studios": "片商", "series": "系列"}[key])
            lb.setStyleSheet("color:#d4af37;font-size:12px;font-weight:bold;")
            g3v.addWidget(lb, 0, col)
            body = QLabel("—")
            body.setWordWrap(True)
            body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            body.setStyleSheet("color:#b9ad97;font-size:11px;"
                               "font-family:Consolas,'Courier New',monospace;")
            g3v.addWidget(body, 1, col)
            self.ins_lists[key] = body
        v.addWidget(g3)

        # 分布 + 共现
        g4 = QGroupBox("分布")
        g4v = QGridLayout(g4)
        g4v.setHorizontalSpacing(18)
        self.ins_dist = {}
        for col, key in enumerate(("画质", "评分", "时长", "年份", "入库月")):
            lb = QLabel(key)
            lb.setStyleSheet("color:#d4af37;font-size:12px;font-weight:bold;")
            g4v.addWidget(lb, 0, col)
            body = QLabel("—")
            body.setWordWrap(True)
            body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            body.setStyleSheet("color:#b9ad97;font-size:11px;"
                               "font-family:Consolas,'Courier New',monospace;")
            g4v.addWidget(body, 1, col)
            self.ins_dist[key] = body
        v.addWidget(g4)

        g5 = QGroupBox("标签共现（老是一起出现的两个标签）")
        g5v = QVBoxLayout(g5)
        self.ins_cooc = QLabel("—")
        self.ins_cooc.setWordWrap(True)
        self.ins_cooc.setStyleSheet("color:#b9ad97;font-size:11px;")
        g5v.addWidget(self.ins_cooc)
        v.addWidget(g5)

        v.addStretch(1)
        return page

    def _insight_scope(self, idx=None):
        """第 `idx` 项的 (库名, 是否只看收藏)；idx=None 取当前选中项。"""
        if idx is None:
            idx = self.ins_lib.currentIndex()
        data = self.ins_lib.itemData(idx)
        if isinstance(data, (tuple, list)) and len(data) == 2:
            return (data[0] or None), bool(data[1])
        return (data or None), False      # 兼容老配置里存成纯库名的写法

    def _on_insight_scope(self, *_):
        """换统计范围 → 记进偏好、作废旧结果并重算（否则页面还挂着上一个范围的画像）。"""
        lib, fav = self._insight_scope()
        self.s.set_insight_scope(lib, fav)      # v1.24.1：下次打开还是这个范围
        self._insight_data = {}
        self.ins_status.setText("统计范围已切换，正在重新分析…")
        self._run_insight()

    def _run_insight(self):
        w = self._insight_worker
        if w is not None and w.isRunning():
            self._insight_pending = True      # 换范围时上一次还在跑 → 记下来，跑完再补一次
            return
        self._insight_pending = False
        lib, fav = self._insight_scope()
        self.ins_run.setEnabled(False)
        self.ins_bar.setRange(0, 0)              # 忙碌态
        self.ins_status.setText(f"正在分析「{self.ins_lib.currentText()}」…")
        self._insight_worker = PortraitWorker(lib, fav, parent=self)
        self._insight_worker.progress.connect(self._on_insight_progress)
        self._insight_worker.done.connect(self._on_insight_done)
        self._insight_worker.start()

    def _on_insight_progress(self, i, n, msg):
        self.ins_status.setText(msg)
        if n:
            self.ins_bar.setRange(0, 100)
            self.ins_bar.setValue(int(i * 100 / max(n, 1)))

    def _on_insight_done(self, data):
        self.ins_run.setEnabled(True)
        self.ins_bar.setRange(0, 100)
        if getattr(self, "_insight_pending", False):
            # 分析期间用户又换了范围 → 这次结果作废，按当前范围再跑一次
            self._insight_pending = False
            QTimer.singleShot(0, self._run_insight)
            return
        if not data or data.get("error"):
            self.ins_bar.setValue(0)
            self.ins_status.setText(f"分析失败：{(data or {}).get('error', '未知错误')}")
            return
        self._insight_data = data
        self.ins_bar.setValue(100)
        ov = data["overview"]
        self.ins_status.setText(
            f"分析完成：{ov['scope']} · {ov['media']:,} 部作品 · "
            "换范围会立刻重算。")
        self.ins_line.setText(data.get("line") or "—")
        self.ins_radar.set_data(data.get("radar"))
        self.ins_radar_tip.setText("　".join(
            f"{lb} {int(round(v * 100))}%（{det}）" for lb, v, det in data.get("radar", [])))
        fav_txt = ""
        if ov["favorite"] and ov["favorite"] < ov["media"]:
            fav_txt = f"（其中收藏 {ov['favorite']:,} 部）"
        self.ins_ov.setText(
            f"统计范围：<b>{ov['scope']}</b><br>"
            f"作品总数：<b>{ov['media']:,}</b> 部{fav_txt}<br>"
            f"演员：<b>{ov['actors']:,}</b> 位 / {ov['actor_links']:,} 条关联<br>"
            f"导演：<b>{ov['directors']:,}</b> 位 / {ov['director_links']:,} 条关联<br>"
            f"系列：<b>{ov['series']:,}</b> 个 · 片商：<b>{ov['studios']:,}</b> 家<br>"
            f"不同标签：<b>{ov['tags']:,}</b> 个<br>"
            f"平均评分：<b>{ov['avg_rating']:.2f}</b>（10 分制）<br>"
            f"累计时长：<b>{insight_mod.human_hours(ov['total_hours'])}</b><br>"
            f"文件总体积：<b>{insight_mod.human_size(ov['total_size'])}</b>")
        for key, body in self.ins_lists.items():
            body.setText(self._bar_lines(data.get(key) or [], show_bar=True))
        for key, body in self.ins_dist.items():
            body.setText(self._bar_lines((data.get("dist") or {}).get(key) or []))
        # cooc 是 [( (tagA, tagB), 次数 )]，键为元组，不是三元组
        cooc = data.get("cooc") or []
        parts = []
        for item in cooc:
            pair, cnt = item[0], item[1]
            if isinstance(pair, (tuple, list)) and len(pair) >= 2:
                parts.append(f"「{pair[0]}」+「{pair[1]}」 {int(cnt):,} 部")
        self.ins_cooc.setText("　".join(parts) or "—")
        applog.log(f"[画像概览] {ov['scope']}：{ov['media']} 部作品分析完成")

    @staticmethod
    def _bar_lines(items, show_bar=True, limit=16):
        """把 [(名称, 计数)] 画成「文本 + █ 条」的简易条形图（不引图表库）。"""
        items = list(items)[:limit]
        if not items:
            return "—"
        top = max(c for _n, c in items) or 1
        lines = []
        for name, c in items:
            label = str(name)[:18].ljust(18)
            bar = ("  " + "█" * max(1, int(round(c / top * 12)))) if show_bar else ""
            lines.append(f"{label}{c:>7,}{bar}")
        return "\n".join(lines)

    # ---------- 智能推荐（v1.24.0 反馈 8） ----------
    def _build_smart(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(14)

        g1 = QGroupBox("推荐算法")
        g1v = QVBoxLayout(g1)
        hint = QLabel(rich(
            "「智能推荐」导航页按 **我的收藏的影片（标签 / 片商 / 系列）** 与 "
            "**演员库 / 导演库里收藏的演员与导演** 来推荐。\n"
            "· 普通智能算法：偏好向量 × IDF 加权余弦相似度 + MMR 去重；\n"
            "· AI 智能算法：在普通算法之上叠加**本地离线 AI** —— 内置标签共现联想；"
            "若本机有 Ollama（127.0.0.1:11434）则再让本地模型做语义扩词，全程不出网。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a2967f;font-size:11px;")
        g1v.addWidget(hint)

        self.rb_normal = QRadioButton("普通智能算法（向量相似度 + 去重）")
        self.rb_ai = QRadioButton("AI 智能算法（本地离线 AI 辅助）")
        self.rb_normal.setChecked(self.s.recommend.get("algo", "normal") != "ai")
        self.rb_ai.setChecked(self.s.recommend.get("algo", "normal") == "ai")
        self.rb_normal.toggled.connect(self._save_smart_prefs)
        self.rb_ai.toggled.connect(self._save_smart_prefs)
        g1v.addWidget(self.rb_normal)
        g1v.addWidget(self.rb_ai)

        self.ai_state = QLabel("—")
        self.ai_state.setWordWrap(True)
        self.ai_state.setStyleSheet("color:#8c8071;font-size:11px;")
        g1v.addWidget(self.ai_state)
        # v1.24.1（反馈 2）：按钮留引用 —— 检测期间要置灰并改文案，让「点了有反应」看得见
        self.ai_test = QPushButton("检测本地 AI 引擎")
        self.ai_test.setObjectName("Ghost")
        self.ai_test.setToolTip(f"探测 {rec_mod.OLLAMA_HOST} 上是否有可用的 Ollama（纯本地）")
        self.ai_test.clicked.connect(self._refresh_ai_state)
        g1v.addWidget(self.ai_test, alignment=Qt.AlignLeft)

        # v1.25.0（反馈 1）：默认用本机 Ollama，但**模型可以自己填**。
        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        mrow.addWidget(QLabel("调用模型"))
        self.ed_ai_model = QLineEdit()
        self.ed_ai_model.setPlaceholderText("留空 = 自动使用本机第一个模型")
        self.ed_ai_model.setToolTip(
            "填 Ollama 里的模型名（就是 `ollama list` 第一列那个名字，带标签）。\n"
            "例：qwen2.5:7b / llama3.1:8b / qwen3:4b / muse-glimmer:latest")
        self.ed_ai_model.setText(str(self.s.recommend.get("ai_model") or ""))
        self.ed_ai_model.editingFinished.connect(self._on_ai_model_edited)
        mrow.addWidget(self.ed_ai_model, 1)
        self.btn_ai_models = QPushButton("读取本机模型")
        self.btn_ai_models.setObjectName("Ghost")
        self.btn_ai_models.setToolTip("读取本机 Ollama 的模型清单（等价于命令行 `ollama list`）")
        self.btn_ai_models.clicked.connect(self._load_ai_models)
        mrow.addWidget(self.btn_ai_models)
        g1v.addLayout(mrow)
        self.cb_ai_model = QComboBox()
        self.cb_ai_model.setToolTip("读取到的本机模型；选一个即自动填入上面的输入框")
        self.cb_ai_model.addItem("（还没读取 —— 点右边「读取本机模型」）", "")
        self.cb_ai_model.currentIndexChanged.connect(self._pick_ai_model)
        g1v.addWidget(self.cb_ai_model)
        mhint = QLabel(rich(
            "**怎么填**：先启动 Ollama，然后在命令行执行 `ollama list` 查看已经安装的模型，"
            "把第一列的完整名字填进上面的输入框即可。\n"
            "**输入示例**：qwen2.5:7b　/　llama3.1:8b　/　qwen3:4b　/　"
            "gemma3:12b　/　muse-glimmer:latest　（冒号和标签都要带上）\n"
            "留空 = 自动使用本机第一个模型；填了但本机没装，会自动降级为内置联想，"
            "并在下面的检测结果里告诉你本机到底装了哪些。"))
        mhint.setWordWrap(True)
        mhint.setStyleSheet("color:#a2967f;font-size:11px;")
        g1v.addWidget(mhint)
        v.addWidget(g1)

        g2 = QGroupBox("推荐范围与偏好")
        g2v = QVBoxLayout(g2)
        row = QHBoxLayout()
        row.addWidget(QLabel("每次推荐"))
        self.sp_count = QSpinBox()
        self.sp_count.setRange(6, 120)
        self.sp_count.setValue(int(self.s.recommend.get("count", 24)))
        self.sp_count.valueChanged.connect(self._save_smart_prefs)
        row.addWidget(self.sp_count)
        row.addWidget(QLabel("部"))
        row.addSpacing(16)
        row.addWidget(QLabel("多样性"))
        self.sl_div = QSlider(Qt.Horizontal)
        self.sl_div.setRange(0, 90)
        self.sl_div.setValue(int(float(self.s.recommend.get("diversity", 0.5)) * 100))
        self.sl_div.setFixedWidth(180)
        self.sl_div.setToolTip("越大越不容易一整屏都是同一系列 / 同一演员的作品")
        self.sl_div.valueChanged.connect(self._save_smart_prefs)
        row.addWidget(self.sl_div)
        self.lb_div = QLabel("—")
        self.lb_div.setStyleSheet("color:#8c8071;font-size:11px;")
        row.addWidget(self.lb_div)
        row.addStretch(1)
        g2v.addLayout(row)

        # v1.25.0（反馈 3）：已经推荐过的，多少轮之内不再重复出现。
        rowr = QHBoxLayout()
        rowr.setSpacing(8)
        rowr.addWidget(QLabel("已经推荐的"))
        self.sp_rounds = QSpinBox()
        self.sp_rounds.setRange(0, 50)
        self.sp_rounds.setSuffix(" 轮")
        self.sp_rounds.setValue(int(self.s.recommend.get("no_repeat_rounds", 3)))
        self.sp_rounds.setToolTip(
            "最近这么多轮推荐过的作品，不再重复出现。\n"
            "每点一次「换一批」、或每次进「智能推荐」页 = 1 轮；0 = 不限制。")
        self.sp_rounds.valueChanged.connect(self._save_smart_prefs)
        rowr.addWidget(self.sp_rounds)
        rowr.addWidget(QLabel("内不再重复出现"))
        rowr.addSpacing(16)
        self.lb_hist = QLabel("—")
        self.lb_hist.setStyleSheet("color:#8c8071;font-size:11px;")
        rowr.addWidget(self.lb_hist)
        b_hist = QPushButton("清空推荐历史")
        b_hist.setObjectName("Ghost")
        b_hist.setToolTip("忘掉之前推荐过哪些作品；下次推荐从头开始（收藏仍然不会被推荐）")
        b_hist.clicked.connect(self._clear_smart_history)
        rowr.addWidget(b_hist)
        rowr.addStretch(1)
        g2v.addLayout(rowr)

        self.ck_tags = QCheckBox("结合收藏影片的标签 / 片商 / 系列")
        self.ck_actors = QCheckBox("结合演员库里收藏的演员")
        self.ck_directors = QCheckBox("结合导演库里收藏的导演")
        self.ck_watched = QCheckBox("排除已看过的（播放次数 > 0）")
        self.ck_urating = QCheckBox("把「用户评分 ≥ 8.5」的作品也算喜欢（弱信号）")
        for ck, key, dflt in ((self.ck_tags, "use_tags", True),
                              (self.ck_actors, "use_actors", True),
                              (self.ck_directors, "use_directors", True),
                              (self.ck_watched, "exclude_watched", True),
                              (self.ck_urating, "use_userrating", False)):
            ck.setChecked(bool(self.s.recommend.get(key, dflt)))
            ck.toggled.connect(self._save_smart_prefs)
            g2v.addWidget(ck)
        v.addWidget(g2)

        g3 = QGroupBox("向量编辑")
        g3v = QVBoxLayout(g3)
        h3 = QLabel("偏好向量的每一项都能手动调权重：加强 / 减弱 / 屏蔽 / 软排斥。"
                    "这是从 nfo_profiler 的同名功能借鉴来的。")
        h3.setWordWrap(True)
        h3.setStyleSheet("color:#a2967f;font-size:11px;")
        g3v.addWidget(h3)
        self.vec_count = QLabel("—")
        self.vec_count.setStyleSheet("color:#8c8071;font-size:11px;")
        g3v.addWidget(self.vec_count)
        row3 = QHBoxLayout()
        b_open = QPushButton("打开向量编辑…")
        b_open.setObjectName("Primary")
        b_open.clicked.connect(self._open_vector_editor)
        b_clr = QPushButton("清空全部权重")
        b_clr.setObjectName("Ghost")
        b_clr.clicked.connect(self._clear_vectors)
        row3.addWidget(b_open)
        row3.addWidget(b_clr)
        row3.addStretch(1)
        g3v.addLayout(row3)
        v.addWidget(g3)

        v.addStretch(1)
        QTimer.singleShot(0, self._refresh_ai_state)
        self._refresh_vector_count()
        self._refresh_hist_label()
        return page

    def _refresh_ai_state(self):
        """探测本机 Ollama（v1.24.1 反馈 2）。

        **为什么原来「没有反馈」**：进页面时会自动探一次并把结果显示出来，而点按钮走的
        是同一条同步探测 + 同一个 `setText` —— 结论一模一样，界面上一个字都不会变，
        用户点下去当然以为按钮坏了（还要白等 0.5 秒超时）。

        现在：先立刻写「正在检测…」并把按钮置灰（点击的即时反馈），探测丢到线程里跑，
        回来后带 **时间戳** 与明确的结论写出来 —— 就算结论和上次相同，时间戳也变了。
        """
        w = getattr(self, "_ai_worker", None)
        if w is not None and w.isRunning():
            return
        self.ai_state.setStyleSheet("color:#e8d27a;font-size:11px;")
        self.ai_state.setText(
            f"正在检测本地 AI 引擎…　探测 {rec_mod.OLLAMA_HOST}（最多等 1 秒）")
        self.ai_test.setEnabled(False)
        self.ai_test.setText("检测中…")
        self._ai_worker = AiProbeWorker()      # 不挂 parent：探测线程被销毁时才不会 abort
        self._ai_worker.done.connect(self._on_ai_probe)
        self._ai_worker.start()

    def _on_ai_probe(self, st):
        self.ai_test.setEnabled(True)
        self.ai_test.setText("检测本地 AI 引擎")
        st = st or {}
        eng = st.get("engine")
        ts = QTime.currentTime().toString("HH:mm:ss")
        if eng == "ollama":
            head = f"✅ 检测完成（{ts}）—— 引擎：<b>{html_esc(st.get('label'))}</b>"
            color = "#9ecf8a"
        elif eng == "error":
            head = f"❌ 检测失败（{ts}）—— 引擎：<b>未知</b>"
            color = "#e08a7a"
        else:
            head = f"⚠ 检测完成（{ts}）—— 未检测到本地 Ollama，当前引擎：<b>" \
                   f"{html_esc(st.get('label'))}</b>"
            color = "#e8d27a"
        self.ai_state.setStyleSheet(f"color:{color};font-size:11px;")
        self.ai_state.setText(f"{head}<br>{html_esc(st.get('detail'))}")
        applog.log(f"[AI 引擎检测] engine={eng} at {ts}")

    def _refresh_vector_count(self):
        n = len(db.vector_overrides())
        self.vec_count.setText(f"当前手动权重：{n} 条")

    def _save_smart_prefs(self, *_):
        self.lb_div.setText(f"λ={self.sl_div.value() / 100:.2f}")
        kw = dict(algo=("ai" if self.rb_ai.isChecked() else "normal"),
                  count=int(self.sp_count.value()),
                  use_tags=self.ck_tags.isChecked(),
                  use_actors=self.ck_actors.isChecked(),
                  use_directors=self.ck_directors.isChecked(),
                  exclude_watched=self.ck_watched.isChecked(),
                  use_userrating=self.ck_urating.isChecked(),
                  diversity=self.sl_div.value() / 100.0)
        # 用 getattr 兜一下：这两个控件是 v1.25.0 才加的，
        # 万一日后有人把它们的构造顺序挪到信号连接之后，也不该直接崩。
        ed = getattr(self, "ed_ai_model", None)
        if ed is not None:
            kw["ai_model"] = ed.text().strip()
        sp = getattr(self, "sp_rounds", None)
        if sp is not None:
            kw["no_repeat_rounds"] = int(sp.value())
        self.s.set_recommend(**kw)
        self._refresh_hist_label()

    # ---------- v1.25.0（反馈 1）：模型选择 ----------
    def _on_ai_model_edited(self):
        """输入框改完（回车 / 失焦）：落盘 + 重新检测，让下面的结论立刻反映新模型。"""
        self._save_smart_prefs()
        self._refresh_ai_state()

    def _load_ai_models(self):
        w = getattr(self, "_ai_models_worker", None)
        if w is not None and w.isRunning():
            return
        self.btn_ai_models.setEnabled(False)
        self.btn_ai_models.setText("读取中…")
        self._ai_models_worker = AiModelsWorker()
        self._ai_models_worker.done.connect(self._on_ai_models)
        self._ai_models_worker.start()

    def _on_ai_models(self, names):
        self.btn_ai_models.setEnabled(True)
        self.btn_ai_models.setText("读取本机模型")
        names = [str(x) for x in (names or []) if x]
        self.cb_ai_model.blockSignals(True)
        self.cb_ai_model.clear()
        if not names:
            self.cb_ai_model.addItem("（没读到模型：Ollama 没启动，或还没 pull 过任何模型）", "")
        else:
            self.cb_ai_model.addItem(f"本机已装 {len(names)} 个模型（点选即填入）", "")
            for nm in names:
                self.cb_ai_model.addItem(nm, nm)
        self.cb_ai_model.setCurrentIndex(0)
        self.cb_ai_model.blockSignals(False)
        self._refresh_ai_state()

    def _pick_ai_model(self, idx):
        nm = self.cb_ai_model.itemData(idx) if idx is not None and idx >= 0 else None
        if not nm:
            return
        self.ed_ai_model.setText(str(nm))
        self._on_ai_model_edited()

    # ---------- v1.25.0（反馈 3）：推荐历史 ----------
    def _refresh_hist_label(self):
        lb = getattr(self, "lb_hist", None)
        if lb is None:
            return
        n = len(self.s.smart_history or [])
        lb.setText(f"已记录 {n} 轮 / 当前避让 {len(self.s.recent_smart_ids())} 部"
                   if n else "还没有推荐记录")

    def _clear_smart_history(self):
        self.s.clear_smart_history()
        lb = getattr(self, "lb_hist", None)
        if lb is not None:
            lb.setText("已清空 —— 下次推荐从头开始")
        applog.log("[智能推荐] 已清空推荐历史")

    def _open_vector_editor(self):
        dlg = self._vector_dlg
        if dlg is None:
            dlg = VectorEditorDialog(self, on_saved=self._on_vectors_changed)
            self._vector_dlg = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_vectors_changed(self):
        self._refresh_vector_count()
        if self.on_changed:
            self.on_changed()          # 让主界面作废推荐缓存

    def _clear_vectors(self):
        if QMessageBox.question(self, "确认", "清空全部手动权重？"
                                "（只影响推荐，不动任何影片数据）") != QMessageBox.Yes:
            return
        db.clear_vector_overrides()
        self.s.clear_vector()
        self._on_vectors_changed()

    def _build_dedupe(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(14)

        g1 = QGroupBox("重复影片检测")
        g1v = QVBoxLayout(g1)
        # 注意：QLabel 不吃 Markdown，写 `**强调**` 会原样显示成星号（v1.24.0 出图时
        # 才发现）。要用强调就写成 HTML 并置 RichText。
        hint = QLabel(
            "按索引里的「番号 / 标题 + 年份」跨目录比对，找出「同一部片子在两个文件夹里各存了一份」。<br>"
            "· 每次点「开始检测」都会<b>先清空上次结果再重算</b>，并且默认<b>先校验磁盘上文件是否还在</b> ——"
            "已经删掉的副本不会再出现在结果里（这是「删了片子结果里还有」的根因）；<br>"
            "· 「可回收空间」= 每组保留体积最大的那一份后，其余副本的体积之和；<br>"
            "· 检测只读索引、不动任何磁盘文件，产出清单供你人工核对后再决定是否删除。<br>"
            "· 结果可以<b>展开</b>看每个副本的完整路径，<b>双击</b>任意一条即用资源管理器定位到该文件。")
        hint.setTextFormat(Qt.RichText)
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a2967f;font-size:11px;")
        g1v.addWidget(hint)

        # ---- v1.32.0（反馈 1）：算法模式（与「演员检测 / 标签优化」同一套写法）
        alg = QGroupBox("检测方式")
        algv = QVBoxLayout(alg)
        algv.setContentsMargins(10, 8, 10, 8)
        algv.setSpacing(6)
        arow = QWidget()
        arh = QHBoxLayout(arow)
        arh.setContentsMargins(0, 0, 0, 0)
        arh.setSpacing(14)
        self.dd_rb_normal = QRadioButton("普通算法（本地规则，秒出结果）")
        self.dd_rb_ai = QRadioButton("AI 算法（本地离线 AI 复核，较慢）")
        self.dd_rb_normal.setChecked(True)
        for rb in (self.dd_rb_normal, self.dd_rb_ai):
            arh.addWidget(rb)
        self.dd_fast = QCheckBox("极速模式：只复核普通算法拿不准的组")
        self.dd_fast.setChecked(True)
        self.dd_fast.setToolTip(
            "打开（默认）：置信度「高 / 极高」且各份体积时长一致的组直接采纳普通算法结论，"
            "只把有疑点的送去 AI —— 真机上能把复核量压掉大半。\n"
            "关闭：全部重复组都让 AI 过一遍（结论更全，但可能要等几分钟）。")
        arh.addWidget(self.dd_fast)
        self.dd_ai_btn = QPushButton("检测本地 AI 引擎")
        self.dd_ai_btn.setObjectName("Ghost")
        self.dd_ai_btn.setCursor(Qt.PointingHandCursor)
        self.dd_ai_btn.clicked.connect(lambda: self._probe_detect_ai(self.dd_ai_lbl))
        arh.addWidget(self.dd_ai_btn)
        arh.addStretch(1)
        algv.addWidget(arow)
        self.dd_ai_lbl = QLabel("选「AI 算法」时会自动探测本机 Ollama；"
                                "用哪个模型跟「智能推荐」页共用同一项设置。")
        self.dd_ai_lbl.setWordWrap(True)
        self.dd_ai_lbl.setStyleSheet("color:#8c8071;font-size:11px;")
        algv.addWidget(self.dd_ai_lbl)
        self.dd_rb_ai.toggled.connect(
            lambda on: on and self._probe_detect_ai(self.dd_ai_lbl))
        self.dd_rb_normal.toggled.connect(self._save_dedupe_prefs)
        self.dd_rb_ai.toggled.connect(self._save_dedupe_prefs)
        self.dd_fast.toggled.connect(self._save_dedupe_prefs)
        g1v.addWidget(alg)

        opt = QHBoxLayout()
        opt.setSpacing(8)
        opt.addWidget(QLabel("媒体库"))
        self.dd_lib = QComboBox()
        self.dd_lib.addItems(["（全部库）"] + self.s.library_names())
        opt.addWidget(self.dd_lib)
        opt.addSpacing(12)
        opt.addWidget(QLabel("最低置信度"))
        self.dd_conf = QComboBox()
        self.dd_conf.addItems(["低", "中", "高", "极高"])
        self.dd_conf.setCurrentText(self.s.dedupe.get("min_confidence", "低"))
        self.dd_conf.setToolTip("只列出不低于该置信度的重复组；置信度由「番号 / 标题+年份」及体积是否一致判定")
        opt.addWidget(self.dd_conf)
        opt.addStretch(1)
        self.dd_run = QPushButton("开始检测")
        self.dd_run.setObjectName("Primary")
        self.dd_run.setToolTip("清空上次结果后重新检测")
        self.dd_run.clicked.connect(self._run_dedupe)
        opt.addWidget(self.dd_run)
        g1v.addLayout(opt)

        # v1.24.0（反馈 2）：同目录分片的排除开关
        opt2 = QHBoxLayout()
        opt2.setSpacing(8)
        self.dd_excl = QCheckBox("自动排除「同一目录下的多份」（CD1/CD2、part1/part2 这类分片）")
        self.dd_excl.setChecked(bool(self.s.dedupe.get("exclude_multipart", True)))
        self.dd_excl.setToolTip(
            "打开（默认）：同目录多份判定为分片，只单列、不算重复；\n"
            "关闭：同目录多份也会当成重复组列出来，由你自己判断。")
        self.dd_excl.toggled.connect(self._save_dedupe_prefs)
        opt2.addWidget(self.dd_excl)
        opt2.addStretch(1)
        self.dd_verify = QCheckBox("校验磁盘文件是否还在")
        self.dd_verify.setChecked(True)
        self.dd_verify.setToolTip("打开：已从磁盘删掉的副本不再参与比对（更准，但要多花几秒遍历磁盘）")
        opt2.addWidget(self.dd_verify)
        g1v.addLayout(opt2)

        self.dd_bar = QProgressBar()
        self.dd_bar.setRange(0, 100)
        self.dd_bar.setValue(0)
        g1v.addWidget(self.dd_bar)
        self.dd_status = QLabel("尚未检测。点「开始检测」扫描当前索引。")
        self.dd_status.setStyleSheet("color:#a2967f;font-size:11px;")
        self.dd_status.setWordWrap(True)
        g1v.addWidget(self.dd_status)
        v.addWidget(g1)

        g2 = QGroupBox("检测结果")
        g2v = QVBoxLayout(g2)
        self.dd_summary = QLabel("—")
        self.dd_summary.setWordWrap(True)
        g2v.addWidget(self.dd_summary)

        # v1.24.0（反馈 7）：从 QTableWidget 换成**树**（组 → 每个副本），
        # 与 nfo_profiler 一致：可展开看路径，双击任一条用资源管理器定位。
        self.dd_tree = QTreeWidget()
        self.dd_tree.setColumnCount(6)
        self.dd_tree.setHeaderLabels(
            ["标识 / 文件", "依据", "置信度", "体积", "时长", "目录"])
        self.dd_tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dd_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dd_tree.setAlternatingRowColors(False)
        self.dd_tree.setRootIsDecorated(True)
        self.dd_tree.setUniformRowHeights(True)
        self.dd_tree.setFixedHeight(320)
        self.dd_tree.itemDoubleClicked.connect(self._open_dedupe_item)
        g2v.addWidget(self.dd_tree)

        tip7 = QLabel("双击任意一条（或分组行）即用资源管理器打开它所在的文件夹并选中该文件。")
        tip7.setStyleSheet("color:#8c8071;font-size:11px;")
        tip7.setWordWrap(True)
        g2v.addWidget(tip7)

        # v1.33.0（反馈 1）：结果文件导入 / 导出 —— 全库跑一次要 70 多秒，
        # 当天没处理完的导出来，第二天导入接着处理，不必重新扫描。
        # v1.33.1（反馈 2）：取消「导出 CSV」「导出 JSON」两枚按钮 ——
        # 与「导出结果文件…」功能重叠且格式对用户无意义，只留可回灌的结果文件。
        ex2 = QHBoxLayout()
        self.dd_exp_result = QPushButton("导出结果文件…")
        self.dd_exp_result.setObjectName("Ghost")
        self.dd_exp_result.setToolTip("把本次检测结果存成一个 JSON，下次可导入继续处理（不必重新扫描）")
        self.dd_exp_result.clicked.connect(self._export_dedupe_result)
        self.dd_imp_result = QPushButton("导入结果文件…")
        self.dd_imp_result.setObjectName("Ghost")
        self.dd_imp_result.setToolTip("导入上次导出的检测结果，直接查看/导出/继续 AI 复核，无需重新扫描")
        self.dd_imp_result.clicked.connect(self._import_dedupe_result)
        ex2.addWidget(self.dd_exp_result)
        ex2.addWidget(self.dd_imp_result)
        ex2.addStretch(1)
        g2v.addLayout(ex2)
        v.addWidget(g2)

        v.addStretch(1)
        return page

    def _dedupe_algo(self):
        """当前选的算法：`"ai"` / `"normal"`。"""
        return "ai" if getattr(self, "dd_rb_ai", None) is not None \
            and self.dd_rb_ai.isChecked() else "normal"

    def _probe_detect_ai(self, label):
        """探测本机 Ollama 并把结论写进 `label`（三个检测页共用一个实现）。

        走 `aireview.ai_available()` 而不是自己再写一遍探测 —— 四个检测页必须
        **口径完全一致**，否则会出现「演员检测说可用、图像检测说不可用」这种怪事。
        """
        try:
            import aireview as ar
            ok, note = ar.ai_available(self.s.ai_model() if hasattr(self.s, "ai_model") else "")
        except Exception as e:
            label.setText("探测失败：%s" % e)
            label.setStyleSheet("color:#e8b76a;font-size:11px;")
            return
        if ok:
            label.setText("✓ " + note)
            label.setStyleSheet("color:#8fd18f;font-size:11px;")
        else:
            label.setText("✗ " + note)
            label.setStyleSheet("color:#e8b76a;font-size:11px;")

    def _save_dedupe_prefs(self, *_):
        self.s.set_dedupe_prefs(exclude_multipart=self.dd_excl.isChecked(),
                               min_confidence=self.dd_conf.currentText(),
                               algo=self._dedupe_algo(),
                               fast=bool(getattr(self, "dd_fast", None) is not None
                                         and self.dd_fast.isChecked()))

    def _run_dedupe(self):
        if getattr(self, "_dd_worker", None) is not None and self._dd_worker.isRunning():
            return
        lib = self.dd_lib.currentText()
        lib = "" if lib == "（全部库）" else lib
        self._save_dedupe_prefs()
        # v1.24.0（反馈 1）：**重检前先清空上次结果**（表格 / 树 / 汇总 / 导出用的报告），
        # 否则用户会看到「已经删掉的片子还在结果里」的旧数据。
        self._clear_dedupe_result()
        algo = self._dedupe_algo()
        self.dd_run.setEnabled(False)
        self.dd_bar.setRange(0, 0)                 # 忙碌态
        self.dd_status.setText("正在读取作品元数据…")
        self._dd_worker = DedupeWorker(lib, self.dd_conf.currentText(),
                                       exclude_multipart=self.dd_excl.isChecked(),
                                       verify_exists=self.dd_verify.isChecked(),
                                       algo=algo,
                                       model=self._ai_model_name(),
                                       fast=bool(getattr(self, "dd_fast", None) is None
                                                 or self.dd_fast.isChecked()))
        self._dd_worker.progress.connect(self._on_dedupe_progress)
        self._dd_worker.done.connect(self._on_dedupe_done)
        self._dd_worker.start()

    def _ai_model_name(self):
        """本地 AI 用哪个模型 —— 与「智能推荐」页共用配置，绝不各存一份。"""
        try:
            return str(self.s.smart.get("ai_model") or "")
        except Exception:
            return ""

    def _clear_dedupe_result(self):
        self._dd_report = None
        self.dd_tree.clear()
        self.dd_summary.setText("—")
        self.dd_status.setText("正在重新检测（已清空上次结果）…")

    def _open_dedupe_item(self, item, _col=0):
        """双击 → 资源管理器打开所在文件夹并选中该文件（v1.24.0 反馈 7）。"""
        path = item.data(0, Qt.UserRole) if item is not None else None
        if not path:
            item = item.parent() if item is not None else None
            path = item.data(0, Qt.UserRole) if item is not None else None
        if not path:
            return
        try:
            if os.path.exists(path):
                # `explorer /select,` 会打开父目录并高亮该文件；注意逗号后不能有空格
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                folder = os.path.dirname(path)
                if os.path.isdir(folder):
                    subprocess.Popen(["explorer", os.path.normpath(folder)])
                else:
                    QMessageBox.information(self, "无法定位",
                                            f"文件与所在目录都不存在：\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"{type(e).__name__}: {e}")

    def _on_dedupe_progress(self, a, b, msg):
        if b:
            self.dd_bar.setRange(0, 100)
            self.dd_bar.setValue(int(a * 100 / max(b, 1)))
        self.dd_status.setText(msg)

    def _on_dedupe_done(self, report):
        self.dd_bar.setRange(0, 100)
        self.dd_run.setEnabled(True)
        if report is None:
            self.dd_bar.setValue(0)
            self.dd_status.setText("检测失败（详见运行日志）。")
            return
        self._dd_report = report
        s = report.summary()
        self.dd_bar.setValue(100)
        gone = f"，其中 {report.missing} 部在磁盘上已不存在、未参与比对" if report.missing else ""
        # v1.32.0（反馈 1）：把「用了哪个算法、AI 复核了多少条」如实写出来。
        # 选 AI 但引擎不可用时**必须**让用户看见降级原因，否则会以为 AI 跑过了。
        algo_note = ""
        if report.algo == "ai":
            ai = report.ai or {}
            if ai.get("ai"):
                algo_note = (f" · AI 复核 {s['ai_done']} 组"
                             + (f"（{s['ai_skipped']} 组按极速模式跳过）"
                                if s["ai_skipped"] else "")
                             + (f" · {s['ai_failed']} 组复核失败" if s["ai_failed"] else ""))
            else:
                algo_note = " · AI 不可用，已按普通算法给出结果"
        self.dd_status.setText(
            f"检测完成（{'AI 算法' if report.algo == 'ai' else '普通算法'}）："
            f"核对 {s['scanned']} 部作品{gone}，耗时 {s['elapsed']} 秒。{algo_note}")
        mp = (f"同目录分片（已排除）{s['multipart_groups']} 组"
              if s.get("multipart_excluded", True)
              else "同目录分片（未排除，已并入上方结果）")
        self.dd_summary.setText(
            f"重复组 <b>{s['dup_groups']}</b> 组 · 涉及 {s['dup_movies']} 部 · "
            f"冗余 {s['redundant_copies']} 份 · 可回收 <b>{s['redundant_text']}</b> · {mp}"
            + (f"<br><span style='color:#8c8071;'>AI 复核：{s['ai_note']}</span>"
               if report.algo == "ai" and s.get("ai_note") else ""))
        self._fill_dedupe_tree(report)
        self.dd_tree.resizeColumnToContents(0)
        applog.log(f"[重复检测] 完成：{s['dup_groups']} 组重复，可回收 {s['redundant_text']}，"
                   f"已失效副本 {report.missing}，算法 {report.algo}")

    def _fill_dedupe_tree(self, report):
        """把重复组填进树：分组行可展开看每个副本的完整路径（v1.24.0 反馈 7）。

        v1.32.0（反馈 1）：表头改为从 `self.dd_tree.headerItem().setText()` 动态设置 ——
        只在选了 AI 算法时才追加「AI 建议」列，普通算法下不多出一列空白。
        """
        show_ai = (report.algo == "ai")
        heads = (["标识 / 文件", "依据", "置信度", "AI 建议", "体积", "时长", "目录"]
                 if show_ai else ["标识 / 文件", "依据", "置信度", "体积", "时长", "目录"])
        self.dd_tree.setColumnCount(len(heads))
        self.dd_tree.setHeaderLabels(heads)
        # 列号随表头长度变，先算出来，下面所有 setForeground / setToolTip 都用它
        C_AI = 3 if show_ai else -1
        C_SIZE = 4 if show_ai else 3
        C_DUR = 5 if show_ai else 4
        C_DIR = 6 if show_ai else 5
        self.dd_tree.clear()

        def _ai_cells(g):
            """一组重复的 AI 建议两个格子（组行 / 成员行）。"""
            if not show_ai:
                return []
            a = g.ai or {}
            if not a:
                return ["—"]
            return ["%s（%s）" % (a.get("advice") or "", a.get("confidence") or "")]

        for g in report.groups:
            row = [f"{g.label}   （{g.copies} 份，冗余 {g.redundant_copies}）",
                   "番号" if g.kind == "num" else "标题+年份",
                   g.confidence] + _ai_cells(g) + \
                  [g.total_text, "", " | ".join(g.folders)]
            top = QTreeWidgetItem(row)
            top.setToolTip(C_DIR, "\n".join(g.folders))
            ai_tip = ""
            if show_ai and g.ai:
                ai_tip = "\nAI 建议：%s（%s）%s" % (g.ai.get("advice") or "",
                                                  g.ai.get("confidence") or "",
                                                  ("　" + (g.ai.get("reason") or ""))
                                                  if g.ai.get("reason") else "")
            top.setToolTip(0, f"{g.note or ''}\n可回收 {g.redundant_text}{ai_tip}")
            if g.redundant_bytes:
                top.setForeground(0, QBrush(QColor("#f0c674")))
            if show_ai and g.ai:
                top.setForeground(C_AI, QBrush(QColor(
                    "#8fd18f" if (g.ai.get("advice") or "") == "全部保留" else "#f0c674")))
            # 分组行双击 → 打开它最大的那一份（体积最大的留、其余是冗余）
            if g.members:
                top.setData(0, Qt.UserRole, g.members[0].path)
            for m in g.members:
                cells = [(m.original_filename or m.path),
                         "保留（最大）" if m is g.members[0] else "冗余副本",
                         m.num or ""] + ([""] if show_ai else []) + \
                        [m.size_text, m.duration_text, m.folder]
                child = QTreeWidgetItem(cells)
                child.setData(0, Qt.UserRole, m.path)
                child.setToolTip(0, m.path)
                child.setToolTip(C_DIR, m.folder)
                if m is not g.members[0]:
                    child.setForeground(1, QBrush(QColor("#e2685a")))
                top.addChild(child)
            self.dd_tree.addTopLevelItem(top)
        if report.multipart:
            head = QTreeWidgetItem([f"同目录分片（{len(report.multipart)} 组，未计入重复）"]
                                   + [""] * (len(heads) - 1))
            head.setForeground(0, QBrush(QColor("#8c8071")))
            for g in report.multipart:
                it = QTreeWidgetItem([g.label, "同目录多份", g.confidence]
                                     + ([""] if show_ai else [])
                                     + [g.total_text, "", " | ".join(g.folders)])
                for m in g.members:
                    ch = QTreeWidgetItem([m.original_filename or m.path, "分片",
                                          m.num or ""]
                                         + ([""] if show_ai else [])
                                         + [m.size_text, m.duration_text, m.folder])
                    ch.setData(0, Qt.UserRole, m.path)
                    it.addChild(ch)
                head.addChild(it)
            self.dd_tree.addTopLevelItem(head)
        self.dd_tree.expandToDepth(0)

    # ---- v1.33.0（反馈 1）：结果文件导出 / 导入 ----
    # v1.33.1（反馈 2）：入口按钮已取消，保留此方法供脚本 / 冒烟调用，不再挂 UI。
    def _export_dedupe(self, fmt):
        rep = getattr(self, "_dd_report", None)
        if rep is None:
            QMessageBox.information(self, "提示", "请先执行一次检测。")
            return
        default = f"重复影片清单.{fmt}"
        flt = "CSV (*.csv)" if fmt == "csv" else "JSON (*.json)"
        path, _sel = QFileDialog.getSaveFileName(self, "导出重复清单", default, flt)
        if not path:
            return
        try:
            p = dup_mod.export_csv(rep, path) if fmt == "csv" else dup_mod.export_json(rep, path)
            QMessageBox.information(self, "完成", f"已导出：\n{p}")
            applog.log(f"[重复检测] 已导出清单：{p}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _export_dedupe_result(self):
        """把本次检测结果存成可再次导入的结果文件。"""
        rep = getattr(self, "_dd_report", None)
        if rep is None:
            QMessageBox.information(self, "提示", "请先执行一次检测（或先导入上次的结果）。")
            return
        default = "重复检测结果.json"
        path, _sel = QFileDialog.getSaveFileName(self, "导出检测结果", default, "结果文件 (*.json)")
        if not path:
            return
        try:
            p = dup_mod.export_json(rep, path)
            QMessageBox.information(
                self, "完成",
                f"已导出：\n{p}\n\n下次用「导入结果文件…」载入本文件，即可接着处理"
                f"（本页现有 {len(rep.groups)} 组重复 + {len(rep.multipart)} 组同目录分片）。")
            applog.log(f"[重复检测] 已导出结果文件：{p}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _import_dedupe_result(self):
        """导入上次导出的结果文件 → 直接渲染结果树（不必重新扫描）。"""
        path, _sel = QFileDialog.getOpenFileName(self, "导入检测结果", "",
                                                 "结果文件 (*.json);;所有文件 (*)")
        if not path:
            return
        try:
            rep = dup_mod.import_json(path)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"{e}\n\n请确认选的是本页「导出结果文件…」"
                                                  f"产出的文件。")
            applog.log(f"[重复检测] 导入结果失败：{e}", "error")
            return
        # 复用正常检测完成的渲染路径 —— 树、汇总、导出、后续 AI 复核全都一致。
        self._on_dedupe_done(rep)
        self.dd_status.setText(self.dd_status.text()
                               + f"　（本结果是**导入**的：{os.path.basename(path)}，"
                                 f"生成于 {rep.generated_at or '未知时间'}）")
        applog.log(f"[重复检测] 已导入结果文件：{path}（{len(rep.groups)} 组重复）")
        QMessageBox.information(
            self, "导入完成",
            f"已载入 {len(rep.groups)} 组重复、{len(rep.multipart)} 组同目录分片。\n"
            f"可以直接「导出结果文件…」留档，或切到「AI 算法」对这些结果做复核。")

    # ---------- 数据与日志（v1.13.0 新增） ----------
    def _build_data(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(14)

        # 数据导出 / 导入
        g1 = QGroupBox("数据导出 / 导入")
        g1v = QVBoxLayout(g1)
        # v1.25.0（反馈 2）：这里原来是 Qt 默认行距，而下面那个勾选区用了
        # ph.setSpacing(2) —— 三列勾选框与「全选 / 全不选 / 只选轻量项」按钮行
        # 挤在一起（截图为证）。把两处间距统一成 10，上下都拉开。
        g1v.setSpacing(10)
        h1 = QLabel(rich(
            "导出「已处理与扫描过的信息」—— 媒体索引（含画质/评分/添加日期等）+ 演员资料 + "
            "媒体库配置，打包成一个 zip 备份；日后可导入用于**恢复数据库**。\n"
            "v1.24.0 起还能**按内容分类导出**（例如只导出「影片收藏」「演员收藏」，"
            "换台机器时只搬这些轻量信息，不必搬 5 万条索引）。"))
        h1.setWordWrap(True)
        h1.setStyleSheet("color:#a2967f;font-size:11px;")
        g1v.addWidget(h1)

        # v1.24.0（反馈 9）：导出内容可勾选
        pick = QWidget()
        ph = QVBoxLayout(pick)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.setSpacing(10)      # v1.25.0（反馈 2）：原为 2，与下方按钮行贴着
        ph.addWidget(QLabel("导出内容（可多选）："))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        self.exp_ck = {}
        selected = set(self.s.export_sections())
        for i, (key, label) in enumerate(cfg.EXPORT_SECTIONS):
            ck = QCheckBox(label)
            ck.setChecked(key in selected)
            ck.toggled.connect(self._save_export_sections)
            grid.addWidget(ck, i // 3, i % 3)
            self.exp_ck[key] = ck
        ph.addLayout(grid)
        q = QHBoxLayout()
        q.setContentsMargins(0, 0, 0, 0)
        b_all = QPushButton("全选")
        b_all.setObjectName("Ghost")
        b_all.clicked.connect(lambda: self._set_export_sections(True))
        b_none = QPushButton("全不选")
        b_none.setObjectName("Ghost")
        b_none.clicked.connect(lambda: self._set_export_sections(False))
        b_light = QPushButton("只选轻量项（收藏 / 播放 / 评分 / 演员收藏）")
        b_light.setObjectName("Ghost")
        b_light.clicked.connect(
            lambda: self._set_export_sections(False,
                                              only=("favorite", "play", "userrating",
                                                    "people_fav")))
        q.addWidget(b_all); q.addWidget(b_none); q.addWidget(b_light)
        q.addStretch(1)
        ph.addLayout(q)
        g1v.addWidget(pick)

        r1 = QWidget()
        r1h = QHBoxLayout(r1)
        r1h.setContentsMargins(0, 0, 0, 0)
        exp = QPushButton("导出所选分类…")
        exp.setObjectName("Primary")
        exp.setToolTip(rich("按上面勾选的内容分类导出（导入时是**合并**，不覆盖整库）"))
        exp.clicked.connect(self._export_data)
        exp_all = QPushButton("整库导出…")
        exp_all.setObjectName("Ghost")
        exp_all.setToolTip("整库快照（media_center.db + settings.json），导入时覆盖整库")
        exp_all.clicked.connect(lambda: self._export_data(whole=True))
        imp = QPushButton("导入数据…")
        imp.setObjectName("Ghost")
        imp.setToolTip("自动识别是「分类导出包」还是「整库快照」：前者合并、后者覆盖")
        imp.clicked.connect(self._import_data)
        r1h.addWidget(exp)
        r1h.addWidget(exp_all)
        r1h.addWidget(imp)
        r1h.addStretch(1)
        g1v.addWidget(r1)
        self.data_hint = QLabel(rich(
            "导入前会自动把现有的数据库 / 设置另存为 *.bak-<时间戳>，可手动还原。"
            "「整库导出」的包导入后会**覆盖**当前索引；"
            "「分类导出」的包导入时只**合并**所选的这几类信息。"))
        self.data_hint.setWordWrap(True)
        self.data_hint.setStyleSheet("color:#a2967f;font-size:11px;")
        g1v.addWidget(self.data_hint)
        v.addWidget(g1)

        # 日志导出
        g2 = QGroupBox("运行日志")
        g2v = QVBoxLayout(g2)
        h2 = QLabel("软件会把全部运行记录（启动 / 扫描 / 刮削 / 报错等）写入日志文件。"
                    "出现 BUG 时点「导出日志」把压缩包发给开发者即可快速定位。")
        h2.setWordWrap(True)
        h2.setStyleSheet("color:#a2967f;font-size:11px;")
        g2v.addWidget(h2)
        self.log_path_lbl = QLabel("日志位置：" + applog.log_path())
        self.log_path_lbl.setWordWrap(True)
        self.log_path_lbl.setStyleSheet("color:#8c8071;font-size:11px;")
        g2v.addWidget(self.log_path_lbl)
        r2 = QWidget()
        r2h = QHBoxLayout(r2)
        r2h.setContentsMargins(0, 0, 0, 0)
        exp_log = QPushButton("导出日志…")
        exp_log.setObjectName("Primary")
        exp_log.clicked.connect(self._export_logs)
        open_dir = QPushButton("打开日志文件夹")
        open_dir.setObjectName("Ghost")
        open_dir.clicked.connect(self._open_log_dir)
        r2h.addWidget(exp_log)
        r2h.addWidget(open_dir)
        r2h.addStretch(1)
        g2v.addWidget(r2)
        v.addWidget(g2)

        # 运行日志（实时显示 app.log 内容）—— v1.19.0 反馈 101：用户要的是实时日志文本，
        # 而非 v1.18.0 的数据库统计汇总面板（已移除）。
        g3 = QGroupBox("运行日志（实时）")
        g3v = QVBoxLayout(g3)
        g3hint = QLabel("实时显示 app.log 的尾部内容（约每 1.5 秒刷新），告诉你软件当前在做什么、进度如何。"
                        "关闭本窗口即停止刷新。")
        g3hint.setWordWrap(True)
        g3hint.setStyleSheet("color:#a2967f;font-size:11px;")
        g3v.addWidget(g3hint)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._log_view.setStyleSheet(
            "font-family: Consolas, 'Courier New', Menlo, monospace; "
            "font-size:11px; background:rgba(0,0,0,0.25); color:#d9cfbf;")
        g3v.addWidget(self._log_view, 1)
        self._log_path_lbl2 = QLabel("日志文件：" + applog.log_path())
        self._log_path_lbl2.setWordWrap(True)
        self._log_path_lbl2.setStyleSheet("color:#8c8071;font-size:11px;")
        g3v.addWidget(self._log_path_lbl2)
        v.addWidget(g3)

        # 启动实时刷新定时器（窗口显示时开始，关闭时停止）
        self._rt_timer = QTimer(self)
        self._rt_timer.setInterval(1500)
        self._rt_timer.timeout.connect(self._refresh_log)
        self._refresh_log()   # 立即填一次，避免打开时空白

        v.addStretch(1)
        return page

    def _refresh_log(self):
        """v1.19.0 反馈 101：实时读取 app.log 尾部，反映当前进度与正在做的事。
        只读尾部（最多 200KB）避免大日志卡顿；刷新后自动滚到最底。"""
        try:
            path = applog.log_path()
            if not os.path.exists(path):
                self._log_view.setPlainText("（暂无日志文件）")
                return
            size = os.path.getsize(path)
            tail = min(size, 200 * 1024)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                if tail < size:
                    f.seek(size - tail)
                    f.readline()        # 丢弃可能不完整的半行
                text = f.read()
            self._log_view.setPlainText(text)
            sb = self._log_view.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception as e:
            applog.log(f"读取运行日志失败：{e}", "error")

    def _save_export_sections(self, *_):
        self.s.set_export_sections([k for k, ck in self.exp_ck.items() if ck.isChecked()])

    def _set_export_sections(self, on, only=None):
        for k, ck in self.exp_ck.items():
            ck.blockSignals(True)
            ck.setChecked(bool(on) or (only is not None and k in only))
            ck.blockSignals(False)
        self._save_export_sections()

    def _export_data(self, whole=False):
        default = os.path.join(os.path.expanduser("~"), backup_mod.data_export_name())
        title = "整库导出" if whole else "分类导出"
        path, _ = QFileDialog.getSaveFileName(self, title, default, "ZIP 备份 (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        if whole:
            r = backup_mod.export_data(path)
            items = r.get("items", [])
        else:
            secs = [k for k, ck in self.exp_ck.items() if ck.isChecked()]
            if not secs:
                QMessageBox.information(self, "提示", "请至少勾选一项导出内容。")
                return
            r = backup_mod.export_sections(path, secs)
            items = [f"{next((lb for k2, lb in cfg.EXPORT_SECTIONS if k2 == k), k)}"
                     f"（{r.get('counts', {}).get(k, 0)} 条）" for k in secs]
        if r.get("ok"):
            applog.log(f"数据导出：{path} 含 {items}")
            QMessageBox.information(
                self, "导出完成", f"已导出到：\n{path}\n\n包含：{'、'.join(items)}")
            self.data_hint.setText("最近导出：" + path)
        else:
            applog.log(f"数据导出失败：{r.get('error')}", "error")
            QMessageBox.warning(self, "导出失败", r.get("error") or "未知错误")

    def _import_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入数据", "", "ZIP 备份 (*.zip)")
        if not path:
            return
        # v1.24.0（反馈 9）：自动识别包类型 —— 分类包是**合并**，整库快照是**覆盖**
        kind = "whole"
        try:
            with zipfile.ZipFile(path) as z:
                if "sections.json" in set(z.namelist()):
                    kind = "sections"
        except Exception:
            pass
        if kind == "sections":
            msg = rich("这是一个**分类导出包**：会把包里这几类信息**合并**进现有数据"
                       "（不删除、不覆盖其他内容）。\n"
                       "现有数据库会先自动另存为 *.bak-<时间戳>（可手动还原）。\n\n"
                       "导入后建议重启软件。是否继续？")
        else:
            msg = rich("这是一个**整库快照**：会用备份包**覆盖**当前的媒体索引与设置。\n"
                       "现有数据会先自动另存为 *.bak-<时间戳>（可手动还原）。\n\n"
                       "导入后建议重启软件。是否继续？")
        if QMessageBox.question(self, "导入数据", msg) != QMessageBox.Yes:
            return
        r = (backup_mod.import_sections(path) if kind == "sections"
             else backup_mod.import_data(path))
        if r.get("ok"):
            backup_mod.reload_settings()
            applog.log(f"数据导入（{kind}）：{path} 恢复 {r.get('restored')}")
            QMessageBox.information(
                self, "导入完成",
                f"已{'合并' if kind == 'sections' else '恢复'}："
                f"{'、'.join(r.get('restored', []))}\n\n请重启软件以完全生效。")
            self.data_hint.setText("最近导入：" + path + "　（重启后完全生效）")
            if self.on_changed:
                self.on_changed()
        else:
            applog.log(f"数据导入失败：{r.get('error')}", "error")
            QMessageBox.warning(self, "导入失败", r.get("error") or "未知错误")

    def _export_logs(self):
        default = os.path.join(os.path.expanduser("~"), backup_mod.log_export_name())
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", default, "ZIP 压缩包 (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        r = applog.export_logs(path)
        if r.get("ok"):
            applog.log(f"日志导出：{path}（{r.get('count')} 个文件）")
            QMessageBox.information(
                self, "导出完成", f"已导出 {r.get('count')} 个日志文件到：\n{path}")
        else:
            QMessageBox.warning(self, "导出失败", r.get("error") or "未知错误")

    def _open_log_dir(self):
        d = applog.log_dir()
        try:
            os.startfile(d)                 # Windows 资源管理器打开
        except Exception:
            QMessageBox.information(self, "日志位置", d)

    # ---------- 媒体库动作 ----------
    def _add_path(self):
        d = QFileDialog.getExistingDirectory(self, "选择媒体库目录")
        if d:
            self.path_list.addItem(d)
            self.path_list.setCurrentRow(self.path_list.count() - 1)

    def _move_default_path(self, delta):
        """把默认路径列表里当前选中的目录上/下移一位（顺序即扫描优先级）。"""
        r = self.path_list.currentRow()
        t = r + delta
        if r < 0 or t < 0 or t >= self.path_list.count():
            return
        it = self.path_list.takeItem(r)
        self.path_list.insertItem(t, it)
        self.path_list.setCurrentRow(t)

    def _sync_default_path_btns(self):
        """没有选中行时，↑/↓ 置灰。"""
        has = self.path_list.currentRow() >= 0
        for b in (getattr(self, "dp_up", None), getattr(self, "dp_down", None)):
            if b is not None:
                b.setEnabled(has)

    def _add_library(self):
        name = self.lib_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请填写媒体库名称。")
            return
        if self.s.library(name):
            QMessageBox.warning(self, "提示", f"已存在名为「{name}」的媒体库，请换个名字。")
            return
        # 允许先建库、后补路径（有些盘还没接上）；没有路径时下面的提示会提醒去编辑。
        paths = [self.path_list.item(i).text() for i in range(self.path_list.count())]
        self.s.add_library(name, self.lib_kind.currentText(), paths)
        self.lib_name.clear()
        self.path_list.clear()
        self._rebuild_lib_list()
        if self.on_changed:
            self.on_changed()
        tip = "可直接点「扫描」索引其中的影片。" if paths else "点「编辑」可再补上媒体文件夹。"
        QMessageBox.information(self, "已添加", f"媒体库「{name}」已添加。\n{tip}")

    def _edit_library(self, lib):
        dlg = LibraryEditDialog(self, lib)
        if dlg.exec() != QDialog.Accepted:
            return
        name, kind, paths = dlg.result_data()
        if not name:
            QMessageBox.warning(self, "提示", "请填写媒体库名称。")
            return
        old = lib["name"]
        if name != old:
            if self.s.library(name):
                QMessageBox.warning(self, "提示", f"已存在名为「{name}」的媒体库，请换个名字。")
                return
            # 同步已有媒体的 library 字段
            db.rename_library(old, name)
        ok = self.s.update_library(old, name, kind, paths)
        if not ok:
            QMessageBox.warning(self, "提示", "保存失败：未找到原媒体库。")
            return
        self._rebuild_lib_list()
        if self.on_changed:
            self.on_changed()
        QMessageBox.information(self, "已保存", f"媒体库「{name}」已更新。")

    def _rebuild_lib_list(self):
        self.lib_list.clear()
        if not self.s.libraries:
            li = QListWidgetItem(self.lib_list)
            empty = QLabel("（还没有媒体库 —— 用上面的表单新建一个，名称由你自己定）")
            empty.setStyleSheet("color:#8c8071;font-size:11px;padding:6px 4px;")
            li.setSizeHint(QSize(empty.sizeHint().width(), LIB_ROW_H))
            self.lib_list.addItem(li)
            self.lib_list.setItemWidget(li, empty)
            self.lib_list.setFixedHeight(LIB_ROW_H + 10)
            return
        for lib in self.s.libraries:
            li = QListWidgetItem(self.lib_list)
            li.setData(Qt.UserRole, lib["name"])     # 便于按行反查库名
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(6, 4, 6, 4)
            h.setSpacing(8)
            info = QLabel(f"{lib['name']}  （{lib['kind']} · {len(lib.get('paths', []))} 个路径）")
            info.setMinimumWidth(160)
            h.addWidget(info, 1)
            edit = QPushButton("编辑")
            edit.setObjectName("Ghost")
            edit.clicked.connect(lambda _c, L=lib: self._edit_library(L))
            scan = QPushButton("扫描")
            scan.setObjectName("Ghost")
            scan.clicked.connect(lambda _c, L=lib: self._scan_library(L))
            delete = QPushButton("删除")
            delete.setObjectName("Ghost")
            delete.clicked.connect(lambda _c, L=lib: self._del_library(L))
            for b in (edit, scan, delete):
                b.setFixedHeight(28)         # 与正文行高匹配，不会被行高裁掉
                h.addWidget(b)
            # v1.14.0 反馈 6：行高用显式常量（原来 row.sizeHint() 量到的高度不足以
            # 容纳 28px 按钮 + 上下 4px 边距，按钮底部被切掉一截）
            li.setSizeHint(QSize(row.sizeHint().width(), LIB_ROW_H))
            self.lib_list.addItem(li)
            self.lib_list.setItemWidget(li, row)
        # 列表高度按条目数自适应（3 行以内全显，更多则滚动）
        self.lib_list.setFixedHeight(min(len(self.s.libraries), 4) * LIB_ROW_H + 10)

    def _scan_library(self, lib):
        self._scan_total = 1
        self._scan_done_n = 0
        self._set_lib_status(f"正在扫描「{lib['name']}」…（后台进行，可继续使用主界面）", "#d4af37")
        self._worker = ScanNamedWorker(lib)
        self._worker.done.connect(self._on_scan_done)
        self._worker.start()

    def _scan_all(self):
        if not self.s.libraries:
            QMessageBox.warning(self, "提示", "尚未配置任何媒体库。")
            return
        self._scan_queue = list(self.s.libraries)
        self._scan_total = len(self._scan_queue)
        self._scan_done_n = 0
        self._scan_next()

    def _scan_next(self):
        if not self._scan_queue:
            self._set_lib_status("全部媒体库扫描完成。", "#7fc08a")
            return
        lib = self._scan_queue.pop(0)
        self._set_lib_status(
            f"正在扫描「{lib['name']}」…（{self._scan_done_n + 1}/{self._scan_total}，"
            f"后台进行，可继续使用主界面）", "#d4af37")
        self._worker = ScanNamedWorker(lib)
        self._worker.done.connect(lambda c, n: (self._on_scan_done(c, n), self._scan_next()))
        self._worker.start()

    def _set_lib_status(self, text, color="#a2967f"):
        lbl = getattr(self, "lib_status", None)
        if lbl is None:
            return
        lbl.setText(text)
        lbl.setStyleSheet(f"color:{color};font-size:11px;")
        applog.log(f"[设置·媒体库] {text}")

    def _on_scan_done(self, counts, name):
        """扫描结束。v1.14.0 反馈 7：改为**状态栏文字提示**，不再弹模态框。

        扫描本身跑在 QThread 里；完成时弹模态窗会把设置窗口与主界面一起挡住，
        用户必须点掉才能继续 —— 这正是「设置里的功能影响了主体功能」。
        """
        if counts.get("error"):
            self._set_lib_status(f"「{name}」扫描出错：{counts['error']}", "#e08e8e")
        else:
            self._scan_done_n = getattr(self, "_scan_done_n", 0) + 1
            self._set_lib_status(
                f"「{name}」扫描完成：电影 {counts.get('movie', 0)} 部 / "
                f"剧集 {counts.get('tvshow', 0)} 部 / 分集 {counts.get('episode', 0)} 个",
                "#7fc08a")
        if self.on_changed:
            self.on_changed()

    def _del_library(self, lib):
        if QMessageBox.question(
                self, "删除媒体库",
                rich(f"确定删除媒体库「{lib['name']}」？\n\n"
                     "· 只移除这个库的配置，**不会删除磁盘上的任何视频文件**\n"
                     "· 已有索引记录仍可在「全部 / 首页」里看到\n"
                     "· 删掉后不会再自动恢复（软件已无「内置库」概念）"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.s.remove_library(lib["name"])
        self._rebuild_lib_list()
        if self.on_changed:
            self.on_changed()

    # ==================================================================
    # 标签优化（v1.25.0 反馈 4）
    # ------------------------------------------------------------------
    # 与「智能推荐」同源：都用「普通智能算法 / AI 智能算法」那套本地离线能力，
    # 区别在**打分对象**是标签本身 —— 结合标题与 nfo 里已有的信息，给 nfo 的
    # <genre> 补全、并做日语→中文这类标签转化。
    # 流程刻意拆成两段：
    #   1) 「扫描并预览」= 只读盘 + 只算，把每个文件会变成什么样列出来；
    #   2) 「执行写入」= 用户看过预览、点过确认之后才落盘（可选自动备份）。
    # 这样即使算法给出一堆怪标签，也不会在用户没看见的情况下改掉 5 万个 nfo。
    # ==================================================================
    def _build_tagopt(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(12)
        to = self.s.tagopt

        # ---------- 处理范围 ----------
        g1 = QGroupBox("处理范围")
        g1v = QVBoxLayout(g1)
        h1 = QLabel(rich(
            "按范围找出其中**已经刮削好的 .nfo**，结合**标题**与 nfo 里已有的信息"
            "（片商 / 系列 / 原有标签）推断标签，先给一份**预览**，确认后才写回磁盘。\n"
            "· 普通智能算法：纯本地规则 —— 标题关键词 + 片商 / 系列伪标签 + 全库标签共现；\n"
            "· AI 智能算法：在普通算法之上叠加**本地离线 AI**（Ollama 不可用时自动降级）。"))
        h1.setWordWrap(True)
        h1.setStyleSheet("color:#a2967f;font-size:11px;")
        g1v.addWidget(h1)

        srow = QHBoxLayout()
        srow.setSpacing(14)
        self.rb_to_file = QRadioButton("单一文件")
        self.rb_to_folder = QRadioButton("文件夹")
        self.rb_to_lib = QRadioButton("媒体库")
        for rb in (self.rb_to_file, self.rb_to_folder, self.rb_to_lib):
            srow.addWidget(rb)
        srow.addStretch(1)
        g1v.addLayout(srow)

        prow = QHBoxLayout()
        prow.setSpacing(8)
        prow.addWidget(QLabel("路径"))
        self.to_path = QLineEdit()
        self.to_path.setText(str(to.get("path") or ""))
        self.to_path.setPlaceholderText("视频文件或 .nfo 的完整路径")
        prow.addWidget(self.to_path, 1)
        self.btn_to_browse = QPushButton("浏览…")
        self.btn_to_browse.setObjectName("Ghost")
        self.btn_to_browse.clicked.connect(self._tagopt_browse)
        prow.addWidget(self.btn_to_browse)
        g1v.addLayout(prow)

        lrow = QHBoxLayout()
        lrow.setSpacing(8)
        lrow.addWidget(QLabel("媒体库"))
        self.to_lib = QComboBox()
        self.to_lib.setMinimumWidth(260)
        for lib in (self.s.libraries or []):
            nm = lib.get("name") or ""
            if nm:
                self.to_lib.addItem(nm, nm)
        want_lib = str(to.get("library") or "")
        if want_lib:
            idx = self.to_lib.findData(want_lib)
            if idx >= 0:
                self.to_lib.setCurrentIndex(idx)
        lrow.addWidget(self.to_lib)
        self.lb_to_scope = QLabel("—")
        self.lb_to_scope.setStyleSheet("color:#8c8071;font-size:11px;")
        self.lb_to_scope.setWordWrap(True)
        lrow.addWidget(self.lb_to_scope, 1)
        g1v.addLayout(lrow)

        sc = str(to.get("scope") or "file")
        (self.rb_to_folder if sc == "folder" else
         self.rb_to_lib if sc == "library" else self.rb_to_file).setChecked(True)
        v.addWidget(g1)

        # ---------- 优化方式 ----------
        g2 = QGroupBox("优化方式")
        g2v = QVBoxLayout(g2)
        self.rb_to_normal = QRadioButton("普通智能算法（本地规则 + 全库标签共现）")
        self.rb_to_ai = QRadioButton("AI 智能算法（本地离线 AI 辅助补全）")
        (self.rb_to_ai if to.get("algo") == "ai"
         else self.rb_to_normal).setChecked(True)
        g2v.addWidget(self.rb_to_normal)
        g2v.addWidget(self.rb_to_ai)
        self.to_ai_state = QLabel("点上面的「AI 智能算法」会检测本机 Ollama 是否可用；"
                                  "用哪个模型跟「智能推荐」页共用同一项设置。")
        self.to_ai_state.setWordWrap(True)
        self.to_ai_state.setStyleSheet("color:#8c8071;font-size:11px;")
        g2v.addWidget(self.to_ai_state)

        self.ck_to_trans = QCheckBox("日语标签转中文（例：中出し → 中出）")
        self.ck_to_over = QCheckBox("用中文覆盖原日语标签（不勾 = 保留原日语，另补一条中文）")
        self.ck_to_full = QCheckBox("补全缺失标签（标题关键词 / 片商 / 系列 / 全库共现）")
        self.ck_to_bak = QCheckBox("写入前备份原 nfo（*.nfo.bak-<时间戳>）")
        for ck, key, dflt in ((self.ck_to_trans, "translate", True),
                              (self.ck_to_over, "overwrite", False),
                              (self.ck_to_full, "complete", True),
                              (self.ck_to_bak, "backup", True)):
            ck.setChecked(bool(to.get(key, dflt)))
            g2v.addWidget(ck)
        v.addWidget(g2)

        # ---------- 预览与执行 ----------
        g3 = QGroupBox("预览与执行（先预览，确认后才写盘）")
        g3v = QVBoxLayout(g3)
        # v1.33.1（反馈 1）：五枚按钮**同排水平对齐** —— 原先「导出/导入结果文件…」
        # 单独占一行，与「扫描并预览」错位，视觉上像从属关系；合并成一行后
        # 主操作在前、结果文件操作在后，中间用竖线分隔表达分组。
        arow = QHBoxLayout()
        arow.setSpacing(8)
        self.btn_to_scan = QPushButton("扫描并预览")
        self.btn_to_scan.setObjectName("Primary")
        self.btn_to_scan.setToolTip("只读盘 + 只算，不改动任何文件")
        self.btn_to_scan.clicked.connect(self._tagopt_scan)
        arow.addWidget(self.btn_to_scan)
        self.btn_to_run = QPushButton("执行写入")
        self.btn_to_run.setObjectName("Ghost")
        self.btn_to_run.setEnabled(False)
        self.btn_to_run.setToolTip("把预览结果写回 nfo（会先弹一次确认）")
        self.btn_to_run.clicked.connect(self._tagopt_apply)
        arow.addWidget(self.btn_to_run)
        self.btn_to_clear = QPushButton("清空预览")
        self.btn_to_clear.setObjectName("Ghost")
        self.btn_to_clear.clicked.connect(self._tagopt_clear)
        arow.addWidget(self.btn_to_clear)
        # 结果文件导入 / 导出 —— 扫全库 nfo 要逐个读盘（还可能跑 AI），
        # 当天没写完的导出来，第二天导入后**直接点「执行写入」**，不必重新扫。
        sep_to = QFrame()
        sep_to.setObjectName("VRule")
        sep_to.setFixedWidth(1)
        sep_to.setFixedHeight(18)
        arow.addSpacing(6)
        arow.addWidget(sep_to)
        arow.addSpacing(6)
        self.btn_to_exp = QPushButton("导出结果文件…")
        self.btn_to_exp.setObjectName("Ghost")
        self.btn_to_exp.setToolTip("把当前预览的改动清单存成一个 JSON，下次可导入后直接写入")
        self.btn_to_exp.clicked.connect(self._tagopt_export_result)
        arow.addWidget(self.btn_to_exp)
        self.btn_to_imp = QPushButton("导入结果文件…")
        self.btn_to_imp.setObjectName("Ghost")
        self.btn_to_imp.setToolTip("导入上次导出的改动清单，填回预览表格后可直接执行写入")
        self.btn_to_imp.clicked.connect(self._tagopt_import_result)
        arow.addWidget(self.btn_to_imp)
        arow.addStretch(1)
        g3v.addLayout(arow)

        self.to_progress = QProgressBar()
        self.to_progress.setRange(0, 100)
        self.to_progress.setValue(0)
        self.to_progress.setTextVisible(False)
        self.to_progress.setFixedHeight(10)
        g3v.addWidget(self.to_progress)
        self.to_status = QLabel("还没有扫描。选好范围后点「扫描并预览」——"
                               "这一步只读不写，不会改动任何文件。")
        self.to_status.setWordWrap(True)
        # 进度文案里会出现 `||`、`&` 之类的原文，强制纯文本，别让 QLabel 当富文本解析
        self.to_status.setTextFormat(Qt.PlainText)
        self.to_status.setStyleSheet("color:#8c8071;font-size:11px;")
        g3v.addWidget(self.to_status)

        self.to_table = QTableWidget(0, 5)
        self.to_table.setHorizontalHeaderLabels(
            ["文件", "引擎", "原有标签", "将新增", "日语→中文"])
        self.to_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.to_table.verticalHeader().setVisible(False)
        self.to_table.setShowGrid(False)
        self.to_table.setMinimumHeight(230)
        hh = self.to_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for _i in (1, 2, 3, 4):
            hh.setSectionResizeMode(_i, QHeaderView.ResizeToContents)
        g3v.addWidget(self.to_table, 1)
        v.addWidget(g3)

        v.addStretch(1)
        self._to_plans = []
        self._to_changed = []

        # ---------- 统一接信号 ----------
        # 放在最后接：上面 setChecked / setCurrentIndex 都发生在连接之前，
        # 否则回调会读到「还没建出来」的控件（本项目踩过这种构造期回调）。
        for rb in (self.rb_to_file, self.rb_to_folder, self.rb_to_lib):
            rb.toggled.connect(self._tagopt_scope_changed)
            rb.toggled.connect(self._tagopt_save_prefs)
        for rb in (self.rb_to_normal, self.rb_to_ai):
            rb.toggled.connect(self._on_tagopt_algo_changed)
        for ck in (self.ck_to_trans, self.ck_to_over, self.ck_to_full, self.ck_to_bak):
            ck.toggled.connect(self._tagopt_save_prefs)
        self.ck_to_trans.toggled.connect(self._on_to_trans_changed)
        self.to_path.editingFinished.connect(self._tagopt_save_prefs)
        self.to_lib.currentIndexChanged.connect(self._tagopt_save_prefs)
        self._tagopt_scope_changed()
        self._on_to_trans_changed()
        return page

    # ---------- 标签优化：状态与偏好 ----------
    def _tagopt_scope(self):
        if self.rb_to_folder.isChecked():
            return "folder"
        if self.rb_to_lib.isChecked():
            return "library"
        return "file"

    def _tagopt_value(self):
        if self._tagopt_scope() == "library":
            return str(self.to_lib.currentData() or "")
        return str(self.to_path.text() or "").strip()

    def _tagopt_kwargs(self):
        """交给 tagopt.TagOptimizer.plan_one 的参数。"""
        trans = self.ck_to_trans.isChecked()
        return dict(algo=("ai" if self.rb_to_ai.isChecked() else "normal"),
                    translate=trans,
                    overwrite=trans and self.ck_to_over.isChecked(),
                    complete=self.ck_to_full.isChecked(),
                    use_cooccur=True,
                    ai_model=(self.s.recommend.get("ai_model") or None),
                    ai_limit=14)

    def _tagopt_save_prefs(self, *_):
        self.s.set_tagopt(scope=self._tagopt_scope(),
                          path=str(self.to_path.text() or "").strip(),
                          library=str(self.to_lib.currentData() or ""),
                          algo=("ai" if self.rb_to_ai.isChecked() else "normal"),
                          translate=self.ck_to_trans.isChecked(),
                          overwrite=self.ck_to_over.isChecked(),
                          complete=self.ck_to_full.isChecked(),
                          backup=self.ck_to_bak.isChecked())

    def _tagopt_scope_changed(self, *_):
        sc = self._tagopt_scope()
        is_lib = (sc == "library")
        self.to_path.setEnabled(not is_lib)
        self.btn_to_browse.setEnabled(not is_lib)
        self.to_lib.setEnabled(is_lib)
        if sc == "file":
            self.to_path.setPlaceholderText("视频文件或 .nfo 的完整路径")
            self.btn_to_browse.setText("选文件…")
            tip = "只处理这一个文件对应的 nfo"
            place = "视频文件或 .nfo 的完整路径"
        elif sc == "folder":
            self.to_path.setPlaceholderText("文件夹路径（其下所有 .nfo 都会被处理）")
            self.btn_to_browse.setText("选文件夹…")
            tip = "会递归处理该目录下找到的全部 .nfo（*.bak-* 备份文件会被跳过）"
            place = "文件夹路径（其下所有 .nfo 都会被处理）"
        else:
            self.to_path.setPlaceholderText("（媒体库模式下不用填路径）")
            self.btn_to_browse.setText("浏览…")
            tip = ("当前共 %d 个媒体库" % len(self.s.libraries or []))
            place = "（媒体库模式下不用填路径）"
        self.to_path.setPlaceholderText(place)
        self.lb_to_scope.setText(tip)

    def _on_to_trans_changed(self, *_):
        """「覆盖源标签」只有先勾了「日语转中文」才有意义。"""
        on = self.ck_to_trans.isChecked()
        self.ck_to_over.setEnabled(on)
        self.ck_to_over.setToolTip(
            "勾上：日语标签直接被中文替换（标签总数不变）。\n"
            "不勾：保留原日语标签，并在它后面补一条中文（两种写法都能搜到）。"
            if on else "先勾上「日语标签转中文」才用得到这一项。")

    def _tagopt_browse(self):
        cur = str(self.to_path.text() or "").strip()
        if self._tagopt_scope() == "folder":
            p = QFileDialog.getExistingDirectory(self, "选择文件夹", cur)
        else:
            p, _flt = QFileDialog.getOpenFileName(
                self, "选择文件", cur,
                "视频或 nfo (*.mp4 *.mkv *.avi *.wmv *.ts *.mov *.nfo);;所有文件 (*)")
        if p:
            self.to_path.setText(p)
            self._tagopt_save_prefs()

    def _on_tagopt_algo_changed(self, *_):
        self._tagopt_save_prefs()
        if not self.rb_to_ai.isChecked():
            self.to_ai_state.setStyleSheet("color:#8c8071;font-size:11px;")
            self.to_ai_state.setText("当前用普通智能算法：纯本地规则 + 全库标签共现，"
                                     "完全不依赖 AI，速度最快。")
            return
        w = getattr(self, "_to_ai_worker", None)
        if w is not None and w.isRunning():
            return
        self.to_ai_state.setStyleSheet("color:#e8d27a;font-size:11px;")
        self.to_ai_state.setText("正在检测本地 AI 引擎…")
        self._to_ai_worker = AiProbeWorker()
        self._to_ai_worker.done.connect(self._on_to_ai_probe)
        self._to_ai_worker.start()

    def _on_to_ai_probe(self, st):
        st = st or {}
        eng = st.get("engine")
        if eng == "ollama":
            self.to_ai_state.setStyleSheet("color:#9ecf8a;font-size:11px;")
            self.to_ai_state.setText("本地离线 AI 可用：" + html_esc(st.get("label"))
                                     + "　—— 想换模型去「智能推荐」页填。")
        elif eng == "error":
            self.to_ai_state.setStyleSheet("color:#e08a7a;font-size:11px;")
            self.to_ai_state.setText("AI 引擎检测失败，将退回内置算法："
                                     + html_esc(st.get("detail")))
        else:
            self.to_ai_state.setStyleSheet("color:#e8d27a;font-size:11px;")
            self.to_ai_state.setText("没检测到可用的本地模型，将退回内置算法："
                                     + html_esc(st.get("detail")))

    # ---------- 标签优化：执行 ----------
    def _tagopt_clear(self):
        self._to_plans = []
        self._to_changed = []
        self.to_table.setRowCount(0)
        self.btn_to_run.setEnabled(False)
        self.to_progress.setValue(0)
        self.to_status.setStyleSheet("color:#8c8071;font-size:11px;")
        self.to_status.setText("已清空预览。")

    # ---- v1.33.0（反馈 1）：结果文件导出 / 导入 ----
    def _tagopt_export_result(self):
        """把当前预览的改动清单存成可再次导入的结果文件。"""
        plans = list(getattr(self, "_to_plans", None) or [])
        if not plans:
            QMessageBox.information(self, "提示", "还没有扫描结果，先点「扫描并预览」。")
            return
        default = "标签优化结果.json"
        path, _sel = QFileDialog.getSaveFileName(self, "导出扫描结果", default, "结果文件 (*.json)")
        if not path:
            return
        try:
            p = tagopt_mod.export_json(plans, path)
            changed = len(getattr(self, "_to_changed", None) or [])
            QMessageBox.information(
                self, "完成",
                f"已导出：\n{p}\n\n共 {len(plans)} 条扫描记录（其中 {changed} 条会改动）。"
                f"\n下次用「导入结果文件…」载入，即可直接点「执行写入」。")
            applog.log(f"[标签优化] 已导出结果文件：{p}（{len(plans)} 条）")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _tagopt_import_result(self):
        """导入上次导出的扫描结果 → 填回预览表格，「执行写入」立即可用。"""
        path, _sel = QFileDialog.getOpenFileName(self, "导入扫描结果", "",
                                                 "结果文件 (*.json);;所有文件 (*)")
        if not path:
            return
        try:
            plans = tagopt_mod.import_json(path)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"{e}\n\n请确认选的是本页「导出结果文件…」"
                                                  f"产出的文件。")
            applog.log(f"[标签优化] 导入结果失败：{e}", "error")
            return
        changed = [p for p in plans if not p.get("error")
                   and list(p.get("before") or []) != list(p.get("after") or [])]
        self._to_plans = plans
        self._to_changed = changed
        self._fill_to_table(changed)
        self.btn_to_run.setEnabled(bool(changed))
        self.to_progress.setValue(0)
        self.to_status.setStyleSheet("color:#e8d27a;font-size:11px;")
        self.to_status.setText(
            "已导入 %s：%d 条扫描记录、其中 %d 条标签会变化。"
            "确认无误后点「执行写入」即可（**无需重新扫描**）。"
            % (os.path.basename(path), len(plans), len(changed)))
        applog.log(f"[标签优化] 已导入结果文件：{path}（{len(plans)} 条 / 改动 {len(changed)}）")

    def _on_to_progress(self, i, n, msg):
        if n and n > 0:
            self.to_progress.setValue(max(0, min(100, int(round(i * 100.0 / n)))))
        if msg:
            self.to_status.setText(str(msg))

    def _tagopt_scan(self):
        w = getattr(self, "_to_scan_worker", None)
        if w is not None and w.isRunning():
            return
        sc = self._tagopt_scope()
        val = self._tagopt_value()
        if not val:
            self.to_status.setStyleSheet("color:#e08a7a;font-size:11px;")
            self.to_status.setText(
                "✗ 还没有可处理的目标 —— 先填路径（或选一个媒体库）。"
                if sc != "library" else
                "✗ 当前没有任何媒体库 —— 先去「服务管理」建一个。")
            return
        self._tagopt_save_prefs()
        self.btn_to_scan.setEnabled(False)
        self.btn_to_run.setEnabled(False)
        self.to_table.setRowCount(0)
        self.to_progress.setValue(0)
        self.to_status.setStyleSheet("color:#e8d27a;font-size:11px;")
        self.to_status.setText("正在扫描 " + val + " …这一步只读不写。")
        opt = tagopt_mod.TagOptimizer(self.s)
        self._to_scan_worker = TagOptScanWorker(opt, sc, val, self._tagopt_kwargs())
        self._to_scan_worker.progress.connect(self._on_to_progress)
        self._to_scan_worker.done.connect(self._on_tagopt_scan)
        self._to_scan_worker.start()

    def _on_tagopt_scan(self, plans, err):
        self.btn_to_scan.setEnabled(True)
        self.to_progress.setValue(0)
        plans = list(plans or [])
        self._to_plans = plans
        if err:
            self._to_changed = []
            self.to_table.setRowCount(0)
            self.btn_to_run.setEnabled(False)
            self.to_status.setStyleSheet("color:#e08a7a;font-size:11px;")
            self.to_status.setText("✗ " + str(err))
            return
        changed = [p for p in plans if not p.get("error")
                   and list(p.get("before") or []) != list(p.get("after") or [])]
        self._to_changed = changed
        self._fill_to_table(changed)
        self.btn_to_run.setEnabled(bool(changed))
        if not changed:
            self.to_status.setStyleSheet("color:#9ecf8a;font-size:11px;")
            self.to_status.setText(
                "✓ 扫了 %d 个 nfo，标签都已经是最新的，没有需要改的。" % len(plans))
            return
        add_n = sum(len(p.get("added") or []) for p in changed)
        tr_n = sum(len(p.get("translated") or []) for p in changed)
        ai_n = sum(1 for p in changed if p.get("engine") == "ollama")
        bad_n = sum(1 for p in plans if p.get("error"))
        bits = ["扫了 %d 个 nfo，其中 %d 个标签会变化；预计新增 %d 条标签"
                % (len(plans), len(changed), add_n)]
        if tr_n:
            bits.append("、翻译 %d 条日语标签" % tr_n)
        if ai_n:
            bits.append("（%d 个用了本地离线 AI）" % ai_n)
        if bad_n:
            bits.append("；另有 %d 个读取失败" % bad_n)
        bits.append("。确认无误后点「执行写入」。表格里的数字都能悬停看明细。")
        self.to_status.setStyleSheet("color:#e8d27a;font-size:11px;")
        self.to_status.setText("".join(bits))

    def _fill_to_table(self, plans, cap=800):
        self.to_table.setRowCount(0)
        for p in list(plans or [])[:cap]:
            r = self.to_table.rowCount()
            self.to_table.insertRow(r)
            nfo = str(p.get("nfo") or "")
            it0 = QTableWidgetItem(os.path.basename(nfo) or nfo)
            it0.setToolTip(nfo)
            self.to_table.setItem(r, 0, it0)
            self.to_table.setItem(r, 1, QTableWidgetItem(
                "本地 AI（Ollama）" if p.get("engine") == "ollama" else "内置算法"))
            self.to_table.setItem(r, 2, QTableWidgetItem(str(len(p.get("before") or []))))
            added = [str(x) for x in (p.get("added") or [])]
            it3 = QTableWidgetItem("+" + str(len(added)))
            it3.setToolTip("、".join(added) if added else "（无新增）")
            self.to_table.setItem(r, 3, it3)
            tr = list(p.get("translated") or [])
            it4 = QTableWidgetItem(str(len(tr)))
            it4.setToolTip("；".join("%s → %s" % (a, b) for a, b in tr) if tr
                           else "（没有需要翻译的日语标签）")
            self.to_table.setItem(r, 4, it4)
        n = len(plans or [])
        if n > cap:
            self.to_status.setText(self.to_status.text()
                                   + "（表格只列前 %d 个，实际会处理全部 %d 个）" % (cap, n))

    def _tagopt_apply(self):
        w = getattr(self, "_to_run_worker", None)
        if w is not None and w.isRunning():
            return
        changed = list(self._to_changed or [])
        if not changed:
            return
        n = len(changed)
        backup = self.ck_to_bak.isChecked()
        if backup:
            tail = "\n\n写入前会把每个原文件另存为 *.nfo.bak-<时间戳>，随时可手工还原。"
        else:
            tail = "\n\n注意：你已经关掉「写入前备份」——原标签会被直接改写，无法撤销。"
        if QMessageBox.question(
                self, "确认写入标签",
                "将把预览结果写回 %d 个 nfo 文件。" % n + tail,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.btn_to_run.setEnabled(False)
        self.btn_to_scan.setEnabled(False)
        self.to_progress.setValue(0)
        self.to_status.setStyleSheet("color:#e8d27a;font-size:11px;")
        self.to_status.setText("正在写入 %d 个 nfo…（同时同步数据库里的标签）" % n)
        opt = tagopt_mod.TagOptimizer(self.s)
        self._to_run_worker = TagOptRunWorker(opt, changed, backup)
        self._to_run_worker.progress.connect(self._on_to_progress)
        self._to_run_worker.done.connect(self._on_tagopt_applied)
        self._to_run_worker.start()

    def _on_tagopt_applied(self, stats):
        self.btn_to_scan.setEnabled(True)
        self.to_progress.setValue(0)
        s = stats or {}
        errs = list(s.get("errors") or [])
        head = ("✓ 完成：写入 %d 个 · 跳过 %d 个 · 失败 %d 个 · 数据库同步 %d 条"
                % (s.get("written", 0), s.get("skipped", 0),
                   s.get("failed", 0), s.get("db_synced", 0)))
        if errs:
            head += "（首个错误：" + str(errs[0]) + "）"
            self.to_status.setStyleSheet("color:#e8d27a;font-size:11px;")
        else:
            self.to_status.setStyleSheet("color:#9ecf8a;font-size:11px;")
        self.to_status.setText(head)
        applog.log("[标签优化] " + head)
        self._to_plans = []
        self._to_changed = []
        self.btn_to_run.setEnabled(False)
        if self.on_changed:
            self.on_changed()
