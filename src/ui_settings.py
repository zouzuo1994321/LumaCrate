# -*- coding: utf-8 -*-
"""
设置界面（参考截图 2–7）
========================
- 个性化设置：导航菜单(开关 + 上下排序) / 首页管理(模块开关) / 内容卡片(显示评分·分辨率·演员·导演)
- 服务管理：媒体库(新建 / 列表 / 扫描全部 —— 全部由用户自己命名，无内置库) / 后台任务管理(启用 / 库 / 时间 / 频率)
自绘 ToggleSwitch（无额外图片依赖）。
"""
import json
import os
import math
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import zipfile
from datetime import datetime

from PySide6.QtCore import (Qt, QThread, Signal, QPropertyAnimation, Property, QTime,
                            QEasingCurve, QSize, QTimer, QRectF, QPointF)
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QFont, QBrush, QPainterPath
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QStackedWidget, QFrame, QLineEdit, QComboBox, QTimeEdit,
    QFileDialog, QWidget, QAbstractButton, QAbstractItemView, QGroupBox,
    QFormLayout, QGridLayout, QMessageBox, QCheckBox, QRadioButton, QInputDialog,
    QSpinBox, QProgressBar, QPlainTextEdit, QApplication, QSlider, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QDoubleSpinBox, QScrollArea,   # v1.40.7：`_freeze()` 要用（原来是函数内局部 import）
)

import config as cfg
import database as db
import duplicates as dup_mod
import insight as insight_mod
import recommend as rec_mod
import scraper as scraper_mod
import browser_session                  # v1.41.0（方案B）：常驻浏览器抓取会话
import applog
import backup as backup_mod
import prefs as prefs_mod          # v1.43.0：偏好管理（番号级收藏 / 评分 / 人物收藏置顶）
from ui_cleanup import PeopleCleanDialog   # v1.43.0：演员库清理
import tagopt as tagopt_mod
import ui_imagedetect              # v1.30.0 反馈 2：图像检测
import ui_manualedit               # v1.30.0 反馈 3：手动修改
import ui_actorcheck               # v1.31.0 反馈 3：演员检测
import i18n                        # v1.32.0 反馈 3：界面语言（19 种）
from scan_ring import ScanRing     # v1.39.0（需求 3）：导航项「进行中」转圈

# v1.40.11：执行日志框（sc_log）与「运行日志（实时）」框（_log_view）统一为同一套样式。
# 等宽字体 + 半透明深色底 + 浅色字，复制运行日志的观感（仅样式复刻，不做实时文件 tail）。
LOG_BOX_STYLE = (
    "font-family: Consolas, 'Courier New', Menlo, monospace; "
    "font-size:11px; background:rgba(0,0,0,0.25); color:#d4d4d8;"
)
from ui_hero import compact_button


def cf_browser_snapshot_path():
    """v1.40.2（反馈 2）：内置浏览器留下的**持久 cookie 快照**路径。

    与 `cf_browser.py` 里 `SNAPSHOT_NAME` 必须一致 —— 那边每次成功取到 cookie
    都会额外写一份到这里，这样**关窗之后**「读取 Cookie」按钮仍读得到，
    不必重新过一次人机校验。
    """
    try:
        import cf_browser
        return cf_browser.snapshot_path()
    except Exception:
        import tempfile
        return os.path.join(tempfile.gettempdir(), "lmc_cf_snapshot.json")


# v1.13.0：拉大行距，避免列表里内容被裁（反馈 1/2）；导航菜单列表高度改为按条目数自适应（反馈 7）
# v1.22.0：再整体加大一档 —— 用户反馈「提高行距以保证按钮完整显示」，行内 28~30px 的
# ↑/↓/测试 等窄按钮原来贴边（行高 = 按钮高 + 上下边距刚好相等），字体降级/DPI 缩放时
# 底部会被裁掉一截。这里把每行高度提到「按钮高 + 16px 呼吸」。
NAV_ROW_H = 52          # 导航菜单每行高度（含 ↑/↓ + 开关）
SRC_ROW_H = 44          # 数据源每行高度（描述允许换到第 2 行 + ↑/↓/测试）
# v1.14.0 反馈 6：媒体库列表每行也要留足高度 —— 原来用 row.sizeHint()，
# 行内的「编辑/扫描/删除」按钮被压得底部缺一截（截图为证）。
# v1.46.15（反馈「压缩已配置的媒体库的高度」）：54 → 44。54 的时候行里其实空着一大截：
#   列表项自带 `QListWidget::item{padding:5px 4px}` 吃掉上下各 5px（行内控件实际只有 44，
#   按钮 28 + 行内边距 8 = 36，还剩 8px 分给上下），视觉上三行像被拉开。
#   现在把这个列表单独命名 `LibList`，在 QSS 里把 item padding 压到 2px，行高 44 →
#   行内控件正好 40 = 按钮 28 + 行边距 8 + 4px 余量；列表整体 3 行从 172 → 138。
LIB_ROW_H = 44          # 媒体库每行高度（按此定 sizeHint，按钮完整可见）
#: 列表容器自身的额外高度 = 上下边框各 1px + 首/末项 2px 内边距（QSS #LibList::item）。
#  v1.46.15 之前是写死的 +10：那是给 5px item padding 留的，跟着 44 的行高会多出一条空白。
LIST_CHROME = 6


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


# ---------- 自绘色卡（v1.43.4 起自绘；v2.0.0 改 HeroUI 圆形）----------
class _AccentSwatch(QPushButton):
    """高亮色色卡：**正圆色点 + 选中白环 + 手绘勾**（HeroUI 的 swatch 语义）。

    为什么不用「QSS 圆角 + 文字 ✓」（v1.43.4 真机截图实锤的两个问题）：
      ① 26×26 + `border-radius:13px`（正圆）时，圆角会把中间的 ✓ 裁掉一圈；
      ② **✓ 这个字形在按钮字体下根本渲染不出来**，白边里是个 tofu 方框。
    ⇒ 自绘：圆、环、勾全部 QPainter 画，尺寸与字形都不依赖字体与 QSS。

    v2.0.0：从「30×24 圆角扁平方形」改成 **28×28 正圆**，选中态参考 HeroUI Pro
    的模板配色切换器 —— 色点外一圈 2px 白环（留 2px 间隙）+ 居中的白勾。
    色点的直径固定 20（选中时 18，给白环让位），11 个点排在 1170 宽的内容区里绰绰有余。
    """

    W = H = 28
    R_DOT = 10.0          # 未选中：色点半径
    R_DOT_ON = 9.0        # 选中：色点略缩，给白环留间隙
    R_RING = 13.0         # 选中：外环半径
    RING_W = 2.0

    def __init__(self, hexv, name="", parent=None):
        super().__init__(parent)
        self._hex = hexv
        self._name = name
        self._on = False
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("QPushButton{background:transparent;border:none;padding:0;}")
        if name:
            self.setToolTip(f"{name}  {hexv}")

    def set_on(self, on: bool):
        if bool(on) != self._on:
            self._on = bool(on)
            self.update()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            cx, cy = self.width() / 2.0, self.height() / 2.0
            hover = self.underMouse()
            if self._on:
                # 选中：外环（白）+ 间隙 + 色点 + 勾
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, 235), self.RING_W))
                p.drawEllipse(QPointF(cx, cy), self.R_RING, self.R_RING)
                r = self.R_DOT_ON
            else:
                r = self.R_DOT + (0.6 if hover else 0.0)
            p.setBrush(QColor(self._hex))
            p.setPen(QPen(QColor(255, 255, 255, 70 if not hover else 120), 1.0))
            p.drawEllipse(QPointF(cx, cy), r, r)
            if self._on:
                # 手绘勾：线宽 2、圆头，按色点半径等比缩放，怎么缩都不会被裁
                pen = QPen(QColor(255, 255, 255), 2.0)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                p.setPen(pen)
                path = QPainterPath()
                path.moveTo(cx - 3.9, cy + 0.3)
                path.lineTo(cx - 1.1, cy + 3.1)
                path.lineTo(cx + 4.1, cy - 3.2)
                p.drawPath(path)
        finally:
            p.end()


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

    # 轨道底色：关 #3f3f46 → 开 <当前高亮色>。
    # v1.26.0（反馈 1）：原来这里写死朱红 —— 用户在「外观 → 高亮色」里换成藕荷/天青后，
    # 设置页里所有自绘开关的轨道**仍然是红的**（截图：色板高亮停在藕荷，开关全是朱红）。
    # 现在改成每次绘制时现取高亮色（与 QSS 令牌同源）。_ON 保留为兜底值 = ACCENT_DEFAULT。
    _OFF = (0x3f, 0x3f, 0x46)
    _ON = (0x00, 0x6f, 0xee)

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
        p.setBrush(QColor("#fafafa"))
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
    """数据源连接自检（不阻塞界面）。

    v1.46.6（反馈 4）：新增 `as_url=True` —— 「其他数据源」填的自定义站点不在
    `SOURCE_BASES` 里，走 `test_source_url()` 直接测那个网址。
    """
    done = Signal(str, dict)

    def __init__(self, source, proxy, timeout, as_url=False):
        super().__init__()
        self.source, self.proxy, self.timeout = source, proxy, timeout
        self.as_url = bool(as_url)

    def run(self):
        try:
            if self.as_url:
                r = scraper_mod.test_source_url(self.source, self.proxy, self.timeout)
            else:
                r = scraper_mod.test_source(self.source, self.proxy, self.timeout)
        except Exception as e:
            r = {"ok": False, "msg": f"{type(e).__name__}: {e}", "ms": 0}
        self.done.emit(self.source, r)


class TestCookieWorker(QThread):
    """v1.44.1（需求 3）：用已获取的 Cookie 做一次存活检测（不阻塞界面）。

    v1.46.5（反馈 2）：新增 `as_url=True` 分支 —— 「其他数据源」填的是**自建 / 第三
    方站点网址**，不在 `SOURCE_BASES` 里，走 `test_cookie_url()`；`done` 里 `source`
    原样回传该网址，由专用槽函数认领（不会串到内置源的行标签上）。
    """
    done = Signal(str, dict)

    def __init__(self, source, proxy, timeout, as_url=False):
        super().__init__()
        self.source, self.proxy, self.timeout = source, proxy, timeout
        self.as_url = bool(as_url)

    def run(self):
        try:
            if self.as_url:
                r = scraper_mod.test_cookie_url(self.source, self.proxy, self.timeout)
            else:
                r = scraper_mod.test_cookie(self.source, self.proxy, self.timeout)
        except Exception as e:
            r = {"ok": False, "msg": f"{type(e).__name__}: {e}", "ms": 0,
                 "has_cookie": False}
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
            p.setPen(QColor("#71717a"))
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
        p.setPen(QPen(QColor("#338ef7"), 2.0))
        p.setBrush(QBrush(QColor(51, 142, 247, 62)))
        p.drawPolygon(poly)
        # 3) 顶点小圆点
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#8fc0ff"))
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
            p.setPen(QColor("#a1a1aa"))
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


class OllamaLaunchWorker(QThread):
    """用 powershell 拉起本机 Ollama（v1.35.0 需求 1）。

    后台跑 `recommend.launch_ollama()`：先探测是否已经在跑，没跑就
    `Start-Process ollama serve` 后台拉起，再用 /api/tags 轮询确认起来了。
    避免把软件启动 / 设置窗口卡在 Ollama 的启动等待上。
    """

    done = Signal(bool, str)

    def run(self):
        try:
            ok, msg = rec_mod.launch_ollama()
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"
        self.done.emit(bool(ok), str(msg))


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


class PrefsWorker(QThread):
    """偏好导入 / 导出，搬到后台线程跑（v1.46.12）。

    为什么必须搬：原来 `_export_prefs/_import_prefs` 直接在当前（GUI）线程里调
    `prefs_mod.export_prefs/import_prefs`，实测一次导入 **7.09s** 且期间事件循环
    **一次都不跳**（50ms 定时器 0 次触发）——
      · 415 个 nfo 逐个回写（每个要 exists + ET.parse + tree.write）≈ 4.2s；
      · 结尾 `on_changed()` 整页重建 ≈ 1.4s；
      · 中途没有任何 `processEvents()`。
    Windows 只要 5 秒不泵消息就给窗口打「未响应」，用户看到的就是「卡死了」。

    这里只做两件事：跑真活、把 `progress` 转发出去；界面归页面管。
    `request_stop()` 是**协作式**的 —— 真正的停止点在 `prefs._tick` 每次回调时
    看返回值，所以点「停止」最多等到下一批（25 条 / 2 次 nfo 写回）。
    """

    progress = Signal(int, int, str)      # done, total（0=不定长）, label
    done = Signal(dict)

    def __init__(self, mode, path, include=None, parent=None):
        super().__init__(parent)
        self.mode = mode                  # "export" / "import"
        self.path = path
        self.include = list(include or [])
        self._stop = False

    def request_stop(self):
        self._stop = True

    def _cb(self, done, total, label):
        self.progress.emit(int(done), int(total), str(label))
        return self._stop                 # True → prefs 侧就地中止

    def run(self):
        try:
            if self.mode == "export":
                r = prefs_mod.export_prefs(self.path, "all", self.include,
                                           progress=self._cb)
            else:
                r = prefs_mod.import_prefs(self.path, progress=self._cb)
        except Exception as e:            # prefs 内部已兜底，这里是双保险
            r = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        finally:
            # 本线程的 SQLite 连接用完就关 —— 别留给已结束的线程
            # （db.get_conn 是 thread-local，不关会挂在 threading.local 里等 GC）
            try:
                db.close_conn()
            except Exception:
                pass
        self.done.emit(r)


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
        hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        b_fill.setToolTip("按「画像概览」里权重最高的标签 / 片商 / 演员自动生成一批权重。\n"
                          "会先弹面板让你选统计范围（全部 / 我的收藏 / 某个媒体库）、\n"
                          "每个维度取前多少个、每个维度给多少权重，选完记住。")
        b_fill.clicked.connect(self._autofill)
        b_fav = QPushButton("从收藏的演员自动填充")
        b_fav.setObjectName("Ghost")
        b_fav.setToolTip("把你「演员库 / 导演库」里**收藏（★）**的演员与导演，\n"
                         "一键写成向量权重，让智能推荐明显偏向他们。")
        b_fav.clicked.connect(self._autofill_fav)
        b_del = QPushButton("删除选中")
        b_del.setObjectName("Ghost")
        b_del.clicked.connect(self._delete)
        b_clr = QPushButton("全部清空")
        b_clr.setObjectName("Ghost")
        b_clr.clicked.connect(self._clear)
        btns.addWidget(b_fill)
        btns.addWidget(b_fav)
        btns.addWidget(b_del)
        btns.addStretch(1)
        btns.addWidget(b_clr)
        v.addLayout(btns)

        self.status = QLabel("—")
        self.status.setStyleSheet("color:#71717a;font-size:11px;")
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
        """打开参数面板，按「画像概览」的高频项生成一批权重。

        v1.34.0（需求 1）：原来这里是**硬编码**的计划（标签前 30 / 其余各前 10，
        权重 1.5/1.3/1.2，统计范围固定全库）。现在改成先弹 `AutoFillDialog`
        让用户自己选 **统计范围 / 每维度前 N / 每维度权重**，选完记住偏好。
        """
        dlg = AutoFillDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        # 面板确认时已经写完库、也存好偏好 —— 这里只负责刷新列表
        self.reload()
        n = len(db.vector_overrides())
        self.status.setText(f"已按所选参数自动填充，现在共 {n} 条手动权重。")
        if self.on_saved:
            self.on_saved()

    def _autofill_fav(self):
        """从收藏的演员 / 导演自动填充（v1.35.0 需求 2）。

        把「演员库 / 导演库」里 **收藏（favorite=1）** 的人，一键写成向量权重
        （actor / director 维度），让智能推荐明显偏向他们。权重用同一个量级
        （默认 1.5，0~5 可选）。
        """
        try:
            favs = db.favorite_people() or []
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"读取收藏的演员失败：{e}")
            return
        picks = []
        for p in favs:
            role = str(p.get("role_type") or "").lower()
            if role.startswith("direct"):
                dim = "director"
            elif role.startswith("actor"):
                dim = "actor"
            else:
                continue
            picks.append((dim, str(p.get("name") or "").strip()))
        picks = [(d, n) for d, n in picks if n]
        if not picks:
            QMessageBox.information(
                self, "没有可填充的",
                "你还没有在「演员库 / 导演库」里收藏（★）任何演员或导演。\n"
                "先去收藏几位，再来这里一键填充。")
            return
        w, ok = QInputDialog.getDouble(
            self, "从收藏的演员自动填充",
            f"将你收藏的 {len(picks)} 位演员 / 导演写成向量权重，\n"
            "权重越大越偏向他们（1 = 默认，2 = 明显偏向）：",
            1.5, 0.0, 5.0, 1)
        if not ok:
            return
        for dim, name in picks:
            db.set_vector_override(dim, name, w)
            self.s.set_vector_weight(dim, name, w)
        applog.log(f"[向量编辑] 从收藏的演员自动填充 {len(picks)} 位，权重 {w:g}")
        self.reload()
        self.status.setText(
            f"已从收藏的演员自动填充 {len(picks)} 位（权重 {w:g}），"
            f"现在共 {len(db.vector_overrides())} 条手动权重。")
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


