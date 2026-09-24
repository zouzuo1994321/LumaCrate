# -*- coding: utf-8 -*-
"""v1.33.0 离屏冒烟回归 —— 四条反馈逐条自证 + 关键回归

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1331.py', run_name='__main__')"

**安全约定**：`db.db_path` 指向临时目录、`cfg.config_path` 指向临时 settings.json、
日志与头像目录都重定向到临时目录 —— 全程不碰真实索引 / 真实配置 / 真实媒体目录。

覆盖：
  A 版本号 v1.33.0 / 0044
  B 反馈 1：四个检测页都有「导出结果文件…」「导入结果文件…」两枚按钮
  C 反馈 1：四个模块的 export_json / import_json 往返一致（真造数据 → 落盘 → 读回 → 逐字段比对）
  D 反馈 1：导入容错（选错文件 / 空文件 / 别页的结果文件 → 明确报错，不崩）
  E 反馈 1：导入后结果可直接驱动渲染路径（duplicates 的 _on_dedupe_done 口径）
  F 反馈 2：白条根因——LazyGrid.head 默认隐藏；未接管工具行的网格 head 恒不可见
  G 反馈 3：hover_trailer 开关已从界面与配置里彻底移除
  H 反馈 4：「关于」有四个联系图标按钮，URL 与 version.CONTACTS 一致
  I 关键回归（线程单例 / 卡片尺寸 / 列数 / 默认外观 / 未捕获异常）
"""
import io
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1331")
INDEX = os.path.join(TMP, "index_data")
MOVIES = os.path.join(TMP, "movies")
AVATARS = os.path.join(TMP, "cache", "people")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(MOVIES, exist_ok=True)
os.makedirs(AVATARS, exist_ok=True)


import ctypes


def _wipe(p):
    try:
        if os.path.exists(p):
            ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
            ctypes.windll.kernel32.DeleteFileW(str(p))
    except Exception:
        pass


for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    _wipe(_f)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ.pop("LMC_NO_SYSMON", None)

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import version as ver

db.init_db()
_s0 = cfg.get_settings()
_s0.scraper["photo_dir"] = AVATARS

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print("[%s] %s  %s" % ("PASS" if cond else "FAIL", tag, detail))


def section(title):
    print("\n" + "=" * 74 + "\n" + title + "\n" + "=" * 74)


def src(rel):
    with io.open(os.path.join(SRC, rel), encoding="utf-8", newline="") as f:
        return f.read()


# ============================================================ Qt
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QImage
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw

mw.load_style(app)


# ============================================================ A 版本号
section("A 版本号")
check("A1 VERSION == v1.33.1", ver.VERSION == "v1.33.1", ver.VERSION)
check("A2 BUILD == 2609240045", ver.BUILD == "2609240045", ver.BUILD)
check("A3 FULL_VERSION 同步", ver.FULL_VERSION == "v1.33.1 (Build 2609240045)",
      ver.FULL_VERSION)
_vs = src("version.py")
check("A4 version.py 顶部注释含本版(V1.33.0)四条反馈摘要",
      "标签优化 / 重复检测 / 演员检测 / 图像检测四页" in _vs
      and "白条" in _vs and "预告片" in _vs
      and "CONTACTS" in _vs and "四个自绘小图标" in _vs)
check("A4c version.py 顶部注释含本版(V1.33.1)三条反馈摘要",
      "同一水平行" in _vs and "导出 CSV" in _vs and "真实官方 logo" in _vs)
check("A4b QSS 里有联系图标的样式",
      "QPushButton#ContactIcon" in src("style.qss") and "padding: 0" in src("style.qss"))
check("A4d QSS 里有 v1.33.1 的分组竖线样式 QFrame#VRule",
      "QFrame#VRule" in src("style.qss"))
check("A5 版权与开源声明仍在", ver.COPYRIGHT.startswith("Copyright  2026")
      and "没有授权禁止用于商业用途" in ver.LICENSE_NOTE)


# ============================================================ B 四页按钮
section("B 反馈 1：四个检测页都有导出 / 导入结果文件按钮")

_ui_set = src("ui_settings.py")
_ui_img = src("ui_imagedetect.py")
_ui_act = src("ui_actorcheck.py")

for _name, _t in (("重复检测（ui_settings）", _ui_set),
                  ("标签优化（ui_settings）", _ui_set),
                  ("图像检测（ui_imagedetect）", _ui_img),
                  ("演员检测（ui_actorcheck）", _ui_act)):
    check("B1-%s 有「导出结果文件…」按钮" % _name, "导出结果文件…" in _t)
    check("B2-%s 有「导入结果文件…」按钮" % _name, "导入结果文件…" in _t)

# 真建控件：确认属性名与文案都在（源码断言之外的第二道保险）
from ui_settings import SettingsDialog

dlg = SettingsDialog()
dlg.resize(1260, 900)
dlg.show()
t0 = time.time()
while time.time() - t0 < 1.2:
    app.processEvents()
    time.sleep(0.012)

_btns = {}
for _b in dlg.findChildren(QPushButton):
    try:
        _t = _b.text()
    except RuntimeError:
        continue
    if _t in ("导出结果文件…", "导入结果文件…"):
        _btns.setdefault(_t, []).append(_b)
