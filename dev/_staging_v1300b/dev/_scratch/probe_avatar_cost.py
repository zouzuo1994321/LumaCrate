# -*- coding: utf-8 -*-
"""确认：建卡开销的大头是不是头像读盘。"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT,"src"))
INDEX = os.path.join(ROOT,"index_data"); TMP = os.path.join(INDEX,"_probe_tmp6")
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
rows = db.query_people(role_type="Actor", limit=120, offset=1200, sort="letter", asc=True)
paths = [ (r.get("thumb") or r.get("photo_path") or "").strip() for r in rows ]
print("120 行里有头像路径的：%d" % sum(1 for p in paths if p))
t=time.time(); n=0
for p in paths[:60]:
    if p: mw._cached_avatar(p, mw._ACTOR_AVATAR); n+=1
dt=time.time()-t
print("首次（冷）头像 %d 张：%.3fs -> %.1f ms/张" % (n, dt, dt*1000/max(1,n)))
t=time.time()
for p in paths[:60]:
    if p: mw._cached_avatar(p, mw._ACTOR_AVATAR)
dt2=time.time()-t
print("再来一次（命中缓存）：%.4fs" % dt2)
# 纯读盘
t=time.time()
for p in paths[60:120]:
    if p:
        try: open(p,'rb').read()
        except Exception: pass
print("纯 read() 60 个文件：%.3fs" % (time.time()-t))
# 建卡（头像已缓存 vs 未缓存）
win = mw.MainWindow(); win.resize(1920,1080); win.show()
for _ in range(20): app.processEvents(); time.sleep(0.01)
cfg.get_settings().set_actor_prefs("letter", True, {})
page = win._view_actors(); win.stack.addWidget(page); win.stack.setCurrentWidget(page)
g = page.findChild(mw.LazyGrid)
for _ in range(40):
    for _ in range(4): app.processEvents(); time.sleep(0.01)
    if g is not None and g._loaded: break
rows2 = db.query_people(role_type="Actor", limit=60, offset=3000, sort="letter", asc=True)
t=time.time()
for r in rows2: g._make(r)
print("建 60 张新卡（头像未缓存）：%.3fs -> %.1f ms/张" % (time.time()-t, (time.time()-t)*1000/60))
t=time.time()
for r in rows2: g._make(r)
print("同 60 张再来（头像已缓存）：%.3fs" % (time.time()-t))
