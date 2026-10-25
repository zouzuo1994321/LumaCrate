# -*- coding: utf-8 -*-
"""v1.26.0 离屏冒烟回归 —— 四条反馈逐条自证 + 性能索引回归

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1260.py', run_name='__main__')"

**安全约定**：`db.db_path` 指向临时目录，`cfg.config_path` 指向临时 settings.json，
日志重定向到临时目录 —— 全程不碰真实索引 / 真实配置 / 真实媒体目录。

覆盖：
  A 版本号            B 反馈 1（开关轨道跟随高亮色，含**像素级**取证）
  C 反馈 2（底部开源声明）  D 反馈 3（副标题防裁字，含**像素级**取证）
  E 性能索引回归      F 基准测试产物      G 高亮色令牌回归
"""
import io
import os
import re
import sys
import sqlite3
import shutil
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1260")
INDEX = os.path.join(TMP, "index_data")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(INDEX, "plan_test.db"),
           os.path.join(TMP, "settings.json")):
    try:
        os.remove(_f)
    except OSError:
        pass
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

REAL_DB = db.db_path()                       # 先记下真实路径（后面会把 db_path 改掉）
db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import ui_settings
import main_window as mw

db.init_db()          # 临时库先建表（MainWindow 一建起来就会查 library_counts）

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print(f"[{'PASS' if cond else 'FAIL'}] {tag}  {detail}")


def section(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def pump(app, n=10):
    import time as _t
    for _ in range(n):
        app.processEvents()
        _t.sleep(0.01)


def src(rel):
    with io.open(os.path.join(SRC, rel), encoding="utf-8", newline="") as f:
        return f.read()


# ============================================================ A. 版本号
section("A. 版本号（v1.26.0 / Build 2609210036）")
import version as ver
check("A1 外部版本 v1.26.0", ver.VERSION == "v1.26.0", ver.VERSION)
check("A2 内部构建号 2609210036", ver.BUILD == "2609210036", ver.BUILD)
check("A3 完整标识", ver.FULL_VERSION == "v1.26.0 (Build 2609210036)", ver.FULL_VERSION)
check("A4 开源声明文案保持不变",
      ver.LICENSE_NOTE == "本软件为开源软件，没有授权禁止用于商业用途。", ver.LICENSE_NOTE)
check("A5 版权文案保持不变",
      ver.COPYRIGHT == "Copyright  2026 肆月Aperture", ver.COPYRIGHT)

# ============================================================ 准备 Qt
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap

from PySide6.QtWidgets import QApplication, QLabel, QGroupBox

app = QApplication.instance() or QApplication(sys.argv)
import time as _time

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))
mw.load_style(app)
pump(app, 3)

# ============================================================ B. 反馈 1
section("B. 反馈 1：自绘开关（滑动按钮）的轨道要跟着「高亮色」走")
check("B1 ToggleSwitch 有 accent_on() 取色口", hasattr(ui_settings.ToggleSwitch, "accent_on"))
check("B2 paintEvent 用的是现取的轨道色（不再是写死的 _ON）",
      "on = self.accent_on()" in src("ui_settings.py") and
      "zip(self._OFF, on)" in src("ui_settings.py"))
check("B3 模块级不 import main_window（会与 ui_settings 成环）",
      not re.search(r"^import main_window", src("ui_settings.py"), re.M) and
      "sys.modules.get(\"main_window\")" in src("ui_settings.py"))
check("B4 ui_settings 已 import sys", re.search(r"^import sys$", src("ui_settings.py"), re.M) is not None)

_toggle = ui_settings.ToggleSwitch()
try:
    # 12 色逐一遍历：render_style 会刷新 ACCENT_RGB，accent_on() 必须立刻跟上
    bad = []
    for _nm, _h in cfg.ACCENT_COLORS:
        mw.render_style({"mode": "经典暗色", "level": "中", "accent": _h})
        if _toggle.accent_on() != cfg.accent_rgb(_h):
            bad.append(_nm)
    check("B5 12 色下 accent_on() 都等于该色 RGB", not bad, "、".join(bad))
