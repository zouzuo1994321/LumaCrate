# -*- coding: utf-8 -*-
"""v2.0.0 预览出图（离屏）。

产物（都落在 docs/preview/）：
  1. v200_components_v1.png / v200_components_v2.png  —— 同一套控件，旧 QSS vs 新 QSS
  2. v200_components_compare.png                      —— 上面两张并排（左旧右新）
  3. v200_swatches_compare.png                        —— 色卡：v1 方形（按 v1 实现复刻）vs v2 正圆
  4. v200_main.png                                    —— 主窗 1920x1080
  5. v200_settings_appearance.png                     —— 工具窗「个性化设置」页
  6. v200_actorcheck.png                              —— 演员检测页（拖拽条保持原样）
  7. v200_grip_band.png                               —— 拖拽条把手带放大（证明没被 QSS 盖掉）

注意：`QWidget.grab()` 是透明底图，PIL 直接 convert("RGB") 会把半透明层算成纯白，
所以一律先 alpha_composite 到取样出来的底色再存（v1.28.0 踩过）。
"""
import colorsys
import os
import sys
import tempfile
from collections import Counter

from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QProgressBar, QPushButton,
                               QRadioButton, QSlider, QSpinBox, QVBoxLayout,
                               QWidget)

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import config as cfg
import database as db

TMP = tempfile.mkdtemp(prefix="lmc_v200_preview_")
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()
try:
    import backdrop
    backdrop.auto_apply = lambda w, *a, **k: None
except Exception:
    pass

import main_window as mw
from main_window import MainWindow, load_style

try:
    import ui_actorcheck as uac
except Exception:
    uac = None
try:
    from ui_settings import SettingsDialog
except Exception:
    SettingsDialog = None

OUT = os.path.join(ROOT, "docs", "preview")
os.makedirs(OUT, exist_ok=True)

OLD_ACCENT = "#c0392b"
NEW_ACCENT = "#006fee"
LEGACY_QSS = os.path.join(ROOT, "docs", "legacy", "style_v1_46_15.qss")


# --------------------------------------------------------------------------
# 旧 QSS 渲染：令牌替换规则与 v1 的 render_style() 一致，只是派生系数用旧的
# --------------------------------------------------------------------------
def _old_shades(hexv):
    r = int(hexv[1:3], 16); g = int(hexv[3:5], 16); b = int(hexv[5:7], 16)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)

    def mk(dl, ds):
        ll = max(0.0, min(1.0, l + dl)); ss = max(0.0, min(1.0, s + ds))
        rr, gg, bb = colorsys.hls_to_rgb(h, ll, ss)
        return (int(round(rr * 255)), int(round(gg * 255)), int(round(bb * 255)))

    return {"base": (r, g, b), "dark": mk(-0.135, 0.05),
            "deep": mk(-0.080, 0.03), "light": mk(0.110, 0.08)}


def legacy_qss(accent=OLD_ACCENT):
    with open(LEGACY_QSS, encoding="utf-8") as f:
        qss = f.read()
    veil, panel = cfg.appearance_alphas({"style": "glass", "alpha": None})
    surf = min(255, int(panel) + 30)
    dlg = min(255, max(int(surf), 232))
    for token, val in (("__VEIL__", veil), ("__PANEL__", panel),
                       ("__SURF__", surf), ("__DLG__", dlg)):
        qss = qss.replace(token, str(int(val)))
    sh = _old_shades(accent)
    for token, key in (("__ACCENT_LIGHT__", "light"), ("__ACCENT_DARK__", "dark"),
                       ("__ACCENT_DEEP__", "deep"), ("__ACCENT__", "base")):
        r, g, b = sh[key]
        qss = qss.replace("rgba(%s," % token, "rgba(%d, %d, %d," % (r, g, b))
        qss = qss.replace(token, "#%02x%02x%02x" % (r, g, b))
    return qss