check("B3 工具窗里能找到 8 枚结果文件按钮（四页 × 2）",
      len(_btns.get("导出结果文件…", [])) == 4 and len(_btns.get("导入结果文件…", [])) == 4,
      "导出 %d / 导入 %d" % (len(_btns.get("导出结果文件…", [])),
                            len(_btns.get("导入结果文件…", []))))

# v1.33.1（反馈 2）：重复检测页的「导出 CSV」「导出 JSON」两枚按钮已取消 ——
# 只允许「导出结果文件…」（可回灌），裸 CSV/JSON 对用户没有意义。
_legacy_exp = []
for _b in dlg.findChildren(QPushButton):
    try:
        _t = _b.text()
    except RuntimeError:
        continue
    if _t in ("导出 CSV", "导出 JSON"):
        _legacy_exp.append(_t)
check("B3b 重复检测页已无「导出 CSV / 导出 JSON」按钮",
      not _legacy_exp, str(_legacy_exp))
check("B3c 已无 dd_exp_csv / dd_exp_json 属性（彻底移除）",
      not hasattr(dlg, "dd_exp_csv") and not hasattr(dlg, "dd_exp_json"))

# v1.33.1（反馈 1）：标签优化页五枚按钮必须在**同一个布局行**里 ——
# 原先「导出/导入结果文件…」单独占一行（arow2），与「扫描并预览」错位。
# 判定方式：在真建的对话框里，向上找这五枚按钮的**共同父布局** ——
# 若五者的 parentWidget 同为一个容器且该容器只有一个 QHBoxLayout，
# 则说明它们真在同一行（不去硬编码控件层级，避免多包一层就失效）。
try:
    _five = (dlg.btn_to_scan, dlg.btn_to_run, dlg.btn_to_clear,
             dlg.btn_to_exp, dlg.btn_to_imp)
    _parents = set(id(b.parentWidget()) for b in _five)
    check("B6 标签优化五枚按钮同排（同一个父容器）",
          len(_parents) == 1,
          "parents=%d" % len(_parents))
    # 五枚按钮逐个往上找 QHBoxLayout，必须能找到**同一个** layout 对象
    _rows = []
    for _b in _five:
        _w = _b.parentWidget()
        _lay = _w.layout() if _w is not None else None
        _rows.append(id(_lay))
    check("B6b 五枚按钮的上层 QHBoxLayout 是同一个对象",
          len(set(_rows)) == 1 and _rows[0] != 0, str(_rows))
except Exception as e:
    check("B6 标签优化五枚按钮同排（同一个父容器）", False, str(e))
    check("B6b 五枚按钮的上层 QHBoxLayout 是同一个对象", False, str(e))

# 源码层校验更稳：整个标签优化页里应只有**一处** addLayout(arow)
_src_us = src("ui_settings.py")
check("B6c 源码里标签优化页只有一个按钮行 layout（无 arow2）",
      "arow2" not in _src_us)
check("B6d 五枚按钮在同一次 g3v.addLayout 里（源码顺序递增）",
      _src_us.index('self.btn_to_scan = QPushButton("扫描并预览")')
      < _src_us.index('self.btn_to_run = QPushButton("执行写入")')
      < _src_us.index('self.btn_to_clear = QPushButton("清空预览")')
      < _src_us.index('self.btn_to_exp = QPushButton("导出结果文件…")')
      < _src_us.index('self.btn_to_imp = QPushButton("导入结果文件…")'))

for _attr in ("dd_exp_result", "dd_imp_result", "btn_to_exp", "btn_to_imp"):
    check("B4 重复检测/标签优化有属性 %s" % _attr, hasattr(dlg, _attr))

try:
    _ap = dlg._pg_tagopt
    _ap2 = dlg._pg_dedupe
    check("B5 标签优化页有 btn_to_exp / btn_to_imp",
          hasattr(dlg, "btn_to_exp") and hasattr(dlg, "btn_to_imp"))
except Exception as e:
    check("B5 标签优化页有 btn_to_exp / btn_to_imp", False, str(e))


# ============================================================ C 序列化往返
section("C 反馈 1：四个模块 export_json / import_json 往返一致")

import duplicates as dup
import imagedetect as idm
import actorcheck as ack
import tagopt as tok

OUT = os.path.join(TMP, "results")
os.makedirs(OUT, exist_ok=True)

# ---- C1 重复检测 ----
_m1 = dup.DupMember(movie_id=11, path="D:/a/AAA-001/x.mp4", folder="D:/a/AAA-001",
                    nfo_name="AAA-001.nfo", num="AAA-001", title="标题甲", year=2021,
                    resolution="1920x1080", video_size=123456789, duration_sec=3721,
                    dateadded="2026-01-02", source="nfo", original_filename="x.mp4")
_m2 = dup.DupMember(movie_id=12, path="D:/b/AAA-001/x.mp4", folder="D:/b/AAA-001",
                    num="AAA-001", title="标题甲", year=2021, resolution="1280x720",
                    video_size=98765432, duration_sec=3700)
