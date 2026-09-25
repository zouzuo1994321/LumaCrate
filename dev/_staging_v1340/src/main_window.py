# -*- coding: utf-8 -*-
"""流明盒 (LumaCrate) 主界面 (PySide6 原生，Emby 风格布局，不依赖浏览器)。"""
import os
import re
import json
import math
import html
import time
import base64                      # v1.33.1：联系图标 logo 以 base64 内联
from datetime import datetime

from PySide6.QtCore import (Qt, QThread, Signal, QTimer, QRect, QPoint, QSize, QRectF, QPointF,
                            QUrl, QObject, QEvent, QByteArray)
from PySide6.QtGui import (QPixmap, QKeySequence, QShortcut, QGuiApplication, QPainter,
                           QColor, QPen, QFont, QPainterPath, QPolygonF, QIcon,
                           QDesktopServices, QImage)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QScrollArea,
    QGridLayout, QFrame, QDialog, QTextBrowser, QFileDialog, QMessageBox,
    QStackedWidget, QSizePolicy, QSpacerItem, QMenu, QInputDialog, QApplication,
    QCheckBox, QProgressBar, QComboBox, QLayout, QButtonGroup,
    QGraphicsDropShadowEffect, QDoubleSpinBox,
)

import database as db
import version as ver
import scanner as scanner_mod
import player as player_mod
import config as cfg
import backdrop
import veil as veil_mod
import media_meta as mm
import applog
import recommend as rec_mod         # v1.34.0：推荐墙顶部「引导向量」要用来解析 / 取常量
import sysmon                    # v1.27.0：侧栏「实时状态」面板（叶子模块，无循环导入）
import i18n                      # v1.32.0：界面语言（叶子模块，无循环导入；查不到原样返回中文）
from ui_hero import HeroView, circle_pixmap, cover_pixmap, placeholder_pixmap, compact_button
from ui_home import HomeListView
from ui_settings import SettingsDialog, LibraryEditDialog

STYLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.qss")
# v1.25.0（反馈 5）：当前「高亮色」的 RGB。由 render_style() 在每次重载样式表时刷新，
# 自绘控件（PosterCard / ActorCard 的选中描边、选中卡的外发光）读它取色 ——
# QSS 那边走令牌替换，两边拿到的必须是同一个值，否则描边和光晕会串色。
ACCENT_RGB = (192, 57, 43)
POSTER_W, POSTER_H = 158, 236

# 影片卡分区尺寸：四项高度严格相加 = 卡片高，避免此前「内容 342 > 卡片 328」溢出，
# 导致小字区被裁到 21px、「导演」那一行永远看不见（v1.11.0 修复）。
# v1.11.1：副标题（年份/评分/画质）与演员/导演小字都进了「内容卡片」设置，
# 于是卡高必须按「实际渲染了哪些分区」动态算，不能再写死一个常数。
_CARD_PAD = 7
_CARD_SPACING = 4
_TITLE_H = 40        # 标题最多 2 行（#CardTitle 13px，行距约 19px）
_SUB_H = 16          # 评分 / 年份 / 画质
_LINE_H = 16         # 小字单行高（演员 / 导演 各一行）
_CREW_H = _LINE_H * 2
_PLAY_BTN = 26       # v1.17.0：卡片右下角圆形播放按钮直径
_STAR_BTN = 26       # v1.21.0：卡片左下角收藏星标按钮（与播放按钮左右对称）
POSTER_CARD_W = POSTER_W + _CARD_PAD * 2


def poster_card_height(crew_lines: int = 2, has_sub: bool = True) -> int:
    """按实际渲染的分区数算卡高（不变式：卡高 == 边距 + 图 + 标题 + 副标题 + 小字行 + 间距）。"""
    children = 2 + (1 if has_sub else 0) + (1 if crew_lines else 0)   # 图 / 标题 / 副标题 / 小字
    return (_CARD_PAD * 2 + POSTER_H + _TITLE_H
            + (_SUB_H if has_sub else 0) + _LINE_H * crew_lines
            + _CARD_SPACING * (children - 1))


POSTER_CARD_H = poster_card_height()      # 全开时的卡高（350），兼容旧断言

# v1.17.0：卡片右下角「直接播放」按钮 —— 只对**确实是视频文件**的条目显示。
# 用扩展名判断而**不做磁盘 I/O**：5 万片规模下每张卡 os.path.isfile() 会拖慢滚动
# （尤其 X:/Y:/ 这类外置/网络盘），扩展名判断是纯字符串运算，零成本且足够准。
_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".wmv", ".mov", ".ts", ".m2ts", ".iso", ".rmvb",
               ".flv", ".webm", ".mpg", ".mpeg", ".m4v", ".rm", ".3gp", ".vob", ".mts"}


def playable_media(media) -> bool:
    """该条目是否可直接播放（file_path 是视频文件）。"""
    fp = (media or {}).get("file_path") or ""
    return os.path.splitext(fp)[1].lower() in _VIDEO_EXTS


def _qt_alive(*objs) -> bool:
    """这些 Qt 对象的 C++ 实体是否还在。

    v1.24.1：`LazyGrid` 用 `QTimer.singleShot(1, self._pump)` 分批建卡，而定时器的队列项
    持有的是 **Python 端的绑定方法**。页面被 `_replace_current()` / `deleteLater()` 换掉后，
    C++ 那侧已经析构，可定时器仍会触发 → `_pump()` 里访问布局就抛
    「Internal C++ object already deleted」。换页越快越容易撞上（冒烟里直接复现了）。
    """
    for o in objs:
        if o is None:
            continue
        try:
            o.objectName()
        except RuntimeError:
            return False
    return True


# ---------- 卡片角标按钮（v1.21.0） ----------
def _star_path(cx, cy, r_out, r_in=None):
    """五角星路径（尖角朝上，10 个顶点内外交替）。

    r_in 默认取外接半径的 0.42 —— 比正五角星的理论值 0.382 略饱满，
    在 20px 上下的小尺寸里更像「星」而不是齿轮。
    """
    r_in = r_out * 0.42 if r_in is None else r_in
    path = QPainterPath()
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r_out if i % 2 == 0 else r_in
        x, y = cx + rad * math.cos(ang), cy + rad * math.sin(ang)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    return path


class _PlayGlyphButton(QPushButton):
    """卡片右下角圆形播放按钮：圆底 / 描边走 QSS(#CardPlay)，三角形**几何绘制**。

    v1.21.0（反馈 2）：原先用字符「▶」当图标，字形的左右 side bearing 不对称，
    26px 圆圈里永远偏左，怎么调 padding 都对不准圆心。
    改为画多边形，并把三角形的**重心**对齐圆心（重心 = 外接矩形中心向右偏 1/3 半宽，
    这是播放键通行的光学居中做法，纯几何外接框居中的话视觉上会偏左）。
    """

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setObjectName("CardPlay")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(_PLAY_BTN, _PLAY_BTN)

    def paintEvent(self, e):
        super().paintEvent(e)                      # 先让 QSS 画圆底 + 描边
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        sw, sh = 4.0, 4.7                          # 三角形半宽 / 半高
        dx = sw / 3.0                              # 让重心落在圆心
        tri = QPolygonF([
            QPointF(cx - sw + dx, cy - sh),
            QPointF(cx - sw + dx, cy + sh),
            QPointF(cx + sw + dx, cy),
        ])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(243, 240, 234))
        p.drawPolygon(tri)
        p.end()


class _FavStarButton(QPushButton):
    """卡片左下角收藏星标：**全自绘**（不画 QSS 背景，保持星形内部透明）。

    未收藏：深色光晕 + 白色描边，内部透明（能透出海报，和反馈原话一致）；
    已收藏：金色实心五角星 + 细暗描边（亮底剧照上也压得住）。
    """

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setObjectName("CardStar")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(_STAR_BTN, _STAR_BTN)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet("background:transparent;border:none;")
        self._on = False

    def set_on(self, on):
        on = bool(on)
        if on != self._on:
            self._on = on
            self.update()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        r = min(self.width(), self.height()) / 2.0 - 1.6
        if self.underMouse():
            r += 0.6
        path = _star_path(cx, cy, r)
        if self._on:
            p.setBrush(QColor(247, 201, 72))
            p.setPen(QPen(QColor(74, 52, 6, 210), 1.0))
            p.drawPath(path)
        else:
            p.setBrush(Qt.NoBrush)
            # 先描一圈半透明黑影当光晕，白描边在明亮剧照上才不会「消失」
            p.setPen(QPen(QColor(0, 0, 0, 150), 3.6))
            p.drawPath(path)
            p.setPen(QPen(QColor(255, 255, 255) if self.underMouse()
                          else QColor(246, 243, 238), 1.7))
            p.drawPath(path)
        p.end()

# 扫描模式 -> 菜单文案（文件夹右键 / 媒体库右键共用）
SCAN_MODE_CN = {"new": "扫描新添加和修改的",
                "fill": "扫描全部补充缺失",
                "overwrite": "扫描全部并覆盖",
                "purge": "扫描并删除失效的"}


def _clip_text(s, n: int = 12) -> str:
    """卡片小字限宽：超长按字符数截断加省略号（本机 QLabel 无 setTextElideMode）。"""
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


def _fit_lines(text, width: int, lines: int, fm) -> str:
    """把文本压进 lines 行以内（超出截断加 …）。

    v1.11.0：标题 QLabel 是定高的，文字需要 3 行时第 3 行会被裁掉一半
    （看着像「异常」）。这里按真实字宽二分找到能放下 2 行的最大长度。
    """
    text = (text or "").strip()
    if not text:
        return ""
    budget = fm.lineSpacing() * lines

    def fits(t):
        return fm.boundingRect(0, 0, width, 100000, Qt.TextWordWrap, t).height() <= budget

    if fits(text):
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(text[:mid] + "…"):
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + "…"


# ---------- meta / 尺寸 解析（演员卡 / 详情页共用） ----------
# 老库里残留的「站内样板文案 / HTML 碎片」特征词（v1.11.0 演员卡乱码修复）
_META_JUNK = ("掲載", "情報交換", "無料動画", "アダルトビデオ",
              "property=", "content=", "og:")


def _parse_meta(s):
    """解析 people.meta。老库里有非法 JSON（被截断 / 未转义引号），此时尽力提取键值对。"""
    if not s:
        return {}
    if isinstance(s, dict):
        return s
    try:
        d = json.loads(s)
        return d if isinstance(d, dict) else {}
    except Exception:
        pass
    out = {}
    # 值可以没有收尾引号（老库里有被截断的记录），故用 (?:"|$) 兜底
    for m in re.finditer(r'"([^"]{1,24})"\s*:\s*"([^"]*)(?:"|$)', str(s)):
        out.setdefault(m.group(1), m.group(2))
    return out


def _clean_meta_value(v, limit: int = 60):
    """清洗刮削残留：剥 HTML 标签、断开未闭合标签残片、丢弃站内样板文案。

    真机库里 11 条 meta 的「出身地 / 尺寸 / 事务所」其实是页面
    `<meta property="og:description">` 的样板文案（形如
    `：東京都。AV女優、…"> <meta property="og:description" content="…`）。
    这里尽力抢救出「冒号后的短片段」（東京都），取不到就返回空串（宁缺勿脏）。
    """
    if not v:
        return ""
    s = html.unescape(str(v))
    s = re.sub(r"<[^>]*>", " ", s)
    s = s.split("<", 1)[0]                        # 未闭合标签起的残片一律丢弃
    s = re.sub(r"\s*(?:property|content)\s*=.*$", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    if any(t in s for t in _META_JUNK):
        m = re.search(r"[：:]\s*([^。、，,｜|\s]{1,20})", s)
        s = m.group(1) if m else ""
    return s.strip("、。，, ｜| ・：: 　")[:limit]


def _parse_size(s):
    """从刮削的「尺寸」串(如 T153/B85/W58/H83 或 B85 W58 H83)解析胸/腰/臀。"""
    s = _clean_meta_value(s, 80)
    if not s:
        return None, None, None
    b = re.search(r"B[\s:：]?(\d{2,3})", s, re.I)
    w = re.search(r"W[\s:：]?(\d{2,3})", s, re.I)
    h = re.search(r"H[\s:：]?(\d{2,3})", s, re.I)
    return (b.group(1) if b else None,
            w.group(1) if w else None,
            h.group(1) if h else None)


#: meta 里可能承载罩杯的键（真机库里 3870 / 5909 位演员有独立的「罩杯」键）
_CUP_META_KEYS = ("罩杯", "カップ", "cup", "CUP")


def _parse_cup(size_str, *extra):
    """解析罩杯字母（`尺寸` 串形如 `T155 / B111( Lカップ ) / W65 / H96 / S`）。

    v1.31.0（反馈 2）：真机库里罩杯信息一直都在，只是 v1.10.0 的 `_parse_size`
    当年只取了 B/W/H 三项，卡片上「三围」因此少了最关键的一档。
    两个来源都试（按可靠性排序）：
      ① `尺寸` 串里 `B111( Lカップ )` 括号内的字母；
      ② 紧随字母的 `カップ`；
      ③ 任意括号里的裸字母；
      ④ 独立键（`meta["罩杯"]`）里就是一个裸字母（L / E / I / H …）。
    取不到一律返回空串（宁缺勿脏，别拿字母瞎凑）。
    """
    for s in (size_str,) + tuple(extra or ()):
        t = _clean_meta_value(s, 60)
        if not t:
            continue
        m = (re.search(r"B\s*\d{2,3}\s*[（(]\s*([A-Za-z]{1,3})", t)
             or re.search(r"([A-Za-z]{1,3})\s*カップ", t)
             or re.search(r"[（(]\s*([A-Za-z]{1,3})\s*[)）]", t))
        if m:
            return m.group(1).upper()
        if re.fullmatch(r"[A-Za-z]{1,3}", t):
            return t.upper()
    return ""


def _person_status(p):
    """演员状态：库里 status 优先；为空时按「作品最新年份」启发式推断。

    真机库 85 位演员 status 全为空 → 卡片一律「未知」看起来像坏了。
    v1.11.0 起：有近两年作品 → 现役；只有更早作品 → 退役；无作品 → 未知。
    详情页可手动改，手动值优先（推断只在 status 为空时生效）。
    """
    st = (p.get("status") or "").strip()
    if st in ("现役", "退役"):
        return st
    try:
        y = int(p.get("last_year"))
    except (TypeError, ValueError):
        return ""
    return "现役" if y >= datetime.now().year - 1 else "退役"


def render_style(appearance: dict = None) -> str:
    """读取 style.qss 并替换透明令牌（磨砂玻璃浓度 / 经典暗色）。"""
    if not os.path.exists(STYLE_FILE):
        return ""
    try:
        with open(STYLE_FILE, encoding="utf-8") as f:
            qss = f.read()
    except Exception:
        return ""
    ap = appearance or cfg.get_settings().appearance
    veil, panel = cfg.appearance_alphas(ap)
    surf = min(255, int(panel) + 30)
    dlg = min(255, max(int(surf), 232))
    for token, val in (("__VEIL__", veil), ("__PANEL__", panel),
                       ("__SURF__", surf), ("__DLG__", dlg)):
        qss = qss.replace(token, str(int(val)))
    # v1.25.0（反馈 5）：高亮色令牌。QSS 的 rgba() 通道位写不了十六进制，
    # 所以这里替换成 "r, g, b" 文本；同时刷新模块级 ACCENT_RGB，让自绘控件同步换色。
    # 先替换长令牌再替换短令牌（__ACCENT_DARK__ 里不含 __ACCENT__，顺序其实无所谓，
    # 但写成从长到短以后再加令牌就不会踩坑）。
    global ACCENT_RGB
    acc_hex = (ap or {}).get("accent")
    ACCENT_RGB = cfg.accent_rgb(acc_hex)
    shades = cfg.accent_shades(acc_hex)
    for token, key in (("__ACCENT_LIGHT__", "light"), ("__ACCENT_DARK__", "dark"),
                       ("__ACCENT_DEEP__", "deep"), ("__ACCENT__", "base")):
        r, g, b = shades[key]
        # 1) `rgba(__TOKEN__, 0.75)`：QSS 的 rgba() 通道位不认十六进制，只能填 "r, g, b"。
        qss = qss.replace(f"rgba({token},", f"rgba({r}, {g}, {b},")
        # 2) 剩下的**裸令牌**（`border-color: __ACCENT_LIGHT__;` 这种直接当颜色值的）：
        #    必须换十六进制 —— 塞 "224, 82, 67" 进去不是合法 CSS，Qt 会把整条声明丢掉，
        #    表现为「换了高亮色但某些描边/选中底没变」，且不报错。
        qss = qss.replace(token, f"#{r:02x}{g:02x}{b:02x}")
    return qss


def load_style(app, appearance: dict = None):
    app.setStyleSheet(render_style(appearance))


# ---------- 删除媒体库确认对话框 ----------
class DeleteLibraryDialog(QDialog):
    """删除媒体库前的确认：明确「不动磁盘文件」，并可选择是否清掉索引记录。"""

    def __init__(self, parent, lib):
        super().__init__(parent)
        self.setWindowTitle("删除媒体库")
        self.resize(520, 300)
        self.lib = lib
        stat = db.count_library(lib["name"])
        self._stat = stat

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(10)
        icon = QLabel("将删除媒体库")
        icon.setStyleSheet("font-size:16px;font-weight:700;color:#e7c86a;")
        v.addWidget(icon)
        info = QLabel(f"「{lib['name']}」　（已索引 {stat['count']} 项 · "
                      f"{mm.human_size(stat['size'])}）")
        info.setWordWrap(True)
        v.addWidget(info)
        if lib.get("paths"):
            pl = QLabel("关联媒体文件夹：\n" + "\n".join(lib["paths"][:5]))
            pl.setStyleSheet("color:#a2967f;font-size:11px;")
            pl.setWordWrap(True)
            v.addWidget(pl)

        # QLabel 不认 Markdown（写 `**` 会原样显示成星号）→ 直接用 <b> 走富文本
        warn = QLabel("⚠ 该操作不可撤销；<b>不会删除磁盘上的任何文件</b>。")
        warn.setStyleSheet("color:#e07a6a;font-size:12px;")
        warn.setWordWrap(True)
        v.addWidget(warn)

        self.chk_media = QCheckBox("同时删除该媒体库下的媒体索引记录（仅清索引，不动磁盘文件）")
        self.chk_media.setChecked(False)
        if stat["count"] == 0:
            self.chk_media.setEnabled(False)
        v.addWidget(self.chk_media)
        v.addStretch(1)

        btns = QHBoxLayout()
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("确认删除")
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)

    def showEvent(self, e):
        super().showEvent(e)
        try:
            backdrop.auto_apply(self)
        except Exception:
            pass

    def result_data(self):
        return {"delete_media": self.chk_media.isChecked() and self.chk_media.isEnabled(),
                "count": self._stat["count"]}


def _pix(path, w, h):
    pm = cover_pixmap(path, w, h)
    if pm.isNull():
        pm = QPixmap(w, h)
        pm.fill(Qt.transparent)
    return pm


# ---------- 图像缓存（v1.14.0） ----------
# 海报不再是「建卡时现读磁盘 + 缩放」：滚动/重绘同一张卡时直接命中缓存。
# 上限内用简单淘汰（超限整体清空），避免无界增长吃内存。
_COVER_CACHE = {}
_COVER_CACHE_MAX = 800
_AVATAR_CACHE = {}
_AVATAR_CACHE_MAX = 800


def _cached_cover(path, w, h):
    if not path:
        return QPixmap()
    key = (path, w, h)
    pm = _COVER_CACHE.get(key)
    if pm is None:
        pm = cover_pixmap(path, w, h)
        if len(_COVER_CACHE) >= _COVER_CACHE_MAX:
            _COVER_CACHE.clear()
        _COVER_CACHE[key] = pm
    return pm


def _cached_avatar(path, size):
    if not path:
        return None
    key = (path, size)
    pm = _AVATAR_CACHE.get(key)
    if pm is None:
        pm = circle_pixmap(path, size)
        if len(_AVATAR_CACHE) >= _AVATAR_CACHE_MAX:
            _AVATAR_CACHE.clear()
        _AVATAR_CACHE[key] = pm
    return pm


def _clear_image_caches():
    _COVER_CACHE.clear()
    _AVATAR_CACHE.clear()


# ---------- 「筛选 + 排序」工具条（v1.14.0，反馈 4 / 5） ----------
# 排序菜单参照 Emby：先列排序字段，分隔线后再给「降序 / 升序」，当前项打勾。
MEDIA_FILTER_SPECS = [
    ("favorite", "收藏情况", [("全部", None), ("已收藏", {"favorite": True}),
                              ("未收藏", {"favorite": False})]),
    ("urating", "用户评分", [("全部", None),
                             ("有评分", {"has_user_rating": True}),
                             ("未评分", {"has_user_rating": False}),
                             ("≥ 3 分", {"min_user_rating": 3}),
                             ("≥ 5 分", {"min_user_rating": 5}),
                             ("≥ 7 分", {"min_user_rating": 7}),
                             ("≥ 9 分", {"min_user_rating": 9})]),
    ("year", "年份", [("全部", None), ("2020 之后", {"year_from": 2020}),
                      ("2010 之后", {"year_from": 2010}), ("2000 之后", {"year_from": 2000}),
                      ("2000 及以前", {"year_to": 2000})]),
    ("kind", "类型", [("全部", None), ("电影", {"kind": "movie"}), ("剧集", {"kind": "tvshow"})]),
    ("quality", "画质", [("全部", None)] + [(q, {"quality": q}) for q, _ in db.QUALITY_FILTERS]),
]

ACTOR_FILTER_SPECS = [
    ("favorite", "收藏情况", [("全部", None), ("已收藏", {"favorite": True}),
                              ("未收藏", {"favorite": False})]),
    ("pinned", "置顶", [("全部", None), ("已置顶", {"pinned": True}), ("未置顶", {"pinned": False})]),
    ("status", "状态", [("全部", None)] + [(s, {"status": s}) for s in db.ACTOR_STATUSES]),
    ("photo", "头像", [("全部", None), ("有头像", {"has_photo": True}),
                       ("无头像", {"has_photo": False})]),
]


