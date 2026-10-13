# -*- coding: utf-8 -*-
"""v1.40.0 预览出图（离屏）：演员刮削页改版的前后对照。

要证明的三件事（用户三条 UI 反馈）：
  ① 反馈 1 ——「演员资料统计」从数据源组框里**抽出来**，成为带标题/边框的独立模块；
     并把「数据源组框被压缩 → 列表只剩一两行」这个真实病灶一并治好
     （按内容真实需求钉住组框最小高）。
  ② 反馈 2 ——「执行」区日志框由 `setFixedHeight(48)`（≈3 行）加大到最小 240px。
  ③ 反馈 3 ——「代理」由「填了才生效」的隐式行为改成**显式开关**，关掉即纯直连。

出图注意（铁律）：`QWidget.grab()` 是**透明底图**，直接 `convert("RGB")` 会把半透明
层显示成纯白，图会骗人。必须先 `alpha_composite` 到容器底色再存。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_preview_1400_")
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
    """放大出图（看细节：开关形态、统计条单行、日志区高度）。"""
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
# 反馈 1 的截图里那串统计数字（6562 / 3867 / 3485 / 2393 / 3867 / 0）
STATS_TEXT = ("演员 6562 人 · 已有头像 3867 · 已有生日 3485 · 已有别名 2393 · "
              "已刮削 3867 · 待修复 0")

dlg = SettingsDialog(None)
dlg.resize(1085, 920)
dlg.show()
dlg._show("演员刮削")
for _ in range(25):
    app.processEvents()

# 把统计条填成用户截图里的真实文案（临时库没有 people 表，否则会显示「统计失败」）
if hasattr(dlg, "sc_stats"):
    dlg.sc_stats.setText(STATS_TEXT)
    for _ in range(4):
        app.processEvents()

page = dlg.stack.currentWidget()          # ⚠ 用 stack 当前页，别用 `_pg_scraper`：
# `_make_scrollable()` 会把页面包进 QScrollArea 并换掉 `_pg_scraper` 的引用，
# 若抓的是旧引用会得到一张 640×480 的空图（踩过）。
inner = page.widget() if hasattr(page, "widget") else page

# ---- ① 整页（反馈 1 + 2 + 3 的所有改动都在这一页） ----
save(page, "v1400_scraper_full.png")

# ---- ② 前两个模块特写：「演员刮削」+「演员资料统计」独立成模块 ----
boxes = inner.findChildren(QGroupBox)
stats_box = next((b for b in boxes if b.title() == "演员资料统计"), None)
enabled_box = next((b for b in boxes if b.title() == "演员刮削"), None)
if stats_box is not None and enabled_box is not None:
    save(enabled_box, "v1400_mod_switch.png")
    save(stats_box, "v1400_mod_stats.png")
    zoom(stats_box, "v1400_mod_stats_zoom.png", factor=2)

# ---- ③ 数据源组框（另存一张：证明它不再夹着统计条、且列表不再被压扁） ----
src_box = next((b for b in boxes if "数据源" in b.title()), None)
if src_box is not None:
    save(src_box, "v1400_mod_sources.png")
    print("[体检] 数据源组框 h=%d sh=%d minH=%d"
          % (src_box.height(), src_box.sizeHint().height(), src_box.minimumHeight()))
    _lay = src_box.layout()
    for _i in range(_lay.count()):
        _w = _lay.itemAt(_i).widget()
        if _w is None:
            continue
        _extra = ""
        if isinstance(_w, QLabel):
            _extra = "  hfw=%d text=%r" % (
                _w.heightForWidth(_w.width()) if _w.width() > 0 else -1,
                _w.text()[:26])
        print("        [%d] %-13s h=%3d sh=%3d%s"
              % (_i, type(_w).__name__, _w.height(), _w.sizeHint().height(), _extra))

# ---- ④ 刮削策略：代理显式开关（反馈 3）----
strat_box = next((b for b in boxes if b.title() == "刮削策略"), None)
if strat_box is not None:
    save(strat_box, "v1400_mod_strategy.png")
    # 单独把「代理」那一行放大，看清输入框 + 「使用代理」+ 开关
    if hasattr(dlg, "sc_proxy_on"):
        row_host = dlg.sc_proxy.parentWidget()
        if row_host is not None:
            zoom(row_host, "v1400_proxy_row_zoom.png", factor=2)
        # 附带一张「开关打开」态，证明输入框会从置灰恢复
        dlg.sc_proxy_on.setChecked(True)
        for _ in range(6):
            app.processEvents()
        if row_host is not None:
            zoom(row_host, "v1400_proxy_row_on_zoom.png", factor=2)
        dlg.sc_proxy_on.setChecked(False)
        for _ in range(6):
            app.processEvents()

# ---- ⑤ 执行区（反馈 2：日志框加大）----
exec_box = next((b for b in boxes if b.title() == "执行"), None)
if exec_box is not None:
    save(exec_box, "v1400_mod_exec.png")
    print("[体检] 日志框 minH=%d maxH=%d h=%d"
          % (dlg.sc_log.minimumHeight(), dlg.sc_log.maximumHeight(),
             dlg.sc_log.height()))

# ---- ⑥ Cloudflare 验证助手（反馈 4 的出路）----
try:
    dlg._open_cloudflare()
    for _ in range(10):
        app.processEvents()
    cf = getattr(dlg, "_cf_dlg", None)
    if cf is not None:
        save(cf, "v1400_cloudflare_dialog.png")
except Exception as e:
    print("[跳过] CloudflareDialog 出图失败：%s: %s" % (type(e).__name__, e))

print("PREVIEW_1400_DONE")