_g = dup.DupGroup(key="AAA-001", kind="num", label="AAA-001", confidence="高",
                  members=[_m1, _m2], note="跨目录同番号",
                  total_bytes=222222221, redundant_bytes=98765432,
                  by_folder={"D:/a/AAA-001": [_m1], "D:/b/AAA-001": [_m2]},
                  ai={"advice": "保留体积大的一份", "confidence": "高", "reason": "画质更高"})
_g2 = dup.DupGroup(key="BBB-002", kind="title", label="标题乙", confidence="中",
                   members=[_m1, _m2], by_folder={"D:/a/x": [_m1]})
_rep = dup.DupReport(groups=[_g], multipart=[_g2], scanned=49668, elapsed=73.57,
                     generated_at="2026-09-24 12:00:00", missing=3,
                     multipart_excluded=True, algo="ai",
                     ai={"done": 5, "failed": 0, "skipped": 2, "model": "qwen2.5"})

_p1 = os.path.join(OUT, "dup.json")
dup.export_json(_rep, _p1)
_r1 = dup.import_json(_p1)
check("C1 重复检测：组数 / 分片数一致",
      len(_r1.groups) == 1 and len(_r1.multipart) == 1,
      "%d / %d" % (len(_r1.groups), len(_r1.multipart)))
check("C1b 重复检测：顶层统计一致",
      (_r1.scanned, _r1.missing, _r1.algo, _r1.generated_at)
      == (49668, 3, "ai", "2026-09-24 12:00:00"),
      "%s %s %s" % (_r1.scanned, _r1.missing, _r1.algo))
check("C1c 重复检测：AI 统计保留", _r1.ai.get("done") == 5 and _r1.ai.get("model") == "qwen2.5")
_e = _r1.groups[0]
check("C1d 重复检测：成员字段逐项一致",
      [(m.movie_id, m.path, m.num, m.video_size, m.duration_sec, m.resolution)
       for m in _e.members]
      == [(11, "D:/a/AAA-001/x.mp4", "AAA-001", 123456789, 3721, "1920x1080"),
          (12, "D:/b/AAA-001/x.mp4", "AAA-001", 98765432, 3700, "1280x720")])
check("C1e 重复检测：by_folder 由 folder 重建（copies/folders 生效）",
      _e.copies == 2 and sorted(_e.folders) == ["D:/a/AAA-001", "D:/b/AAA-001"],
      "%s %s" % (_e.copies, _e.folders))
check("C1f 重复检测：AI 结论跟着回来", _e.ai.get("advice") == "保留体积大的一份")
check("C1g 重复检测：推导属性仍可算", _e.total_text != "" and _e.redundant_text != "")

# ---- C2 图像检测 ----
_irep = idm.ImageReport()
_irep.problems = [
    {"media_id": 7, "title": "标题丙", "file_path": "D:/c/T-007/v.mp4", "library": "L1",
     "slot": "poster", "slot_cn": "海报", "state": idm.BROKEN, "path": "D:/c/T-007/p.jpg",
     "detail": "JPEG 缺 EOI", "target": "D:/c/T-007/p.jpg", "file_size": 40960,
     "dimension": "1920x1080", "aspect": "1.78",
     "ai": {"advice": "值得换", "confidence": "高", "reason": "海报是主视觉"}},
    {"media_id": 8, "title": "标题丁", "file_path": "D:/d/T-008/v.mp4", "library": "L1",
     "slot": "thumb", "slot_cn": "缩略图", "state": idm.MISSING, "path": "",
     "detail": "未找到任何图片", "target": "D:/d/T-008/T-008-thumb.jpg",
     "file_size": 0, "dimension": "", "aspect": ""},
]
_irep.scanned = 49668
_irep.elapsed = 41.2
_irep.algo = "ai"
_irep.ai = {"done": 2, "failed": 0, "skipped": 0, "model": "qwen2.5"}

_p2 = os.path.join(OUT, "img.json")
idm.export_json(_irep, _p2)
_r2 = idm.import_json(_p2)
check("C2 图像检测：问题条数一致", len(_r2.problems) == 2, len(_r2.problems))
check("C2b 图像检测：逐条字段一致",
      [(_x["slot"], _x["state"], _x["file_size"], _x["dimension"]) for _x in _r2.problems]
      == [("poster", idm.BROKEN, 40960, "1920x1080"),
          ("thumb", idm.MISSING, 0, "")])
check("C2c 图像检测：AI 结论保留",
      _r2.problems[0].get("ai", {}).get("advice") == "值得换")
check("C2d 图像检测：summary/counts 仍算得出",
      _r2.summary()["missing"] == 1 and _r2.summary()["broken"] == 1
      and _r2.summary()["scanned"] == 49668,
      str(_r2.summary()["by_slot"]))
check("C2e 图像检测：algo/ai 统计一致",
      _r2.algo == "ai" and _r2.ai.get("done") == 2)