class FilterSortBar(QWidget):
    """影片墙 / 演员库的「筛选 + 排序」条。

    · 排序：一个按钮弹出菜单（字段列表 + 降序/升序），与 Emby 的排序菜单一致；
    · 筛选：一排紧凑下拉（收藏情况 / 用户评分 / 年份 / 类型 / 画质…），选项直接映射成
      数据库查询条件，**在 SQL 层过滤**而不是把全部数据拉到内存再筛；
    · 变更即回调 `changed`，由页面重查并重载网格（结果全量分页）。
    """

    changed = Signal()

    def __init__(self, kind="media", sort="sort_title", asc=True, filters=None, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._sort = sort
        self._asc = bool(asc)
        self._filters = dict(filters or {})
        self._specs = MEDIA_FILTER_SPECS if kind == "media" else ACTOR_FILTER_SPECS
        self._sorts = db.MEDIA_SORTS if kind == "media" else db.ACTOR_SORTS
        self._combos = {}

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        self.sort_btn = QPushButton()
        self.sort_btn.setObjectName("Ghost")
        self.sort_btn.setCursor(Qt.PointingHandCursor)
        self.sort_btn.clicked.connect(self._open_sort_menu)
        h.addWidget(self.sort_btn)

        for key, label, options in self._specs:
            lbl = QLabel(label + "：")
            lbl.setStyleSheet("color:#9b8e7a;font-size:11px;")
            h.addWidget(lbl)
            cb = QComboBox()
            cb.setMinimumWidth(96)
            for text, value in options:
                cb.addItem(text, value)
            cb.currentIndexChanged.connect(self._on_filter_changed)
            self._combos[key] = (cb, options)
            h.addWidget(cb)
            self._select_combo(cb, options)

        reset = QPushButton("重置")
        reset.setObjectName("Ghost")
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self._reset)
        h.addWidget(reset)
        h.addStretch(1)
        self._sync_sort_btn()

    # ------ 内部 ------
    def _select_combo(self, cb, options):
        """按当前 filters 反选下拉项（页面前进/后退时不丢筛选状态）。"""
        target = None
        for i, (_text, value) in enumerate(options):
            if value is None:
                continue
            if all(self._filters.get(k) == v for k, v in value.items()):
                target = i
                break
        cb.blockSignals(True)
        cb.setCurrentIndex(target if target is not None else 0)
        cb.blockSignals(False)

    def _on_filter_changed(self, *_):
        merged = {}
        for key, (cb, options) in self._combos.items():
            idx = cb.currentIndex()
            value = options[idx][1] if 0 <= idx < len(options) else None
            if isinstance(value, dict):
                merged.update(value)
        self._filters = merged
        self.changed.emit()

    def _reset(self):
        for cb, options in self._combos.values():
            cb.blockSignals(True)
            cb.setCurrentIndex(0)
            cb.blockSignals(False)
        self._filters = {}
        self.changed.emit()

    def _sort_label(self) -> str:
        name = next((l for k, l, _e in self._sorts if k == self._sort), self._sort)
        return f"排序：{name} {'↑' if self._asc else '↓'}"

    def _sync_sort_btn(self):
        self.sort_btn.setText(self._sort_label())

    def _open_sort_menu(self):
        menu = QMenu(self)
        for key, label, _expr in self._sorts:
            act = menu.addAction(("✓ " if key == self._sort else "   ") + label)
            act.triggered.connect(lambda _c, k=key: self._set_sort(k))
        menu.addSeparator()
        for asc, label in ((False, "降序"), (True, "升序")):
            act = menu.addAction(("✓ " if asc == self._asc else "   ") + label)
            act.triggered.connect(lambda _c, a=asc: self._set_sort(self._sort, a))
        menu.exec(self.sort_btn.mapToGlobal(self.sort_btn.rect().bottomLeft()))

    def _set_sort(self, key, asc=None):
        self._sort = key
        if asc is not None:
            self._asc = bool(asc)
        self._sync_sort_btn()
        self.changed.emit()

    # ------ 对外 ------
    def sort(self):
        return self._sort

    def asc(self):
        return self._asc

    def filters(self):
        return dict(self._filters)


# ---------- 多维筛选面板（v1.16.0，反馈 1「强化筛选」） ----------
class FlowLayout(QLayout):
    """简易流式布局：一行放不下就自动换行（Qt 官方 FlowLayout 例子精简版）。

    为什么需要它：风格有 17 个 chip、地区有 14 个，窗口一窄单行 HBox 会把它们裁掉。
    用 FlowLayout 让 chip 自然换行，任何窗口宽度下选项都完整可见。
    """

    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

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
        x, y, line_h = eff.x(), eff.y(), 0
        for it in self._items:
            hint = it.sizeHint()
            nx = x + hint.width()
            if nx - 1 > eff.right() and line_h > 0:
                x = eff.x()
                y = y + line_h + self.spacing()
                nx = x + hint.width()
                line_h = 0
            if not test_only:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x = nx + self.spacing()
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.bottom()


def _year_facet_options():
    """年份维度：近 6 年逐年 → 再按十年分段 → 最后「更早」。"""
    y = datetime.now().year
    opts = [("全部", None)]
    for yy in range(y, y - 6, -1):
        opts.append((str(yy), {"year_from": yy, "year_to": yy}))
    start = y - 6
    while start >= 1990:
        lo = start - 9
        opts.append((f"{start}-{lo}", {"year_from": lo, "year_to": start}))
        start -= 10
    opts.append(("更早", {"year_to": start}))
    return opts


# 每个维度 = (键, 标签, [(chip 文案, 过滤字典)])；「全部」的值为 None（即不筛）。
# v1.17.0：**删除「状态」(ident) 与「进度」(progress) 两类筛选**（用户反馈 2）。
# 它们在 `database._media_where` 里的 SQL 支持仍保留，供其它调用与旧库兼容，只是 UI 不再暴露。
MEDIA_FACETS = [
    ("genre", "风格", [("全部", None)] + [(g, {"genre": g}) for g in db.GENRE_FACETS]
                      + [("其他", {"genre_other": True})]),
    ("country", "地区", [("全部", None)] + [(c, {"country": c}) for c in db.COUNTRY_FACETS]
                        + [("其他", {"country_other": True})]),
    ("year", "年份", _year_facet_options()),
    ("kind", "类型", [("全部", None), ("电影", {"kind": "movie"}),
                      ("剧集", {"kind": "tvshow"}), ("合集", {"has_collection": True})]),
    ("favorite", "收藏", [("全部", None), ("已收藏", {"favorite": True}),
                          ("未收藏", {"favorite": False})]),
    ("urating", "评分", [("全部", None), ("有评分", {"has_user_rating": True}),
                         ("未评分", {"has_user_rating": False}),
                         ("≥ 5 分", {"min_user_rating": 5}),
                         ("≥ 7 分", {"min_user_rating": 7}),
                         ("≥ 9 分", {"min_user_rating": 9})]),
]


class FacetBar(QWidget):
    """影片墙的「**可收缩**多维 chip 筛选 + 排序」面板（v1.16.0 引入，v1.17.0 改为可收缩）。

    平日**收缩**：头部只有右对齐的「排序 / 筛选」两个小按钮，不占版面；
    点「筛选」才展开各维度 chip（每维一行、点一下即筛，无需展开下拉）。
    维度之间是「与」；同一维度内单选（QButtonGroup 互斥）；chip 超宽自动换行（FlowLayout）。
    展开 / 收缩状态由 `wall_prefs.facet_open` 记住（只存偏好，不重建列表）。
    """

    changed = Signal()                 # 筛选 / 排序变化 → 需要重建列表
    toggled = Signal(bool)             # 展开 / 收缩 → 只存偏好，不重建

    def __init__(self, sort="sort_title", asc=True, filters=None, facets=None,
                 open_=False, with_header=True, parent=None):
        super().__init__(parent)
        self._sort = sort
        self._asc = bool(asc)
        self._filters = dict(filters or {})
        self._facets = facets if facets is not None else MEDIA_FACETS
        self._sorts = db.MEDIA_SORTS
        self._groups = {}            # key -> [(btn, value), ...]（QButtonGroup 保互斥）
        self._loading = False
        self._open = bool(open_)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        # ---- 头部按钮（排序 / 筛选）：默认由 FacetBar 自带并右对齐；
        #      with_header=False 时只创建、不挂布局 —— 交给页面自行排到统一工具行。 ----
        self.sort_btn = QPushButton()
        self.sort_btn.setObjectName("Ghost")
        self.sort_btn.setCursor(Qt.PointingHandCursor)
        self.sort_btn.clicked.connect(self._open_sort_menu)
        self.filter_btn = QPushButton()
        self.filter_btn.setObjectName("Ghost")
        self.filter_btn.setCheckable(True)
        self.filter_btn.setCursor(Qt.PointingHandCursor)
        self.filter_btn.clicked.connect(self._toggle_open)
        if with_header:
            top = QHBoxLayout(); top.setContentsMargins(0, 0, 0, 0); top.setSpacing(8)
            top.addStretch(1)
            top.addWidget(self.sort_btn)
            top.addWidget(self.filter_btn)
            v.addLayout(top)

        # ---- 可收缩区域：各维度 chip 行 + 「重置筛选」 ----
        self._panel = QWidget()
        pv = QVBoxLayout(self._panel)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(3)
        for key, label, options in self._facets:
            row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setFixedWidth(44)
            lbl.setStyleSheet("color:#9b8e7a;font-size:11px;")
            row.addWidget(lbl)
            host = QWidget()
            flow = FlowLayout(host, margin=0, spacing=4)
            grp = QButtonGroup(self)
            grp.setExclusive(True)
            pairs = []
            for text, value in options:
                b = QPushButton(text)
                b.setObjectName("Chip")
                b.setCheckable(True)
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _c, k=key: self._on_chip(k))
                grp.addButton(b)
                flow.addWidget(b)
                pairs.append((b, value))
            self._groups[key] = pairs
            row.addWidget(host, 1)
            pv.addLayout(row)
        foot = QHBoxLayout(); foot.setContentsMargins(0, 0, 0, 0)
        foot.addStretch(1)
        self.reset_btn = QPushButton("重置筛选")
        self.reset_btn.setObjectName("Ghost")
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.clicked.connect(self._reset)
        foot.addWidget(self.reset_btn)
        pv.addLayout(foot)
        v.addWidget(self._panel)

        self._sync_sort_btn()
        self._apply_filters_to_chips()
        self.set_open(self._open)

    # ------ 展开 / 收缩 ------
    def set_open(self, on):
        on = bool(on)
        self._open = on
        self._panel.setVisible(on)
        self.filter_btn.setChecked(on)
        self.filter_btn.setText("筛选 ▴" if on else "筛选 ▾")
        self.filter_btn.setToolTip(
            "收起筛选项" if on else
            "展开筛选项：风格 / 地区 / 年份 / 类型 / 收藏 / 评分")

    def is_open(self):
        return bool(self._open)

    def _toggle_open(self):
        self.set_open(not self._open)
        self.toggled.emit(self._open)

    # ------ 内部 ------
    def _on_chip(self, key):
        if self._loading:
            return
        merged = {}
        for pairs in self._groups.values():
            for b, value in pairs:
                if b.isChecked() and isinstance(value, dict):
                    merged.update(value)
                    break
        self._filters = merged
        self.changed.emit()

    def _reset(self):
        self._loading = True
        for pairs in self._groups.values():
            if pairs:
                pairs[0][0].setChecked(True)
        self._loading = False
        self._filters = {}
        self.changed.emit()

    def _apply_filters_to_chips(self):
        """按当前 filters 反选 chip（页面前进/后退不丢筛选状态）。"""
        self._loading = True
        for pairs in self._groups.values():
            target = 0
            for i, (_b, value) in enumerate(pairs):
                if value is None:
                    continue
                if all(self._filters.get(k) == v for k, v in value.items()):
                    target = i
                    break
            pairs[target][0].setChecked(True)
        self._loading = False

    def _sort_label(self):
        name = next((l for k, l, _e in self._sorts if k == self._sort), self._sort)
        suffix = "" if self._sort == "random" else (" ↑" if self._asc else " ↓")
        return f"排序：{name}{suffix}"

    def _sync_sort_btn(self):
        self.sort_btn.setText(self._sort_label())

    def _open_sort_menu(self):
        menu = QMenu(self)
        for key, label, _expr in self._sorts:
            act = menu.addAction(("✓ " if key == self._sort else "   ") + label)
            act.triggered.connect(lambda _c, k=key: self._set_sort(k))
        if self._sort != "random":      # 随机排序无升/降序之分
            menu.addSeparator()
            for asc, label in ((False, "降序"), (True, "升序")):
                act = menu.addAction(("✓ " if asc == self._asc else "   ") + label)
                act.triggered.connect(lambda _c, a=asc: self._set_sort(self._sort, a))
        menu.exec(self.sort_btn.mapToGlobal(self.sort_btn.rect().bottomLeft()))

    def _set_sort(self, key, asc=None):
        self._sort = key
        if asc is not None:
            self._asc = bool(asc)
        self._sync_sort_btn()
        self.changed.emit()

    # ------ 对外 ------
    def sort(self):
        return self._sort

    def asc(self):
        return self._asc

    def filters(self):
        return dict(self._filters)


