# -*- coding: utf-8 -*-
"""v1.40.4 补充出图：把**真机 app.log 里的真实判因行**渲染进日志框，出图。

为什么要这一步：真机 `74_live_diag_v1404.png` 是全黑的 ——
`live_verify` 的 `g.grab()` 抓的是**透明底图**（`QWidget.grab()` 不画父底色），
PIL 直接 convert("RGB") 就把半透明当纯白/纯黑。真机证据改用 **app.log 原文**，
这里只做「观感图」，数据源是**真机日志里的那两行**（不是造的字串）。
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"

E = r"E:\【01】自研软件\【26-19】本地影视中心"
sys.path.insert(0, os.path.join(E, "src"))
os.chdir(E)

OUT = os.path.join(E, "dev", "screenshots")

from PySide6.QtWidgets import QApplication, QGroupBox
from PySide6.QtGui import QFontDatabase, QImage

app = QApplication.instance() or QApplication(sys.argv)
app.setStyle("Fusion")
for fp in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.isfile(fp):
        QFontDatabase.addApplicationFont(fp)
        break

from main_window import load_style
load_style(app)
import ui_settings

print("[自证] ui_settings:", ui_settings.__file__)

from PIL import Image


def save_widget(w, path, bg=(24, 23, 22)):
    pm = w.grab()
    img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    wpx, hpx = img.width(), img.height()
    bpl = img.bytesPerLine()
    raw = bytes(img.constBits())[:bpl * hpx]
    im = Image.frombytes("RGBA", (wpx, hpx), raw, "raw", "BGRA", bpl, 1)
    canvas = Image.new("RGBA", im.size, bg + (255,))
    canvas.alpha_composite(im)
    canvas.convert("RGB").save(path)
    print(f"  [出图] {os.path.basename(path)}  {canvas.width}x{canvas.height}")


dlg = ui_settings.SettingsDialog()
dlg.show()
dlg._show("演员刮削")
app.processEvents()

# ★ 真机 app.log 里的原文（16:39 那一轮，v1.40.4 判因）
REAL_LINES = [
    "[测试] www.minnano-av.com：不可用 — 站点按客户端 TLS 指纹拦截（HTTP 403）："
    "**请在「工具 → 演员刮削 → Cloudflare 验证…」里用系统浏览器过一次校验**"
    "（浏览器能打开说明出口 IP 没被拒，缺的只是通行 cookie） （333 ms）",
    "[测试] IMDB：不可用 — 命中反爬挑战页（HTTP 202）：站点用的是 JS 挑战，"
    "**回 HTTP 200/202 也是挑战页**，不等于拿到了正文。IMDB 用的是 **AWS WAF**："
    "放行凭据是 aws-waf-token，必须由浏览器执行 challenge.js 才能生成 —— "
    "本软件的无头请求拿不到它，**取 cookie 也拿不到**。可行出路：① 用「站点验证」里的"
    "内置浏览器过一次人机校验；② 或直接改用 minnano 作为该演员的数据源。（1439 ms）",
    "[诊断] 失败层：HTTP 正文（反爬挑战页）　★ 决定性判据：TCP + TLS **都通**，"
    "但拿回来的是**反爬挑战页**（正文 1997 字节，HTTP 202，只有挑战脚本、没有正文）。"
    "**这不是 cookie 能解的** —— 挑战页要靠浏览器**执行 JS** 换取放行凭据"
    "（Cloudflare 的 cf_clearance / AWS WAF 的 aws-waf-token），本软件的无头请求永远拿不到。",
    "[诊断] 正文 1997 字节，HTTP 202 —— 挑战页靠浏览器执行 JS 放行，取 cookie 无效；出路见上一条。",
    "[诊断] ③ 正文识别为反爬挑战页（HTTP 200/202 也会是挑战页，别被状态码骗了）",
]

for ln in REAL_LINES:
    dlg._log(ln)
app.processEvents()

g3 = None
pg = dlg._pg_scraper
from PySide6.QtWidgets import QScrollArea
while isinstance(pg, QScrollArea):
    pg = pg.widget()
lay = pg.layout()
for i in range(lay.count()):
    w = lay.itemAt(i).widget()
    if isinstance(w, QGroupBox) and w.title() == "执行":
        g3 = w
if g3 is not None:
    save_widget(g3, os.path.join(OUT, "75_diag_text_v1404.png"))
else:
    print("[警告] 未找到执行组框")

dlg.close()
