# -*- coding: utf-8 -*-
"""v1.40.2 预览出图（离屏）：三条反馈修复的前后对照。

要证明的三件事：
  ① 反馈 1 —— 「站点验证」对话框**行距压缩**：边距 16→10、行距 12→7、
     两步说明压成单行、高级面板内边距与输入框高度同步收紧。出图为证。
  ② 反馈 2 —— 新增**独立「读取 Cookie」按钮**（用户明确要求），
     且失败时给**分层判因**（不是笼统的「cookie 过期」）。
  ③ 反馈 3 —— 「执行」区**底部不留白**：执行组框吃 stretch、页面无页级弹簧；
     工具窗默认高 **960px**。出图为证 + 逐子项数据自证。

出图注意（铁律）：`QWidget.grab()` 是**透明底图**，直接 `convert("RGB")` 会把半透明
层显示成纯白，图会骗人。必须先 `alpha_composite` 到容器底色再存。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_preview_1402_")
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
print("[体检③] 工具窗默认高（resize）= %d x %d" % (dlg.width(), dlg.height()))
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
save(page, "v1402_scraper_full.png")

boxes = inner.findChildren(QGroupBox)

# ---- ② 执行区：反馈 3 的主战场（底部留白） ----
exec_box = next((b for b in boxes if b.title() == "执行"), None)
if exec_box is not None:
    save(exec_box, "v1402_mod_exec.png")
    print("[体检①] 执行组框 h=%d sh=%d minH=%d  （吃 stretch → 底边贴页底，不再有空白带）"
          % (exec_box.height(), exec_box.sizeHint().height(),
             exec_box.minimumHeight()))
    print("        日志框 minH=%d maxH=%d h=%d（弹性）"
          % (dlg.sc_log.minimumHeight(), dlg.sc_log.maximumHeight(),
             dlg.sc_log.height()))
    _pw = exec_box.parentWidget()
    _play = _pw.layout() if _pw is not None else None
    if _play is not None:
        print("        页面布局：count=%d spacing=%d"
              % (_play.count(), _play.spacing()))
        _last = _play.itemAt(_play.count() - 1)
        print("        末项是弹簧 spacer：%s（应为 False）"
              % (_last is not None and _last.widget() is None
                 and _last.spacerItem() is not None))

# ---- ③ 站点验证对话框：反馈 1（行距）+ 反馈 2（读 Cookie 按钮） ----
try:
    dlg._open_cloudflare()
    for _ in range(12):
        app.processEvents()
    cf = getattr(dlg, "_cf_dlg", None)
    if cf is not None:
        cf.show()
        for _ in range(10):
            app.processEvents()
        save(cf, "v1402_cloudflare_compact.png")
        _lay = cf.layout()
        _m = _lay.contentsMargins()
        print("[体检②] CloudflareDialog 边距 L%d T%d R%d B%d spacing=%d "
              "sizeHint=%dx%d"
              % (_m.left(), _m.top(), _m.right(), _m.bottom(), _lay.spacing(),
                 cf.sizeHint().width(), cf.sizeHint().height()))
        print("        「读取 Cookie」按钮=%r　「打开内置浏览器」=%r"
              % (getattr(cf, "btn_read").text(), cf.btn_open.text()))
        # 展开「高级 ▾」再出一张
        cf.btn_adv.setChecked(True)
        for _ in range(10):
            app.processEvents()
        save(cf, "v1402_cloudflare_advanced.png")
        zoom(cf, "v1402_cloudflare_zoom.png", factor=2)
        cf.close()
except Exception as e:
    print("[跳过] CloudflareDialog 出图失败：%s: %s" % (type(e).__name__, e))

# ---- ④ 失败判因文案（静态文本出图，证明不再误导） ----
try:
    import scraper
    diag = scraper.diagnose_host("https://www.minnano-av.com/", "", 6)
    print("[体检④] diagnose_host stage=%s ok=%s" % (diag.get("stage"), diag.get("ok")))
    print("        verdict=%s" % diag.get("verdict"))
except Exception as e:
    print("[跳过] diagnose_host 失败：%s" % e)

print("PREVIEW_1402_DONE")