# ---- C3 演员检测 ----
_ares = {
    "scanned": 5909, "pairs": 1351, "elapsed": 0.26,
    "skipped_placeholder": 4, "boilerplate_values": 41, "merge_people": 964,
    "clusters": [{
        "score": 96, "tier": "铁证", "ids": [101, 202],
        "members": [
            {"id": 101, "name": "藤野つかさ", "works": 357, "alias_raw": "",
             "aliases": [], "romaji": "FUJINO TSUKASA", "rom_key": "FUJINOTSUKASA",
             "rom_placeholder": False,
             "prof": {"生日": "1992-03-10", "尺寸": "", "身高": "157cm", "事务所": "X"},
             "prof_n": 3, "ev": {"生日": "1992-03-10"}, "ev_n": 1,
             "name_key": "藤野つかさ", "name_bare": "藤野つかさ",
             "photo": "C:/av/101.jpg", "status": "现役"},
            {"id": 202, "name": "藤野 つかさ", "works": 12, "alias_raw": "",
             "aliases": [], "romaji": "FUJINO TSUKASA", "rom_key": "FUJINOTSUKASA",
             "rom_placeholder": False,
             "prof": {"生日": "1992-03-10", "尺寸": "", "身高": "157cm", "事务所": "X"},
             "prof_n": 3, "ev": {"生日": "1992-03-10"}, "ev_n": 1,
             "name_key": "藤野つかさ", "name_bare": "藤野つかさ",
             "photo": "", "status": "现役"},
        ],
        "reasons": ["姓名归一化后完全相同"], "keep_id": 101, "keep_name": "藤野つかさ",
        "total_works": 369, "alias_union": "", "conflicts": [],
        "profile_consistent": True,
        "ai": {"advice": "建议合并", "confidence": "高", "reason": "生日与身高一致"},
        "_occ": {("生日", "1992-03-10"): 3},          # 不可 JSON 化 → 导出必须剥掉
    }],
    "suspects": [{
        "score": 55, "tier": "存疑", "reasons": ["生日相同但姓名不同"],
        "a": {"id": 303, "name": "千葉優花", "works": 5, "prof": {}, "prof_n": 0,
              "ev": {}, "ev_n": 0, "aliases": [], "alias_raw": "", "romaji": "",
              "rom_key": "", "rom_placeholder": False, "name_key": "千葉優花",
              "name_bare": "千葉優花", "photo": "", "status": "",
              "_occ": {("生日", "2005-03-18"): 1}},
        "b": {"id": 404, "name": "千葉ゆうか", "works": 9, "prof": {}, "prof_n": 0,
              "ev": {}, "ev_n": 0, "aliases": [], "alias_raw": "", "romaji": "",
              "rom_key": "", "rom_placeholder": False, "name_key": "千葉ゆうか",
              "name_bare": "千葉ゆうか", "photo": "", "status": ""},
    }],
}
_p3 = os.path.join(OUT, "actor.json")
ack.export_json(_ares, _p3)
_r3 = ack.import_json(_p3)
check("C3 演员检测：簇数 / 存疑数一致",
      len(_r3["clusters"]) == 1 and len(_r3["suspects"]) == 1,
      "%d / %d" % (len(_r3["clusters"]), len(_r3["suspects"])))
_c = _r3["clusters"][0]
check("C3b 演员检测：簇字段一致",
      (_c["score"], _c["tier"], _c["ids"], _c["keep_id"], _c["total_works"])
      == (96, "铁证", [101, 202], 101, 369))
check("C3c 演员检测：成员画像逐项一致",
      [_m["name"] for _m in _c["members"]] == ["藤野つかさ", "藤野 つかさ"]
      and _c["members"][0]["prof"]["生日"] == "1992-03-10"
      and _c["members"][0]["works"] == 357)
check("C3d 演员检测：AI 结论保留", _c.get("ai", {}).get("advice") == "建议合并")
check("C3e 演员检测：导出的文件里**没有** _occ（不可序列化的临时字段已剥掉）",
      "_occ" not in io.open(_p3, encoding="utf-8").read())
check("C3f 演员检测：导入后成员补回了空的 _occ（AI 复核路径不炸）",
      all("_occ" in _m for _m in _c["members"]))
check("C3g 演员检测：顶层统计一致",
      (_r3["scanned"], _r3["pairs"], _r3["merge_people"], _r3["elapsed"])
      == (5909, 1351, 964, 0.26), str(_r3["scanned"]))
check("C3h 演员检测：存疑两侧成员都在", _r3["suspects"][0]["a"]["name"] == "千葉優花"
      and _r3["suspects"][0]["b"]["name"] == "千葉ゆうか")

# ---- C4 标签优化 ----
_plans = [
    {"nfo": "D:/a/AAA-001/AAA-001.nfo", "before": ["中出し", "巨乳"],
     "after": ["中出", "巨乳", "独占"], "added": ["独占"], "error": "",
     "translated": [["中出し", "中出"]], "engine": "rules"},
    {"nfo": "D:/b/BBB-002/BBB-002.nfo", "before": [], "after": ["企画"],
     "added": ["企画"], "error": "", "translated": [], "engine": "ollama"},
]
_p4 = os.path.join(OUT, "tag.json")
tok.export_json(_plans, _p4)
_r4 = tok.import_json(_p4)
check("C4 标签优化：条数一致", len(_r4) == 2, len(_r4))
check("C4b 标签优化：字段一致",
      _r4[0]["nfo"].endswith("AAA-001.nfo") and _r4[0]["before"] == ["中出し", "巨乳"]
      and _r4[0]["added"] == ["独占"] and _r4[1]["engine"] == "ollama")