# --------------------------------------------------------------------------
# 存图：透明底 → 贴底色
# --------------------------------------------------------------------------
def save_rgb(pix, out_path, bg=(17, 17, 19), force_bg=None):
    """grab → 贴底色 → 存 RGB。

    `force_bg`：强制底色。**页面级控件一定要传** —— 页面根控件在 QSS 里是
    `background: transparent`，抓出来整张图都是透明的，此时「按最多数不透明像素
    取样」会被某一块彩色控件带偏（v2.0.0 出图时演员检测页整张变成按钮蓝）。
    """
    raw = os.path.join(TMP, "raw.png")
    pix.save(raw)
    im = Image.open(raw).convert("RGBA")
    if force_bg is not None:
        base = Image.new("RGBA", im.size, tuple(force_bg) + (255,))
    else:
        cnt = Counter()
        for y in range(0, im.height, 5):
            for x in range(0, im.width, 7):
                p = im.getpixel((x, y))
                if p[3] > 240:
                    cnt[p[:3]] += 1
        base = Image.new("RGBA", im.size, (cnt.most_common(1)[0][0] if cnt else bg) + (255,))
    Image.alpha_composite(base, im).convert("RGB").save(out_path)
    return out_path


class _Backdrop(QWidget):
    """预览用的画布：自绘底色（不依赖 QSS，免得两套 QSS 各画一个色）。"""

    def __init__(self, bg):
        super().__init__()
        self._bg = QColor(*bg)
        self.setAttribute(Qt.WA_StyledBackground, False)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), self._bg)
        p.end()


class _OldSwatch(QWidget):
    """v1 色卡复刻：30×24 圆角扁平方形（radius 6），选中套亮描边 + ✓。

    v1.43.4 定稿的形状，代码已在 v2.0.0 改成正圆 —— 这里只为对照图重建。
    """

    W, H = 30, 24

    def __init__(self, hexv, on=False):
        super().__init__()
        self._c = QColor(hexv)
        self._on = on
        self.setFixedSize(self.W, self.H)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(self._c)
        p.drawRoundedRect(r, 6, 6)
        if self._on:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(255, 255, 255, 230))
            p.drawRoundedRect(r, 6, 6)
            f = p.font(); f.setPixelSize(12); f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(255, 255, 255))
            p.drawText(r, Qt.AlignCenter, "\u2713")
        p.end()


OLD_COLORS = ["#c0392b", "#e2659a", "#e08a3c", "#d4af37", "#5aa469", "#2e9e8f",
              "#3fa9c9", "#3b6fd4", "#8e5bd4", "#b07aa1", "#c9d6dd", "#7a8b99"]


def _section(title, v2=True):
    lb = QLabel(title)
    lb.setStyleSheet("color:#a1a1aa;font-size:11px;font-weight:700;" if v2
                     else "color:#9b8e7a;font-size:11px;font-weight:700;")
    return lb


