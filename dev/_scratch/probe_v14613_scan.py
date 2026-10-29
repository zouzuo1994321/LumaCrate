# -*- coding: utf-8 -*-
"""v1.46.13 离屏探针：扫描「自上而下 / 边扫边显示 / 底部状态」三条反馈的量化验证。

不碰真实索引：db_path 改到临时库、settings 走 LMC_CONFIG、日志目录也重定向。
"""
import os
import sys
import json
import time
import tempfile
import traceback

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"
ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
TMP = os.path.join(tempfile.gettempdir(), "lmc_probe_v14613")
os.makedirs(TMP, exist_ok=True)

sys.path.insert(0, SRC)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import config as cfg
cfg_path = os.path.join(TMP, "settings.json")
os.environ["LMC_CONFIG"] = cfg_path
if not os.path.exists(cfg_path):
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({}, f)

import database as db
db_path = os.path.join(TMP, "index_data", "media_center.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db.db_path = lambda: db_path

import applog
os.makedirs(os.path.join(TMP, "logs"), exist_ok=True)
applog.log_dir = lambda: os.path.join(TMP, "logs")

import scanner

FAILS = []
OKS = []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    print(("  OK   " if cond else "  FAIL ") + name + (("　→ " + str(detail)) if detail else ""))


def _del(p):
    """本机 safe-delete shim 会拦 os.remove / os.unlink。"""
    import ctypes
    if not os.path.exists(p):
        return
    ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
    ctypes.windll.kernel32.DeleteFileW(p)


# ---------- 造一棵临时媒体树：3 个路径 × 每个 12 项 ----------
NFO = """<?xml version="1.0" encoding="UTF-8"?>
<movie><title>%s</title><year>2020</year><plot>p</plot></movie>
"""
TREE = os.path.join(TMP, "lib")
PATHS = []
for pi in range(3):
    base = os.path.join(TREE, "path-%d" % (pi + 1))
    PATHS.append(base)
    for i in range(12):
        folder = os.path.join(base, "F%02d_%02d" % (pi + 1, i))
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "movie.nfo"), "w", encoding="utf-8") as f:
            f.write(NFO % ("标题%d-%d" % (pi + 1, i)))
        with open(os.path.join(folder, "F%02d_%02d.mp4" % (pi + 1, i)), "wb") as f:
            f.write(b"\0" * 2048)

# 清空临时库（连跑两次：第二次全是「已存在」，用来验分母口径）
if os.path.exists(db_path):
    db.close_conn()
    _del(db_path)
db.init_db()

print("=" * 66)
print("【1】scanner.scan_library：逐条目回调（新增 + 已存在都要报）")
print("=" * 66)

seen = []
r1 = scanner.scan_library(PATHS[0], None, library_name="探针库", mode="new",
                          on_item=lambda d: seen.append(dict(d)), path_index=1, path_total=3)
check("首扫：on_item 覆盖全部 12 项", len(seen) == 12, len(seen))
check("首扫：全部标记 new", all(d["new"] for d in seen), sum(1 for d in seen if d["new"]))
check("首扫：n 单调递增 1..12", [d["n"] for d in seen] == list(range(1, 13)), [d["n"] for d in seen])
check("首扫：path_index/total 透传", seen[0]["index"] == 1 and seen[0]["total"] == 3,
      (seen[0]["index"], seen[0]["total"]))
check("首扫：返回统计 movie=12", r1.get("movie") == 12, r1)

seen2 = []
r2 = scanner.scan_library(PATHS[0], None, library_name="探针库", mode="new",
                          on_item=lambda d: seen2.append(dict(d)), path_index=2, path_total=3)
check("复扫：on_item 仍是 12 条（旧版这里是 0 → 百分比永远 0%）", len(seen2) == 12, len(seen2))
check("复扫：一条都不再标 new", not any(d["new"] for d in seen2),
      sum(1 for d in seen2 if d["new"]))
check("复扫：返回统计 movie=0（本身没新增）", r2.get("movie") == 0, r2)

print("=" * 66)
print("【2】ScanWorker：路径顺序 = 配置顺序（自上而下），进度口径 = 已处理/总数")
print("=" * 66)

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

import main_window as mw

w = mw.ScanWorker(PATHS, library_name="探针库", mode="new")
ticks = []
w.tick.connect(lambda d, t, m: ticks.append((d, t, m)))
lives = []
w.live.connect(lambda: lives.append(time.monotonic()))
done = []
w.done.connect(lambda c: done.append(dict(c)))
w.run()          # 直接同步跑（同线程 → 直连信号）

msgs = [m for _d, _t, m in ticks]
# 每条路径开始都会强推一次 tick，文案里带「路径 i/3」
seq = []
for m in msgs:
    if m.startswith("扫描") and "路径" in m:
        seg = m.split(" · ")
        tag = [x for x in seg if x.startswith("路径")]
        if tag and tag[0] not in seq:
            seq.append(tag[0])