class LazyGrid(QWidget):
    """**增量渲染**的卡片网格（v1.14.0，反馈 1 / 3 / 8）。

    为什么必须这样：5 万条规模下一次性建 5 万个卡片控件会把 GUI 线程锁死几十秒，
    用户看到的就是「点一下就未响应」。这里改成：
      · 每次只建 `batch` 张卡，建完一批**把控制权交还事件循环**再建下一批；
      · 顶部实时显示「已加载 x / 总数」+ 进度条 —— 加载状态直观可见；
      · 未加载的部分不创建任何控件，也不占内存；
      · 数据本身也按页从数据库取（offset/limit），不把 5 万行一次性读进内存。
    """

    # v1.28.1（反馈）：演员库 / 导演库由每行 5 个改为 **每行 6 个**。
    # 两库共用 kind="actor"（见 _view_actors / _view_directors），所以一处即覆盖两者。
    # 宽度校验：1920 默认窗 − 侧栏 186 − 页面左右边距 40 − 竖滚动条 ≈ 1680；
    # 6 列 = 6×236 + 5×12 = 1476，留有余量，不会把最后一列挤出可视区。
    COLS_BY_KIND = {"media": 8, "actor": 6, "folder": 6}

    refresh_requested = Signal()      # v1.16.0：随机排序下点「刷新一下」

    def __init__(self, fetch, make_card, total, kind="media", batch=60, unit="部",
                 refreshable=False, parent=None):
        super().__init__(parent)
        self._fetch = fetch                 # (offset, limit) -> list
        self._make = make_card              # item -> QWidget
        self._total = max(0, int(total))
        self._loaded = 0
        self.batch = max(1, int(batch))
        self.unit = unit
        self._cols = self.COLS_BY_KIND.get(kind, 8)
        self._busy = False
        self._scrollbar = None
        self._error = ""
        self._jump_target = None      # v1.30.0：A-Z 跳转目标下标
        self._jump_cb = None

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        self.head = QWidget()
        hl = QHBoxLayout(self.head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)
        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet("color:#c8b892;font-size:12px;")
        hl.addWidget(self.count_lbl)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setMaximumWidth(260)
        self.bar.setVisible(False)      # v1.33.0：默认不显示
        hl.addWidget(self.bar, 1)
        # v1.33.0（反馈 2）：**head 必须默认隐藏**。
        # 原缺陷：`_update_head()` 首行是「未接管工具行就 return」，而演员库 / 导演库 /
        # 最近播放 / 合集这四页的 LazyGrid **都没调 `mark_toolbar_placed()`** →
        # 该函数一次都没跑过 → head 保持 QWidget 的默认可见状态 → 里面的
        # QProgressBar（`maximum` 从未设置、也没有任何进度）在工具行右侧画出一条
        # **空槽灰白细条**，就是用户截图里那条「白条」。
        # 影片墙（_wall_page）与智能推荐（_view_smart）调了 mark_toolbar_placed，
        # 所以它们反而是干净的 —— 与用户「只有这四个界面有」的观察完全吻合。
        self.head.setVisible(False)
        v.addWidget(self.head)

        # v1.18.0：加载更多 / 刷新一下 移出网格头部，由页面统一排到工具行
        # （与 排序/筛选 同行、左排序右加载，视觉对齐）。此处只创建并暴露。
        # v1.21.1（反馈 3）：必须以 self 为 parent 且**默认隐藏** —— 页面若没接管
        # （如 _grid 造的「最近播放 / 演员作品 / 合集预览」网格），_update_head() 里的
        # setVisible(True) 会让这个**无父控件**变成独立顶层小窗：切换页面时闪出一个
        # 只有「加载更多」的窗口。加 parent 兜底 + _toolbar_ready 门闩双保险。
        self._refreshable = bool(refreshable)
        self._toolbar_ready = False
        self.more_btn = QPushButton("加载更多", self)
        self.more_btn.setObjectName("Ghost")
        self.more_btn.setCursor(Qt.PointingHandCursor)
        self.more_btn.clicked.connect(lambda: self._pump())
        self.more_btn.setVisible(False)
        self.refresh_btn = QPushButton("刷新一下", self)
        self.refresh_btn.setObjectName("Ghost")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())
        self.refresh_btn.setVisible(False)

        self._body = QWidget()
        self._grid = QGridLayout(self._body)
        self._grid.setSpacing(12)
        self._grid.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self._body)
        v.addStretch(1)

        if self._total <= 0:
            self.count_lbl.setText("（暂无内容）")
            self.bar.setVisible(False)
            self.more_btn.setVisible(False)
        else:
            self._update_head()
            QTimer.singleShot(0, self._pump)     # 首批延后到事件循环，先让页面画出来

    # ------ 对外 ------
    def attach_scroll(self, scrollbar):
        """挂上外层滚动条：滚到接近底部时自动继续加载。"""
        self._scrollbar = scrollbar
        scrollbar.valueChanged.connect(self._on_scroll)

    def _on_scroll(self, value):
        if self._loaded >= self._total:
            return
        sb = self._scrollbar
        if sb is None or not _qt_alive(self, sb):
            return
        if value >= sb.maximum() - 240:
            self._pump()

    def mark_toolbar_placed(self):
        """v1.21.1（反馈 3）：页面工具行已接管 more_btn/refresh_btn，解除浮动窗门闩。

        _view_recent / _view_actor_detail / _view_collections 等走 _grid() 造的
        「小列表网格」**没有**工具行，按钮必须一直隐藏；只有 _wall_page 这种带工具行
        的网格才调本方法，让按钮按加载进度正常显隐。门闩未开时 _update_head 不碰
        这两个按钮的可见性，从而杜绝「无父控件凭空变成顶层小窗」的故障。
        """
        self._toolbar_ready = True
        if self._refreshable:
            self.refresh_btn.setVisible(True)
        self._update_head()

    def _update_head(self):
        # v1.18.0（反馈 1）：隐藏加载进度读条「正在读取… 已加载 X / Y 部（Z%）」。
        # 数万部的库下长期停在 0% 显得像卡死；改为加载中不显示计数/进度，
        # 仅在全部载入后给出最终「共 N 部」，卡片本身增量出现即是最直观的进度反馈。
        # v1.21.1（反馈 3）：未 mark_toolbar_placed 的网格（_grid 小列表）其按钮
        # 默认隐藏，这里**不**改可见性，避免它们被 setVisible(True) 后变成浮动窗。
        # v1.33.0（反馈 2）：**这里必须主动把 head 收起来，不能只 return。**
        # 演员库 / 导演库 / 最近播放 / 合集都没调 mark_toolbar_placed → 本函数以前
        # 一次都没执行过，head 就一直是可见的，`bar`（QProgressBar，无进度）画出
        # 一条空槽白条挂在工具行右侧。显式 hide 一次，把这条路径钉死。
        if not self._toolbar_ready:
            self.head.setVisible(False)
            return
        if self._loaded >= self._total:
            self.head.setVisible(True)
            self.count_lbl.setText(f"共 {self._total} {self.unit}（已全部载入）")
            self.bar.setVisible(False)
            self.more_btn.setVisible(False)
        else:
            self.head.setVisible(False)     # 加载中不显示计数/进度读条
            self.more_btn.setVisible(True)

    def _pump(self):
        if self._busy or self._loaded >= self._total:
            return
        # v1.24.1：页面可能已被换掉（定时器仍会触发），C++ 实体没了就安静退出，
        # 否则会抛「Internal C++ object (QGridLayout) already deleted」。
        if not _qt_alive(self, self._grid):
            return
        self._busy = True
        try:
            rows = self._fetch(self._loaded, self.batch) or []
        except Exception as e:
            self._error = f"{type(e).__name__}: {e}"
            applog.log(f"读取列表失败：{self._error}", "error")
            rows = []
        for item in rows:
            idx = self._loaded
            card = self._make(item)
            self._grid.addWidget(card, idx // self._cols, idx % self._cols)
            self._loaded += 1
        if not rows:
            self._total = self._loaded          # 到底了
        self._busy = False
        if self._error:
            self.count_lbl.setText(f"读取出错：{self._error}")
            self.more_btn.setVisible(False)
            return
        self._update_head()
        if self._loaded < self._total and self._should_continue():
            # 关键：不在本轮事件里死循环建卡 —— 交给事件循环，界面全程保持可响应
            QTimer.singleShot(1, self._pump)

    def _should_continue(self):
        """够一屏了吗？够就停下，把控制权交回用户（滚动 / 点「加载更多」再继续）。

        这条规则同时兜住两件事：① 首屏一定会被填满，不会出现空白页面；
        ② 5 万条也不会一口气全建成控件（那正是「未响应」的来源）。
        """
        sb = self._scrollbar
        if sb is None:                       # 没挂滚动条（列表页等）→ 保守分页，不全量建卡
            return self._loaded < 600
        return sb.maximum() <= 0

    # ------ A-Z 字母索引跳转（v1.30.0 反馈 4） ------
    def card_at(self, index):
        """第 index 个条目对应的卡片控件（还没建到那里则返回 None）。"""
        if index is None or not (0 <= index < self._loaded):
            return None
        if not _qt_alive(self, self._grid):
            return None
        it = self._grid.itemAtPosition(index // self._cols, index % self._cols)
        return it.widget() if it is not None else None

    def jump_to(self, index, callback=None):
        """滚动定位到第 `index` 个条目。

        目标位置如果还没被渲染出来，这里会**分批补载**（每批交还一次事件循环，
        不让 GUI 线程被几万张卡的建设卡死），到位后用 `callback(card)` 回调，
        由页面去调 `scroll.ensureWidgetVisible(card)`。

        为什么不直接 while 补齐：演员库 5909 人时，一路补到 'Z' 要建几千张卡，
        同步跑会有好几秒的「未响应」，正是 v1.14.0 增量渲染要消灭的东西。
        """
        if not self._total or not _qt_alive(self, self._grid):
            return
        self._jump_target = max(0, min(int(index), self._total - 1))
        self._jump_cb = callback
        QTimer.singleShot(0, self._jump_step)

    def _jump_step(self):
        if not _qt_alive(self, self._grid):
            return
        tgt = getattr(self, "_jump_target", None)
        if tgt is None:
            return
        if self._busy:                    # 常规增量渲染正在跑，让一轮，别两边同时加布局
            QTimer.singleShot(8, self._jump_step)
            return
        if self._loaded > tgt:
            cb, card = self._jump_cb, self.card_at(tgt)
            self._jump_target = None
            self._jump_cb = None
            self._update_head()             # 把「正在跳转…」表头还原
            if cb is not None:
                cb(card)
            return
        self._busy = True
        # v1.30.0：批量取 600（普通增量渲染仍是 self.batch）。
        # 实测 5909 位演员跳到 'Z'：每批 240 → 32s、600 → 26s、2400 → 14s。
        # 开销大头是「每批结束后的整表布局激活」，批越少越省；但单批越大 GUI 阻塞
        # 越久（2400 会一次卡 3 秒），折中取 600（单批 ~0.8s，界面还在动）。
        want = min(max(self.batch, 600), max(0, self._total - self._loaded))
        try:
            rows = self._fetch(self._loaded, want) or []
        except Exception as e:
            applog.log(f"字母跳转读取列表失败：{e}", "error")
            rows = []
        try:
            for item in rows:
                idx = self._loaded
                self._grid.addWidget(self._make(item), idx // self._cols, idx % self._cols)
                self._loaded += 1
        except RuntimeError:
            pass                           # 页面已被换掉，C++ 对象没了 → 安静退出
        if not rows:
            self._total = self._loaded     # 到底了
        self._busy = False
        self._update_head()
        if rows:
            if self._jump_target is not None:
                self._show_jump_progress(tgt)
            QTimer.singleShot(0, self._jump_step)
        else:
            cb, card = self._jump_cb, self.card_at(min(tgt, max(0, self._loaded - 1)))
            self._jump_target = None
            self._jump_cb = None
            if cb is not None:
                cb(card)

    def _show_jump_progress(self, tgt):
        """跳转途中给个明确进度（v1.30.0）。

        v1.18.0 刻意把加载中的计数/读条藏了 —— 数万部的库里百分比长期停在 0%，
        看着像卡死。但字母跳转**知道终点**，写「正在跳转… 3200 / 4806」是真进度，
        比一片死寂强；跳转结束 `_update_head()` 会把表头还原成「共 N 位」。
        """
        if not getattr(self, "_toolbar_ready", False):
            return                          # 小列表网格（_grid）没工具行，别碰按钮可见性
        self.head.setVisible(True)
        self.bar.setVisible(False)
        self.more_btn.setVisible(False)
        self.count_lbl.setText("正在跳转… 已载入 %d / %d" % (self._loaded, tgt + 1))


class ScanWorker(QThread):
    progress = Signal(str)
    done = Signal(dict)
    live = Signal()      # v1.22.0（反馈 4）：扫描进行中就地刷新首页 / 侧栏计数
    # v1.24.0（反馈 11）：结构化进度 (已完成条目数, 预估总条目数, 当前消息)
    # —— 侧边栏媒体库名旁的圆形进度环用它显示「正在刷新 + 百分比」。
    tick = Signal(int, int, str)

    def __init__(self, paths, library_name=None, mode="overwrite",
                 total_hint=None, precount=True):
        super().__init__()
        self.paths = list(paths) if isinstance(paths, (list, tuple)) else [paths]
        self.library_name = library_name
        self.mode = mode
        self._last_live = 0.0
        self._n = 0
        # total_hint：调用方已经数过了（如 FolderScanDialog）→ 别再走一遍磁盘
        self._total = int(total_hint or 0)
        self._precount = bool(precount) and not self._total

    def _count_files(self):
        """预估总量：数一遍视频文件（只走目录、不读文件内容，几万文件约 1~3 秒）。"""
        n = 0
        try:
            for root in self.paths:
                if root and os.path.isdir(root):
                    for _dp, _dn, fns in os.walk(root):
                        for f in fns:
                            if f.lower().endswith(scanner_mod.VIDEO_EXTS):
                                n += 1
        except Exception:
            return 0
        return n

    def run(self):
        if self._precount:
            self._total = self._count_files()
            self._precount = False
        try:
            counts = {"movie": 0, "tvshow": 0, "episode": 0}
            for p in self.paths:
                if p and os.path.isdir(p):
                    c = scanner_mod.scan_library(
                        p, lambda m: self._on_progress(m),
                        library_name=self.library_name, mode=self.mode)
                    for k in counts:
                        counts[k] += c.get(k, 0)
            self.live.emit()          # 扫完再刷一次，确保首页反映最终结果
            self.done.emit(counts)
        except Exception as e:
            self.done.emit({"error": str(e)})

    def _on_progress(self, m):
        self.progress.emit(m)
        # 每来一条进度消息算「处理了 1 个条目」。扫描器基本是「一个文件/一个分集一条消息」，
        # 所以 已完成/预估文件数 是个足够准的百分比（不做精确对齐，进度环只求直观）。
        self._n += 1
        if self._n % 3 == 0 or self._n <= 3:
            self.tick.emit(self._n, self._total, m)
        now = time.monotonic()
        if now - self._last_live >= 1.2:
            self._last_live = now
            self.live.emit()


class CountWorker(QThread):
    """统计媒体库路径下的视频文件数量（供「先确认数量再扫描」用，见 v1.13.0 反馈）。"""
    progress = Signal(str)
    done = Signal(int, int)          # (视频文件数, 命中视频的文件夹数)

    def __init__(self, paths):
        super().__init__()
        self.paths = list(paths or [])

    def run(self):
        vids, folders = 0, 0
        try:
            for root in self.paths:
                if not root or not os.path.isdir(root):
                    continue
                for _dirpath, _dirnames, filenames in os.walk(root):
                    hit = False
                    for f in filenames:
                        if f.lower().endswith(scanner_mod.VIDEO_EXTS):
                            vids += 1
                            hit = True
                    if hit:
                        folders += 1
                    if vids and vids % 200 == 0:
                        self.progress.emit(f"已统计 {vids} 个视频文件…")
        except Exception as e:
            self.progress.emit(f"统计出错：{e}")
        self.done.emit(vids, folders)


class PurgeWorker(QThread):
    """「扫描并删除失效的」：后台检查文件是否还在，删除失效索引（不动磁盘）。"""
    progress = Signal(str)
    done = Signal(dict)

    def __init__(self, library_name, paths):
        super().__init__()
        self.library_name = library_name
        self.paths = paths

    def run(self):
        try:
            res = scanner_mod.prune_missing(
                library_name=self.library_name, roots=self.paths,
                progress=lambda m: self.progress.emit(m))
            self.done.emit(res)
        except Exception as e:
            self.done.emit({"error": str(e)})


class SmartWorker(QThread):
    """智能推荐的后台计算（v1.24.0 反馈 8）。

    普通算法实测 1.5 秒、AI 算法 4.5 秒（4.8 万条索引）—— 放在主线程会**明显卡界面**，
    所以一律丢到线程里跑，完成后再原地换页。
    """

    done = Signal(object)
    progress = Signal(int, int, str)

    def __init__(self, page=1, limit=None, algo=None, library=None, parent=None,
                 guides=None):
        super().__init__(parent)
        self.page = int(page)
        self.limit = limit
        self.algo = algo
        self.library = library
        # v1.34.0（需求 2）：本次临时的引导向量（推荐墙顶部输入框），不落库
        self.guides = list(guides or [])

    def run(self):
        try:
            res = rec_mod.recommend(page=self.page, limit=self.limit, algo=self.algo,
                                    library=self.library,
                                    guides=self.guides,
                                    progress=lambda i, n, m: self.progress.emit(i, n, m))
        except Exception as e:                       # 推荐失败绝不能把界面搞崩
            applog.log(f"智能推荐失败：{type(e).__name__}: {e}", "error")
            res = {"picks": [], "meta": {}, "empty": f"推荐失败：{type(e).__name__}: {e}"}
        self.done.emit(res)


class ScanRing(QWidget):
    """侧边栏媒体库名旁边的**圆形进度环**（v1.24.0 反馈 11）。

    需求：正在扫描的媒体库旁边显示一个像进度环一样的圆形，展示进度、并能一眼看出
    「该库正在刷新」。所以这里不只是显示百分比：扫描中会**转圈**（`QTimer` 驱动弧线旋转），
    扫完/空闲时整个环淡化消失。
    """

    RING = 18

    def __init__(self, parent=None):
        super().__init__(parent)
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


class FolderScanDialog(QDialog):
    """文件夹（媒体库）扫描：先统计数量 → 用户确认 → 扫描并显示进度。

    v1.13.0 反馈：「文件夹中可以针对媒体库右键扫描，可以先确认数量再进行扫描，
    然后显示文件夹的扫描进度。」
    """

    def __init__(self, parent, lib, mode, on_tick=None):
        super().__init__(parent)
        self.lib = lib
        self.mode = mode
        self._scanning = False
        self.result = {}
        # v1.24.0（反馈 11）：把 (已完成, 总数, 消息) 回传给主窗口 → 侧栏媒体库旁的进度环
        self._on_tick = on_tick
        self._vids = 0
        self.setWindowTitle("扫描媒体库")
        self.resize(580, 340)

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(10)

        title = QLabel(f"扫描媒体库「{lib['name']}」")
        title.setStyleSheet("font-size:16px;font-weight:700;color:#e7c86a;")
        v.addWidget(title)

        info = QLabel("模式：" + SCAN_MODE_CN.get(mode, mode) + "\n媒体文件夹：\n"
                      + "\n".join(lib.get("paths", [])[:6]))
        info.setWordWrap(True)
        info.setStyleSheet("color:#a2967f;font-size:11px;")
        v.addWidget(info)

        self.count_lbl = QLabel("正在统计要扫描的文件数量…")
        v.addWidget(self.count_lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)              # 统计阶段：忙碌指示
        v.addWidget(self.bar)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#a2967f;font-size:11px;")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        v.addStretch(1)

        btns = QHBoxLayout()
        self.cancel = QPushButton("取消")
        self.cancel.setObjectName("Ghost")
        self.cancel.clicked.connect(self._on_cancel)
        self.start = QPushButton("开始扫描")
        self.start.setObjectName("Primary")
        self.start.setEnabled(False)
        self.start.clicked.connect(self._start_scan)
        btns.addStretch(1)
        btns.addWidget(self.cancel)
        btns.addWidget(self.start)
        v.addLayout(btns)

        self._counter = CountWorker(lib.get("paths", []))
        self._counter.progress.connect(self.status.setText)
        self._counter.done.connect(self._on_counted)
        self._counter.start()

    def _on_counted(self, vids, folders):
        self._vids = int(vids or 0)
        self.count_lbl.setText(
            f"共发现 {vids} 个视频文件 / {folders} 个文件夹。确认无误后点「开始扫描」。")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.status.setText("")
        self.start.setEnabled(True)

    def _start_scan(self):
        if self._scanning:
            return
        self._scanning = True
        self.start.setEnabled(False)
        self.start.setText("扫描中…")
        self.cancel.setText("停止")
        self.bar.setRange(0, 0)
        applog.log(f"扫描：{self.lib['name']} mode={self.mode} paths={self.lib.get('paths')}")
        self._worker = ScanWorker(self.lib.get("paths", []),
                                  library_name=self.lib["name"], mode=self.mode,
                                  total_hint=self._vids)     # 统计阶段已经数过了，别再走一遍
        self._worker.progress.connect(self.status.setText)
        if self._on_tick:
            self._worker.tick.connect(self._on_tick)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, counts):
        self._scanning = False
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.result = counts or {}
        if self.result.get("error"):
            applog.log(f"扫描出错：{self.lib['name']} {self.result['error']}", "error")
            QMessageBox.warning(self, "扫描出错", self.result["error"])
            self.reject()
            return
        applog.log(f"扫描完成：{self.lib['name']} {self.result}")
        self.accept()

    def _on_cancel(self):
        for attr in ("_counter", "_worker"):
            w = getattr(self, attr, None)
            if w is not None and getattr(w, "isRunning", lambda: False)():
                try:
                    w.terminate()
                    w.wait(2000)
                except Exception:
                    pass
        self.reject()

    def closeEvent(self, e):
        for attr in ("_counter", "_worker"):
            w = getattr(self, attr, None)
            if w is not None and getattr(w, "isRunning", lambda: False)():
                try:
                    w.terminate()
                    w.wait(2000)
                except Exception:
                    pass
        super().closeEvent(e)


class PosterCard(QFrame):
    """影片卡片：图片与标题严格分区不重叠；小字固定两行显示「演员 / 导演」；
    单击选中(粉色流光外轮廓)、双击进入详情。底色与边框均自绘。"""

    def __init__(self, media, on_open, actor_text="", director_text="",
                 on_select=None, parts_count=0, on_play=None, on_fav=None,
                 reason=""):
        super().__init__()
        self.media = media
        # v1.24.0（反馈 8）：智能推荐页把「为什么推它」挂到卡片 tooltip 上
        self._reason = reason or media.get("reason") or ""
        if self._reason:
            self.setToolTip(self._reason)
        self._on_open = on_open
        self._on_select = on_select
        self._on_play = on_play
        self._on_fav = on_fav
        self._selected = False
        self._phase = 0.0
        self._timer = None
        self._parts_count = parts_count
        self.setObjectName("PosterCard")
        self.setCursor(Qt.PointingHandCursor)
        # 「内容卡片」设置：评分 / 年份 / 画质 / 演员 / 导演 都可单独开关（v1.11.1）。
        # 先算出到底要渲染哪几块，再定卡高 —— 否则关掉一块就会露出空白或被裁。
        cc = cfg.get_settings().content_cards
        parts = []
        if cc.get("show_rating", True) and media.get("rating") is not None:
            parts.append("★ %.1f" % media["rating"])
        if cc.get("show_year", True):
            parts.append(str(media.get("year") or "?"))
        if cc.get("show_quality", True) and media.get("quality"):
            parts.append(media["quality"])
        crew_lines = []
        if cc.get("show_actors", True):
            crew_lines.append("演员：%s" % (_clip_text(actor_text) or "—"))
        if cc.get("show_directors", True):
            crew_lines.append("导演：%s" % (_clip_text(director_text) or "—"))
        self.setFixedSize(POSTER_CARD_W,
                          poster_card_height(len(crew_lines), bool(parts)))
        self.setAttribute(Qt.WA_StyledBackground, False)   # 自绘底色，避免被样式背景覆盖
        v = QVBoxLayout(self)
        v.setContentsMargins(_CARD_PAD, _CARD_PAD, _CARD_PAD, _CARD_PAD)
        v.setSpacing(_CARD_SPACING)
        img = QLabel()
        pm = _cached_cover(media.get("poster") or media.get("thumb"), POSTER_W, POSTER_H)
        if pm.isNull():
            pm = placeholder_pixmap(POSTER_W, POSTER_H, text=(media.get("title") or "影")[:1])
        img.setPixmap(pm)
        img.setFixedSize(POSTER_W, POSTER_H)
        img.setStyleSheet("border-radius:6px;")
        v.addWidget(img, alignment=Qt.AlignCenter)
        title = QLabel()
        title.setObjectName("CardTitle")
        # 字号在代码里定死（#CardTitle 的 QSS 只留颜色），这样 fontMetrics 才是准的，
        # _fit_lines 才能正确地把标题压进 2 行、不露出半截第三行。
        _tf = title.font()
        _tf.setPixelSize(13)
        _tf.setWeight(QFont.DemiBold)
        title.setFont(_tf)
        _full_title = media.get("title", "") or ""
        title.setText(_fit_lines(_full_title, POSTER_W, 2, title.fontMetrics()))
        title.setToolTip(_full_title)
        title.setAlignment(Qt.AlignCenter | Qt.AlignTop)
        title.setWordWrap(True)
        title.setFixedHeight(_TITLE_H)
        v.addWidget(title)
        # 副信息：评分 / 年份 / 画质（三项都受内容卡片设置控制；全关则整块不建，卡高相应缩短）
        sub = None
        if parts:
            sub = QLabel("  ·  ".join(parts))
            sub.setObjectName("CardSub")
            sub.setAlignment(Qt.AlignCenter)
            sub.setFixedHeight(_SUB_H)
            v.addWidget(sub)
        # 小字：演员 + 导演（按开关逐行生成；缺数据用「—」占位，行数变化时卡高同步变化）
        crew = None
        if crew_lines:
            crew = QLabel("\n".join(crew_lines))
            crew.setObjectName("CardCrew")
            crew.setStyleSheet("font-size:10px;color:#9b8e7a;line-height:1.4;")
            crew.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            crew.setWordWrap(False)
            crew.setFixedHeight(_LINE_H * len(crew_lines))
            v.addWidget(crew)
        self._facts = crew if crew is not None else _TextSummary()
        for _c in (img, title, sub, crew):
            if _c is not None:
                _c.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # v1.15.0：有分片（选集）的影片在卡片右上角加「选集 N」角标
        if self._parts_count:
            badge = QLabel(f"选集 {self._parts_count}")
            badge.setObjectName("PartsBadge")
            badge.setStyleSheet(
                "background:#d4af37;color:#14110f;font-size:10px;font-weight:bold;"
                "border-radius:3px;padding:1px 5px;")
            badge.setFixedSize(54, 16)
            badge.move(POSTER_CARD_W - 54 - 6, 6)
            badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self._parts_badge = badge

        # v1.17.0（反馈 3）：右下角圆形播放按钮 —— 不必进详情页即可直接播放。
        # 它是**真控件**（上面那些子标签都设了 WA_TransparentForMouseEvents，它没有），
        # 所以点它只会触发播放，不会穿透到卡片变成「选中 / 双击打开详情」。
        # 只有 file_path 确实是视频文件的条目才建按钮（见 playable_media）。
        # v1.21.0（反馈 2）：三角形改几何绘制居中，不再用字符「▶」。
        self.play_btn = None
        if on_play is not None and playable_media(media):
            b = _PlayGlyphButton(self)
            b.setToolTip("直接播放（不进详情页）")
            b.clicked.connect(lambda: self._on_play(self.media))
            b.move(_CARD_PAD + POSTER_W - _PLAY_BTN - 5,
                   _CARD_PAD + POSTER_H - _PLAY_BTN - 5)
            b.raise_()
            self.play_btn = b

        # v1.21.0（反馈 3）：左下角收藏星标，与右下角播放按钮左右对称。
        # 已收藏 = 金色实心五角星；未收藏 = 白描边 + 内部透明。同样是**真控件**。
        self.fav_btn = None
        if on_fav is not None:
            fb = _FavStarButton(self)
            fav_on = bool(media.get("favorite"))
            fb.set_on(fav_on)
            fb.setToolTip("取消收藏" if fav_on else "加入收藏")
            fb.clicked.connect(self._fav_clicked)
            fb.move(_CARD_PAD + 5, _CARD_PAD + POSTER_H - _STAR_BTN - 5)
            fb.raise_()
            self.fav_btn = fb

    def _fav_clicked(self):
        """点左下角星标：交给回调切库（回调会改写 media['favorite']），再据实刷新星标。"""
        if self._on_fav is None:
            return
        self._on_fav(self.media)
        if self.fav_btn is not None:
            on = bool(self.media.get("favorite"))
            self.fav_btn.set_on(on)
            self.fav_btn.setToolTip("取消收藏" if on else "加入收藏")

    # ---------- 选中 / 流光动画 ----------
    def set_selected(self, on):
        if self._selected == on:
            return
        self._selected = on
        # v1.25.0 加固：定时器「只建一次、之后复用」。
        # 原来每次选中都新建一个 QTimer 并覆盖旧引用 —— 旧的那个虽然还挂在卡片下（父对象
        # 是卡片）不泄漏，但只要它被析构，`self._timer` 就成了「已析构的 C++ 对象」，
        # 下一次进来在 `self._timer.stop()` 处抛：
        #   RuntimeError: libshiboken: Internal C++ object (PySide6.QtCore.QTimer) already deleted.
        # 真机 app.log 抓到过（2026-09-21 09:25:33，扫描后 mousePressEvent → _select_card
        # → set_selected）。所以这里 stop 要兜底，真析构了就丢引用、下面按需重建。
        t = self._timer
        if t is not None:
            try:
                t.stop()
            except RuntimeError:
                t = None
                self._timer = None
        if on:
            if self._timer is None:
                self._timer = QTimer(self)
                self._timer.timeout.connect(self._tick)
            self._timer.start(40)
        self.update()

    def _tick(self):
        self._phase += 0.22
        self.update()

    # ---------- 交互：单击选中 / 双击进入 ----------
    def mousePressEvent(self, e):
        if not _qt_alive(self):
            return
        if e.button() == Qt.LeftButton and self._on_select:
            self._on_select(self)
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        # v1.24.1：页面被 _replace_current() 换掉后（LazyGrid 刷新 / 换库 / 换筛选），
        # 队列里可能还压着投给本卡的鼠标事件 —— 此时 C++ 对象已析构，
        # 下面任何 self 的调用（含 super()）都会抛
        # RuntimeError: Internal C++ object (PosterCard) already deleted。
        # 真实日志里抓到过 `main_window.py, in mouseDoubleClickEvent`，故先判存活。
        if not _qt_alive(self):
            return
        if self._on_open:
            self._on_open(self.media)
        super().mouseDoubleClickEvent(e)

    # ---------- 自绘 ----------
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # 内缩 3px：给选中流光留出绘制空间（原先发光画在控件外，被边界裁掉）
        r = self.rect().adjusted(3, 3, -3, -3)
        radius = 12
        p.setBrush(QColor(255, 255, 255, 14))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, radius, radius)
        p.setBrush(Qt.NoBrush)
        if self._selected:
            # v1.25.0（反馈 5）：色相跟「外观 → 高亮色」走，描边加粗、呼吸幅度加大。
            # 这里画的是**内**圈光晕（超出控件边界的会被裁掉）；真正往卡片外扩散的
            # 那层由 _select_card() → _apply_card_glow() 的 QGraphicsDropShadowEffect 负责。
            ar, ag, ab = ACCENT_RGB
            alpha = int(205 + 50 * (0.5 + 0.5 * math.sin(self._phase)))
            p.setPen(QPen(QColor(ar, ag, ab, 95), 7))
            p.drawRoundedRect(r, radius, radius)
            p.setPen(QPen(QColor(ar, ag, ab, alpha), 3.2))
            p.drawRoundedRect(r, radius, radius)
        else:
            p.setPen(QPen(QColor(255, 255, 255, 70), 1.2))
            p.drawRoundedRect(r, radius, radius)
        p.end()


# ---------- 文件夹卡片（v1.17.0，反馈 1） ----------
# 文件夹没有单一海报，封面用该目录下前 2 张海报**拼贴**（Emby 文件夹视图的做法）。
FOLDER_CARD_W = 176
_FOLDER_PAD = 6
FOLDER_COVER_W = FOLDER_CARD_W - _FOLDER_PAD * 2      # 164
FOLDER_COVER_H = 108
FOLDER_CARD_H = _FOLDER_PAD * 2 + FOLDER_COVER_H + 4 + 18 + 4 + 16


def folder_cover_pixmap(posters, w, h):
    """文件夹卡片封面：把最多 2 张海报并排拼成一块（圆角裁剪 + 中缝暗线）。"""
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, w, h), 7, 7)
    p.setClipPath(clip)
    p.fillRect(0, 0, w, h, QColor("#1d1813"))
    paths = [x for x in (posters or []) if x][:2]
    if not paths:
        p.drawPixmap(0, 0, placeholder_pixmap(w, h, text="夹"))
    elif len(paths) == 1:
        p.drawPixmap(0, 0, _cached_cover(paths[0], w, h))
    else:
        half = w // 2
        for i, pp in enumerate(paths):
            sw = (w - half) if i else half          # 右侧那块补足余数像素
            p.drawPixmap(i * half, 0, _cached_cover(pp, sw, h))
        p.setPen(QPen(QColor(0, 0, 0, 130), 2))
        p.drawLine(half, 0, half, h)
    p.end()
    return pm


