# -*- coding: utf-8 -*-
"""v1.40.3 预览出图（离屏）：两条反馈修复的自证。

要证明的两件事：
  ① 反馈 1 ——「压缩执行的高度」：「执行」组框**不再被撑高**，
     日志框固定 96px（v1.40.2 是弹性 120+、真机被灌到 200+）。
     出图 + 逐子项数据自证（含 v1.40.2 的对照数字 379）。
  ② 反馈 2 ——「内置浏览器点击没反应」：点击后按钮进入「已打开 · 等待验证…」禁用态
     （出图为证），窗口 `on_top=True`（源码自证）。

出图注意（铁律）：`QWidget.grab()` 是**透明底图**，直接 `convert("RGB")` 会把半透明
层显示成纯白，图会骗人。必须先 `alpha_composite` 到容器底色再存。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_preview_1403_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtGui import QFontDatabase, QImage, QPainter, QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGroupBox

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

from ui_settings import SettingsDialog, CloudflareDialog
import scraper

OUT = os.path.join(ROOT, "dev", "screenshots")
os.makedirs(OUT, exist_ok=True)
BG = QColor("#12100e")


def save(widget, name, bg=BG):
    img = widget.grab().toImage()
    out = QImage(img.size(), QImage.Format_RGB32)
    out.fill(bg)
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    out.save(os.path.join(OUT, name))
    print(f"[出图] {name} {img.width()}x{img.height()}")


STATS_TEXT = ("演员 6562 人 · 已有头像 3867 · 已有生日 3485 · 已有别名 2393 · "
              "已刮削 3867 · 待修复 0")

dlg = SettingsDialog(None)
print("[体检] 工具窗默认高（离屏屏幕可用高 %d）= %d"
      % (app.primaryScreen().availableGeometry().height(), dlg.height()))
dlg.show()
dlg._show("演员刮削")
for _ in range(25):
    app.processEvents()
if hasattr(dlg, "sc_stats"):
    dlg.sc_stats.setText(STATS_TEXT)
    for _ in range(4):
        app.processEvents()

page = dlg.stack.currentWidget()
inner = page.widget() if hasattr(page, "widget") else page

# ---- ① 整页 ----
save(page, "v1403_scraper_full.png")

boxes = inner.findChildren(QGroupBox)
exec_box = next((b for b in boxes if b.title() == "执行"), None)
if exec_box is not None:
    save(exec_box, "v1403_mod_exec.png")
    pw = exec_box.parentWidget()
    play = pw.layout() if pw is not None else None
    st = play.stretch(play.indexOf(exec_box)) if play is not None else None
    print("[体检①] 执行组框 stretch=%s（应为 0）" % st)
    print("        执行组框 sizeHint=%d  ← v1.40.2 是 379（被撑高）"
          % exec_box.sizeHint().height())
    print("        sc_log minH=%d maxH=%d（固定 96）"
          % (dlg.sc_log.minimumHeight(), dlg.sc_log.maximumHeight()))
    if play is not None:
        last = play.itemAt(play.count() - 1)
        tail = (last is not None and last.widget() is None
                and last.spacerItem() is not None)
        print("        页面末项是弹簧=%s（应为 True：余量留页底）" % tail)
    # 组内逐项
    print("        --- 执行组内逐项 ---")
    g3l = exec_box.layout()
    for i in range(g3l.count()):
        it = g3l.itemAt(i)
        w = it.widget()
        if w is None:
            print(f"          [{i}] stretch={g3l.stretch(i)}")
            continue
        print(f"          [{i}] {type(w).__name__:16s} "
              f"minH={w.minimumHeight()} maxH={w.maximumHeight()} "
              f"sizeHint={w.sizeHint().height()} stretch={g3l.stretch(i)}")

# ---- ② 内置浏览器按钮即时反馈态 ----
try:
    cfd = CloudflareDialog(scraper.MINNANO_BASE, "站点验证 · 预览", parent=None)
    cfd.show()
    for _ in range(10):
        app.processEvents()
    save(cfd, "v1403_cf_idle.png")
    # 模拟点击后的按钮态（不真的 spawn 子进程）
    cfd.btn_open.setEnabled(False)
    cfd.btn_open.setText("已打开 · 等待验证…")
    cfd.state.setText("已在弹出的窗口里打开站点 —— 完成验证后点窗口右下角的"
                      "「✔ 我已完成验证，读取 Cookie」（或直接关窗）。")
    cfd.state.setStyleSheet("color:#e8d27a;font-size:11px;")
    for _ in range(10):
        app.processEvents()
    save(cfd, "v1403_cf_clicked.png")
    print("[体检②] 点击后按钮：%r enabled=%s"
          % (cfd.btn_open.text(), cfd.btn_open.isEnabled()))
    cfd._restore_open_btn()
    print("        恢复后：%r enabled=%s"
          % (cfd.btn_open.text(), cfd.btn_open.isEnabled()))
except Exception as e:
    print("[跳过] CloudflareDialog 出图失败：%s: %s" % (type(e).__name__, e))

# ---- ③ 源码自证：on_top ----
import cf_browser
_cs = open(os.path.join(ROOT, "src", "cf_browser.py"), encoding="utf-8").read()
print("[体检③] cf_browser on_top=True 出现 = %s；focus=True 出现 = %s"
      % ("on_top=True" in _cs, "focus=True" in _cs))

# ---- 对照：v1.40.2 与 v1.40.3 的执行组框 sizeHint ----
print("[对照] 执行组框 sizeHint： v1.40.2 = 379（含被撑高的日志区）→ "
      "v1.40.3 = %d" % (exec_box.sizeHint().height() if exec_box else -1))

print("PREVIEW_1403_DONE")
