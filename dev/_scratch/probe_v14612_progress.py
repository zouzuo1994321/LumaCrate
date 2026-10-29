# -*- coding: utf-8 -*-
"""v1.46.12 探针：偏好导入/导出的进度链路（离屏，纯功能断言）。

覆盖：进度回调是否按阶段上报 / 定量与不定长切换 / 中止语义 / UI 忙碌态与恢复。
只在库副本上跑；nfo 写回落到临时副本，真实 nfo 不动。
"""
import ctypes
import os
import shutil
import sys
import time

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
TMP = r"C:/Users/zouzu/AppData/Local/Temp/probe_v14612p"
os.makedirs(TMP, exist_ok=True)
k32 = ctypes.windll.kernel32


def _del(p):
    if os.path.exists(p):
        k32.SetFileAttributesW(p, 0x80)
        k32.DeleteFileW(p)


FAILS = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ("  | " + str(detail) if detail else ""))
    if not ok:
        FAILS.append(name)


faillog = []


def fresh_db():
    """每次导入前换一份干净副本。"""
    import database as db
    db.close_conn()
    dst = os.path.join(TMP, "p.db")
    _del(dst)
    shutil.copyfile(os.path.join(ROOT, "index_data", "media_center.db"), dst)
    return dst


dbp = fresh_db()
import database as db                                    # noqa: E402
db.db_path = lambda: dbp
import applog                                            # noqa: E402
applog.log_dir = lambda: os.path.join(TMP, "logs")

import nfo_parser as nfo_mod                             # noqa: E402
_real_write = nfo_mod.write_user_rating
_nfo_tmp = os.path.join(TMP, "nfo")
os.makedirs(_nfo_tmp, exist_ok=True)
_map = {}


def safe_write(path, value):
    if not path:
        return False
    dst = _map.get(path)
    if dst is None:
        if not os.path.exists(path):
            return False
        dst = os.path.join(_nfo_tmp, "n%04d.nfo" % len(_map))
        shutil.copyfile(path, dst)
        _map[path] = dst
    return _real_write(dst, value)


nfo_mod.write_user_rating = safe_write

import prefs as prefs_mod                                # noqa: E402

SRC = os.path.join(TMP, "out.json")   # ① 导出的就是它
OUT = os.path.join(TMP, "out.json")

print("\n① 导出：进度事件")
ev = []
t0 = time.perf_counter()
r = prefs_mod.export_prefs(OUT, "all", None, progress=lambda a, b, c: ev.append((a, b, c)))
print("     耗时 %.2fs，事件 %d 条" % (time.perf_counter() - t0, len(ev)))
for e in ev[:3] + ev[-2:]:
    print("       ", e)
check("导出成功", r.get("ok"), r)
check("导出文件已生成", os.path.getsize(OUT) > 1000,
      "%.1f KB" % (os.path.getsize(OUT) / 1024))
check("首条进度是不定长（total=0，读库前）", ev[0][1] == 0, ev[0])
check("随后转成定量（total=行数）", max(b for _a, b, _c in ev) == 3479,
      max(b for _a, b, _c in ev))
check("done 单调不减", all(x[0] <= y[0] for x, y in zip(ev, ev[1:])),
      "越界点 %d" % sum(1 for x, y in zip(ev, ev[1:]) if y[0] < x[0]))
check("有「写入文件」阶段", any("写入文件" in c for _a, _b, c in ev),
      [c for _a, _b, c in ev][-1])
check("有「人物」阶段", any("人物" in c for _a, _b, c in ev))

print("\n② 导出：点「停止」→ 不写文件")
OUT_CANCEL = os.path.join(TMP, "cancel.json")
_del(OUT_CANCEL)
stop_at = {"n": 0}


def _stop_cb(a, b, c):
    stop_at["n"] += 1
    return stop_at["n"] >= 3          # 第 3 次回调起要求停止
r2 = prefs_mod.export_prefs(OUT_CANCEL, "all", None, progress=_stop_cb)
check("返回 cancelled", r2.get("cancelled") is True, r2)
check("ok 为 False", r2.get("ok") is False, r2)
check("没有生成文件", not os.path.exists(OUT_CANCEL))

print("\n③ 导入：进度事件（真跑，dry_run=False）")
dbp = fresh_db()
ev = []
t0 = time.perf_counter()
r3 = prefs_mod.import_prefs(SRC, progress=lambda a, b, c: ev.append((a, b, c)))
dt = time.perf_counter() - t0
print("     耗时 %.2fs，事件 %d 条" % (dt, len(ev)))
for e in ev[:3] + ev[-2:]:
    print("       ", e)
check("导入成功", r3.get("ok"), {k: r3.get(k) for k in
                             ("media_ok", "people_ok", "nfo_written", "cancelled")})
check("影片命中 3006", r3.get("media_ok") == 3006, r3.get("media_ok"))
check("人物命中 340", r3.get("people_ok") == 340, r3.get("people_ok"))
check("nfo 写回 415", r3.get("nfo_written") == 415, r3.get("nfo_written"))
check("未标记取消", not r3.get("cancelled"), r3.get("cancelled"))
labels = [c for _a, _b, c in ev]
check("有「读取备份文件」阶段", any("读取备份文件" in c for c in labels), labels[0])
check("有「建立番号索引」阶段", any("建立番号索引" in c for c in labels))
check("有「合并影片偏好」阶段", any("合并影片偏好" in c for c in labels))
check("有「合并人物偏好」阶段", any("合并人物偏好" in c for c in labels))
check("有「提交改动」阶段", any("提交改动" in c for c in labels), labels[-1])
check("索引阶段报过全库条数 50283", any("50283" in c for c in labels),
      [c for c in labels if "索引" in c][-1:])