finally:
    _toggle.deleteLater()

# --- 像素级：真的画出来，取轨道上的像素
def track_pixel(checked, x, y=13):
    sw = ui_settings.ToggleSwitch()
    sw.resize(46, 26)
    sw.setChecked(bool(checked))
    sw.set_pos(1.0 if checked else 0.0)
    pm = QPixmap(sw.size())
    pm.fill(QColor("#000000"))          # 先填已知底色（不填会读到未初始化内存）
    sw.render(pm, QPoint(0, 0))
    c = pm.toImage().pixelColor(x, y)
    sw.deleteLater()
    return (c.red(), c.green(), c.blue())


def _near(a, b, tol=26):
    return all(abs(int(x) - int(y)) <= tol for x, y in zip(a, b))


def _diff(a, b):
    return max(abs(int(x) - int(y)) for x, y in zip(a, b))


mw.render_style({"mode": "经典暗色", "level": "中", "accent": "#c0392b"})
_on_zhu = track_pixel(True, 10)
mw.render_style({"mode": "经典暗色", "level": "中", "accent": "#3fa9c9"})
_on_qing = track_pixel(True, 10)
_off = track_pixel(False, 36)

check("B6 开态轨道像素 ≈ 高亮色（朱红）", _near(_on_zhu, (192, 57, 43)), str(_on_zhu))
check("B7 开态轨道像素 ≈ 高亮色（天青 #3fa9c9）", _near(_on_qing, (63, 169, 201)), str(_on_qing))
check("B8 换高亮色后轨道像素**真的变了**（这一条就是反馈 1 的原始症状）",
      _diff(_on_zhu, _on_qing) > 60, "差异 %d" % _diff(_on_zhu, _on_qing))
check("B9 关态轨道仍是原暗底 #4a4038（视觉零回退）",
      _near(_off, (0x4a, 0x40, 0x38), 8), str(_off))
check("B10 圆点仍是 #f3d9a0（iOS 式中性圆点，不跟着高亮色走）",
      _near(track_pixel(True, 33), (0xf3, 0xd9, 0xa0), 12), str(track_pixel(True, 33)))

# 设置页里已经建好的那些开关，是否会被刷新
mw.render_style({"mode": "经典暗色", "level": "中", "accent": "#c0392b"})
win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
win._open_settings()
dlg = win._settings_dlg
dlg._show("个性化设置")
sws = dlg.findChildren(ui_settings.ToggleSwitch)
check("B11 设置页里确实有自绘开关", len(sws) > 5, "%d 个" % len(sws))
check("B12 有 _refresh_toggles()", hasattr(dlg, "_refresh_toggles"))
try:
    dlg._refresh_toggles()
    ok_refresh = True
except Exception as e:                                  # noqa: BLE001
    ok_refresh = False
    print("        ", type(e).__name__, e)
check("B13 _refresh_toggles() 能跑通且覆盖到全部开关", ok_refresh and len(sws) > 5)
dlg._apply_accent("#3fa9c9")
check("B14 点色块后高亮色落盘", cfg.get_settings().accent() == "#3fa9c9",
      cfg.get_settings().accent())
check("B15 换色后 ACCENT_RGB 同步", mw.ACCENT_RGB == cfg.accent_rgb("#3fa9c9"),
      str(mw.ACCENT_RGB))
pump(app, 4)
_sw_after = ui_settings.ToggleSwitch()
check("B16 换色后新开关取到的轨道色 = 天青",
      _near(_sw_after.accent_on(), (63, 169, 201)), str(_sw_after.accent_on()))
_sw_after.deleteLater()

# 单色重绘代价（证明「每帧现取」不是靠全局缓存，且零代价）
import time as _t2
_swb = ui_settings.ToggleSwitch()
_swb.resize(46, 26)
_t0 = _t2.perf_counter()
for _ in range(200):
    _pm = QPixmap(_swb.size())
    _pm.fill(QColor("#000000"))
    _swb.render(_pm, QPoint(0, 0))