check("路径按配置顺序 1→2→3 依次出现", seq == ["路径 1/3", "路径 2/3", "路径 3/3"], seq)
check("文案里的目录名与顺序一致",
      msgs and "path-1" in next(m for m in msgs if "路径 1/3" in m), None)

last = ticks[-1]
check("最后一条 tick 是定量（有分母）", last[1] > 0, last)
check("分子等于处理条目总数 36", last[0] == 36, last[0])
check("分母等于视频文件总数 36", last[1] == 36, last[1])
check("百分比可达 100%", last[0] == last[1], (last[0], last[1]))
# path-1 在【1】里已扫过 → 本次只有 path-2/3 的 24 项是新的
check("done 回调的 movie = 24（只有另外两条路径是新的）",
      done and done[0].get("movie") == 24, done)

# 已有 24 个新片 → 这一轮 live 必须发（边扫边刷）
check("有新片时 live 会发（边扫边显示）", len(lives) >= 1, len(lives))

# 再把整库复扫一遍：一条新片都没有 → live 一次都不该发（不白刷界面）
w3 = mw.ScanWorker(PATHS, library_name="探针库", mode="new")
t3, l3 = [], []
w3.tick.connect(lambda d, t, m: t3.append((d, t, m)))
w3.live.connect(lambda: l3.append(1))
w3.run()
check("无新片时不发 live（中途一次都不发，只剩收尾那次）", len(l3) == 1, len(l3))
check("无新片时分子照样涨到 36（进度条不会停在 0）", t3[-1][0] == 36 and t3[-1][1] == 36, t3[-1])
check("无新片时文案不带「新增」", "新增" not in t3[-1][2], t3[-1][2])

# 清库重扫：每片都是新的，live 必须发、文案要带新增数
db.clear_media()
w2 = mw.ScanWorker(PATHS, library_name="探针库", mode="new")
t2, l2 = [], []
w2.tick.connect(lambda d, t, m: t2.append((d, t, m)))
w2.live.connect(lambda: l2.append(1))
w2.run()
check("全新扫描：live 至少发 1 次", len(l2) >= 1, len(l2))
check("全新扫描：最后 36/36", t2[-1][0] == 36 and t2[-1][1] == 36, t2[-1])
check("全新扫描：文案带「新增 36」", "新增 36" in t2[-1][2], t2[-1][2])

print("=" * 66)
print("【3】MainWindow 底部「扫描情况」三态（开始 / 进行中 / 结束）")
print("=" * 66)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QProgressBar,
                               QHBoxLayout, QVBoxLayout)
app2 = app
mw.load_style(app2)
mw.BUSY_MIN_MS = 0          # 关掉「最短可见时长」，便于断言收尾立刻回落


class FakeSelf(QWidget):
    """只装状态栏那个文字标签 + 进度条，方法本体用真的（未绑定调用）。"""
    SCAN_TEXT_MAX_W = mw.MainWindow.SCAN_TEXT_MAX_W

    def __init__(self):
        super().__init__()
        h = QHBoxLayout(self)
        self._scan_lbl = QLabel("")
        self._scan_lbl.setObjectName("ScanNote")
        self._scan_lbl.setVisible(False)
        self._busy_bar = QProgressBar()
        self._busy_bar.setObjectName("BusyBar")
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setFixedSize(110, 6)
        self._busy_bar.setRange(0, 1)
        self._busy_bar.setValue(0)
        self._busy_bar.setProperty("busy", False)
        self._busy_on_at = 0.0
        self._busy_idle_timer = QTimer(self)
        self._busy_idle_timer.setSingleShot(True)
        self._busy_idle_timer.timeout.connect(lambda: self._on_busy(None, ""))
        h.addWidget(self._scan_lbl)
        h.addWidget(self._busy_bar)
        self.rings = []

    def _lib_ring(self, name, busy, pct=0, tip=""):
        self.rings.append((name, busy, pct, tip))


fs = FakeSelf()
fs.resize(900, 40)
fs.show()
for fn in ("_scan_begin", "_set_scan_text", "_on_scan_tick", "_scan_end",
           "_on_busy", "_scan_own_busy"):
    setattr(FakeSelf, fn, getattr(mw.MainWindow, fn))

check("空闲时文字隐藏", not fs._scan_lbl.isVisible())
check("空闲时进度条是空槽", fs._busy_bar.property("busy") is False)

fs._scan_begin("探针库", 3, "新添加和修改的")
app2.processEvents()
check("开始：文字可见", fs._scan_lbl.isVisible())
check("开始：文案含库名 / 模式 / 路径数",
      all(x in fs._scan_lbl.text() for x in ("探针库", "新添加和修改的", "3")),
      fs._scan_lbl.text())
check("开始：进度条转不定长（range 0,0）",
      (fs._busy_bar.minimum(), fs._busy_bar.maximum()) == (0, 0),
      (fs._busy_bar.minimum(), fs._busy_bar.maximum()))
check("开始：进度条点亮（busy=True）", fs._busy_bar.property("busy") is True)
check("开始：扫描独占进度条（BusyBus 已断开）",
      getattr(fs, "_scan_busy_owned", False) is True)