class CloudflareDialog(GlassDialog):
    """v1.40.1（反馈 3）：Cloudflare / AWS WAF 验证助手 —— **内置浏览器**取 cookie。

    用户原话：「站点验证使用内置浏览器，参考 微博bot小助手 那种方式来获取 cookie」。

    v1.40.0 的做法是「用系统浏览器打开 → F12 抠 document.cookie → 粘回来」。用户
    实测觉得太绕（要开 DevTools、要找到 cf_clearance、还要手动粘贴）。改成**内置
    浏览器**：本对话框点「打开内置浏览器」后，弹出一个内嵌 WebView2 的窗口，用户
    在里面把 Cloudflare / AWS WAF 的验证过掉，窗口右下角有个「✅ 我已完成验证，
    读取 Cookie」按钮，点一下 cookie 就自动取回、注入刮削器并复测 —— 全程不用碰
    DevTools。

    为什么走子进程（关键取舍）
      · 复刻的是 微博bot小助手 的 `pywebview` + `window.get_cookies()` 路线
        （它复用的是系统自带的 **WebView2 运行时**，exe 只 58.7MB，不打包 Chromium）；
      · 但 pywebview 有硬约束：`webview.start()` **必须在 MainThread**（源码断言
        「pywebview must be run on a main thread.」）。而本软件是 PySide6/Qt，
        `app.exec()` 独占主线程 → 同进程调不了。微博bot 整个 GUI 就是 pywebview，
        所以它在主线程；我们只能**另起一个子进程**跑浏览器（`src/cf_browser.py`）。
      · 父子通信走**结果 JSON 文件**（子进程原子写、父进程轮询），零 IPC 依赖，
        子进程崩了也只丢一次验证、不会拖垮主界面。

    为什么不用 QWebEngineView：它要拖进 ~150MB 的 Chromium 运行时（Qt6WebEngineCore.dll
    194MB + icudtl.dat 10MB …），对「单文件 exe」是灾难级代价；且它自己的指纹同样
    可能被 Cloudflare 挡（等于白加）。pywebview 复用系统 WebView2，代价近乎为零。

    保留的手动通路：内置浏览器不可用时（WebView2 未装 / pywebview 缺失），仍可
    「手动粘贴 cookie」—— 折叠在「高级 ▾」里，不占主视线。
    """

    def __init__(self, host_url, title, parent=None, on_done=None):
        super().__init__(parent)
        self.host_url = host_url
        self.on_done = on_done
        self._proc = None
        self._session_owned = False     # v1.41.0（方案B）：存活子进程已托管给浏览器会话
        self._resfile = None
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll_result)
        self.setWindowTitle(title or "Cookie 获取")
        self.setMinimumWidth(660)

        v = QVBoxLayout(self)
        # v1.40.2（反馈 1）：用户截图指出「行与行间隔太大」—— 把外边距与行距都收紧
        # （16→10 / 12→7），并把两步说明压成单行显示（原来每步各占一行还多留白）。
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(7)

        # v1.44.1（需求 3）：顶部网址**可点击** —— 点一下就用内置浏览器进入该站点
        head = QLabel(
            f"<b>数据源网址：</b><a href='{html_esc(host_url)}' "
            f"style='color:#d4d4d8;'>{html_esc(host_url)}</a><br>"
            "点上面这个网址（或下方「打开内置浏览器」）进入站点，"
            "<b>登录 / 过完人机校验</b>后点「获取 Cookie」，自动抓取并复用。")
        head.setWordWrap(True)
        head.setTextFormat(Qt.RichText)
        head.setStyleSheet("color:#d4d4d8;font-size:12px;")
        head.setOpenExternalLinks(False)
        head.linkActivated.connect(lambda _u="": self._open_builtin())
        v.addWidget(head)

        steps = QLabel(
            "<b>两步走：</b>① 点上方网址进入站点，必要时先<b>登录账号</b>；"
            "② 回到这里点「<b>获取 Cookie</b>」——通行 cookie 会自动取回并复测。")
        steps.setTextFormat(Qt.RichText)
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.RichText)
        steps.setStyleSheet("color:#a1a1aa;font-size:11px;")
        v.addWidget(steps)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_open = QPushButton("打开内置浏览器")
        self.btn_open.setObjectName("Primary")
        self.btn_open.setToolTip("弹出内置 WebView2 窗口，在里面完成站点的人机校验")
        self.btn_open.clicked.connect(self._open_builtin)
        row.addWidget(self.btn_open)
        # v1.40.2（反馈 2）：**独立**的「读取 Cookie」按钮 —— 用户明确要求
        # 「单独安排一个按钮进行 cookie 读取」。之前唯一入口是内置浏览器窗口右下角
        # 那个按钮，窗口一关就没了；现在主对话框里直接可读：
        #   · 内置浏览器还开着 → 直接去问它要（走结果文件 / 请求它 dump）；
        #   · 已经关掉了 → 读内置浏览器上次留下的用户数据目录里的 cookie。
        self.btn_read = QPushButton("获取 Cookie")
        self.btn_read.setObjectName("Primary")
        self.btn_read.setToolTip(
            "从内置浏览器读取该站点的 cookie（含 cf_clearance）并注入刮削器。\n"
            "内置浏览器还开着会直接取；已关闭则读上次留下的一份。")
        self.btn_read.clicked.connect(self._read_cookie)
        row.addWidget(self.btn_read)
        self.btn_webview = QPushButton("检查环境")
        self.btn_webview.setObjectName("Ghost")
        self.btn_webview.setToolTip("确认 pywebview 与系统 WebView2 运行时是否就绪")
        self.btn_webview.clicked.connect(self._check_webview)
        row.addWidget(self.btn_webview)
        row.addStretch(1)
        v.addLayout(row)

        self.state = QLabel("—")
        self.state.setWordWrap(True)
        self.state.setStyleSheet("color:#a1a1aa;font-size:11px;")
        v.addWidget(self.state)

        # ---------- 高级 ▾：手动粘贴 cookie（内置浏览器不可用时的兜底） ----------
        self.btn_adv = QPushButton("高级选项（手动粘贴 cookie）")
        self.btn_adv.setObjectName("Ghost")
        self.btn_adv.setCheckable(True)
        self.btn_adv.toggled.connect(self._toggle_adv)
        v.addWidget(self.btn_adv)

        self.adv = QWidget()
        av = QVBoxLayout(self.adv)
        av.setContentsMargins(0, 2, 0, 0)
        av.setSpacing(5)
        tip = QLabel("在系统浏览器里按 F12 → Console 执行 <code>document.cookie</code>，"
                     "把整串结果（重点含 <code>cf_clearance</code>）粘到下面：")
        tip.setWordWrap(True)
        tip.setTextFormat(Qt.RichText)
        tip.setStyleSheet("color:#a1a1aa;font-size:11px;")
        av.addWidget(tip)
        self.ed = QPlainTextEdit()
        self.ed.setPlaceholderText("cf_clearance=…")
        self.ed.setMinimumHeight(64)
        av.addWidget(self.ed)
        self.adv.setVisible(False)
        v.addWidget(self.adv)

        btns = QHBoxLayout()
        btns.setSpacing(6)
        self.btn_save = QPushButton("保存并校验")
        self.btn_save.setObjectName("Primary")
        self.btn_save.setToolTip("把「高级」里粘贴的 cookie 保存下来并复测")
        self.btn_save.clicked.connect(self._save_and_verify)
        btns.addWidget(self.btn_save)
        self.btn_clear = QPushButton("清除已存 cookie")
        self.btn_clear.setObjectName("Ghost")
        self.btn_clear.clicked.connect(self._clear)
        btns.addWidget(self.btn_clear)
        btns.addStretch(1)
        self.btn_close = QPushButton("关闭")
        self.btn_close.setObjectName("Ghost")
        self.btn_close.clicked.connect(self.close)
        btns.addWidget(self.btn_close)
        v.addLayout(btns)

        self._refresh_state()

    # ---------- 行为 ----------
    def _refresh_state(self):
        st = scraper_mod.cookie_state(self.host_url)
        if st["count"]:
            mark = "✅ 已含通行 cookie" if st["has_pass"] else "⚠ 有 cookie 但没看到 cf_clearance"
            self.state.setText(
                f"{mark}：该站点已保存 {st['count']} 条（{', '.join(st['names'][:6])}）"
                f"，保存于 {st['at']}。")
            self.state.setStyleSheet("color:#45d483;font-size:11px;")
        else:
            self.state.setText("当前该站点没有保存任何手工 cookie，请求仍会被拦。")
            self.state.setStyleSheet("color:#f87171;font-size:11px;")

    def _toggle_adv(self, on):
        self.adv.setVisible(bool(on))
        self.btn_adv.setText("高级 ▴（手动粘贴 cookie）" if on else "高级 ▾（手动粘贴 cookie）")
        self.adjustSize()

    # ---------- 内置浏览器（pywebview 子进程） ----------
    def _helper_cmd(self):
        """构造子进程命令行：优先用冻结 exe（同目录 exe 自身 + `--cf-browser`），
        源码运行时用当前 python 解释器 + src/cf_browser.py。"""
        import tempfile
        resfile = os.path.join(tempfile.gettempdir(), "lmc_cf_result.json")
        try:
            if os.path.exists(resfile):
                os.remove(resfile)
        except Exception:
            # Windows 下偶尔被占用；换个名字即可
            resfile = os.path.join(tempfile.gettempdir(),
                                   "lmc_cf_result_%d.json" % int(time.time()))
        host = urllib.parse.urlparse(self.host_url).netloc
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cf_browser.py")
        # v1.41.0（方案B）：若「用内置浏览器抓取」开关打开，给子进程传 persist=1，
        # 让它在取完 cookie 后**不销毁窗口**、转常驻抓取会话（验证窗口 = 抓取后端）。
        persist = "1" if cfg.get_settings().scraper.get("browser_scrape") else "0"
        if getattr(sys, "frozen", False):
            # 打包后 cf_browser.py 已进 exe；主程序 main.py 里识别 `--cf-browser`
            # 这个开关并把控制权交给 cf_browser.main()。
            cmd = [sys.executable, "--cf-browser", self.host_url, resfile, host, persist]
        else:
            cmd = [sys.executable, script, self.host_url, resfile, host, persist]
        return cmd, resfile

    def _webview_ready(self):
        """探测 pywebview 与系统 WebView2 是否就绪，返回 (ok, 说明)。"""
        if getattr(sys, "frozen", False):
            return True, "内置 exe（已随包带上 pywebview）"
        try:
            import webview            # noqa: F401
        except Exception as e:
            return False, f"pywebview 未安装（{e}）"
        # WebView2 运行时（Edge）
        exe = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                           "Microsoft", "EdgeWebView", "Application")
        found = ""
        try:
            for n in os.listdir(exe):
                p = os.path.join(exe, n, "msedgewebview2.exe")
                if os.path.exists(p):
                    found = n
                    break
        except Exception:
            pass
        if found:
            return True, f"pywebview 就绪，WebView2 运行时 {found}"
        return False, "未找到系统 WebView2 运行时（请安装 Microsoft Edge WebView2 Runtime）"

    def _check_webview(self):
        ok, msg = self._webview_ready()
        self.state.setText(("✅ " if ok else "❌ ") + msg)
        self.state.setStyleSheet(
            "color:#45d483;font-size:11px;" if ok else "color:#f87171;font-size:11px;")

    def _read_cookie(self):
        """v1.40.2（反馈 2）：**独立**的「读取 Cookie」按钮。

        用户原话：「cookie 读取存在问题，单独安排一个按钮进行 cookie 读取」。
        读 cookie 的两条通路，按优先级：
          ① 内置浏览器**还开着**（子进程在跑）→ 令它立刻 dump 一次到结果文件，
             轮询到就注入（复用 `_poll_result` 那条既有链路）；
          ② 内置浏览器**已关闭** → 去读子进程写下的「持久快照」文件
             （`cf_browser.py` 每次成功取 cookie 都会额外存一份到固定路径，
             这样关窗之后仍然读得到，不必重新过一次校验）。
        两条都拿不到就明确告诉用户「先点『打开内置浏览器』过一次校验」。
        """
        # 通路 ①：内置浏览器还开着 → 直接问它要
        if self._proc is not None and self._proc.poll() is None:
            try:
                import tempfile
                resfile = os.path.join(tempfile.gettempdir(), "lmc_cf_result.json")
                # 让子进程主动 dump：结果文件先删掉，再由对话框发一个「请求读取」信号文件
                try:
                    if os.path.exists(resfile):
                        os.remove(resfile)
                except Exception:
                    pass
                reqfile = os.path.join(tempfile.gettempdir(), "lmc_cf_request.json")
                with open(reqfile, "w", encoding="utf-8") as f:
                    f.write('{"action":"dump"}')
                self._resfile = resfile
                self._on_builtin_snapshot = True
                self.state.setText("正在向内置浏览器请求 cookie…（若窗口无响应，"
                                   "请在窗口里点「读取 Cookie」）")
                self.state.setStyleSheet("color:#8fc0ff;font-size:11px;")
                applog.log("[站点验证] 读取 Cookie：内置浏览器在运行，请求 dump")
                if not self._timer.isActive():
                    self._timer.start()
                # 2.5 秒还没等到 → 退回快照
                QTimer.singleShot(2500, self._read_cookie_snapshot)
                return
            except Exception as e:
                applog.log(f"[站点验证] 请求内置浏览器 dump 失败：{e}")
        self._read_cookie_snapshot()

    def _read_cookie_snapshot(self):
        """去读内置浏览器留下的**持久快照**（关窗后仍可用）。"""
        if getattr(self, "_on_builtin_snapshot", False) and self._resfile \
                and os.path.exists(self._resfile):
            return          # 已经读到结果文件了，`_poll_result` 会接手
        snap = cf_browser_snapshot_path()
        if not snap or not os.path.exists(snap):
            self.state.setText("❌ 还没读到任何 cookie —— 请先点「打开内置浏览器」，"
                               "在弹出的窗口里过一次校验再点本按钮。")
            self.state.setStyleSheet("color:#f87171;font-size:11px;")
            applog.log("[站点验证] 读取 Cookie：无快照文件，需先过一次校验")
            return
        try:
            with open(snap, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.state.setText(f"❌ 快照文件解析失败：{e}")
            self.state.setStyleSheet("color:#f87171;font-size:11px;")
            return
        want = urllib.parse.urlparse(self.host_url).netloc
        if data.get("host") and want and data["host"] != want:
            self.state.setText(f"⚠ 快照是给 {data['host']} 的，与本站 {want} 不符 ——"
                               "请先在内置浏览器里打开本站过一次校验。")
            self.state.setStyleSheet("color:#8fc0ff;font-size:11px;")
            return
        self.state.setText("已从内置浏览器快照读回 cookie，正在注入并复测…")
        self._on_helper_done(data)

    def _focus_builtin_window(self, pid=None):
        """把内置浏览器（pywebview）窗口**拉到前台**。

        v1.40.3（本轮反馈 2「点击没反应」）：真机复现证明窗口建得出来但**被主程序挡住**
        （它是独立顶层窗口、默认不置顶），用户看不到 → 以为点击无效。
        `cf_browser.py` 里已给窗口 `on_top=True`；这里再主动找一次它的窗口并
        `SetForegroundWindow`，双保险（窗口创建有延迟，故由调用方分几次调）。
        """
        try:
            import ctypes
            u = ctypes.windll.user32
            target_pid = pid or (self._proc.pid if self._proc is not None else 0)
            found = []

            WNDENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def _cb(h, _l):
                n = u.GetWindowTextLengthW(h)
                if n <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(h, buf, n + 1)
                if "站点验证" in buf.value and "内置浏览器" in buf.value:
                    found.append(h)
                return True

            u.EnumWindows(WNDENUMPROC(_cb), 0)
            for h in found:
                try:
                    u.ShowWindow(h, 9)          # SW_RESTORE
                    u.SetForegroundWindow(h)
                except Exception:
                    pass
            return bool(found)
        except Exception:
            return False

    def _open_builtin(self):
        ok, msg = self._webview_ready()
        if not ok:
            self.state.setText(f"❌ {msg}　可点「高级 ▾」手动粘贴 cookie。")
            self.state.setStyleSheet("color:#f87171;font-size:11px;")
            self.btn_adv.setChecked(True)
            return
        # 已有子进程在跑就不重复开
        if self._proc is not None and self._proc.poll() is None:
            self.state.setText("内置浏览器已在运行 —— 请在弹出的窗口里完成验证。")
            self.state.setStyleSheet("color:#8fc0ff;font-size:11px;")
            # v1.40.3：窗口可能被主程序挡住 → 顺手把它拉回前台（修「点了没反应」）
            self._focus_builtin_window()
            return
        try:
            import tempfile
            cmd, resfile = self._helper_cmd()
            logp = os.path.join(tempfile.gettempdir(), "lmc_cf_browser.log")
            self._resfile = resfile
            flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                # 子进程自己会开 pywebview 窗口；不要多弹一个控制台黑框。
                flags = subprocess.CREATE_NO_WINDOW
            self._logf = open(logp, "wb")
            self._proc = subprocess.Popen(cmd, stdout=self._logf, stderr=self._logf,
                                          creationflags=flags)
            applog.log(f"[站点验证] 启动内置浏览器子进程 pid={self._proc.pid} "
                       f"url={self.host_url}")
            self.state.setText("已在弹出的窗口里打开站点 —— 完成验证后点窗口右下角的"
                              "「✔ 我已完成验证，读取 Cookie」（或直接关窗）。")
            self.state.setStyleSheet("color:#8fc0ff;font-size:11px;")
            self._timer.start()
            # ★ v1.40.3（本轮反馈 2）：点击后**给即时反馈 + 主动把窗口拉前台**。
            #   子进程要解压 onefile + 起 WebView2，真实窗口出现约需 2~5 秒；
            #   这期间旧代码界面毫无变化 → 用户以为「点了没反应」反复点。
            #   这里：① 按钮先进入「已打开…」禁用态（避免连点重复 spawn）；
            #   ② 分几次（1.5s / 3s / 5s）尝试把内置浏览器窗口拉到前台。
            self.btn_open.setEnabled(False)
            self.btn_open.setText("已打开 · 等待验证…")
            if not hasattr(self, "_open_restore_timer"):
                self._open_restore_timer = QTimer(self)
                self._open_restore_timer.setSingleShot(True)
                self._open_restore_timer.timeout.connect(self._restore_open_btn)
            self._open_restore_timer.start(6000)
            for delay in (1500, 3000, 5000):
                QTimer.singleShot(delay, self._focus_builtin_window)
        except Exception as e:
            applog.log(f"[站点验证] 启动内置浏览器失败：{e}")
            self.state.setText(f"❌ 启动失败：{e}　可点「高级 ▾」手动粘贴。")
            self.state.setStyleSheet("color:#f87171;font-size:11px;")
            self._restore_open_btn()

    def _restore_open_btn(self):
        """把「打开内置浏览器」按钮恢复成可点态（v1.40.3）。"""
        try:
            self.btn_open.setEnabled(True)
            self.btn_open.setText("打开内置浏览器")
        except Exception:
            pass

    def _poll_result(self):
        if not self._resfile or not os.path.exists(self._resfile):
            # 子进程已退出但没写结果 → 大概率是启动就崩了
            if self._proc is not None and self._proc.poll() is not None:
                self._timer.stop()
                self._on_helper_done(None)
            return
        self._timer.stop()
        data = None
        try:
            with open(self._resfile, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            data = {"ok": False, "error": f"结果文件解析失败：{e}"}
        self._on_helper_done(data)

    def _stop_builtin(self):
        """终止内置浏览器子进程（若有）并清空引用。"""
        if self._proc is not None:
            try:
                if self._proc.poll() is None:
                    self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def _on_helper_done(self, data):
        # v1.40.3：内置浏览器已结束 → 「打开内置浏览器」按钮恢复可点态
        self._restore_open_btn()
        try:
            if self._logf:
                self._logf.close()
        except Exception:
            pass
        if not data or not data.get("ok"):
            err = (data or {}).get("error") or "内置浏览器未取到 cookie"
            self._stop_builtin()
            self.state.setText(f"❌ {err}　可再试一次，或点「高级 ▾」手动粘贴。")
            self.state.setStyleSheet("color:#f87171;font-size:11px;")
            return
        pairs = scraper_mod.parse_cookie_header(data.get("cookie", ""))
        if not pairs:
            self._stop_builtin()
            self.state.setText("❌ 取回的 cookie 解析为空，请重试。")
            self.state.setStyleSheet("color:#f87171;font-size:11px;")
            return
        n = scraper_mod.inject_cookies(self.host_url, pairs)
        has_pass = any(k in scraper_mod._PASS_COOKIE_NAMES for k in pairs)
        applog.log(f"[站点验证] 内置浏览器取回 {n} 条 cookie -> {self.host_url}"
                   f"（含通行 cookie: {has_pass}）")
        self._refresh_state()
        if self.on_done:
            self.on_done(n)
        # v1.41.0（方案B）：浏览器抓取开关打开 → 把存活子进程**托管**给浏览器会话单例，
        # 不终止（窗口保留为常驻抓取后端，cookie 罐与会话复用）；关闭开关或取 cookie 失败
        # 时保持原行为：终止子进程。
        if cfg.get_settings().scraper.get("browser_scrape") and self._proc is not None \
                and self._proc.poll() is None:
            browser_session.SESSION.attach(self._proc, self.host_url)
            self._session_owned = True
            self.state.setText(self.state.text()
                               + "　✅ 浏览器会话已就绪（抓取中，请保持验证窗口开启）")
            self.state.setStyleSheet("color:#45d483;font-size:11px;")
            applog.log(f"[站点验证] 浏览器会话已托管 {self.host_url}（pid={self._proc.pid}）")
        else:
            self._stop_builtin()
        self._verify_now()

    def _copy_snippet(self):
        try:
            QApplication.clipboard().setText("document.cookie")
        except Exception:
            pass
        self.state.setText("已把 `document.cookie` 复制到剪贴板 —— "
                           "到浏览器 Console 里粘贴、回车，再把输出整串复制回来。")
        self.state.setStyleSheet("color:#8fc0ff;font-size:11px;")

    def _save_and_verify(self):
        pairs = scraper_mod.parse_cookie_header(self.ed.toPlainText())
        if not pairs:
            self.state.setText("没解析出任何 cookie —— 请确认粘贴的是 `name=value` 形式的内容。")
            self.state.setStyleSheet("color:#f87171;font-size:11px;")
            return
        n = scraper_mod.inject_cookies(self.host_url, pairs)
        has_pass = any(k in scraper_mod._PASS_COOKIE_NAMES for k in pairs)
        self._refresh_state()
        applog.log(f"[站点验证] 注入 {n} 条 cookie -> {self.host_url}"
                   f"（含通行 cookie: {has_pass}）")
        if self.on_done:
            self.on_done(n)
        # 保存完自动跑一次测连，让用户立刻看到是否真的通了（不等他回上一页点「测试」）
        self._verify_now()

    def _verify_now(self):
        """用刚注入的 cookie 复测**当前这个站点**。

        ★ v1.46.6（反馈 4）：原来这一行是「host 里含 minnano 就测 minnano，**否则一律
          当成 imdb**」。于是任何非 minnano 的站点都会被当成 IMDB 去复测 —— 用户对
          avbase.net / javdb / wikipedia / 自定义站点取完 cookie，红字永远是
          「IMDB 用的是 AWS WAF…」，日志里的诊断也一直写着
          「① TCP 连接 **www.imdb.com**:443 成功」，跟他正在操作的站点毫无关系。
          这正是「怎么无论怎么样都显示这个报错」的根因。
        现在：先按 `SOURCE_BASES` 反查 host → 命中就用该源的检索自检；
        没命中（自定义站点）→ 走 `test_source_url()`，直接测用户填的那个网址。
        """
        src = scraper_mod.source_of_url(self.host_url)
        name = (scraper_mod.SOURCE_NAMES.get(src, src) if src
                else urllib.parse.urlparse(self.host_url).netloc)
        self.state.setText(self.state.text() + f"　正在用新 cookie 复测 {name}…")
        if src:
            self._verify = TestSourceWorker(src, "", 12)
        else:
            self._verify = TestSourceWorker(self.host_url, "", 12, as_url=True)
        self._verify.done.connect(self._on_verified)
        self._verify.start()

    def _on_verified(self, key, res):
        ok = bool(res.get("ok"))
        msg = res.get("msg") or ""
        diag = res.get("diag") or {}
        if ok:
            self.state.setText(f"✅ 复测通过：{msg}（{res.get('ms')} ms）")
            self.state.setStyleSheet("color:#45d483;font-size:11px;")
            applog.log(f"[站点验证] 复测通过 -> {self.host_url}（{res.get('ms')} ms）")
            return
        # v1.40.2（反馈 2）：**修掉误导性结论**。老文案不管什么原因都甩一句
        # 「cookie 过期」—— 而探针实测（TCP 通 / TLS 被 RST / 各种指纹都一样）
        # 证明这类失败是**连接在 TLS 握手阶段就被掐断**，HTTP 请求根本没发出去，
        # cookie 压根没机会被发送。再让用户去折腾 cookie 是把他往死路上引。
        #
        # ★ v1.40.4（反馈 2「握手成功了也不太行」）：上一版只分 tls / tcp 两支，
        #   其余一律落到「若持续失败，请查日志」—— 而**最需要说清的那一支**
        #   （TLS 通、正文是挑战页）恰恰落在这里，用户刚过完一次验证就看到
        #   「复测未通过 … 若持续失败请查日志」，自然觉得「握手成功了也不太行」。
        #   现在按 `stage` 四支分开，waf 那支直接说「过完验证也可能仍被挑战」。
        verdict = diag.get("verdict") or ""
        if diag.get("stage") == "tls":
            tail = ("　—— ★ 判因（分层探针）：连接在 **TLS 握手阶段**就被重置，"
                    "**这不是 cookie 的问题**（请求还没发出，cookie 没用上）。"
                    "请换网络 / 换代理，或检查本机防火墙与安全软件是否按进程拦截。")
        elif diag.get("stage") == "tcp":
            tail = "　—— 连 TCP 都连不上，是 DNS / 网络问题，与 cookie 无关。"
        elif diag.get("stage") == "waf":
            tail = ("　—— ★ 判因（分层探针）：**TCP + TLS 都通**，但站点回的正文是"
                    "反爬挑战页（HTTP 200/202 也会是挑战页）。这类挑战要浏览器**执行 JS**"
                    "换放行凭据，手工粘 cookie 一般无效。\n"
                    "　　这里的复测走的是**无头请求**；若已在刮削页打开「用内置浏览器抓取」，"
                    "实际刮削会走 WebView2 会话，本行失败**不代表刮不到**。")
        elif diag.get("stage") == "http":
            tail = ("　—— 链路通、但 HTTP 层被硬拒（应用层拦截），"
                    "可试换代理 / 换出口 IP 后复测。")
        else:
            tail = "　—— 若持续失败，请查运行日志（工具 → 数据 → 日志）确认具体原因。"
        # v1.46.6（反馈 4）：把**复测的站点**写进红字里。原来文案只有「复测未通过」，
        # 而实际测的却是写死的 imdb，用户根本看不出测错了对象。
        _hn = urllib.parse.urlparse(self.host_url).netloc or self.host_url
        self.state.setText(f"❌ 复测未通过（{_hn}）：{msg}（{res.get('ms')} ms）{tail}")
        self.state.setStyleSheet("color:#f87171;font-size:11px;")
        # 把分层诊断结论写进运行日志 —— 用户明确要求「查看运行日志，查明失败原因」
        applog.log(f"[站点验证] 复测未通过 -> {self.host_url}：{msg}（{res.get('ms')} ms）")
        if diag:
            applog.log(f"[站点验证·诊断] stage={diag.get('stage')} "
                       f"waf={diag.get('waf')} body_len={diag.get('body_len')} "
                       f"ok={diag.get('ok')} verdict={verdict}")
            for line in (diag.get("detail") or []):
                applog.log(f"[站点验证·诊断] {line}")

    def _clear(self):
        scraper_mod.clear_cookies(self.host_url)
        self.ed.clear()
        self._refresh_state()

    def closeEvent(self, ev):
        try:
            self._timer.stop()
        except Exception:
            pass
        # v1.41.0（方案B）：若子进程已托管给浏览器会话（常驻抓取后端），关对话框不要杀它；
        # 会话由 browser_session 单例持有，用户关掉验证窗口时才会自然结束。
        if self._session_owned:
            self._proc = None
            return
        try:
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass
        try:
            if getattr(self, "_logf", None):
                self._logf.close()
        except Exception:
            pass
        super().closeEvent(ev)


# ---------- 媒体库编辑 / 新建对话框：名称 / 类型 / 媒体文件夹 ----------

class AutoFillDialog(GlassDialog):
    """「从画像自动填充」的参数面板（v1.34.0 需求 1）。

    需求原文：「从画像自动填充功能中，加入自己选用哪个统计范围的画像。然后标签前多少、
    片商前多少、演员前多少、导演前多少、默认每项给到多少权重，都可以自己选择范围。」

    所以这里把原来**硬编码**的那套（`Portrait().build()` + 固定的
    `(:30, 1.5) / (:10, 1.3) / (:10, 1.2)` 计划）全部变成可调项：

    - **统计范围**：全部媒体库 / 只算「我的收藏」/ 指定某个媒体库（复用 `insight.Portrait`）；
    - **每维度「取前 N」**：1~999，取消勾选 = 不用这个维度；
    - **每维度「权重」**：0~5（跟向量编辑的手动权重同一量纲）；
    - **每维度启用勾选**：一键跳过不想要的维度。

    参数「记住偏好」：确认后落 `config.Settings.autofill`，下次打开还是上次那套。
    """

    DIMS = [("tag", "标签", "收藏影片里出现最多的题材词"),
            ("studio", "片商", "「片商:」开头的厂牌 / 制作商"),
            ("series", "系列", "「系列:」开头的作品系列"),
            ("actor", "演员", "演员库里出现最多的演员"),
            ("director", "导演", "导演库里出现最多的导演")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("从画像自动填充 · 参数")
        self.s = cfg.get_settings()
        self._prefs = json.loads(json.dumps(self.s.autofill or {}))
        self._build()
        # v1.34.1 修复（用户反馈 2「切『我的收藏』时高度不一致 / 与说明块重叠」）：
        # 原来写死 `resize(660, 560)`，但本面板的 sizeHint 会随**内容**变化 ——
        # 切到「我的收藏」时范围提示文字从 1 行变 2 行，sizeHint 从 598 涨到 628，
        # 而窗口还是 560 → 布局被压缩，QGroupBox 被挤到比 sizeHint 矮 30px，
        # 里面的 SpinBox 溢出、和下面的说明块叠在一起。
        # 修法：宽度给一个舒服的定值，**高度按 sizeHint 自适应**（并给上下限兜底），
        # 这样无论哪个范围、什么字体，都不会再被压缩。
        self._fit_height()

    def _fit_height(self):
        """按当前内容的真实高度定高（宽度固定 660，居中）。"""
        w = max(660, self.sizeHint().width())
        h = self.sizeHint().height()
        h = max(h, 420)                       # 下限兜底，太矮会 clipping
        h = min(h, 900)                       # 上限兜底，防止超大字体撑爆屏幕
        self.resize(w, h)


    # ---------- 构建 ----------
    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(10)

        hint = QLabel(rich(
            "按「画像概览」的统计结果，把 **高频项** 批量写成向量权重（写进 "
            "`vector_overrides` 表，立刻对智能推荐生效）。\n"
            "同名条目会被**覆盖**；这里选的参数会记住，下次打开还是这套。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        v.addWidget(hint)

        # ---- 统计范围 ----
        g1 = QGroupBox("统计范围")
        # v1.34.2（用户反馈 1）：组框钉成 Fixed，不被外层布局拉伸去吃白，
        # 内部边距/行距也收紧，避免「统计范围」组框下方留一大块空白。
        g1.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        f1 = QFormLayout(g1)
        f1.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        f1.setContentsMargins(10, 8, 10, 8)
        f1.setVerticalSpacing(6)
        f1.setHorizontalSpacing(10)
        self.cb_scope = QComboBox()
        self.cb_scope.addItem("全部媒体库", "")
        self.cb_scope.addItem("我的收藏（只统计收藏的影片）", "__FAV__")
        try:
            for lib in (self.s.libraries or []):
                nm = str(lib.get("name") or "").strip()
                if nm:
                    self.cb_scope.addItem(f"媒体库：{nm}", nm)
        except Exception:
            pass
        # ⚠️ 恢复时要**先看 favorites_only**：`findData("")` 会命中第 0 项
        # （「全部媒体库」的 data 就是空串），于是「上次选的是我的收藏」永远恢复不回来。
        saved_scope = str(self._prefs.get("scope") or "")
        if self._prefs.get("favorites_only"):
            idx = self.cb_scope.findData("__FAV__")
        else:
            idx = self.cb_scope.findData(saved_scope)
        self.cb_scope.setCurrentIndex(idx if idx >= 0 else 0)
        self.cb_scope.setToolTip(
            "用哪个范围的画像来生成权重。\n"
            "「我的收藏」适合「我就是想找跟已收藏很像的」；\n"
            "某个媒体库适合「这个库我口味不一样」。")
        f1.addRow("统计", self.cb_scope)
        self.lb_scope_tip = QLabel("—")
        self.lb_scope_tip.setStyleSheet("color:#71717a;font-size:11px;")
        # v1.34.2（用户反馈 1）根因修复：wordWrap=True 时 QLabel 的 sizeHint 会按多行
        # 估算高度，QFormLayout 把它拉伸到约 3 行高（实测 v1.34.1 tip 高 60px、v1.34.2 初版
        # 仍 45px，而文本只有 1 行 ~17px）—— 这正是「统计范围组框下方留白太多」的真因。
        # 关闭换行 + 定死 1 行高；三档文案已在 _refresh_est 压成单行，故不会裁字。
        self.lb_scope_tip.setWordWrap(False)
        self.lb_scope_tip.setFixedHeight(
            self.lb_scope_tip.fontMetrics().lineSpacing() + 3)
        f1.addRow("", self.lb_scope_tip)
        v.addWidget(g1)

        # ---- 各维度 前 N + 权重 + 启用 ----
        g2 = QGroupBox("每个维度取多少 · 给多少权重")
        # v1.34.2（用户反馈 1）：同 g1，钉 Fixed 不被拉伸。
        g2.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        gl = QGridLayout(g2)
        gl.setHorizontalSpacing(10)
        gl.setVerticalSpacing(8)
        for c, h in enumerate(("维度", "启用", "取前 N 个", "权重", "说明")):
            lb = QLabel(h)
            lb.setStyleSheet("color:#a1a1aa;font-size:11px;")
            gl.addWidget(lb, 0, c)
        self.dim_rows = {}
        dims_cfg = (self._prefs.get("dims") or {})
        for r, (key, cn, tip) in enumerate(self.DIMS, start=1):
            cur = dict(dims_cfg.get(key) or {})
            dflt = cfg.DEFAULT_AUTOFILL["dims"].get(key) or {"on": True, "top": 10, "w": 1.0}
            ck = QCheckBox()
            ck.setChecked(bool(cur.get("on", dflt["on"])))
            ck.setToolTip(f"不勾选就跳过「{cn}」")
            gl.addWidget(ck, r, 1, Qt.AlignCenter)
            sp_top = QSpinBox()
            sp_top.setRange(*cfg.Settings.AUTOFILL_TOP_RANGE)
            # v1.34.2（用户反馈 2）：去掉「 个」后缀 —— 带后缀时「999 个」比「999」宽，
            # 在 SPIN_MAX_W 限宽下第 3 位会被吞（实测原来只能写 99）。去掉后缀后
            # 三位数字「999」能完整显示，上限 999 才真正填得进去。
            sp_top.setValue(int(cur.get("top", dflt["top"])))
            # v1.34.1 修复：原来是 setFixedWidth(96)，但 QSS 的 padding 5px 10px
            # 加上「200 个」+ 上下箭头后 `minimumSizeHint().width()` 会超过 96，
            # 结果数字被挤到贴边、与上下边框「重叠」。改成给足 + 允许伸展。
            sp_top.setMinimumWidth(cfg.SPIN_MIN_W)
            sp_top.setMaximumWidth(cfg.SPIN_MAX_W)
            sp_top.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            gl.addWidget(sp_top, r, 2)
            sp_w = QDoubleSpinBox()
            sp_w.setRange(*cfg.Settings.AUTOFILL_W_RANGE)
            sp_w.setSingleStep(0.1)
            sp_w.setDecimals(2)
            sp_w.setValue(float(cur.get("w", dflt["w"])))
            sp_w.setMinimumWidth(cfg.SPIN_MIN_W)
            sp_w.setMaximumWidth(cfg.SPIN_MAX_W)
            sp_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            gl.addWidget(sp_w, r, 3)
            gl.addWidget(QLabel(f"{cn} · {tip}"), r, 4)
            # 关掉勾选时把两个输入框置灰（视觉上一眼看出被跳过）
            sp_top.setEnabled(ck.isChecked())
            sp_w.setEnabled(ck.isChecked())
            ck.toggled.connect(sp_top.setEnabled)
            ck.toggled.connect(sp_w.setEnabled)
            self.dim_rows[key] = (ck, sp_top, sp_w)
        gl.setColumnStretch(4, 1)
        v.addWidget(g2)

        note = QLabel(rich(
            "权重含义与「向量编辑」一致：**>1 加强**、1 = 默认、0~1 减弱、**0 = 屏蔽**。\n"
            "自动填充是**覆盖写**，不会替你删掉别的条目 —— 想清干净先点「全部清空」。"))
        note.setWordWrap(True)
        note.setStyleSheet("color:#71717a;font-size:11px;")
        v.addWidget(note)

        self.lb_est = QLabel("—")
        self.lb_est.setStyleSheet("color:#8fc0ff;font-size:11px;")
        self.lb_est.setWordWrap(True)
        v.addWidget(self.lb_est)

        foot = QHBoxLayout()
        b_prev = QPushButton("预览将写入的条目…")
        b_prev.setObjectName("Ghost")
        b_prev.setToolTip("先看要写哪些关键词，不写库")
        b_prev.clicked.connect(lambda: self._run(dry=True))
        b_reset = QPushButton("恢复默认")
        b_reset.setObjectName("Ghost")
        b_reset.clicked.connect(self._reset)
        foot.addWidget(b_prev)
        foot.addWidget(b_reset)
        foot.addStretch(1)
        b_cancel = QPushButton("取消")
        b_cancel.clicked.connect(self.reject)
        self.b_ok = QPushButton("填充")
        self.b_ok.setObjectName("Primary")
        self.b_ok.clicked.connect(lambda: self._run(dry=False))
        foot.addWidget(b_cancel)
        foot.addWidget(self.b_ok)
        v.addLayout(foot)

        self.cb_scope.currentIndexChanged.connect(self._refresh_est)
        for key, _cn, _t in self.DIMS:
            ck, sp_top, sp_w = self.dim_rows[key]
            ck.toggled.connect(self._refresh_est)
            sp_top.valueChanged.connect(self._refresh_est)
            sp_w.valueChanged.connect(self._refresh_est)
        QTimer.singleShot(0, self._refresh_est)

    # ---------- 状态 ----------
    def _scope(self):
        """当前统计范围 → (library, favorites_only, 人话)。"""
        data = self.cb_scope.currentData()
        if data == "__FAV__":
            return "", True, "我的收藏"
        return str(data or ""), False, str(self.cb_scope.currentText() or "全部媒体库")

    def _plan(self):
        """当前参数 → [(dim, top, weight), ...]（只含启用且 top>0 的维度）。"""
        out = []
        for key, cn, _t in self.DIMS:
            ck, sp_top, sp_w = self.dim_rows[key]
            if not ck.isChecked():
                continue
            top = int(sp_top.value())
            if top <= 0:
                continue
            out.append((key, cn, top, float(sp_w.value())))
        return out

    def _refresh_est(self, *_):
        lib, fav, cn = self._scope()
        plan = self._plan()
        n = sum(t for _k, _c, t, _w in plan)
        bits = "、".join(f"{c}前 {t}（权重 {w:g}）" for _k, c, t, w in plan)
        # ⚠️ 先设格式再设文本：`setTextFormat` 只影响**之后**的 setText。
        # 反过来的话（先 setText 再设 RichText）Qt 会按上一次的格式重新解析，
        # 文案里的 `<` / `&` 会被当成标签吃掉。
        for w in (self.lb_est, self.lb_scope_tip):
            w.setTextFormat(Qt.RichText)
        self.lb_est.setText(
            f"将统计「{cn}」的画像，预计最多写入 <b>{n}</b> 条：{bits or '（没有启用任何维度）'}")
        self.b_ok.setEnabled(bool(plan))
        # v1.34.2（用户反馈 1）：三档文案压成单行（lb_scope_tip 已锁 1 行高），
        # 高度恒定、不再随范围切换上下跳。
        if fav:
            self.lb_scope_tip.setText(
                "只统计已收藏的影片 —— 生成的权重要跟收藏口径一致时选这个（收藏少则更聚焦你的口味）。")
        elif lib:
            _ln = lib if len(lib) <= 12 else lib[:11] + "…"
            self.lb_scope_tip.setText(
                f"只统计媒体库「{_ln}」里的作品（适合这个库口味不一样时，权重不串库）。")
        else:
            self.lb_scope_tip.setText(
                "统计索引里的全部作品（范围最广，适合按整体口味找片）。")
        # v1.34.1：文案长度变了 → 允许的**最小高度**也会跟着变，立刻重新适配，
        # 否则切到「我的收藏」（提示多占一行）时窗口高度不够、内容被压到重叠。
        # 用 QTimer.singleShot(0, ...) 是因为此刻布局还没把新文案算完，
        # 直接量 sizeHint 会拿到旧值。
        QTimer.singleShot(0, self._fit_height)

    def _reset(self):
        d = cfg.DEFAULT_AUTOFILL
        self.cb_scope.setCurrentIndex(0)
        for key, _cn, _t in self.DIMS:
            ck, sp_top, sp_w = self.dim_rows[key]
            base = d["dims"].get(key) or {"on": True, "top": 10, "w": 1.0}
            ck.setChecked(bool(base["on"]))
            sp_top.setValue(int(base["top"]))
            sp_w.setValue(float(base["w"]))
        self._refresh_est()

    # ---------- 执行 ----------
    def _run(self, dry=False):
        lib, fav, cn = self._scope()
        plan = self._plan()
        if not plan:
            QMessageBox.information(self, "提示", "至少要启用一个维度。")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            data = insight_mod.Portrait(library=lib or None,
                                        favorites_only=fav).build()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            applog.log(f"[向量编辑] 自动填充取画像失败：{type(e).__name__}: {e}", "error")
            QMessageBox.warning(self, "失败", f"取画像失败：{type(e).__name__}: {e}")
            return
        finally:
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

        # 维度名 → Portrait 里的键
        src_key = {"tag": "tags", "studio": "studios", "series": "series",
                   "actor": "actors", "director": "directors"}
        picked = []
        for dim, dim_cn, top, w in plan:
            items = data.get(src_key.get(dim, dim + "s")) or []
            for key, _c in items[:top]:
                k = str(key or "").strip()
                if not k:
                    continue
                picked.append((dim, dim_cn, k, w))

        if dry:
            self._show_preview(cn, picked)
            return

        n = 0
        for dim, _dim_cn, key, w in picked:
            db.set_vector_override(dim, key, w)
            self.s.set_vector_weight(dim, key, w)
            n += 1
        # 记住这套参数
        self.s.set_autofill(
            scope=("" if fav else lib),
            favorites_only=fav,
            dims={k: {"on": self.dim_rows[k][0].isChecked(),
                      "top": int(self.dim_rows[k][1].value()),
                      "w": float(self.dim_rows[k][2].value())}
                  for k, _c, _t in self.DIMS})
        applog.log(f"[向量编辑] 自动填充 {n} 条（范围={cn}）")
        self.accept()

    def _show_preview(self, scope_cn, picked):
        head = f"统计范围「{scope_cn}」，共 {len(picked)} 条：\n\n"
        by = {}
        for dim, dim_cn, key, w in picked:
            by.setdefault(dim_cn, []).append(f"{key}({w:g})")
        body = "\n\n".join(f"【{d}】{len(v)} 条：{'、'.join(v[:24])}"
                           + ("…" if len(v) > 24 else "") for d, v in by.items())
        dlg = QDialog(self)
        dlg.setWindowTitle("预览（不会写入）")
        dlg.resize(620, 460)
        v = QVBoxLayout(dlg)
        lb = QLabel(head + body)
        lb.setWordWrap(True)
        ta = QPlainTextEdit(head + body)
        ta.setReadOnly(True)
        v.addWidget(ta, 1)
        row = QHBoxLayout(); row.addStretch(1)
        b = QPushButton("关闭"); b.clicked.connect(dlg.accept)
        row.addWidget(b); v.addLayout(row)
        dlg.exec()


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
    # ★ v1.40.7（本轮）：**固定默认尺寸 1320×960**，切页不再让窗口长高/收矮。
    # 用户反馈原文：「界面默认大小改为 1320x960px，不随着工具内的内容进行调整，
    #   内部模块不随着界面调整，直接冻结。」
    # 经澄清：「打开默认 1320x960（撤销自适应）但可以手动再调整宽度和高度」+
    #          「窗口可拖，但内容不跟着拉伸」。
    #
    # v1.40.6 的「按页自适应高度」（切到矮页自动收矮、切到高页自动长高）副作用太多：
    # 窗口在用户切页时**自己跳高度**，观感上是「界面在跟着内容变」；且不同页的高度
    # 折算依赖 `stack.height()`（还受 chrome 影响），实测换算容易偏。
    # ⇒ 本版直接**取消自动收放**：打开即 1320×960，之后只有用户自己能改尺寸。
    #
    # 保留 MIN_H：仅作为**拖拽下限**（避免被拖到极窄导致导航文字挤没），
    # 不再参与「自动收矮」。MAX_H 保留给下面的 `_fit_page`（兜底值，正常不生效）。
    MIN_H = 560
    MAX_H = 960
    #: v1.40.7：打开时的默认逻辑尺寸 1320×960（用户指定）。
    DEF_W = 1320
    DEF_H = 960
    #: v1.40.7（Task #236）：左侧导航固定宽（`_build()` 里 `nav_frame.setFixedWidth(150)`）。
    NAV_W = 150
    #: v1.40.7（Task #236）：页面内容**固定绘制宽度** = 默认窗口宽 - 导航宽。
    # 窗口拉宽时画布仍按这个宽度绘制并居中（两侧留白），组框尺寸纹丝不动。
    # ⚠ 必须扣掉 NAV_W：`QDialog` 的有效最小宽 = `max(显式最小宽, 布局最小宽)`，
    #   若页宽取 1320，加上 150 的导航布局最小宽就被顶到 1470（探针实测），
    #   `resize(1320)` 会被 Qt 静默忽略 → 窗口比要求的宽。
    CONTENT_W = DEF_W - NAV_W       # = 1170

    def __init__(self, parent=None, on_changed=None):
        super().__init__(parent)
        # v1.24.0（反馈 5）：入口与标题由「设置」改为「工具」
        self.setWindowTitle("工具")
        # ★ v1.40.7（本轮）：默认尺寸固定 1320×960 —— 不再跟屏幕宽度缩到 1000，
        #   也不再看屏幕可用高。仅在屏幕确实装不下时才收敛（小屏兜底）。
        sw = self.screen()
        avail = sw.availableGeometry() if sw is not None else None
        if avail is not None:
            w = min(self.DEF_W, max(760, avail.width() - 40))
            h = min(self.DEF_H, max(self.MIN_H, avail.height() - 40))
        else:
            w, h = self.DEF_W, self.DEF_H
        # v1.40.7：`setMinimumHeight(MIN_H)` 保留 —— 用户要「可以手动再调整宽度和
        # 高度」，所以**不能** `setFixedSize`，只需给一个拖拽下限。
        # ⚠ 注意：`QDialog` 的有效最小高 = `max(显式最小高, 布局最小高)`。
        #   v1.40.6 真机踩过「高内容页（个性化设置 1413px）把窗口顶到 1408px」——
        #   修法是那些页**保持 QScrollArea 形态**吸收大最小高（见 `_build()` 里
        #   `_page_scroll` 的用法），而不是去调 `setMinimumHeight`。
        self.setMinimumHeight(self.MIN_H)
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
        self._manual_page = ui_manualedit.ManualEditPage()
        # v1.40.8：手动修改右栏换片后内容高会变（nfo 字段多的影片能到 1400+），
        # 画布最小高必须跟着重算，否则新内容被切 / 底部一片死黑（用户截图 1）。
        self._manual_page.contentChanged.connect(
            lambda: self._refresh_frozen_height(self._manual_page))
        self._pg_manual = self._page_scroll(self._manual_page)
        self._pg_insight = self._page_scroll(self._build_insight())
        # v1.43.0（需求 4）：数据源从 3 个加到 6 个（wikipedia / theporndb / javdb），
        # 再加「头像独立源 gfriends」与「ThePornDB Key」两行 —— 内容已高过 960 视口。
        # ⚠ v1.43.1（反馈 1「行高变大」）：上一版误改成 `_page_scroll`（= lock_height=False），
        #   画布 `setWidgetResizable(True)` 会让**组框自己吸掉多余高度**（顶部「演员刮削」
        #   组框被撑到 ~90px）。`_freeze(..., lock_height=True)` 本身就是「画布高=内容高 +
        #   可滚」（`setWidgetResizable(False)`），内容超视口时照样出滚动条 —— 正是想要的。
        self._pg_scraper = self._freeze(self._build_scraper(), lock_height=True)
        self._pg_smart = self._page_scroll(self._build_smart())     # v1.24.0：智能推荐
        self._pg_tagopt = self._page_scroll(self._build_tagopt())   # v1.25.0：标签优化
        self._pg_service = self._page_scroll(self._build_service())
        self._pg_aiengine = self._page_scroll(self._build_aiengine())  # v1.35.0：AI 引擎设置
        self._pg_dedupe = self._page_scroll(self._build_dedupe())   # v1.23.0：重复检测
        # v1.31.0（反馈 3）：演员检测自带上下两块 + 内外滚动，**不再套 _page_scroll**
        # （外面再包一层滚动区会让两个分隔条的高度互相打架）。
        # v1.40.7（Task #236）：但**宽度仍要冻结** —— 改用 `_freeze()`（只钉固定宽、
        # 不再包一层滚动区），既不打架又让窗口拉宽时内容纹丝不动。
        self._pg_actorcheck = self._freeze(ui_actorcheck.ActorCheckPage(), scroll=False)
        self._pg_imagedetect = self._page_scroll(ui_imagedetect.ImageDetectPage())
        # v1.44.0（需求 4）：「数据与日志」拆成「数据管理」+「日志中心」两页
        self._pg_data = self._page_scroll(self._build_data())
        self._pg_logs = self._page_scroll(self._build_logs())
        for pg in (self._pg_personal, self._pg_manual, self._pg_insight, self._pg_scraper,
                   self._pg_smart, self._pg_tagopt, self._pg_service, self._pg_aiengine,
                   self._pg_dedupe,
                   self._pg_actorcheck, self._pg_imagedetect, self._pg_data,
                   self._pg_logs):
            self.stack.addWidget(pg)
        root.addWidget(self.stack, 1)

        # v1.39.0（需求 3）：左侧导航「进行中」转圈的轮询定时器。集中轮询而不在各
        # worker 启动点插桩 —— 页面重建/销毁都不影响这里的判定（全部 getattr 兜底）。
        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(400)
        self._busy_timer.timeout.connect(self._refresh_nav_rings)

        # v1.40.0（反馈 1）：挂一个「内容比可视区矮就别让它被压」的守卫。
        #
        # 这条守卫针对的是**真根因**（而不是症状）：设置窗是**不套滚动区**的写死高度，
        # 一旦某页内容超过可视高度，Qt 不会滚动，而是**把控件往下压** —— 被压的总是
        # 排在最后那个 QLabel（QGroupBox 的高度由布局分配，标签可被压到只剩描边）。
        # 用户截图 1 那条「空白带」就是这么来的：`src_hint` 的 sizeHint 是 60px
        # （文案折成 4 行），实际只被分到 15px —— 文字整段看不见，只剩一条细边。
        #
        # 修法不靠「猜一个够大的窗口」：`_fit_page()` 量当前页的 sizeHint，
        # 需要时把**窗口**长高（上限屏幕可用高度），长不动了才让页面自己滚动。
        self._install_fit_guard()
        self._show("个性化设置")

    @staticmethod
    def _pin_min_height(box, lay):
        """把 `box` 的最小高钉成「它内容真正需要的高度」。
        v1.40.0（反馈 1）。取 **layout 里逐子项 sizeHint 之和**，而不是
        `lay.sizeHint().height()` —— 后者有个致命陷阱：布局一旦被压缩过，
        `sizeHint()` 返回的就**已经是缩水值**（探针实测：同一个组框，空间够时
        报 262，被压过之后报 247）。照它钉等于把「被压扁的状态」固化下来，
        白钉一场。逐子项累加绕开了这个陷阱：每个子控件自己的 `sizeHint()`
        不受父布局压缩影响（实测 QListWidget 恒报 192，哪怕实际只分到 120）。

        必须**等布局激活后**才取值（`QTimer.singleShot(0, ...)`）—— 构造途中
        `sizeHint()` 是未布局的估算值，照它钉会在真机上重新压扁内容。
        另取 `lay.minimumSize()` 兜底，保证「一个字都别裁」。

        v1.40.1（反馈 1 回修）：探针实测出**「逐子项累加」自己也会虚高** ——
        上面的注释里那句「QListWidget 恒报 192，哪怕实际只分到 120」正是
        病根被写成了论据：`src_list` 在真源里是 `setFixedHeight(120)`，但
        `sizeHint()` 仍返回 QListWidget 的通用默认 192；`src_hint` 折行标签
        按当前宽只需 15~30，却因 `sizeHint()` 报 60 而被算成 60。两者相加
        把组框钉到 280，而真实内容只需 ~208 → **底部凭空多出 70px 空白**
        （用户截图 1）。修法两步：
          ① `need` 一律用 `min(need, maximumHeight())` 夹一次 —— `setFixedHeight`
             出的控件 min==max，这一夹就把 `sizeHint()` 的 `192` 拉回真实 `120`；
          ② 折行子项只要 `heightForWidth(当前宽)` 拿得到正数，就**不再**回退
             `sizeHint()`（那正是「宽度未知」的保守估算，与真实宽无关）。
        """
        try:
            needs = []
            for i in range(lay.count()):
                it = lay.itemAt(i)
                w = it.widget()
                if w is None:
                    continue          # 弹簧 / 间隔项不占内容高
                # ★ 折行 QLabel 特殊处理：它的 `sizeHint().height()` 是「宽度未知」
                # 的保守估算（本例 60 = 4 行），而按真实宽算只要 15（1 行）。
                # 用它会把组框钉得虚高、平白多出一大段空白。改用 `heightForWidth`
                # 按当前宽算真实需求 —— 这正是「不裁字」与「不虚高」的平衡点。
                need = 0
                try:
                    if w.hasHeightForWidth() and w.width() > 0:
                        need = w.heightForWidth(w.width())
                except Exception:
                    need = 0
                if need <= 0:
                    need = w.sizeHint().height()
                need = max(need, w.minimumSizeHint().height())
                # ★ 固定高控件（`setFixedHeight` / `setMaximumHeight`）不该按
                # `sizeHint()` 算：它的通用默认值（QListWidget 的 192）与实际
                # 占据高度（120）无关。夹一次 maximumHeight 即可归真。
                try:
                    cap = w.maximumHeight()
                    if 0 < cap < need:
                        need = cap
                except Exception:
                    pass
                needs.append(need)
            if not needs:
                return
            # ⚠ v1.43.1（反馈 1 真因）：本函数原本只服务**竖向**布局。
            #   顶部「演员刮削」组是 **QHBoxLayout**（一行：说明 + 开关 + 统计 +
            #   两个按钮），按「子项高度相加 + 每段 8px 间距」算出来是
            #   17+15+33+33+4×8 = 133，而真实只需一行 67px →
            #   组框被钉到 133、用户看到的就是「行高变大」。
            #   ⇒ 横向布局取**最高子项**，且间距不占高度。
            try:
                from PySide6.QtWidgets import QBoxLayout
                _dir = lay.direction()
                _horizontal = _dir in (QBoxLayout.Direction.LeftToRight,
                                       QBoxLayout.Direction.RightToLeft)
            except Exception:
                _horizontal = False
            if _horizontal:
                total = max(needs)
            else:
                total = sum(needs)
                if len(needs) > 1:
                    total += (len(needs) - 1) * max(0, lay.spacing())
            m = lay.contentsMargins()
            total += m.top() + m.bottom()
            h = max(total, lay.minimumSize().height())
            if h > box.minimumHeight():
                box.setMinimumHeight(h)
        except Exception:
            pass

    @staticmethod
    def _pin_label_height(lb):
        """给折行 QLabel 按「它真正需要的高度」钉死 minimumHeight。

        v1.40.0（反馈 1）。折行 QLabel 是**唯一** `hasHeightForWidth()` 的子项，
        因此在空间不足时永远是第一个被 Qt 压缩的对象 —— 而它的 `minimumSizeHint()`
        默认只报「一行」，所以能被压到一行高、文字整段消失（用户截图里那条空白带）。
        把 minimumHeight 钉成 `heightForWidth(当前宽)` 之后，任何布局都压不动它。

        必须等布局跑完（`singleShot(0)`）才能拿到真实宽度 —— 宽度不同，折行数不同，
        所需高度也就不同。宽度变化时用 `resizeEvent` 再钉一次（见 `_HintLabel` 的用法：
        这里直接在 resize 后重算，无需子类化）。
        """
        try:
            w = lb.width()
            if w <= 0:
                w = lb.sizeHint().width()
            need = lb.heightForWidth(w)
            if need <= 0:
                need = lb.sizeHint().height()
            if need > lb.minimumHeight():
                lb.setMinimumHeight(need)
        except Exception:
            pass

    def _install_fit_guard(self):
        """★ v1.40.7：**已停用**。

        v1.40.0 建立它是为了让 `_fit_page` 可重入安全（`_make_scrollable()` 会动
        `QStackedWidget` 的索引 → 触发 `currentChanged` → 又回调进 `_fit_page`）。
        本版 `_fit_page` / `_make_scrollable` 都已停用，不再有重入路径。
        保留空壳仅为兼容旧调用点（`_build()` 里仍会调一次）。
        """
        self._in_fit = False

    def _fit_page(self, *_):
        """★ v1.40.7（本轮）：**整体停用** —— 切页不再收放窗口高度。

        用户反馈：「界面默认大小改为 1320x960px，**不随着工具内的内容进行调整**」。
        v1.40.6 的「按页自适应」（切到矮页 `_compact_to()` 收矮、切到高页
        `_grow_to()` 长高）正是在「跟着内容调整」，与本轮要求直接冲突。

        保留函数体（而不是删掉）的理由：`stack.currentChanged` 已经连到它、
        `_show()` 里也有 `QTimer.singleShot(0, self._fit_page)`，删掉会得
        `AttributeError`；留一个早退的空壳风险最低。

        仍然*要做*的一件事：**保证高内容页保持滚动区形态**（不要被 `_wrap_*`
        解开成裸页）。原因见 v1.40.6 真机踩到的坑 —— `QDialog` 的有效最小高 =
        `max(setMinimumHeight(MIN_H), 布局最小高)`，裸页会把窗口顶穿到 1408px。
        本版所有页在 `_build()` 阶段就已经是「画布 + 滚动区」形态（`_freeze()`），
        不再有人解包，所以这里只是**兜底**：万一有人把页面换成了裸高页，
        给它补一层滚动。
        """
        return

    def _unwrap_page(self, sc):
        """★ v1.40.7：**已停用**。

        v1.40.6 的「解包」是把 `_freeze()` 出来的「画布 + 滚动区」还原成裸页，
        好让窗口能收矮。本版取消自适应后**没有任何理由再解包** ——
        解包反而会破坏「内容固定宽」的画布结构。保留空壳仅为兼容旧调用点。
        """
        return None

    def _compact_to(self, need_content_h):
        """★ v1.40.7：**已停用**（切页不再收矮窗口）。

        保留空壳仅为兼容可能的旧调用点；`_fit_page()` 已直接 `return`，
        正常路径上不会再走到这里。
        """
        return

    def _grow_to(self, need_content_h):
        """★ v1.40.7：**已停用**（切页不再长高窗口）。同 `_compact_to()`。"""
        return

    @staticmethod
    def _content_height(pg):
        """粗估页面「不被压缩时」需要的总高：外层竖向布局里各子项 sizeHint 之和 + 间距。

        为什么不用 `pg.sizeHint()`：Qt 的布局在空间不足时会**直接返回缩水后的值**，
        用它当判据必然自证「装得下」（v1.40.0 探针踩到的坑）。这里改成逐子项累加，
        并取 `layout().sizeHint()` 与手工累加中的较大值兜底。
        """
        lay = pg.layout()
        if lay is None:
            return pg.sizeHint().height()
        total = 0
        for i in range(lay.count()):
            it = lay.itemAt(i)
            w = it.widget()
            if w is not None:
                total += w.sizeHint().height()
            else:
                total += it.sizeHint().height()
        total += max(0, lay.count() - 1) * max(0, lay.spacing())
        m = lay.contentsMargins()
        total += m.top() + m.bottom()
        return max(total, lay.sizeHint().height())

    def _make_scrollable(self, pg):
        """★ v1.40.7：**已停用**。

        旧语义是「把裸页包进 QScrollArea 以吸收大最小高」（v1.40.0/v1.40.6 用）。
        本版所有页在 `_build()` 阶段就经 `_freeze()` 定型，**不需要**运行时再包；
        且现在包出来的是裸滚动区（没有固定宽画布），会破坏「内容冻结」。
        保留空壳仅为兼容旧调用点。
        """
        return

    def showEvent(self, e):
        super().showEvent(e)
        # 让设置窗口也享受磨砂玻璃
        import backdrop
        self._backdrop = backdrop.auto_apply(self)
        # v1.18.0 反馈 98：打开即开始刷新「实时运行状态」
        if getattr(self, "_rt_timer", None) is not None:
            self._rt_timer.start()
        # v1.39.0（需求 3）：打开即开始轮询「进行中任务」，驱动左侧导航转圈
        if getattr(self, "_busy_timer", None) is not None:
            self._busy_timer.start()

    def resizeEvent(self, e):
        """★ v1.40.7：窗口尺寸**完全交给用户**，这里不再做任何自动调整。

        v1.40.6 曾在这里区分「用户拖动 vs 程序 resize」（靠 `_auto_h` /
        `_program_resize` / `_user_resized_h` 三个状态）以支持「按页自适应」——
        本版取消了自适应，那套状态机也就没有存在意义，全部移除。
        保留覆写只为**将来**在此挂钩（例如记住用户改过的尺寸）留个位置。
        """
        super().resizeEvent(e)

    def _freeze(self, widget, scroll=True, lock_height=False):
        """把一页「冻结」成**固定宽度**画布（v1.40.7，Task #236；v1.40.8 修正高度）。

        `lock_height=True`（v1.40.9，反馈「演员刮削各子模块锁定高度」）：画布**不随
        视口拉伸** —— 钉死成「内容真实需要的高度」，窗口再高也不给页面多余高度，于是
        页内 `Expanding` 子控件（数据源的 QListWidget / 执行的日志框）再也吸不到余量、
        子模块高度恒定。仅内容**矮于视口**的页需要（演员刮削内容 ~807 < 视口 ~950）；
        内容**高于视口**的页（个性化设置 / 画像概览等）画布本就取内容高、永不收到多余
        高度，用不到这个开关，保持默认 `False` 走可滚逻辑。

        用户要求「窗口可拖，但**内容不跟着拉伸**」：窗口一拉宽，组框不该跟着摊宽、
        文字行不该变长。这条是**宽度**诉求。

        ⚠ v1.40.7 误把「宽度冻结」实现成了「宽 + 高都钉死」，用
        `page.setFixedHeight(page.sizeHint().height())`。两个致命后果（真机截图确认）：

          ① `sizeHint()` 是**构造途中**（未布局）的估算值，普遍偏小。实测
             手动修改页 356、画像概览 792，而真实内容分别需要 ~1400 / ~1200。
          ② 「整页自带滚动区」的页面（手动修改 = 左右分裂 + 右栏自己的
             `_NoHScroll`；画像概览 = 雷达/概览/高频榜/分布/共现）被钉死在一个
             比视口还矮的高度后，**页面内部的滚动区拿不到该有的高度** ——
             内容在固定高度处被**硬切**，底部留一大片死黑，页内滚动条也因
             高度不足而形同虚设。

        ⇒ v1.40.8 修正：**只钉宽度，高度交给画布/视口**。结构::

            [QScrollArea]视口可任意拉伸
              └─ [QWidget canvas]宽固定 CONTENT_W（左对齐），**高度=视口高**
                   └─ 真页面 widget（宽度 CONTENT_W，高度随画布）

        效果：
          · 拉宽窗口 → 画布仍 CONTENT_W、右侧纯留白，**组框宽度一字不变**；
          · 拉高窗口 → 画布跟着长高，页面拿到完整可视高 —— 内部自带滚动区的页
            （手动修改 / 画像概览）滚动条正常工作，内容**不再被硬切**；
          · 窗口本身不会因为页面内容变高而变高（画布高 = 视口高，不取内容高）。

        「内部模块尺寸不随窗口重排」这条仍然成立：**宽度**被钉死，组框的宽度、
        列数、文字折行全部不随窗口宽度变化；纵向那些 `Expanding` 控件（日志框/
        列表/树）会跟着视口高变化，但这是**页内滚动**的正常语义，不是重排。

        `scroll=False`（演员检测页）只做「固定宽」，**不额外套** `QScrollArea` ——
        该页自带内外两块滚动，再包一层会让两个分隔条的高度互相打架（v1.31.0 的坑）。
        """
        page = widget
        # ★ 只钉**宽度**。不再 `setFixedHeight`（见上面 v1.40.8 说明）。
        #   同时清掉可能存在的固定高（`setFixedHeight` 会把 min==max 一起设死），
        #   否则页面回到画布里仍是硬切状态。
        try:
            page.setMinimumHeight(0)
            page.setMaximumHeight(16777215)
        except Exception:
            pass
        page.setFixedWidth(self.CONTENT_W)
        if not scroll:
            return page
        canvas = QWidget()
        canvas.setObjectName("LmcFreezeCanvas")   # v1.40.8：供 `_refresh_frozen_height` 反查
        # ★ 水平方向**左对齐**：用户截图里内容紧贴左侧导航，拉宽窗口时也应当是
        #   「左边不动、右边留白」。
        # ⚠ v1.40.8 踩坑：**不能**用 `addWidget(page, 1, Qt.AlignLeft)` —— Qt 里给
        #   布局项传对齐旗标会让该项在**两个方向**都退化成 `sizeHint` 尺寸（对齐
        #   旗标与「拉伸填充」互斥）。实测页面高只剩 478（= sizeHint 一档），
        #   而不是铺满视口高 → 页内滚动区拿不到高度，内容又回到硬切状态。
        #   正解：**不带对齐旗标**地 `addWidget(page, 1)`（纵向填满画布高），
        #   横向靠「页面自身 `setFixedWidth` + 末尾一份零宽弹簧」自然左对齐 ——
        #   页面宽度被钉死，多余的横向空间全部落到弹簧上，视觉上就是「左边不动」。
        cv = QHBoxLayout(canvas)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(page, 1)                 # 无对齐旗标 → 纵向填满画布高
        cv.addStretch(0)                      # 横向多余空间全给弹簧 → 页面靠左
        # ★ v1.40.8：画布的**最小高** = 页面内容真正需要的高度（布局激活后测）。
        #   `setWidgetResizable(True)` 下画布高 = `max(视口高, minimumSizeHint高)`：
        #     · 内容矮于视口（手动修改选片前 354）→ 画布取视口高，页面铺满、无滚动条；
        #     · 内容高于视口（个性化设置 1384 / 画像概览 ~1200）→ 画布取内容高，
        #       外侧滚动区出现滚动条，页面拿到完整高度、内容**不被压扁也不被硬切**。
        #   ⚠ 必须在**布局激活后**取值 —— 构造途中 `sizeHint()` 是估算值（实测手动
        #   修改报 354、画像概览报 792，真值远不止）。而且**一轮 `singleShot(0)`
        #   还不够**：画像概览分析完成后文本从「—」涨成 8 行、AI 引擎设置的表单
        #   还在等子控件自己的 `_pin_min_height` —— 都要过几轮事件循环才稳定。
        #   所以这里用「重试到稳定」的写法（见 `_defer_canvas_height`）。
        canvas.setMinimumHeight(0)           # 先给 0，避免构造途中报出虚高值卡住窗口
        self._defer_canvas_height(canvas, page, lock=lock_height)
        sc = QScrollArea()
        # ★ v1.40.9：lock_height 时**关掉** resizable —— 画布高度由下方延迟钉死成
        #   内容高，窗口拉高时画布停在内容高、多余高度落在滚动区视口里（页面脚下留白），
        #   页面与子模块都不再被拉长。非 lock 时保持 True（画布铺满视口 / 内容超高可滚）。
        sc.setWidgetResizable(not lock_height)
        sc.setWidget(canvas)
        # v1.40.10（反馈 5）：冻结页**永不出现底部横向滚轴**。
        # 根因：页面被 `setFixedWidth(CONTENT_W=1170)` 钉死；但内容高过视口（个性化设置
        # ≈1384 > 视口 ≈950）时竖向滚轴出现、吃掉 ~10px → 视口宽变成 1160 < 页面 1170
        # → Qt 判定内容比视口宽，于是补一条底部横向滚轴（用户截图实锤）。
        # 修法：`ScrollBarAlwaysOff` 关掉横向滚轴；页面右侧 18px 页边距足以吸收那 10px，
        # 组框内容不被裁（所有冻结页都是「组框 + 页边距」结构，关横向滚轴零副作用）。
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setProperty("lmc_frozen", True)      # 供冒烟 / 探针识别
        return sc

    def _defer_canvas_height(self, canvas, page, tries=6, grown=False, lock=False):
        """延到布局稳定后，把画布最小高钉成「页面内容真正需要的高度」（v1.40.8）。

        ★ 为什么要「重试」而不是量一次：v1.40.8 冒烟抓到两处**静默偏小** ——
          画像概览 899（真值 1242，分析完成后文本才涨）、AI 引擎设置 468
          （真值 481，表单内子控件自己的 `_pin_min_height` 还没跑完）。
        一轮 `singleShot(0)` 量出来的是「半稳定态」，画布钉矮了 → 内容仍被切。
        修法：**每轮量一次，只要比上轮大就继续排下一轮**，最多 `tries` 轮；
        量到不再增长即收敛（正常 2~3 轮）。

        ★ 还必须是**单调变大**语义：内容变高才更新，变矮不缩（避免抖动）。
          内容真的变矮（换片）走 `_refresh_frozen_height`，那里允许缩小。

        ★ v1.40.9：`lock=True` 时，收敛的那一轮把画布**钉死成固定高**
          （`setFixedHeight(need)`）—— 画布既不再随视口拉伸、也不再被后续重算改小，
          页面与子模块高度彻底恒定（演员刮削用）。非 lock 时只动最小高、保留可滚。
        """
        def _apply():
            try:
                if canvas is None or page is None:
                    return
                need = self._content_need_height(page)
            except RuntimeError:
                return        # C++ 侧已析构（窗口关了 / 页被重建）
            except Exception:
                return
            if need <= 0:
                return
            try:
                if need > canvas.minimumHeight():
                    canvas.setMinimumHeight(need)
                    # 变高了 → 布局还要再走一轮，继续量（最多 tries 轮）
                    if tries > 1:
                        QTimer.singleShot(0, lambda: self._defer_canvas_height(
                            canvas, page, tries - 1, grown=True, lock=lock))
                elif lock:
                    # 已收敛 + 要求锁定 → 钉死固定高（min==max），画布不再随视口变。
                    # 用「页面真实所需的自然高」取大，确保 >= 内容：sizeHint 比
                    # minimumSizeHint 更全，漏掉会把锁高页面底部切掉（与 v1.40.7 同源 bug）。
                    real = need
                    try:
                        real = max(real, page.minimumSizeHint().height(),
                                   page.sizeHint().height())
                    except Exception:
                        pass
                    canvas.setFixedHeight(real)
                elif grown:
                    # 本轮已是最后一轮，或不再增长 → 收敛，不再排
                    pass
                else:
                    # 首轮就与初值持平 → 多半还没稳定，再给一次机会
                    if tries > 1:
                        QTimer.singleShot(0, lambda: self._defer_canvas_height(
                            canvas, page, tries - 1, grown=False, lock=lock))
            except RuntimeError:
                pass
            except Exception:
                pass
        QTimer.singleShot(0, _apply)

    @staticmethod
    def _content_need_height(page):
        """量一个页面「真正需要的高度」（v1.40.8）。

        取 `max(layout 逐子项 sizeHint 累加, layout.minimumSize().height())`，
        再与 `page.minimumSizeHint()` 取大 —— 三条路取最保险的那条。
        `layout.sizeHint()` 单用不行（被压缩过就缩水），`minimumSizeHint` 单用
        也不行（Qt 对很多控件给的默认值偏保守）。
        """
        try:
            lay = page.layout()
        except RuntimeError:
            return 0
        best = 0
        if lay is not None:
            try:
                total = 0
                for i in range(lay.count()):
                    it = lay.itemAt(i)
                    w = it.widget()
                    if w is None:
                        continue
                    h = 0
                    # 折行标签优先按真实宽算（`sizeHint()` 是「宽度未知」的保守估算）
                    try:
                        if w.hasHeightForWidth() and w.width() > 0:
                            h = w.heightForWidth(w.width())
                    except Exception:
                        h = 0
                    if h <= 0:
                        try:
                            h = w.sizeHint().height()
                        except Exception:
                            h = 0
                    try:
                        h = max(h, w.minimumSizeHint().height())
                    except Exception:
                        pass
                    # v1.40.9：还要采纳「被显式钉死的 minimumHeight」（如 _pin_min_height
                    # 钉过的子模块）—— minimumSizeHint() 不一定反映它，漏掉会把画布量矮、
                    # 锁高页面底部被切（与 v1.40.7 同源的低估 bug）。
                    try:
                        mh = w.minimumHeight()
                        if mh > h:
                            h = mh
                    except Exception:
                        pass
                    total += h
                # 纵向 spacing 与上下边距要算进去，否则量出来比真值小
                try:
                    total += lay.spacing() * max(0, lay.count() - 1)
                    m = lay.contentsMargins()
                    total += m.top() + m.bottom()
                except Exception:
                    pass
                best = max(best, total)
            except Exception:
                pass
            try:
                best = max(best, lay.minimumSize().height())
            except Exception:
                pass
        try:
            best = max(best, page.minimumSizeHint().height())
        except Exception:
            pass
        try:
            best = max(best, page.minimumHeight())
        except Exception:
            pass
        return best

    def _refresh_frozen_height(self, page):
        """页面内容重建（换片/换选）后，重算所属画布的最小高（v1.40.8）。

        手动修改换一部影片后右栏内容高会变（有的 nfo 字段多、有的少），画布若
        还按旧值钉着，就会把新内容切掉或留白。这里从页面反查它所在的画布并补量。

        与 `_defer_canvas_height` 的区别：这里**允许缩小**（换一部字段少的影片，
        画布应跟着变矮，否则底部留一大片死黑），所以直接 `setMinimumHeight(need)`；
        并且重跑一遍「重试到稳定」的循环，等新内容的布局落定。
        """
        try:
            canvas = page.parentWidget()
            while canvas is not None and canvas.objectName() != "LmcFreezeCanvas":
                canvas = canvas.parentWidget()
            if canvas is None:
                return
            need = self._content_need_height(page)
            if need <= 0:
                return
            canvas.setMinimumHeight(need)
            # 新内容可能还要几轮才稳定（尤其右栏表单里的折行标签）
            self._defer_canvas_height(canvas, page)
        except RuntimeError:
            pass
        except Exception:
            pass

    def _show_refresh_frozen(self, scroll_or_page):
        """切页后补量画布最小高（v1.40.8）。

        隐藏页的布局是「半稳定态」：折行标签不知道真实宽、自带滚动区的页拿不到
        视口高。切到该页后它的几何才成立，此时量才准。延一轮事件循环再量。
        """
        def _go():
            try:
                pg = scroll_or_page
                if isinstance(pg, QScrollArea):
                    if not pg.property("lmc_frozen"):
                        return
                    cv = pg.widget()
                    if cv is None or cv.layout() is None or cv.layout().count() == 0:
                        return
                    pg = cv.layout().itemAt(0).widget()
                if pg is None:
                    return
                self._refresh_frozen_height(pg)
            except RuntimeError:
                pass
            except Exception:
                pass
        QTimer.singleShot(0, _go)

    def _page_scroll(self, widget):
        """v1.40.7：改为 `_freeze()` 的薄包装（保留旧名字，调用点很多）。"""
        return self._freeze(widget, scroll=True)

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
        ("基础工具", ["个性化设置", "服务管理", "手动修改", "引擎设置"]),
        ("数据优化", ["演员刮削", "智能推荐", "标签优化"]),
        ("智能检测", ["重复检测", "演员检测", "图像检测"]),
        ("数据分析", ["画像概览", "数据管理", "日志中心"]),
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
        self.nav_rings = {}          # v1.39.0（需求 3）：key -> ScanRing（进行中任务转圈）
        # `ORDER` 保持「扁平、按可见顺序」—— dev/ 下的 live_verify 与 render 脚本
        # 都按它遍历页面，分组只是显示层的包装。
        self.ORDER = [k for _g, keys in self.NAV_GROUPS for k in keys]
        for group, keys in self.NAV_GROUPS:
            old.addWidget(self._section(group))
            for key in keys:
                # v1.39.0（需求 3）：按钮右侧挂一枚 ScanRing（运行中任务转圈）。
                # 包一层 row 容器而不是给 QPushButton 加子控件 —— 按钮自己的
                # padding/文字布局不动，ring 隐藏时按钮铺满整行（几何与旧版一致，
                # live_verify 的点击坐标不受影响）。
                row = QWidget()
                rh = QHBoxLayout(row)
                rh.setContentsMargins(0, 0, 6, 0)
                rh.setSpacing(4)
                b = QPushButton(i18n.tr(key))
                b.setObjectName("Nav")
                b.setToolTip("%s · %s" % (i18n.tr(key), key))   # 悬停能看回原名，排查方便
                b.clicked.connect(lambda _c, k=key: self._show(k))
                rh.addWidget(b, 1)
                ring = ScanRing(row, size=14)
                ring.hide()          # 空闲不可见，也不占布局空间
                rh.addWidget(ring)
                old.addWidget(row)
                self.sub_btns[key] = b
                self.nav_rings[key] = ring
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

    # ---------- 左侧导航「进行中」转圈（v1.39.0 需求 3） ----------
    def _running_tasks(self):
        """当前正在跑的任务 → 对应导航页 key 的集合。

        判定全部走 getattr + isRunning()，不持有 worker 引用；worker 随页面
        重建/销毁都不影响这里。跨页任务（演员检测 / 图像检测）问页面要状态
        （各自实现 `is_busy()`）。
        """
        keys = set()
        for attr, key in (
            ("_worker", "服务管理"),            # 媒体库扫描（ScanNamedWorker）
            ("_scrape_worker", "演员刮削"),     # ScrapeWorker
            ("_to_scan_worker", "标签优化"),    # TagOptScanWorker
            ("_to_run_worker", "标签优化"),     # TagOptRunWorker
            ("_to_ai_worker", "标签优化"),      # 标签优化页的 AI 探测
            ("_dd_worker", "重复检测"),         # DedupeWorker
            ("_insight_worker", "画像概览"),    # PortraitWorker
            ("_ai_worker", "引擎设置"),
            ("_ae_probe_worker", "引擎设置"),
            ("_ae_models_worker", "引擎设置"),
            ("_ae_launch_worker", "引擎设置"),
            ("_prefs_worker", "数据管理"),      # v1.46.12：偏好导入 / 导出
        ):
            w = getattr(self, attr, None)
            if w is not None and w.isRunning():
                keys.add(key)
        for t in (getattr(self, "_test_workers", None) or []):   # 数据源测试（TestSourceWorker）
            if t.isRunning():
                keys.add("演员刮削")
                break
        for attr, key in (("_pg_actorcheck", "演员检测"),
                          ("_pg_imagedetect", "图像检测")):
            if self._page_busy(getattr(self, attr, None)):
                keys.add(key)
        return keys

    @staticmethod
    def _page_busy(pg):
        """跨页任务忙碌判定。

        ⚠ 必须容忍页面被 `_page_scroll` 包成 QScrollArea —— 图像检测页就是
        （`self._pg_imagedetect = self._page_scroll(ImageDetectPage())`），
        演员检测页没包。直接 `pg.is_busy()` 会在 QScrollArea 上抛
        AttributeError，400ms 轮询每次都炸在这儿 → 所有转圈都不更新
        （v1.39.0 冒烟当场抓到，见 dev/smoke_v1390.py）。
        """
        from PySide6.QtWidgets import QScrollArea
        if isinstance(pg, QScrollArea):
            pg = pg.widget()
        fn = getattr(pg, "is_busy", None)
        return bool(callable(fn) and fn())

    def _refresh_nav_rings(self):
        """按 _running_tasks() 更新左侧导航按钮旁的转圈（与主页侧栏同款 ScanRing）。"""
        if not getattr(self, "nav_rings", None):
            return
        keys = self._running_tasks()
        for key, ring in self.nav_rings.items():
            ring.set_state(key in keys, 0, "%s 正在进行" % key)

    def _show(self, key):
        self._current_key = key
        for k, b in self.sub_btns.items():
            b.setStyleSheet(
                "background:rgba(255,255,255,0.12);color:#fafafa;" if k == key else "")
        self.stack.setCurrentWidget({
            "个性化设置": self._pg_personal,
            "手动修改": self._pg_manual,
            "画像概览": self._pg_insight,
            "演员刮削": self._pg_scraper,
            "智能推荐": self._pg_smart,
            "标签优化": self._pg_tagopt,
            "服务管理": self._pg_service,
            "引擎设置": self._pg_aiengine,
            "重复检测": self._pg_dedupe,
            "演员检测": self._pg_actorcheck,
            "图像检测": self._pg_imagedetect,
            "数据管理": self._pg_data,
            "日志中心": self._pg_logs,
        }.get(key, self._pg_personal))
        # v1.40.0（反馈 1）：切页后按需长高窗口 / 给该页套滚动。
        # 用 singleShot(0) 而不是直接调 —— 此刻 `setCurrentWidget` 刚换完，
        # 布局还没重新算过，直接量会拿到上一页的几何。
        # v1.40.7：`_fit_page` 已停用（不再收放窗口），这行保留仅为兼容调用点。
        QTimer.singleShot(0, self._fit_page)
        # v1.40.8：切到某页时补量一次画布最小高 —— 隐藏页的布局是「半稳定态」，
        # 有些内容（折行标签 / 自带滚动区的页）只有真正可见时才能量准。
        self._show_refresh_frozen(self.stack.currentWidget())
        # v1.24.0：画像概览第一次打开时自动分析一次（后续手动点「重新分析」）
        if key == "画像概览" and not self._insight_data:
            self._run_insight()

    def open_person_editor(self, person):
        """右键演员/导演头像跳转而来：切到「演员检测」页并直接按 id 载入该人编辑表单（v1.40.12）。

        演员与导演都能编辑 —— `db.get_person` 按 id 取整行，不区分 role_type。
        直接按 id 载入，避免「演员检测」手动编辑列表只收 Actor 导致导演搜不到。
        """
        self.show()
        self.raise_()
        self.activateWindow()
        self._show("演员检测")
        pg = self._pg_actorcheck
        if pg is None:
            return
        name = (person.get("name") or "").strip()
        pid = person.get("id")
        if name:
            try:
                pg.kw.setText(name)
            except Exception:
                pass
        if pid:
            try:
                pg._load_person(int(pid))
            except Exception as e:
                applog.log(f"演员检测：右键跳转载入失败：{e}", "error")
        # 列表刷新（演员可命中；导演不在 actor 列表里，列表为空但表单已按 id 载入，功能不受影响）
        try:
            pg._search_people()
        except Exception:
            pass

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
        self.ap_lang_hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        self.ap_lang_hint.setWordWrap(True)
        g0v.addWidget(self.ap_lang_hint)
        self._refresh_lang_hint()
        self.ap_hint = QLabel("")
        self.ap_hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        self.ap_hint.setWordWrap(True)
        g0v.addWidget(self.ap_hint)
        # 窗口透明度（整窗半透明透出桌面）
        # v2.0.1（反馈 1）：滑块把手是 18×18 正圆，靠 margin:-6px 0 探出 6px 槽外，
        # 控件默认 sizeHint 只有 15px → 圆球上下被切平。这里显式抬高到 24px
        # （18 + 上下各 3px 余量），并给这一行加 4px 上下内边距，避免贴着上一行文字。
        oph = QWidget()
        ophl = QHBoxLayout(oph)
        ophl.setContentsMargins(0, 4, 0, 2)
        ophl.addWidget(QLabel("窗口透明度"))
        self.op_slider = QSlider(Qt.Horizontal)
        self.op_slider.setFixedHeight(24)
        self.op_slider.setRange(30, 100)
        self.op_slider.setValue(int(round(float(self.s.window_opacity) * 100)))
        self.op_slider.valueChanged.connect(self._preview_opacity)
        self.op_slider.sliderReleased.connect(self._commit_opacity)
        ophl.addWidget(self.op_slider, 1)
        self.op_val = QLabel(f"{int(round(float(self.s.window_opacity) * 100))}%")
        self.op_val.setFixedWidth(48)
        # v2.0.2（反馈 6）：百分比读数改**白色**（原写死 #66a9ff —— 换主题色它也不变，
        # 而且低对比度看不清）。走 #PlainValue，字号沿用全局。
        self.op_val.setObjectName("PlainValue")
        ophl.addWidget(self.op_val)
        g0v.addWidget(oph)
        # v2.0.0：色板换成 HeroUI 的语义色（极光蓝 / 天青 / 青碧 / 翡翠 / 琥珀 /
        # 鎏金 / 玫红 / 粉色 / 紫棠 / 藕荷 / 月白 / 石墨，v2.0.1 在玫红后补「粉色」），
        # 色卡也改成**正圆色点 + 选中白环 + 白勾**。
        # 卡片选中的描边 + 外发光、按钮 / chip / 滑块 / 勾选框的强调色，
        # 全部由它派生（QSS 走令牌替换，自绘控件走 main_window.ACCENT_RGB），
        # 所以换一个色，整套界面一起变。
        acrow = QWidget()
        ach = QHBoxLayout(acrow)
        ach.setContentsMargins(0, 2, 0, 0)
        ach.setSpacing(6)
        ach.addWidget(QLabel("高亮色"))
        ach.addSpacing(4)
        self._accent_btns = {}
        for _nm, _hex in cfg.ACCENT_COLORS:
            b = _AccentSwatch(_hex, _nm)   # v2.0.0：正圆色点（选中白环 + 手绘勾）
            b.clicked.connect(lambda _c, h=_hex: self._apply_accent(h))
            ach.addWidget(b)
            self._accent_btns[_hex] = b
        ach.addSpacing(12)
        self.lb_accent = QLabel("—")
        self.lb_accent.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        # v1.46.0（反馈 2）：演员卡是否显示性别符号
        self.sw_gender = ToggleSwitch(
            checked=bool(self.s.appearance.get("show_gender", True)))
        self.sw_gender.toggled.connect(self._apply_card_gender)
        srl.addWidget(self._row("演员卡性别符号（♂/♀）", self.sw_gender))
        side_hint = QLabel("控制侧栏底部这两块的显隐（侧栏各页面共用）；"
                           "关掉「实时状态」后采集线程也不会启动。")
        side_hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
    def _apply_card_gender(self, *_):
        """v1.46.0（反馈 2）：演员卡性别符号开关 → 落盘并通知主窗重建当前页。"""
        self.s.set_appearance(show_gender=self.sw_gender.isChecked())
        if self.on_changed:
            self.on_changed()

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
        """刷新色卡的选中态（v1.43.4 起由 `_AccentSwatch.set_on()` 自绘）。

        历史坑（已不再适用，保留记录）：原先用控件级 QSS + 文字「✓」，
        既要显式 `padding:0` 压制全局 `QPushButton{padding:7px 14px}`，
        又会因为正圆 radius 与缺字形，出现「圆心显示不全」。
        """
        cur = self.s.accent()
        for hexv, b in getattr(self, "_accent_btns", {}).items():
            on = str(hexv).lower() == str(cur).lower()
            if hasattr(b, "set_on"):
                b.set_on(on)
            b.setToolTip(f"{cfg.accent_name(hexv)}  {hexv}"
                         + ("（当前使用）" if on else "  ·  点击切换"))
        lb = getattr(self, "lb_accent", None)
        if lb is not None:
            lb.setText(f"当前：{cfg.accent_name(cur)}  {cur}")

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
            lb.setStyleSheet("color:#a1a1aa;font-size:11px;")
            return
        note = ("界面语言已切到 %s（%s）。导航与常用动作已本地化；"
                "算法说明、免责声明等业务细节仍保留中文原文 —— "
                "本项目界面文案量很大，逐条机器翻译反而会误导。" % (i18n.cn_name(code), code))
        if i18n.is_rtl(code):
            note += "　⚠ 该语言从右往左书写，但本软件版面仍是左起 —— 只译文字、未做镜像。"
        lb.setText(note)
        lb.setStyleSheet("color:#71717a;font-size:11px;")

    # ---------- 演员刮削 ----------
    def _build_scraper(self):
        page = QWidget()
        v = QVBoxLayout(page)
        # v1.40.2（反馈 1/3）：整体收紧留白 —— 用户反馈「行与行间隔太大 / 底部留白太多」。
        # 上下 12→8、组间 10→7，四个组框更紧凑，也把高度省给日志区。
        # v1.42.0（反馈：数据源行太高 + 下方留白）：组间 7→5，进一步收紧模块间空档。
        v.setContentsMargins(16, 8, 16, 8)
        v.setSpacing(5)
        sc = self.s.scraper

        # v1.40.0（反馈 1）：把「总开关」与「资料统计」从数据源组框里**整体抽出来**，
        # 各自成立独立模块。
        #
        # 为什么原来那样不行（用户三张截图）：
        #   ① 统计条夹在「启用演员刮削」行与数据源列表之间，视觉上属于数据源那一段，
        #      而这行讲的其实是**演员库资料的总体状况**，与「数据源」毫无关系；
        #   ② 数据源组框的内容本来就高（开关行 + 统计行 + 2 行列表 + 测试按钮 + 提示），
        #      窗口是**不套滚动区**的写死高度（SettingsDialog.resize 上限 900）——
        #      内容一旦超过可视高度，Qt 就把最后那个 `src_hint` 标签压到只剩描边
        #      （真机实测被压成 5~7px，文字整段看不见，形成截图 1 红框那条「空白带」）。
        # 抽出来之后：数据源组框少两行、统计模块自带标题与边框，两个问题一起消失。

        # 模块一 + 模块二（v1.40.5 反馈 1 —— 用户截图：「左右分布压缩到一行」）
        #
        # v1.40.0 曾把「总开关」与「资料统计」拆成**两个独立组框**；用户本轮截图指出：
        # 两个组框各自只有**一行**内容，各自却被 `QGroupBox` 默认的
        # `contentsMargins=(9,9,9,9)` + 约 20px 标题撑到 78 / 81px（探针实测内容仅需
        # 48 / 51px，各多出 **30px**）—— 两块加起来 159px 的纵向空间，只为了放两行字。
        #
        # ⇒ 正解：**合成一个组框、一行**。左边是「启用演员刮削」的文字 + 开关，
        #   右边是统计串 + 「刷新统计」按钮，用 `addStretch(1)` 在中间弹性分隔。
        #   纵向占用从 159px 降到约 50px，组框内那两处 30px 空白一并消失。
        #
        # ⚠ 属性名 `self.sc_enabled` / `self.sc_stats` 必须保留 ——
        #   `_refresh_scraper_stats()` 与 `dev/_scratch/ui_coords.py` 都按名引用。
        # v1.40.10（反馈 1）：压缩「演员刮削」顶部开关区高度 —— 用户用红框圈出此区，
        # 要求压矮。三项收紧：① 组内上下留白 4→2；② 列间距 12→8；
        # ③ 启用说明标签 **禁止换行**（`setWordWrap(False)`）—— 它在窄窗口会折成两行
        # 把整行顶高（实测是 108px 的主因），锁成单行后行高回到开关本高。
        # `_pin_min_height(ge)` 在下方按「改后的真实 sizeHint」重新钉最小高，
        # 所以上面三项会直接反映到组框最终高度上（不再被旧布局撑高）。
        ge = QGroupBox("演员刮削")
        geh = QHBoxLayout(ge)
        geh.setContentsMargins(9, 2, 9, 2)
        geh.setSpacing(8)
        self.sc_enabled = ToggleSwitch(checked=bool(sc.get("enabled")))
        self.sc_enabled.toggled.connect(lambda c: self.s.set_scraper(enabled=c))
        _en_lab = QLabel("启用演员刮削（补齐演员头像 / 别名 / 生日 / 简介）")
        _en_lab.setWordWrap(False)
        geh.addWidget(_en_lab, 0)
        geh.addWidget(self.sc_enabled, 0)
        geh.addStretch(1)
        self.sc_stats = QLabel("—")
        self.sc_stats.setStyleSheet("color:#a1a1aa;font-size:11px;")
        # v1.39.5（反馈 2）：原为 setWordWrap(True) —— 统计串有 6 段（演员 / 头像 / 生日 /
        # 别名 / 已刮削 / 待修复），窄窗口下会折成 2~3 行，把「刷新统计」按钮顶到中间、
        # 整条看起来像没对齐（用户截图要求「单独成行」）。
        # 改为**不换行 + 左侧弹性**：统计串永远只占一行，超宽时由 QLabel 自己省略。
        self.sc_stats.setWordWrap(False)
        self.sc_stats.setMinimumWidth(0)
        from PySide6.QtWidgets import QSizePolicy as _SP
        self.sc_stats.setSizePolicy(_SP.Ignored, _SP.Preferred)
        geh.addWidget(self.sc_stats, 1)
        refresh = QPushButton("刷新统计")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self._refresh_scraper_stats)
        geh.addWidget(refresh, 0)
        # v1.43.0（需求 3）：演员库清理 —— 放顶部工具行，不额外占竖向空间
        self.sc_clean = QPushButton("演员库清理…")
        self.sc_clean.setObjectName("Ghost")
        self.sc_clean.setToolTip(rich(
            "删除**没有作品关联**的冗余演员 / 导演记录（只清索引，不动头像与媒体文件；"
            "收藏 / 置顶的人不列入）"))
        self.sc_clean.clicked.connect(self._open_people_clean)
        geh.addWidget(self.sc_clean, 0)
        v.addWidget(ge)
        # v1.40.9：把每个子模块的最小高钉成「内容真实需求」—— 与其他工具一致，
        # 即使窗口被拉高、画布锁定后也不让组框被布局压扁（数据源 g0 在下方单独钉）。
        QTimer.singleShot(0, lambda box=ge, lay=geh: self._pin_min_height(box, lay))

        # 模块三：数据源（自上而下依次尝试，命中后补其缺失字段）
        g0 = QGroupBox("演员刮削数据源（自上而下依次尝试，命中后补其缺失字段）")
        g0v = QVBoxLayout(g0)
        # v1.40.5（反馈 2）：组内 spacing 8 → 4，收紧「列表 / 按钮+提示」之间的空档。
        g0v.setSpacing(4)
        self.src_list = QListWidget()
        self.src_list.setSelectionMode(QAbstractItemView.NoSelection)   # 点「测试」不再整行变红
        # v1.43.2（反馈 1）：原来写死 `ScrollBarAlwaysOff` —— 当时列表按行数长高、
        # 永远装得下；v1.43.1 起列表固定只露三行，**必须**给滚轴，否则第 4~6 个
        # 数据源（IMDB / ThePornDB / JavDB）根本滚不到。宽度/配色由 style.qss 的
        # `QScrollBar:vertical` 统一（10px、半透明白 handle、悬停变高亮色）。
        self.src_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.src_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.src_list.setObjectName("SrcSourceList")   # v1.43.2：滚轴单独加粗（见 style.qss）
        self.src_list.setSpacing(2)
        g0v.addWidget(self.src_list)
        self._rebuild_source_list()
        srcbtns = QWidget()
        sbh = QHBoxLayout(srcbtns)
        sbh.setContentsMargins(0, 0, 0, 0)
        sbh.setSpacing(8)
        test_all = QPushButton("测试全部数据源")
        test_all.setObjectName("Ghost")
        test_all.clicked.connect(self._test_all_sources)
        sbh.addWidget(test_all)
        # v1.44.1（需求 3）：Cookie 存活批量自检
        test_ck = QPushButton("测试全部 Cookie 存活")
        test_ck.setObjectName("Ghost")
        test_ck.setToolTip(rich(
            "对每个**已启用**的数据源，用已获取的 Cookie 发一次轻量请求，"
            "判断 Cookie 是否仍有效（未获取 / 已过期 / 仍可用 三种结论）。"))
        test_ck.clicked.connect(self._test_all_cookies)
        sbh.addWidget(test_ck)
        # v1.40.0（反馈 4）：Cloudflare / WAF 验证助手的入口。
        # 放这里而不是塞进「刮削策略」参数网格 —— 网格是 6 项定值参数，多一个按钮
        # 会破坏 2 列对齐；而且它属于「连不上时怎么办」的处置动作，与「测试」同类。
        self.sc_cf = QPushButton("Cookie 获取…")
        self.sc_cf.setObjectName("Ghost")
        self.sc_cf.setToolTip(
            "站点被人机校验（Cloudflare / AWS WAF）挡住时点这里：\n"
            "借你的系统浏览器过一次校验，把通行 cookie 取回来复用。")
        self.sc_cf.clicked.connect(self._open_cloudflare)
        sbh.addWidget(self.sc_cf)
        # v1.40.5（反馈 2 —— 用户截图：「行间距太大，上下留白太多」）：
        #   原来是「按钮行」与「提示行」上下两行（组框 spacing=8），中间隔出一段空档。
        #   ⇒ 正解：**合到同一行** —— 按钮在左、提示在右，中间用 `addStretch` 弹性分隔；
        #     提示用 wordWrap 折行，窄窗时自己向下长，不再靠换行拉开距离。
        self.src_hint = QLabel("提示：minnano-av 面向日本 AV 女优（日文名检索）；IMDB 面向普通影视演员（英文名检索）；"
                              "无法直连 minnano-av 时在下方填写代理。")
        self.src_hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        self.src_hint.setWordWrap(True)
        # ⚠ v1.40.5 血泪：折行 QLabel 与按钮同行时**不能**用 `SizePolicy.Ignored`。
        #   `Ignored` 让布局把它当「宽度可以为 0」——`heightForWidth(0)` 于是算出
        #   4 行（60px），组框 sizeHint 直接爆到 831px（探针实测）。
        #   用 `Minimum`：允许它缩到 `minimumSizeHint`，但 `sizeHint` 仍按自己的
        #   文本宽算 → 组框 sizeHint = 231（120 列表 + 4 + 33 按钮 + 边距，正确）。
        #   （微探针实测：Ignored 无 min → 831；Ignored+min240 → 231；Minimum → 231。）
        self.src_hint.setMinimumWidth(0)
        self.src_hint.setSizePolicy(_SP.Minimum, _SP.Preferred)
        sbh.addStretch(1)
        sbh.addWidget(self.src_hint, 3)
        # v1.40.0（反馈 1）：给折行标签钉住最小高 —— **宽度未知时**的兜底。
        #
        # ⚠ 先纠正一个我在本轮排查中一度搞错的判断（探针逐值实锤后修正）：
        # `sizeHint().height()` 在这条标签上返回 **60**（按 198px 窄宽估算的 4 行），
        # 但那是「宽度未知」的保守估算。在**真实窗口宽**下量 `heightForWidth(1092)`
        # 只有 **15**（11px 字体行距），78 个字的文案在 1092px 里确实**一行放得下**。
        # 所以用户的截图里 `src_hint h=15` **不是**被压扁的 bug —— 文字是完整的。
        # 那条「空白带」的真实构成是：数据源列表被压到 120px（sizeHint 192），
        # 加上组框自身的留白，在「统计行」与「刮削策略」之间形成一段视觉空档。
        #
        # 这条钉高依然保留，因为它在**窄窗口**下是真有用的（W=900 时
        # `heightForWidth` 返回 30，标签需要两行；不钉的话 Qt 有把折行 QLabel
        # 压到一行、文字被截的风险 —— 折行 QLabel 是组框里唯一 `hasHeightForWidth()`
        # 的子项，空间不足时永远是第一个被牺牲的）。钉法是「按当前宽算真实需求」，
        # 所以宽窗口下它钉出的就是 15（不会平白占地方），窄窗口下自动变 30。
        g0v.addWidget(srcbtns)

        # ---------- v1.46.5（反馈 2）：其他数据源 ----------
        # 用户原话：「增加 其他数据源 的按钮，单选后点击 内置浏览器可以跳转到该网址
        # 进行 cookie 获取。」
        #
        # 为什么做成「二选一单选」而不是再加一个按钮：内置 5 个源的 cookie 目标本来
        # 由「已启用源里的第一个」隐式决定，用户看不见也改不了；加一个 radio 把这条
        # **隐式规则显式化**，选中「其他数据源」后「Cookie 获取…」的目标就变成用户
        # 自己填的网址 —— 一套按钮两种目标，不新增行数也不会误点到错的那个。
        #
        # ⚠ 两个 radio 必须是**同一个父控件**的子控件，Qt 才会自动互斥。
        otherw = QWidget()
        oh = QHBoxLayout(otherw)
        oh.setContentsMargins(0, 0, 0, 0)
        oh.setSpacing(8)
        self.sc_cf_auto = QRadioButton("Cookie 目标：自动")
        self.sc_cf_auto.setToolTip(
            "「Cookie 获取…」默认对**已启用数据源里排在最前**的那个站点取 cookie。")
        self.sc_cf_other = QRadioButton("其他数据源")
        self.sc_cf_other.setToolTip(
            "勾选后，「Cookie 获取…」先用内置浏览器打开右边这个网址，\n"
            "过完人机校验即把 cookie 注入该站点（内置 5 个源之外也能用）。")
        self.sc_other_url = QLineEdit()
        self.sc_other_url.setMinimumWidth(240)
        self.sc_other_url.setClearButtonEnabled(True)
        self.sc_other_url.setToolTip(
            "填站点**首页**（例如 https://javdb.com）。\n"
            "可省略 https://，保存时会自动补全；只接受 http / https。")
        self.sc_other_test = compact_button(
            "测试", 52, 28, "用该站点已注入的 cookie 发一次轻量请求，判断是否仍存活")
        self.sc_other_test.clicked.connect(self._test_other_source)
        self.sc_other_state = QLabel("—")
        self.sc_other_state.setStyleSheet("color:#a1a1aa;font-size:11px;")
        self.sc_other_state.setMinimumWidth(56)
        oh.addWidget(self.sc_cf_auto, 0)
        oh.addWidget(self.sc_cf_other, 0)
        oh.addWidget(self.sc_other_url, 1)
        oh.addWidget(self.sc_other_test, 0)
        oh.addWidget(self.sc_other_state, 0)
        g0v.addWidget(otherw)
        # 回填配置（老配置没有这两键 → 取 DEFAULT_SCRAPER 的 False / ""）
        _other_on = bool(sc.get("other_source_on", False))
        self.sc_cf_other.setChecked(_other_on)
        self.sc_cf_auto.setChecked(not _other_on)
        self.sc_other_url.setText(str(sc.get("other_source_url") or ""))
        # 只关心「其他数据源是否被选中」——两个 radio 天然互斥，选中另一个即 False
        self.sc_cf_other.toggled.connect(self._on_other_source_toggled)
        self.sc_other_url.editingFinished.connect(self._save_other_url)
        self._apply_other_source(_other_on)

        # v1.41.0（方案B）：用内置浏览器会话抓取（绕开 TLS 指纹 / 进程级拦截）
        self.sc_browser_on = ToggleSwitch(checked=bool(sc.get("browser_scrape", False)))
        self.sc_browser_on.toggled.connect(self._on_browser_scrape_toggled)
        broww = QWidget()
        browh = QHBoxLayout(broww)
        browh.setContentsMargins(0, 0, 0, 0)
        browh.setSpacing(8)
        browh.addWidget(QLabel("用内置浏览器抓取"))
        browh.addWidget(self.sc_browser_on)
        browh.addWidget(QLabel("被拦的源改走 WebView2 常驻会话（需先对该源点一次「Cookie 获取」）"))
        browh.addStretch(1)
        g0v.addWidget(broww)
        # v1.43.0（需求 4）：**头像独立源 gfriends** —— 与上面的「资料源」分开：
        # 它只出头像、不出任何资料字段，所以单独一个开关，不参与 sources 排序。
        self.sc_gf = ToggleSwitch(checked=bool(sc.get("gfriends_photo", True)))
        self.sc_gf.toggled.connect(lambda c: self.s.set_scraper(gfriends_photo=c))
        gfrow = QWidget()
        gfh = QHBoxLayout(gfrow)
        gfh.setContentsMargins(0, 0, 0, 0)
        gfh.setSpacing(8)
        gfh.addWidget(QLabel("头像独立源：gfriends"))
        gfh.addWidget(self.sc_gf)
        gfh.addWidget(QLabel("资料源都没给头像时按姓名补一张（github.com/gfriends/gfriends，"
                             "约 10 万张，首次使用下载 4.8MB 索引）"))
        gfh.addStretch(1)
        g0v.addWidget(gfrow)        # 把开关状态同步给浏览器会话单例（后台刮削也算）
        browser_session.SESSION.set_enabled(bool(sc.get("browser_scrape", False)))
        # v1.40.0（反馈 1）：**钉住组框最小高**，让「数据源列表」不再被压。
        #
        # 探针实测（E 盘 v1.40.0 / 真机 1085px 宽 / 离屏）：
        #   组框 h=247  sizeHint=262   → 差 15px
        #   ├─ QListWidget  h=120  sh=192   ★ 这里才是被压得最狠的（少 72px）
        #   ├─ QWidget(按钮行) h=33  sh=33
        #   └─ QLabel(src_hint) h=15  sh=15  （一行放得下，没被裁）
        # 也就是说：老版本「列表只露一两行就断、下面一段空」的观感，主因是
        # QListWidget 被布局压掉 72px，而不是提示标签出问题。
        #
        # 光靠「把窗口调高」治不了：屏幕可用高只有 800，窗口顶到 1093 仍不够时
        # `_fit_page()` 的长高路线就失效了。所以按**内容真实需求**钉最小高 ——
        # 布局宁可让**页面**滚动，也不会再牺牲组框里的列表。
        #
        # ⚠ 不用 `lay.sizeHint().height()`：那玩意儿在被压缩过一次之后返回的就是
        # 缩水值（本例 247），拿它钉等于把「被压扁的状态」固化下来，白钉。
        # `_pin_min_height()` 内部改成**逐子项 sizeHint 累加**（与 `_content_height`
        # 同一套算法），取到的才是 262 这个真实需求。
        QTimer.singleShot(0, lambda box=g0, lay=g0v: self._pin_min_height(box, lay))
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
        # v1.40.0（反馈 3）：代理显式开关 —— 之前只有输入框，靠「填没填」隐式决定，
        # 用户没法表达「我要直连、别用系统的那个代理」。关掉时代码走 cfg.scraper_proxy()
        # 返回空串（连系统代理都不套），同时把输入框置灰给出即时视觉反馈。
        self.sc_proxy_on = ToggleSwitch(checked=bool(sc.get("proxy_enabled", False)))
        self.sc_proxy_on.toggled.connect(self._on_proxy_toggled)
        proxyw = QWidget()
        proxyh = QHBoxLayout(proxyw)
        proxyh.setContentsMargins(0, 0, 0, 0)
        proxyh.setSpacing(8)
        proxyh.addWidget(self.sc_proxy, 1)
        proxyh.addWidget(QLabel("使用代理"))
        proxyh.addWidget(self.sc_proxy_on)
        self._apply_proxy_enabled(self.sc_proxy_on.isChecked())
        # v1.40.0（反馈 3）：把落盘的开关状态同步给引擎（不只影响本页——后台刮削也算）。
        scraper_mod.set_proxy_disabled(not self.sc_proxy_on.isChecked())
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
                ("代理", proxyw), ("头像缓存目录", dirw))):
            r, c = i // 2, (i % 2) * 2
            nf.addWidget(QLabel(lab), r, c)
            nf.addWidget(wid, r, c + 1)
        g2v.addLayout(nf)
        v.addWidget(g2)
        QTimer.singleShot(0, lambda box=g2, lay=g2v: self._pin_min_height(box, lay))

        # 执行：四种刮削模式（v1.22.0 反馈 1 —— 全量 / 增量 / 补齐 / 修复）
        g3 = QGroupBox("执行")
        g3v = QVBoxLayout(g3)
        # v1.40.2（反馈 3）：组内行距收紧，减少「执行」区整体的竖向占用与底部漂浮感。
        g3v.setSpacing(6)
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
        modehint.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        self.sc_mode_hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        self.sc_mode_hint.setWordWrap(True)
        g3v.addWidget(self.sc_mode_hint)
        self.sc_prog = QProgressBar()
        self.sc_prog.setRange(0, 100)
        self.sc_prog.setValue(0)
        g3v.addWidget(self.sc_prog)
        self.sc_log = QPlainTextEdit()
        self.sc_log.setReadOnly(True)
        # v1.40.0（反馈 2）：用户要求「加大执行日志显示区域」。
        # 原来写死 setFixedHeight(48) —— 在默认字体下只有 ~3 行，一条完整的测连结果
        # （「[测试] IMDB：不可用 — 命中反爬挑战页…」这类文案本身就要折 2 行）都把框撑满，
        # 历史日志一滚就看不见了。
        # v1.40.1（反馈 2 回修）：v1.40.0 直接提到 240px（约 14 行）又**占得太多**，
        # 用户要求「缩小一半」。取 120px（约 7 行）作**默认弹性高度**。
        # ★ v1.40.3（本轮，反馈 1「压缩执行的高度」）：**上一版修错了方向**。
        #   上一版让执行组框吃 stretch=1，本意是「组框底边贴页底、不留白」，实际效果是
        #   **多余高度全进了日志框**（QPlainTextEdit 的水平/垂直 sizePolicy = Expanding，
        #   组内只有它一个 Expanding 项）→ 真机 1080p 下日志框被撑到 200px+，
        #   用户看到的就是「执行区一大片空的日志区」（本轮截图）。
        #   ⇒ 正解：**日志框固定高度**（`setFixedHeight`，彻底不参与拉伸），
        #   执行组框也**不再吃 stretch**，多余高度交回页级弹簧（放到页尾）。
        #   这样执行区高度 = 内容固有高度（与窗口大小无关），页面总高变大时
        #   多余空间出现在**页底空白**而不是**日志框里**，符合「压缩执行的高度」。
        self.sc_log.setFixedHeight(96)          # 约 6 行；固定值 → 不再随窗口长高
        # v1.40.11：样式复刻「运行日志（实时）」—— 等宽字体 + 半透明深色底 + 浅色字 + 不自动换行。
        self.sc_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.sc_log.setStyleSheet(LOG_BOX_STYLE)
        self.sc_log.setPlaceholderText("刮削日志…")
        g3v.addWidget(self.sc_log)
        note = QLabel("说明：仅补齐演员资料并下载头像，不修改任何媒体文件；遵守目标站点 robots / 使用条款，"
                      "间隔过小可能被限流。")
        note.setStyleSheet("color:#a1a1aa;font-size:11px;")
        note.setWordWrap(True)
        g3v.addWidget(note)
        # v1.40.2（反馈 3）：曾把执行组框改成 stretch=1（「让组框吃满余量、底边贴页底」）。
        # ★ v1.40.3（本轮，反馈 1「压缩执行的高度」）：**这条改法是错的，现在回退**。
        #   实测（探针 probe_exec_h.py）：`QPlainTextEdit` 的 sizePolicy 是 Expanding，
        #   组内只有它一个 Expanding 项 → stretch=1 时**所有余量都灌进日志框**，
        #   真机 1080p 下日志框被撑到 200px+，用户看到的正是「执行区一大片空的日志区」
        #   （本轮截图 1086×320 的核心问题）。
        #   ⇒ 正解：执行组框**不吸 stretch**（=0），日志框**固定高度**（setFixedHeight），
        #   页尾放回一段弹簧 —— 余量出现在**页面底部空白**，而不是**日志框里**。
        #   效果：执行区高度 = 内容固有高度（与窗口大小无关），即「压缩执行的高度」。
        # ★ v1.40.4（本轮，反馈 1「取消执行窗的弹性，让界面高度锁死在 960px」）：
        #   上一版把余量放在「页尾弹簧」里 —— 它仍然是一种弹性（弹簧会吃掉所有
        #   剩余高度，页面总高不变时看不出，但窗口被 `_fit_page` 撑高时那段空白就
        #   会变长，视觉上仍是「执行区在长高」）。用户要求**彻底取消弹性**。
        #   ⇒ 正解：**去掉页尾弹簧**。执行组框之下不再有任何可伸缩项 →
        #   页面 = 5 个组框的固有高度之和（严格恒定），而窗口本身已被
        #   `setFixedHeight(960)` 钉死 → 两者都不再随任何操作变化。
        #   余量的去处：由上层 `QStackedWidget` 吸收（页面在 stack 里顶端对齐、
        #   底部留白归 stack，与执行区无关）。
        v.addWidget(g3)
        QTimer.singleShot(0, lambda box=g3, lay=g3v: self._pin_min_height(box, lay))

        self._refresh_scraper_stats()
        # v1.43.1（反馈 1 真因）：只把页面改回 lock_height 还不够 —— **组框自身**
        # 的垂直 sizePolicy 是 Preferred，父布局手里一旦多出几十像素（画布按
        # sizeHint 取高时会自带余量），Qt 就把它塞进第一个能长的组框：
        # 「演员刮削」组框从 67px 被撑到 133px，看起来就是「行高变大」。
        # ⇒ 本页所有组框统一 `(Preferred, Maximum)`：高度 = sizeHint，绝不吃余量。
        try:
            for _g in page.findChildren(QGroupBox):
                _g.setSizePolicy(_SP.Preferred, _SP.Maximum)
        except Exception:
            pass
        return page

    def _rebuild_source_list(self):
        self.src_list.clear()
        # v1.42.2：`_src_rows` 存的是**上一批**结果标签的引用；下面就要把旧行
        # 控件收尸销毁，留着即悬空引用（若某数据源的测试 worker 迟到回报，
        # `_on_test_done` 拿到已删的 C++ 标签会 RuntimeError）。每批重建都会
        # 重新注册所有在列数据源，先清空。
        self._src_rows.clear()
        # v1.42.2（反馈 2）：Qt 已知行为 —— `clear()` **不会**删除
        # `setItemWidget` 挂上去的旧行 widget，它们会以孤儿身份继续留在
        # viewport 上（实测每次重建往 viewport 堆 3 个孤儿行控件、连带各自
        # 6 个子控件；用户反复「上移/下移」数据源后会无限堆积，且重排后旧行
        # widget 停在新行的旧位置上，有透出重影的风险）。这里先显式收尸再重建。
        for _w in self.src_list.viewport().children():
            if isinstance(_w, QWidget):
                # 三连：hide + 脱父 + deleteLater。单用 deleteLater 要等事件
                # 轮次冲 DeferredDelete 才生效（无事件循环时永远挂在 viewport
                # 上）；直接脱父不 hide 会让**可见**行控件变成顶层小窗闪一下。
                _w.hide()
                _w.setParent(None)
                _w.deleteLater()
        sc = self.s.scraper
        info = {x["key"]: x for x in cfg.SCRAPER_SOURCES}
        for key in sc.get("sources", []):
            it = info.get(key, {"key": key, "name": key, "desc": ""})
            li = QListWidgetItem(self.src_list)
            li.setData(Qt.UserRole, key)          # 便于按行反查数据源 key
            row = QWidget()
            h = QHBoxLayout(row)
            # v1.42.0（反馈：数据源行太高）：上下留白 4→2，配合 SRC_ROW_H 44 收紧行高。
            h.setContentsMargins(6, 2, 6, 2)
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
            res.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        # v1.42.2（反馈 2）：真机曾出现「IMDB 行下方凭空多一条 44px 空槽」——
        # 截图实证：空档色=列表底（20,18,14）而非组框底（27,25,23）、列表
        # 底边框紧贴其下、空档内零内容像素 → 列表里多了一个**没有挂 widget
        # 的项**，把 count 算成 4、`setFixedHeight` 按 44×4+8=184 钉高。
        # 根因未复现（离屏 / Windows 平台 + 同版本 Qt 6.11.2 + 3 源配置均稳定
        # count=3，4 源场景也每行都带 widget），按「宁缺勿滥」原则做兜底：
        # 正常循环里每一项都会 setItemWidget，清掉漏网的幻影项即可。
        for _i in range(self.src_list.count() - 1, -1, -1):
            _it = self.src_list.item(_i)
            if self.src_list.itemWidget(_it) is None:
                try:
                    applog.log("演员刮削：清掉无 widget 的幻影数据源行"
                               f"（idx={_i} key={_it.data(Qt.UserRole)!r}）", "warn")
                except Exception:
                    pass
                self.src_list.takeItem(_i)
        n = self.src_list.count()
        # v1.43.1（反馈 5）：列表**固定只露三行**（44×3+8=140），其余靠列表自带滚轴翻页。
        # 六源全展开（272px）会把整页顶出视口、连带把「执行」区挤到滚动区外面。
        self.src_list.setFixedHeight(max(64, SRC_ROW_H * min(n, 3) + 8))

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

    # ---------- v1.40.0（反馈 3）：代理显式开关 ----------
    def _apply_proxy_enabled(self, on):
        """开关状态 → 输入框可用性 + 即时视觉反馈。

        关（直连）：输入框置灰、值仍保留（下次打开还在，不丢用户填过的地址）；
        开：输入框恢复，占位提示写明「留空则用系统代理」。
        """
        on = bool(on)
        self.sc_proxy.setEnabled(on)
        self.sc_proxy.setPlaceholderText(
            "留空则用系统代理；例如 http://127.0.0.1:7890" if on
            else "代理已关闭（直连）—— 打开右侧开关后才生效")
        self.sc_proxy.setToolTip(
            "已启用：请求会走这个代理；留空时回落到系统代理设置。\n"
            "关闭时：完全直连，**连系统代理也不套**。" if on
            else "当前为直连模式：不看这个输入框、也不读系统代理。")

    def _on_proxy_toggled(self, checked):
        self.s.set_scraper(proxy_enabled=bool(checked))
        self._apply_proxy_enabled(checked)
        # 同步告诉 scraper 引擎「用户要的就是纯直连」——否则 http_get 里
        # `if not proxy: proxy = _system_proxy()` 会把关掉的代理又补回来。
        scraper_mod.set_proxy_disabled(not bool(checked))
        self._log("[代理] 已%s —— %s" % (
            "启用" if checked else "关闭（直连）",
            ("使用 " + self.sc_proxy.text().strip())
            if checked and self.sc_proxy.text().strip()
            else ("使用系统代理" if checked else "忽略代理与系统代理设置")))

    def _on_browser_scrape_toggled(self, checked):
        """v1.41.0（方案B）：开关「用内置浏览器抓取」。

        打开 → 把浏览器会话单例置为可用；关闭 → 回收所有已托管的浏览器会话
        （避免遗留常驻 WebView2 窗口）。无论开关键，都要先对被拦的源点一次
        「Cloudflare 验证」建立会话，抓取才会真正走浏览器。
        """
        on = bool(checked)
        self.s.set_scraper(browser_scrape=on)
        browser_session.SESSION.set_enabled(on)
        if not on:
            browser_session.SESSION.detach()      # 关开关即回收所有常驻会话
        self._log("[浏览器抓取] 已%s —— %s" % (
            "启用" if on else "关闭",
            "被拦的源将改走 WebView2 常驻会话（需先对该源点一次「Cookie 获取」）"
            if on else "恢复无头抓取，常驻浏览器会话已回收"))

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

    def _open_people_clean(self):
        """v1.43.0（需求 3）：演员库清理对话框（删除无作品关联的冗余条目）。"""
        dlg = PeopleCleanDialog(self, on_done=self._after_people_clean)
        dlg.exec()

    def _after_people_clean(self):
        self._refresh_scraper_stats()
        if self.on_changed:
            self.on_changed()

    def _log(self, text):
        self.sc_log.appendPlainText(text)

    def _test_all_cookies(self):
        """v1.44.1（需求 3）：批量检测已启用数据源的 Cookie 是否存活。"""
        keys = self.s.scraper_sources()
        if not keys:
            QMessageBox.information(self, "提示", "请至少启用一个数据源。")
            return
        self._log(f"[Cookie 自检] 检查 {len(keys)} 个已启用数据源的 Cookie 存活…")
        if not hasattr(self, "_cookie_workers"):
            self._cookie_workers = []
        for key in keys:
            w = TestCookieWorker(key, self.s.scraper_proxy(),
                                 int(self.sc_timeout.value()))
            w.done.connect(self._on_cookie_done)
            w.finished.connect(self._prune_cookie_workers)
            self._cookie_workers.append(w)
            w.start()

    def _prune_cookie_workers(self):
        try:
            self._cookie_workers = [w for w in getattr(self, "_cookie_workers", [])
                                    if w.isRunning()]
        except Exception:
            pass

    def _on_cookie_done(self, key, res):
        name = scraper_mod.SOURCE_NAMES.get(key, key)
        ok = bool(res.get("ok"))
        if ok:
            state = "可用"
        elif not res.get("has_cookie"):
            state = "未获取"
        else:
            state = "已失效"
        self._log(f"[Cookie] {name}：{state} — {res.get('msg')}"
                  f"（{res.get('ms')} ms）")
        lbl = self._src_rows.get(key)
        if lbl is not None:
            lbl.setText("Cookie✓" if ok else ("未获取" if not res.get("has_cookie") else "失效"))
            lbl.setStyleSheet("color:#45d483;font-size:11px;" if ok
                              else "color:#f87171;font-size:11px;")
        try:
            applog.log(f"[Cookie 自检] {name} ok={ok} msg={res.get('msg')}")
        except Exception:
            pass

    def _test_source(self, key):
        self._log(f"[测试] {scraper_mod.SOURCE_NAMES.get(key, key)} …")
        lbl = self._src_rows.get(key)
        if lbl is not None:
            lbl.setText("测试中…")
            lbl.setStyleSheet("color:#66a9ff;font-size:11px;")
        w = TestSourceWorker(key, self.s.scraper_proxy(), int(self.sc_timeout.value()))
        w.done.connect(self._on_test_done)
        w.start()
        if not hasattr(self, "_test_workers"):
            self._test_workers = []
        self._test_workers.append(w)

    def _test_all_sources(self):
        for key in self.s.scraper.get("sources", []):
            self._test_source(key)

    # ---------- v1.46.5（反馈 2）：其他数据源 ----------
    def _apply_other_source(self, on):
        """单选状态 → 网址输入框 / 测试按钮的可用性与提示文案。"""
        on = bool(on)
        self.sc_other_url.setEnabled(on)
        self.sc_other_test.setEnabled(on)
        self.sc_other_url.setPlaceholderText(
            "填站点首页，例如 https://example.com" if on
            else "未启用 —— 勾选左侧「其他数据源」后可填")
        if not on:
            self.sc_other_state.setText("—")
            self.sc_other_state.setStyleSheet("color:#a1a1aa;font-size:11px;")

    def _on_other_source_toggled(self, on):
        """「其他数据源」被选中 / 取消 → 立刻落盘，并说清「Cookie 获取…」现在打哪儿。"""
        on = bool(on)
        self.s.set_scraper(other_source_on=on)
        self._apply_other_source(on)
        if on:
            url = scraper_mod.normalize_base_url(self.sc_other_url.text())
            self._log("[Cookie 目标] 已切到「其他数据源」：%s"
                      % (url or "（还没填网址，点「Cookie 获取…」会被拦下）"))
            if not url:
                self.sc_other_url.setFocus()
        else:
            self._log("[Cookie 目标] 已切回「自动」—— 取已启用数据源里排在最前的那个")

    def _save_other_url(self):
        """规整并保存自定义网址（`example.com` → `https://example.com`）。"""
        raw = (self.sc_other_url.text() or "").strip()
        url = scraper_mod.normalize_base_url(raw)
        if raw and not url:
            self.sc_other_state.setText("网址无效")
            self.sc_other_state.setStyleSheet("color:#f87171;font-size:11px;")
            self._log("[Cookie 目标] 网址无效（只接受 http / https，且需带域名）：%s" % raw)
            return
        if url and url != raw:
            self.sc_other_url.setText(url)
        if (self.s.scraper.get("other_source_url") or "") != url:
            self.s.set_scraper(other_source_url=url)

    def _test_other_source(self):
        """用自定义站点**已注入的 cookie** 发一次轻量请求，判断是否仍存活。"""
        self._save_other_url()
        url = scraper_mod.normalize_base_url(self.sc_other_url.text())
        if not url:
            QMessageBox.information(
                self, "提示", "请先填写站点网址（例如 https://example.com）再测试。")
            self.sc_other_url.setFocus()
            return
        self.sc_other_state.setText("测试中…")
        self.sc_other_state.setStyleSheet("color:#66a9ff;font-size:11px;")
        self._log(f"[Cookie 自检] 其他数据源 {url} …")
        w = TestCookieWorker(url, self.s.scraper_proxy(),
                            int(self.sc_timeout.value()), as_url=True)
        w.done.connect(self._on_other_cookie_done)
        w.finished.connect(self._prune_cookie_workers)
        if not hasattr(self, "_cookie_workers"):
            self._cookie_workers = []
        self._cookie_workers.append(w)
        w.start()

    def _on_other_cookie_done(self, url, res):
        ok = bool(res.get("ok"))
        if ok:
            state = "可用"
        elif not res.get("has_cookie"):
            state = "未获取"
        else:
            state = "已失效"
        self.sc_other_state.setText("✓ 可用" if ok else state)
        self.sc_other_state.setStyleSheet(
            "color:#45d483;font-size:11px;" if ok else "color:#f87171;font-size:11px;")
        self._log(f"[Cookie] 其他数据源（{url}）：{state} — {res.get('msg')}"
                  f"（{res.get('ms')} ms）")
        try:
            applog.log(f"[Cookie 自检·其他数据源] {url} ok={ok} msg={res.get('msg')}")
        except Exception:
            pass

    # ---------- v1.40.0（反馈 4）：Cloudflare / WAF 验证助手 ----------
    def _cookie_target(self):
        """「Cookie 获取」现在要打哪个站点 → `(host_url, 显示名, 是否自定义)`。

        v1.46.5（反馈 2）：抽成独立方法，一是让 `_open_cloudflare` 只剩「开对话框」，
        二是离屏冒烟可以直接断言目标解析结果（不必真弹对话框、更不必起浏览器子进程）。
        自定义网址无效时返回 `(None, "其他数据源", True)` —— 调用方负责提示用户。
        """
        custom = bool(getattr(self, "sc_cf_other", None) is not None
                      and self.sc_cf_other.isChecked())
        if custom:
            url = scraper_mod.normalize_base_url(self.sc_other_url.text())
            return (url or None), "其他数据源", True
        key = (self.s.scraper_sources() or ["minnano"])[0]
        # v1.46.5：原来只映射了 minnano / imdb 两个 key，其余（avbase / javdb /
        # wikipedia）**统统落到 minnano 的站点** —— 用户选了 javdb 却去 minnano
        # 取 cookie，日志里却写着「Cookie 获取 · JavDB」。改用 SOURCE_BASES 统一取。
        host = scraper_mod.SOURCE_BASES.get(key, scraper_mod.MINNANO_BASE)
        return host, scraper_mod.SOURCE_NAMES.get(key, key), False

    def _open_cloudflare(self):
        """打开验证对话框。站点由「Cookie 目标」单选决定（v1.46.5）：

        · **自动** → 用户已启用且排在最前的数据源（老行为）；
        · **其他数据源** → 用户自填网址，并**直接拉起内置浏览器跳转到该网址**，
          用户在里面过完人机校验就点「获取 Cookie」，cookie 会注入这个 host。
        """
        host, name, custom = self._cookie_target()
        if custom:
            if not host:
                QMessageBox.information(
                    self, "提示",
                    "已选「其他数据源」，但网址还是空的或无效。\n\n"
                    "请先填一个站点首页（例如 https://example.com），"
                    "再点「Cookie 获取…」。")
                self.sc_other_url.setFocus()
                return
            self._save_other_url()
            host, name, custom = self._cookie_target()
        if getattr(self, "_cf_dlg", None) is None:
            self._cf_dlg = CloudflareDialog(host, f"Cookie 获取 · {name}", parent=self)
        else:
            self._cf_dlg.host_url = host
            self._cf_dlg.setWindowTitle(f"Cookie 获取 · {name}")
            self._cf_dlg._refresh_state()
        self._cf_dlg.show()
        self._cf_dlg.raise_()
        self._cf_dlg.activateWindow()
        if custom:
            # 用户要的就是「单选后点内置浏览器直接跳到该网址」—— 延迟一帧等对话框
            # 先画出来，再拉起内置浏览器（`_open_builtin` 自身对重复调用有守卫）。
            self._log(f"[Cookie 目标] 用内置浏览器打开自定义站点：{host}")
            QTimer.singleShot(120, self._cf_dlg._open_builtin)

    def _on_test_done(self, key, res):
        name = scraper_mod.SOURCE_NAMES.get(key, key)
        self._log(f"[测试] {name}：{'可用' if res.get('ok') else '不可用'} — "
                  f"{res.get('msg')} （{res.get('ms')} ms）")
        # v1.40.2（反馈 2）：用户要求「查看运行日志，查明失败原因」。把分层诊断结论
        # 直接写进日志框（用户看的就是这里），一眼能看出「拦在 TLS 握手」还是「cookie 问题」。
        #
        # ★ v1.40.4（反馈 2「握手成功了也不太行」）：上一版只打 stage + verdict，
        #   而 stage 只有 tcp/tls/http 三档 → **TLS 通了但正文是挑战页**（IMDB 的
        #   真实情形）与「HTTP 层被硬拒」都被混进 `stage=http`，用户看到的就是
        #   「失败层：http」配一句「若仍被拦，才是 cookie / WAF 层的问题」——
        #   等于没回答。现在 `diagnose_host` 已探到 HTTP 正文层，新增 `waf` /
        #   `body_len` 两个字段，这里**按真实层**给一句明确结论 + 下一步。
        diag = res.get("diag") or {}
        if not res.get("ok") and diag:
            stage = diag.get("stage")
            self._log(f"[诊断] 失败层：{self._stage_cn(stage)}　{diag.get('verdict')}")
            if stage == "waf":
                self._log(f"[诊断] 正文 {diag.get('body_len')} 字节，"
                          f"HTTP {diag.get('http_code')} —— 挑战页靠浏览器执行 JS 放行，"
                          "取 cookie 无效；出路见上一条。")
            for line in (diag.get("detail") or []):
                self._log(f"[诊断] {line}")
            applog.log(f"[刮削测试·诊断] {name} stage={stage} "
                       f"waf={diag.get('waf')} body_len={diag.get('body_len')} "
                       f"verdict={diag.get('verdict')}")
        lbl = self._src_rows.get(key)
        if lbl is not None:
            ok = bool(res.get("ok"))
            lbl.setText("可用" if ok else "不可用")
            lbl.setStyleSheet("color:#45d483;font-size:11px;" if ok
                              else "color:#f87171;font-size:11px;")

    @staticmethod
    def _stage_cn(stage):
        """失败层的中文名。★ v1.40.4（反馈 2）：上一版直接打英文 `tls` / `http`，
        用户得自己猜是哪一层；而 `http` 这一个词把「被硬拒」与「拿到挑战页」
        混在一起，正是「握手成功了也不太行」的成因。"""
        return {"tcp": "TCP 连接（DNS / 路由）",
                "tls": "TLS 握手",
                "waf": "HTTP 正文（反爬挑战页）",
                "http": "HTTP 应用层",
                "ok": "无（链路与正文都正常）"}.get(stage or "", stage or "未知")

    def _scrape_opts(self):
        """当前配置好的刮削参数（含数据源、头像目录）。"""
        sc = dict(self.s.scraper)
        sources = self.s.scraper_sources()
        if not sources:
            return None
        sc["sources"] = sources
        sc["photo_dir"] = self.s.scraper_photo_dir()
        # v1.40.0（反馈 3）：代理由开关决定 —— 关掉时这里就是空串（直连），
        # scraper 侧的 `if not proxy: proxy = _system_proxy()` 也就不会兜回系统代理。
        sc["proxy"] = self.s.scraper_proxy()
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
                     + (f"代理 {sc.get('proxy')}。" if sc.get('proxy') else "**直连**（未启用代理）。")
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
        # v1.46.12：偏好的后台线程**必须在窗口销毁前收掉** —— 它 parent 是本窗口，
        # 窗口一 deleteLater 就会「QThread: Destroyed while thread is still running」
        # 直接把进程 abort（v1.27.0 踩过的同一个坑）。停止点是协作式的，
        # 每 25 条 / 每次进度回调都会看一眼，所以这里等得住。
        pw = getattr(self, "_prefs_worker", None)
        if pw is not None:
            try:
                if pw.isRunning():
                    pw.request_stop()
                    self.pref_status.setText("正在停止偏好任务…")
                    pw.wait(10000)
            except RuntimeError:
                pass
        for t in (getattr(self, "_test_workers", None) or []):
            if t.isRunning():
                t.wait(3000)
        # v1.18.0 反馈 98：关闭即停止刷新定时器
        if getattr(self, "_rt_timer", None) is not None:
            self._rt_timer.stop()
        # v1.39.0（需求 3）：导航转圈轮询也停掉（任务仍在后台跑，只是不刷了）
        if getattr(self, "_busy_timer", None) is not None:
            self._busy_timer.stop()
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
        hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        # v1.46.15：单独命名 —— QSS 里把它的 ::item 上下 padding 从 5px 压到 2px，
        # 否则 44 的行高里仍有 10px 被内边距吃掉（见 LIB_ROW_H 注释）。
        self.lib_list.setObjectName("LibList")
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
        self.lib_status.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        v.setSpacing(10)

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
        self.ins_status.setStyleSheet("color:#a1a1aa;font-size:11px;")
        top.addWidget(self.ins_status, 1)
        v.addLayout(top)

        # 一句话画像
        g0 = QGroupBox("一句话画像")
        g0v = QVBoxLayout(g0)
        self.ins_line = QLabel("—")
        self.ins_line.setWordWrap(True)
        self.ins_line.setStyleSheet("color:#d4d4d8;font-size:13px;")
        g0v.addWidget(self.ins_line)
        v.addWidget(g0)

        # 雷达 + 概览数字
        mid = QHBoxLayout()
        mid.setSpacing(12)
        g1 = QGroupBox("八维偏好雷达")
        g1v = QVBoxLayout(g1)
        self.ins_radar = RadarChart()
        # v1.40.9（反馈「画像概览不用下滚轴」）：把雷达钉到 260 高，免得它把
        # 「雷达 + 概览」整行撑到 ~384，从而给下方省出高度让全页塞进一屏。
        self.ins_radar.setFixedHeight(220)
        g1v.addWidget(self.ins_radar, 1)
        self.ins_radar_tip = QLabel("—")
        self.ins_radar_tip.setWordWrap(True)
        self.ins_radar_tip.setStyleSheet("color:#71717a;font-size:11px;")
        g1v.addWidget(self.ins_radar_tip)
        mid.addWidget(g1, 3)

        g2 = QGroupBox("概览")
        g2v = QVBoxLayout(g2)
        self.ins_ov = QLabel("—")
        self.ins_ov.setWordWrap(True)
        self.ins_ov.setTextFormat(Qt.RichText)
        self.ins_ov.setStyleSheet("color:#d4d4d8;font-size:12px;")
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
            # v2.0.2（反馈 5）：列标题跟随高亮色（原写死 #66a9ff → 换主题不变色）
            lb.setObjectName("PanelTitleSm")
            g3v.addWidget(lb, 0, col)
            body = self._bar_label()
            g3v.addWidget(body, 1, col)
            self.ins_lists[key] = body

        # 分布 + 共现（v1.40.9：高频榜 g3 与分布 g4 并排成一行，见下方 low 行）
        g4 = QGroupBox("分布")
        g4v = QGridLayout(g4)
        g4v.setHorizontalSpacing(18)
        self.ins_dist = {}
        for col, key in enumerate(("画质", "评分", "时长", "年份", "入库月")):
            lb = QLabel(key)
            # v2.0.2（反馈 5）：同上，跟随高亮色
            lb.setObjectName("PanelTitleSm")
            g4v.addWidget(lb, 0, col)
            body = self._bar_label()
            g4v.addWidget(body, 1, col)
            self.ins_dist[key] = body

        # v1.40.9（反馈「画像概览不用下滚轴」）：高频榜 + 分布 并排成一行，
        # 原来单列各 ~310 高、上下堆叠占 ~632，并排后只占一行 ~310，
        # 直接省掉一整块竖向高度，配合雷达收窄让全页能塞进一屏、不出现下滚轴。
        low = QHBoxLayout()
        low.setSpacing(12)
        low.addWidget(g3)
        low.addWidget(g4)
        v.addLayout(low)

        g5 = QGroupBox("标签共现（老是一起出现的两个标签）")
        g5v = QVBoxLayout(g5)
        self.ins_cooc = QLabel("—")
        self.ins_cooc.setWordWrap(True)
        self.ins_cooc.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
            body.setText(self._bar_lines(data.get(key) or [], body,
                                          show_bar=True, accent=self.s.accent()))
        for key, body in self.ins_dist.items():
            body.setText(self._bar_lines((data.get("dist") or {}).get(key) or [],
                                          body, accent=self.s.accent()))
        # cooc 是 [( (tagA, tagB), 次数 )]，键为元组，不是三元组
        cooc = data.get("cooc") or []
        parts = []
        for item in cooc:
            pair, cnt = item[0], item[1]
            if isinstance(pair, (tuple, list)) and len(pair) >= 2:
                parts.append(f"「{pair[0]}」+「{pair[1]}」 {int(cnt):,} 部")
        self.ins_cooc.setText("　".join(parts) or "—")
        # v1.40.8：分析完成后「高频榜 / 分布 / 共现」由「—」涨成真内容，整页高
        # 大幅增加（792 → 1200+）。画布最小高必须跟着重算，否则底部「标签共现」
        # 被裁掉（用户截图 2）。延一轮事件循环再量，等布局吃进新文本。
        self._refresh_frozen_height_soon(self._pg_insight)
        applog.log(f"[画像概览] {ov['scope']}：{ov['media']} 部作品分析完成")

    def _refresh_frozen_height_soon(self, scroll_or_page):
        """延一轮事件循环后重算画布最小高（v1.40.8）。

        v1.40.8 起就是 `_show_refresh_frozen()` 的别名 —— 两者语义完全一致
        （传滚动区或页面都认、都延一轮、都走 `_refresh_frozen_height`）。
        保留这个名字是因为「分析完成后重算」这个调用点的语义更具体。
        """
        self._show_refresh_frozen(scroll_or_page)

    @staticmethod
    def _bar_label():
        """画像概览里「高频榜 / 分布」的等宽条形文本标签。

        v1.39.1（反馈 4）：**必须 `setWordWrap(False)` + 横向 `Ignored` 尺寸策略**。
        旧版是 `wordWrap=True`，而条形图那一行是「标签 + 右对齐计数 + █ 条」拼出来
        的**长文本**，列宽（约 150px ≈ 22 个等宽格）根本放不下 → Qt 把它折行，
        结果计数与条形被甩到下一行、和下一条目的文字糊成一片（用户截图里
        「系列 / 片商 / 导演」列最明显）。改成不换行后：一行就是一行，超宽部分
        由 `_bar_lines()` 按像素预算先裁掉（名字截断加 …），永远不会折行。
        横向 `Ignored` 是配套的 —— 不换行的 QLabel 其 `minimumSizeHint()` 就是
        整段文本宽度，直接用会把网格列顶宽、把整页横向撑爆（Qt 老坑）。

        v1.40.10（反馈 3 · 美化）：改用 **RichText**（`setTextFormat(RichText)`），
        让名字 / 计数 / 条形三段各上不同颜色 —— 条形用当前**高亮色**（accent），
        名字用 tan、计数用浅金，整列从「一片灰字」变成「带强调色的条形图」，
        与全站风格统一。`setWordWrap(False)` 保留：长行不折行、超宽由
        `_bar_lines()` 裁掉，多行之间靠 `<br>` 换行（RichText 下 `<br>` 仍生效）。
        """
        lb = QLabel("—")
        lb.setWordWrap(False)
        lb.setTextFormat(Qt.RichText)
        lb.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        lb.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        lb.setStyleSheet("color:#a1a1aa;font-size:12px;"
                         "font-family:Consolas,'Courier New',monospace;")
        return lb

    def _bar_lines(self, items, body, show_bar=True, limit=16, accent="#f31260"):
        """把 [(名称, 计数)] 画成「文本 + █ 条」的简易条形图（不引图表库）。

        v1.39.1（反馈 4）：**按目标标签的实际像素宽度裁剪**，不再按字符数。
        根因：旧写法 `str(name)[:18].ljust(18)` 是按**字符数**对齐，可这字体是
        等宽 + CJK 回退 —— 一个汉字占 **2 个**等宽格，18 个汉字实际要 36 格，
        远超 18 格预算；再加上 `{:>7,}` 计数与 14 格条形，整行轻易超出列宽一倍
        以上，QLabel 一换行，计数和条形就与下一条目重叠（用户截图实锤）。
        现在按 `QFontMetrics.horizontalAdvance` 量**真实像素**，逐字裁到预算内，
        并用空格把计数列对齐；每个条目严格一行。

        v1.40.10（反馈 3 · 美化）：输出改为 **HTML**（`name` / `count` / `bar` 三段
        各包一层 `<span>`，条形段用传入的 `accent` 高亮色）。等宽对齐靠把 ASCII
        空格替换成 `&nbsp;`（Consolas 下 `&nbsp;` 与空格同宽，像素对齐不破）；
        名字里的 `& < >` 先转义避免打乱 HTML。调用方传 `accent=self.s.accent()`
        让条形跟随用户当前选的高亮色，切色后立即同步。
        """
        items = [(str(n), int(c)) for n, c in list(items)[:limit] if c is not None]
        if not items:
            return "—"
        top = max(c for _n, c in items) or 1
        fm = body.fontMetrics()
        adv = fm.horizontalAdvance

        # ---- 各段预算（像素）----
        col_w = body.width()
        if col_w < 60:                       # 还没布局（首帧）→ 按组框宽度估
            col_w = max(120, (body.parentWidget().width() or 700) // 5)
        cnt_txt = [f"{c:,}" for _n, c in items]
        cnt_px = max(adv(t) for t in cnt_txt) + 10      # 计数右对齐 + 左右留白
        blk = max(1, adv("█"))
        free = max(48, col_w - cnt_px - 8)               # 标签 + 条形 共用
        bar_cells = 0
        bar_px = 0
        if show_bar:
            bar_cells = max(4, min(10, int(free * 0.45) // blk))
            bar_px = adv("  ") + blk * bar_cells
        name_px = max(24, free - bar_px)

        def clip(s, budget):
            if adv(s) <= budget:
                return s
            ell = adv("…")
            out = ""
            for ch in s:
                if adv(out + ch) > budget - ell:
                    break
                out += ch
            return (out + "…") if out else "…"

        def htm(s):
            """转义 HTML 特殊字符，并把空格换成 &nbsp; 保等宽对齐。"""
            return (s.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;").replace(" ", "&nbsp;"))

        sp = max(1, adv(" "))
        lines = []
        for (name, c), ctext in zip(items, cnt_txt):
            lab = clip(name, name_px)
            lab += " " * int(max(0, name_px - adv(lab)) // sp)   # 像素级补空格
            # 计数列右对齐：**同样按像素补空格**。不能靠 `{:>N}` 的字符宽度 ——
            # CJK 回退下一个汉字占 2 格，按字符数补空格必然对不齐（探针实测）。
            gap = int(max(0, cnt_px - 10 - adv(ctext)) // sp)
            bar = ("  " + "█" * max(1, int(round(c / top * bar_cells)))) if bar_cells else ""
            # 三段上色：名字 tan / 计数浅金 / 条形 accent（&nbsp; 保对齐）
            line = ('<span style="color:#a1a1aa">%s</span>'
                    '<span style="color:#a1a1aa">%s%s</span>'
                    '<span style="color:%s">%s</span>') % (
                        htm(lab), "&nbsp;" * gap, htm(ctext), accent, htm(bar))
            lines.append(line)
        # 悬停给完整名字（正文是裁过的，tooltip 里看全名）
        full = "\n".join(f"{n}  {c:,}" for n, c in items)
        body.setToolTip(full)
        return "<br>".join(lines)

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
        hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        self.ai_state.setStyleSheet("color:#71717a;font-size:11px;")
        g1v.addWidget(self.ai_state)
        # v1.24.1（反馈 2）：按钮留引用 —— 检测期间要置灰并改文案，让「点了有反应」看得见
        self.ai_test = QPushButton("检测本地 AI 引擎")
        self.ai_test.setObjectName("Ghost")
        self.ai_test.setToolTip(f"探测 {rec_mod.OLLAMA_HOST} 上是否有可用的 Ollama（纯本地）")
        self.ai_test.clicked.connect(self._refresh_ai_state)
        g1v.addWidget(self.ai_test, alignment=Qt.AlignLeft)

        # v1.35.0（需求 1）：调用哪个模型、怎样自动拉起 Ollama，统一挪到
        # 「基础工具 → 引擎设置」页 —— 这里只留「选哪个算法 + 本地引擎是否可用」，
        # 跟「重复检测 / 演员检测 / 图像检测」的检测方式分组保持一致。
        g1_note = QLabel(rich(
            "AI 智能算法要用到的**本地模型**与**自动拉起 Ollama** 的开关，"
            "都放在左侧「基础工具 → <b>引擎设置</b>」页里统一管理。"))
        g1_note.setWordWrap(True)
        g1_note.setStyleSheet("color:#a1a1aa;font-size:11px;")
        g1v.addWidget(g1_note)
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
        self.sl_div.setFixedHeight(24)      # v2.0.1：同「窗口透明度」—— 18px 圆球要完整
        self.sl_div.setRange(0, 90)
        self.sl_div.setValue(int(float(self.s.recommend.get("diversity", 0.5)) * 100))
        self.sl_div.setFixedWidth(180)
        self.sl_div.setToolTip("越大越不容易一整屏都是同一系列 / 同一演员的作品")
        self.sl_div.valueChanged.connect(self._save_smart_prefs)
        row.addWidget(self.sl_div)
        self.lb_div = QLabel("—")
        self.lb_div.setStyleSheet("color:#71717a;font-size:11px;")
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
        self.lb_hist.setStyleSheet("color:#71717a;font-size:11px;")
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

        # v1.36.0（需求 2）：引导向量「中文自动翻译成日文再模糊匹配」。
        # 用户大概率敲中文，而库里的标签 / 艺人名是日文原文 —— 打开后输入词会先翻成
        # 日文候选，再各跑一遍 `resolve_guide_tokens_fuzzy`，结果**并进**原有命中里。
        self.ck_guide_ja = QCheckBox("引导向量：输入中文时自动翻译成日文再模糊匹配")
        self.ck_guide_ja.setToolTip(
            "库里的标签 / 艺人名大多是日文原文，而引导输入框里通常敲的是中文。\n"
            "打开后：输入「轮奸」会额外按「輪姦」匹配；输入「三上悠亚」会额外按「三上悠亜」匹配。\n"
            "译文命中与原本命中的结果会合并 —— 只增不减，多出来的引导项可以逐条点 × 移除。")
        self.ck_guide_ja.setChecked(bool(self.s.recommend.get("guide_ja_translate", False)))
        self.ck_guide_ja.toggled.connect(self._save_smart_prefs)
        g2v.addWidget(self.ck_guide_ja)
        g2_hint = QLabel(rich(
            "翻译是**纯离线**的「术语表 + 字形对照（简体 → 日本新字体）」，毫秒级完成、不出网。\n"
            "字形类（三上悠亚 → 三上悠亜、桥本有菜 → 橋本有菜）走逐字对照；"
            "词义类（中出 → 中出し、护士 → ナース、捆绑 → 緊縛）走内置术语表。"))
        g2_hint.setWordWrap(True)
        g2_hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        g2v.addWidget(g2_hint)
        v.addWidget(g2)

        g3 = QGroupBox("向量编辑")
        g3v = QVBoxLayout(g3)
        h3 = QLabel("偏好向量的每一项都能手动调权重：加强 / 减弱 / 屏蔽 / 软排斥。"
                    "这是从 nfo_profiler 的同名功能借鉴来的。")
        h3.setWordWrap(True)
        h3.setStyleSheet("color:#a1a1aa;font-size:11px;")
        g3v.addWidget(h3)
        self.vec_count = QLabel("—")
        self.vec_count.setStyleSheet("color:#71717a;font-size:11px;")
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

    # ---------- AI 引擎设置（v1.35.0 需求 1） ----------
    def _build_aiengine(self):
        """「基础工具 → 引擎设置」页：统一管理**调用哪个本地模型**与
        **自动拉起 Ollama**。

        v1.35.0（需求 1）：原来「调用模型 / 读取本机模型 / 下拉 / 怎么填」这些
        具体设置堆在「智能推荐」页的「推荐算法」组里，和「重复检测 / 演员检测 /
        图像检测」那套只放单选 + 状态 + 检测按钮的「检测方式」分组风格不一致。
        现在「智能推荐」页只留算法单选（同检测方式分组），模型相关全部搬到这里，
        让 AI 引擎配置有一个集中的去处。
        """
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(14)

        g1 = QGroupBox("本地 AI 引擎")
        g1v = QVBoxLayout(g1)
        hint = QLabel(rich(
            "AI 智能算法会用到的本地模型（Ollama，127.0.0.1:11434，纯离线、不出网）。\n"
            "留空 = 自动使用本机第一个已装模型；填了但本机没装则自动降级为内置联想。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        g1v.addWidget(hint)

        self.ae_state = QLabel("—")
        self.ae_state.setWordWrap(True)
        self.ae_state.setStyleSheet("color:#71717a;font-size:11px;")
        g1v.addWidget(self.ae_state)
        self.ae_test = QPushButton("检测本地 AI 引擎")
        self.ae_test.setObjectName("Ghost")
        self.ae_test.setToolTip(f"探测 {rec_mod.OLLAMA_HOST} 上是否有可用的 Ollama（纯本地）")
        self.ae_test.clicked.connect(self._refresh_ae_state)
        g1v.addWidget(self.ae_test, alignment=Qt.AlignLeft)

        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        mrow.addWidget(QLabel("调用模型"))
        self.ae_ed_model = QLineEdit()
        self.ae_ed_model.setPlaceholderText("留空 = 自动使用本机第一个模型")
        self.ae_ed_model.setToolTip(
            "填 Ollama 里的模型名（就是 `ollama list` 第一列那个名字，带标签）。\n"
            "例：qwen2.5:7b / llama3.1:8b / qwen3:4b / muse-glimmer:latest")
        self.ae_ed_model.setText(str(self.s.recommend.get("ai_model") or ""))
        self.ae_ed_model.editingFinished.connect(self._on_ae_model_edited)
        mrow.addWidget(self.ae_ed_model, 1)
        self.ae_btn_models = QPushButton("读取本机模型")
        self.ae_btn_models.setObjectName("Ghost")
        self.ae_btn_models.setToolTip("读取本机 Ollama 的模型清单（等价于命令行 `ollama list`）")
        self.ae_btn_models.clicked.connect(self._load_ae_models)
        mrow.addWidget(self.ae_btn_models)
        g1v.addLayout(mrow)

        self.ae_cb_model = QComboBox()
        self.ae_cb_model.setToolTip("读取到的本机模型；选一个即自动填入上面的输入框")
        self.ae_cb_model.addItem("（还没读取 —— 点右边「读取本机模型」）", "")
        self.ae_cb_model.currentIndexChanged.connect(self._pick_ae_model)
        g1v.addWidget(self.ae_cb_model)

        mhint = QLabel(rich(
            "**怎么填**：先启动 Ollama，然后在命令行执行 `ollama list` 查看已经安装的模型，"
            "把第一列的完整名字填进上面的输入框（或点「读取本机模型」后从下拉选）。\n"
            "**输入示例**：qwen2.5:7b　/　llama3.1:8b　/　qwen3:4b　/　"
            "gemma3:12b　/　muse-glimmer:latest　（冒号和标签都要带上）。\n"
            "留空 = 自动使用本机第一个模型；填了但本机没装会自动降级为内置联想。"))
        mhint.setWordWrap(True)
        mhint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        g1v.addWidget(mhint)
        v.addWidget(g1)

        g2 = QGroupBox("自动拉起 Ollama")
        g2v = QVBoxLayout(g2)
        self.ae_autostart = QCheckBox("开机时自动拉起 Ollama（powershell 执行 `ollama serve`）")
        self.ae_autostart.setChecked(bool(self.s.recommend.get("auto_start_ollama", False)))
        self.ae_autostart.setToolTip(
            "打开（默认关）：软件启动时自动用 powershell 后台拉起本机 Ollama 服务；\n"
            "仅当本机没运行时才尝试，已运行则不重复拉起；没装 Ollama 时静默跳过。")
        self.ae_autostart.toggled.connect(self._save_aiengine_prefs)
        g2v.addWidget(self.ae_autostart)

        self.ae_launch = QPushButton("立即启动")
        self.ae_launch.setObjectName("Primary")
        self.ae_launch.setToolTip("现在就用 powershell 拉起本机 Ollama（= `ollama serve`）")
        self.ae_launch.clicked.connect(self._launch_ollama)
        g2v.addWidget(self.ae_launch, alignment=Qt.AlignLeft)

        self.ae_launch_state = QLabel("—")
        self.ae_launch_state.setWordWrap(True)
        self.ae_launch_state.setStyleSheet("color:#71717a;font-size:11px;")
        g2v.addWidget(self.ae_launch_state)
        v.addWidget(g2)

        v.addStretch(1)
        QTimer.singleShot(0, self._refresh_ae_state)
        return page

    def _refresh_ae_state(self):
        """探测本机 Ollama，结果写进 引擎设置页的 ae_state（同 _refresh_ai_state 口径）。"""
        w = getattr(self, "_ae_probe_worker", None)
        if w is not None and w.isRunning():
            return
        self.ae_state.setStyleSheet("color:#8fc0ff;font-size:11px;")
        self.ae_state.setText(
            f"正在检测本地 AI 引擎…　探测 {rec_mod.OLLAMA_HOST}（最多等 1 秒）")
        self.ae_test.setEnabled(False)
        self.ae_test.setText("检测中…")
        self._ae_probe_worker = AiProbeWorker()
        self._ae_probe_worker.done.connect(self._on_ae_probe)
        self._ae_probe_worker.start()

    def _on_ae_probe(self, st):
        self.ae_test.setEnabled(True)
        self.ae_test.setText("检测本地 AI 引擎")
        st = st or {}
        eng = st.get("engine")
        ts = QTime.currentTime().toString("HH:mm:ss")
        if eng == "ollama":
            head = f"✅ 检测完成（{ts}）—— 引擎：<b>{html_esc(st.get('label'))}</b>"
            color = "#45d483"
        elif eng == "error":
            head = f"❌ 检测失败（{ts}）—— 引擎：<b>未知</b>"
            color = "#f87171"
        else:
            head = f"⚠ 检测完成（{ts}）—— 未检测到本地 Ollama，当前引擎：<b>" \
                   f"{html_esc(st.get('label'))}</b>"
            color = "#8fc0ff"
        self.ae_state.setStyleSheet(f"color:{color};font-size:11px;")
        self.ae_state.setText(f"{head}<br>{html_esc(st.get('detail'))}")
        applog.log(f"[AI 引擎设置·检测] engine={eng} at {ts}")

    def _save_aiengine_prefs(self, *_):
        self.s.set_recommend(
            ai_model=self.ae_ed_model.text().strip() if getattr(self, "ae_ed_model", None) else "",
            auto_start_ollama=bool(getattr(self, "ae_autostart", None)
                                   and self.ae_autostart.isChecked()))

    def _on_ae_model_edited(self):
        """模型输入框改完（回车 / 失焦）：落盘 + 重新检测，让页面结论立刻反映新模型。"""
        self._save_aiengine_prefs()
        self._refresh_ae_state()

    def _load_ae_models(self):
        w = getattr(self, "_ae_models_worker", None)
        if w is not None and w.isRunning():
            return
        self.ae_btn_models.setEnabled(False)
        self.ae_btn_models.setText("读取中…")
        self._ae_models_worker = AiModelsWorker()
        self._ae_models_worker.done.connect(self._on_ae_models)
        self._ae_models_worker.start()

    def _on_ae_models(self, names):
        self.ae_btn_models.setEnabled(True)
        self.ae_btn_models.setText("读取本机模型")
        names = [str(x) for x in (names or []) if x]
        self.ae_cb_model.blockSignals(True)
        self.ae_cb_model.clear()
        if not names:
            self.ae_cb_model.addItem("（没读到模型：Ollama 没启动，或还没 pull 过任何模型）", "")
        else:
            self.ae_cb_model.addItem(f"本机已装 {len(names)} 个模型（点选即填入）", "")
            for nm in names:
                self.ae_cb_model.addItem(nm, nm)
        self.ae_cb_model.setCurrentIndex(0)
        self.ae_cb_model.blockSignals(False)
        self._refresh_ae_state()

    def _pick_ae_model(self, idx):
        nm = self.ae_cb_model.itemData(idx) if idx is not None and idx >= 0 else None
        if not nm:
            return
        self.ae_ed_model.setText(str(nm))
        self._on_ae_model_edited()

    def _launch_ollama(self):
        """立即用 powershell 拉起本机 Ollama（按钮触发）。"""
        w = getattr(self, "_ae_launch_worker", None)
        if w is not None and w.isRunning():
            return
        self.ae_launch.setEnabled(False)
        self.ae_launch.setText("拉起中…")
        self.ae_launch_state.setStyleSheet("color:#8fc0ff;font-size:11px;")
        self.ae_launch_state.setText("正在用 powershell 拉起 Ollama 服务…（最多等 20 秒）")
        self._ae_launch_worker = OllamaLaunchWorker()
        self._ae_launch_worker.done.connect(self._on_ollama_launch)
        self._ae_launch_worker.start()

    def _on_ollama_launch(self, ok, msg):
        self.ae_launch.setEnabled(True)
        self.ae_launch.setText("立即启动")
        color = "#45d483" if ok else "#f5a524"
        self.ae_launch_state.setStyleSheet(f"color:{color};font-size:11px;")
        self.ae_launch_state.setText(("✅ " if ok else "⚠ ") + msg)
        applog.log(f"[AI 引擎设置·拉起] ok={ok} {msg}")
        # 拉起成功后自动读取本机模型，把下拉填满
        if ok:
            self._load_ae_models()
        else:
            self._refresh_ae_state()

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
        self.ai_state.setStyleSheet("color:#8fc0ff;font-size:11px;")
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
            color = "#45d483"
        elif eng == "error":
            head = f"❌ 检测失败（{ts}）—— 引擎：<b>未知</b>"
            color = "#f87171"
        else:
            head = f"⚠ 检测完成（{ts}）—— 未检测到本地 Ollama，当前引擎：<b>" \
                   f"{html_esc(st.get('label'))}</b>"
            color = "#8fc0ff"
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
        # v1.36.0（需求 2）：引导向量「中文 → 日文」开关（同样 getattr 兜底，
        # 避免日后有人把构造顺序挪到信号连接之后就直接崩）。
        ck_ja = getattr(self, "ck_guide_ja", None)
        if ck_ja is not None:
            kw["guide_ja_translate"] = bool(ck_ja.isChecked())
        self.s.set_recommend(**kw)
        self._refresh_hist_label()

    # ---------- v1.35.0（需求 1）：模型选择已移至「引擎设置」页（_build_aiengine） ----------

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
        hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
                                "用哪个模型跟「基础工具 → 引擎设置」页共用同一项设置。")
        self.dd_ai_lbl.setWordWrap(True)
        self.dd_ai_lbl.setStyleSheet("color:#71717a;font-size:11px;")
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
        self.dd_status.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        tip7.setStyleSheet("color:#71717a;font-size:11px;")
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
            label.setStyleSheet("color:#f5a524;font-size:11px;")
            return
        if ok:
            label.setText("✓ " + note)
            label.setStyleSheet("color:#45d483;font-size:11px;")
        else:
            label.setText("✗ " + note)
            label.setStyleSheet("color:#f5a524;font-size:11px;")

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
            + (f"<br><span style='color:#71717a;'>AI 复核：{s['ai_note']}</span>"
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
                top.setForeground(0, QBrush(QColor("#f5a524")))
            if show_ai and g.ai:
                top.setForeground(C_AI, QBrush(QColor(
                    "#45d483" if (g.ai.get("advice") or "") == "全部保留" else "#f5a524")))
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
                    child.setForeground(1, QBrush(QColor("#f87171")))
                top.addChild(child)
            self.dd_tree.addTopLevelItem(top)
        if report.multipart:
            head = QTreeWidgetItem([f"同目录分片（{len(report.multipart)} 组，未计入重复）"]
                                   + [""] * (len(heads) - 1))
            head.setForeground(0, QBrush(QColor("#71717a")))
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
        g1 = QGroupBox("元数据导出 / 导入")
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
        h1.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        self.data_hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        g1v.addWidget(self.data_hint)
        v.addWidget(g1)

        # ---------- v1.43.0（需求 2）：偏好管理 ----------
        # 与上面的「元数据导出 / 导入」是两种东西：上面搬的是**索引与资料**（体积大、
        # 按 id 走），这里只搬**个人偏好**（体积小、按**番号 / 姓名**走），所以放进
        # 单独一组，文案也把「换路径 / 换电脑 / nfo 被覆盖后恢复」说清楚。
        gp = QGroupBox("偏好管理（按番号备份 / 恢复个人偏好）")
        gpv = QVBoxLayout(gp)
        gpv.setSpacing(8)
        _ph = QLabel(rich(
            "只备份**你的偏好**，与文件路径无关：影片收藏 / 观看次数 / 用户评分"
            "（同时回写 nfo 的 `<userrating>` —— nfo 被重新刮削覆盖也能恢复），"
            "以及演员库、导演库里**收藏与置顶**的人。\n"
            "换目录、换电脑、重装系统后导入即可找回；备份是单个 JSON，跨版本可读。"))
        _ph.setWordWrap(True)
        _ph.setStyleSheet("color:#a1a1aa;font-size:11px;")
        gpv.addWidget(_ph)
        pr = QWidget()
        prh = QHBoxLayout(pr)
        prh.setContentsMargins(0, 0, 0, 0)
        prh.setSpacing(8)
        # v1.45.5（反馈 4）：**勾选要导出的内容**（原来只有"范围"下拉，不能自由组合）
        self.pref_inc = {}
        _inc_row = QWidget()
        _il = QHBoxLayout(_inc_row)
        _il.setContentsMargins(0, 0, 0, 0)
        _il.setSpacing(10)
        _il.addWidget(QLabel("导出内容"))
        for _k, _lab in prefs_mod.INCLUDE_ITEMS:
            _cb = QCheckBox(_lab)
            _cb.setChecked(True)
            self.pref_inc[_k] = _cb
            _il.addWidget(_cb)
        _il.addStretch(1)
        prh.addWidget(_inc_row)
        pex = QPushButton("导出偏好…")
        pex.setObjectName("Primary")
        pex.setToolTip(rich("把收藏 / 观看记录 / 用户评分 / 人物收藏与置顶导出为单个 JSON"))
        pex.clicked.connect(self._export_prefs)
        pim = QPushButton("导入偏好…")
        pim.setObjectName("Ghost")
        pim.setToolTip(rich("按**番号**与**姓名**合并回当前索引；不删数据、不覆盖资料字段"))
        pim.clicked.connect(self._import_prefs)
        self.pref_ex, self.pref_im = pex, pim
        # v1.46.12：跑到一半可以停（协作式中止，已处理的部分照常提交）
        self.pref_stop = compact_button("停止", 56, 30, "停止当前的导入 / 导出")
        self.pref_stop.setVisible(False)
        self.pref_stop.clicked.connect(self._stop_prefs)
        prh.addWidget(pex)
        prh.addWidget(pim)
        prh.addWidget(self.pref_stop)
        prh.addStretch(1)
        gpv.addWidget(pr)

        # ---------- v1.46.12（反馈）：导入 / 导出的进度 ----------
        # 原来这两个动作同步跑在 GUI 线程、全程不泵消息，一次导入实测 7.09s，
        # Windows 5 秒就判「未响应」，用户既看不到进度也不知道成功了几条。
        # 现在进度行独立成一条（不定长 → 定量），并显示**当前阶段 + 已完成条数**。
        prow = QWidget()
        prl = QHBoxLayout(prow)
        prl.setContentsMargins(0, 0, 0, 0)
        prl.setSpacing(8)
        self.pref_bar = QProgressBar()
        self.pref_bar.setTextVisible(False)
        self.pref_bar.setFixedHeight(6)
        self.pref_bar.setRange(0, 0)
        self.pref_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.pref_status = QLabel("")
        self.pref_status.setStyleSheet("color:#d4d4d8;font-size:11px;")   # 进度文字，比说明文字亮一档
        self.pref_status.setMinimumWidth(0)
        prl.addWidget(self.pref_bar, 1)
        prl.addWidget(self.pref_status, 0)
        prow.setVisible(False)
        self.pref_prog_row = prow
        gpv.addWidget(prow)

        self.pref_hint = QLabel("尚未导出 / 导入过偏好。")
        self.pref_hint.setWordWrap(True)
        self.pref_hint.setStyleSheet("color:#71717a;font-size:11px;")
        gpv.addWidget(self.pref_hint)
        v.addWidget(gp)

        # ---------- v1.44.0（需求 4）：维护与重置（危险操作） ----------
        gd = QGroupBox("维护与重置（危险操作，执行前需二次确认）")
        gdv = QVBoxLayout(gd)
        gdv.setSpacing(8)
        dhint = QLabel(rich(
            "下面四项都会**改动本地数据**，每一项都要**连点两次确认**。"
            "执行前建议先用上面的「导出所选分类」把收藏 / 评分备份一份。"))
        dhint.setWordWrap(True)
        dhint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        gdv.addWidget(dhint)
        for _label, _tip, _slot in (
                ("清理缓存",
                 "删除演员头像缓存与 gfriends 索引缓存（不动索引库、不动设置）",
                 self._clean_cache),
                ("删除数据库",
                 "删除媒体索引库（保留设置与媒体库配置；重启后是空库）",
                 self._drop_database),
                ("恢复默认设置",
                 "设置恢复出厂默认（清空媒体库列表与全部偏好；不动索引库）",
                 self._reset_settings),
                ("初始化软件",
                 "索引库 + 缓存 + 设置全部清空，等同于全新安装（不可撤销）",
                 self._factory_reset)):
            _r = QWidget()
            _rh = QHBoxLayout(_r)
            _rh.setContentsMargins(0, 0, 0, 0)
            _rh.setSpacing(8)
            _b = QPushButton(_label)
            _b.setObjectName("Ghost")
            _b.setToolTip(rich(_tip))
            _b.clicked.connect(_slot)
            _lab = QLabel(_tip)
            _lab.setWordWrap(True)
            _lab.setStyleSheet("color:#a1a1aa;font-size:11px;")
            _rh.addWidget(_b, 0)
            _rh.addWidget(_lab, 1)
            gdv.addWidget(_r)
        v.addWidget(gd)

        v.addStretch(1)
        return page

    def _build_logs(self):
        """v1.44.0（需求 4）：日志中心 —— 从「数据与日志」拆出来的独立页。"""
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(14)

        # ---------- v1.45.5（反馈 3）：刮削诊断（从"诊断与可观测"提前落在这里） ----------
        gd = QGroupBox("刮削诊断（各数据源 Cookie 与最近一次测试）")
        gdv = QVBoxLayout(gd)
        gdv.setSpacing(6)
        dhi = QLabel("显示每个数据源的通行 Cookie 是否已获取，以及最近一次「测试 / Cookie 存活」的结果。"
                     "点「刷新」重读；真正的网络请求在「演员刮削」页发起。")
        dhi.setWordWrap(True)
        dhi.setStyleSheet("color:#a1a1aa;font-size:11px;")
        gdv.addWidget(dhi)
        self.diag_tbl = QTableWidget(0, 5)
        self.diag_tbl.setHorizontalHeaderLabels(["数据源", "Cookie", "最近结果", "耗时", "时间"])
        self.diag_tbl.verticalHeader().setVisible(False)
        self.diag_tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.diag_tbl.setSelectionMode(QAbstractItemView.NoSelection)
        self.diag_tbl.setFixedHeight(170)
        try:
            hh = self.diag_tbl.horizontalHeader()
            hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            hh.setSectionResizeMode(2, QHeaderView.Stretch)
            hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
            hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        except Exception:
            pass
        gdv.addWidget(self.diag_tbl)
        drow = QHBoxLayout()
        _dbtn = QPushButton("刷新诊断")
        _dbtn.setObjectName("Ghost")
        _dbtn.clicked.connect(self._refresh_diag)
        drow.addWidget(_dbtn)
        drow.addStretch(1)
        gdv.addLayout(drow)
        v.addWidget(gd)

        # 日志导出
        g2 = QGroupBox("运行日志")
        g2v = QVBoxLayout(g2)
        h2 = QLabel("软件会把全部运行记录（启动 / 扫描 / 刮削 / 报错等）写入日志文件。"
                    "出现 BUG 时点「导出日志」把压缩包发给开发者即可快速定位。")
        h2.setWordWrap(True)
        h2.setStyleSheet("color:#a1a1aa;font-size:11px;")
        g2v.addWidget(h2)
        self.log_path_lbl = QLabel("日志位置：" + applog.log_path())
        self.log_path_lbl.setWordWrap(True)
        self.log_path_lbl.setStyleSheet("color:#71717a;font-size:11px;")
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
        g3hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        g3v.addWidget(g3hint)
        # v1.45.5（反馈 3）：过滤与关键词搜索
        _frow = QWidget()
        _fl = QHBoxLayout(_frow)
        _fl.setContentsMargins(0, 0, 0, 0)
        _fl.setSpacing(8)
        self.log_kw = QLineEdit()
        self.log_kw.setPlaceholderText("搜索关键词（番号 / 演员 / 源…）")
        self.log_kw.setFixedWidth(260)
        self.log_kw.textChanged.connect(lambda *_: self._refresh_log())
        _fl.addWidget(self.log_kw)
        self.log_err_only = QCheckBox("只看 WARN / ERROR")
        self.log_err_only.toggled.connect(lambda *_: self._refresh_log())
        _fl.addWidget(self.log_err_only)
        _fl.addStretch(1)
        g3v.addWidget(_frow)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._log_view.setStyleSheet(LOG_BOX_STYLE)
        g3v.addWidget(self._log_view, 1)
        self._log_path_lbl2 = QLabel("日志文件：" + applog.log_path())
        self._log_path_lbl2.setWordWrap(True)
        self._log_path_lbl2.setStyleSheet("color:#71717a;font-size:11px;")
        g3v.addWidget(self._log_path_lbl2)
        v.addWidget(g3)

        # 启动实时刷新定时器（窗口显示时开始，关闭时停止）
        self._rt_timer = QTimer(self)
        self._rt_timer.setInterval(1500)
        self._rt_timer.timeout.connect(self._refresh_log)
        self._refresh_log()   # 立即填一次，避免打开时空白

        v.addStretch(1)
        return page

    # ---------- v1.44.0（需求 4）：维护与重置（危险操作，二次确认） ----------
    def _confirm_twice(self, title, first, second):
        """两次确认；第二次默认按钮是「否」（回车不会误执行）。"""
        if QMessageBox.question(self, title, rich(first)) != QMessageBox.Yes:
            return False
        return QMessageBox.question(
            self, title + "（再次确认）", rich(second),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    @staticmethod
    def _app_root():
        return applog.base_dir()

    @staticmethod
    def _dir_size(path):
        total = 0
        for dp, _dn, fn in os.walk(path):
            for f in fn:
                try:
                    total += os.path.getsize(os.path.join(dp, f))
                except Exception:
                    pass
        return total

    def _clean_cache(self):
        if not self._confirm_twice(
                "清理缓存",
                "将删除 `cache/` 下的**演员头像缓存**与 gfriends 索引缓存。\n"
                "索引库、设置、媒体库都不受影响；头像可在下次刮削时重新下载。",
                "再确认一次：确定要清理缓存吗？"):
            return
        cache = os.path.join(self._app_root(), "cache")
        n, size = 0, 0
        try:
            if os.path.isdir(cache):
                for name in os.listdir(cache):
                    p = os.path.join(cache, name)
                    try:
                        if os.path.isdir(p):
                            size += self._dir_size(p)
                            shutil.rmtree(p)
                        else:
                            size += os.path.getsize(p)
                            os.remove(p)
                        n += 1
                    except Exception as e:
                        applog.log(f"清理缓存：跳过 {name}（{e}）", "warn")
        except Exception as e:
            applog.log(f"清理缓存失败：{e}", "error")
            QMessageBox.warning(self, "清理失败", str(e))
            return
        applog.log(f"清理缓存：删除 {n} 项，约 {size / 1048576:.1f} MB")
        QMessageBox.information(self, "清理完成",
                                f"已删除 {n} 项，约释放 {size / 1048576:.1f} MB。")

    def _drop_database(self):
        if not self._confirm_twice(
                "删除数据库",
                "将**删除媒体索引库**（`index_data/media_center.db`）。\n"
                "媒体文件、设置、媒体库配置都不动；重启后索引为空，需要重新扫描。",
                "再确认一次：删除后只能靠重新扫描恢复，确定继续？"):
            return
        try:
            db.close_all()
            p = db.db_path()
            for f in (p, p + "-wal", p + "-shm"):
                if os.path.exists(f):
                    os.remove(f)
        except Exception as e:
            applog.log(f"删除数据库失败：{e}", "error")
            QMessageBox.warning(self, "删除失败", str(e))
            return
        applog.log("删除数据库：已完成，等待重启")
        QMessageBox.information(self, "已删除",
                                "索引库已删除。\n请重启软件，并在「媒体库」里重新扫描。")

    def _reset_settings(self):
        if not self._confirm_twice(
                "恢复默认设置",
                "将把**设置恢复出厂默认**：媒体库列表、导航、外观、刮削偏好等全部重置；"
                "索引库与媒体文件不受影响。",
                "再确认一次：媒体库列表会被清空（索引还在，但侧栏看不到库），确定继续？"):
            return
        try:
            sp = cfg.config_path()
            if os.path.exists(sp):
                shutil.copy(sp, sp + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
            s = cfg.get_settings()
            s.__init__()             # 回到全部默认值
            s.save()
        except Exception as e:
            applog.log(f"恢复默认设置失败：{e}", "error")
            QMessageBox.warning(self, "恢复失败", str(e))
            return
        applog.log("恢复默认设置：完成")
        QMessageBox.information(self, "已恢复", "设置已恢复默认，请重启软件生效。")

    def _factory_reset(self):
        if not self._confirm_twice(
                "初始化软件",
                "**索引库 + 缓存 + 设置**全部清空，等同全新安装；媒体文件不会被动。",
                "再确认一次：此操作不可撤销（设置会先自动备份为 .bak），确定继续？"):
            return
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            sp = cfg.config_path()
            if os.path.exists(sp):
                shutil.copy(sp, sp + ".bak-" + ts)
            db.close_all()
            p = db.db_path()
            for f in (p, p + "-wal", p + "-shm"):
                if os.path.exists(f):
                    os.remove(f)
            cache = os.path.join(self._app_root(), "cache")
            if os.path.isdir(cache):
                shutil.rmtree(cache)
            s = cfg.get_settings()
            s.__init__()
            s.save()
        except Exception as e:
            applog.log(f"初始化软件失败：{e}", "error")
            QMessageBox.warning(self, "初始化失败", str(e))
            return
        applog.log("初始化软件：索引库 / 缓存 / 设置已清空")
        QMessageBox.information(self, "已初始化",
                                "软件已初始化（索引库、缓存、设置均已清空）。\n请重启软件。")

    def _refresh_diag(self):
        """v1.45.5：把 scraper.diag_snapshot() 画进「刮削诊断」表。"""
        try:
            snap = scraper_mod.diag_snapshot()
        except Exception as e:
            applog.log(f"读取刮削诊断失败：{e}", "error")
            return
        tbl = getattr(self, "diag_tbl", None)
        if tbl is None:
            return
        tbl.setRowCount(0)
        for key, info in snap.items():
            r = tbl.rowCount()
            tbl.insertRow(r)
            name = scraper_mod.SOURCE_NAMES.get(key, key)
            ck = "✓ 已获取" if info.get("cookie_ok") else "— 未获取"
            last = info.get("last") or {}
            res = ("可用" if last.get("ok") else "失败") if last else "未测试"
            msg = (last.get("msg") or "")[:60]
            cells = [name, ck, (res + ("：" + msg if msg else "")) if last else res,
                     ("%d ms" % last["ms"]) if last else "—", last.get("at") or "—"]
            for c, txt in enumerate(cells):
                it = QTableWidgetItem(str(txt))
                if c == 1:
                    it.setForeground(QColor("#45d483" if info.get("cookie_ok") else "#a1a1aa"))
                elif c == 2 and last:
                    it.setForeground(QColor("#45d483" if last.get("ok") else "#f87171"))
                tbl.setItem(r, c, it)

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
            _kw = (self.log_kw.text() or "").strip().lower() if hasattr(self, "log_kw") else ""
            if _kw or (hasattr(self, "log_err_only") and self.log_err_only.isChecked()):
                _lines = text.splitlines()
                if hasattr(self, "log_err_only") and self.log_err_only.isChecked():
                    _lines = [l for l in _lines if any(t in l for t in
                              ("[ERROR]", "[WARN]", "Traceback", "未捕获异常"))]
                if _kw:
                    _lines = [l for l in _lines if _kw in l.lower()]
                text = chr(10).join(_lines[-400:]) or "（没有匹配的日志行）"
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

    # ---------- v1.43.0（需求 2）：偏好管理 ----------
    # v1.46.12：两个动作都改成「后台线程 + 真进度」，见 PrefsWorker 的注释。
    def _export_prefs(self):
        if self._prefs_running():
            return
        default = os.path.join(os.path.expanduser("~"), prefs_mod.prefs_export_name())
        path, _ = QFileDialog.getSaveFileName(self, "导出偏好", default,
                                              "偏好备份 (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        _inc = [k for k, cb in getattr(self, "pref_inc", {}).items() if cb.isChecked()]
        if not _inc:
            QMessageBox.information(self, "提示", "请至少勾选一项导出内容。")
            return
        self._prefs_run("export", path, _inc)

    def _import_prefs(self):
        if self._prefs_running():
            return
        path, _ = QFileDialog.getOpenFileName(self, "导入偏好", "",
                                              "偏好备份 (*.json)")
        if not path:
            return
        if QMessageBox.question(
                self, "导入偏好",
                rich("会把备份里的**收藏 / 观看次数 / 用户评分**按番号合并回当前索引，"
                     "用户评分同时写回 nfo。\n"
                     "**不删除任何数据、不覆盖资料字段**，可反复执行。\n\n是否继续？")
        ) != QMessageBox.Yes:
            return
        self._prefs_run("import", path)

    # ---- 进度 / 生命周期 ----
    def _prefs_running(self) -> bool:
        w = getattr(self, "_prefs_worker", None)
        try:
            return w is not None and w.isRunning()
        except RuntimeError:               # C++ 侧已销毁
            return False

    def _prefs_run(self, mode, path, include=None):
        """起后台线程并进入忙碌态（按钮禁用 + 进度条 + 阶段文字）。"""
        self._prefs_mode = mode
        self._prefs_path = path
        self.pref_ex.setEnabled(False)
        self.pref_im.setEnabled(False)
        self.pref_stop.setVisible(True)
        self.pref_stop.setEnabled(True)
        self.pref_prog_row.setVisible(True)
        self.pref_bar.setRange(0, 0)       # 先不定长，收到 total 再转定量
        self.pref_bar.setValue(0)
        _t = "正在导出偏好…" if mode == "export" else "正在导入偏好…"
        self.pref_status.setText(_t)
        self.pref_hint.setText(("导出中：" if mode == "export" else "导入中：") + path)
        w = PrefsWorker(mode, path, include, parent=self)
        w.progress.connect(self._on_prefs_progress)
        w.done.connect(self._on_prefs_done)
        self._prefs_worker = w
        w.start()

    def _stop_prefs(self):
        """协作式停止：真正的停止点在 prefs 的每次进度回调里。"""
        w = getattr(self, "_prefs_worker", None)
        if w is None or not self._prefs_running():
            return
        w.request_stop()
        self.pref_stop.setEnabled(False)
        self.pref_status.setText("正在停止（等当前这一批处理完）…")

    def _on_prefs_progress(self, done, total, label):
        if total > 0:
            if self.pref_bar.maximum() != total or self.pref_bar.minimum() != 0:
                self.pref_bar.setRange(0, total)
            self.pref_bar.setValue(max(0, min(int(done), int(total))))
        elif self.pref_bar.maximum() != 0:
            self.pref_bar.setRange(0, 0)   # total 未知 → 不定长
        self.pref_status.setText(label)

    def _prefs_busy_end(self):
        self.pref_ex.setEnabled(True)
        self.pref_im.setEnabled(True)
        self.pref_stop.setVisible(False)
        self.pref_stop.setEnabled(True)
        self.pref_prog_row.setVisible(False)
        self.pref_bar.setRange(0, 1)
        self.pref_bar.setValue(0)

    def _on_prefs_done(self, r):
        mode = getattr(self, "_prefs_mode", "import")
        r = r if isinstance(r, dict) else {}
        who = "导出" if mode == "export" else "导入"
        if not r.get("ok"):
            self._prefs_busy_end()
            if r.get("cancelled"):
                applog.log(f"偏好{who}已取消")
                self.pref_hint.setText(f"已取消{who}（未改动任何数据 / 未生成文件）。")
            else:
                applog.log(f"偏好{who}失败：{r.get('error')}", "error")
                QMessageBox.warning(self, f"{who}失败", r.get("error") or "未知错误")
            return
        if mode == "import":
            # 刷新界面本身也要 1.4s（重建侧栏 + 首页）→ 先把「正在刷新」画出来
            self.pref_bar.setRange(0, 0)
            self.pref_status.setText("正在刷新界面…")
            # 带 context 的 singleShot：窗口在这 60ms 里被销毁也不会回落到已删除对象
            QTimer.singleShot(60, self, lambda: self._prefs_finish(mode, r))
        else:
            self._prefs_finish(mode, r)

    def _prefs_finish(self, mode, r):
        if mode == "import" and self.on_changed:
            try:
                self.on_changed()
            except Exception as e:
                applog.log(f"偏好导入后刷新界面失败：{type(e).__name__}: {e}", "error")
        self._prefs_busy_end()
        path = r.get("path") or getattr(self, "_prefs_path", "") or ""
        if mode == "export":
            applog.log(f"偏好导出：{path} 影片 {r['media']} 条、人物 {r['people']} 条")
            self.pref_hint.setText(
                f"最近导出：{path}（影片 {r['media']} 条 · 人物 {r['people']} 位）")
            extra = (f"\n\n（{r['no_code']} 条既无番号也无标题，已跳过）"
                     if r.get("no_code") else "")
            QMessageBox.information(
                self, "导出完成",
                f"已导出到：\n{path}\n\n"
                f"影片偏好 {r['media']} 条\n人物收藏 / 置顶 {r['people']} 位" + extra)
            return
        if r.get("cancelled"):
            applog.log(f"偏好导入已停止：影片命中 {r['media_ok']}、"
                       f"人物命中 {r['people_ok']}、nfo 写回 {r['nfo_written']}")
            self.pref_hint.setText(
                f"已停止导入（已处理的部分已保存）：影片命中 {r['media_ok']} · "
                f"人物 {r['people_ok']} · nfo 写回 {r['nfo_written']}")
            QMessageBox.information(
                self, "已停止导入",
                f"影片偏好已合并 {r['media_ok']} 条（未匹配 {r['media_miss']} 条）\n"
                f"人物收藏 / 置顶已合并 {r['people_ok']} 位\n"
                f"nfo 评分已写回 {r['nfo_written']} 个文件\n\n"
                "已处理的部分**已经保存**，备份文件没有被动过，可以随时再导入一次。")
            return
        applog.log(f"偏好导入：{path} 影片命中 {r['media_ok']}、"
                   f"人物命中 {r['people_ok']}、nfo 评分写入 {r['nfo_written']}")
        self.pref_hint.setText(
            f"最近导入：{path}（影片命中 {r['media_ok']} · 未匹配 {r['media_miss']} · "
            f"人物 {r['people_ok']} · nfo 写回 {r['nfo_written']}）")
        QMessageBox.information(
            self, "导入完成",
            f"影片偏好命中 {r['media_ok']} 条（未匹配 {r['media_miss']} 条）\n"
            f"人物收藏 / 置顶命中 {r['people_ok']} 位（未匹配 {r['people_miss']} 位）\n"
            f"nfo 评分写回 {r['nfo_written']} 个文件\n\n刷新界面即可看到结果。")

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
            empty.setStyleSheet("color:#71717a;font-size:11px;padding:6px 4px;")
            li.setSizeHint(QSize(empty.sizeHint().width(), LIB_ROW_H))
            self.lib_list.addItem(li)
            self.lib_list.setItemWidget(li, empty)
            self.lib_list.setFixedHeight(LIB_ROW_H + LIST_CHROME)
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
            # v1.46.15（反馈「压缩后这些按钮显示不全了」）：这三个按钮原来用裸
            # QPushButton + setFixedHeight(28)。全局 QSS 是 `QPushButton{padding:7px 14px}`，
            # 28px 高的框减掉上下各 7px 内边距后内容区只剩 12px，而一行「编辑」字要 17px
            # —— Qt 会把字形**上下各切掉约 3px**，看起来就是「按钮里的字显示不全」。
            # （sizeHint 实测 56×33，被 setFixedHeight(28) 硬压到 28，证据在此。）
            # 改走 ui_hero.compact_button()：它给按钮打 compact 属性，
            # QSS 里 `QPushButton[compact="1"]{padding:0 4px;}` 把内边距压成 0，
            # 内容区恢复 26px，字完整居中；宽高仍锁 56×28，行高不受影响。
            edit = compact_button("编辑", 56, 28, "修改这个媒体库的名称 / 类型 / 路径")
            edit.clicked.connect(lambda _c, L=lib: self._edit_library(L))
            scan = compact_button("扫描", 56, 28, "只扫描这一个媒体库（后台进行）")
            scan.clicked.connect(lambda _c, L=lib: self._scan_library(L))
            delete = compact_button("删除", 56, 28, "从配置里删掉这个媒体库（不动硬盘文件）")
            delete.clicked.connect(lambda _c, L=lib: self._del_library(L))
            for b in (edit, scan, delete):
                h.addWidget(b)
            # v1.14.0 反馈 6：行高用显式常量（原来 row.sizeHint() 量到的高度不足以
            # 容纳 28px 按钮 + 上下 4px 边距，按钮底部被切掉一截）
            li.setSizeHint(QSize(row.sizeHint().width(), LIB_ROW_H))
            self.lib_list.addItem(li)
            self.lib_list.setItemWidget(li, row)
        # 列表高度按条目数自适应（4 行以内全显，更多则滚动）
        self.lib_list.setFixedHeight(
            min(len(self.s.libraries), 4) * LIB_ROW_H + LIST_CHROME)

    def _scan_library(self, lib):
        self._scan_total = 1
        self._scan_done_n = 0
        self._set_lib_status(f"正在扫描「{lib['name']}」…（后台进行，可继续使用主界面）", "#66a9ff")
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
            self._set_lib_status("全部媒体库扫描完成。", "#45d483")
            return
        lib = self._scan_queue.pop(0)
        self._set_lib_status(
            f"正在扫描「{lib['name']}」…（{self._scan_done_n + 1}/{self._scan_total}，"
            f"后台进行，可继续使用主界面）", "#66a9ff")
        self._worker = ScanNamedWorker(lib)
        self._worker.done.connect(lambda c, n: (self._on_scan_done(c, n), self._scan_next()))
        self._worker.start()

    def _set_lib_status(self, text, color="#a1a1aa"):
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
            self._set_lib_status(f"「{name}」扫描出错：{counts['error']}", "#f87171")
        else:
            self._scan_done_n = getattr(self, "_scan_done_n", 0) + 1
            self._set_lib_status(
                f"「{name}」扫描完成：电影 {counts.get('movie', 0)} 部 / "
                f"剧集 {counts.get('tvshow', 0)} 部 / 分集 {counts.get('episode', 0)} 个",
                "#45d483")
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
        h1.setStyleSheet("color:#a1a1aa;font-size:11px;")
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
        self.lb_to_scope.setStyleSheet("color:#71717a;font-size:11px;")
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
        self.to_ai_state = QLabel("「AI 智能算法」会调用本地离线 AI（Ollama）；"
                                  "点下面的按钮可手动检测本机是否可用，"
                                  "用哪个模型跟「智能推荐」页共用同一项设置。")
        self.to_ai_state.setWordWrap(True)
        self.to_ai_state.setStyleSheet("color:#71717a;font-size:11px;")
        g2v.addWidget(self.to_ai_state)

        # v1.34.3（反馈 2）：显式「检测本地 AI 引擎」按钮 —— 与其它检测页一致。
        # 原先只在切到「AI 智能算法」时自动探测，用户想主动重测却没有入口。
        self.to_ai_btn = QPushButton("检测本地 AI 引擎")
        self.to_ai_btn.setObjectName("Ghost")
        self.to_ai_btn.setCursor(Qt.PointingHandCursor)
        self.to_ai_btn.clicked.connect(self._start_tagopt_ai_probe)
        g2v.addWidget(self.to_ai_btn)

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
        self.to_status.setStyleSheet("color:#71717a;font-size:11px;")
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
            self.to_ai_state.setStyleSheet("color:#71717a;font-size:11px;")
            self.to_ai_state.setText("当前用普通智能算法：纯本地规则 + 全库标签共现，"
                                     "完全不依赖 AI，速度最快。")
            return
        self._start_tagopt_ai_probe()

    def _start_tagopt_ai_probe(self):
        """v1.34.3（反馈 2）：标签优化页显式触发本地 AI 引擎探测，收口复用 _on_to_ai_probe。

        抽出成独立方法后，「AI 智能算法」单选切换 与 新增的「检测本地 AI 引擎」按钮
        共用同一套忙碌态 + 探测逻辑，避免两处各写一遍导致行为漂移。
        """
        w = getattr(self, "_to_ai_worker", None)
        if w is not None and w.isRunning():
            return
        self.to_ai_state.setStyleSheet("color:#8fc0ff;font-size:11px;")
        self.to_ai_state.setText("正在检测本地 AI 引擎…")
        self._to_ai_worker = AiProbeWorker()
        self._to_ai_worker.done.connect(self._on_to_ai_probe)
        self._to_ai_worker.start()

    def _on_to_ai_probe(self, st):
        st = st or {}
        eng = st.get("engine")
        if eng == "ollama":
            self.to_ai_state.setStyleSheet("color:#45d483;font-size:11px;")
            self.to_ai_state.setText("本地离线 AI 可用：" + html_esc(st.get("label"))
                                     + "　—— 想换模型去「智能推荐」页填。")
        elif eng == "error":
            self.to_ai_state.setStyleSheet("color:#f87171;font-size:11px;")
            self.to_ai_state.setText("AI 引擎检测失败，将退回内置算法："
                                     + html_esc(st.get("detail")))
        else:
            self.to_ai_state.setStyleSheet("color:#8fc0ff;font-size:11px;")
            self.to_ai_state.setText("没检测到可用的本地模型，将退回内置算法："
                                     + html_esc(st.get("detail")))

    # ---------- 标签优化：执行 ----------
    def _tagopt_clear(self):
        self._to_plans = []
        self._to_changed = []
        self.to_table.setRowCount(0)
        self.btn_to_run.setEnabled(False)
        self.to_progress.setValue(0)
        self.to_status.setStyleSheet("color:#71717a;font-size:11px;")
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
        self.to_status.setStyleSheet("color:#8fc0ff;font-size:11px;")
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
            self.to_status.setStyleSheet("color:#f87171;font-size:11px;")
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
        self.to_status.setStyleSheet("color:#8fc0ff;font-size:11px;")
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
            self.to_status.setStyleSheet("color:#f87171;font-size:11px;")
            self.to_status.setText("✗ " + str(err))
            return
        changed = [p for p in plans if not p.get("error")
                   and list(p.get("before") or []) != list(p.get("after") or [])]
        self._to_changed = changed
        self._fill_to_table(changed)
        self.btn_to_run.setEnabled(bool(changed))
        if not changed:
            self.to_status.setStyleSheet("color:#45d483;font-size:11px;")
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
        self.to_status.setStyleSheet("color:#8fc0ff;font-size:11px;")
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
        self.to_status.setStyleSheet("color:#8fc0ff;font-size:11px;")
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
            self.to_status.setStyleSheet("color:#8fc0ff;font-size:11px;")
        else:
            self.to_status.setStyleSheet("color:#45d483;font-size:11px;")
        self.to_status.setText(head)
        applog.log("[标签优化] " + head)
        self._to_plans = []
        self._to_changed = []
        self.btn_to_run.setEnabled(False)
        if self.on_changed:
            self.on_changed()