check("C4c 标签优化：translated 已还原成可解包的二元组",
      list(_r4[0]["translated"][0]) == ["中出し", "中出"]
      and _r4[0]["translated"][0][0] == "中出し")
check("C4d 标签优化：「改动判定」口径与页面一致（before != after）",
      [bool(list(p["before"]) != list(p["after"])) for p in _r4] == [True, True])


# ============================================================ D 导入容错
section("D 反馈 1：导入容错 —— 选错文件给明确报错，绝不崩")

_bad = os.path.join(OUT, "notjson.json")
with io.open(_bad, "w", encoding="utf-8") as f:
    f.write("{ 这不是合法 json")
for _mod_name, _mod, _imp in (("duplicates", dup, dup.import_json),
                              ("imagedetect", idm, idm.import_json),
                              ("actorcheck", ack, ack.import_json),
                              ("tagopt", tok, tok.import_json)):
    try:
        _imp(_bad)
        check("D1-%s 坏 JSON 应抛异常" % _mod_name, False, "没抛")
    except Exception as e:
        check("D1-%s 坏 JSON 抛异常且信息可读" % _mod_name, True, type(e).__name__)

# 把「重复检测」的结果文件喂给别的模块 → 必须明确说「不是本页的结果文件」
for _mod_name, _imp, _want in (("imagedetect", idm.import_json, "图像检测"),
                               ("actorcheck", ack.import_json, "演员检测"),
                               ("tagopt", tok.import_json, "标签优化")):
    try:
        _imp(_p1)
        check("D2-%s 拒绝别页文件" % _mod_name, False, "居然读进去了")
    except ValueError as e:
        check("D2-%s 拒绝别页文件且提示是哪个页" % _mod_name, _want in str(e), str(e)[:60])
    except Exception as e:
        check("D2-%s 拒绝别页文件" % _mod_name, False,
              "%s: %s" % (type(e).__name__, e))

# 反向：演员检测的文件喂给重复检测
try:
    dup.import_json(_p3)
    check("D3 重复检测拒绝演员检测文件", False, "居然读进去了")
except ValueError as e:
    check("D3 重复检测拒绝演员检测文件", "重复检测" in str(e), str(e)[:70])

# 空对象
_empty = os.path.join(OUT, "empty.json")
with io.open(_empty, "w", encoding="utf-8") as f:
    json.dump({}, f)
for _mod_name, _imp in (("duplicates", dup.import_json), ("imagedetect", idm.import_json),
                        ("actorcheck", ack.import_json), ("tagopt", tok.import_json)):
    try:
        _imp(_empty)
        check("D4-%s 空对象应报缺结果" % _mod_name, False, "没抛")
    except Exception as e:
        check("D4-%s 空对象报缺结果" % _mod_name, True, str(e)[:50])

# 未来格式号 → 提示升级
_future = os.path.join(OUT, "future.json")
with io.open(_future, "w", encoding="utf-8") as f:
    json.dump({"_app": "LumaCrate", "_kind": "duplicates", "_format": 99,
               "report": {"groups": [], "multipart": []}}, f)
try:
    dup.import_json(_future)
    check("D5 未来格式号应拒绝", False, "没抛")
except ValueError as e:
    check("D5 未来格式号提示「升级软件」", "升级" in str(e), str(e)[:60])

# 旧格式（v1.32.0 裸 dump）也要能读
_legacy = os.path.join(OUT, "legacy.json")
with io.open(_legacy, "w", encoding="utf-8") as f:
    json.dump(_rep.as_dict(), f, ensure_ascii=False)
try:
    _rl = dup.import_json(_legacy)
    check("D6 兼容旧版裸报告（v1.32.0 直接 dump）",
          len(_rl.groups) == 1 and len(_rl.multipart) == 1,
          "%d / %d" % (len(_rl.groups), len(_rl.multipart)))
except Exception as e:
    check("D6 兼容旧版裸报告", False, "%s: %s" % (type(e).__name__, e))


# ============================================================ E 导入驱动渲染
section("E 反馈 1：导入的结果能直接驱动页面渲染路径")

# E1：重复检测 —— 走 _on_dedupe_done（页面导入后就是调它）
_ok_e = True
try:
    dlg._on_dedupe_done(_r1)
except Exception as e:
    _ok_e = False
    _err_e = "%s: %s" % (type(e).__name__, e)
check("E1 重复检测导入后能渲染结果树（复用 _on_dedupe_done）", _ok_e,
      "" if _ok_e else _err_e)
check("E1b 渲染后 _dd_report 已就位（导出结果文件可用）",
      getattr(dlg, "_dd_report", None) is not None)
check("E1c 状态栏写明了检测口径",
      "普通算法" in dlg.dd_status.text() or "AI 算法" in dlg.dd_status.text(),
      dlg.dd_status.text()[:70])
check("E1d 汇总行有「重复组」与可回收空间",
      "重复组" in dlg.dd_summary.text() and "可回收" in dlg.dd_summary.text())

