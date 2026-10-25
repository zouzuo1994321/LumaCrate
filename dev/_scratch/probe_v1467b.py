# -*- coding: utf-8 -*-
"""v1.46.7 全页面自检：每个含 LazyGrid 的页面都必须挂上滚动条与视口，且尾部可达。

判据（任一不满足即「滚到底就空白」）：
  · `grid._scrollbar is not None`  —— 虚拟化靠它拿 value
  · `grid._viewport is not None`   —— 虚拟化靠它拿高度
  · body 高度 ≥ 末行卡片底部       —— 否则滚动条 max 到不了尾
  · 滚到 max 后末索引 ≈ total-1
"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1467b"
os.makedirs(TMP, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)

import config as cfg
import applog

cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP

import main_window as mw
import database as db

mw.load_style(app)
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()

FAIL = []


def settle(n=30):
    for _ in range(n):
        app.processEvents()


def check(tag, page):
    grids = page.findChildren(mw.LazyGrid)
    if not grids:
        print("  %-24s 无 LazyGrid（跳过）" % tag, flush=True)
        return
    for gi, g in enumerate(grids):
        sub = tag if len(grids) == 1 else "%s#%d" % (tag, gi)
        sb, vp = g._scrollbar, g._viewport
        ok_sb = sb is not None
        if not g._virtual:
            # 非虚拟（virtual=False，如合集页的 batch=48 增量建卡）：
            # 没有 viewport / _cards 概念，只要求滚动条挂上，且已建出第一批卡片。
            built = len(getattr(g, "_built", []) or [])
            try:
                built = max(built, g._grid.count())     # 非虚拟模式卡片挂在 QGridLayout 里
            except Exception:
                pass
            ok = ok_sb and built > 0
            if not ok:
                FAIL.append(sub)
            print("  %-24s total=%-6d [增量] sb=%-8s 已建=%d  %s"
                  % (sub, g._total, "OK" if ok_sb else "★NONE", built,
                     "PASS" if ok else "FAIL"), flush=True)
            continue
        ok_vp = vp is not None
        tail_ok, last, mx = True, -1, -1
        if ok_sb:
            mx = sb.maximum()
            sb.setValue(mx)
            settle(16)
            idx = sorted(g._cards)
            last = idx[-1] if idx else -1
            tail_ok = last >= g._total - 1 - max(1, g._cols_now)
        body_ok = True
        if g._cards:
            bottom = max(w.geometry().bottom() for w in g._cards.values())
            body_ok = g._body.height() >= bottom
        ok = ok_sb and ok_vp and tail_ok and body_ok
        if not ok:
            FAIL.append(sub)
        print("  %-24s total=%-6d cols=%d sb=%-8s vp=%-4s body=%d 末行底=%s 末索引=%s/%d  %s"
              % (sub, g._total, g._cols_now,
                 "OK" if ok_sb else "★NONE", "OK" if ok_vp else "★NONE",
                 g._body.height(), "OK" if body_ok else "★矮",
                 last, g._total - 1, "PASS" if ok else "FAIL"), flush=True)


def run(tag, fn):
    print("\n[%s]" % tag, flush=True)
    try:
        page = fn()
    except Exception as e:
        print("  建页失败：%s: %s" % (type(e).__name__, e), flush=True)
        FAIL.append(tag + "(建页)")
        return
    win.stack.addWidget(page)
    win.stack.setCurrentWidget(page)
    settle(40)
    check(tag, page)
    page.deleteLater()
    settle(4)


conn = db.get_conn()
pid_actor = conn.execute(
    "SELECT p.id FROM people p JOIN media_people mp ON mp.person_id=p.id "
    "WHERE p.role_type='Actor' GROUP BY p.id ORDER BY COUNT(mp.media_id) DESC LIMIT 1"
).fetchone()[0]
pid_director = conn.execute(
    "SELECT p.id FROM people p JOIN media_people mp ON mp.person_id=p.id "
    "WHERE p.role_type='Director' GROUP BY p.id ORDER BY COUNT(mp.media_id) DESC LIMIT 1"
).fetchone()[0]

run("最近播放", lambda: win._view_recent())
run("我的收藏", lambda: win._view_favorites())
run("媒体墙(全部)", lambda: win._wall_page(None))
run("合集", lambda: win._view_collections())
run("演员库", lambda: win._view_actors())
run("导演库", lambda: win._view_directors())
run("演员全部作品", lambda: win._view_actor_detail(pid_actor))
run("导演全部作品", lambda: win._view_actor_detail(pid_director))

print("\n失败页：%s" % (FAIL or "无"), flush=True)
print("PROBE_V1467B_DONE", flush=True)