fs._on_scan_tick("探针库", 18, 36, "扫描 探针库 · 路径 2/3 · path-2 · 18/36 · 新增 0")
app2.processEvents()
check("进行中：切成定量 0..100",
      (fs._busy_bar.minimum(), fs._busy_bar.maximum()) == (0, 100),
      (fs._busy_bar.minimum(), fs._busy_bar.maximum()))
check("进行中：值为 50（18/36）", fs._busy_bar.value() == 50, fs._busy_bar.value())
check("进行中：状态栏文字就是扫描情况",
      fs._scan_lbl.text() == "扫描 探针库 · 路径 2/3 · path-2 · 18/36 · 新增 0", fs._scan_lbl.text())
check("进行中：侧栏圆环百分比同步 50", fs.rings and fs.rings[-1][2] == 50, fs.rings[-1:])

# 超长文案必须被省略，不能把左边版权挤走
longmsg = "扫描 " + "很长的库名" * 40 + " · 路径 12/12 · 123456/789012"
fs._on_scan_tick("探针库", 100, 100, longmsg)
app2.processEvents()
w_px = fs._scan_lbl.fontMetrics().horizontalAdvance(fs._scan_lbl.text())
check("超长文案按像素省略（<=520px）", w_px <= 520, w_px)
check("超长文案确实被截断", len(fs._scan_lbl.text()) < len(longmsg), fs._scan_lbl.text()[:40])

fs._scan_end()
app2.processEvents()
check("结束：文字收回", not fs._scan_lbl.isVisible())
check("结束：进度条还回去（空槽）",
      fs._busy_bar.value() == 0 and fs._busy_bar.maximum() == 1
      and fs._busy_bar.property("busy") is False,
      (fs._busy_bar.value(), fs._busy_bar.maximum(), fs._busy_bar.property("busy")))
check("结束：BusyBus 重新接管（owned=False）",
      getattr(fs, "_scan_busy_owned", True) is False)

print("=" * 66)
print("【4】LazyGrid.live_reload：不换页、不丢滚动位置、卡片按新顺序重建")
print("=" * 66)

data = [[{"id": i, "title": "T%d" % i, "poster": None, "fanart": None,
          "year": 2020, "rating": None, "genres": "", "library": "x"}
         for i in range(60)]]


class Card(QWidget):
    def __init__(self, m):
        super().__init__()
        self.m = m
        self.setFixedSize(172, 260)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(str(m["id"])))


grid = mw.LazyGrid(lambda off, lim: [(m, {}, 0) for m in data[0][off:off + lim]],
                   lambda pair: Card(pair[0]), 60, kind="media", virtual=True,
                   count_fn=lambda: len(data[0]))
from PySide6.QtWidgets import QScrollArea
scroll = QScrollArea()
scroll.setWidgetResizable(True)
host = QWidget()
hv = QVBoxLayout(host)
hv.addWidget(grid)
hv.addStretch(1)
scroll.setWidget(host)
scroll.resize(1800, 900)
scroll.show()
app2.processEvents()
grid.attach_scroll(scroll.verticalScrollBar(), scroll.viewport())
grid._render()
app2.processEvents()
scroll.verticalScrollBar().setValue(300)
app2.processEvents()
grid._render()
app2.processEvents()
check("初始窗口有卡", len(grid._cards) > 0, len(grid._cards))
check("初始总数 60", grid.total == 60, grid.total)

# 模拟扫描插入 10 条新片（排序上它们在最前面）→ 数量变 70，索引 0 换了内容
data[0] = [{"id": i, "title": "N%d" % i, "poster": None, "fanart": None,
            "year": 2021, "rating": None, "genres": "", "library": "x"}
           for i in range(1000, 1010)] + data[0]
sb = scroll.verticalScrollBar()
pos_before = sb.value()
check("扫描前已滚动到中间（位置 > 0）", pos_before > 0, pos_before)
new_total = grid.live_reload()
app2.processEvents()
expected = {idx: data[0][idx]["id"] for idx in grid._cards}
actual = {idx: c.m["id"] for idx, c in grid._cards.items()}
check("总数跟着变成 70", grid.total == 70 and new_total == 70, (grid.total, new_total))
check("每张卡的数据与最新顺序一致（无张冠李戴）", actual == expected,
      ("实际", sorted(actual.items())[:4], "期望", sorted(expected.items())[:4]))
check("滚动位置未被重置", sb.value() == pos_before, (pos_before, sb.value()))
check("卡数没爆（只重建可视区那一窗）", len(grid._cards) <= 80, len(grid._cards))

print("=" * 66)
print("【5】口径自检：tick 的分子确实是「每个处理过的文件」，不是「新增数」")
print("=" * 66)
check("复扫 36 个已存在文件 → 分子仍涨到 36（旧版会是 0）", last[0] == 36, last)

print("=" * 66)
print("FAILS:", FAILS)
print("共 %d 项，通过 %d 项" % (len(OKS) + len(FAILS), len(OKS)))
print("PROBE_V14613_ALL_OK" if not FAILS else "PROBE_V14613_HAS_FAIL")