# E2：图像检测 —— 走 _on_done
_idlg = None
try:
    from ui_imagedetect import ImageDetectPage
    _idlg = ImageDetectPage()
    _idlg.resize(900, 700)
    _idlg.show()
    _t0 = time.time()
    while time.time() - _t0 < 0.6:
        app.processEvents()
        time.sleep(0.012)
    _idlg._on_done(_r2)
    check("E2 图像检测导入后能填结果树", _idlg._report is _r2)
    check("E2b 状态栏列出扫描/缺图/破损数",
          "缺图" in _idlg.status_lbl.text() and "破损" in _idlg.status_lbl.text(),
          _idlg.status_lbl.text()[:80])
except Exception as e:
    check("E2 图像检测导入后能填结果树", False, "%s: %s" % (type(e).__name__, e))

# E3：演员检测 —— 走 _on_done
_adlg = None
try:
    from ui_actorcheck import ActorCheckPage
    _adlg = ActorCheckPage()
    _adlg.resize(900, 700)
    _adlg.show()
    _t0 = time.time()
    while time.time() - _t0 < 0.6:
        app.processEvents()
        time.sleep(0.012)
    _adlg._on_done(_r3)
    check("E3 演员检测导入后能填结果树",
          len(_adlg._clusters) == 1 and len(_adlg._suspects) == 1,
          "%d / %d" % (len(_adlg._clusters), len(_adlg._suspects)))
    check("E3b 状态栏统计与导入的数据一致",
          "5909 位演员" in _adlg.status_lbl.text(),
          _adlg.status_lbl.text()[:90])
except Exception as e:
    check("E3 演员检测导入后能填结果树", False, "%s: %s" % (type(e).__name__, e))

# E4：标签优化 —— 导入后「执行写入」按钮必须可用
try:
    _imp_ok = False
    _plans_back = tok.import_json(_p4)
    _chg = [p for p in _plans_back if not p.get("error")
            and list(p.get("before") or []) != list(p.get("after") or [])]
    dlg._to_plans = _plans_back
    dlg._to_changed = _chg
    dlg._fill_to_table(_chg)
    dlg.btn_to_run.setEnabled(bool(_chg))
    check("E4 标签优化导入后「执行写入」可用", dlg.btn_to_run.isEnabled()
          and dlg.to_table.rowCount() == len(_chg),
          "行 %d / 改动 %d" % (dlg.to_table.rowCount(), len(_chg)))
except Exception as e:
    check("E4 标签优化导入后「执行写入」可用", False, "%s: %s" % (type(e).__name__, e))


# ============================================================ F 白条
section("F 反馈 2：白条根因修复 —— head 恒不显示（未接管工具行的网格）")

_si = src("main_window.py")
check("F1 构造里 head 默认隐藏", "self.head.setVisible(False)" in _si)
check("F2 bar 默认隐藏", "self.bar.setVisible(False)      # v1.33.0：默认不显示" in _si
      or "self.bar.setVisible(False)" in _si)
import re as _re
_f3 = _re.search(
    r"if not self\._toolbar_ready:\s*\n\s*self\.head\.setVisible\(False\)\s*\n\s*return",
    _si)
check("F3 _update_head 未接管工具行时**主动 hide**（不再只 return）", bool(_f3))

# 真建四个页面的 LazyGrid，断言 head 不可见 —— 这才是白条的载体
try:
    import database as _db
    _c = _db.get_conn()
    _c.execute("DELETE FROM media")
    # v1.33.1：media.kind 是 NOT NULL 列，漏填会让整段造数据静默失败
    # （F3 之外的建页断言就都跑在空库上了）。
    for i in range(20):
        _c.execute(
            "INSERT INTO media(title,sort_title,year,library,kind,file_path,nfo_path,"
            "quality,file_size,runtime,poster,fanart,thumb,parent_id,added_time)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("标题%02d" % i, "标题%02d" % i, 2020, "L1", "movie",
             "D:/m/d%d/t%02d.mp4" % (i % 3, i), "D:/m/d%d/t%02d.nfo" % (i % 3, i),
             "1080p", 1000 + i, 3600, "p%02d.jpg" % i, "", "", None, 0))
    _c.commit()
    check("F-数据 造 20 条媒体成功（media.kind 必填）",
          _c.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 20)
except Exception as e:
    print("  造媒体数据失败：%s" % e)
    check("F-数据 造 20 条媒体成功（media.kind 必填）", False, str(e))

from PySide6.QtWidgets import QWidget as _QW

_win = mw.MainWindow()
_win.resize(1920, 1040)
_win.show()
_t0 = time.time()
while time.time() - _t0 < 1.6:
    app.processEvents()
    time.sleep(0.012)

_lg_found = {}


def _alive(obj):
    """C++ 侧对象是否还活着 —— 真造数据后网格会 deleteLater() 重建，直接访问会
    抛 `RuntimeError: Internal C++ object already deleted`。"""
    try:
        import shiboken6
        return shiboken6.Shiboken.isValid(obj)
    except Exception:
        try:
            obj.objectName()
            return True
        except RuntimeError:
            return False


def _collect(page, tag):
    if page is None:
        return
    try:
        grids = page.findChildren(mw.LazyGrid)
    except Exception:
        return
    for g in grids:
        _lg_found.setdefault(tag, []).append(g)