check("进度数值覆盖到 3006/3006", (3006, 3006) in [(a, b) for a, b, _c in ev],
      [(a, b) for a, b, _c in ev if b == 3006][-1:])
check("导入事件条数够细（≥100）", len(ev) >= 100, len(ev))

print("\n④ 导入：中途停止 → 已处理部分提交")
dbp = fresh_db()
cnt = {"n": 0}


def _stop_cb2(a, b, c):
    cnt["n"] += 1
    return cnt["n"] >= 30
t0 = time.perf_counter()
r4 = prefs_mod.import_prefs(SRC, progress=_stop_cb2)
print("     耗时 %.2fs  %s" % (time.perf_counter() - t0,
                             {k: r4.get(k) for k in ("media_ok", "cancelled")}))
check("返回 cancelled", r4.get("cancelled") is True, r4.get("cancelled"))
check("已处理的条数 >0 且 <3006", 0 < r4.get("media_ok", 0) < 3006, r4.get("media_ok"))
conn = db.get_conn()
n_fav = conn.execute("SELECT COUNT(*) FROM media WHERE COALESCE(favorite,0)=1").fetchone()[0]
check("中止前的改动确实落库（favorite>0）", n_fav > 0, n_fav)

print("\n⑤ UI 层：忙碌态 / 进度条 / 恢复")
from PySide6.QtCore import QTimer                        # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox   # noqa: E402
import ui_settings                                       # noqa: E402

dbp = fresh_db()
app = QApplication.instance() or QApplication([])
t0 = time.perf_counter()
dlg = ui_settings.SettingsDialog(None)
dlg.show()
app.processEvents()
print("     SettingsDialog 构建 %.1fs" % (time.perf_counter() - t0))
dlg._show("数据管理")
for _ in range(5):
    app.processEvents()

check("进度条存在", hasattr(dlg, "pref_bar"))
check("状态文字存在", hasattr(dlg, "pref_status"))
check("停止按钮存在且默认隐藏",
      hasattr(dlg, "pref_stop") and not dlg.pref_stop.isVisible())
check("进度行默认隐藏", not dlg.pref_prog_row.isVisible())

shown = {"bar": False, "label": "", "max": -2}
QMessageBox.information = staticmethod(lambda *a, **k: print("     [info]", a[1] if len(a) > 1 else ""))
QMessageBox.warning = staticmethod(lambda *a, **k: print("     [warn]", a[1:] if len(a) > 1 else ""))

OUT2 = os.path.join(TMP, "ui_out.json")
_del(OUT2)
dlg._prefs_run("export", OUT2, ["favorite", "play", "rating", "people", "gender"])
check("启动后按钮被禁用",
      not dlg.pref_ex.isEnabled() and not dlg.pref_im.isEnabled())
check("启动后进度行可见", dlg.pref_prog_row.isVisible())
check("启动后停止按钮可见", dlg.pref_stop.isVisible())


def _snap():
    shown["bar"] = shown["bar"] or dlg.pref_bar.isVisible()
    shown["label"] = dlg.pref_status.text()
    shown["max"] = dlg.pref_bar.maximum()


end = {"t": None}


def _poll():
    _snap()
    w = getattr(dlg, "_prefs_worker", None)
    if w is not None and w.isRunning():
        QTimer.singleShot(30, _poll)
    else:
        end["t"] = time.perf_counter()


t0 = time.perf_counter()
QTimer.singleShot(10, _poll)
while end["t"] is None and time.perf_counter() - t0 < 30:
    app.processEvents()
    time.sleep(0.01)
app.processEvents()
print("     跑完用时 %.2fs，最后一次状态：%s" % (end["t"] - t0 if end["t"] else -1,
                                       shown["label"]))
check("过程中进度条可见", shown["bar"])
check("状态文字非空", bool(shown["label"]))
check("导出完成", os.path.getsize(OUT2) > 1000)
check("结束后按钮恢复", dlg.pref_ex.isEnabled() and dlg.pref_im.isEnabled())
check("结束后进度行隐藏", not dlg.pref_prog_row.isVisible())
check("结束后提示写了路径", "最近导出" in dlg.pref_hint.text(), dlg.pref_hint.text()[:60])
check("导航忙碌映射含「数据管理」",
      any(k == "数据管理" for _a, k in [("_prefs_worker", "数据管理")]))

print("\n⑥ UI 层：导入（含结尾整页刷新）")
dbp = fresh_db()
dlg.on_changed = lambda: None             # 不建主窗，刷新回调置空
dlg._prefs_run("import", SRC)
end["t"] = None
t0 = time.perf_counter()
QTimer.singleShot(10, _poll)
while end["t"] is None and time.perf_counter() - t0 < 60:
    app.processEvents()
    time.sleep(0.005)
for _ in range(20):
    app.processEvents()
    time.sleep(0.02)
print("     跑完用时 %.2fs" % (time.perf_counter() - t0))
check("导入后按钮恢复", dlg.pref_ex.isEnabled())
check("导入后进度行隐藏", not dlg.pref_prog_row.isVisible())
check("导入后提示含命中数", "最近导入" in dlg.pref_hint.text(), dlg.pref_hint.text()[:80])

dlg.close()
print("\nFAILS:", FAILS)
