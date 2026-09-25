# -*- coding: utf-8 -*-
"""跳到 Z 的总耗时 vs 批量大小（批数越少，批次间固定开销越少，但单批卡顿越长）。"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT,"src"))
INDEX = os.path.join(ROOT,"index_data"); TMP = os.path.join(INDEX,"_probe_tmpC")
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
for B in (240, 600, 1200, 2400):
    # 每轮重建一页（清掉已建卡，保证起点一致）
    old = win.stack.currentWidget()
    page = win._view_actors(); win.stack.addWidget(page); win.stack.setCurrentWidget(page)
    if old is not None and old is not page:
        win.stack.removeWidget(old); old.deleteLater()
    g=None
    for _ in range(40):
        pump(4); g=page.findChild(mw.LazyGrid)
        if g is not None and g._loaded: break
    import letter_index
    bar = page.findChild(letter_index.LetterIndexBar)
    g.batch = B
    t0=time.time(); tgt=bar.position_of("Z"); bar.click_letter("Z")
    while g._loaded <= tgt and time.time()-t0 < 200: pump(2)
    print("batch=%-5d -> 跳到 Z 耗时 %5.1fs   loaded=%s" % (B, time.time()-t0, g._loaded))
