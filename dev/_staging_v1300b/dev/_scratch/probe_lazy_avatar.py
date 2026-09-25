# -*- coding: utf-8 -*-
"""验证懒加载头像：① 跳转大幅提速 ② 看得见的卡头像真的画出来了（不是永远空白）。"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT,"src"))
INDEX = os.path.join(ROOT,"index_data"); TMP = os.path.join(INDEX,"_probe_tmp7")
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"]="offscreen"; os.environ["LMC_NO_SPLASH"]="1"
os.environ["LMC_NO_BACKDROP"]="1"; os.environ["LMC_NO_SYSMON"]="1"
import applog
applog.log_dir=lambda: os.path.join(TMP,"logs"); os.makedirs(applog.log_dir(), exist_ok=True)
applog.log_path=lambda: os.path.join(TMP,"logs","app.log")
import config as cfg, database as db
db.db_path=lambda: os.path.join(INDEX,"media_center.db")
cfg.config_path=lambda: os.path.join(TMP,"settings.json"); cfg._SETTINGS=None
from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QScrollArea
app = QApplication.instance() or QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc","C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f): QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei",10))
import main_window as mw; mw.load_style(app)
def pump(n=1,dt=0.005):
    for _ in range(n): app.processEvents(); time.sleep(dt)
win = mw.MainWindow(); win.resize(1920,1080); win.show(); pump(30)
cfg.get_settings().set_actor_prefs("letter", True, {})
page = win._view_actors(); win.stack.addWidget(page); win.stack.setCurrentWidget(page)
for _ in range(40):
    pump(4); g=page.findChild(mw.LazyGrid)
    if g is not None and g._loaded: break
import letter_index
bar = page.findChild(letter_index.LetterIndexBar); sc = page.findChild(QScrollArea)
print("首屏 loaded=%s total=%s" % (g._loaded, g._total))
# 可见卡片：绘制后头像应已加载
vis = [g.card_at(i) for i in range(0, 12)]
vis = [c for c in vis if c is not None]
pump(10)
ok = sum(1 for c in vis if not c._avatar_pending)
print("首屏可见卡 %d 张，已加载头像 %d 张" % (len(vis), ok))
# 未绘制的远处卡应保持 pending（不读盘）
far = g.card_at(0)
t0=time.time(); tgt=bar.position_of("Z"); bar.click_letter("Z")
while g._loaded <= tgt and time.time()-t0 < 200: pump(3)
print("跳到 Z(idx=%s)：耗时 %.1fs  loaded=%s" % (tgt, time.time()-t0, g._loaded))
card = g.card_at(tgt)
if card is not None and sc is not None:
    sc.ensureWidgetVisible(card, 80, 140)
pump(30)
print("目标卡 pending=%s（应为 False=已读）" % (card._avatar_pending if card else None))
if card is not None:
    pm = card._avatar.pixmap()
    print("目标卡头像 pixmap: %sx%s  isNull=%s" % (pm.width(), pm.height(), pm.isNull()))
    # 亮度断言：头像区不能还是占位纯色
    img = card.grab().toImage()
    w,h = img.width(), img.height()
    vals=[]
    for y in range(10, 70, 3):
        for x in range(10, 70, 3):
            c=img.pixelColor(x,y); vals.append((c.red()+c.green()+c.blue())/3)
    uniq = len(set(int(v)//8 for v in vals))
    print("头像区平均亮度 %.1f  色阶数 %d（占位图通常 <6）" % (sum(vals)/len(vals), uniq))
