# -*- coding: utf-8 -*-
"""v1.40.1 预览出图（离屏）：三条反馈修复的前后对照。

要证明的三件事：
  ① 反馈 1 —— 数据源组框**底部不再留空**（`_pin_min_height` 不再被 `sizeHint()`
     虚高：QListWidget 192→120、折行标签 60→heightForWidth）。出图同时打印
     「组框 h / sh / minH」与逐子项明细，用数据自证。
  ② 反馈 2 —— 「执行」区日志框由最小 240px 缩回 **120px**（仍弹性，拉窗跟着长）。
  ③ 反馈 3 —— 「站点验证」对话框改为**内置浏览器**：主入口「打开内置浏览器」+
     两步走文案 + 「高级 ▾（手动粘贴 cookie）」折叠兜底；并单独出一张「展开态」。

出图注意（铁律）：`QWidget.grab()` 是**透明底图**，直接 `convert("RGB")` 会把半透明
层显示成纯白，图会骗人。必须先 `alpha_composite` 到容器底色再存。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_preview_1401_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtGui import QFontDatabase, QImage, QPainter, QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db
import applog

db.db_path = lambda: os.path.join(TMP, "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

from main_window import load_style

load_style(app)

from ui_settings import SettingsDialog

OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)

BG = QColor("#12100e")


def save(widget, name, bg=BG):
    """把控件截图垫到容器底色后存盘（否则半透明层会被显示成纯白）。"""
    img = widget.grab().toImage()
    out = QImage(img.size(), QImage.Format_RGB32)
    out.fill(bg)
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    path = os.path.join(OUT, name)
    out.save(path)
    print(f"[出图] {name} {img.width()}x{img.height()}")
    return path


def zoom(widget, name, factor=2, bg=BG):
    """放大出图（看细节）。"""
    src = widget.grab().toImage()
    sc = src.scaled(src.width() * factor, src.height() * factor,
                    Qt.KeepAspectRatio, Qt.FastTransformation)
    out = QImage(sc.size(), QImage.Format_RGB32)
    out.fill(bg)
    p = QPainter(out)
    p.drawImage(0, 0, sc)
    p.end()
    out.save(os.path.join(OUT, name))
    print(f"[出图] {name} {sc.width()}x{sc.height()}")


# ================================================================ 真实数据形态
STATS_TEXT = ("演员 6562 人 · 已有头像 3867 · 已有生日 3485 · 已有别名 2393 · "
              "已刮削 3867 · 待修复 0")

dlg = SettingsDialog(None)
dlg.resize(1085, 920)
dlg.show()
dlg._show("演员刮削")
for _ in range(25):
    app.processEvents()

if hasattr(dlg, "sc_stats"):
    dlg.sc_stats.setText(STATS_TEXT)
    for _ in range(4):
        app.processEvents()

page = dlg.stack.currentWidget()          # ⚠ 用 stack 当前页（`_make_scrollable` 换过引用）
inner = page.widget() if hasattr(page, "widget") else page

# ---- ① 整页（三条反馈的改动都在这一页） ----
save(page, "v1401_scraper_full.png")

boxes = inner.findChildren(QGroupBox)

# ---- ② 数据源组框：反馈 1 的主战场 ----
src_box = next((b for b in boxes if "数据源" in b.title()), None)
if src_box is not None:
    save(src_box, "v1401_mod_sources.png")
    print("[体检①] 数据源组框 h=%d sh=%d minH=%d  （v1.40.0 时 minH=280）"
          % (src_box.height(), src_box.sizeHint().height(), src_box.minimumHeight()))
    _lay = src_box.layout()
    _tot = 0
    for _i in range(_lay.count()):
        _w = _lay.itemAt(_i).widget()
        if _w is None:
            continue
        _need = 0
        try:
            if _w.hasHeightForWidth() and _w.width() > 0:
                _need = _w.heightForWidth(_w.width())
        except Exception:
            _need = 0
        if _need <= 0:
            _need = _w.sizeHint().height()
        _need = max(_need, _w.minimumSizeHint().height())
        _cap = _w.maximumHeight()
        _raw = _need
        if 0 < _cap < _need:
            _need = _cap
        _tot += _need
        print("        [%d] %-13s sh=%4d cap=%8d -> need=%4d  h=%3d"
              % (_i, type(_w).__name__, _w.sizeHint().height(), _cap, _need, _w.height()))
    print("        逐子项真实需求合计 = %d" % _tot)
    # 组框底部「留白」= 组框高 - 内容需求（越接近 0 越好）
    print("        ⚠ 底部留白提示：组框 minH - 内容需求 = %d"
          % (src_box.minimumHeight() - _tot))

# ---- ③ 执行区：反馈 2（日志框 120px）----
exec_box = next((b for b in boxes if b.title() == "执行"), None)
if exec_box is not None:
    save(exec_box, "v1401_mod_exec.png")
    print("[体检②] 日志框 minH=%d maxH=%d h=%d  （v1.40.0 时 minH=240，现应为 120）"
          % (dlg.sc_log.minimumHeight(), dlg.sc_log.maximumHeight(), dlg.sc_log.height()))

# ---- ④ 站点验证对话框：反馈 3（内置浏览器）----
try:
    cfd = dlg._open_cloudflare()
    for _ in range(12):
        app.processEvents()
    cf = getattr(dlg, "_cf_dlg", None) or cfd
    if cf is not None:
        cf.show()
        for _ in range(10):
            app.processEvents()
        save(cf, "v1401_cloudflare_builtin.png")
        h = cf.sizeHint().height()
        print("[体检③] CloudflareDialog 主入口=%r 高级默认可见=%s h=%d"
              % (cf.btn_open.text(), cf.adv.isVisibleTo(cf), cf.height()))
        # 展开「高级 ▾」再出一张
        cf.btn_adv.setChecked(True)
        for _ in range(10):
            app.processEvents()
        save(cf, "v1401_cloudflare_advanced.png")
        zoom(cf, "v1401_cloudflare_zoom.png", factor=2)
        cf.close()
except Exception as e:
    print("[跳过] CloudflareDialog 出图失败：%s: %s" % (type(e).__name__, e))

print("PREVIEW_1401_DONE")