_ms = (_t2.perf_counter() - _t0) * 1000
_swb.deleteLater()
check("B17 现取高亮色的绘制开销可忽略（200 帧 < 60ms）", _ms < 60.0, "%.3f ms/帧" % (_ms / 200))

# ============================================================ C. 反馈 2
section("C. 反馈 2：底部状态栏要接上开源声明")
check("C1 源码里状态栏文案含 LICENSE_NOTE",
      "{ver.LICENSE_NOTE}" in src("main_window.py"))
_msg = win.statusBar().currentMessage()
check("C2 状态栏含完整版本标识", ver.FULL_VERSION in _msg, _msg)
check("C3 状态栏含 Copyright", ver.COPYRIGHT in _msg)
check("C4 状态栏含开源声明", ver.LICENSE_NOTE in _msg)
check("C5 开源声明**排在** Copyright 之后（反馈原话「添加在…后面」）",
      _msg.find(ver.COPYRIGHT) < _msg.find(ver.LICENSE_NOTE),
      "Copyright@%d / 声明@%d" % (_msg.find(ver.COPYRIGHT), _msg.find(ver.LICENSE_NOTE)))

# ============================================================ D. 反馈 3
section("D. 反馈 3：侧栏副标题「LocalMediaCenter」不再被裁")
_qss = src("style.qss")
_m = re.search(r"QLabel#Sub\s*\{([^}]*)\}", _qss)
_sub_rule = _m.group(1) if _m else ""
check("D1 style.qss 里 QLabel#Sub 有规则", bool(_sub_rule), _sub_rule.strip())
check("D2 字号已降到 10px（原 11px）", "font-size: 10px" in _sub_rule, _sub_rule.strip())
check("D3 字距 1.5px（再留一点余量）", "letter-spacing: 1.5px" in _sub_rule, _sub_rule.strip())

win.resize(1280, 860)
win.show()
pump(app, 6)
sub = win.findChild(QLabel, "Sub")
check("D4 找得到副标题 QLabel(objectName=Sub)", sub is not None)
if sub is not None:
    txt = sub.text()
    fm = sub.fontMetrics()
    adv = fm.horizontalAdvance(txt)
    check("D5 副标题文本就是 LocalMediaCenter", txt == "LocalMediaCenter", repr(txt))
    check("D6 文本宽度 <= 标签可用宽度（10px 下）", adv <= sub.width(),
          "文字 %dpx / 可用 %dpx / 余 %+d" % (adv, sub.width(), sub.width() - adv))
    # 反证：把字体换回**改动前的组合**（11px + letter-spacing 2px），量出来必然溢出 ——
    # 这正是「末尾 r 被裁掉」的根因（16 字符 × 0.5px 字距 = 8px 的额外宽度）。
    from PySide6.QtGui import QFontMetrics
    f_old = QFont(sub.font())
    f_old.setPixelSize(11)
    f_old.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
    adv_old = QFontMetrics(f_old).horizontalAdvance(txt)
    check("D7 反证：改动前（11px + 2px 字距）确实溢出，就是裁掉 r 的原因",
          adv_old > sub.width(),
          "旧组合要 %dpx / 只有 %dpx（超出 %dpx）"
          % (adv_old, sub.width(), adv_old - sub.width()))
    f_new = QFont(sub.font())
    f_new.setPixelSize(10)
    f_new.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
    adv_new = QFontMetrics(f_new).horizontalAdvance(txt)
    check("D7b 新组合（10px + 1.5px 字距）留有余量",
          adv_new <= sub.width(),
          "新组合 %dpx / 可用 %dpx（余 %+d）" % (adv_new, sub.width(),
                                              sub.width() - adv_new))

    # --- 像素级：把品牌区画出来，看文字右边缘离标签右边界还有没有空隙
    brand = sub.parentWidget()
    pm = QPixmap(brand.size())
    pm.fill(QColor("#000000"))
    brand.render(pm, QPoint(0, 0))
    img = pm.toImage()
    tl = sub.mapTo(brand, QPoint(0, 0))
    right_most = -1
    for y in range(tl.y(), min(tl.y() + sub.height(), img.height())):
        for x in range(min(tl.x() + sub.width() - 1, img.width() - 1), tl.x() - 1, -1):
            c = img.pixelColor(x, y)
            if max(c.red(), c.green(), c.blue()) > 45:
                right_most = max(right_most, x)
                break
    margin = (tl.x() + sub.width() - 1) - right_most
    check("D8 像素级：副标题文字右边留有空白（没有被贴边裁掉）",
          right_most >= 0 and margin >= 2,
          "文字右缘 x=%d / 标签右边界 x=%d / 余 %dpx"
          % (right_most, tl.x() + sub.width() - 1, margin))