def build_gallery(v2=True, bg=(17, 17, 19)):
    """一套有代表性的控件。v2=False 时色卡用 v1 方形复刻。"""
    root = _Backdrop(bg)
    root.resize(880, 570)
    lay = QVBoxLayout(root)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(10)

    # ---- 按钮 ----
    lay.addWidget(_section("Buttons", v2))
    row = QHBoxLayout(); row.setSpacing(8)
    b1 = QPushButton("默认按钮")
    b2 = QPushButton("主操作"); b2.setObjectName("Primary")
    b3 = QPushButton("次操作"); b3.setObjectName("Ghost")
    b4 = QPushButton("禁用"); b4.setEnabled(False)
    c1 = QPushButton("未选"); c1.setObjectName("Chip"); c1.setCheckable(True)
    c2 = QPushButton("已选"); c2.setObjectName("Chip"); c2.setCheckable(True); c2.setChecked(True)
    for w in (b1, b2, b3, b4, c1, c2):
        row.addWidget(w)
    row.addStretch(1)
    lay.addLayout(row)

    # ---- 输入类 ----
    lay.addWidget(_section("Inputs", v2))
    row = QHBoxLayout(); row.setSpacing(8)
    le = QLineEdit(); le.setPlaceholderText("搜索标题 / 番号 …"); le.setFixedWidth(210)
    cb = QComboBox(); cb.addItems(["年份", "评分", "加入时间"]); cb.setFixedWidth(110)
    sp = QSpinBox(); sp.setRange(0, 9999); sp.setValue(2026); sp.setFixedWidth(90)
    row.addWidget(le); row.addWidget(cb); row.addWidget(sp)
    row.addStretch(1)
    lay.addLayout(row)

    row = QHBoxLayout(); row.setSpacing(10)
    ck1 = QCheckBox("已勾选"); ck1.setChecked(True)
    ck2 = QCheckBox("未勾选")
    r1 = QRadioButton("单选 A"); r1.setChecked(True)
    r2 = QRadioButton("单选 B")
    for w in (ck1, ck2, r1, r2):
        row.addWidget(w)
    row.addStretch(1)
    lay.addLayout(row)

    # ---- 滑块 / 进度 ----
    lay.addWidget(_section("Slider / Progress", v2))
    sl = QSlider(Qt.Horizontal); sl.setRange(0, 100); sl.setValue(62)
    sl.setFixedWidth(260)
    pb = QProgressBar(); pb.setRange(0, 100); pb.setValue(62); pb.setFixedWidth(260)
    pb.setTextVisible(False)
    row = QHBoxLayout(); row.setSpacing(14)
    row.addWidget(sl); row.addWidget(pb); row.addStretch(1)
    lay.addLayout(row)

    # ---- 列表 ----
    lay.addWidget(_section("List", v2))
    lw = QListWidget()
    lw.setFixedHeight(96)
    for i, t in enumerate(["4K 原盘 · 2160p", "蓝光 · 1080p", "WEB-DL · 1080p"]):
        it = QListWidgetItem(t)
        lw.addItem(it)
        if i == 0:
            it.setSelected(True)
    lay.addWidget(lw)

    # ---- 色卡 ----
    lay.addWidget(_section("Accent palette", v2))
    row = QHBoxLayout(); row.setSpacing(8)
    if v2:
        from ui_settings import _AccentSwatch
        for i, (nm, hx) in enumerate(cfg.ACCENT_COLORS):
            sw = _AccentSwatch(hx, nm)
            sw.set_on(i == 0)
            row.addWidget(sw)
    else:
        for i, hx in enumerate(OLD_COLORS):
            row.addWidget(_OldSwatch(hx, on=(i == 0)))
    row.addStretch(1)
    lay.addLayout(row)

    # ---- 开关 ----
    if v2:
        lay.addWidget(_section("Switch", v2))
        try:
            from ui_settings import ToggleSwitch
            row = QHBoxLayout(); row.setSpacing(12)
            for on in (True, False):
                t = ToggleSwitch(); t.setChecked(on)
                # 离屏下动画不跑完 → _pos 停在 0，两个开关都会画成「关」。
                # 预览图要的是终态，直接把动画收尾。
                try:
                    t._anim.stop()
                    t._pos = 1.0 if on else 0.0
                    t.update()
                except Exception:
                    pass
                row.addWidget(t)
            row.addStretch(1)
            lay.addLayout(row)
        except Exception as ex:
            lay.addWidget(QLabel("ToggleSwitch 不可用: %s" % ex))

    lay.addStretch(1)
    return root


# ==========================================================================
# ① + ② 组件对照
# ==========================================================================
shots = {}
for tag, use_v2 in (("v1", False), ("v2", True)):
    if use_v2:
        load_style(app, {"accent": NEW_ACCENT, "style": "glass", "alpha": None})
        g = build_gallery(True, (17, 17, 19))
    else:
        app.setStyleSheet(legacy_qss())
        g = build_gallery(False, (23, 19, 15))
    g.setAttribute(Qt.WA_DontShowOnScreen, True)
    g.show()
    app.processEvents()
    app.processEvents()
    path = os.path.join(OUT, "v200_components_%s.png" % tag)
    save_rgb(g.grab(), path, force_bg=((17, 17, 19) if use_v2 else (23, 19, 15)))
    shots[tag] = path
    print("saved", os.path.basename(path), g.width(), "x", g.height())

a = Image.open(shots["v1"]); b = Image.open(shots["v2"])
gap = 10
cmp_im = Image.new("RGB", (a.width + gap + b.width, max(a.height, b.height)), (8, 8, 9))
cmp_im.paste(a, (0, 0)); cmp_im.paste(b, (a.width + gap, 0))
cmp_im.save(os.path.join(OUT, "v200_components_compare.png"))
print("saved v200_components_compare.png")