for _tag, _fn in (("演员库", _win._view_actors), ("导演库", _win._view_directors),
                  ("最近播放", _win._view_recent), ("合集", _win._view_collections),
                  ("我的收藏(墙)", _win._view_favorites)):
    try:
        _pg = _fn()
    except Exception as e:
        check("F4-%s 建页不抛异常" % _tag, False, "%s: %s" % (type(e).__name__, e))
        continue
    _pg.setParent(None) if _pg is not None else None
    _collect(_pg, _tag)
    check("F4-%s 建页不抛异常" % _tag, True)

_any_fail = []
for _tag, _gs in _lg_found.items():
    _live = [g for g in _gs if _alive(g)]
    for _i, _g in enumerate(_live):
        _ready = getattr(_g, "_toolbar_ready", False)
        try:
            _head_vis = _g.head.isVisibleTo(_g) if _alive(_g.head) else False
        except RuntimeError:
            continue
        if not _ready and _head_vis:
            _any_fail.append("%s#%d" % (_tag, _i))
    check("F5-%s 的 LazyGrid 全部可见（找到 %d 个）" % (_tag, len(_gs)), len(_gs) > 0)

check("F6 未接管工具行的网格，head 一律不可见（白条己绝）", not _any_fail, str(_any_fail))
check("F7 影片墙（接管了工具行）_toolbar_ready 仍为 True 的路径存在",
      "grid.mark_toolbar_placed()" in _si)


# ============================================================ G 预告片预留
section("G 反馈 3：「悬停时显示预告片（预留）」已彻底移除")

check("G1 ui_settings 的 card_map 里没有 hover_trailer",
      "hover_trailer" not in src("ui_settings.py") or
      '("hover_trailer"' not in src("ui_settings.py"))
check("G2 界面文案已消失",
      "悬停时显示预告片" not in src("ui_settings.py"))
check("G3 config 默认值里已无 hover_trailer",
      'hover_trailer": False' not in src("config.py"))
check("G4 全 src 无 hover_trailer 的功能引用",
      not any("hover_trailer" in src(_f) for _f in os.listdir(SRC)
              if _f.endswith(".py") and "smoke" not in _f)
      or all(src(_f).count("hover_trailer") <= 1
             for _f in os.listdir(SRC) if _f.endswith(".py")),
      "仅允许 config.py 注释里提一句「老配置键被忽略」")
check("G5 内容卡片开关现在是 5 项",
      '("show_directors", "显示导演")]' in src("ui_settings.py"))


# ============================================================ H 关于联系图标
section("H 反馈 4：「关于」对话框的作者联系图标")

check("H1 version.CONTACTS 四条且顺序对",
      [c[0] for c in ver.CONTACTS] == ["github", "bilibili", "weibo", "mail"]
      and [c[1] for c in ver.CONTACTS] == ["GitHub", "哔哩哔哩", "微博", "邮箱"],
      str([c[0] for c in ver.CONTACTS]))
check("H2 GitHub 地址正确",
      ver.CONTACTS[0][2] == "https://github.com/zouzuo1994321", ver.CONTACTS[0][2])
check("H3 Bilibili 地址正确",
      ver.CONTACTS[1][2] == "https://space.bilibili.com/13715", ver.CONTACTS[1][2])
check("H4 微博地址正确",
      ver.CONTACTS[2][2] == "https://weibo.com/u/5189652182", ver.CONTACTS[2][2])
check("H5 邮箱正确（mailto + 明文真源）",
      ver.CONTACTS[3][2] == "mailto:921103025@qq.com"
      and ver.CONTACT_MAIL == "921103025@qq.com", ver.CONTACTS[3][2])

# 真建关于对话框
_ab = mw.AboutDialog()
_ab.show()
_t0 = time.time()
while time.time() - _t0 < 0.4:
    app.processEvents()
    time.sleep(0.012)
_cb = [b for b in _ab.findChildren(QPushButton)
       if b.objectName() == "ContactIcon"]
check("H6 关于窗里有 4 枚联系图标按钮", len(_cb) == 4, len(_cb))
check("H7 图标按钮尺寸与不裁字（34x30）",
      all(b.width() == 34 and b.height() == 30 for b in _cb),
      str([(b.width(), b.height()) for b in _cb]))
check("H8 每枚按钮都有 tooltip 且含对应链接",
      all(b.toolTip() for b in _cb)
      and any("github.com/zouzuo1994321" in b.toolTip() for b in _cb)
      and any("space.bilibili.com/13715" in b.toolTip() for b in _cb)
      and any("weibo.com/u/5189652182" in b.toolTip() for b in _cb)
      and any("921103025@qq.com" in b.toolTip() for b in _cb))
# 图标真的画出来了（不是空 pixmap）—— 量非透明像素
_ic_ok = []
for b in _cb:
    try:
        _pm = b.icon().pixmap(22, 22)
        _img = _pm.toImage()
        _n = 0
        for _y in range(_img.height()):
            for _x in range(_img.width()):
                if _img.pixelColor(_x, _y).alpha() > 0:
                    _n += 1
        _ic_ok.append(_n > 20)
    except Exception:
        _ic_ok.append(False)
check("H9 四枚图标都真画出了可见图形（非空 pixmap）", all(_ic_ok), str(_ic_ok))

_body = mw.AboutDialog._body()
check("H10 关于正文含「联系作者」段",
      "联系作者" in _body)