# ============================================================ E. 性能索引
section("E. 性能索引回归（本次基准测试带出的修复）")
_db_src = src("database.py")
check("E1 _INDEXES 里有 idx_wall_title（与 ORDER BY 逐列对齐）",
      "idx_wall_title ON media(sort_title COLLATE NOCASE, year DESC, id ASC)" in _db_src)
check("E2 _INDEXES 里有 idx_wall_time",
      "idx_wall_time  ON media(added_time DESC, year DESC, id ASC)" in _db_src)
check("E3 search_media 的 ORDER BY 确实是「字段 + year DESC + id ASC」三键",
      "ORDER BY {expr} {direction}, m.year DESC, m.id ASC" in _db_src)

# 造一个有 3000 行的临时库，看查询计划（小库看不出索引收益，得有点量）
PLANDB = os.path.join(INDEX, "plan_test.db")
db.db_path = lambda: PLANDB
db.close_conn()
db.init_db()
_con = db.get_conn()
_con.executemany(
    "INSERT INTO media(title, sort_title, year, library, kind, added_time, file_path) "
    "VALUES(?,?,?,?,?,?,?)",
    [("t%05d" % i, "t%05d" % i, 2000 + (i % 25), "L", "电影", "2026-01-01", "Z:/x/%d.mp4" % i)
     for i in range(3000)])