class FolderCard(QFrame):
    """文件夹卡片：拼贴封面 + 目录名 + 「共 N 部」。

    单击进入该目录的影片墙；右键沿用媒体库扫描菜单；目录不存在时封面右上角标红「!」。
    底色 / 边框自绘（与 PosterCard 同一套路：`WA_StyledBackground=False` + paintEvent）。
    """

    def __init__(self, name, path, count, posters, on_open, on_menu=None, missing=False):
        super().__init__()
        self.name = name
        self.path = path
        self._on_open = on_open
        self._on_menu = on_menu
        self._missing = bool(missing)
        self._hover = False
        self.setObjectName("FolderCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(FOLDER_CARD_W, FOLDER_CARD_H)
        self.setAttribute(Qt.WA_StyledBackground, False)

        v = QVBoxLayout(self)
        v.setContentsMargins(_FOLDER_PAD, _FOLDER_PAD, _FOLDER_PAD, _FOLDER_PAD)
        v.setSpacing(4)
        img = QLabel()
        img.setPixmap(folder_cover_pixmap(posters, FOLDER_COVER_W, FOLDER_COVER_H))
        img.setFixedSize(FOLDER_COVER_W, FOLDER_COVER_H)
        v.addWidget(img, alignment=Qt.AlignCenter)
        title = QLabel(name)
        title.setStyleSheet("color:#e2685a;font-size:12px;font-weight:600;")
        title.setAlignment(Qt.AlignCenter)
        title.setFixedHeight(18)
        v.addWidget(title)
        sub = QLabel(f"共 {count} 部")
        sub.setStyleSheet("color:#a2967f;font-size:11px;")
        sub.setAlignment(Qt.AlignCenter)
        sub.setFixedHeight(16)
        v.addWidget(sub)
        for _c in (img, title, sub):
            _c.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        tip = [name]
        if path:
            tip.append(path)
        else:
            tip.append("（该媒体库未设置媒体文件夹）")
        if self._missing:
            tip.append("⚠ 目录不存在（可能已搬迁或盘符未挂载）")
        self.setToolTip("\n".join(tip))
        title.setToolTip("\n".join(tip))

        if self._missing:
            warn = QLabel("!", self)
            warn.setStyleSheet("background:#a32a20;color:#ffffff;font-size:11px;"
                               "font-weight:700;border-radius:8px;")
            warn.setAlignment(Qt.AlignCenter)
            warn.setFixedSize(16, 16)
            warn.move(FOLDER_CARD_W - _FOLDER_PAD - 16, _FOLDER_PAD + 2)
            warn.setToolTip("目录不存在（可能已搬迁或盘符未挂载）")
            warn.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        # 同 PosterCard：合集墙也是 LazyGrid，换页后残留事件可能投给已析构的卡。
        if not _qt_alive(self):
            return
        if e.button() == Qt.LeftButton and self._on_open:
            self._on_open(self.path, self.name)
        super().mousePressEvent(e)

    def contextMenuEvent(self, e):
        if not _qt_alive(self):
            return
        if self._on_menu:
            self._on_menu(self, e.pos())
        else:
            super().contextMenuEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 24 if self._hover else 14))
        p.drawRoundedRect(r, 10, 10)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(192, 57, 43, 205) if self._hover else QColor(255, 255, 255, 46),
                      1.4 if self._hover else 1.0))
        p.drawRoundedRect(r, 10, 10)
        p.end()


# 演员卡尺寸与间距（紧凑定高：内容恒满，不再出现 v1.10.0 那样的大片空白）
ACTOR_CARD_W = 236
ACTOR_CARD_H = 160          # v1.22.0（反馈 5）：加高，保证姓名换行 + 六项信息 + 右上角☆/▲ 都不被裁
_ACTOR_PAD = 12
_ACTOR_AVATAR = 56
_ACTOR_BTN = 26
# 六项信息（状态单独做成彩色徽标）：标签 -> (行, 列, 跨列数)
# 「三围」的值形如「胸92·腰58·臀89」，比半边卡宽还长 —— 早期放右列会被硬裁掉尾巴，
# 所以让它**整行跨两列**（可用的整行宽 ≈ 212px，实测文本 ≈ 133px，留足余量）。
# v1.30.0 反馈 1：右列「胸围」换成「作品」（参演片数）。理由：「三围」里已经带了胸围
# （胸92·腰58·臀89），单列出来是冗余；而「作品数」是判断演员是否值得点进去的第一信息。
# 卡片仍是 3 行、高度不变 → 不用动 ACTOR_CARD_H / DirectorCard 那一套定高算式。
_ACTOR_FACTS = (("出生", 0, 0, 1), ("出身地", 0, 1, 1), ("身高", 1, 0, 1),
                ("作品", 1, 1, 1), ("三围", 2, 0, 2))


class _TextSummary:
    """聚合文本片段并提供 .text()：用于演员卡 tooltip 与冒烟断言。"""

    def __init__(self):
        self._parts = []

    def add(self, s):
        if s:
            self._parts.append(str(s))

    def text(self) -> str:
        return "\n".join(self._parts)


class ActorCard(QFrame):
    """演员卡片：头像 + 六项信息平铺；右上角 ☆收藏 / ▲置顶；
    现役绿 / 退役黄；选中粉色流光高亮。底色与边框均自绘。

    v1.11.0 修复两处「卡片异常」：
    - ☆/▲ 看不见 —— 全局 QSS `QPushButton{padding:7px 14px}` 把 26×26 按钮的
      内容区压成负数，字形被完全裁掉。现给按钮补 `padding:0`，并改成卡片右上角
      浮动定位（不参与布局），与需求「右上角小三角」一致。
    - 大片空白 —— 原先固定高 244 而 facts 常为空（真机库 85 位演员无刮削数据）。
      现改为紧凑定高，六项信息**恒显示**，缺数据统一用「—」占位。
    """

    #: 卡面显示哪几项：(标签, 行, 列, 跨列数)。子类 `DirectorCard` 换掉这一组
    #: （导演不显示生日 / 出身地 / 身高 / 胸围 / 三围 —— v1.24.0 反馈 10）。
    FACTS = _ACTOR_FACTS
    #: 卡片定高。子类 `DirectorCard` 的事实区比演员卡少两行，覆盖此值压低卡片
    #: （v1.28.1 反馈：导演去掉「简介」后卡片高度同步收紧）。
    CARD_H = ACTOR_CARD_H

    def __init__(self, person, on_open, on_fav, on_pin, on_select, main_win):
        super().__init__()
        self.person = person
        self._on_open = on_open
        self._on_fav = on_fav
        self._on_pin = on_pin
        self._on_select = on_select
        self._main = main_win
        self._selected = False
        self._phase = 0.0
        self._timer = None
        self.setObjectName("ActorCard")
        self.setFixedSize(ACTOR_CARD_W, self.CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(_ACTOR_PAD, 10, _ACTOR_PAD, 10)
        v.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(10)
        self._avatar = QLabel()
        # 头像走缓存：演员库翻页/重绘时不再反复读盘 + 裁剪（v1.14.0）。
        # v1.30.0 再进一步：改成「画到才读」—— 这里只摆占位圆，真正的读盘推迟到
        # 卡片第一次被绘制（= 真的被用户看见）时，见 `_ensure_avatar`。
        self._avatar_path = (self.person.get("thumb")
                             or self.person.get("photo_path") or "").strip()
        self._avatar_pending = bool(self._avatar_path)
        self._avatar.setPixmap(circle_pixmap(None, _ACTOR_AVATAR))
        self._avatar.setFixedSize(_ACTOR_AVATAR, _ACTOR_AVATAR)
        head.addWidget(self._avatar)
        col = QVBoxLayout()
        col.setSpacing(3)
        col.setContentsMargins(0, 2, _ACTOR_BTN * 2 + 10, 0)   # 右侧留给右上角浮动按钮
        self._name = QLabel(self.person.get("name", ""))
        self._name.setStyleSheet("font-size:15px;font-weight:700;color:#f3e8d6;")
        self._name.setWordWrap(True)
        col.addWidget(self._name)
        self._status_badge = QLabel()
        self._status_badge.setFixedHeight(16)
        col.addWidget(self._status_badge)
        head.addLayout(col, 1)
        v.addLayout(head)

        # 六项信息：恒显示（缺 → —），两列对齐
        self._fact_cells = {}
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(9)
        grid.setVerticalSpacing(4)
        for key, r, c, span in self.FACTS:
            cell = QLabel()
            cell.setTextFormat(Qt.RichText)
            cell.setWordWrap(False)
            cell.setFixedHeight(17)
            self._fact_cells[key] = cell
            grid.addWidget(cell, r, c, 1, span)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        v.addLayout(grid)
        v.addStretch(1)

        # ☆ 收藏 / ▲ 置顶：浮在卡片右上角（不参与布局，避免被全局按钮样式挤压）
        # 用 △/▲（GB2312 几何符号，中文字体必有）；不用 ▶ —— 部分字体缺该字形会渲染成方框
        self._pin = QPushButton("△", self)
        self._star = QPushButton("☆", self)
        for b, tip, slot in ((self._pin, "置顶", self._toggle_pin),
                             (self._star, "收藏", self._toggle_fav)):
            b.setFixedSize(_ACTOR_BTN, _ACTOR_BTN)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            b.clicked.connect(slot)
        self._star.move(ACTOR_CARD_W - 10 - _ACTOR_BTN, 10)
        self._pin.move(ACTOR_CARD_W - 10 - _ACTOR_BTN * 2 - 4, 10)
        self._star.raise_()
        self._pin.raise_()

        for _c in (self._avatar, self._status_badge, self._name):
            _c.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        for _c in self._fact_cells.values():
            _c.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._facts = _TextSummary()
        self._update_texts()

    def _fact_values(self) -> dict:
        """卡面各项的取值（缺 → 空串，由 `_set_fact` 统一显示成「—」）。"""
        p = self.person
        meta = _parse_meta(p.get("meta"))       # meta 经清洗，兼容老库里的 HTML 乱码
        size = meta.get("尺寸", "")
        bust, waist, hip = _parse_size(size)
        cup = _parse_cup(size, *(meta.get(k, "") for k in _CUP_META_KEYS))
        bits = []
        if bust:
            bits.append("胸" + str(bust))
        if waist:
            bits.append("腰" + str(waist))
        if hip:
            bits.append("臀" + str(hip))
        # v1.31.0（反馈 2）：罩杯写在三围最前面（`H 胸88·腰56·臀84`），由 `_set_fact`
        # 单独加粗。仅「有字母没尺寸」时也显示字母本身 —— 罩杯本身就是有效信息。
        torso = "·".join(bits)
        if cup:
            torso = (cup + " " + torso) if torso else cup
        # 作品数：SELECT 里用 COUNT(mp.media_id) 聚合出来的左连接计数，没戏就是 0
        works = p.get("works") or p.get("works_n") or 0
        try:
            works_n = int(works)
        except (TypeError, ValueError):
            works_n = 0
        return {
            "出生": (p.get("birthday") or "").strip(),
            "出身地": _clean_meta_value(meta.get("出身地") or meta.get("出生地") or ""),
            "身高": _clean_meta_value(meta.get("身高") or ""),
            "三围": torso,
            "作品": ("%d 部" % works_n) if works_n > 0 else "",
        }

    #: 「三围」值开头的罩杯（`H 胸88·…` 里的 `H`）—— 单独加粗，其余原样
    _CUP_LEAD_RE = re.compile(r"^([A-Za-z]{1,3})\s+(\S.*)$")

    def _set_fact(self, key, value):
        """把一项信息写进单元格（标签暗色 + 值亮色；空值统一「—」）。

        v1.31.0（反馈 2）：「三围」开头的罩杯字母**加粗并提亮**，其余照旧。
        注意富文本里的颜色必须显式写进 `<span style="color:…">`（继承不到 QSS）。
        """
        val = str(value).strip() if value else "—"
        inner = html.escape(val)
        if key == "三围":
            m = self._CUP_LEAD_RE.match(val)
            if m:
                inner = ('<b><span style="color:#e8d7ab;">%s</span></b>&nbsp;%s'
                         % (html.escape(m.group(1)), html.escape(m.group(2))))
        self._fact_cells[key].setText(
            '<span style="color:#7b7160;">%s</span>'
            '&nbsp;<span style="color:#c9bda7;">%s</span>'
            % (key, inner))

    def _update_texts(self):
        p = self.person
        status = _person_status(p)
        if status == "现役":
            self._status_badge.setText("● 现役")
            self._status_badge.setStyleSheet("color:#7fdca0;font-size:11px;font-weight:700;")
        elif status == "退役":
            self._status_badge.setText("● 退役")
            self._status_badge.setStyleSheet("color:#e8d27a;font-size:11px;font-weight:700;")
        else:
            self._status_badge.setText("● 未知")
            self._status_badge.setStyleSheet("color:#9b8e7a;font-size:11px;")
        # padding:0 是关键：全局 QPushButton 有 `padding:7px 14px`，会把 26×26
        # 按钮的内容区压成负数 → 字形被完全裁掉（v1.10.0 ☆/▲ 看不见的根因）
        base = "padding:0;min-width:0;border:none;background:transparent;"
        self._star.setText("★" if p.get("favorite") else "☆")
        self._star.setStyleSheet(base + "font-size:15px;color:%s;"
                                 % ("#f3d9a0" if p.get("favorite") else "#9b8e7a"))
        self._pin.setText("▲" if p.get("pinned") else "△")
        self._pin.setStyleSheet(base + "font-size:13px;color:%s;"
                                % ("#f3d9a0" if p.get("pinned") else "#9b8e7a"))
        facts = self._fact_values()
        summ = _TextSummary()
        for key, _r, _c, _span in self.FACTS:
            self._set_fact(key, facts.get(key, ""))
            summ.add("%s %s" % (key, facts.get(key) or "—"))
        self._facts = summ
        self.setToolTip("%s\n%s\n%s" % (p.get("name") or "",
                                        self._status_badge.text(), summ.text()))

    def _ensure_avatar(self):
        """真正把头像读进来（只调一次）。

        为什么要拖到绘制时才读：演员库 5909 人时，A-Z 索引条跳到 'Z' 要一路补建
        4800 张卡；原先在 `_build` 里同步读 NAS 上的 JPEG（冷读实测 ~5.7 ms/张），
        整趟要 59 秒看着像卡死。改成「画到才读」后，没被看见的卡根本不读盘 ——
        跳转、首屏、滚动都一起变快（缓存命中后仍是 0 成本，见 `_cached_avatar`）。
        """
        if not self._avatar_pending:
            return
        self._avatar_pending = False           # 先落闸：读失败也不再重试，避免滚动反复读坏图
        if not _qt_alive(self, self._avatar):
            return
        try:
            pm = _cached_avatar(self._avatar_path, _ACTOR_AVATAR)
        except Exception as e:                  # 单张图坏了不能拖垮整页
            applog.log("头像读取失败：%s" % e, "warning")
            return
        if pm is not None and _qt_alive(self, self._avatar):
            self._avatar.setPixmap(pm)

    def _toggle_fav(self):
        self._on_fav(self.person)

    def _toggle_pin(self):
        self._on_pin(self.person)

    # ---------- 选中 / 流光动画 ----------
    def set_selected(self, on):
        if self._selected == on:
            return
        self._selected = on
        # v1.25.0 加固：定时器「只建一次、之后复用」。
        # 原来每次选中都新建一个 QTimer 并覆盖旧引用 —— 旧的那个虽然还挂在卡片下（父对象
        # 是卡片）不泄漏，但只要它被析构，`self._timer` 就成了「已析构的 C++ 对象」，
        # 下一次进来在 `self._timer.stop()` 处抛：
        #   RuntimeError: libshiboken: Internal C++ object (PySide6.QtCore.QTimer) already deleted.
        # 真机 app.log 抓到过（2026-09-21 09:25:33，扫描后 mousePressEvent → _select_card
        # → set_selected）。所以这里 stop 要兜底，真析构了就丢引用、下面按需重建。
        t = self._timer
        if t is not None:
            try:
                t.stop()
            except RuntimeError:
                t = None
                self._timer = None
        if on:
            if self._timer is None:
                self._timer = QTimer(self)
                self._timer.timeout.connect(self._tick)
            self._timer.start(40)
        self.update()

    def _tick(self):
        self._phase += 0.22
        self.update()

    # ---------- 交互：单击选中 / 双击查看 ----------
    def mousePressEvent(self, e):
        if not _qt_alive(self):
            return
        if e.button() == Qt.LeftButton and self._on_select:
            self._on_select(self)
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        # 同 PosterCard：换页/重排后队列里残留的鼠标事件可能投给已析构的卡。
        if not _qt_alive(self):
            return
        if self._on_open:
            self._on_open(self.person)
        super().mouseDoubleClickEvent(e)

    # ---------- 自绘（现役绿 / 退役黄 / 选中粉） ----------
    def paintEvent(self, e):
        # v1.30.0：头像按需加载 —— 只有真被画出来（= 用户看得见）的卡才读盘。
        # 放在 QPainter 之前：setPixmap 会再触发一次重绘，那时 pending 已落闸，不会递归。
        if self._avatar_pending:
            self._ensure_avatar()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # 内缩 3px：给选中流光留出绘制空间（原先发光画在控件外被裁掉）
        r = self.rect().adjusted(3, 3, -3, -3)
        radius = 12
        status = _person_status(self.person)
        # 底色/描边给足对比度，让「现役绿 / 退役黄」在小卡上一眼可辨
        if status == "现役":
            base, border = QColor(46, 122, 74, 92), QColor(116, 220, 140, 205)
        elif status == "退役":
            base, border = QColor(148, 120, 38, 86), QColor(236, 202, 96, 210)
        else:
            base, border = QColor(255, 255, 255, 14), QColor(255, 255, 255, 70)
        p.setBrush(base)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, radius, radius)
        p.setBrush(Qt.NoBrush)
        if self._selected:
            # v1.25.0（反馈 5）：与 PosterCard 同一套规则（高亮色 + 加粗 + 外发光）
            ar, ag, ab = ACCENT_RGB
            alpha = int(205 + 50 * (0.5 + 0.5 * math.sin(self._phase)))
            p.setPen(QPen(QColor(ar, ag, ab, 95), 7))
            p.drawRoundedRect(r, radius, radius)
            p.setPen(QPen(QColor(ar, ag, ab, alpha), 3.2))
            p.drawRoundedRect(r, radius, radius)
        else:
            p.setPen(QPen(border, 1.4))
            p.drawRoundedRect(r, radius, radius)
        p.end()


# 导演卡的两项（**刻意不含** 生日 / 出身地 / 身高 / 胸围 / 三围 —— v1.24.0 反馈 10；
# v1.28.1 反馈：再去掉「简介」——真机 1218 位导演的 bio 几乎全空，只留一排「—」白占高度）
_DIRECTOR_FACTS = (("作品", 0, 0, 1), ("别名", 0, 1, 1))
# 事实区只剩 1 行（演员卡 3 行）→ 卡片压低 2 行：每行 = 单元格高 17 + 网格竖向间距 4。
# 余量核对：上下边距 20 + 头部（最长两行姓名）59 + 间距 8 + 事实行 17 + 间距 8 = 112 < 118。
DIRECTOR_CARD_H = ACTOR_CARD_H - 2 * (17 + 4)     # 160 - 42 = 118


class DirectorCard(ActorCard):
    """导演卡（v1.24.0 反馈 10）：外形与演员卡完全一致（头像 / 姓名 / 状态 / ☆ / ▲），
    但信息区换成 **作品数 / 别名**（v1.28.1 起去掉「简介」，卡片高度随之收紧）。

    为什么不用演员那五项：导演的 nfo 里这些字段基本是空的（实测 1218 位导演几乎全空），
    照搬只会得到五排「—」。导演真正有信息量的是「拍过多少部 / 别名」。
    """

    FACTS = _DIRECTOR_FACTS
    CARD_H = DIRECTOR_CARD_H

    def _fact_values(self) -> dict:
        p = self.person
        works = p.get("works") or p.get("works_n") or ""
        return {
            "作品": (f"{int(works)} 部" if str(works).isdigit() else ""),
            "别名": (p.get("alias") or "").strip(),
        }


