# -*- coding: utf-8 -*-
"""给 _jump_step 分段计时：取数 / 建卡 / _update_head / 事件循环让位，各占多少。"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT,"src"))
INDEX = os.path.join(ROOT,"index_data"); TMP = os.path.join(INDEX,"_probe_tmp9")
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
bar = page.findChild(letter_index.LetterIndexBar)
STAT = {"fetch":0.0,"make":0.0,"head":0.0,"batches":0,"cards":0}
orig_fetch = g._fetch
def timed_fetch(o, l):
    t=time.time(); r = orig_fetch(o,l); STAT["fetch"]+=time.time()-t; return r
g._fetch = timed_fetch
orig_head = g._update_head
def timed_head():
    t=time.time(); orig_head(); STAT["head"]+=time.time()-t
g._update_head = timed_head
orig_jump = g._jump_step
def timed_jump():
    before=g._loaded; t=time.time()
    orig_jump()
    STAT["make"] += time.time()-t - 0.0
    STAT["batches"] += 1; STAT["cards"] += max(0, g._loaded-before)
g._jump_step = timed_jump
t0=time.time(); tgt=bar.position_of("Z"); bar.click_letter("Z")
while g._loaded <= tgt and time.time()-t0 < 200: pump(2)
total=time.time()-t0
print("跳到 Z：总 %.1fs  批数 %d  建卡 %d 张" % (total, STAT["batches"], STAT["cards"]))
print("  取数累计 %.1fs | _jump_step 内部累计 %.1fs（含取数+建卡+update_head）| _update_head 累计 %.1fs"
      % (STAT["fetch"], STAT["make"], STAT["head"]))
print("  事件循环让位/其它 %.1fs" % (total - STAT["make"]))
