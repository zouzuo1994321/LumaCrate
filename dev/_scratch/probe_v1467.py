# -*- coding: utf-8 -*-
"""v1.46.7 探针：「演员/导演 → 全部作品」页的网格有没有挂上滚动条、尾部能不能滚到。

假设（v1.46.6 之前遗留）：`_page()` 只认 `body_widget.lazy_grid` 或 body 本身就是
带 `attach_scroll` 的网格；`_view_actor_detail` 把 `_grid(works)` 塞进普通 QWidget
容器 → 挂不上 → 虚拟模式拿不到 scrollbar/viewport → y 恒 0、vh 用 700 兜底 →
永远只渲染前 5~6 行（8 列 → 40~48 张），滚下去一片空白。
"""
import os
import sys

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v1467"
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


def settle(n=25):
    for _ in range(n):
        app.processEvents()


def top_people(role, limit=3):
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT p.id, p.name, COUNT(mp.media_id) c FROM people p "
        "JOIN media_people mp ON mp.person_id=p.id "
        "WHERE p.role_type=? GROUP BY p.id ORDER BY c DESC LIMIT ?",
        (role, limit)).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def pick_kind(kind, limit=3):
    """kind='actor'/'director' → role_type 实际存的是 'Actor'/'Director'。"""
    rt = "Actor" if kind == "actor" else "Director"
    return top_people(rt, limit)


def inspect(tag, page):
    grids = page.findChildren(mw.LazyGrid)
    print("[%s] LazyGrid 数量=%d" % (tag, len(grids)), flush=True)
    if not grids:
        return None
    g = grids[0]
    sb = g._scrollbar
    print("    virtual=%s total=%d batch=%d  cols_now=%d"
          % (g._virtual, g._total, g.batch, g._cols_now), flush=True)
    print("    _scrollbar=%s  _viewport=%s"
          % ("None ★未挂" if sb is None else "OK max=%d" % sb.maximum(),
             "None" if g._viewport is None else "OK"), flush=True)
    print("    body 高=%d  卡片数=%d  索引=[%s..%s]"
          % (g._body.height(), len(g._cards),
             min(g._cards) if g._cards else "-", max(g._cards) if g._cards else "-"),
          flush=True)
    if sb is None:
        print("    ⇒ 页面滚动条：找不到（无法模拟滚到底）", flush=True)
        return g
    sb.setValue(sb.maximum())
    settle(20)
    idx = sorted(g._cards)
    print("    滚到底 value=%d/%d 后：卡片数=%d 索引=[%s..%s]  应到 %d  %s"
          % (sb.value(), sb.maximum(), len(g._cards),
             idx[0] if idx else "-", idx[-1] if idx else "-", g._total - 1,
             "OK" if idx and idx[-1] >= g._total - 1 - g._cols_now else "★截断"),
          flush=True)
    return g


# ---------- 演员「全部作品」 ----------
for role, label in (("actor", "演员"), ("director", "导演")):
    tops = pick_kind(role, 2)
    print("\n== %s 作品数 Top：%s" % (label, tops), flush=True)
    for pid, name, cnt in tops[:1]:
        page = win._view_actor_detail(pid)
        win.stack.addWidget(page)
        win.stack.setCurrentWidget(page)
        settle(40)
        print("\n-- %s「%s」%d 部 --" % (label, name, cnt), flush=True)
        inspect("%s全部作品" % label, page)
        page.deleteLater()

# ---------- 对照：媒体墙（应正常挂上） ----------
print("\n== 对照组：媒体墙 ==", flush=True)
wall = win._wall_page(None)
win.stack.addWidget(wall)
win.stack.setCurrentWidget(wall)
settle(35)
inspect("媒体墙", wall)

print("\nPROBE_V1467_DONE", flush=True)
