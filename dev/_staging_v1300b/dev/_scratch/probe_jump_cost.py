# -*- coding: utf-8 -*-
"""量：从首屏跳到最远字母（Z / #）要多久，逐批计时。"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT,"src"))
INDEX = os.path.join(ROOT,"index_data"); TMP = os.path.join(INDEX,"_probe_tmp4")
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"]="offscreen"; os.environ["LMC_NO_SPLASH"]="1"
os.environ["LMC_NO_BACKDROP"]="1"; os.environ["LMC_NO_SYSMON"]="1"
import applog
applog.log_dir=lambda: os.path.join(TMP,"logs"); os.makedirs(applog.log_dir(), exist_ok=True)
applog.log_path=lambda: os.path.join(TMP,"logs","app.log")
import config as cfg, database as db
db.db_path=lambda: os.path.join(INDEX,"media_center.db")
cfg.config_path=lambda: os.path.join(TMP,"settings.json"); cfg._SETTINGS=None
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc","C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f): QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei",10))
import main_window as mw; mw.load_style(app)
def pump(n=1,dt=0.005):
    for _ in range(n): app.processEvents(); time.sleep(dt)
win = mw.MainWindow(); win.resize(1920,1080); win.show(); pump(20)
cfg.get_settings().set_actor_prefs("letter", True, {})
page = win._view_actors(); win.stack.addWidget(page); win.stack.setCurrentWidget(page)
for _ in range(40):
    pump(4); g=page.findChild(mw.LazyGrid)
    if g is not None and g._loaded: break
import letter_index
bar = page.findChild(letter_index.LetterIndexBar)
print("首屏 loaded=%s  total=%s" % (g._loaded, g._total))
print("索引：", {k:v for k,v in sorted(bar.index().items()) if k in ("A","C","M","S","Z","#")})
# 单卡造价
t=time.time()
rows = db.query_people(role_type="Actor", limit=60, offset=0, sort="letter", asc=True)
tq=time.time()-t
t=time.time()
for r in rows: g._make(r)
print("取 60 行 %.3fs；建 60 张卡 %.3fs -> %.1f ms/张" % (tq, time.time()-t, (time.time()-t)*1000/60))
for L in ("C","Z","#"):
    tgt = bar.position_of(L)
    if tgt is None: print("%s 无映射" % L); continue
    t0=time.time(); last=g._loaded; marks=[]
    bar.click_letter(L)
    while g._loaded <= tgt and time.time()-t0 < 300:
        pump(3)
        if g._loaded != last:
            last=g._loaded; marks.append((round(time.time()-t0,1), g._loaded))
    print("\n跳到 %s (idx=%d)：耗时 %.1fs  最终 loaded=%s" % (L, tgt, time.time()-t0, g._loaded))
    print("   进度采样(秒,已建):", marks[:6], "...", marks[-2:] if len(marks)>6 else "")
    if time.time()-t0 >= 300: print("   !! 超过 300s 未完成"); break