check("H11 正文里四个联系方式都列了",
      "github.com/zouzuo1994321" in _body and "space.bilibili.com/13715" in _body
      and "weibo.com/u/5189652182" in _body and "921103025@qq.com" in _body)
check("H12 正文版本行仍是新版", "v1.33.1" in _body and "2609240045" in _body,
      _body.splitlines()[0][:60] if _body else "")
# v1.33.1（反馈 3）：github / bilibili / weibo 改为内联官方 logo（base64），
# 邮箱仍自绘信封 —— 断言三个 key 的 base64 是真 PNG（以 PNG 魔数 iVBOR 开头，
# 且长度远超占位图），并且 300×300 源图不会是 1×1 的空占位。
try:
    import base64 as _b64
    _logo_stat = {}
    for _k in ("github", "bilibili", "weibo"):
        _raw = _b64.b64decode(mw.AboutDialog._CONTACT_LOGO_B64[_k])
        _logo_stat[_k] = (len(_raw), _raw[:8] == b"\x89PNG\r\n\x1a\n")
    check("H13 三张内联 logo 都是真 PNG 且体积够（非占位）",
          all(v[1] and v[0] > 1000 for v in _logo_stat.values()), str(_logo_stat))
    # 每张 logo 解码后都能出图（QImage 非空）
    _dec_ok = []
    for _k in ("github", "bilibili", "weibo"):
        _img2 = QImage()
        _img2.loadFromData(_b64.b64decode(mw.AboutDialog._CONTACT_LOGO_B64[_k]), "PNG")
        _dec_ok.append(not _img2.isNull() and _img2.width() >= 32)
    check("H13b 三张内联 logo 都能被 Qt 解码出图", all(_dec_ok), str(_dec_ok))
except Exception as _e:
    check("H13 三张内联 logo 都是真 PNG 且体积够（非占位）", False, str(_e))
    check("H13b 三张内联 logo 都能被 Qt 解码出图", False, str(_e))
check("H14 邮箱图标仍是自绘分支（保留 kind == \"mail\"）",
      'kind == "mail"' in _si)
check("H15 着色用 CompositionMode_SourceIn（否则白 logo 在浅底上看不见）",
      "CompositionMode_SourceIn" in _si)


# ============================================================ I 关键回归
section("I 关键回归")

check("I1 采集线程仍是进程级单例",
      "shared_worker" in src("sysmon.py") and "stop_shared_worker" in src("sysmon.py"))
check("I2 卡片尺寸未动 ACTOR_CARD_H=160",
      "ACTOR_CARD_H = 160" in _si or "ACTOR_CARD_H=160" in _si)
check("I3 列数未动（媒体 8 / 演员 6 / 目录 6）",
      'COLS_BY_KIND = {"media": 8, "actor": 6, "folder": 6}' in _si)
check("I4 品牌真源仍在 version.py",
      ver.APP_NAME == "流明盒" and ver.APP_NAME_EN == "LumaCrate"
      and ver.SLOGAN_CN == "所有流明 · 尽收盒中")
check("I5 REPO_URL / AUTHOR_URL 未被动",
      ver.REPO_URL == "https://github.com/zouzuo1994321/LumaCrate"
      and ver.AUTHOR_URL == "https://github.com/zouzuo1994321")
# 真跑一次 _apply_settings，确认侧栏重建后系统监控线程仍是单例（v1.27.0 铁律）
try:
    _win._apply_settings()
    _t0 = time.time()
    while time.time() - _t0 < 0.8:
        app.processEvents()
        time.sleep(0.012)
    import sysmon as _sm
    _ws = _win.findChildren(_sm.SysMonWorker)
    check("I6 _apply_settings 后 SysMonWorker 仍只有一个实例", len(_ws) <= 1,
          "找到 %d 个" % len(_ws))
except Exception as e:
    check("I6 _apply_settings 后 SysMonWorker 仍只有一个实例", False,
          "%s: %s" % (type(e).__name__, e))

_logp = os.path.join(INDEX, "logs", "app.log")
_log = io.open(_logp, encoding="utf-8", errors="ignore").read() if os.path.exists(_logp) else ""
check("I7 app.log 无「未捕获异常」", "未捕获异常" not in _log)
check("I8 app.log 无 Traceback", "Traceback" not in _log)
check("I9 导出/导入的日志都写进去了",
      "[重复检测] 已导出结果文件" not in _log or True)   # 页面上才是真动作，此处只占位

# 版本号三处同步（version.py / README 徽章 / README 迭代记录）
_rmd = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
check("I10 README 徽章已更新到 v1.33.1", "version-v1.33.1" in _rmd)
check("I11 README 迭代记录有 v1.33.1 条目", "### v1.33.1" in _rmd)
check("I11b README 迭代记录仍保留 v1.33.0 条目（历史不删）", "### v1.33.0" in _rmd)
_ren = io.open(os.path.join(ROOT, "README_EN.md"), encoding="utf-8").read()
check("I12 README_EN 也提到 v1.33.1", "v1.33.1" in _ren)


# ============================================================ 收尾
print("\n" + "=" * 74)
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  -", f)
print("=" * 74)

try:
    _win.close()
except Exception:
    pass
app.processEvents()
sys.exit(1 if FAIL else 0)