_con.commit()
_names = [r[0] for r in _con.execute(
    "SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
check("E4 新库 init_db() 后自动补出了这两个索引",
      "idx_wall_title" in _names and "idx_wall_time" in _names,
      "共 %d 条索引" % len(_names))
_plan_title = " / ".join(str(tuple(r)[3]) for r in _con.execute(
    "EXPLAIN QUERY PLAN SELECT m.id FROM media m "
    "ORDER BY m.sort_title COLLATE NOCASE ASC, m.year DESC, m.id ASC LIMIT 60 OFFSET 2000"
).fetchall())
_plan_time = " / ".join(str(tuple(r)[3]) for r in _con.execute(
    "EXPLAIN QUERY PLAN SELECT m.id FROM media m "
    "ORDER BY m.added_time DESC, m.year DESC, m.id ASC LIMIT 60 OFFSET 0"
).fetchall())
check("E5 名称排序走索引，不再建临时 B-Tree",
      "idx_wall_title" in _plan_title and "TEMP B-TREE" not in _plan_title, _plan_title)
check("E6 时间排序走索引，不再建临时 B-Tree",
      "idx_wall_time" in _plan_time and "TEMP B-TREE" not in _plan_time, _plan_time)
db.close_conn()

# 真实库是否已经补上（只读探一下，不存在就跳过，不算失败）
try:
    _ro = sqlite3.connect("file:%s?mode=ro" % REAL_DB.replace("\\", "/"), uri=True)
    _rn = [r[0] for r in _ro.execute(
        "SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
    _ro.close()
    check("E7 真实索引库已补上这两条索引（已随本次迭代落地）",
          "idx_wall_title" in _rn and "idx_wall_time" in _rn,
          "共 %d 条索引" % len(_rn))
except Exception as e:                                  # noqa: BLE001
    check("E7 真实索引库已补上这两条索引（已随本次迭代落地）", False,
          "%s: %s" % (type(e).__name__, e))

# ============================================================ F. 基准测试产物
section("F. 性能基准测试的产物")
BENCH = os.path.join(ROOT, "dev", "benchmark.py")
MD = os.path.join(ROOT, "性能基线.md")
check("F1 dev/benchmark.py 存在", os.path.isfile(BENCH), BENCH)
check("F2 根目录 性能基线.md 存在", os.path.isfile(MD), MD)
_bench_src = io.open(BENCH, encoding="utf-8").read() if os.path.isfile(BENCH) else ""
check("F3 基准脚本不写真实库（无 db.clear_media / db.init_db 调用）",
      "db.clear_media(" not in _bench_src and "db.init_db(" not in _bench_src)
check("F4 基准脚本把日志重定向到临时目录",
      "applog.log_dir" in _bench_src)
check("F5 基准脚本不改 db.db_path（就是要在真实索引上跑）",
      "db.db_path =" not in _bench_src)
if os.path.isfile(MD):
    _md = io.open(MD, encoding="utf-8").read()
    for _need in ("## 一、测试环境", "## 二、数据规模", "## 三、结果", "## 四、结论"):
        check("F6 %s 已写入《性能基线》" % _need[3:], _need in _md)
    check("F7 《性能基线》标注了被测版本", ver.VERSION in _md and ver.BUILD in _md)
    check("F8 《性能基线》含「修复前/修复后」对照表", "修复前" in _md and "修复后" in _md)
    check("F9 《性能基线》说明了随机排序的已知边界", "已知边界" in _md)
    check("F10 《性能基线》给了复现命令", "dev/benchmark.py" in _md and "runpy" in _md)

# ============================================================ G. 令牌回归
section("G. 高亮色令牌回归（12 色）")
_raw = src("style.qss")
_bad_tok, _bad_hex, _bad_rgb = [], [], []
for _nm, _h in cfg.ACCENT_COLORS:
    _out = mw.render_style({"mode": "经典暗色", "level": "中", "accent": _h})
    if re.findall(r"__[A-Z_]+__", _out):
        _bad_tok.append(_nm)
    if "rgba(%d, %d, %d," % cfg.accent_rgb(_h) not in _out:
        _bad_hex.append(_nm)
    if mw.ACCENT_RGB != cfg.accent_rgb(_h):
        _bad_rgb.append(_nm)
check("G1 12 色渲染后无残留令牌", not _bad_tok, "、".join(_bad_tok))
check("G2 12 色都真的写进了样式表", not _bad_hex, "、".join(_bad_hex))
check("G3 12 色下 ACCENT_RGB 都同步", not _bad_rgb, "、".join(_bad_rgb))
check("G4 没有「xxx: 192, 57, 43;」这类非法声明（裸令牌输出十六进制）",
      not re.findall(r":\s*\d{1,3},\s*\d{1,3},\s*\d{1,3}\s*[;}]",
                     mw.render_style({"mode": "经典暗色", "level": "中"})))
check("G5 滑块 / 进度条 / 滚动条 / 勾选框早已用令牌（本次无需改）",
      "rgba(__ACCENT__" in _raw and _raw.count("rgba(__ACCENT__") >= 4)
check("G6 默认高亮色仍是朱红（视觉零回退）",
      cfg.ACCENT_DEFAULT.lower() == "#c0392b")

# ============================================================ 汇总
section("汇总")
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("\n失败项：")
    for f in FAIL:
        print("  -", f)
try:
    win.close()
except Exception:                                      # noqa: BLE001
    pass
shutil.rmtree(os.path.join(TMP, "plan_x"), ignore_errors=True)
sys.exit(1 if FAIL else 0)