# ==========================================================================
# ③ 色卡对照（v1 方形复刻 vs v2 正圆真控件）
# ==========================================================================
def swatch_strip(v2):
    bg = (17, 17, 19) if v2 else (23, 19, 15)
    w = _Backdrop(bg)
    w.resize(700, 72 if v2 else 66)
    lay = QHBoxLayout(w)
    lay.setContentsMargins(18, 12 if not v2 else 16, 18, 12 if not v2 else 16)
    lay.setSpacing(10)
    if v2:
        from ui_settings import _AccentSwatch
        for i, (nm, hx) in enumerate(cfg.ACCENT_COLORS):
            sw = _AccentSwatch(hx, nm)
            sw.set_on(i == 0)
            lay.addWidget(sw)
    else:
        for i, hx in enumerate(OLD_COLORS):
            lay.addWidget(_OldSwatch(hx, on=(i == 0)))
    lay.addStretch(1)
    w.setAttribute(Qt.WA_DontShowOnScreen, True)
    w.show()
    app.processEvents()
    return w


load_style(app, {"accent": NEW_ACCENT, "style": "glass", "alpha": None})
w2 = swatch_strip(True)
p2 = save_rgb(w2.grab(), os.path.join(TMP, "sw2.png"), (17, 17, 19), force_bg=(17, 17, 19))
app.setStyleSheet(legacy_qss())
w1 = swatch_strip(False)
p1 = save_rgb(w1.grab(), os.path.join(TMP, "sw1.png"), (23, 19, 15), force_bg=(23, 19, 15))
i1 = Image.open(p1); i2 = Image.open(p2)
out = Image.new("RGB", (max(i1.width, i2.width), i1.height + i2.height + 8), (8, 8, 9))
out.paste(i1, (0, 0)); out.paste(i2, (0, i1.height + 8))
out.save(os.path.join(OUT, "v200_swatches_compare.png"))
print("saved v200_swatches_compare.png")

# ==========================================================================
# ④ 主窗
# ==========================================================================
load_style(app, {"accent": NEW_ACCENT, "style": "glass", "alpha": None})
win = MainWindow()
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()
app.processEvents()
app.processEvents()
save_rgb(win.grab(), os.path.join(OUT, "v200_main.png"), (10, 10, 11), force_bg=(10, 10, 11))
print("saved v200_main.png", win.width(), "x", win.height())

# ==========================================================================
# ⑤ 工具窗 → 个性化设置
# ==========================================================================
if SettingsDialog is not None:
    class _FakeScr:
        def availableGeometry(self):
            return QRect(0, 0, 2560, 1392)

        def geometry(self):
            return QRect(0, 0, 2560, 1440)

    SettingsDialog.screen = lambda self: _FakeScr()
    dlg = SettingsDialog(win)
    dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
    dlg.resize(1320, 960)
    dlg.show()
    app.processEvents()
    for k, b in dlg.sub_btns.items():
        if "个性化" in k:
            b.click()
            break
    app.processEvents()
    app.processEvents()
    pg = dlg._pg_appear if hasattr(dlg, "_pg_appear") else None
    target = pg if (pg is not None and pg.width() > 200) else dlg
    save_rgb(target.grab(), os.path.join(OUT, "v200_settings_appearance.png"), (10, 10, 11), force_bg=(10, 10, 11))
    print("saved v200_settings_appearance.png", target.width(), "x", target.height())
    dlg.close()

# ==========================================================================
# ⑥ 演员检测页 + ⑦ 拖拽条把手带
# ==========================================================================
if uac is not None:
    page = uac.ActorCheckPage()
    page.setAttribute(Qt.WA_DontShowOnScreen, True)
    page.resize(1200, 860)
    page.show()
    app.processEvents(); app.processEvents()
    save_rgb(page.grab(), os.path.join(OUT, "v200_actorcheck.png"), (17, 17, 19),
             force_bg=(17, 17, 19))
    print("saved v200_actorcheck.png")

    sps = page.findChildren(uac._GripSplitter)
    print("grip splitters:", len(sps), [s.objectName() for s in sps])
    if sps:
        sp = sps[0]
        y0 = sp.mapTo(page, sp.rect().topLeft()).y() + sp.sizes()[0]
        band = page.grab(QRect(0, y0, page.width(), 14))
        pth = save_rgb(band, os.path.join(TMP, "band.png"), (17, 17, 19),
                       force_bg=(17, 17, 19))
        im = Image.open(pth)
        im = im.crop((im.width // 2 - 240, 0, im.width // 2 + 240, 14))
        im = im.resize((im.width * 4, im.height * 8), Image.NEAREST)
        im.save(os.path.join(OUT, "v200_grip_band.png"))
        print("saved v200_grip_band.png")

print("PREVIEW_DONE")