class AboutDialog(QDialog):
    """「关于」对话框（v1.32.0 反馈 4：内容重写）。

    设计口径
    --------
    * **只放真源里的东西** —— 名称 / 标语 / 版本 / 版权 / 链接全部从 `version.py` 取，
      这里一个字符串都不硬编码（改品牌只改 version.py，两处一起变）。
    * **把「这个软件能干什么」写清楚** —— 第一次打开的人从「关于」就能看懂八个模块各自
      干什么、数据存在哪、要不要联网。旧版只有三行简介。
    * **免责与隐私如实写明** —— 本软件不联网刮削、不上传任何东西、AI 完全本地；
      「仅供个人已合法持有的本地媒体文件管理使用」这句必须有。
    """

    #: 「关于」里列的功能模块 —— (标题, 一句话说明)。顺序与「工具」导航分组一致。
    SECTIONS = [
        ("媒体库", "海报墙 / 列表双视图，支持多媒体库、文件夹、合集、分页与随机排序；"
                   "5 万片规模下靠 SQL 下推 + 增量渲染保持流畅。"),
        ("演员与导演", "独立 people 表（Emby 模式），可从演员反查全部作品、按作品数排序；"
                       "卡片直接显示三围与罩杯。"),
        ("智能推荐", "本地离线推荐：八维画像 + 可选向量编辑；接入本地 Ollama 时可用 AI 增强。"),
        ("手动修改", "不改 nfo 也能修：17 项字段 + 海报/缩略图/背景图三槽位上传，写回并同步索引。"),
        ("标签优化", "批量清洗标题里的冗余标签（普通算法 / AI 算法二选一），改动前自动备份。"),
        ("重复检测", "跨目录找同一部片子的多份副本，算出可回收空间；AI 复核给保留建议。"),
        ("演员检测", "揪出「不同艺名其实是同一人」，逐簇给判定依据，由你确认后关联合并。"),
        ("图像检测", "找出缺图与截断图（JPEG 缺 EOI / PNG 缺 IEND），逐个上传替换。"),
        ("画像概览与日志", "八维偏好雷达、高频榜、分布与共现分析；索引 / 日志可一键导出。"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 %s" % ver.APP_NAME)
        self.setMinimumWidth(660)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(8)

        head = QLabel("%s　%s" % (ver.APP_NAME, ver.VERSION))
        head.setStyleSheet("font-size:19px;font-weight:700;color:#f7e3b4;")
        v.addWidget(head)
        sub = QLabel("%s / %s" % (ver.APP_NAME_EN, ver.FULL_VERSION))
        sub.setStyleSheet("color:#a2967f;font-size:12px;")
        v.addWidget(sub)

        # Slogan 走 QLabel#Slogan 的鎏金样式（启动画面共用同一句）
        sl = QLabel("%s　·　%s" % (ver.SLOGAN_CN, ver.SLOGAN_EN))
        sl.setObjectName("Slogan")
        sl.setWordWrap(True)
        v.addWidget(sl)

        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setMarkdown(self._body())
        tb.setStyleSheet("background:#1c1714;color:#e8e0d4;"
                         "border:1px solid #2a221c;border-radius:6px;")
        tb.setMinimumHeight(380)
        v.addWidget(tb, 1)

        # v1.33.0（反馈 4）：作者联系图标栏 —— 四个**自绘**小图标（不依赖任何外部
        # 图片文件，onefile exe 里最省事），点一下就用系统浏览器 / 邮件客户端打开。
        v.addWidget(self._contact_bar())

        ok = QPushButton("确定")
        ok.setObjectName("Primary")
        ok.setCursor(Qt.PointingHandCursor)
        ok.clicked.connect(self.accept)
        v.addWidget(ok, alignment=Qt.AlignRight)

    # ---------------------------------------------------------------- 联系图标
    # v1.33.1（反馈 3）：github / bilibili / weibo 三枚改为**真实品牌图形** ——
    # 用户提供的官方 logo 剪影（RGBA 300×300、填充近白、alpha 为遮罩）以 base64
    # 内联在本文件里，运行时按 `tint` 重新着色（CompositionMode_SourceIn）。
    #
    # 为什么内联 base64 而不是 --add-data 图片：单文件 exe 里 `sys._MEIPASS` 路径
    # 在 v1.23.0 图标链上踩过一次（打包后 404 → 空白图标），内联字符串则**打包与
    # 直接跑源码完全同一条路径**，没有任何资源定位风险。三张图合计约 12KB。
    _CONTACT_LOGO_B64 = {
        # github  (github-1.png)  2266 bytes PNG → 3024 chars b64
        "github": (
            "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"
        ),
        # bilibili  (bilibili-1.png)  3398 bytes PNG → 4532 chars b64
        "bilibili": (
            "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"
        ),
        # weibo  (weibo-1.png)  3417 bytes PNG → 4556 chars b64
        "weibo": (
            "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"
        ),
    }
    _CONTACT_LOGO_CACHE = {}

    @classmethod
    def _contact_logo_pixmap(cls, kind, size, tint):
        """把内联的品牌 logo 剪影按 `tint` 着色成 `size×size` 的 QPixmap。"""
        key = (kind, int(size), tint)
        hit = cls._CONTACT_LOGO_CACHE.get(key)
        if hit is not None:
            return hit
        raw = QByteArray(base64.b64decode(cls._CONTACT_LOGO_B64[kind]))
        img = QImage()
        img.loadFromData(raw, "PNG")
        if img.isNull():
            return None
        # 先按原图长边缩放到目标尺寸（保持比例），再居中贴到 size×size 画布
        img = img.scaled(int(size), int(size),
                         Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm = QPixmap(int(size), int(size))
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        x = (int(size) - img.width()) // 2
        y = (int(size) - img.height()) // 2
        p.drawImage(x, y, img)
        # 关键一步：把颜色**整体替换**为目标色，只保留原图 alpha ——
        # 源 logo 是近白填充，直接画在浅底按钮上会「看不见」。
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(QRect(0, 0, int(size), int(size)), QColor(tint))
        p.end()
        cls._CONTACT_LOGO_CACHE[key] = pm
        return pm

    @classmethod
    def _contact_icon(cls, kind, size=22, tint="#e8e0d4"):
        """按 `version.CONTACTS` 的 key 生成联系图标（QIcon）。

        - github / bilibili / weibo：用户提供的官方 logo 剪影（内联 base64）着色后出图；
        - mail：仍用 QPainterPath 自绘信封 —— 邮箱没有「官方 logo」，自绘反而是最
          干净的做法（也避免和 Gmail / QQ 邮箱商标混淆）。

        自绘的历史理由仍然成立：用字符图标（"" "✉"）会因字体缺字变方块，且字形
        side bearing 不对称永远不对齐（v1.21.0 播放键同款坑）。
        """
        if kind in cls._CONTACT_LOGO_B64:
            try:
                pm = cls._contact_logo_pixmap(kind, size, tint)
                if pm is not None and not pm.isNull():
                    return QIcon(pm)
            except Exception as e:                       # 兜底：解码失败退回自绘
                applog.log("联系图标加载失败 %s：%s" % (kind, e), "error")
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        col = QColor(tint)
        s = float(size)
        if kind == "mail":
            # 信封：一个方框 + 一个 V 形折线
            p.setPen(Qt.NoPen); p.setBrush(col)
            p.drawRoundedRect(QRectF(s * 0.08, s * 0.22, s * 0.84, s * 0.58),
                              s * 0.08, s * 0.08)
            pen = QPen(QColor("#1c1714")); pen.setWidthF(max(1.4, s * 0.075))
            pen.setJoinStyle(Qt.RoundJoin); p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawPolyline(QPolygonF([QPointF(s * 0.14, s * 0.30), QPointF(s * 0.50, s * 0.56),
                                      QPointF(s * 0.86, s * 0.30)]))
        p.end()
        return QIcon(pm)

    def _contact_bar(self):
        """四个联系图标 + 一行说明，居中排一行。"""
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 2, 0, 0)
        h.setSpacing(10)
        lbl = QLabel("联系作者：")
        lbl.setStyleSheet("color:#a2967f;font-size:12px;")
        h.addWidget(lbl)
        for kind, name, url in ver.CONTACTS:
            b = QPushButton()
            b.setObjectName("ContactIcon")
            b.setFixedSize(34, 30)
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(self._contact_icon(kind))
            b.setIconSize(QSize(22, 22))
            # 邮箱显示明文，方便直接抄走；其余显示跳转地址
            shown = ver.CONTACT_MAIL if kind == "mail" else url
            b.setToolTip("%s\n%s" % (name, shown))
            b.clicked.connect(lambda _c, u=url: self._open_contact(u))
            h.addWidget(b)
        mail = QLabel("<a href='mailto:%s' style='color:#d4af37;text-decoration:none;'>%s</a>"
                      % (ver.CONTACT_MAIL, ver.CONTACT_MAIL))
        mail.setOpenExternalLinks(True)
        mail.setStyleSheet("font-size:12px;")
        mail.setCursor(Qt.PointingHandCursor)
        h.addWidget(mail)
        h.addStretch(1)
        return box

    @staticmethod
    def _open_contact(url):
        """打开外链 —— 失败**只记日志、绝不弹框**（与主窗 open_url 同口径）。"""
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            applog.log("打开联系链接失败 %s：%s" % (url, e), "error")

    @classmethod
    def _body(cls) -> str:
        lines = []
        lines.append("**%s / %s**" % (ver.APP_NAME, ver.APP_NAME_EN))
        lines.append("")
        # 正文里也要有版本 —— 对话框头部那行只在窗口上，用户复制正文 / 截图时
        # 就丢了版本信息，报 bug 时最常见的就是「你用的哪版」对不上。
        lines.append("版本：`%s`　·　内部构建号 `%s`" % (ver.FULL_VERSION, ver.BUILD))
        lines.append("")
        lines.append("*%s — %s*" % (ver.SLOGAN_CN, ver.SLOGAN_EN))
        lines.append("")
        lines.append("## 这是什么")
        lines.append("")
        lines.append("一个**纯本地**的影视收藏管理桌面软件 —— 不依赖浏览器、不起 Web 服务，"
                     "海报墙、演员关联、批量整理全部在你自己机器上完成。"
                     "设计上借鉴了 Emby 的观影体验与 tinyMediaManager 的本地管理思路，"
                     "但**刮削已阉割**：只读取你已经刮削好的 nfo，不主动联网抓取。")
        lines.append("")
        lines.append("## 功能一览")
        lines.append("")
        for title, desc in cls.SECTIONS:
            lines.append("- **%s**：%s" % (title, desc))
        lines.append("")
        lines.append("## 隐私与联网")
        lines.append("")
        lines.append("- **不联网刮削**：软件本身不会向任何刮削站点发起请求，"
                     "所有资料来自你本地已有的 nfo 文件。")
        lines.append("- **AI 完全本地**：普通算法之外的可选 AI 复核走本机 Ollama（默认端口 11434），"
                     "**全程不出网**；模型没装时自动降级为普通算法。")
        lines.append("- **数据留在本机**：索引是程序目录下 `index_data/media_center.db` 一个 SQLite 文件，"
                     "头像在同目录的图片缓存里；除你手动点「导出」外，任何数据都不会离开这台机器。")
        lines.append("- **AI 收到的内容做过脱敏**：重复检测 / 图像检测送进模型的只有"
                     "体积、时长、画质、槽位这类判定所需的量，**不含盘符、目录名、番号与文件名**。")
        lines.append("")
        lines.append("## 技术栈")
        lines.append("")
        lines.append("- Python 3.13 + PySide6（Qt 6）原生界面，无浏览器内核")
        lines.append("- SQLite 单文件索引；SQL 下推 + 增量渲染支撑 5 万片规模")
        lines.append("- PyInstaller `--onefile --windowed` 打包为**单文件 exe**，免安装、免运行库")
        lines.append("- 首次启动即自动建库，不需要任何配置")
        lines.append("")
        lines.append("## 界面语言")
        lines.append("")
        lines.append("19 种：简体中文（基准）、英语、日语、韩语、西班牙语、印地语、阿拉伯语、"
                     "葡萄牙语、俄语、德语、法语、意大利语、土耳其语、荷兰语、波兰语、"
                     "瑞典语、泰语、越南语、印尼语。在「工具 → 个性化设置 → 外观 → 界面语言」切换，"
                     "**立即生效、无需重启**。")
        lines.append("")
        lines.append("## 使用须知")
        lines.append("")
        lines.append("- 本软件**仅供个人对自己已合法持有的本地媒体文件做整理与浏览**。")
        lines.append("- 软件不提供、不下载、不分发任何影视内容，删除类操作一律由你自己确认后执行。")
        lines.append("- " + ver.LICENSE_NOTE)
        lines.append("- " + ver.COPYRIGHT)
        lines.append("")
        lines.append("## 链接")
        lines.append("")
        lines.append("- 项目主页：<%s>" % ver.REPO_URL)
        lines.append("- 作者主页：<%s>" % ver.AUTHOR_URL)
        lines.append("")
        lines.append("### 联系作者")
        lines.append("")
        # v1.33.0（反馈 4）：正文里也列一遍 —— 图标栏是给「看」的，这里是给「抄」的
        # （用户复制正文 / 截图时链接不会丢）。
        for _kind, _name, _url in ver.CONTACTS:
            if _kind == "mail":
                lines.append("- %s：`%s`" % (_name, ver.CONTACT_MAIL))
            else:
                lines.append("- %s：<%s>" % (_name, _url))
        return "\n".join(lines)

    def showEvent(self, e):
        super().showEvent(e)
        try:
            backdrop.auto_apply(self)
        except Exception:
            pass


def open_url(url: str) -> bool:
    """用系统默认浏览器打开外部链接（v1.28.0 反馈 2 / 3）。

    任何失败都只记一条日志、**绝不弹框报错** —— 用户机器上没装浏览器或关联被改坏时，
    点一下软件不该跳出个错误框。
    """
    if not url:
        return False
    try:
        ok = bool(QDesktopServices.openUrl(QUrl(url)))
    except Exception as e:
        try:
            applog.log(f"打开链接失败：{url}（{e}）")
        except Exception:
            pass
        return False
    try:
        applog.log(f"打开链接：{url}（{'ok' if ok else '系统未接管'}）")
    except Exception:
        pass
    return ok


class LinkFilter(QObject):
    """把「点一下打开外链」挂到任意既有控件上（v1.28.0 反馈 2 / 3）。

    为什么用**事件过滤器**而不是子类化：品牌区是 QWidget、底部是 QStatusBar，
    子类化会改控件类型，而 QSS 里的类型选择器（`QStatusBar{…}`）一旦不命中，
    底部那条背景 / 上边框就会整条消失。过滤器对控件本身零侵入、也不碰任何样式。

    注意：必须有人**持有引用**（本项目里挂成 `self._brand_link` / `self._footer_link`），
    否则 Python 一侧被 GC 后过滤器就失效了。
    """

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def eventFilter(self, obj, ev):
        if (ev.type() == QEvent.MouseButtonPress
                and ev.button() == Qt.LeftButton and self.url):
            open_url(self.url)
            return True                     # 吃掉事件，别再往下传
        return False


class MainWindow(QMainWindow):
    def __init__(self, logo_path=None):
        super().__init__()
        self._logo_path = logo_path
        if logo_path and os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))   # v1.22.0（反馈 3）：logo 作为窗口/任务栏图标
        self.setWindowTitle(f"{ver.APP_NAME}  {ver.FULL_VERSION}")
        # 说明：磨砂是「应用内」实现的（见 veil.py 顶部注释 —— 系统级 Acrylic /
        # Mica 在 Qt 窗口上一律不透出，实测数据记录在那里）。所以这里**不**开
        # WA_TranslucentBackground，窗口保持不透明，可读性可控。
        self._apply_default_geometry()
        self._nav = []
        self._nav_i = -1
        self._backdrop_info = {}
        self._selected_card = None
        self._lib_counts = {}          # 媒体库 -> 影片总数（侧边栏名称后显示，v1.14.0）
        self._settings_dlg = None      # 非模态设置窗口（v1.14.0）
        # v1.24.0（反馈 8/11）：智能推荐缓存 + 侧边栏媒体库圆形进度环
        self._smart_picks = []
        self._smart_algo = None
        self._smart_res = {}
        self._smart_placeholder = None
        self._smart_worker = None
        # v1.34.0（需求 2）：本次临时的引导向量 —— [{"token","weight","dim","key","label"}]。
        # **不落库**，只活在这一次会话里（换一批会沿用，切走别的页再回来也保留）。
        self._smart_guides = []
        # v1.24.1（反馈 3）：当前所在的人物页（演员库 / 导演库）—— 收藏 / 置顶后按它原地重建
        self._people_builder = None
        self._lib_rings = {}
        self._scan_workers = {}
        self._build()
        self._backfill_crew()
        self._refresh_stats()
        self.go(self._view_home)
        self._start_bg_task()
        self._apply_appearance()

    def _backfill_crew(self):
        """一次性补写 media_people 关联（演员 + 导演）。

        v1.11.0：旧版索引只有 Actor 关联（真机库 Director 关联实测 0 条），
        影片卡的「导演」小字因此永远为空。这里读 nfo 重新解析并补齐；
        scanner.backfill_people_links 幂等（内容一致即跳过写库），可安全反复调用。
        """
        try:
            if db.count_people_links("Director") > 0 or db.count_people_links() == 0:
                return
            stats = scanner_mod.backfill_people_links()
            if stats.get("media"):
                print("[crew] 演职员关联回填：%s" % stats)
        except Exception as e:
            print("[crew] 演职员关联回填失败：%s" % e)

    def _apply_appearance(self):
        """重载样式表 + 应用/关闭系统模糊（磨砂玻璃）。"""
        s = cfg.get_settings()
        load_style(QApplication.instance() or QApplication([]), s.appearance)
        # v1.25.0（反馈 5）：换了高亮色之后，当前已选中卡片的外发光也要立刻跟着换
        # （否则要取消选中再重新点一下才变色）。
        sel = getattr(self, "_selected_card", None)
        if sel is not None:
            self._apply_card_glow(sel)
        self._apply_veil(s.appearance)
        self._apply_opacity()
        if os.environ.get("LMC_NO_BACKDROP") == "1":
            self._backdrop_info = {"ok": False, "method": "none", "detail": "disabled"}
            return self._backdrop_info
        try:
            self._backdrop_info = backdrop.apply_backdrop(
                self, s.appearance.get("mode", "磨砂玻璃"),
                s.appearance.get("level", "中"))
        except Exception as e:
            self._backdrop_info = {"ok": False, "method": "none", "detail": str(e)}
        return self._backdrop_info

    def _apply_veil(self, appearance):
        """把外观设置灌进磨砂底衬：经典暗色 → 纯色；磨砂玻璃 → 模糊底图 + 压暗。"""
        v = getattr(self, "veil", None)
        if v is None:
            return
        glass = appearance.get("mode", "磨砂玻璃") == "磨砂玻璃"
        scrim, _panel = cfg.appearance_alphas(appearance)
        v.veil.set_enabled(glass)
        v.veil.set_scrim(scrim)
        v.update()

    def set_backdrop(self, path):
        """设置磨砂底衬的背景图（剧照 / 演员照）。传 None 回到兜底底图。"""
        v = getattr(self, "veil", None)
        if v is None:
            return
        try:
            v.set_source(path)
        except Exception:
            pass

    def _apply_opacity(self):
        """整窗透明度（0.2~1.0，1=不透明），由设置驱动；让窗口透出桌面。"""
        op = cfg.get_settings().window_opacity
        try:
            self.setWindowOpacity(max(0.2, min(1.0, float(op))))
        except Exception:
            pass

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_backdrop_done", False):
            self._backdrop_done = True
            QTimer.singleShot(0, self._apply_appearance)

    def _apply_default_geometry(self):
        """默认 1920×1080，并按可用屏幕钳制 + 居中。"""
        w, h = 1920, 1080
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = min(w, avail.width())
            h = min(h, avail.height())
            self.resize(w, h)
            self.move(avail.x() + max(0, (avail.width() - w) // 2),
                      avail.y() + max(0, (avail.height() - h) // 2))
        else:
            self.resize(w, h)

    # ---------- 构建 ----------
    def _build(self):
        central = veil_mod.VeilWidget()          # 自绘磨砂底衬
        self.veil = central
        self.setCentralWidget(central)
        h = QHBoxLayout(central); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        self.h_layout = h

        self._lib_counts = db.library_counts()   # 侧边栏库名后要显示总数（一次分组统计）
        self.sidebar = self._build_sidebar()
        h.addWidget(self.sidebar)

        right = QVBoxLayout(); right.setContentsMargins(0, 0, 0, 0); right.setSpacing(0)
        right.addWidget(self._topbar())
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        h.addLayout(right, 1)
        # v1.26.0（反馈 2）：用户要求把开源声明也放到最底部，且要**跟在 Copyright 之后**。
        # v1.28.0（反馈 3）：**整条状态栏可点** → 打开作者 GitHub 主页。
        # 文字是 showMessage 写的普通文本、本身不可点，所以挂事件过滤器接管鼠标；
        # 样式（背景 / 上边框）完全不动，悬停时靠 style.qss 的 QStatusBar:hover 提亮一点。
        sb = self.statusBar()
        sb.setCursor(Qt.PointingHandCursor)
        sb.setToolTip(f"点击访问作者 GitHub 主页\n{ver.AUTHOR_URL}")
        self._footer_link = LinkFilter(ver.AUTHOR_URL, self)   # 留着引用，否则会被 GC
        sb.installEventFilter(self._footer_link)
        sb.showMessage(
            f"{ver.FULL_VERSION}  |  {ver.COPYRIGHT}  |  {ver.LICENSE_NOTE}")

    def _build_sidebar(self):
        side = QFrame(); side.setObjectName("Sidebar"); side.setFixedWidth(186)
        sv = QVBoxLayout(side); sv.setContentsMargins(8, 12, 8, 10); sv.setSpacing(2)
        sv.addWidget(self._brand())
        s = cfg.get_settings()
        builders = self._nav_builders()
        last_group = None
        for item in s.nav:
            if not item.get("visible", True):
                continue
            group = item.get("group", "")
            if group and group != last_group:
                sv.addWidget(self._section(group))
                last_group = group
            # v1.32.0（反馈 3）：`item["label"]` 是**导航身份**（配置里的真源、用于排序与显隐），
            # 显示时才过 i18n —— 否则配置里会存进外语词、老用户升级后导航就串了。
            sv.addWidget(self._nav_btn(i18n.tr(item["label"]), builders[item["key"]]))
        # 媒体库：**只有一个分组**（v1.12.0 合并了旧版的「媒体库/分类」与「命名媒体库」两套），
        # 全部由用户自己命名；右键 编辑 / 重命名 / 扫描 / 删除。
        sv.addWidget(self._section("媒体库"))
        self._lib_btns = {}
        # 注：库名是用户自己起的（身份），**不翻译**；这里只翻「媒体库」这个分组标题。
        self._lib_rings = {}       # v1.24.0（反馈 11）：库名旁的圆形扫描进度环
        for lib in s.libraries:
            btn = self._lib_btn(lib)
            self._lib_btns[lib["name"]] = btn
            sv.addWidget(self._lib_row(lib["name"], btn))
        # 没有内置库，所以「新建」入口必须在侧边栏就够得着（设置页里也有一份）
        new_btn = self._nav_btn(i18n.tr(self._NEW_LIB_TEXT), self._new_library)
        new_btn.setObjectName("NavDim")
        sv.addWidget(new_btn)
        sv.addItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
        # —— 数据统计（v1.27.0 反馈 2：用户要求「统计信息上移」）——
        # 原来是 4 行光秃秃贴在侧栏最底；现在加一条「数据统计」小标题、正文压成 2 行，
        # 把下面的位置让给新增的「实时状态」面板。原来那句内联 setStyleSheet 挪进
        # style.qss 的 QLabel#SideStats —— 内联样式会和 QSS 抢优先级，也不方便跟主题。
        # v1.28.0（反馈 1）：「数据统计」/「实时状态」两块可在「设置 → 外观」里关掉。
        # 关掉是**整块不建**（不是 hide()）—— 侧栏高度自动收回，不会留一条空白间距；
        # 「实时状态」关掉时连采集线程都不会起（shared_worker 只在有面板订阅时才创建）。
        ap = s.appearance
        if ap.get("show_stats", True):
            sv.addWidget(self._section("数据统计"))
            self.stat_label = QLabel("—")
            self.stat_label.setObjectName("SideStats")
            sv.addWidget(self.stat_label)
        else:
            # 关掉时仍保留一个**已隐藏**的占位标签：`_refresh_stats()` 等多处会直接
            # setText，留个不显示的占位比到处写 None 判断安全（它不进布局，永不显示）。
            self.stat_label = QLabel("—")
            self.stat_label.setObjectName("SideStats")
            self.stat_label.hide()
        if ap.get("show_sysmon", True):
            # —— 实时状态（v1.27.0 反馈 2 新增）——
            # CPU / 内存 / GPU 三条横条 +「网络 · Ollama」+「当前模型」。采样全在工作线程里
            # 跑（nvidia-smi 要起进程、Ollama 探测有 0.4s 超时），详见 src/sysmon.py。
            # 环境变量 LMC_NO_SYSMON=1 也可整个关掉。
            sv.addWidget(self._section("实时状态"))
            self.sysmon = sysmon.SysMonitorPanel()
            sv.addWidget(self.sysmon)
        else:
            self.sysmon = None
        return side

    def _lib_row(self, name, btn):
        """媒体库行 = 按钮 + 右侧圆形进度环（扫描中才出现，v1.24.0 反馈 11）。

        做成**独立一行**而不是把环当成按钮的子控件：库名后面本来就跟了「（12345）」，
        叠在按钮右侧会盖住数字。
        """
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(btn, 1)
        ring = ScanRing(row)
        self._lib_rings[name] = ring
        h.addWidget(ring, 0, Qt.AlignVCenter)
        return row

    def _lib_ring(self, name, busy, pct=0, tip=""):
        ring = getattr(self, "_lib_rings", {}).get(name)
        if ring is not None:
            ring.set_state(busy, pct, tip)

    def _lib_btn(self, lib):
        # 名称后显示该媒体库的影片总数（v1.14.0 反馈 2）。计数来自一次 GROUP BY 查询，
        # 不做逐个库 COUNT。
        name = lib["name"]
        n = self._lib_counts.get(name)
        b = QPushButton(f"{name}（{n}）" if n is not None else name)
        b.setObjectName("Nav")
        b.setToolTip(f"{name}：{n if n is not None else '—'} 部影片（右键可扫描 / 编辑 / 重命名 / 删除）")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.go(lambda: self._lib_view(lib)))
        b.setContextMenuPolicy(Qt.CustomContextMenu)
        b.customContextMenuRequested.connect(
            lambda pos, L=lib, B=b: self._lib_menu(L, B, pos))
        return b

    def _lib_menu(self, lib, btn, pos):
        menu = QMenu(self)
        act_edit = menu.addAction("编辑")
        act_rename = menu.addAction("重命名")
        scan_menu = menu.addMenu("扫描")
        a_new = scan_menu.addAction("扫描新添加和修改的")
        a_fill = scan_menu.addAction("扫描全部补充缺失")
        a_over = scan_menu.addAction("扫描全部并覆盖")
        a_purge = scan_menu.addAction("扫描并删除失效的")
        menu.addSeparator()
        act_del = menu.addAction("删除")
        act_edit.triggered.connect(lambda: self._edit_library(lib))
        act_rename.triggered.connect(lambda: self._rename_library(lib))
        a_new.triggered.connect(lambda: self._scan_library_cat(lib, "new"))
        a_fill.triggered.connect(lambda: self._scan_library_cat(lib, "fill"))
        a_over.triggered.connect(lambda: self._scan_library_cat(lib, "overwrite"))
        a_purge.triggered.connect(lambda: self._purge_library(lib))
        act_del.triggered.connect(lambda: self._delete_library(lib))
        menu.exec(btn.mapToGlobal(pos))

    def _delete_library(self, lib):
        dlg = DeleteLibraryDialog(self, lib)
        if dlg.exec() != QDialog.Accepted:
            return
        res = dlg.result_data()
        name = lib["name"]
        removed = 0
        if res.get("delete_media"):
            removed = db.delete_library(name)
        cfg.get_settings().remove_library(name)
        self._apply_settings()
        self.go(self._view_home)
        QMessageBox.information(
            self, "已删除",
            f"媒体库「{name}」已删除。"
            + (f"\n同时清理了 {removed} 条媒体索引记录。" if removed else "")
            + "\n磁盘上的文件未做任何改动。")

    def _new_library(self):
        """新建媒体库：名称 / 类型 / 文件夹全部由用户自己填（软件不再自带任何库）。"""
        dlg = LibraryEditDialog(self, {"name": "", "kind": "混合", "paths": []},
                                title="新建媒体库")
        if dlg.exec() != QDialog.Accepted:
            return
        name, kind, paths = dlg.result_data()
        if not name:
            QMessageBox.warning(self, "提示", "请填写媒体库名称。")
            return
        s = cfg.get_settings()
        if s.library(name):
            QMessageBox.warning(self, "提示", f"已存在名为「{name}」的媒体库，请换个名字。")
            return
        s.add_library(name, kind, paths)
        self._apply_settings()
        lib = s.library(name)
        if lib:
            self.go(lambda: self._lib_view(lib))
        tip = ("右键该库 → 扫描，即可索引其中的影片。" if paths
               else "右键该库 → 编辑，可添加媒体文件夹后再扫描。")
        QMessageBox.information(self, "已创建", f"媒体库「{name}」已创建。\n{tip}")

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
            if cfg.get_settings().library(name):
                QMessageBox.warning(self, "提示", f"已存在名为「{name}」的媒体库，请换个名字。")
                return
            db.rename_library(old, name)        # 同步已有媒体的 library 字段
        cfg.get_settings().update_library(old, name, kind, paths)
        self._apply_settings()

    def _rename_library(self, lib):
        name, ok = QInputDialog.getText(self, "重命名媒体库", "新的名称：", text=lib["name"])
        if not ok or not (name or "").strip():
            return
        name = name.strip()
        if name == lib["name"]:
            return
        if cfg.get_settings().library(name):
            QMessageBox.warning(self, "提示", f"已存在名为「{name}」的媒体库，请换个名字。")
            return
        db.rename_library(lib["name"], name)
        cfg.get_settings().rename_library(lib["name"], name)
        self._apply_settings()

    def _lib_view(self, lib):
        """媒体库页：分页影片墙，标题显示该库影片总数（v1.14.0 反馈 2）。"""
        name = lib["name"]
        base = {"library": name}
        if db.count_media(library=name) == 0 and lib.get("filter"):
            base = dict(lib["filter"])       # 兼容旧版「按条件归类」的库
        return self._wall_page(name, base)

    def _nav_builders(self):
        return {
            "home": lambda: self.go(self._view_home),
            "recent": lambda: self.go(self._view_recent),
            "favorites": lambda: self.go(self._view_favorites),
            # v1.24.0（反馈 8）：智能推荐（按收藏影片的标签 + 收藏的演员推）
            "smart": lambda: self.go(self._view_smart),
            "folders": lambda: self.go(self._view_folders),
            "collections": lambda: self.go(self._view_collections),
            # 「全部」也走分页影片墙 —— 5 万条规模下不能一次性读全库（v1.14.0）
            "all": lambda: self.go(lambda: self._wall_page("全部")),
            "actors": lambda: self.go(self._view_actors),
            # v1.24.0（反馈 10）：导演库（与演员库同款卡片，但不显示生日/出身地/身高/胸围/三围）
            "directors": lambda: self.go(self._view_directors),
        }

    def _brand(self):
        """侧栏品牌区：logo 与「流明盒」**横向平齐**（v1.23.0 反馈 2，原先 logo 竖排在上）。

        v1.28.0（反馈 2）：整块**可点** → 打开项目 GitHub 主页。手型光标 + 悬停提示 +
        `style.qss` 里 `QWidget#BrandBox:hover` 的一层极淡提亮（用户提过「不知道能不能点」）；
        用事件过滤器实现，不给自绘区写任何 background（那是本项目复发过的硬边色带老坑）。
        """
        w = QWidget()
        w.setObjectName("BrandBox")
        w.setCursor(Qt.PointingHandCursor)
        w.setToolTip(f"打开项目主页\n{ver.REPO_URL}")
        w.setAttribute(Qt.WA_Hover, True)          # 让 QSS 的 :hover 生效
        # 普通 QWidget 默认**不绘制** QSS 背景（QWidget::paintEvent 是空的）——
        # 不打开这个属性，style.qss 里 QWidget#BrandBox:hover 的提亮永远画不出来
        # （第一版出图时实测：悬停前后像素一模一样）。开它之后静态态仍是
        # `background: transparent`，只在悬停时多一层极淡白，外观与之前一致。
        w.setAttribute(Qt.WA_StyledBackground, True)
        self._brand_link = LinkFilter(ver.REPO_URL, w)   # 留着引用，否则会被 GC
        w.installEventFilter(self._brand_link)
        h = QHBoxLayout(w); h.setContentsMargins(6, 6, 6, 10); h.setSpacing(8)
        if getattr(self, "_logo_path", None) and os.path.exists(self._logo_path):
            try:
                pm = QPixmap(self._logo_path).scaled(
                    28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo = QLabel(); logo.setPixmap(pm); logo.setObjectName("BrandLogo")
                logo.setFixedSize(28, 28)
                h.addWidget(logo, 0, Qt.AlignVCenter)
            except Exception:
                pass
        col = QVBoxLayout(); col.setSpacing(0); col.setContentsMargins(0, 0, 0, 0)
        t = QLabel(ver.APP_NAME); t.setObjectName("TitleBig")
        s = QLabel(ver.APP_NAME_EN); s.setObjectName("Sub")
        col.addWidget(t); col.addWidget(s)
        h.addLayout(col, 1)
        # 子标签各装一份过滤器：Qt 只对**系统真实事件**做「父级冒泡」，合成事件
        # （自动化测试 / 某些输入法路径）不会冒泡，装一份最稳；不会重复触发 ——
        # 过滤器一旦命中就 return True 把事件吃掉，事件仍是 accepted 状态、不再上浮。
        for _ch in w.findChildren(QLabel):
            _ch.setCursor(Qt.PointingHandCursor)
            _ch.setToolTip(w.toolTip())
            _ch.installEventFilter(self._brand_link)
        return w

    def _section(self, text):
        # v1.32.0（反馈 3）：分组标题只在**显示层**翻译 —— 调用点传的仍是中文原名，
        # 中文键同时也是 i18n 词典的 key，查不到就原样显示。
        l = QLabel(i18n.tr(text))
        l.setObjectName("Section")
        l.setContentsMargins(8, 12, 0, 2)
        return l

    def _nav_btn(self, text, fn):
        b = QPushButton(text)
        b.setObjectName("Nav")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(fn)
        return b

    def _topbar(self):
        bar = QFrame(); bar.setObjectName("TopBar")
        h = QHBoxLayout(bar); h.setContentsMargins(12, 8, 12, 8); h.setSpacing(8)
        # ← → 用 compact_button：全局 QSS 的 padding:7px 14px 会把 36px 宽按钮的
        # 内容区压到 6px，箭头字形只剩一道残影（v1.11.1 修复「按钮不显示」）
        self.back_btn = compact_button("←", 36, 30, "后退")
        self.back_btn.clicked.connect(self._back)
        self.fwd_btn = compact_button("→", 36, 30, "前进")
        self.fwd_btn.clicked.connect(self._forward)
        h.addWidget(self.back_btn); h.addWidget(self.fwd_btn)

        self.search = QLineEdit()
        # v1.32.0（反馈 3）：搜索框提示语走词典（`COMMON` 里有整句译文），
        # 提示语属于「会引导操作」的文案，值得翻译；业务细节不译。
        self.search.setPlaceholderText(
            i18n.tr("搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）"))
        self.search.returnPressed.connect(self._do_search)
        h.addWidget(self.search, 1)

        scan = QPushButton("扫描媒体库"); scan.setObjectName("Primary")
        scan.clicked.connect(self._scan)
        refresh = QPushButton("刷新"); refresh.setObjectName("Ghost")
        refresh.clicked.connect(self._refresh_view)
        # v1.24.0（反馈 5）：入口名称由「设置」改为「工具」（内容没变，只是叫法对上了）
        settings = QPushButton("工具"); settings.setObjectName("Ghost")
        settings.setToolTip("工具（原「设置」）：个性化 / 画像概览 / 演员刮削 / 智能推荐 / "
                            "服务管理 / 重复检测 / 数据与日志")
        settings.clicked.connect(self._open_settings)
        about = QPushButton("关于"); about.setObjectName("Ghost")
        about.clicked.connect(lambda: AboutDialog(self).exec())
        h.addWidget(scan); h.addWidget(refresh); h.addWidget(settings); h.addWidget(about)

        QShortcut(QKeySequence("Ctrl+K"), self, self._focus_search)
        return bar

    def _focus_search(self):
        self.search.setFocus(); self.search.selectAll()

    # ---------- 导航 ----------
    def go(self, builder, push=True):
        widget = builder()
        if widget is None:      # 构建器返回空（例如内部已自行跳转）时直接忽略，避免 addWidget(None) 崩溃
            return
        old = self.stack.currentWidget()
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        if old:
            self.stack.removeWidget(old)
        if push:
            self._nav = self._nav[:self._nav_i + 1]
            self._nav.append(builder)
            self._nav_i = len(self._nav) - 1
        self._update_nav_buttons()

    def _back(self):
        if self._nav_i > 0:
            self._nav_i -= 1
            self.go(self._nav[self._nav_i], push=False)

    def _forward(self):
        if self._nav_i < len(self._nav) - 1:
            self._nav_i += 1
            self.go(self._nav[self._nav_i], push=False)

    def _update_nav_buttons(self):
        self.back_btn.setEnabled(self._nav_i > 0)
        self.fwd_btn.setEnabled(self._nav_i < len(self._nav) - 1)

    # ---------- 视图 ----------
    def _page(self, title, body_widget):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        host = QWidget()
        v = QVBoxLayout(host); v.setContentsMargins(20, 16, 20, 20); v.setSpacing(12)
        if title:
            v.addWidget(self._h1(title))
        v.addWidget(body_widget)
        v.addStretch(1)
        scroll.setWidget(host)
        # v1.14.0：增量网格挂上外层滚动条 → 滚到接近底部自动续载。
        # 页面主体可能是个容器（如「筛选条 + 网格」），此时取容器上的 lazy_grid 引用。
        target = getattr(body_widget, "lazy_grid", None)
        if target is None and hasattr(body_widget, "attach_scroll"):
            target = body_widget
        if target is not None:
            target.attach_scroll(scroll.verticalScrollBar())
        return scroll

    def _h1(self, text):
        l = QLabel(text); l.setStyleSheet("font-size:20px;font-weight:bold;color:#d4af37;")
        return l

    def _crewed(self, rows):
        """给一批影片补上「演员 / 导演」小字 + 选集数（v1.15.0）。

        v1.14.0：`cast_crew_map` 只查**这批** media_id —— 原来每次渲染都整表扫描
        media_people，5 万片规模下几十万行全进内存，正是「一操作就卡死」的主因。
        v1.15.0：`parts_counts` 同样按 id 批量取「每个顶层条目有几个分片」。
        """
        ids = [r.get("id") for r in rows if r.get("id")]
        crew = db.cast_crew_map(ids)
        parts = db.parts_counts(ids)
        return [(r, crew.get(r.get("id"), {}), parts.get(r.get("id"), 0)) for r in rows]

    def _poster_card(self, pair):
        m, c, parts_n = pair
        return PosterCard(m, self._open_media, c.get("actors", ""), c.get("directors", ""),
                          on_select=self._select_card, parts_count=parts_n,
                          on_play=self._play_media, on_fav=self._toggle_favorite_card,
                          reason=m.get("reason", ""))

    def _grid(self, items):
        """已备好数据的小列表（最近播放等）：同样走增量网格，避免一次性建大量控件。"""
        items = list(items or [])
        if not items:
            w = QWidget(); v = QVBoxLayout(w)
            v.addWidget(QLabel("（暂无内容。点击右上角「＋ 扫描媒体库」选择含 nfo 的目录）"))
            return w
        pairs = self._crewed(items)
        return LazyGrid(lambda off, lim: pairs[off:off + lim], self._poster_card,
                        len(pairs), kind="media")

    def _wall_page(self, title, base=None, unit="部"):
        """影片墙：**分页读取 + 增量渲染 + 筛选 + 排序**（v1.14.0，反馈 1/2/3/4/8）。

        数据在 SQL 层分页/筛选/排序（不再把整库读进内存），标题后缀显示该库总数，
        网格顶部实时显示读取进度。
        """
        self.set_backdrop(None)
        s = cfg.get_settings()
        prefs = s.wall_prefs or {}
        user_filters = dict(prefs.get("filters") or {})
        # 基础条件（媒体库 / 收藏页 / 合集页）**最后**覆盖，保证页面语义不被筛选条改写
        filt = dict(user_filters)
        filt.update(base or {})
        sort = prefs.get("sort") or "sort_title"
        asc = bool(prefs.get("asc", True))

        bar = FacetBar(sort, asc, user_filters,
                       open_=bool(prefs.get("facet_open", False)),
                       with_header=False)
        random_mode = (sort == "random")

        def fetch(off, lim):
            rows = db.search_media(limit=lim, offset=off, sort=sort, asc=asc,
                                    top_only=True, **filt)
            return self._crewed(rows)

        total = db.count_media(top_only=True, **filt)
        grid = LazyGrid(fetch, self._poster_card, total, kind="media", unit=unit,
                        refreshable=random_mode)

        if random_mode:
            def reshuffle():
                db.reshuffle()             # 换种子 → 同一筛选条件下重新洗牌
                self._replace_current(lambda: self._wall_page(title, base, unit))
            grid.refresh_requested.connect(reshuffle)

        def rebuild():
            cfg.get_settings().set_wall_prefs(bar.sort(), bar.asc(), bar.filters())
            self._replace_current(lambda: self._wall_page(title, base, unit))

        bar.changed.connect(rebuild)
        # v1.17.0：展开 / 收缩筛选面板只记偏好，不重建列表（避免无谓地重新取数）
        bar.toggled.connect(lambda on: cfg.get_settings().set_facet_open(on))

        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
        w.lazy_grid = grid            # 供 _page 挂滚动条（滚到底自动续载）
        w.filter_bar = bar

        # v1.18.0：统一工具行 —— 左侧 排序/筛选，右侧 加载更多/刷新一下（同行对齐）
        tb = QWidget()
        tbl = QHBoxLayout(tb)
        tbl.setContentsMargins(0, 0, 0, 0)
        tbl.setSpacing(8)
        tbl.addWidget(bar.sort_btn)
        tbl.addWidget(bar.filter_btn)
        tbl.addStretch(1)
        tbl.addWidget(grid.more_btn)
        tbl.addWidget(grid.refresh_btn)
        grid.mark_toolbar_placed()      # v1.21.1（反馈 3）：工具行已接管按钮，解锁显隐门闩
        v.addWidget(tb)

        v.addWidget(bar)
        v.addWidget(grid)
        tip = ("筛选与排序在数据库层直接完成，结果按页加载；"
               "滚动到底部或点「加载更多」继续读取。")
        if random_mode:
            tip += "　随机排序下点「刷新一下」可重新洗牌。"
        hint = QLabel(tip); hint.setStyleSheet("color:#8c8071;font-size:11px;"); hint.setWordWrap(True)
        v.addWidget(hint)
        return self._page(f"{title}（{total} {unit}）", w)

    def _view_home(self):
        self.set_backdrop(None)
        return HomeListView(on_open_actor=self._open_actor, on_open_media=self._open_media,
                            on_hover_media=self._backdrop_from_media,
                            on_changed=self._refresh_stats)

    def _backdrop_from_media(self, m):
        """鼠标选到哪部作品，磨砂底衬就用它的剧照。"""
        if isinstance(m, dict):
            self.set_backdrop(m.get("fanart") or m.get("poster"))

    def _view_recent(self):
        return self._page("最近播放 / 最近添加", self._grid(db.recent(60)))

    def _view_favorites(self):
        return self._wall_page("我的收藏", {"favorite": True})

    def _view_grid(self, items, title):
        self.set_backdrop(None)
        return self._page(title, self._grid(items))

    def _view_folders(self):
        """文件夹页（v1.17.0，反馈 1）：改为 **文件夹卡片网格**（Emby 文件夹视图风格）。

        每张卡 = 一个「已加入的目录」（媒体库在设置里配置的媒体文件夹）：
        封面由该目录下前 2 张海报拼贴，下方是目录名与「共 N 部」。
        点卡片 → 进入该目录的影片墙（按 file_path 前缀在 SQL 层筛）；右键 → 扫描菜单。
        目录不存在时封面右上角标红「!」，原因写进 tooltip。
        """
        self.set_backdrop(None)
        s = cfg.get_settings()
        libs = db.libraries()
        counts = db.library_counts()

        entries, seen = [], set()
        for lib in libs:
            paths = [p for p in ((s.library(lib) or {}).get("paths") or []) if p]
            if not paths:                    # 没配置目录的库 → 仍给一张「无目录」卡片
                entries.append({"lib": lib, "path": None, "name": lib, "missing": False})
                continue
            for p in paths:
                if (lib, p) in seen:
                    continue
                seen.add((lib, p))
                entries.append({"lib": lib, "path": p, "missing": not os.path.isdir(p),
                                "name": os.path.basename(p.rstrip("/\\")) or p})
        if not entries:
            return self._page("文件夹", QLabel(
                "尚未扫描任何媒体库。点击右上角「＋ 扫描媒体库」添加。"))

        # 同名目录（X:/Y:/W: 下都叫「【01】Jav精选」）补**盘符**区分；
        # 同盘同名的再带上父目录名，保证卡片名一定不撞。
        dup = {}
        for e in entries:
            if e["path"]:
                dup[e["name"]] = dup.get(e["name"], 0) + 1
        for e in entries:
            if not e["path"] or dup.get(e["name"], 0) <= 1:
                continue
            p = os.path.abspath(e["path"])
            suffix = " · ".join(x for x in (os.path.splitdrive(p)[0],
                                            os.path.basename(os.path.dirname(p))) if x)
            e["name"] = f"{e['name']}（{suffix or '?'}）"

        stats = db.folder_stats([e["path"] for e in entries if e["path"]])

        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(12)
        host = QWidget()
        fl = FlowLayout(host, margin=0, spacing=14)
        for e in entries:
            st = (stats.get(e["path"]) if e["path"]
                  else {"count": counts.get(e["lib"], 0), "posters": []}) or {}
            card = FolderCard(e["name"], e["path"], int(st.get("count") or 0),
                              st.get("posters") or [], on_open=self._open_folder,
                              on_menu=lambda c, pos, L=e["lib"]: self._folder_menu(L, c, pos),
                              missing=e["missing"])
            fl.addWidget(card)
        v.addWidget(host)
        hint = QLabel("提示：点卡片进入该目录的影片墙；在卡片上点右键，可「扫描新添加和修改的 / "
                      "扫描全部补充缺失 / 扫描全部并覆盖 / 扫描并删除失效的」，扫描前会先统计数量"
                      "供你确认，并显示进度。目录不存在的卡片会在封面右上角标红「!」。")
        hint.setStyleSheet("color:#a2967f;font-size:11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)
        return self._page(f"文件夹（{len(entries)}）", w)

    def _open_folder(self, path, name):
        """点文件夹卡片 → 只看该目录下的影片（在 SQL 层按 file_path 前缀筛）。"""
        if not path:
            return
        base = {"path_prefix": path}
        self.go(lambda: self._wall_page(name, base))

    def _folder_menu(self, name, btn, pos):
        """文件夹（媒体库）右键菜单：三种扫描模式。"""
        menu = QMenu(self)
        a_new = menu.addAction(SCAN_MODE_CN["new"])
        a_fill = menu.addAction(SCAN_MODE_CN["fill"])
        a_over = menu.addAction(SCAN_MODE_CN["overwrite"])
        a_purge = menu.addAction(SCAN_MODE_CN["purge"])
        a_new.triggered.connect(lambda: self._scan_folder(name, "new"))
        a_fill.triggered.connect(lambda: self._scan_folder(name, "fill"))
        a_over.triggered.connect(lambda: self._scan_folder(name, "overwrite"))
        a_purge.triggered.connect(lambda: self._purge_folder(name))
        menu.exec(btn.mapToGlobal(pos))

    def _scan_folder(self, name, mode):
        """按媒体库名找到配置（含路径）→ 先统计数量确认 → 扫描并显示进度。"""
        lib = cfg.get_settings().library(name)
        if not lib:
            QMessageBox.information(
                self, "提示",
                f"文件夹「{name}」没有对应的媒体库配置（可能来自旧版索引）。\n\n"
                "请到「设置 → 服务管理 → 媒体库」新建同名媒体库并设置文件夹后再扫描。")
            return
        paths = [p for p in lib.get("paths", []) if p and os.path.isdir(p)]
        if not paths:
            QMessageBox.information(
                self, "提示",
                f"媒体库「{name}」尚未设置有效（存在）的媒体文件夹，请先在设置里编辑路径。")
            return
        dlg = FolderScanDialog(
            self, lib, mode,
            on_tick=lambda d, t, m, N=name: self._lib_ring(
                N, True, (100 * d / t) if t else 0, m))
        if dlg.exec() != QDialog.Accepted:
            self._lib_ring(name, False)
            return
        self._lib_ring(name, False)          # 扫描结束 → 进度环淡出
        c = dlg.result or {}
        QMessageBox.information(
            self, "扫描完成",
            f"媒体库「{name}」\n电影 {c.get('movie', 0)} 部 / "
            f"剧集 {c.get('tvshow', 0)} 部 / 分集 {c.get('episode', 0)} 个")
        self._refresh_stats()
        self.go(self._view_folders)

    def _view_collections(self):
        """合集页（v1.24.0 反馈 3）：**改成影片墙的样式**，参考「我的收藏」。

        原来是一列朴素的文字按钮；现在每个合集一张**卡片**（拼贴封面 + 名称 + 「共 N 部」），
        点卡片进入该合集的影片墙（与我的收藏同款的 `_wall_page` 分页 + 筛选 + 排序）。
        """
        self.set_backdrop(None)
        cols = db.collections()
        if not cols:
            return self._page("合集", QLabel("暂无合集（nfo 中未包含 <set> 节点）。"))

        # **必须分页**：真机有 7000+ 个合集，一次性建 7000 张卡会直接把界面卡死
        # （v1.24.0 离屏冒烟里就是这么被 SIGTERM 掉的）。走 LazyGrid，每批 48 张。
        posters = db.collection_posters([n for n, _c in cols])

        def fetch(off, lim):
            return cols[off:off + lim]

        def make(pair):
            name, n = pair
            card = FolderCard(name, None, int(n), posters.get(name) or [],
                              on_open=lambda _p, _n, N=name: self.go(
                                  lambda: self._wall_page(N, {"collection": N})))
            card.setToolTip(f"{name}\n共 {n} 部\n点击进入该合集的影片墙")
            return card

        grid = LazyGrid(fetch, make, len(cols), kind="folder", batch=48, unit="个")
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(12)
        w.lazy_grid = grid
        v.addWidget(grid)
        hint = QLabel("提示：每个合集一张卡片，封面由该合集前 2 部作品的海报拼贴而成；"
                      "点卡片进入该合集的影片墙（与「我的收藏」同一套分页 / 筛选 / 排序）。"
                      "合集较多时按批加载，滚动到接近底部自动继续。")
        hint.setStyleSheet("color:#a2967f;font-size:11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)
        return self._page(f"合集（{len(cols)}）", w)

    def _view_directors(self):
        """导演库（v1.24.0 反馈 10）：参考演员库，但**不显示**生日 / 出生地 / 身高 / 胸围 / 三围。

        导演的 nfo 里基本没有这些个人资料（实测 1218 位导演，几乎全是空），
        留着那五行只会让每张卡都是「—」。所以导演卡改为显示：作品数 / 收藏 / 置顶 / 状态。
        """
        s = cfg.get_settings()
        prefs = s.actor_prefs or {}
        filt = dict(prefs.get("filters") or {})
        sort = prefs.get("sort") or "works"
        asc = bool(prefs.get("asc", False))

        bar = FilterSortBar("actor", sort, asc, prefs.get("filters") or {})
        total = db.count_people(role_type="Director", **filt)
        if total <= 0 and not filt:
            return self._page("导演库", QLabel("暂无导演（nfo 中未包含 director 节点）。"))

        def fetch(off, lim):
            return db.query_people(role_type="Director", limit=lim, offset=off,
                                   sort=sort, asc=asc, **filt)

        def make(p):
            return DirectorCard(p, on_open=self._open_actor, on_fav=self._toggle_person_fav,
                                on_pin=self._toggle_person_pin, on_select=self._select_card,
                                main_win=self)

        grid = LazyGrid(fetch, make, total, kind="actor", unit="位")

        def rebuild():
            cfg.get_settings().set_actor_prefs(bar.sort(), bar.asc(), bar.filters())
            self._replace_current(self._view_directors)

        bar.changed.connect(rebuild)

        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
        w.lazy_grid = grid
        w.filter_bar = bar
        v.addWidget(bar)
        v.addWidget(grid)
        hint = QLabel("头像+作品数/别名卡片 · 不显示生日/出身地/身高/胸围/三围/简介（导演资料里本就没有） · "
                      "☆收藏 · 右上角▲置顶 · 双击查看作品")
        hint.setStyleSheet("color:#8c8071;font-size:11px;")
        v.addWidget(hint)
        # v1.24.1（反馈 3）：记住「当前人物页」是导演库，收藏 / 置顶后原地重建这一页
        self._people_builder = self._view_directors
        page = self._page(f"导演库（共 {total} 位）", w)
        # v1.31.0（反馈 1）：撤销 v1.30.0 的 A-Z 索引条，直接返回原页面
        return page

    # ---------- 智能推荐（v1.24.0 反馈 8） ----------
    def _view_smart(self, force=False):
        self.set_backdrop(None)
        rec = dict(cfg.get_settings().recommend or {})
        algo = "ai" if rec.get("algo") == "ai" else "normal"
        if self._smart_picks and not force and self._smart_algo == algo:
            return self._smart_wall()             # 复用上次结果，不重复算

        page = QWidget()
        v = QVBoxLayout(page); v.setSpacing(10)
        self._smart_tip = QLabel("正在按「我的收藏」的标签与「演员库」里收藏的演员生成推荐…")
        self._smart_tip.setStyleSheet("color:#c9bda7;font-size:12px;")
        self._smart_tip.setWordWrap(True)
        v.addWidget(self._smart_tip)
        self._smart_bar = QProgressBar()
        self._smart_bar.setRange(0, 100)
        self._smart_bar.setValue(0)
        v.addWidget(self._smart_bar)
        v.addStretch(1)
        self._smart_placeholder = page
        self._smart_algo = algo
        self._start_smart(1)
        return self._page("智能推荐", page)

    def _start_smart(self, page_no):
        w = getattr(self, "_smart_worker", None)
        if w is not None and w.isRunning():
            return
        rec = dict(cfg.get_settings().recommend or {})
        self._smart_worker = SmartWorker(
            page=page_no, limit=int(rec.get("count", 24)), algo=self._smart_algo,
            guides=self._smart_guides, parent=self)
        self._smart_worker.progress.connect(self._on_smart_progress)
        self._smart_worker.done.connect(self._on_smart_done)
        self._smart_worker.start()

    def _on_smart_progress(self, i, n, msg):
        # v1.24.1：推荐在后台跑，用户可能已经切走 → 占位页连同这两个控件已被释放。
        # 不判活的话会对着已析构的 QLabel/QProgressBar 调 setText/setValue，
        # 刷出一堆「Internal C++ object already deleted」。setText 必须判活；setValue 同理。
        tip = getattr(self, "_smart_tip", None)
        if tip is not None and _qt_alive(tip):
            tip.setText(msg)
        bar = getattr(self, "_smart_bar", None)
        if bar is not None and n and _qt_alive(bar):
            bar.setValue(int(i * 100 / max(n, 1)))

    @staticmethod
    def _hydrate_picks(picks):
        """把推荐结果的 id 换成**完整 media 行**（v1.24.1 反馈 1，智能推荐墙海报不显示的根因）。

        推荐引擎取数走 `db.media_for_insight()` —— 那是**分析专用投影**，只有
        id/title/genres/year/rating… 这些列，**没有 poster / fanart / thumb / file_path**。
        直接拿去画卡片：海报一律落到 `placeholder_pixmap()` 变成占位图（看起来「照片没有显示」），
        右下角播放按钮也因为 `playable_media()` 查不到 file_path 而不创建。

        这里按 id 回查完整行，并保留推荐专有的 `score` / `reason`，之后渲染路径与「全部」页
        完全一致 —— 左下角 ☆ 收藏、右下角 ▶ 播放自然都会出现。
        """
        picks = [dict(p) for p in (picks or [])]
        ids = []
        for p in picks:
            try:
                ids.append(int(p.get("id")))
            except (TypeError, ValueError):
                continue
        if not ids:
            return picks
        try:
            full = {int(r["id"]): r for r in db.media_by_ids(ids)}
        except Exception as e:                  # 回填失败也不能让推荐页崩掉
            applog.log(f"[智能推荐] 回填完整行失败：{type(e).__name__}: {e}", "error")
            return picks
        out, miss = [], 0
        for p in picks:
            try:
                row = full.get(int(p.get("id")))
            except (TypeError, ValueError):
                row = None
            if not row:
                miss += 1
                out.append(p)                   # 查不到就原样留着，至少不丢条目
                continue
            m = dict(row)
            for k in ("score", "reason"):       # 推荐专有字段，别被完整行覆盖掉
                if p.get(k) is not None:
                    m[k] = p[k]
            out.append(m)
        if miss:
            applog.log(f"[智能推荐] {miss} 条推荐在 media 表中已不存在（回填时跳过）")
        return out

    def _on_smart_done(self, res):
        self._smart_res = res or {}
        # v1.24.1（反馈 1）：必须回填完整行，否则卡片全是占位图（见 _hydrate_picks）
        self._smart_picks = self._hydrate_picks((res or {}).get("picks", []))
        # 只有当前还停在「加载中」那一页时才换页（用户可能已经点去别处了）。
        # 注意：`_page()` 返回的是 **QScrollArea 包装**，占位页是它的后代，不能直接 is 比较。
        # v1.24.1：占位页可能已被 `_replace_current` 释放 → isAncestorOf 会抛 RuntimeError。
        cur = self.stack.currentWidget()
        holder = getattr(self, "_smart_placeholder", None)
        if (holder is not None and _qt_alive(holder, cur)
                and cur is not None and cur.isAncestorOf(holder)):
            self._replace_current(self._smart_wall)
        applog.log(f"[智能推荐] {self._smart_algo} → {len(self._smart_picks)} 部")

    def _guide_bar(self, row):
        """把「引导向量」控件**接在工具行里**（v1.34.0 需求 2，位置按用户截图定）。

        需求原文：「换一批旁边加入一个输入框，可以手动增加一个高权重引导向量，
        比如我输入一个艺人名，则本次推荐中该艺人智能推荐的占比就会加强。」

        设计（用户确认）：
        - 位置：**与「换一批」同一行**，输入框放在「换一批」**左侧**；
        - 生效：**本次临时**（不进 `vector_overrides` 表，切页保留、重启即忘）；
        - 维度：**自动识别** —— 先查 people 表（演员/导演），再查标签/片商/系列；
        - 认不出来：给一个维度下拉框让用户自己指定，不让输入白白丢掉。

        参数 `row` 是工具行的 QHBoxLayout；本方法只 `addWidget` 进去，不另起一行。
        工具行左侧的 info 标签会被压窄，所以这里给它设了 `setMinimumWidth(0)`
        兜底（见 `_smart_wall`），窄屏下 info 允许省略、输入框优先。
        """
        lb = QLabel("引导向量")
        lb.setStyleSheet("color:#c9bda7;font-size:12px;")
        row.addWidget(lb)

        self.guide_edit = QLineEdit()
        self.guide_edit.setObjectName("guide_edit")
        self.guide_edit.setPlaceholderText("艺人 / 标签 / 片商 / 系列，如：さつき芽衣")
        self.guide_edit.setToolTip(
            "输入一个词，本次推荐就会明显偏向它（不写入任何设置，只影响这一批）。\n"
            "支持演员、导演、标签、片商、系列名；输入后会自动识别是哪一类。\n"
            "权重越大越偏向（0.5 = 轻微、2 = 明显、5 以上基本霸屏）。")
        self.guide_edit.setMinimumWidth(150)
        self.guide_edit.setMaximumWidth(300)
        self.guide_edit.returnPressed.connect(self._add_guide)
        row.addWidget(self.guide_edit)

        self.guide_w = QDoubleSpinBox()
        self.guide_w.setObjectName("guide_w")
        self.guide_w.setRange(rec_mod.GUIDE_MIN_WEIGHT, rec_mod.GUIDE_MAX_WEIGHT)
        self.guide_w.setSingleStep(0.5)
        self.guide_w.setDecimals(1)
        self.guide_w.setValue(rec_mod.GUIDE_DEFAULT_WEIGHT)
        self.guide_w.setFixedWidth(72)
        self.guide_w.setToolTip(
            "0.5 = 轻微偏向（约 1/6 命中）\n"
            "2.0 = 明显偏向（约 2/3 命中，默认）\n"
            "5.0 以上 = 基本霸屏")
        row.addWidget(self.guide_w)

        b_add = compact_button("加强", 52, 28, "把输入的关键词加进本次推荐（回车同效）")
        b_add.setObjectName("Primary")
        b_add.clicked.connect(self._add_guide)
        row.addWidget(b_add)

        b_clr = compact_button("清空", 52, 28, "去掉全部引导，回到纯画像推荐（不重新计算）")
        b_clr.setObjectName("Ghost")
        b_clr.clicked.connect(self._clear_guides)
        row.addWidget(b_clr)

        # 已生效的引导 chips（每个带一个 × 用来单独移除）+ 状态文案，接在同一行右侧。
        self.guide_chips = QWidget()
        self.guide_chips.setObjectName("guide_chips")
        self.guide_chips_l = QHBoxLayout(self.guide_chips)
        self.guide_chips_l.setContentsMargins(0, 0, 0, 0)
        self.guide_chips_l.setSpacing(6)
        row.addWidget(self.guide_chips)

        self.guide_state = QLabel("—")
        self.guide_state.setObjectName("guide_state")
        self.guide_state.setStyleSheet("color:#8c8071;font-size:11px;")
        self.guide_state.setToolTip("引导向量的当前状态")
        row.addWidget(self.guide_state)

    def _refresh_guides(self):
        """重刷已生效的引导 chips 与状态文案。"""
        box = getattr(self, "guide_chips", None)
        lay = getattr(self, "guide_chips_l", None)
        if box is None or lay is None or not _qt_alive(box):
            return
        while lay.count():
            it = lay.takeAt(0)
            cw = it.widget()
            if cw is not None:
                cw.setParent(None)
                cw.deleteLater()
        guides = self._smart_guides or []
        seen = set()
        for g in list(guides):
            tok = g.get("token")
            if tok in seen:                     # 同一个 token 只出一个 chip（去重）
                continue
            seen.add(tok)
            chip = QWidget()
            chip.setAttribute(Qt.WA_StyledBackground, True)
            chip.setObjectName("GuideChip")
            hl = QHBoxLayout(chip)
            hl.setContentsMargins(8, 3, 6, 3)
            hl.setSpacing(6)
            dim_cn = rec_mod.dim_cn(g.get("dim") or "")
            lb = QLabel(f"{dim_cn}「{g.get('key') or ''}」× {float(g.get('weight') or 0):g}")
            lb.setStyleSheet("color:#e8d27a;font-size:11px;")
            hl.addWidget(lb)
            x = compact_button("×", 20, 18, "移除这条引导")
            x.clicked.connect(lambda _c=False, t=tok: self._remove_guide(t))
            hl.addWidget(x)
            lay.addWidget(chip)
        lay.addStretch(1)
        st = getattr(self, "guide_state", None)
        if st is not None and _qt_alive(st):
            if not guides:
                st.setText("没有引导 —— 当前完全按「我的收藏」的画像推荐。")
            else:
                hits = [g for g in guides if g.get("_hit")]
                if hits:
                    st.setText("引导已生效，点「换一批」可以看效果。")
                else:
                    st.setText("引导已就绪，点「换一批」生效。")

    def _add_guide(self):
        """解析输入 → 加进 `_smart_guides` → 重算推荐。

        识别不出来的词：弹一个维度下拉框让用户指定（用户确认过「没命中就给下拉框」）。
        """
        ed = getattr(self, "guide_edit", None)
        if ed is None or not _qt_alive(ed):
            return
        text = (ed.text() or "").strip()
        if not text:
            return
        try:
            w = float(self.guide_w.value())
        except Exception:
            w = rec_mod.GUIDE_DEFAULT_WEIGHT

        tok, dim, name = (None, None, "")
        try:
            tok, dim, name = rec_mod.resolve_guide_token(text)
        except Exception as e:
            applog.log(f"[引导向量] 识别失败：{type(e).__name__}: {e}", "error")

        if not tok:
            # 认不出来 → 让用户指定维度，再在**那个维度**里重新识别一次
            kinds = [("tag", "标签"), ("actor", "演员"), ("director", "导演"),
                     ("studio", "片商"), ("series", "系列")]
            items = [f"{cn}" for _k, cn in kinds]
            pick, ok = QInputDialog.getItem(
                self, "没认出这个关键词",
                f"没找到「{text}」对应的艺人 / 标签 / 片商 / 系列。\n"
                f"可以把它当成哪一类？（选定后按该维度直接使用）",
                items, 0, False)
            if not ok:
                return
            k = next((kk for kk, cn in kinds if cn == pick), "tag")
            dim = k
            head = rec_mod.GUIDE_HEAD[k]
            tok = head + ":" + text
            name = text

        ent = {"token": tok, "dim": dim, "key": name or tok[2:], "weight": w}
        # 同一个 token 再加 = 覆盖权重（不做多条叠加，避免误点越点越强）
        self._smart_guides = [g for g in (self._smart_guides or [])
                              if g.get("token") != tok]
        self._smart_guides.append(ent)
        applog.log(f"[引导向量] 本次生效 {tok} × {w:g}（共 {len(self._smart_guides)} 条）")
        ed.clear()
        self._refresh_guides()
        self._replace_current(lambda: self._view_smart(force=True))

    def _remove_guide(self, token):
        self._smart_guides = [g for g in (self._smart_guides or [])
                              if g.get("token") != token]
        applog.log(f"[引导向量] 移除 {token}")
        self._refresh_guides()
        self._replace_current(lambda: self._view_smart(force=True))

    def _clear_guides(self):
        if not self._smart_guides:
            return
        self._smart_guides = []
        applog.log("[引导向量] 清空全部引导")
        self._refresh_guides()
        self._replace_current(lambda: self._view_smart(force=True))

    def _smart_wall(self):
        self.set_backdrop(None)
        picks = self._smart_picks or []
        res = self._smart_res or {}
        meta = res.get("meta") or {}
        algo = res.get("algo", "normal")
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)

        # v1.24.1（反馈 1）：与「全部」页**同一套**卡片与增量网格（`_grid` → PosterCard），
        # 左下角 ☆ 收藏 / 右下角 ▶ 播放 由 PosterCard 自己按数据决定是否创建。
        grid = self._grid(picks) if picks else None

        tb = QWidget(); tbl = QHBoxLayout(tb)
        tbl.setContentsMargins(0, 0, 0, 0); tbl.setSpacing(8)
        engine = {"ollama": "本地 Ollama 扩词", "builtin": "内置离线联想"}.get(
            res.get("engine", ""), "")
        algo_cn = ("AI 智能算法" + (f"（{engine}）" if engine else "")
                   if algo == "ai" else "普通智能算法")
        info = QLabel(
            f"<b>{algo_cn}</b> · 依据 {meta.get('favorites', 0)} 部收藏影片"
            f"（{meta.get('liked', 0)} 部高分） + {meta.get('fav_people_n', 0)} 位收藏的演员/导演"
            f" · 候选 {res.get('pool', 0):,} 部")
        info.setStyleSheet("color:#c9bda7;font-size:12px;")
        # v1.34.0：工具行里现在还要塞引导向量输入框 → 让 info 可以被压窄而不是
        # 把别的控件顶出去（QLabel.minimumSizeHint 默认是文本完整宽度、不肯缩）。
        info.setMinimumWidth(0)
        info.setWordWrap(False)
        tbl.addWidget(info, 1)

        # ---- v1.34.0（需求 2）：引导向量，接在「换一批」**左侧**同一行 ----
        # 用户截图指定的位置：「换一批旁边加入一个输入框」。
        self._guide_bar(tbl)
        self._refresh_guides()          # 建完立即按 _smart_guides 刷 chips / 状态文案

        again = QPushButton("换一批")
        again.setObjectName("Ghost")
        again.setToolTip("避开这一批已推荐过的作品，重新推荐一组")
        again.clicked.connect(lambda: self._replace_current(
            lambda: self._view_smart(force=True)))
        tbl.addWidget(again)
        if grid is not None:
            # 与「全部」页同构：加载更多排在工具行右侧，滚动到底也会自动续载
            tbl.addWidget(grid.more_btn)
            w.lazy_grid = grid
            grid.mark_toolbar_placed()
        v.addWidget(tb)

        if grid is not None:
            v.addWidget(grid)
        else:
            tip = res.get("empty") or "暂时没有推荐结果。"
            lb = QLabel(tip); lb.setWordWrap(True)
            lb.setStyleSheet("color:#e8d27a;font-size:12px;")
            v.addWidget(lb)

        top = res.get("profile_top") or []
        if top:
            dims = {"t": "标签", "a": "演员", "d": "导演", "s": "片商", "x": "系列"}
            bits = [f"{dims.get(t[0], '?')}「{t[2:]}」" for t, _w in top[:14]]
            basis = QLabel("当前偏好向量权重最高的项：" + "、".join(bits))
            basis.setWordWrap(True)
            basis.setStyleSheet("color:#8c8071;font-size:11px;")
            v.addWidget(basis)
        hint = QLabel("鼠标悬停在卡片上可以看到「为什么推荐它」。"
                      "想让推荐更准：给更多片子点 ☆，或在「演员库 / 导演库」里收藏你喜欢的演员与导演；"
                      "也可以到「工具 → 智能推荐」切换普通 / AI 算法，或用「向量编辑」手动加权重。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8c8071;font-size:11px;")
        v.addWidget(hint)
        return self._page(f"智能推荐（{len(picks)} 部）", w)

    def _view_actors(self):
        """演员库：分页 + 增量渲染 + 筛选（收藏/置顶/状态/头像）+ 排序（v1.14.0 反馈 5）。"""
        s = cfg.get_settings()
        prefs = s.actor_prefs or {}
        filt = dict(prefs.get("filters") or {})
        sort = prefs.get("sort") or "works"
        asc = bool(prefs.get("asc", False))

        bar = FilterSortBar("actor", sort, asc, prefs.get("filters") or {})
        total = db.count_people(role_type="Actor", **filt)
        if total <= 0 and not filt:
            return self._page("演员库", QLabel("暂无演员（nfo 中未包含 actor 节点）。"))

        def fetch(off, lim):
            return db.query_people(role_type="Actor", limit=lim, offset=off,
                                   sort=sort, asc=asc, **filt)

        def make(p):
            return ActorCard(p, on_open=self._open_actor, on_fav=self._toggle_person_fav,
                             on_pin=self._toggle_person_pin, on_select=self._select_card,
                             main_win=self)

        grid = LazyGrid(fetch, make, total, kind="actor", unit="位")

        def rebuild():
            cfg.get_settings().set_actor_prefs(bar.sort(), bar.asc(), bar.filters())
            self._replace_current(self._view_actors)

        bar.changed.connect(rebuild)

        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
        w.lazy_grid = grid
        w.filter_bar = bar
        v.addWidget(bar)
        v.addWidget(grid)
        hint = QLabel("头像+信息卡片 · 现役绿/退役黄 · ☆收藏 · 右上角▲置顶 · 单击选中 / 双击查看")
        hint.setStyleSheet("color:#8c8071;font-size:11px;")
        v.addWidget(hint)
        # v1.24.1（反馈 3）：进入演员库 → 收藏/置顶后就重建演员库（别重建到导演库去）
        self._people_builder = self._view_actors
        page = self._page(f"演员库（共 {total} 位）", w)
        # v1.31.0（反馈 1）：撤销 v1.30.0 的 A-Z 索引条，直接返回原页面
        return page

    # ---------- 卡片选中（强调色流光 + 外发光，全局唯一） ----------
    def _select_card(self, card):
        if self._selected_card is card:
            # 同一张卡被重复点：活着的直接返回（H33 就是钉这条）；
            # 但它可能**已经析构**（换页 / 扫描刷新后事件队列里残留的鼠标事件），
            # 那就把悬空引用清掉再往下走 —— 保证 `_selected_card` 不改「活的卡 或 None」。
            if card is not None and not _qt_alive(card):
                self._selected_card = None
            else:
                return
        old = self._selected_card
        if old is not None:
            try:
                old.set_selected(False)
                old.setGraphicsEffect(None)     # 摘掉外发光（Qt 会连带删掉旧 effect）
            except RuntimeError:
                pass
        # 目标卡片也可能已被换页 / 刷新析构（事件队列里残留的鼠标事件）——
        # **先判存活再记账**，否则 `_selected_card` 会留下悬空引用。
        if card is None or not _qt_alive(card):
            self._selected_card = None
            return
        self._selected_card = card
        card.set_selected(True)
        self._apply_card_glow(card)

    def _apply_card_glow(self, card):
        """给选中的卡片挂一层真正「向外扩散」的光晕（v1.25.0 反馈 5）。

        卡片 paintEvent 里那圈描边是画在控件内部的，超出边界的部分会被裁掉，
        所以只能算「内发光」；要让光溢到卡片之外，得靠 QGraphicsDropShadowEffect
        （blur radius 撑开模糊半径、offset 归零 = 四周均匀发光）。
        effect 由卡片自己持有（setGraphicsEffect 会转移所有权），页面重建时随卡片一起销毁。
        """
        if not _qt_alive(card):
            return
        r, g, b = ACCENT_RGB
        try:
            eff = QGraphicsDropShadowEffect(card)
            eff.setBlurRadius(38)
            eff.setOffset(0, 0)
            eff.setColor(QColor(r, g, b, 215))
            card.setGraphicsEffect(eff)
            card.raise_()
        except RuntimeError:
            pass

    # ---------- 演员 / 导演收藏 · 置顶 ----------
    def _toggle_person_fav(self, person):
        db.toggle_person_favorite(person["id"])
        QTimer.singleShot(0, self._refresh_people)

    def _toggle_person_pin(self, person):
        db.toggle_person_pinned(person["id"])
        QTimer.singleShot(0, self._refresh_people)

    def _refresh_people(self):
        """收藏 / 置顶后**原地重排当前所在的人物页**（v1.24.1 反馈 3）。

        原来这里硬编码 `_view_actors` —— 在「导演库」点 ☆ 或 ▲ 之后，页面会被整页换成
        演员库，用户看起来就是「点收藏跳到了演员库」。现在记住进入的是哪个页面，原地重建。
        """
        self._replace_current(self._people_builder or self._view_actors)

    # 兼容旧调用点（v1.24.0 及以前的名字）
    _refresh_actors = _refresh_people

    def _replace_current(self, builder):
        """原地替换当前页面（不污染导航历史），用于收藏/置顶后重排。"""
        widget = builder()
        if widget is None:
            return
        old = self.stack.currentWidget()
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        if old:
            self.stack.removeWidget(old)
            old.deleteLater()      # v1.14.0：原来只 remove 不回收，切多次会堆积页面
        self._selected_card = None

    def _view_actor_detail(self, pid):
        p = db.get_person(pid)
        if p:
            self.set_backdrop(p.get("photo_path") or p.get("thumb"))
        works = db.person_works(pid)
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(12)
        hw = QWidget(); head = QHBoxLayout(hw); head.setContentsMargins(0, 0, 0, 0)
        img = QLabel(); img.setPixmap(circle_pixmap(p.get("photo_path") or p.get("thumb"), 150))
        img.setFixedSize(150, 150)
        head.addWidget(img)
        info = QVBoxLayout()
        # v1.23.0（反馈 1）：演员名字旁加 ☆收藏 / ▲置顶（与 people 表 favorite/pinned 同步）
        name_row = QHBoxLayout(); name_row.setSpacing(8)
        name_row.addWidget(self._h1(p["name"]))
        _fav_on = bool(p.get("favorite"))
        _pin_on = bool(p.get("pinned"))
        fav_btn = compact_button("★ 已收藏" if _fav_on else "☆ 收藏", 96, 26,
                                 "加入 / 取消收藏该演员")
        fav_btn.clicked.connect(lambda _c: self._toggle_actor_fav(pid))
        pin_btn = compact_button("▲ 已置顶" if _pin_on else "△ 置顶", 96, 26,
                                 "置顶 / 取消置顶该演员")
        pin_btn.clicked.connect(lambda _c: self._toggle_actor_pin(pid))
        name_row.addWidget(fav_btn); name_row.addWidget(pin_btn)
        name_row.addStretch(1)
        info.addLayout(name_row)
        if p.get("alias"):
            al = QLabel("别名：" + str(p["alias"]))
            al.setWordWrap(True); al.setStyleSheet("color:#d4af37;")
            info.addWidget(al)
        # 状态（现役 / 退役 / 未知）手动切换；未手动设置的按「作品年份」推断
        st = (p.get("status") or "").strip()
        shown = _person_status(p)
        stat_row = QHBoxLayout()
        stat_row.setSpacing(6)
        stat_lbl = QLabel("状态：")
        stat_lbl.setStyleSheet("color:#a2967f;")
        stat_row.addWidget(stat_lbl)
        for val, txt in (("现役", "现役"), ("退役", "退役"), ("", "未知")):
            # v1.23.0（反馈 1）：改用 compact_button。全局 QPushButton{padding:7px 14px} 会把
            # 26px 高的按钮内容区压到 12px，字形上下被裁 —— 即「按钮没用显示全」的根因。
            # ghost=False 高亮「当前判定」（手动值优先，否则按作品年份推断），与卡片配色一致。
            b = compact_button(txt, 60, 26, ghost=(shown != val))
            b.clicked.connect(lambda _c, vv=val: self._set_actor_status(pid, vv))
            stat_row.addWidget(b)
        hint = QLabel("当前判定：%s%s" % (shown or "未知",
                                    "（手动）" if st else "（按作品年份推断）"))
        hint.setStyleSheet("color:#a2967f;font-size:11px;")
        stat_row.addWidget(hint)
        stat_row.addStretch(1)
        info.addLayout(stat_row)

        facts = []
        if p.get("birthday"):
            facts.append("出生 " + str(p["birthday"]))
        if p.get("romaji"):
            facts.append(str(p["romaji"]))
        meta = _parse_meta(p.get("meta"))
        addr = _clean_meta_value(meta.get("出身地") or meta.get("出生地") or "")
        if addr:
            facts.append("出身地 " + addr)
        height = _clean_meta_value(meta.get("身高") or "")
        if height:
            facts.append("身高 " + height)
        bust, waist, hip = _parse_size(meta.get("尺寸", ""))
        cup = _parse_cup(meta.get("尺寸", ""), *(meta.get(k, "") for k in _CUP_META_KEYS))
        if bust or waist or hip or cup:
            sz = []
            if bust:
                sz.append(f"胸{bust}")
            if waist:
                sz.append(f"腰{waist}")
            if hip:
                sz.append(f"臀{hip}")
            # v1.31.0（反馈 2）：罩杯写在三围最前面（`三围 H 胸88·腰56·臀84`）
            seg = "·".join(sz)
            facts.append("三围 " + ((cup + " " + seg) if cup and seg else (cup or seg)))
            if bust:
                facts.append(f"胸围 {bust}cm")
        facts.append(f"参演作品 {len(works)} 部")
        info.addWidget(QLabel("　·　".join(facts)))
        if p.get("bio"):
            b = QLabel(str(p["bio"])); b.setWordWrap(True); info.addWidget(b)
        if p.get("source"):
            src = QLabel(f"资料补全：{p.get('source')}　{p.get('scraped_at') or ''}")
            src.setStyleSheet("color:#a2967f;font-size:11px;")
            src.setWordWrap(True)
            info.addWidget(src)
        info.addItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
        head.addLayout(info)
        v.addWidget(hw)
        t = QLabel("全部作品"); t.setStyleSheet("font-size:16px;font-weight:bold;color:#f3d9a0;")
        v.addWidget(t)
        v.addWidget(self._grid(works))
        return self._page(None, w)

    def _open_media(self, media):
        m = media or {}
        self.set_backdrop(m.get("fanart") or m.get("poster"))
        self.go(lambda: HeroView(media, on_open_actor=self._open_actor,
                                 on_back=self._back, on_changed=self._refresh_stats))

    def _play_media(self, media):
        """卡片右下角播放按钮：**不进详情页**，直接调本地播放器播放（v1.17.0，反馈 3）。"""
        m = media or {}
        res = player_mod.launch(m.get("file_path") or "")
        if res.get("ok"):
            if m.get("id") is not None:
                db.mark_played(m["id"])     # 与详情页播放口径一致：计入「最近播放 / 观看次数」
                m["play_count"] = (m.get("play_count") or 0) + 1
            self.statusBar().showMessage(res.get("msg", "已开始播放"))
        else:
            QMessageBox.warning(self, "播放失败", res.get("msg", "无法打开播放器"))

    def _toggle_favorite_card(self, media):
        """卡片左下角星标：切收藏（与详情页同一口径：db.toggle_favorite），
        并就地改写这条 media 的 favorite —— 卡片据此刷新星标，不必重建整个列表。"""
        mid = (media or {}).get("id")
        if mid is None:
            return
        new = db.toggle_favorite(mid)
        media["favorite"] = new
        self.statusBar().showMessage("已加入收藏" if new else "已取消收藏")
        self._refresh_stats()          # 只刷新左下角统计与侧边栏计数，不重建当前页

    def _open_actor(self, person):
        pid = person.get("id")
        if pid:
            self.go(lambda: self._view_actor_detail(pid))

    def _set_actor_status(self, pid, val):
        db.update_person(pid, only_missing=False, status=val)
        self.go(lambda: self._view_actor_detail(pid))

    # v1.23.0（反馈 1）：详情页 ☆收藏 / ▲置顶，与 people 表同步（和演员库卡片同一份数据）
    def _toggle_actor_fav(self, pid):
        db.toggle_person_favorite(pid)
        self.go(lambda: self._view_actor_detail(pid))

    def _toggle_actor_pin(self, pid):
        db.toggle_person_pinned(pid)
        self.go(lambda: self._view_actor_detail(pid))

    # ---------- 动作 ----------
    def _do_search(self):
        kw = self.search.text().strip()
        person = None
        if "@" in kw:
            kw, person = kw.split("@", 1)
            kw = kw.strip(); person = person.strip()
        items = db.search_media(kw, person=person, top_only=True)
        title = f"搜索：{self.search.text().strip() or '（空）'}"
        self.go(lambda: self._page(title, self._grid(items)))
        self.statusBar().showMessage(f"搜索到 {len(items)} 条结果")

    def _scan(self):
        root = QFileDialog.getExistingDirectory(self, "选择媒体库根目录")
        if not root:
            return
        self.statusBar().showMessage(f"正在扫描: {root}")
        # 顶栏的「扫描媒体库」不指定库名 → 反查这个目录属于哪个媒体库，好把进度环挂到它旁边
        name = self._lib_for_path(root)
        if name:
            self._lib_ring(name, True, 0, f"正在扫描：{root}")
        self._worker = ScanWorker([root], library_name=name)
        self._worker.progress.connect(lambda m: self.statusBar().showMessage(m))
        self._worker.tick.connect(
            lambda d, t, m, N=name: N and self._lib_ring(N, True, (100 * d / t) if t else 0, m))
        self._worker.live.connect(self._on_scan_live)
        self._worker.done.connect(
            lambda c, N=name: (N and self._lib_ring(N, False), self._on_scan_done(c)))
        self._worker.start()

    def _lib_for_path(self, path):
        """目录 → 它所属的媒体库名（没有就返回 None）。"""
        if not path:
            return None
        p = os.path.abspath(path).rstrip("\\/").lower()
        for lib in cfg.get_settings().libraries:
            for q in (lib.get("paths") or []):
                q2 = os.path.abspath(q).rstrip("\\/").lower() if q else ""
                if q2 and (p == q2 or p.startswith(q2 + os.sep)
                           or q2.startswith(p + os.sep)):
                    return lib["name"]
        return None

    _MODE_CN = {"new": "新添加和修改的", "fill": "补充缺失", "overwrite": "全部并覆盖"}
    _NEW_LIB_TEXT = "＋ 新建媒体库"

    def _scan_library_cat(self, lib, mode):
        paths = [p for p in lib.get("paths", []) if p and os.path.isdir(p)]
        if not paths:
            QMessageBox.information(
                self, "提示",
                f"媒体库「{lib['name']}」尚未设置媒体文件夹，请先右键「编辑」添加。")
            return
        self.statusBar().showMessage(
            f"正在扫描：{lib['name']}（{self._MODE_CN.get(mode, mode)}）")
        applog.log(f"扫描：{lib['name']} mode={mode} paths={paths}")
        name = lib["name"]
        self._lib_ring(name, True, 0, f"正在扫描「{name}」…")
        self._worker = ScanWorker(paths, library_name=name, mode=mode)
        self._worker.progress.connect(lambda m: self.statusBar().showMessage(m))
        # v1.24.0（反馈 11）：进度环跟着扫描走 —— 库名旁边转圈 + 显示百分比
        self._worker.tick.connect(
            lambda d, t, m: self._lib_ring(name, True, (100 * d / t) if t else 0, m))
        self._worker.done.connect(
            lambda c, n=name: (self._lib_ring(n, False), self._on_cat_scan_done(c, n)))
        self._worker.start()

    def _on_cat_scan_done(self, counts, name):
        if counts.get("error"):
            QMessageBox.warning(self, "扫描出错", counts["error"])
            return
        QMessageBox.information(
            self, "扫描完成",
            f"媒体库「{name}」\n电影 {counts.get('movie', 0)} 部 / "
            f"剧集 {counts.get('tvshow', 0)} 部 / 分集 {counts.get('episode', 0)} 个")
        self._refresh_stats()
        lib = cfg.get_settings().library(name)
        if lib:
            self.go(lambda: self._lib_view(lib))

    # ---------- 扫描并删除失效的（v1.15.0 反馈 1） ----------
    def _purge_library(self, lib):
        """对媒体库执行「扫描并删除失效的」：删除索引里但磁盘已不存在的记录。"""
        paths = [p for p in lib.get("paths", []) if p and os.path.isdir(p)]
        n = db.count_media(library=lib["name"])
        if QMessageBox.question(
            self, "扫描并删除失效的",
            f"将对媒体库「{lib['name']}」（共 {n} 条索引）执行检查：\n"
            f"任何「索引里存在、但磁盘文件已不存在」的记录都会被删除"
            f"（磁盘上的文件本身不会被改动）。\n\n确定继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.statusBar().showMessage(f"正在检查失效记录：{lib['name']}")
        # v1.24.0（反馈 11）：失效检查也算「该库正在刷新」→ 进度环转起来（无总数 → 转圈态）
        name = lib["name"]
        self._lib_ring(name, True, 0, f"正在检查失效记录：{name}")
        self._purge_worker = PurgeWorker(name, paths)
        self._purge_worker.progress.connect(
            lambda m, N=name: (self.statusBar().showMessage(m),
                               self._lib_ring(N, True, 0, m)))
        self._purge_worker.done.connect(
            lambda c, nm=lib["name"]: self._on_purge_done(c, nm))
        self._purge_worker.start()

    def _purge_folder(self, name):
        lib = cfg.get_settings().library(name)
        if not lib:
            QMessageBox.information(
                self, "提示",
                f"文件夹「{name}」没有对应的媒体库配置（可能来自旧版索引）。\n\n"
                "请到「设置 → 服务管理 → 媒体库」新建同名媒体库并设置文件夹后再扫描。")
            return
        self._purge_library(lib)

    def _on_purge_done(self, res, name):
        self._lib_ring(name, False)            # 失效检查结束 → 进度环淡出
        if res.get("error"):
            QMessageBox.warning(self, "扫描并删除失效的", res["error"])
            return
        removed = res.get("removed", 0)
        QMessageBox.information(
            self, "扫描并删除失效的",
            f"媒体库「{name}」\n已删除 {removed} 条失效记录（磁盘文件未改动）。")
        self._refresh_stats()
        lib = cfg.get_settings().library(name)
        if lib:
            self.go(lambda: self._lib_view(lib))

    def _open_settings(self):
        """打开设置窗口（**非模态**，v1.14.0 反馈 7）。

        原来用 `dlg.exec()` 模态阻塞：设置窗口开着时主界面完全不能操作，
        设置里跑一次扫描也只能干等。现在改为非模态 —— 设置开着的同时仍可正常
        浏览、搜索、切页、播放；重复点「设置」只是把已开的窗口抬到最前。
        """
        dlg = getattr(self, "_settings_dlg", None)
        if dlg is not None:
            try:
                if dlg.isVisible():
                    dlg.raise_()
                    dlg.activateWindow()
                    return
            except RuntimeError:            # C++ 对象已销毁
                pass
        dlg = SettingsDialog(self, on_changed=self._apply_settings)
        dlg.setModal(False)
        dlg.setWindowModality(Qt.NonModal)
        self._settings_dlg = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_scan_live(self):
        """扫描进行中：就地刷新侧栏计数，若首页正在显示则同步刷新（v1.22.0 反馈 4）。

        新索引的影片会立刻出现在首页，不必等整个扫描跑完。
        """
        self._refresh_stats()          # 左侧媒体库「（N）」实时更新
        cur = self.stack.currentWidget()
        if isinstance(cur, HomeListView):
            cur.live_refresh()

    def _on_scan_done(self, counts):
        if counts.get("error"):
            QMessageBox.warning(self, "扫描出错", counts["error"]); return
        QMessageBox.information(
            self, "扫描完成",
            f"电影 {counts.get('movie',0)} 部 / 剧集 {counts.get('tvshow',0)} 部 / "
            f"分集 {counts.get('episode',0)} 个")
        self._refresh_stats()
        self.go(self._view_home)

    def _apply_settings(self):
        # v1.24.0（反馈 8）：工具里改了算法 / 数量 / 维度开关 / 向量权重 → 作废推荐缓存
        self._smart_picks = []
        self._smart_algo = None
        # 重建侧边栏（导航显隐/顺序、媒体库列表）
        self.h_layout.removeWidget(self.sidebar)
        self.sidebar.deleteLater()
        self.sidebar = self._build_sidebar()
        self.h_layout.insertWidget(0, self.sidebar)
        self._refresh_stats()
        # 外观（磨砂玻璃浓度 / 经典暗色）
        self._apply_appearance()
        # 应用内容卡片 / 首页模块设置：刷新首页
        cur = self.stack.currentWidget()
        if isinstance(cur, HomeListView):
            self.go(self._view_home)

    # ---------- 后台扫描任务 ----------
    def _start_bg_task(self):
        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self._bg_check)
        self._bg_last_run = ""
        s = cfg.get_settings()
        if s.background.get("enabled"):
            self._bg_timer.start(60 * 1000)

    def _bg_check(self):
        s = cfg.get_settings()
        if not s.background.get("enabled"):
            self._bg_timer.stop()
            return
        now = datetime.now()
        if now.strftime("%H:%M") != s.background.get("time", "03:00"):
            return
        freq = s.background.get("frequency", "每天")
        today = now.strftime("%Y-%m-%d")
        last = self._bg_last_run
        if freq == "每天":
            ok = True
        elif freq == "每周":
            ok = (not last) or (now - datetime.strptime(last, "%Y-%m-%d")).days >= 7
        else:  # 每月
            ok = (not last) or (now - datetime.strptime(last, "%Y-%m-%d")).days >= 28
        if not ok or last == today:
            return
        self._bg_last_run = today
        libs = s.libraries
        target = s.background.get("library", "")
        if target:
            libs = [x for x in libs if x["name"] == target]
        if not libs:
            return
        self._bg_queue = list(libs)
        self._bg_scan_next()

    def _bg_scan_next(self):
        if not getattr(self, "_bg_queue", None):
            self._refresh_stats()
            return
        lib = self._bg_queue.pop(0)
        w = ScanWorker(lib.get("paths", []), library_name=lib["name"], mode="new")
        w.done.connect(lambda c: self._bg_scan_next())
        w.start()

    def _refresh_stats(self):
        s = db.stats()
        # v1.27.0（反馈 2）：4 行压成 2 行 —— 侧栏底部的竖向空间要让给「实时状态」面板。
        self.stat_label.setText(f"电影 {s['movies']} · 剧集 {s['tvshows']}\n"
                                f"分集 {s['episodes']} · 演员 {s['people']}")
        # 侧边栏媒体库名称后的总数同步刷新（v1.14.0 反馈 2）
        self._lib_counts = db.library_counts()
        for name, btn in getattr(self, "_lib_btns", {}).items():
            n = self._lib_counts.get(name)
            btn.setText(f"{name}（{n}）" if n is not None else name)

    def _refresh_view(self):
        """顶栏「刷新」：既刷新左下角统计，也重绘当前页面。

        v1.13.0 修复反馈「左下角数量刷新了也没更新」——此前「刷新」只是重载首页，
        `stat_label` 根本没重算，于是数字看着永远不变。
        """
        self._refresh_stats()
        if 0 <= self._nav_i < len(self._nav):
            self.go(self._nav[self._nav_i], push=False)
        else:
            self.go(self._view_home)
        self.statusBar().showMessage("已刷新")

    def closeEvent(self, e):
        """关闭窗口时停掉后台定时器与扫描线程，确保彻底退出、不留后台进程。"""
        t = getattr(self, "_bg_timer", None)
        if t is not None:
            try:
                t.stop()
            except Exception:
                pass
        # 非模态设置窗口（v1.14.0）随主窗口一起关闭
        dlg = getattr(self, "_settings_dlg", None)
        if dlg is not None:
            try:
                dlg.close()
            except Exception:
                pass
        # 侧栏「实时状态」的采样线程（v1.27.0）：进程级单例，这里统一停一次。
        # 注意**不要**让面板自己去 stop() —— 侧栏会被 _apply_settings() 反复重建，
        # 线程若挂在面板下，重建时就会「连同运行中的 QThread 一起被销毁」而 abort 进程。
        try:
            sysmon.stop_shared_worker()
        except Exception:
            pass
        # 等待可能正在跑的后台扫描线程结束
        for attr in ("_worker", "_bg_scan_thread"):
            wk = getattr(self, attr, None)
            if wk is not None and getattr(wk, "isRunning", lambda: False)():
                try:
                    wk.wait(3000)
                except Exception:
                    pass
        super().closeEvent(e)

