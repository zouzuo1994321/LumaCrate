# -*- coding: utf-8 -*-
"""v1.40.4 预览出图 —— 执行页全貌 + 执行组框特写 + 硬锁零弹演示。

自证：打印 ui_settings.__file__。
出图注意：QWidget.grab() 是透明底图，必须 alpha_composite 到容器底色再存，
否则 PIL.convert("RGB") 会把半透明显示成纯白，图会骗人。
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

E = r"E:\【01】自研软件\【26-19】本地影视中心"
SRC = os.path.join(E, "src")
sys.path.insert(0, SRC)
os.chdir(E)

OUT = os.path.join(E, "dev", "_scratch")
os.makedirs(OUT, exist_ok=True)

from PySide6.QtWidgets import QApplication, QWidget, QGroupBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase

app = QApplication.instance() or QApplication(sys.argv)
app.setStyle("Fusion")
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"):
    if os.path.isfile(fp):
        QFontDatabase.addApplicationFont(fp)
        break

from main_window import load_style
load_style(app)

import ui_settings
print("[自证] ui_settings:", ui_settings.__file__)

from PIL import Image
from PySide6.QtGui import QImage


def save_widget(w, path, bg=(28, 26, 24)):
    """抓图 → 垫底色 → 存。透明底图必须先合成，否则半透明层会变纯白。"""
    pm = w.grab()
    img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    wpx, hpx = img.width(), img.height()
    ptr = img.constBits()
    raw = bytes(ptr).__bytes__() if not isinstance(ptr, (bytes, bytearray)) else ptr
    # PySide6 的 constBits 返回 memoryview，stride 可能带 padding
    bpl = img.bytesPerLine()
    im = Image.frombytes("RGBA", (wpx, hpx), bytes(raw)[:bpl * hpx], "raw", "BGRA", bpl, 1)
    canvas = Image.new("RGBA", im.size, bg + (255,))
    canvas.alpha_composite(im)
    canvas.convert("RGB").save(path)
    print(f"  [出图] {os.path.basename(path)}  {canvas.width}x{canvas.height}")
    return canvas.width, canvas.height


dlg = ui_settings.SettingsDialog()
dlg.show()
app.processEvents()

# ---------- 图 1：执行页全貌 ----------
dlg._show("演员刮削")
app.processEvents()
for _ in range(3):
    app.processEvents()
pg = dlg._pg_scraper
# 离屏可用高只有 800 → 窗口被夹到 760 → `_fit_page()` 判定装不下，把页面包进了
# QScrollArea（`_make_scrollable`）。取内层真正的页面 widget 再量布局。
from PySide6.QtWidgets import QScrollArea
pg_outer = pg
if isinstance(pg, QScrollArea):
    print("[体检⓪] 执行页被 QScrollArea 包裹（离屏 760 高装不下 1040 内容），取内层")
    pg = pg.widget()
print("\n[体检①] 整窗 minH=%d maxH=%d（应相等）" % (dlg.minimumHeight(), dlg.maximumHeight()))
lay = pg.layout()
print("[体检①] 执行页 item 数 =", lay.count(), " 末项是控件 =",
      lay.itemAt(lay.count() - 1).widget() is not None)
print("[体检①] 有 SpacerItem =",
      any(lay.itemAt(i).spacerItem() is not None for i in range(lay.count())))
g3 = lay.itemAt(lay.count() - 1).widget()
print("[体检①] 执行组框 sizeHint =", g3.sizeHint().height())
g3lay = g3.layout()
print("[体检①] 执行组框内逐项：")
for i in range(g3lay.count()):
    it = g3lay.itemAt(i)
    w = it.widget()
    if w is None:
        print("   [%d] <spacer>" % i)
    else:
        print("   [%d] %-16s minH=%s maxH=%s sizeHint=%s stretch=%d"
              % (i, type(w).__name__, w.minimumHeight(), w.maximumHeight(),
                 w.sizeHint().height(), g3lay.stretch(i)))

w1, h1 = save_widget(pg, os.path.join(OUT, "v1404_scraper_full.png"))

# ---------- 图 2：执行组框特写 ----------
w2, h2 = save_widget(g3, os.path.join(OUT, "v1404_mod_exec.png"))

# ---------- 图 3：硬锁演示 —— 试着 resize 到 1200 ----------
before = dlg.height()
dlg.resize(dlg.width(), 1200)
app.processEvents()
after = dlg.height()
print(f"\n[体检②] resize 到 1200 高：{before} -> {after}（应不变，锁生效）")
h_before = g3.height()
dlg.resize(dlg.width(), 1200)
app.processEvents()
print(f"[体检②] 执行组框高度：{h_before} -> {g3.height()}（应变不变）")

# ---------- 图 4：两站真实诊断结论 ----------
print("\n[体检③] 两站分层诊断（真实网络）：")
try:
    import scraper
    for key, url in (("minnano", "https://www.minnano-av.com/"),
                     ("imdb", "https://www.imdb.com/")):
        d = scraper.diagnose_host(url, "", 8)
        print(f"   {key:8s} stage={d['stage']:6s} waf={d['waf']} "
              f"code={d['http_code']} body={d['body_len']}")
        print(f"            verdict={d['verdict'][:110]}…")
except Exception as e:
    print("   [警告] 诊断失败:", type(e).__name__, e)

# ---------- 图 5：把新判因文案写进日志框，出图看实际观感 ----------
print("\n[体检④] 把新判因文案灌进日志框出图：")
try:
    import scraper
    d_imdb = scraper.diagnose_host("https://www.imdb.com/", "", 8)
    d_min = scraper.diagnose_host("https://www.minnano-av.com/", "", 8)
    sc = dlg
    sc._log("[测试] IMDB：不可用 — " + scraper._explain("命中反爬挑战页（WAF 回 202）", "imdb"))
    sc._log(f"[诊断] 失败层：{sc._stage_cn(d_imdb['stage'])}　{d_imdb['verdict']}")
    for ln in d_imdb["detail"]:
        sc._log(f"[诊断] {ln}")
    sc._log("[测试] www.minnano-av.com：不可用 — "
            + scraper._explain("HTTP 403", "minnano"))
    sc._log(f"[诊断] 失败层：{sc._stage_cn(d_min['stage'])}　{d_min['verdict']}")
    app.processEvents()
    save_widget(g3, os.path.join(OUT, "v1404_mod_exec_logged.png"))
except Exception as e:
    print("   [警告]", type(e).__name__, e)

dlg.close()
print("\n[完成] 出图目录:", OUT)
